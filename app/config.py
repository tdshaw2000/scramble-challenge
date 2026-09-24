import os


class Config:
    TESTING = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"


class ProductionConfig(Config):
    def __init__(self):
        self.SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]


CONFIGS = {
    "testing": TestingConfig,
    "production": ProductionConfig,
}
