from pathlib import Path

from flask import Flask

from app.config import CONFIGS
from app.extensions import db, migrate


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

    from app import models  # noqa: F401  (registers the tables with SQLAlchemy)
    from app.routes import bp

    app.register_blueprint(bp)

    return app
