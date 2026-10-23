import sqlite3
from contextlib import closing

import pytest
from flask_migrate import upgrade

from app import create_app
from app.preflight import PreflightError, check_migrations, main


def _database_at(path, monkeypatch, revision):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    with create_app("production").app_context():
        upgrade(revision=revision)


def _version(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT version_num FROM alembic_version").fetchall()


def test_migrates_a_copy_and_leaves_the_live_database_alone(tmp_path, monkeypatch):
    live = tmp_path / "scramble.db"
    _database_at(live, monkeypatch, "5c1f0d2a7e3b")

    assert check_migrations(live) is True
    assert _version(live) == [("5c1f0d2a7e3b",)]


def test_fails_when_the_migrations_would_fail_and_leaves_the_live_database_alone(
    tmp_path, monkeypatch
):
    live = tmp_path / "scramble.db"
    _database_at(live, monkeypatch, "5c1f0d2a7e3b")
    with closing(sqlite3.connect(live)) as conn, conn:
        conn.execute("UPDATE alembic_version SET version_num = 'not-a-revision'")

    with pytest.raises(PreflightError):
        check_migrations(live)

    assert _version(live) == [("not-a-revision",)]


def test_a_fresh_install_with_no_database_has_nothing_to_check(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'scramble.db'}")

    assert check_migrations(tmp_path / "scramble.db") is False
    assert not (tmp_path / "scramble.db").exists()


def test_command_exits_non_zero_when_the_migrations_would_fail(tmp_path, monkeypatch, capsys):
    live = tmp_path / "scramble.db"
    _database_at(live, monkeypatch, "5c1f0d2a7e3b")
    with closing(sqlite3.connect(live)) as conn, conn:
        conn.execute("UPDATE alembic_version SET version_num = 'not-a-revision'")

    assert main() == 1
    assert "not-a-revision" in capsys.readouterr().err


def test_command_exits_zero_when_the_migrations_work(tmp_path, monkeypatch, capsys):
    _database_at(tmp_path / "scramble.db", monkeypatch, "5c1f0d2a7e3b")

    assert main() == 0
    assert "ok" in capsys.readouterr().out
