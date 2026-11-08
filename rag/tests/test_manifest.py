from __future__ import annotations

import json
from pathlib import Path

import pytest
from souverain_rag.errors import IngestionBlocked, ManifestError
from souverain_rag.extract import extraire
from souverain_rag.ingestion import ingerer, ingerer_chroma
from souverain_rag.manifest import valider_manifeste

from rag.tests.support import ecrire_corpus_autorise


def test_valide_provenance_et_hashes(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)

    manifest = valider_manifeste(path)

    assert manifest.corpus_id == "fixture-v1"
    assert manifest.documents[0].document_id == "public-001"
    assert manifest.documents[0].synthetic is True


def test_extraction_utilise_les_octets_valides_meme_si_la_source_change(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path, text="Contenu validé lors de l'ingestion.")
    manifest = valider_manifeste(path)
    source = tmp_path / "sources" / "public.txt"
    source.write_text("Contenu remplacé après validation.", encoding="utf-8")

    pages = extraire(manifest.documents[0])

    assert pages[0].text == "Contenu validé lors de l'ingestion."


def test_refuse_source_sans_droits_avant_de_lire_la_source(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["documents"][0]["rights"]["status"] = "pending"
    payload["documents"][0]["source_path"] = "source-inexistante.pdf"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IngestionBlocked, match="non approuvés"):
        valider_manifeste(path)


def test_ingestion_non_autorisee_ne_cree_aucun_index(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["documents"][0]["rights"]["status"] = "pending"
    payload["documents"][0]["source_path"] = "source-absente.pdf"
    path.write_text(json.dumps(payload), encoding="utf-8")

    class MustNotEncode:
        fingerprint = "unused"

        def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
            raise AssertionError("Aucun embedding ne doit être calculé.")

        def encode_query(self, text: str) -> tuple[float, ...]:
            raise AssertionError("Aucune requête ne doit être encodée.")

    output = tmp_path / "index"
    with pytest.raises(IngestionBlocked, match="non approuvés"):
        ingerer(path, output, MustNotEncode())

    assert not output.exists()


def test_ingestion_chroma_refuse_avant_connexion_au_serveur(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["documents"][0]["rights"]["status"] = "pending"
    path.write_text(json.dumps(payload), encoding="utf-8")

    def must_not_connect():
        raise AssertionError("Pas de connexion au serveur avant validation des droits.")

    class MustNotEncode:
        fingerprint = "unused"

        def encode_passages(self, texts: list[str]) -> list[tuple[float, ...]]:
            raise AssertionError("Aucun embedding ne doit être calculé.")

        def encode_query(self, text: str) -> tuple[float, ...]:
            raise AssertionError("Aucune requête ne doit être encodée.")

    with pytest.raises(IngestionBlocked, match="non approuvés"):
        ingerer_chroma(path, MustNotEncode(), must_not_connect)


def test_refuse_preuve_modifiee(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    (tmp_path / "rights" / "permission.txt").write_text("Autre contenu", encoding="utf-8")

    with pytest.raises(IngestionBlocked, match="altérée"):
        valider_manifeste(path)


def test_refuse_empreinte_source_modifiee(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    (tmp_path / "sources" / "public.txt").write_text("Texte modifié", encoding="utf-8")

    with pytest.raises(ManifestError, match="SHA-256"):
        valider_manifeste(path)


def test_refuse_chemin_de_source_hors_corpus(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["documents"][0]["source_path"] = "../outside.txt"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestError, match="sort du répertoire"):
        valider_manifeste(path)


def test_refuse_champ_metier_non_reconnu(tmp_path: Path) -> None:
    path = ecrire_corpus_autorise(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["documents"][0]["tenant_id"] = "tenant-secret"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ManifestError, match="Champs de source"):
        valider_manifeste(path)
