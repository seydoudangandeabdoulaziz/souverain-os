from __future__ import annotations

from types import SimpleNamespace

from souverain_app import cli


def test_application_ecoute_uniquement_sur_loopback(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "get_dashboard_settings", lambda: SimpleNamespace(port=8080))
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: captured.update(kwargs))

    cli.main()

    assert captured["host"] == "127.0.0.1"
    assert captured["reload"] is False
