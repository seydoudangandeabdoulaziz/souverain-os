"""Erreurs contrôlées du pipeline RAG."""


class RagError(Exception):
    """Erreur de configuration ou d'exécution du composant documentaire."""


class ManifestError(RagError):
    """Manifeste absent, invalide ou non conforme à la politique de droits."""


class IngestionBlocked(ManifestError):
    """Au moins une source ne possède pas de preuve de droits validée."""


class IndexIntegrityError(RagError):
    """Index absent, modifié ou lié à un autre manifeste/modèle."""


class ModelUnavailable(RagError):
    """Poids E5 approuvés indisponibles localement."""


class SearchBusy(RagError):
    """Une recherche est déjà en cours dans l'unique processus MVP."""
