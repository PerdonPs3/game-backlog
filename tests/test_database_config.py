from datetime import date, datetime

import pytest

from app import create_app
from app.postgres import PostgresConnection, Record, postgres_parameters
import app.postgres as postgres


def test_hosted_database_requires_secret_before_any_connection():
    with pytest.raises(ValueError, match="Set SECRET_KEY"):
        create_app({"DATABASE_URL": "postgresql://invalid.example/backlog"})


def test_invalid_database_url_never_falls_back_to_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        create_app({"DATABASE_URL": "mysql://invalid.example/backlog", "SECRET_KEY": "test"})


def test_environment_config_and_test_isolation(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid.example/backlog")
    monkeypatch.setenv("SECRET_KEY", "environment-test-key")
    application = create_app()
    assert application.config["DATABASE_URL"] == "postgresql://invalid.example/backlog"
    assert application.config["SECRET_KEY"] == "environment-test-key"
    isolated = create_app({"TESTING": True, "SECRET_KEY": "isolated-test-key"})
    assert not isolated.config.get("DATABASE_URL")
    assert isolated.config["SECRET_KEY"] == "isolated-test-key"


def test_postgres_parameters_preserve_literals_and_bound_values():
    query = "SELECT '?' AS literal, '100%' AS percent, \"?column\" FROM games WHERE title = ? AND review = ?"
    assert postgres_parameters(query) == "SELECT '?' AS literal, '100%%' AS percent, \"?column\" FROM games WHERE title = %s AND review = %s"


def test_postgres_rows_preserve_backup_dates_and_positional_access():
    row = Record(("id", "started_on", "created_at"), (17, date(2026, 10, 19), datetime(2026, 10, 19, 14, 30)))
    assert row[0] == row["id"] == 17
    assert tuple(row) == (17, "2026-10-19", "2026-10-19 14:30:00")
    assert dict(row)["started_on"] == "2026-10-19"


def test_hosted_config_never_creates_local_secret_file(monkeypatch):
    def unexpected_write(*args, **kwargs):
        raise AssertionError("Hosted configuration must not write local files")
    monkeypatch.setattr("pathlib.Path.mkdir", unexpected_write)
    monkeypatch.setattr("pathlib.Path.write_text", unexpected_write)
    create_app({"DATABASE_URL": "postgresql://invalid.example/test", "SECRET_KEY": "test"})


def test_vercel_without_database_url_fails_instead_of_using_sqlite(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="Set DATABASE_URL"):
        create_app()


def test_remote_connection_requires_ssl_and_disables_prepared_statements(monkeypatch):
    captured = {}
    def connect(url, **kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(postgres.psycopg, "connect", connect)
    PostgresConnection("postgresql://example.invalid/test")
    assert captured["sslmode"] == "require"
    assert captured["prepare_threshold"] is None
    with pytest.raises(ValueError, match="require SSL"):
        PostgresConnection("postgresql://example.invalid/test?sslmode=disable")


def test_postgres_commands_without_url_never_create_sqlite_database(tmp_path):
    database = tmp_path / "untouched.sqlite"
    application = create_app({"TESTING": True, "SECRET_KEY": "test", "DATABASE": str(database)})
    for command in ("migrate-db", "check-db"):
        result = application.test_cli_runner().invoke(args=[command])
        assert result.exit_code != 0 and "Set DATABASE_URL" in result.output
    assert not database.exists()
