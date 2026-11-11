from io import StringIO
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from config import SCHEMA_REFDATA


@pytest.fixture
def migration_sql(monkeypatch, legacy_migration):
    migration = legacy_migration("rs26102601_add_technical_inspection_codes")
    output = StringIO()
    operations = Operations(MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    ))
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        # Exercise the real table-name resolver against a small catalog fixture.
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS information_schema")
        conn.exec_driver_sql(
            "CREATE TABLE information_schema.tables "
            "(table_schema TEXT, table_name TEXT, table_type TEXT)"
        )
        monkeypatch.setattr(migration, "op", SimpleNamespace(
            get_bind=lambda: conn,
            create_table=operations.create_table,
            create_index=operations.create_index,
        ))
        yield migration, conn, output
    engine.dispose()


@pytest.mark.parametrize("relations, expected_table", [
    ([("gs_database_versions", "VIEW"),
      ("gs_sys_database_versions", "BASE TABLE")], "gs_sys_database_versions"),
    ([("gs_database_versions", "BASE TABLE")], "gs_database_versions"),
    ([("gs_database_versions", "BASE TABLE"),
      ("gs_sys_database_versions", "BASE TABLE")], "gs_sys_database_versions"),
])
def test_upgrade_references_physical_version_table(migration_sql, relations, expected_table):
    migration, conn, output = migration_sql
    conn.execute(sa.text(
        "INSERT INTO information_schema.tables VALUES (:schema, :name, :type)"
    ), [{"schema": SCHEMA_REFDATA, "name": name, "type": kind}
        for name, kind in relations])

    migration.upgrade()

    sql = output.getvalue()
    assert f"REFERENCES {SCHEMA_REFDATA}.{expected_table} (id) ON DELETE CASCADE" in sql
    if expected_table != "gs_database_versions":
        assert f"REFERENCES {SCHEMA_REFDATA}.gs_database_versions " not in sql


@pytest.mark.parametrize("relation_type", [None, "VIEW"])
def test_upgrade_rejects_missing_physical_version_table(migration_sql, relation_type):
    migration, conn, output = migration_sql
    if relation_type:
        conn.execute(sa.text(
            "INSERT INTO information_schema.tables VALUES (:schema, :name, :type)"
        ), {"schema": SCHEMA_REFDATA, "name": "gs_database_versions", "type": relation_type})

    with pytest.raises(RuntimeError, match="Не найдена таблица версий БД"):
        migration.upgrade()

    assert output.getvalue() == ""
