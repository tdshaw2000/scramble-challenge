import pytest

from app import create_app
from app.extensions import db as _db
from tests.fakes import FakeClock, FakeTNoodle


@pytest.fixture
def app():
    app = create_app("testing")
    app.extensions["tnoodle"] = FakeTNoodle()
    app.extensions["clock"] = FakeClock()
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        # Each app gets its own in-memory database, so disposing the engine discards it.
        _db.engine.dispose()


@pytest.fixture
def db(app):
    return _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def tnoodle(app):
    return app.extensions["tnoodle"]


@pytest.fixture
def clock(app):
    return app.extensions["clock"]
