import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db as _db
from tests.fakes import FakeClock, FakeTNoodle

PASSWORD = "correct horse"


@pytest.fixture
def app():
    """The normal test app, with the admin area switched on."""
    app = create_app(
        "testing",
        ADMIN_PASSWORD_HASH=generate_password_hash(PASSWORD),
        SECRET_KEY="test-secret",
    )
    app.extensions["tnoodle"] = FakeTNoodle()
    app.extensions["clock"] = FakeClock()
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.engine.dispose()


@pytest.fixture
def admin(client):
    """A test client that has logged in to the admin area."""
    client.post("/admin/login", data={"password": PASSWORD})
    return client
