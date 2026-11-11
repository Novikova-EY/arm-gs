from io import StringIO

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from config import SCHEMA_RATIONAL_STRUCTURE

NEW_COLUMNS = (
    "design_head", "steam_capacity", "heat_power", "fuel_project", "fuel_main",
    "fuel_reserve", "efficiency_gross", "water_consumption", "operation_mode",
)


def render_sql(monkeypatch, legacy_migration, direction):
    migration = legacy_migration("rs26102602_generalize_technical_characteristics")
    output = StringIO()
    operations = Operations(MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    ))
    monkeypatch.setattr(migration, "op", operations)
    getattr(migration, direction)()
    return output.getvalue()


def test_upgrade_renames_table_and_permits_new_equipment_types(monkeypatch, legacy_migration):
    sql = render_sql(monkeypatch, legacy_migration, "upgrade")
    assert (
        f"ALTER TABLE {SCHEMA_RATIONAL_STRUCTURE}.gs_rs_turbine_technical_characteristics "
        "RENAME TO gs_rs_equipment_technical_characteristics"
    ) in sql
    assert "RENAME turbine_type TO equipment_type" in sql
    assert sql.index("DROP CONSTRAINT ck_rs_turbine_type") < sql.index("ADD CONSTRAINT ck_rs_equipment_type")
    assert "equipment_type IN ('steam', 'gas', 'hydro', 'boiler_energy', 'boiler_water')" in sql
    assert "uq_rs_equipment_code_year_version UNIQUE (database_version_id, equipment_type, equipment_code, report_year)" in sql
    assert all(f"ADD COLUMN {name}" in sql for name in NEW_COLUMNS)


def test_downgrade_returns_turbine_schema_and_drops_other_kinds(monkeypatch, legacy_migration):
    sql = render_sql(monkeypatch, legacy_migration, "downgrade")
    assert (
        f"DELETE FROM {SCHEMA_RATIONAL_STRUCTURE}.gs_rs_equipment_technical_characteristics "
        "WHERE equipment_type NOT IN ('steam', 'gas')"
    ) in sql
    assert all(f"DROP COLUMN {name}" in sql for name in NEW_COLUMNS)
    assert "equipment_type IN ('steam', 'gas')" in sql
    assert "RENAME equipment_type TO turbine_type" in sql
    assert (
        f"ALTER TABLE {SCHEMA_RATIONAL_STRUCTURE}.gs_rs_equipment_technical_characteristics "
        "RENAME TO gs_rs_turbine_technical_characteristics"
    ) in sql
    assert sql.index("DROP CONSTRAINT ck_rs_equipment_type") < sql.index("ADD CONSTRAINT ck_rs_turbine_type")
