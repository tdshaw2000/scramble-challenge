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


@pytest.fixture
def challenge(db):
    from app import services

    challenge = services.create_challenge("Tom", "cookie-co")
    # No sockets until step 3, so mark the CO connected by hand.
    challenge.co_player.connected = True
    _db.session.commit()
    return challenge


@pytest.fixture
def co(challenge):
    return challenge.co_player


@pytest.fixture
def add_player(db, challenge):
    from app.models import Player

    def add(name, connected=True):
        player = Player(
            challenge=challenge, cookie_id=f"cookie-{name}", display_name=name, connected=connected
        )
        _db.session.add(player)
        _db.session.commit()
        return player

    return add
