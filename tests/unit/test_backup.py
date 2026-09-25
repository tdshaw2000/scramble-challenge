"""Database snapshots: one before every deploy and one a night, kept on their own volume."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app import backup


def make_db(path, *names):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE players (name TEXT)")
    conn.executemany("INSERT INTO players VALUES (?)", [(n,) for n in names])
    conn.commit()
    conn.close()


def names_in(path):
    conn = sqlite3.connect(path)
    try:
        return [row[0] for row in conn.execute("SELECT name FROM players ORDER BY name")]
    finally:
        conn.close()


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "data" / "scramble.db"
    path.parent.mkdir()
    make_db(path, "Ann", "Bob")
    return path


@pytest.fixture
def backup_dir(tmp_path):
    return tmp_path / "backups"


NOON = datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)


def test_snapshot_is_a_full_copy_named_after_its_kind_and_utc_time(db_path, backup_dir):
    path = backup.snapshot(db_path, backup_dir, "predeploy", now=NOON)

    assert path == backup_dir / "predeploy-20260925-120000.db"
    assert names_in(path) == ["Ann", "Bob"]


def test_snapshot_is_consistent_while_another_connection_is_mid_write(db_path, backup_dir):
    writer = sqlite3.connect(db_path)
    writer.execute("INSERT INTO players VALUES ('Cat')")  # open, uncommitted transaction

    path = backup.snapshot(db_path, backup_dir, "nightly", now=NOON)
    writer.rollback()
    writer.close()

    assert names_in(path) == ["Ann", "Bob"]


def test_snapshot_of_a_missing_database_does_nothing_and_creates_no_file(tmp_path, backup_dir):
    missing = tmp_path / "nope.db"

    assert backup.snapshot(missing, backup_dir, "predeploy", now=NOON) is None
    assert not missing.exists()


def test_snapshot_keeps_only_the_newest_of_its_own_kind(db_path, backup_dir):
    for day in range(1, 5):
        backup.snapshot(db_path, backup_dir, "nightly", now=NOON.replace(day=day), keep=2)
    backup.snapshot(db_path, backup_dir, "predeploy", now=NOON.replace(day=1), keep=2)

    assert sorted(p.name for p in backup_dir.iterdir()) == [
        "nightly-20260903-120000.db",
        "nightly-20260904-120000.db",
        "predeploy-20260901-120000.db",
    ]


def test_by_default_fourteen_of_each_kind_are_kept(db_path, backup_dir):
    for day in range(1, 17):
        backup.snapshot(db_path, backup_dir, "nightly", now=NOON.replace(day=day))

    assert len(list(backup_dir.iterdir())) == 14
    assert not (backup_dir / "nightly-20260902-120000.db").exists()


def test_snapshots_are_listed_newest_first(db_path, backup_dir):
    backup.snapshot(db_path, backup_dir, "nightly", now=NOON.replace(day=1))
    backup.snapshot(db_path, backup_dir, "predeploy", now=NOON.replace(day=2))

    assert [p.name for p in backup.list_snapshots(backup_dir)] == [
        "predeploy-20260902-120000.db",
        "nightly-20260901-120000.db",
    ]


def test_restore_puts_a_snapshot_back_and_first_saves_what_it_replaces(db_path, backup_dir):
    old = backup.snapshot(db_path, backup_dir, "nightly", now=NOON.replace(day=1))
    make_db(db_path.parent / "other.db", "Zed")
    db_path.unlink()
    (db_path.parent / "other.db").rename(db_path)

    backup.restore(old.name, db_path, backup_dir, now=NOON)

    assert names_in(db_path) == ["Ann", "Bob"]
    assert names_in(backup_dir / "prerestore-20260925-120000.db") == ["Zed"]


@pytest.mark.parametrize("name", ["missing.db", "../data/scramble.db", "/etc/passwd"])
def test_restore_only_accepts_a_snapshot_in_the_backup_folder(name, db_path, backup_dir):
    backup_dir.mkdir()

    with pytest.raises(backup.BackupError):
        backup.restore(name, db_path, backup_dir, now=NOON)
    assert names_in(db_path) == ["Ann", "Bob"]


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # British Summer Time: 03:00 in London is 02:00 UTC.
        (datetime(2026, 9, 25, 1, 0, tzinfo=UTC), datetime(2026, 9, 25, 2, 0, tzinfo=UTC)),
        (datetime(2026, 9, 25, 2, 0, tzinfo=UTC), datetime(2026, 9, 26, 2, 0, tzinfo=UTC)),
        (datetime(2026, 9, 25, 12, 0, tzinfo=UTC), datetime(2026, 9, 26, 2, 0, tzinfo=UTC)),
        # Winter: 03:00 in London is 03:00 UTC.
        (datetime(2026, 12, 1, 12, 0, tzinfo=UTC), datetime(2026, 12, 2, 3, 0, tzinfo=UTC)),
        # The night the clocks go back (25 October 2026).
        (datetime(2026, 10, 24, 12, 0, tzinfo=UTC), datetime(2026, 10, 25, 3, 0, tzinfo=UTC)),
    ],
)
def test_the_nightly_snapshot_runs_at_three_in_the_morning_uk_time(now, expected):
    assert backup.next_nightly(now) == expected


def test_the_schedule_sleeps_until_three_then_snapshots_every_night(db_path, backup_dir):
    now = [datetime(2026, 9, 25, 12, 0, tzinfo=UTC)]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if len(slept) == 3:
            raise KeyboardInterrupt
        now[0] = now[0] + timedelta(seconds=seconds)

    with pytest.raises(KeyboardInterrupt):
        backup.run_schedule(db_path, backup_dir, clock=lambda: now[0], sleep=sleep)

    assert slept[:2] == [14 * 3600, 24 * 3600]
    assert [p.name for p in backup.list_snapshots(backup_dir)] == [
        "nightly-20260927-020000.db",
        "nightly-20260926-020000.db",
    ]


def test_a_failed_nightly_snapshot_does_not_stop_the_schedule(tmp_path, backup_dir, capsys):
    bad = tmp_path / "bad.db"
    bad.write_text("this is not a database")
    now = [datetime(2026, 9, 25, 12, 0, tzinfo=UTC)]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if len(slept) == 2:
            raise KeyboardInterrupt
        now[0] = backup.next_nightly(now[0])

    with pytest.raises(KeyboardInterrupt):
        backup.run_schedule(bad, backup_dir, clock=lambda: now[0], sleep=sleep)

    assert len(slept) == 2
    assert "failed" in capsys.readouterr().err


def test_db_path_comes_from_the_sqlite_database_url():
    assert str(backup.db_path_from_url("sqlite:////data/scramble.db")) == "/data/scramble.db"
    with pytest.raises(backup.BackupError):
        backup.db_path_from_url("postgresql://x/y")


def test_command_line_snapshot_list_and_restore(db_path, backup_dir, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))

    assert backup.main(["snapshot", "predeploy"]) == 0
    made = capsys.readouterr().out
    assert "predeploy-" in made

    assert backup.main(["list"]) == 0
    listed = capsys.readouterr().out
    name = listed.split()[0]
    assert name.startswith("predeploy-")

    assert backup.main(["restore", name]) == 0
    assert "Restored" in capsys.readouterr().out


def test_command_line_reports_a_bad_restore_without_a_traceback(
    db_path, backup_dir, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BACKUP_DIR", str(backup_dir))

    assert backup.main(["restore", "nope.db"]) == 1
    assert "nope.db" in capsys.readouterr().err
