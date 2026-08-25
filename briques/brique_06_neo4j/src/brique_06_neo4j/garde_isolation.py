"""Point de passage unique vers Neo4j — SEUL fichier du projet autorisé
à contenir du texte Cypher, générique (synchronisation) ET métier (les
3 requêtes de garde_isolation). Décision actée à l'analyse : aucune
requête Cypher ailleurs dans le code, ni dans requetes.py (simple
couche de traduction Record → objets typés), ni dans cli.py.

═══════════════════════════════════════════════════════════════════
DISCIPLINE D'ISOLATION MULTI-TENANT — À RESPECTER DANS TOUTE NOUVELLE
REQUÊTE AJOUTÉE À CE FICHIER, SANS EXCEPTION
═══════════════════════════════════════════════════════════════════
Neo4j Community Edition ne supporte qu'une seule base de données (le
multi-base est une fonctionnalité Enterprise — vérifié à l'analyse).
L'isolation multi-tenant est donc LOGIQUE, par propriété tenant_id,
jamais physique comme le schema-per-tenant de PostgreSQL.

Règle non négociable : dans TOUT MATCH, TOUS les motifs de nœuds
portent {tenant_id: $tenant_id} — y compris les nœuds atteints après
plusieurs sauts, pas seulement le nœud de départ. Pour les traversées
à longueur variable (où les nœuds intermédiaires ne sont pas des
variables liées individuellement), une double vérification défensive
ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id) ET
ALL(r IN relationships(path) WHERE r.tenant_id = $tenant_id) est
OBLIGATOIRE — jamais laissé à la seule garantie implicite que les
relations ne peuvent physiquement pas exister entre deux tenants.

Contrainte de schéma en renfort (pas seulement une discipline de code) :
unicité composite (tenant_id, compte_id) sur :Compte — voir
assurer_contraintes(). Empêche la fusion silencieuse de deux comptes de
tenants différents qui partageraient le même compte_id (réutilisation
des préfixes du générateur Brique 3 à l'export UEMOA).

Testé en premier, avant tout autre test de cette brique :
tests/test_isolation_tenant.py.
═══════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

from itertools import combinations

from neo4j import AsyncDriver

from brique_06_neo4j.modeles import TransactionAImporter

# Taille de lot pour l'import par UNWIND — même convention que
# l'ingestion par lots de 500 en Brique 3.
TAILLE_LOT = 500

# Bornes des requêtes de traversée — évite un résultat non borné sur
# un graphe qui grossira avec le temps. Valeurs provisoires MVP.
LONGUEUR_MIN_CHAINE = 3
LONGUEUR_MAX_CHAINE = 6
LONGUEUR_MAX_CHEMIN = 15
LIMITE_RESULTATS = 100


# ─────────────────────────────────────────────────────────────────
# Contraintes de schéma
# ─────────────────────────────────────────────────────────────────


async def assurer_contraintes(driver: AsyncDriver) -> None:
    """Crée les contraintes d'unicité composite, idempotent (IF NOT EXISTS).

    (tenant_id, compte_id) sur :Compte, et (tenant_id, transaction_id)
    sur la relation :ENVOIE — renfort de schéma en plus de la
    discipline de filtrage, pas un substitut.

    Vérifié à l'analyse : les contraintes d'unicité composite (IS
    UNIQUE, sans garantie d'existence) sont disponibles en Neo4j
    Community Edition — à la différence des "node key constraints"
    (existence + unicité combinées), celles-ci réservées à Enterprise.
    """
    async with driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT compte_tenant_unique IF NOT EXISTS "
            "FOR (c:Compte) REQUIRE (c.tenant_id, c.compte_id) IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT transaction_tenant_unique IF NOT EXISTS "
            "FOR ()-[r:ENVOIE]-() REQUIRE (r.tenant_id, r.transaction_id) IS UNIQUE"
        )


# ─────────────────────────────────────────────────────────────────
# Synchronisation (générique) — seule requête d'écriture de la brique
# ─────────────────────────────────────────────────────────────────

_CYPHER_SYNCHRONISER_LOT = """
UNWIND $transactions AS tx
MERGE (a:Compte {tenant_id: $tenant_id, compte_id: tx.sender_account})
MERGE (b:Compte {tenant_id: $tenant_id, compte_id: tx.receiver_account})
MERGE (a)-[r:ENVOIE {tenant_id: $tenant_id, transaction_id: tx.transaction_id}]->(b)
SET r.amount = tx.amount,
    r.currency = tx.currency,
    r.channel = tx.channel,
    r.occurred_at = tx.occurred_at,
    r.is_synthetic = tx.is_synthetic
"""


async def synchroniser_transactions(
    driver: AsyncDriver, tenant_id: str, transactions: list[TransactionAImporter]
) -> int:
    """Projette des transactions dans le graphe, par lots de TAILLE_LOT.

    tenant_id dans la clé de correspondance du MERGE (pas seulement
    dans le SET) — sinon deux tenants avec le même compte_id
    fusionneraient silencieusement en un seul nœud physique. Voir
    l'en-tête du fichier.

    transaction_id comme clé de la relation : repose sur son unicité
    garantie (UUID généré par PostgreSQL, gen_random_uuid(), Brique 1)
    — pas une supposition implicite, vérifiée dans le schéma réel de
    {tenant}.transactions avant de faire ce choix.

    Portée MVP validée à l'analyse : retraverse l'intégralité des
    transactions à chaque exécution, même si MERGE évite toute
    duplication. Cohérent avec le principe déjà appliqué en Brique 4/5
    (recalcul complet plutôt qu'un mécanisme de "traité" fragile) —
    pas une régression, mais même limite d'échelle : à l'échelle UEMOA
    (millions de transactions), un import complet à chaque exécution
    deviendra coûteux. Import incrémental = Vision.

    Retourne le nombre de transactions envoyées (pas le nombre de
    relations réellement créées — MERGE peut ne rien changer si déjà
    présentes, ce n'est pas une erreur).
    """
    await assurer_contraintes(driver)

    nb_envoyees = 0
    async with driver.session() as session:
        for debut in range(0, len(transactions), TAILLE_LOT):
            lot = transactions[debut : debut + TAILLE_LOT]
            parametres = [
                {
                    "sender_account": tx.sender_account,
                    "receiver_account": tx.receiver_account,
                    "transaction_id": str(tx.transaction_id),
                    "amount": float(tx.amount),
                    "currency": tx.currency,
                    "channel": tx.channel,
                    "occurred_at": tx.occurred_at.isoformat(),
                    "is_synthetic": tx.is_synthetic,
                }
                for tx in lot
            ]
            await session.run(
                _CYPHER_SYNCHRONISER_LOT, tenant_id=tenant_id, transactions=parametres
            )
            nb_envoyees += len(lot)

    return nb_envoyees


# ─────────────────────────────────────────────────────────────────
# Requête métier a) — chaînes de redistribution multi-sauts
# ─────────────────────────────────────────────────────────────────

_CYPHER_CHAINES_REDISTRIBUTION = f"""
MATCH path = (a:Compte {{tenant_id: $tenant_id}})
             -[:ENVOIE*{LONGUEUR_MIN_CHAINE}..{LONGUEUR_MAX_CHAINE}]->
             (b:Compte {{tenant_id: $tenant_id}})
WHERE a <> b
  AND ALL(r IN relationships(path) WHERE r.tenant_id = $tenant_id)
  AND ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
RETURN [n IN nodes(path) | n.compte_id] AS comptes,
       [r IN relationships(path) | r.transaction_id] AS transaction_ids
LIMIT $limite
"""


async def detecter_chaines_redistribution(
    driver: AsyncDriver, tenant_id: str
) -> list[dict[str, object]]:
    """Chaînes A→B→C→...→N de longueur 3 à 6 sauts.

    Invisible aux règles séquentielles de la Brique 4 prises
    individuellement : chaque règle regarde une fenêtre courte autour
    d'un seul compte, pas une chaîne de comptes intermédiaires.

    Retourne des dicts bruts (Record.data()), pas des objets typés —
    la traduction vers Chemin (UUID, etc.) est le rôle de requetes.py,
    seul fichier autorisé à faire cette traduction (décision actée à
    l'analyse : garde_isolation.py ne connaît que Neo4j, requetes.py
    ne connaît que la représentation Python interne).
    """
    async with driver.session() as session:
        resultat = await session.run(
            _CYPHER_CHAINES_REDISTRIBUTION, tenant_id=tenant_id, limite=LIMITE_RESULTATS
        )
        return [record.data() async for record in resultat]


# ─────────────────────────────────────────────────────────────────
# Requête métier b) — comptes pont entre deux comptes alertés
# ─────────────────────────────────────────────────────────────────

_CYPHER_COMPTES_PONT = """
UNWIND $comptes_alertes AS compte_source
MATCH (source:Compte {tenant_id: $tenant_id, compte_id: compte_source})
      -[r1:ENVOIE {tenant_id: $tenant_id}]->
      (pont:Compte {tenant_id: $tenant_id})
      -[r2:ENVOIE {tenant_id: $tenant_id}]->
      (cible:Compte {tenant_id: $tenant_id})
WHERE cible.compte_id IN $comptes_alertes
  AND cible.compte_id <> compte_source
  AND NOT pont.compte_id IN $comptes_alertes
RETURN DISTINCT pont.compte_id AS compte_pont,
       compte_source AS compte_alerte_source,
       cible.compte_id AS compte_alerte_cible,
       r1.transaction_id AS transaction_entrante_id,
       r2.transaction_id AS transaction_sortante_id
LIMIT $limite
"""


async def detecter_comptes_pont(
    driver: AsyncDriver, tenant_id: str, comptes_alertes: list[str]
) -> list[dict[str, object]]:
    """Comptes reliant deux comptes déjà alertés (Brique 5), jamais eux-mêmes alertés.

    Invisible au scoring par compte isolé de la Brique 5 : le compte
    pont n'a individuellement jamais franchi le seuil, seule sa
    position topologique entre deux investigations distinctes le
    rend intéressant.

    comptes_alertes vide (cas réel actuel de tenant_ne, aucune alerte
    créée) → liste vide en sortie, sans exécuter la requête — pas une
    erreur, couvert par test_requetes.py.

    Retourne des dicts bruts — voir docstring de
    detecter_chaines_redistribution() sur la répartition avec
    requetes.py.
    """
    if len(comptes_alertes) < 2:
        return []

    async with driver.session() as session:
        resultat = await session.run(
            _CYPHER_COMPTES_PONT,
            tenant_id=tenant_id,
            comptes_alertes=comptes_alertes,
            limite=LIMITE_RESULTATS,
        )
        return [record.data() async for record in resultat]


# ─────────────────────────────────────────────────────────────────
# Requête métier c) — plus court chemin entre deux comptes alertés
# ─────────────────────────────────────────────────────────────────

_CYPHER_PLUS_COURT_CHEMIN = f"""
MATCH (a:Compte {{tenant_id: $tenant_id, compte_id: $compte_a}}),
      (b:Compte {{tenant_id: $tenant_id, compte_id: $compte_b}})
MATCH path = shortestPath((a)-[:ENVOIE*..{LONGUEUR_MAX_CHEMIN}]-(b))
WHERE ALL(r IN relationships(path) WHERE r.tenant_id = $tenant_id)
  AND ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
RETURN [n IN nodes(path) | n.compte_id] AS comptes,
       [r IN relationships(path) | r.transaction_id] AS transaction_ids
"""


async def chemin_le_plus_court_entre_alertes(
    driver: AsyncDriver, tenant_id: str, comptes_alertes: list[str]
) -> list[dict[str, object]]:
    """Plus court chemin entre chaque paire distincte de comptes déjà alertés.

    Révèle si deux comptes flaggés indépendamment par la Brique 5 sont
    en réalité connectés — information qu'aucune règle séquentielle ni
    le scoring par compte isolé ne peut produire.

    Traversée non dirigée (-[:ENVOIE*..N]-, sans flèche) : la question
    posée est "existe-t-il un chemin de connexion", indépendamment du
    sens des transactions qui le composent.

    comptes_alertes avec moins de 2 comptes → liste vide, sans
    exécuter de requête — pas une erreur.

    Retourne des dicts bruts — voir docstring de
    detecter_chaines_redistribution() sur la répartition avec
    requetes.py.
    """
    if len(comptes_alertes) < 2:
        return []

    resultats: list[dict[str, object]] = []
    async with driver.session() as session:
        for compte_a, compte_b in combinations(sorted(set(comptes_alertes)), 2):
            resultat = await session.run(
                _CYPHER_PLUS_COURT_CHEMIN,
                tenant_id=tenant_id,
                compte_a=compte_a,
                compte_b=compte_b,
            )
            resultats.extend([record.data() async for record in resultat])

    return resultats
