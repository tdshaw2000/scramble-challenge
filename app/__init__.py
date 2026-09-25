from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import CONFIGS
from app.extensions import db, migrate, socketio
from app.models import utcnow
from app.tnoodle import TNoodleClient


def create_app(config_name: str = "production", **overrides) -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name]())
    app.config.update(overrides)

    if proxies := app.config["TRUSTED_PROXIES"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=proxies, x_host=proxies)

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

    from app import sockets  # noqa: F401  (registers the socket event handlers)
    from app.routes import bp

    app.register_blueprint(bp)
    socketio.init_app(app, async_mode=app.config["SOCKETIO_ASYNC_MODE"])

    return app
