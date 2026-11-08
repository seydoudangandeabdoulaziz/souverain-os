"""Extraction locale de documents, en conservant les limites de page."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from souverain_rag.chunking import PageText
from souverain_rag.errors import ManifestError
from souverain_rag.manifest import AuthorizedDocument

MAX_PDF_PAGES = 1_000
MAX_EXTRACTED_CHARACTERS = 20_000_000
MAX_PAGE_CHARACTERS = 100_000


def extraire(document: AuthorizedDocument) -> tuple[PageText, ...]:
    suffix = document.source_path.suffix.lower()
    if suffix == ".pdf":
        return _extraire_pdf(document.source_bytes)
    if suffix in {".txt", ".md"}:
        try:
            text = document.source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManifestError(f"Source texte illisible : {document.document_id}.") from exc
        sections = text.split("\f")
        if len(sections) > MAX_PDF_PAGES:
            raise ManifestError("Le document dépasse la limite de pages MVP.")
        return tuple(PageText(number, value) for number, value in enumerate(sections, 1))
    raise ManifestError("Format de source non pris en charge.")


def _extraire_pdf(source_bytes: bytes) -> tuple[PageText, ...]:
    try:
        reader = PdfReader(BytesIO(source_bytes), strict=True)
        if reader.is_encrypted:
            raise ManifestError("Les PDF chiffrés ne sont pas acceptés.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ManifestError("Le PDF dépasse la limite de pages MVP.")
        pages: list[PageText] = []
        total_characters = 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            if len(text) > MAX_PAGE_CHARACTERS:
                raise ManifestError(f"Page {number} trop volumineuse après extraction.")
            total_characters += len(text)
            if total_characters > MAX_EXTRACTED_CHARACTERS:
                raise ManifestError("Le texte extrait dépasse la limite MVP.")
            pages.append(PageText(number, text))
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError("Échec d'extraction du PDF.") from exc
    return tuple(pages)
