from pathlib import Path
from flask import Flask
from secrets import token_hex
from flask_wtf.csrf import CSRFProtect

def create_app(test_config=None):
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    secret_path = instance_path / "secret_key"

    if not secret_path.exists():
        secret_path.write_text(token_hex(32), encoding="utf-8")

    app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8")
    CSRFProtect(app)
    
    app.config["DATABASE"] = str(instance_path / "backlog.sqlite")

    if test_config is None:
        app.config.from_pyfile(
            str(instance_path / "config.py"),
            silent=True,
        )

    if test_config is not None:
        app.config.update(test_config)

    from app import db
    app.teardown_appcontext(db.close_db)
    app.cli.add_command(db.init_db_command)

    from app.catalog import check_igdb_command
    app.cli.add_command(check_igdb_command)

    from app.routes import main
    app.register_blueprint(main)

    return app
