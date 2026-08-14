"""
Fondations de SOUVERAIN-ID — identifiant cryptographique souverain.

IMPORTANT — périmètre de cette brique :
Ce module fournit uniquement la FONDATION de SOUVERAIN-ID : un
identifiant déterministe, dérivé du tenant et de l'email, généré
localement (aucun appel réseau, aucune dépendance externe).

Ce n'est PAS ENCORE le "Passeport Financier Africain" complet décrit
dans le document fondateur (Bloc 4) : pas de signature cryptographique
post-quantique (Dilithium-5), pas d'interopérabilité inter-États.
Cette évolution est prévue en phase transverse, après la couche PQC.

Pourquoi un identifiant DÉTERMINISTE (UUID5) plutôt qu'ALÉATOIRE (UUID4) ?
Un identifiant déterministe (même tenant + même email → toujours le
même souverain_id) facilite les tests, les migrations, et la
vérification d'idempotence — sans dépendre d'un générateur aléatoire
externe. L'unicité réelle du compte reste garantie par la contrainte
d'unicité sur la colonne `email` en base (voir schema_users.sql),
pas par le souverain_id lui-même.
"""

from __future__ import annotations

import uuid

# Namespace fixe et permanent du projet SOUVERAIN-OS, généré une seule
# fois (uuid5(NAMESPACE_DNS, "souverain-os.io")). NE JAMAIS changer
# cette valeur : la changer romprait le déterminisme pour tous les
# souverain_id déjà émis.
SOUVERAIN_ID_NAMESPACE = uuid.UUID("312500d9-ef3b-5167-af2a-c9c3fede1cab")


def generate_souverain_id(tenant_code: str, email: str) -> uuid.UUID:
    """
    Génère l'identifiant SOUVERAIN-ID (fondation) pour un utilisateur.

    Args:
        tenant_code: code court du tenant, ex. "NE".
        email: email de l'utilisateur (identifiant de connexion).

    Returns:
        Un UUID déterministe : le même couple (tenant_code, email)
        produit toujours le même souverain_id.
    """
    seed = f"{tenant_code.lower()}:{email.lower()}"
    return uuid.uuid5(SOUVERAIN_ID_NAMESPACE, seed)
