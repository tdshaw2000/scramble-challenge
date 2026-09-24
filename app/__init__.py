from flask import Flask

from app.config import CONFIGS


def create_app(config_name: str = "production") -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name]())
    return app
