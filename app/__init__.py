from flask import Flask

from app.config import CONFIGS
from app.extensions import db, migrate


def create_app(config_name: str = "production") -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name]())

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401  (registers the tables with SQLAlchemy)

    return app
