from pathlib import Path
from datetime import timedelta
import os
from flask import Flask
from secrets import token_hex
from urllib.parse import urlsplit
from flask_wtf.csrf import CSRFProtect

def create_app(test_config=None):
    hosted = test_config is None and bool(os.environ.get("VERCEL"))
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    app.config["DATABASE"] = str(instance_path / "backlog.sqlite")
    app.config["MAX_CONTENT_LENGTH"] = 3 * 1024 * 1024
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

    if test_config is None and not hosted:
        app.config.from_pyfile(
            str(instance_path / "config.py"),
            silent=True,
        )

    if test_config is not None:
        app.config.update(test_config)
    else:
        for name in ("DATABASE_URL", "SECRET_KEY", "IGDB_CLIENT_ID", "IGDB_CLIENT_SECRET", "SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "PUBLIC_MEMBER_COUNT_EXCLUDED_IDS"):
            if name in os.environ:
                app.config[name] = os.environ[name]

    database_url = app.config.get("DATABASE_URL")
    if hosted and not database_url:
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
    if hosted:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
        )
    app.config.setdefault("AUTH_ENABLED", bool(database_url) and not app.testing)
    if app.config["AUTH_ENABLED"]:
        auth_url = urlsplit(app.config.get("SUPABASE_URL", ""))
        if not database_url or auth_url.scheme != "https" or not auth_url.hostname or auth_url.username or auth_url.password or auth_url.query or auth_url.fragment or auth_url.path not in ("", "/"):
            raise ValueError("Accounts require PostgreSQL and an HTTPS SUPABASE_URL without credentials or a path.")
        if not app.config.get("SUPABASE_PUBLISHABLE_KEY"):
            raise ValueError("Set SUPABASE_PUBLISHABLE_KEY to enable accounts.")
    if hosted and not app.config["AUTH_ENABLED"]:
        raise ValueError("Accounts cannot be disabled on Vercel.")
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    CSRFProtect(app)

    from app import db
    app.teardown_appcontext(db.close_db)
    app.cli.add_command(db.init_db_command)
    from app.migrations import migrate_db_command, check_db_command, migrate_sqlite_command
    app.cli.add_command(migrate_db_command)
    app.cli.add_command(check_db_command)
    app.cli.add_command(migrate_sqlite_command)
    from app.profile_badges import set_admin_badge
    app.cli.add_command(set_admin_badge)

    from app.catalog import check_igdb_command
    app.cli.add_command(check_igdb_command)

    from app.routes import main
    app.register_blueprint(main)
    from app.auth import init_app as init_auth
    init_auth(app)
    from app.public_profiles import init_app as init_public_profiles
    init_public_profiles(app)
    from app.public_catalog import init_app as init_public_catalog
    init_public_catalog(app)

    from app.community import init_app as init_community
    init_community(app)

    from app.account_urls import init_app as init_account_urls
    init_account_urls(app)

    from app.game_fields import STATUSES, star_rating
    app.jinja_env.filters['star_rating'] = star_rating
    from app.countries import country_info
    app.jinja_env.filters['country_info'] = country_info

    @app.context_processor
    def game_choices():
        return {"game_statuses": STATUSES}

    return app
