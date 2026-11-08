"""Découpage déterministe à la page, sans traverser les documents."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

WORDS_PER_CHUNK = 220
OVERLAP_WORDS = 40


@dataclass(frozen=True, slots=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class Passage:
    passage_id: str
    document_id: str
    title: str
    publisher: str
    source_url: str
    page_number: int
    text: str
    synthetic: bool


def decouper_pages(
    document_id: str,
    title: str,
    publisher: str,
    source_url: str,
    pages: tuple[PageText, ...],
    synthetic: bool,
) -> tuple[Passage, ...]:
    passages: list[Passage] = []
    step = WORDS_PER_CHUNK - OVERLAP_WORDS
    for page in pages:
        words = page.text.split()
        if not words:
            continue
        for start in range(0, len(words), step):
            chunk_words = words[start : start + WORDS_PER_CHUNK]
            if not chunk_words:
                break
            text = " ".join(chunk_words)
            identifier = hashlib.sha256(
                f"{document_id}\0{page.page_number}\0{start}\0{text}".encode()
            ).hexdigest()[:24]
            passages.append(
                Passage(
                    passage_id=f"{document_id}:{page.page_number}:{identifier}",
                    document_id=document_id,
                    title=title,
                    publisher=publisher,
                    source_url=source_url,
                    page_number=page.page_number,
                    text=text,
                    synthetic=synthetic,
                )
            )
            if start + WORDS_PER_CHUNK >= len(words):
                break
    return tuple(passages)
