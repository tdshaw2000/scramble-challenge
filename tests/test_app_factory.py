from app import create_app


def test_testing_config_uses_in_memory_sqlite():
    app = create_app("testing")

    assert app.testing is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"


def test_production_config_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/scramble.db")

    app = create_app("production")

    assert app.testing is False
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:////data/scramble.db"
