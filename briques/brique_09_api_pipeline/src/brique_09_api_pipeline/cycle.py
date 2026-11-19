"""Cycle incrémental de détection puis de scoring, sans recalcul global.

Principe (vérifié sur les règles de B4) : l'état de chaque règle est tenu par
compte pivot. Pour chaque compte touché par de nouvelles transactions, on
relit son historique depuis le début de son épisode d'activité, on fait
tourner le moteur B4 (inchangé) sur ce sous-ensemble, on ne garde que les
événements des comptes touchés, puis on dédoublonne par chevauchement
d'intervalle avant insertion. Détections nouvelles et curseur avancent dans
la MÊME transaction SQL : un cycle interrompu puis rejoué ne duplique rien.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
from brique_01_postgresql.tenant_provisioning import validate_schema_name
from brique_04_detection.modeles import DetectionEvent, TransactionObservee
from brique_04_detection.moteur import detecter_sequentiellement
from brique_05_scoring_alertes.agregation import agreger_par_compte
from brique_05_scoring_alertes.lecture import lire_detections_fenetre
from brique_05_scoring_alertes.persistence import enregistrer_scores
from brique_05_scoring_alertes.seuils import FENETRE_JOURS

from brique_09_api_pipeline.episodes import ETAPES, debut_episode
from brique_09_api_pipeline.verrous import CLASSE_CYCLE, CLASSE_INGESTION, cle_tenant

_DEPUIS_TOUJOURS = datetime(1900, 1, 1, tzinfo=UTC)
_JUSQU_A_LA_FIN = datetime(9999, 12, 31, tzinfo=UTC)

_BORNE = "SELECT COALESCE(max(seq), 0) FROM {schema}.ingestion_keys"
_CURSEUR_INIT = (
    "INSERT INTO {schema}.pipeline_cursor (singleton, last_seq) VALUES (true, 0) "
    "ON CONFLICT DO NOTHING"
)
_CURSEUR_LIRE = "SELECT last_seq FROM {schema}.pipeline_cursor WHERE singleton FOR UPDATE"
_CURSEUR_MAJ = (
    "UPDATE {schema}.pipeline_cursor SET last_seq = $1, updated_at = now() WHERE singleton"
)
_NOUVELLES = """
    SELECT t.sender_account, t.receiver_account, t.occurred_at
    FROM {schema}.ingestion_keys k
    JOIN {schema}.transactions t
      ON t.transaction_id = k.transaction_id AND t.occurred_at = k.occurred_at
    WHERE k.seq > $1 AND k.seq <= $2
"""
_HISTORIQUE = """
    SELECT t.transaction_id, t.sender_account, t.receiver_account, t.amount, t.channel,
           t.occurred_at
    FROM unnest($1::text[], $2::timestamptz[], $3::timestamptz[]) AS q(acct, lb, ub)
    JOIN {schema}.transactions t
      ON t.sender_account = q.acct
     AND t.occurred_at >= q.lb AND t.occurred_at < q.ub AND t.occurred_at >= $4
    UNION
    SELECT t.transaction_id, t.sender_account, t.receiver_account, t.amount, t.channel,
           t.occurred_at
    FROM unnest($1::text[], $2::timestamptz[], $3::timestamptz[]) AS q(acct, lb, ub)
    JOIN {schema}.transactions t
      ON t.receiver_account = q.acct
     AND t.occurred_at >= q.lb AND t.occurred_at < q.ub AND t.occurred_at >= $4
"""
_DETECTIONS_CONNUES = """
    SELECT pattern_type, compte_pivot, fenetre_debut, fenetre_fin
    FROM {schema}.detections
    WHERE compte_pivot = ANY($1::text[]) AND fenetre_fin >= $2 AND fenetre_debut <= $3
"""
_INSERT_DETECTION = """
    INSERT INTO {schema}.detections
        (detection_id, tenant_id, country_code, data_classification, pattern_type,
         transaction_ids, compte_pivot, fenetre_debut, fenetre_fin, details)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
"""
_METADONNEES = """
    SELECT tenant_id, country_code, data_classification
    FROM shared.tenants_registry WHERE tenant_id = $1 AND is_active = true
"""


class CycleDejaEnCours(Exception):
    """Un autre cycle du même tenant est en cours (refus rapide, 409)."""


@dataclass
class ResultatCycle:
    nouvelles_transactions: int = 0
    comptes_touches: int = 0
    transactions_relues: int = 0
    detections_nouvelles: int = 0
    replis_episode: int = 0
    episodes_tronques: int = 0
    comptes_scores: int = 0
    alertes_creees: int = 0
    alertes_mises_a_jour: int = 0


async def _charger_episodes(
    connexion: asyncpg.Connection,
    schema: str,
    touches: dict[str, datetime],
    episode_max: timedelta | None = None,
) -> tuple[dict[UUID, TransactionObservee], int, int]:
    """Relit, pour chaque compte touché, son historique depuis son épisode.

    Lecture PAR TRANCHES : à chaque élargissement (6 h, 24 h, 96 h, tout), seule
    la tranche plus ancienne [lb, ub) est lue ; les lignes déjà reçues sont
    conservées. Une ligne n'est rattachée à un compte que dans sa propre tranche,
    ce qui évite tout doublon entre élargissements.
    """
    brut: dict[UUID, tuple[str, str, float, str, datetime]] = {}
    horodatages: dict[str, list[tuple[datetime, UUID]]] = {c: [] for c in touches}
    etape_de: dict[str, int] = dict.fromkeys(touches, 0)
    borne_de: dict[str, datetime] = {}
    plafond_de: dict[str, datetime] = dict.fromkeys(touches, _JUSQU_A_LA_FIN)
    retenus: dict[str, list[UUID]] = {}
    a_traiter = set(touches)
    replis = 0
    tronques = 0
    requete = _HISTORIQUE.format(schema=schema)
    while a_traiter:
        comptes = sorted(a_traiter)
        for compte in comptes:
            largeur = ETAPES[etape_de[compte]]
            borne_de[compte] = _DEPUIS_TOUJOURS if largeur is None else touches[compte] - largeur
        bornes = [borne_de[c] for c in comptes]
        plafonds = [plafond_de[c] for c in comptes]
        lignes = await connexion.fetch(requete, comptes, bornes, plafonds, min(bornes))
        for enregistrement in lignes:
            identifiant, emetteur, destinataire, montant, canal, quand = tuple(enregistrement)
            if identifiant not in brut:
                brut[identifiant] = (emetteur, destinataire, float(montant), canal, quand)
            for compte in {emetteur, destinataire}:
                if compte in a_traiter and borne_de[compte] <= quand < plafond_de[compte]:
                    horodatages[compte].append((quand, identifiant))
        suivants: set[str] = set()
        for compte in comptes:
            historique = sorted(horodatages[compte])
            largeur = ETAPES[etape_de[compte]]
            debut, besoin = debut_episode(
                [h[0] for h in historique],
                touches[compte],
                None if largeur is None else borne_de[compte],
            )
            if besoin and etape_de[compte] + 1 < len(ETAPES):
                suivante = ETAPES[etape_de[compte] + 1]
                if episode_max is not None and (suivante is None or suivante > episode_max):
                    tronques += 1  # plafond atteint : épisode tronqué, compté
                    retenus[compte] = [identifiant for _, identifiant in historique[debut:]]
                    continue
                plafond_de[compte] = borne_de[compte]  # prochaine tranche : plus ancienne
                etape_de[compte] += 1
                if ETAPES[etape_de[compte]] is None:
                    replis += 1
                suivants.add(compte)
                continue
            retenus[compte] = [identifiant for _, identifiant in historique[debut:]]
        a_traiter = suivants
    selection: dict[UUID, TransactionObservee] = {}
    for identifiants in retenus.values():
        for identifiant in identifiants:
            if identifiant not in selection:
                emetteur, destinataire, montant, canal, quand = brut[identifiant]
                selection[identifiant] = TransactionObservee(
                    transaction_id=identifiant,
                    sender_account=emetteur,
                    receiver_account=destinataire,
                    amount=montant,
                    channel=canal,
                    occurred_at=quand,
                )
    return selection, replis, tronques


async def _filtrer_deja_connus(
    connexion: asyncpg.Connection, schema: str, evenements: list[DetectionEvent]
) -> list[DetectionEvent]:
    """Garde les événements sans détection de même (pattern, compte) qui chevauche."""
    if not evenements:
        return []
    comptes = sorted({e.compte_pivot for e in evenements if e.compte_pivot})
    bas = min(e.fenetre_debut for e in evenements)
    haut = max(e.fenetre_fin for e in evenements)
    lignes = await connexion.fetch(_DETECTIONS_CONNUES.format(schema=schema), comptes, bas, haut)
    connus: dict[tuple[str, str], list[tuple[datetime, datetime]]] = {}
    for ligne in lignes:
        connus.setdefault((ligne["pattern_type"], ligne["compte_pivot"]), []).append(
            (ligne["fenetre_debut"], ligne["fenetre_fin"])
        )
    nouveaux: list[DetectionEvent] = []
    for evenement in evenements:
        cle = (evenement.pattern_type, evenement.compte_pivot or "")
        intervalles = connus.setdefault(cle, [])
        if any(d <= evenement.fenetre_fin and evenement.fenetre_debut <= f for d, f in intervalles):
            continue
        intervalles.append((evenement.fenetre_debut, evenement.fenetre_fin))
        nouveaux.append(evenement)
    return nouveaux


async def executer_cycle(
    pool: asyncpg.Pool,
    schema: str,
    tenant_id: UUID,
    episode_max: timedelta | None = None,
) -> ResultatCycle:
    validate_schema_name(schema)
    cle = cle_tenant(tenant_id)
    resultat = ResultatCycle()

    # Phase 0 : borne de lecture. Le verrou exclusif attend la fin des lots
    # d'ingestion en cours (qui tiennent le verrou partagé) : tout seq <= borne
    # est donc validé, aucune ligne de seq inférieur ne peut apparaître après.
    async with pool.acquire() as connexion, connexion.transaction():
        await connexion.execute("SELECT pg_advisory_xact_lock($1, $2)", CLASSE_INGESTION, cle)
        borne = await connexion.fetchval(_BORNE.format(schema=schema))

    async with pool.acquire() as connexion, connexion.transaction():
        verrou_obtenu = await connexion.fetchval(
            "SELECT pg_try_advisory_xact_lock($1, $2)", CLASSE_CYCLE, cle
        )
        if not verrou_obtenu:
            raise CycleDejaEnCours
        await connexion.execute(_CURSEUR_INIT.format(schema=schema))
        curseur = await connexion.fetchval(_CURSEUR_LIRE.format(schema=schema))
        if borne > curseur:
            nouvelles = await connexion.fetch(_NOUVELLES.format(schema=schema), curseur, borne)
            resultat.nouvelles_transactions = len(nouvelles)
            touches: dict[str, datetime] = {}
            for ligne in nouvelles:
                for compte in (ligne["sender_account"], ligne["receiver_account"]):
                    if compte not in touches or ligne["occurred_at"] < touches[compte]:
                        touches[compte] = ligne["occurred_at"]
            resultat.comptes_touches = len(touches)
            if touches:
                (
                    selection,
                    resultat.replis_episode,
                    resultat.episodes_tronques,
                ) = await _charger_episodes(connexion, schema, touches, episode_max)
                resultat.transactions_relues = len(selection)
                ordonnees = sorted(
                    selection.values(), key=lambda t: (t.occurred_at, str(t.transaction_id))
                )
                evenements = [
                    e for e in detecter_sequentiellement(ordonnees) if e.compte_pivot in touches
                ]
                nouveaux = await _filtrer_deja_connus(connexion, schema, evenements)
                if nouveaux:
                    meta = await connexion.fetchrow(_METADONNEES, tenant_id)
                    if meta is None:
                        raise RuntimeError("tenant inactif")
                    await connexion.executemany(
                        _INSERT_DETECTION.format(schema=schema),
                        [
                            (
                                uuid4(),
                                meta["tenant_id"],
                                meta["country_code"],
                                meta["data_classification"],
                                e.pattern_type,
                                e.transaction_ids,
                                e.compte_pivot,
                                e.fenetre_debut,
                                e.fenetre_fin,
                                json.dumps(e.details),
                            )
                            for e in nouveaux
                        ],
                    )
                resultat.detections_nouvelles = len(nouveaux)
            await connexion.execute(_CURSEUR_MAJ.format(schema=schema), borne)

    # Scoring B5 (inchangé, idempotent par UPSERT) sur la fenêtre glissante.
    maintenant = datetime.now(UTC)
    fenetre_debut = maintenant - timedelta(days=FENETRE_JOURS)
    detections = await lire_detections_fenetre(pool, schema, fenetre_debut)
    if detections:
        scores = agreger_par_compte(detections, fenetre_debut, maintenant)
        persistance = await enregistrer_scores(pool, schema, scores)
        resultat.comptes_scores = persistance.nb_comptes_scores
        resultat.alertes_creees = persistance.nb_alertes_creees
        resultat.alertes_mises_a_jour = persistance.nb_alertes_mises_a_jour
    return resultat
