import os


class Config:
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # How long the CO can be away (e.g. a page refresh) before the challenge ends.
    CO_GRACE_SECONDS = 30
    # Folder under static/themes/ holding theme.css. Swap the look by changing this.
    THEME = "mario64"
    # Skins a player can pick from the gear menu (folder name: label). THEME is the default.
    THEMES = {"mario64": "Mario 64", "plain": "Plain", "monkeyisland2": "Monkey"}
    # How many proxies (e.g. Caddy) sit in front of the app. Their X-Forwarded-* headers
    # are only trusted when this is above 0, so share links get the public https address.
    TRUSTED_PROXIES = 0
    # Threads for tests and the dev server; production runs under gunicorn's gevent worker.
    SOCKETIO_ASYNC_MODE = "threading"
    # The admin area (/admin) exists only when both are set. The hash comes from
    # werkzeug.security.generate_password_hash; the key signs the login cookie.
    ADMIN_PASSWORD_HASH = None
    SECRET_KEY = None
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 30
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    TNOODLE_URL = "http://tnoodle.invalid"


class ProductionConfig(Config):
    SOCKETIO_ASYNC_MODE = "gevent"
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
        self.TNOODLE_URL = os.environ.get("TNOODLE_URL", "http://localhost:2014")
        self.TRUSTED_PROXIES = int(os.environ.get("TRUSTED_PROXIES", "0"))
        self.ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH")
        self.SECRET_KEY = os.environ.get("SECRET_KEY")


CONFIGS = {
    "testing": TestingConfig,
    "production": ProductionConfig,
}
