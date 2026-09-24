from datetime import UTC, datetime

from app import create_app
from app.tnoodle import TNoodleClient


def test_testing_config_uses_in_memory_sqlite():
    app = create_app("testing")

    assert app.testing is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://"


def test_production_config_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/scramble.db")

    app = create_app("production")

    assert app.testing is False
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:////data/scramble.db"


def test_production_app_talks_to_tnoodle_at_the_configured_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("TNOODLE_URL", "http://tnoodle:2014")

    app = create_app("production")

    assert isinstance(app.extensions["tnoodle"], TNoodleClient)
    assert app.extensions["tnoodle"].base_url == "http://tnoodle:2014"


def test_app_clock_returns_current_utc_time():
    app = create_app("testing")

    now = app.extensions["clock"]()

    assert now.tzinfo is not None
    assert abs((now - datetime.now(UTC)).total_seconds()) < 5


def test_config_values_can_be_overridden_when_creating_the_app(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path}/x.db")

    assert app.config["SQLALCHEMY_DATABASE_URI"] == f"sqlite:///{tmp_path}/x.db"
    assert app.testing is True
