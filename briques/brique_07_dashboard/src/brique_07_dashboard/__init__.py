"""SOUVERAIN-OS — Brique 7 : Dashboard / investigation.

Interface de consultation pour un analyste : liste des alertes
(Brique 5), détail d'une alerte avec contexte transactionnel (Briques
1/4) et motifs de réseau (Brique 6) — sans écrire de SQL ni de Cypher.

Périmètre strict :
- LECTURE SEULE. Aucun déclenchement de calcul (pas de bouton
  "relancer la détection/le scoring/le graphe") — cohérent avec
  l'esprit CLI-batch déjà en place sur les briques précédentes.
- Pas de changement d'état d'alerte ('ouverte' -> 'fermee') : cette
  responsabilité appartient entièrement à la Brique 8
  (Human-in-the-loop), non commencée.

Hors périmètre, documenté explicitement (pas un oubli) :
- Audit trail immuable (Brique 8).
- RAG / IA locale (phase transverse).
- Notifications citoyens (ADR-001, position non tranchée).
- Export de rapport, signé ou non, avant l'existence de la Brique PQC
  (Dilithium-5) — le document fondateur ne demande que des rapports
  SIGNÉS comme livrable, jamais un export intermédiaire non signé.
  Construire un export non signé maintenant reviendrait à reconstruire
  deux fois la même fonctionnalité une fois la PQC prête.

Multilinguisme : mécanisme d'externalisation posé dès cette brique
(ADR-001, point 6 de 00_DECISIONS_VERROUILLEES.md), même si seul le
français est livré maintenant — voir traductions/.
"""
