import pytest
from sqlalchemy import create_engine, event

from app.migration_safety import foreign_keys_off_during


@pytest.fixture
def connection(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")

    @event.listens_for(engine, "connect")
    def _enforce(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE TABLE parents (id TEXT PRIMARY KEY)")
        conn.exec_driver_sql(
            "CREATE TABLE children (id TEXT PRIMARY KEY, parent_id TEXT REFERENCES parents (id))"
        )
        conn.exec_driver_sql("INSERT INTO parents VALUES ('p1')")
        conn.exec_driver_sql("INSERT INTO children VALUES ('c1', 'p1')")
        conn.commit()
        yield conn
    engine.dispose()


def _enforced(conn):
    return conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_lets_a_parent_row_be_dropped_and_rebuilt(connection):
    with foreign_keys_off_during(connection):
        connection.exec_driver_sql("CREATE TABLE new_parents (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO new_parents SELECT id FROM parents")
        connection.exec_driver_sql("DROP TABLE parents")
        connection.exec_driver_sql("ALTER TABLE new_parents RENAME TO parents")
        connection.commit()

    assert _enforced(connection)


def test_fails_when_the_block_leaves_a_broken_reference(connection):
    with pytest.raises(RuntimeError, match="children"):
        with foreign_keys_off_during(connection):
            connection.exec_driver_sql("DELETE FROM parents")
            connection.commit()


def test_ignores_broken_references_that_were_already_there(connection):
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    connection.exec_driver_sql("INSERT INTO children VALUES ('orphan', 'gone')")
    connection.commit()
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    with foreign_keys_off_during(connection):
        pass

    assert _enforced(connection)


def test_turns_enforcement_back_on_when_the_block_fails(connection):
    with pytest.raises(ValueError):
        with foreign_keys_off_during(connection):
            raise ValueError

    assert _enforced(connection)


def test_does_nothing_on_other_databases():
    class NotSqlite:
        class dialect:
            name = "postgresql"

    with foreign_keys_off_during(NotSqlite()):
        pass
