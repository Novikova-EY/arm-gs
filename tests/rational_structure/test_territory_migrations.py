from io import StringIO
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


@pytest.fixture(params=[
    "rs26102603_add_territory_inputs",
    "rs26102604_add_territory_technologies",
    "rs26102605_add_calculation_workbooks",
    "rs26102701_add_territory_discount_rates",
])
def migration_sql(request, monkeypatch, legacy_migration):
    migration = legacy_migration(request.param)
    output = StringIO()
    operations = Operations(MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    ))
    engine = sa.create_engine("sqlite://")
    with engine.connect() as conn:
        # Run the real resolver against a catalog containing tables and views.
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS information_schema")
        conn.exec_driver_sql(
            "CREATE TABLE information_schema.tables "
            "(table_schema TEXT, table_name TEXT, table_type TEXT)"
        )
        monkeypatch.setattr(migration, "op", SimpleNamespace(
            get_bind=lambda: conn,
            create_table=operations.create_table,
            create_index=operations.create_index,
            drop_table=operations.drop_table,
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
    if migration.revision == "rs26102603":
        assert f"CREATE TABLE {SCHEMA_RATIONAL_STRUCTURE}.gs_rs_territory_inputs" in sql
        assert f"REFERENCES {SCHEMA_REFDATA}.gs_sys_energy_zones (id) ON DELETE CASCADE" in sql
        assert "CONSTRAINT uq_rs_territory_input_version_zone UNIQUE (database_version_id, energy_zone_id)" in sql


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


def test_downgrade_drops_tables_without_resolving_versions(migration_sql):
    migration, conn, output = migration_sql

    migration.downgrade()

    sql = output.getvalue()
    assert f"DROP TABLE {SCHEMA_RATIONAL_STRUCTURE}.gs_rs_" in sql
    assert "REFERENCES" not in sql
