# ADR-006 — Déploiement d'Ollama dans Docker

- **Statut :** Accepté en principe — réserves ouvertes
- **Date :** 21 octobre 2026
- **Contexte :** Clôture de l'étape 6a et préparation de l'étape 6b

## 1. Contexte

L'étape 6a a évalué le modèle local
`ministral-3:8b-instruct-2512-q4_K_M`.

Le verdict de l'étape 6a recommande une exécution dans le service
Docker Compose `ollama`, avec une image épinglée par digest, un port
local et un volume persistant.

L'inférence dans le conteneur a été vérifiée après redémarrage.
Le modèle répond correctement à un test simple.

Mesures observées le 21 octobre 2026 :
- Digest du modèle :
  `1922accd5827ebe6829e536369195db25eaf664528dc66206d646ea3bb386b71`
- Pic mémoire du conteneur pendant l'inférence :
  6,618 Gio
- Durée totale de l'inférence de test à froid :
  environ 72,74 secondes
- Seuil mémoire historique de l'étape 6a :
  6,5 Gio

Le pic mesuré dépasse le seuil historique. Le critère mémoire ne peut
donc pas être considéré comme validé sur la base de cette mesure.

## 2. Décision retenue sous réserves

1. Retenir le service Docker Compose `ollama` comme environnement
   d'exécution cible.
2. Conserver l'image Docker épinglée par digest et le port lié à
   `127.0.0.1`.
3. Conserver le modèle dans le volume Docker persistant et vérifier
   son identité avant toute utilisation.
4. Ne pas désinstaller ni supprimer de composants natifs tant qu'une
   vérification explicite ne l'exige pas. Le processus Ollama observé
   pendant le diagnostic appartient au conteneur Docker.
5. Maintenir une réserve sur la mémoire et mesurer les performances
   dans des scénarios représentatifs avant de déclarer la plateforme
   prête pour l'intégration.
6. Ne pas démarrer l'intégration fonctionnelle de l'étape 6b avant
   validation explicite des critères de fidélité des explications.

## 3. Invariants de sécurité et de produit

Cette décision ne modifie pas les invariants existants :

- L'IA est explicative, locale et invoquée à la demande.
- Les briques B4, B5 et B6 restent déterministes et inchangées.
- L'IA ne prend aucune décision automatique et ne prononce aucun verdict.
- Aucun agent autonome, RAG ou génération de requêtes SQL/Cypher
  n'est introduit.
- Les données d'un tenant ne doivent jamais être exposées à un autre.
- Les explications et les chiffres produits par le modèle doivent être
  vérifiés par rapport aux faits structurés disponibles.
- La décision finale appartient à un humain.

## 4. Critères avant l'étape 6b

- Confirmer la persistance du modèle dans le volume Docker.
- Vérifier l'image Docker et le digest exact du modèle.
- Mesurer la mémoire et la durée de réponse lors de plusieurs tests.
- Définir et automatiser des tests de fidélité sur les faits structurés,
  notamment la distinction entre le poids d'une règle et le nombre
  de transactions ou d'occurrences.
- Documenter les limites observées et obtenir la validation du fondateur.

Le dépassement du seuil mémoire historique doit rester visible dans
les résultats ; il ne peut pas être effacé par une modification
rétroactive du seuil.

## 5. Conséquences

Avantages :
- Environnement d'exécution reproductible et isolé.
- Modèle conservé dans un volume persistant.
- Accès au service limité à la machine locale.

Limites :
- L'inférence CPU à froid peut être lente.
- La consommation mémoire observée dépasse le seuil historique.
- La faisabilité technique ne démontre pas la fidélité des explications.

## 6. Validation

Cet ADR est accepté en principe par le fondateur, avec réserves ouvertes.
Cette acceptation ne vaut pas autorisation de modifier le moteur de détection,
de démarrer l'étape 6b, de désinstaller Ollama natif ou de procéder
à une migration. Le démarrage de l'étape 6b reste bloqué jusqu'à la
définition et à la réussite des tests de fidélité des explications.
La réserve mémoire de 6,618 Gio face au seuil historique de 6,5 Gio
reste explicitement ouverte.
