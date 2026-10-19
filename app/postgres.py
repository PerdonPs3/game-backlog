"""PostgreSQL connection support using the application's qmark SQL parameters."""

import re
from datetime import date, datetime

import psycopg


class Record:
    """Provide SQLite Row's named and positional access for PostgreSQL results."""

    def __init__(self, names, values):
        self._names = names
        # Preserve the string interface used by templates and portable backups.
        self._values = tuple(
            value.isoformat(sep=" ") if isinstance(value, datetime)
            else value.isoformat() if isinstance(value, date) else value
            for value in values
        )

    def keys(self):
        return self._names

    def __getitem__(self, key):
        return self._values[self._names.index(key)] if isinstance(key, str) else self._values[key]

    def __iter__(self):
        return iter(self._values)


def record_factory(cursor):
    names = tuple(column.name for column in cursor.description or ())
    return lambda values: Record(names, values)


def postgres_parameters(statement):
    """Translate placeholders, preserving quoted SQL literals and identifiers.

    This interface accepts application-owned SQL, never user-supplied SQL. Escape
    literal percent signs for psycopg when binding values.
    """
    tokens = re.split(r"('(?:[^']|'')*'|\"(?:[^\"]|\"\")*\")", statement)
    return "".join(
        token.replace("%", "%%") if index % 2
        else token.replace("%", "%%").replace("?", "%s")
        for index, token in enumerate(tokens)
    )


class PostgresConnection:
    def __init__(self, url, schema=None):
        options = {}
        connection_options = psycopg.conninfo.conninfo_to_dict(url)
        if connection_options.get("host") not in ("localhost", "127.0.0.1", "::1"):
            options["sslmode"] = connection_options.get("sslmode", "require")
            if options["sslmode"] not in ("require", "verify-ca", "verify-full"):
                raise ValueError("Remote PostgreSQL connections require SSL.")
        # Dedicated schemas are used only by the opt-in integration test suite.
        if schema:
            if not re.fullmatch(r"test_[a-z0-9_]+", schema):
                raise ValueError("Invalid test database schema.")
            options["options"] = f"-csearch_path={schema},pg_catalog"
        self.connection = psycopg.connect(
            url, autocommit=True, prepare_threshold=None, connect_timeout=10,
            row_factory=record_factory, **options,
        )

    def execute(self, statement, parameters=None):
        if parameters is None:
            return self.connection.execute(statement)
        return self.connection.execute(postgres_parameters(statement), parameters)

    def executemany(self, statement, parameters):
        with self.connection.cursor() as cursor:
            cursor.executemany(postgres_parameters(statement), parameters)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()
