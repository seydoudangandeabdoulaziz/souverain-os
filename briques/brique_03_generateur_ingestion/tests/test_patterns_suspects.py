"""Tests unitaires — patterns criminels sahéliens (Bloc 7)."""

import random
from datetime import datetime, timedelta

from souverain_generateur.generateur_legitime import FUSEAU_NIGER
from souverain_generateur.patterns_suspects import (
    generer_compte_pivot,
    generer_flux_frontalier,
    generer_micro_fractionnement,
    generer_saisonnalite,
    generer_structure_etoile,
    generer_transactions_nocturnes,
)

BASE_TIME = datetime(2026, 3, 1, 12, 0, 0, tzinfo=FUSEAU_NIGER)


def test_transactions_nocturnes_sont_entre_22h_et_4h() -> None:
    rng = random.Random(1)
    transactions = generer_transactions_nocturnes(rng, BASE_TIME)
    for t in transactions:
        heure = t.occurred_at.hour
        assert heure >= 22 or heure < 4
        assert t.pattern_label == "transactions_nocturnes"


def test_structure_etoile_un_seul_emetteur_plusieurs_destinataires() -> None:
    rng = random.Random(2)
    transactions = generer_structure_etoile(rng, BASE_TIME)
    emetteurs = {t.sender_id for t in transactions}
    destinataires = {t.receiver_id for t in transactions}
    assert len(emetteurs) == 1
    assert len(destinataires) >= 6  # cohérent avec l'intensité "moyenne" par défaut
    assert len(destinataires) == len(transactions)  # pas de doublon de destinataire


def test_structure_etoile_fenetre_temporelle_courte() -> None:
    rng = random.Random(2)
    transactions = generer_structure_etoile(rng, BASE_TIME)
    horodatages = [t.occurred_at for t in transactions]
    assert max(horodatages) - min(horodatages) <= timedelta(minutes=90)


def test_micro_fractionnement_montants_sous_le_seuil() -> None:
    rng = random.Random(3)
    transactions = generer_micro_fractionnement(rng, BASE_TIME)
    for t in transactions:
        assert t.amount < 1000
        assert t.pattern_label == "micro_fractionnement"


def test_micro_fractionnement_meme_paire_emetteur_recepteur() -> None:
    rng = random.Random(3)
    transactions = generer_micro_fractionnement(rng, BASE_TIME)
    emetteurs = {t.sender_id for t in transactions}
    recepteurs = {t.receiver_id for t in transactions}
    assert len(emetteurs) == 1
    assert len(recepteurs) == 1


def test_flux_frontalier_vise_des_zones_frontalieres() -> None:
    rng = random.Random(4)
    transactions = generer_flux_frontalier(rng, BASE_TIME)
    for t in transactions:
        assert "frontiere" in t.receiver_id
        assert t.sender_id.startswith("niamey_")


def test_compte_pivot_reception_puis_redistribution_sous_une_heure() -> None:
    rng = random.Random(5)
    transactions = generer_compte_pivot(rng, BASE_TIME)

    receptions = [t for t in transactions if t.pattern_label == "compte_pivot_reception"]
    redistributions = [
        t for t in transactions if t.pattern_label == "compte_pivot_redistribution"
    ]

    assert len(receptions) >= 3
    assert len(redistributions) >= 2

    pivots_reception = {t.receiver_id for t in receptions}
    pivots_redistribution = {t.sender_id for t in redistributions}
    assert pivots_reception == pivots_redistribution  # même compte pivot des deux côtés

    dernier_horodatage_reception = max(t.occurred_at for t in receptions)
    for t in redistributions:
        assert t.occurred_at - dernier_horodatage_reception <= timedelta(hours=1)


def test_saisonnalite_produit_un_pic_autour_de_levenement() -> None:
    rng = random.Random(6)
    transactions = generer_saisonnalite(rng, BASE_TIME, evenement="tabaski")
    for t in transactions:
        assert t.pattern_label == "saisonnalite_tabaski"
        assert abs(t.occurred_at - BASE_TIME) <= timedelta(hours=48)


def test_intensite_forte_genere_plus_de_transactions_que_legere() -> None:
    rng_legere = random.Random(9)
    rng_forte = random.Random(9)
    transactions_legeres = generer_structure_etoile(rng_legere, BASE_TIME, intensite="legere")
    transactions_fortes = generer_structure_etoile(rng_forte, BASE_TIME, intensite="forte")
    assert len(transactions_fortes) > len(transactions_legeres)
