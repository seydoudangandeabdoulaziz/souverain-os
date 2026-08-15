"""Règles de détection — une par pattern sahélien (Bloc 7, document fondateur).

Chaque règle est état-plein : elle reçoit les transactions une par une,
dans l'ordre chronologique (traitement_sequentiel), et maintient sa propre
mémoire courte (fenêtre glissante par compte). Voir base.py pour
l'interface commune.
"""
