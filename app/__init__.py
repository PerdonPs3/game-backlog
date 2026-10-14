from pathlib import Path
from flask import Flask


def create_app():
    app = Flask(__name__)

    instance_path = Path(app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)

    app.config["DATABASE"] = str(instance_path / "backlog.sqlite")

    from app import db
    app.teardown_appcontext(db.close_db)
    app.cli.add_command(db.init_db_command)
    
    from app.routes import main
    app.register_blueprint(main)

    return app