from pathlib import Path
from flask import Flask
from secrets import token_hex
from flask_wtf.csrf import CSRFProtect

def create_app():
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    secret_path = instance_path / "secret_key"

    if not secret_path.exists():
        secret_path.write_text(token_hex(32), encoding="utf-8")

    app.config["SECRET_KEY"] = secret_path.read_text(encoding="utf-8")
    CSRFProtect(app)
    
    app.config["DATABASE"] = str(instance_path / "backlog.sqlite")

    from app import db
    app.teardown_appcontext(db.close_db)
    app.cli.add_command(db.init_db_command)

    from app.routes import main
    app.register_blueprint(main)

    return app