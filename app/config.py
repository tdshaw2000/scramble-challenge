import os


class Config:
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # How long the CO can be away (e.g. a page refresh) before the challenge ends.
    CO_GRACE_SECONDS = 30
    # Folder under static/themes/ holding theme.css. Swap the look by changing this.
    THEME = "mario64"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    TNOODLE_URL = "http://tnoodle.invalid"


class ProductionConfig(Config):
    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
        self.TNOODLE_URL = os.environ.get("TNOODLE_URL", "http://localhost:2014")


CONFIGS = {
    "testing": TestingConfig,
    "production": ProductionConfig,
}
