"""Snapshots of the SQLite database, kept in their own folder (the `backups` volume).

    python -m app.backup snapshot <kind>   take one now (the deploy uses kind "predeploy")
    python -m app.backup schedule          take a "nightly" one at 03:00 UK time, forever
    python -m app.backup list              newest first
    python -m app.backup restore <name>    put one back (stop the web container first)

Snapshots use SQLite's online backup, so they are consistent even while a game is being
played. Each kind keeps its newest KEEP files.
"""

import os
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KEEP = 14
NIGHTLY_HOUR = 3
UK = ZoneInfo("Europe/London")


class BackupError(Exception):
    pass


def _copy(source, dest):
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def snapshot(db_path, backup_dir, kind, now=None, keep=KEEP):
    """Copy the database to <backup_dir>/<kind>-<UTC time>.db and prune that kind.
    Returns the new file, or None when there is no database yet."""
    db_path, backup_dir = Path(db_path), Path(backup_dir)
    if not db_path.exists():
        return None
    now = now or datetime.now(UTC)
    backup_dir.mkdir(parents=True, exist_ok=True)
    path = backup_dir / f"{kind}-{now.astimezone(UTC):%Y%m%d-%H%M%S}.db"
    partial = path.with_suffix(".partial")
    try:
        _copy(db_path, partial)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    for old in sorted(backup_dir.glob(f"{kind}-*.db"), reverse=True)[keep:]:
        old.unlink()
    return path


def list_snapshots(backup_dir):
    """Every snapshot, newest first."""
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    stamp = lambda p: p.stem.rsplit("-", 2)[-2:]  # noqa: E731
    return sorted(backup_dir.glob("*.db"), key=stamp, reverse=True)


def restore(name, db_path, backup_dir, now=None):
    """Put snapshot <name> back in place of the database, first saving the current one
    as a "prerestore" snapshot."""
    backup_dir = Path(backup_dir)
    source = backup_dir / name
    if Path(name).name != name or source not in list_snapshots(backup_dir):
        raise BackupError(f"No snapshot called {name} in {backup_dir}")
    snapshot(db_path, backup_dir, "prerestore", now=now)
    _copy(source, db_path)


def next_nightly(now):
    """The next 03:00 in the UK strictly after `now`, in UTC."""
    local = now.astimezone(UK)
    day = local.date()
    while True:
        run = datetime(day.year, day.month, day.day, NIGHTLY_HOUR, tzinfo=UK)
        if run > local:
            return run.astimezone(UTC)
        day += timedelta(days=1)


def run_schedule(db_path, backup_dir, clock=lambda: datetime.now(UTC), sleep=time.sleep):
    while True:
        due = next_nightly(clock())
        sleep((due - clock()).total_seconds())
        try:
            path = snapshot(db_path, backup_dir, "nightly", now=due)
            print(f"Nightly snapshot: {path}", flush=True)
        except Exception as error:  # keep going; tomorrow may work
            print(f"Nightly snapshot failed: {error}", file=sys.stderr, flush=True)


def db_path_from_url(url):
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url == prefix:
        raise BackupError(f"Only SQLite database files can be backed up, not {url}")
    return Path(url[len(prefix) :])


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        db_path = db_path_from_url(os.environ["DATABASE_URL"])
        backup_dir = Path(os.environ.get("BACKUP_DIR", "/backups"))
        match args:
            case ["snapshot", kind]:
                path = snapshot(db_path, backup_dir, kind)
                print(f"Snapshot: {path}" if path else f"No database at {db_path} yet")
            case ["schedule"]:
                print(f"Nightly snapshots at 0{NIGHTLY_HOUR}:00 UK time", flush=True)
                run_schedule(db_path, backup_dir)
            case ["list"]:
                for path in list_snapshots(backup_dir):
                    print(f"{path.name}  {path.stat().st_size // 1024} KB")
            case ["restore", name]:
                restore(name, db_path, backup_dir)
                print(f"Restored {name}")
            case _:
                print(__doc__, file=sys.stderr)
                return 2
    except BackupError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
