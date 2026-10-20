from pathlib import Path
import runpy

import pytest

from app import create_app
from scripts.build_vercel import build_static


def test_static_build_preserves_asset_urls_and_file_contents(tmp_path):
    source = tmp_path / "app" / "static"
    (source / "icons").mkdir(parents=True)
    (source / "style.css").write_bytes(b"body { color: purple; }")
    (source / "icons" / "game.svg").write_bytes(b"<svg></svg>")
    destination = build_static(tmp_path)
    assert (destination / "style.css").read_bytes() == (source / "style.css").read_bytes()
    assert (destination / "icons" / "game.svg").read_bytes() == b"<svg></svg>"
    assert (source / "style.css").exists()


def test_hosted_entrypoint_never_reads_local_secrets_or_writes_files(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/backlog")
    monkeypatch.setenv("SECRET_KEY", "hosted-test-secret")
    monkeypatch.setenv("SUPABASE_URL", "https://auth.example.invalid")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "public-test-key")
    def unexpected_file_access(*args, **kwargs):
        raise AssertionError("Hosted startup must use environment configuration")
    monkeypatch.setattr("flask.config.Config.from_pyfile", unexpected_file_access)
    monkeypatch.setattr(Path, "mkdir", unexpected_file_access)
    monkeypatch.setattr(Path, "write_text", unexpected_file_access)
    application = runpy.run_path("wsgi.py")["app"]
    assert application.config["DATABASE_URL"] == "postgresql://example.invalid/backlog"
    assert application.config["SESSION_COOKIE_SECURE"]
    assert application.config["SESSION_COOKIE_HTTPONLY"]
    assert application.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    with application.test_request_context():
        from flask import url_for
        assert url_for("static", filename="style.css") == "/static/style.css"


def test_hosted_entrypoint_requires_environment_secret(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/backlog")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="Set SECRET_KEY"):
        create_app()
