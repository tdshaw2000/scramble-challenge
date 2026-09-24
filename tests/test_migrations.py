from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from app import create_app
from app.extensions import db


def test_migrations_produce_the_same_schema_as_the_models(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'migrated.db'}")
    app = create_app("production")

    with app.app_context():
        upgrade()
        with db.engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"compare_type": True, "render_as_batch": True}
            )
            differences = compare_metadata(context, db.metadata)

    assert differences == []
