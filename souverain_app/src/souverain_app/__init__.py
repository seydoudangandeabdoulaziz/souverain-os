"""SOUVERAIN-OS — module d'assemblage neutre.

Introduit à l'analyse de la Brique 8 (validé explicitement par le
fondateur, 29 août 2026) pour respecter la contrainte "zéro fichier
Brique 7 modifié" tout en exposant les routes d'écriture de la
Brique 8 sur la même instance FastAPI que le dashboard Brique 7.

Ni brique_07_dashboard ni brique_08_audit_human_loop ne dépend de
l'autre pour leur propre fonctionnement interne — brique_08 importe
seulement deux fonctions ciblées de brique_07 (get_current_user_from_
cookie, tenant_valide), pas l'inverse. C'est CE module qui connaît les
deux et les assemble.

Ne contient aucune logique métier. Si une Brique 9 (ou au-delà) doit un
jour être montée de la même façon, elle s'ajoute ici, pas dans
brique_07_dashboard.app.creer_application().
"""
