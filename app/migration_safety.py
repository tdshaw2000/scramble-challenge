from collections import Counter
from contextlib import contextmanager


def _broken_references(connection) -> Counter:
    # Counted per (child table, parent table): rowids change when batch mode rebuilds a table.
    rows = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
    return Counter((table, parent) for table, _rowid, parent, _fkid in rows)


@contextmanager
def foreign_keys_off_during(connection):
    """Run a block with SQLite foreign keys off, as SQLite's table-rebuild procedure needs.

    Batch-mode migrations drop and recreate tables that other rows point at, which fails
    with enforcement on. Afterwards, fail on any broken reference the block added; ones
    that were already there (from before enforcement was switched on) are left alone.
    """
    if connection.dialect.name != "sqlite":
        yield
        return

    before = _broken_references(connection)
    # The pragma is a no-op inside a transaction.
    connection.commit()
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        yield
        added = _broken_references(connection) - before
        if added:
            raise RuntimeError(f"Migration left broken foreign keys: {dict(added)}")
    finally:
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
