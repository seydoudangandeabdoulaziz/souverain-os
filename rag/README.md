# souverain-rag

Paquet transverse de recherche documentaire locale, sans LLM. Les sources et
l'index sont communs et publics ; aucune donnée métier, de compte, d'alerte ou
de tenant n'est acceptée par l'API du paquet.

## Préparer un corpus

L'ingestion se fait exclusivement par CLI. Le manifeste JSON v1 exige un
enregistrement par document, une empreinte SHA-256 et une preuve de droits
validée. Les permissions doivent explicitement couvrir `extract`,
`local_storage`, `embedding`, `vector_index` et `display_passages`. Le paquet
vérifie le fichier de preuve par SHA-256, mais ne prétend pas interpréter
automatiquement sa portée juridique : `status: approved`, les opérations
autorisées, le valideur et la date sont une décision humaine documentée.
Toute valeur manquante ou non approuvée bloque l'ensemble de l'ingestion avant
l'extraction des sources.

Le manifeste et ses preuves restent hors du dépôt public lorsqu'ils contiennent
des informations confidentielles. Aucun journal durable d'ingestion n'est
créé. Les rapports FATF encore en attente ne doivent pas être ajoutés à un
manifeste approuvé.

Exemple de structure (les valeurs de preuve ci-dessous sont fictives) :

```json
{
  "manifest_version": "souverain-rag-manifest-v1",
  "corpus_id": "public-reference-v1",
  "documents": [{
    "document_id": "document-public-001",
    "title": "Titre vérifié",
    "publisher": "Éditeur",
    "source_url": "https://example.invalid/document.pdf",
    "published_at": "2026-01-01",
    "acquired_at": "2026-01-02",
    "language": "fr",
    "synthetic": false,
    "source_path": "sources/document.pdf",
    "sha256": "<64 caractères hexadécimaux>",
    "rights": {
      "status": "approved",
      "proof_path": "rights/document-permission.pdf",
      "proof_sha256": "<64 caractères hexadécimaux>",
      "allowed_operations": [
        "extract", "local_storage", "embedding", "vector_index",
        "display_passages"
      ],
      "validated_by": "fondateur",
      "validated_at": "2026-01-03"
    }
  }]
}
```

La preuve réelle doit couvrir chacune des opérations ; ne pas recopier
l'exemple comme approbation. Chemins source et preuve sont relatifs au dossier
du manifeste et ne peuvent en sortir.

## Modèle et commandes

Placer localement les poids E5-small approuvés et définir
`SOUVERAIN_RAG_MODEL_PATH` vers leur dossier. Le chargeur exige le SHA-256
approuvé du fichier `model.safetensors`, travaille sur CPU avec au plus quatre
threads et ne télécharge jamais de poids.

Le serveur vectoriel du MVP est Chroma en mode serveur authentifié, jamais
`PersistentClient` dans l'application. Il est lié à `127.0.0.1`, limité à un
worker et doté d'un plafond mémoire Docker de 2 Gio. Le jeton est fourni par
l'environnement local et ne doit pas être enregistré dans Git :

```sh
export SOUVERAIN_RAG_CHROMA_TOKEN='<secret local>'
docker compose --profile rag up -d chroma
export SOUVERAIN_RAG_MODEL_PATH=/chemin/local/e5-small
export SOUVERAIN_RAG_MANIFEST_PATH=/chemin/corpus/manifest.json
uv run souverain-rag ingest --manifest "$SOUVERAIN_RAG_MANIFEST_PATH"
uv run souverain-rag search --manifest "$SOUVERAIN_RAG_MANIFEST_PATH" --pattern compte_pivot
```

Configurer aussi `SOUVERAIN_RAG_MODEL_PATH`, `SOUVERAIN_RAG_MANIFEST_PATH` et
`SOUVERAIN_RAG_CHROMA_TOKEN` pour le processus hôte de l'application. Le client
Chroma envoie le jeton en Bearer. Les collections sont liées au SHA-256 du
manifeste et à l'empreinte du modèle; chaque démarrage revalide les droits et
les sources avant d'ouvrir la collection. E5 produit localement les vecteurs;
Chroma ne reçoit pas d'embeddings générés par un service externe.

L'index SQLite présent dans le paquet sert uniquement aux tests et au
développement isolé. L'ingestion et la recherche du MVP passent par Chroma
serveur. La recherche n'accepte que les cinq valeurs `PatternType` et impose
`k <= 10`; aucune question libre n'est reçue.

Le MVP suppose un seul processus. `SingleProcessSearchGate` refuse
immédiatement une recherche concurrente. Une exécution multi-processus n'est
pas prise en charge.
