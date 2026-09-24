from pathlib import Path

from flask import Flask

from app.config import CONFIGS
from app.extensions import db, migrate
from app.models import utcnow
from app.tnoodle import TNoodleClient


def create_app(config_name: str = "production") -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name]())

    db.init_app(app)
    migrate.init_app(
        app,
        db,
        directory=str(Path(app.root_path).parent / "migrations"),
        # SQLite can't ALTER most things in place; batch mode rebuilds the table instead.
        render_as_batch=True,
    )

    app.extensions["tnoodle"] = TNoodleClient(app.config["TNOODLE_URL"])
    app.extensions["clock"] = utcnow

    from app.routes import bp

    app.register_blueprint(bp)

    return app
