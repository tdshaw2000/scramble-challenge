import os


class Config:
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # How long the CO can be away (e.g. a page refresh) before the challenge ends.
    CO_GRACE_SECONDS = 30
    # Folder under static/themes/ holding theme.css. Swap the look by changing this.
    THEME = "mario64"
    # How many proxies (e.g. Caddy) sit in front of the app. Their X-Forwarded-* headers
    # are only trusted when this is above 0, so share links get the public https address.
    TRUSTED_PROXIES = 0
    # Threads for tests and the dev server; production runs under gunicorn's gevent worker.
    SOCKETIO_ASYNC_MODE = "threading"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    TNOODLE_URL = "http://tnoodle.invalid"


class ProductionConfig(Config):
    SOCKETIO_ASYNC_MODE = "gevent"

    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
        self.TNOODLE_URL = os.environ.get("TNOODLE_URL", "http://localhost:2014")
        self.TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))


CONFIGS = {
    "testing": TestingConfig,
    "production": ProductionConfig,
}
