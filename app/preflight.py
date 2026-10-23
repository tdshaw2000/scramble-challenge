"""Try the database migrations on a throwaway copy of the live database.

    python -m app.preflight

scripts/deploy.sh runs this with the new image before restarting anything, so a
migration that would fail on real data stops the deploy while the old version is
still serving, instead of leaving the new one crash-looping.
"""

import os
import sys
import tempfile
from pathlib import Path

from alembic import command

from app import create_app
from app.backup import _copy, db_path_from_url
from app.extensions import db


class PreflightError(Exception):
    pass


def check_migrations(db_path):
    """Upgrade a copy of <db_path> to head. Returns False when there is no database yet
    (a fresh install has nothing to check); raises PreflightError when the upgrade fails."""
    db_path = Path(db_path)
    if not db_path.exists():
        return False
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / db_path.name
        _copy(db_path, copy)
        app = create_app("production", SQLALCHEMY_DATABASE_URI=f"sqlite:///{copy}")
        with app.app_context():
            try:
                # Alembic's own upgrade, not flask_migrate's: that one swallows the error
                # into a bare exit code.
                command.upgrade(app.extensions["migrate"].migrate.get_config(), "head")
            except Exception as error:
                raise PreflightError(f"Migrations fail on a copy of {db_path}: {error}") from error
            finally:
                # Let go of the copy before the temporary directory is removed.
                db.engine.dispose()
    return True


def main(argv=None):
    db_path = db_path_from_url(os.environ["DATABASE_URL"])
    try:
        checked = check_migrations(db_path)
    except PreflightError as error:
        print(error, file=sys.stderr)
        return 1
    print("ok: migrations work on a copy" if checked else f"No database at {db_path} yet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
