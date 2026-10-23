import sqlite3
from contextlib import closing

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


def _live_like_database(tmp_path, monkeypatch):
    """A database one revision behind head, holding rows that point at each other."""
    db_file = tmp_path / "live.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    app = create_app("production")
    with app.app_context():
        upgrade(revision="5c1f0d2a7e3b")
    with closing(sqlite3.connect(db_file)) as conn, conn:
        conn.executescript(
            """
            INSERT INTO challenges VALUES ('c1', 'slug', NULL, 'open', NULL, '2026-01-01', NULL);
            INSERT INTO players VALUES ('p1', 'c1', 'cookie', 'Tim', 1, 0, '2026-01-01');
            INSERT INTO rounds VALUES ('r1', 'c1', 1, '333', 'R U', '<svg/>', 'open',
                                       '2026-01-01', NULL);
            UPDATE challenges SET co_player_id = 'p1', current_round_id = 'r1';
            INSERT INTO solves (id, round_id, player_id, plus_two) VALUES ('s1', 'r1', 'p1', 0);
            """
        )
    return app, db_file


def test_upgrade_keeps_rows_that_other_tables_point_at(tmp_path, monkeypatch):
    app, db_file = _live_like_database(tmp_path, monkeypatch)

    with app.app_context():
        upgrade()

    with closing(sqlite3.connect(db_file)) as conn, conn:
        assert conn.execute("SELECT id, timed_inspection FROM rounds").fetchall() == [("r1", 1)]
        assert conn.execute("SELECT id, round_id FROM solves").fetchall() == [("s1", "r1")]
        assert conn.execute("SELECT current_round_id FROM challenges").fetchall() == [("r1",)]


def test_upgrade_recovers_from_a_batch_table_left_by_a_failed_attempt(tmp_path, monkeypatch):
    app, db_file = _live_like_database(tmp_path, monkeypatch)
    with closing(sqlite3.connect(db_file)) as conn, conn:
        conn.execute("CREATE TABLE _alembic_tmp_rounds (id CHAR(32))")

    with app.app_context():
        upgrade()

    with closing(sqlite3.connect(db_file)) as conn, conn:
        assert conn.execute("SELECT id, timed_inspection FROM rounds").fetchall() == [("r1", 1)]
