from pathlib import Path
import os
from flask import Flask
from secrets import token_hex
from flask_wtf.csrf import CSRFProtect

def create_app(test_config=None):
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    app.config["DATABASE"] = str(instance_path / "backlog.sqlite")
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024

    if test_config is None:
        app.config.from_pyfile(
            str(instance_path / "config.py"),
            silent=True,
        )

    if test_config is not None:
        app.config.update(test_config)
    else:
        for name in ("DATABASE_URL", "SECRET_KEY", "IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET"):
            if name in os.environ:
                app.config[name] = os.environ[name]

    database_url = app.config.get("DATABASE_URL")
    if test_config is None and os.environ.get("VERCEL") and not database_url:
        raise ValueError("Set DATABASE_URL before running on Vercel; SQLite is local-only.")
    if database_url and not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
    if not app.config.get("SECRET_KEY"):
        if database_url:
            raise ValueError("Set SECRET_KEY before using PostgreSQL; no local secret file is created.")
        instance_path.mkdir(parents=True, exist_ok=True)
        secret_path = instance_path / "secret_key"
        if not secret_path.exists():
            secret_path.write_text(token_hex(32), encoding="utf-8")
        app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8")
    elif not database_url:
        instance_path.mkdir(parents=True, exist_ok=True)
    CSRFProtect(app)

    from app import db
    app.teardown_appcontext(db.close_db)
    app.cli.add_command(db.init_db_command)
    from app.migrations import migrate_db_command, check_db_command, migrate_sqlite_command
    app.cli.add_command(migrate_db_command)
    app.cli.add_command(check_db_command)
    app.cli.add_command(migrate_sqlite_command)

    from app.catalog import check_igdb_command
    app.cli.add_command(check_igdb_command)

    from app.routes import main
    app.register_blueprint(main)

    from app.game_fields import STATUSES

    @app.context_processor
    def game_choices():
        return {"game_statuses": STATUSES}

    return app
