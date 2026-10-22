"""Пакеты топлива с акцептом и исходная принятая база.

Revision ID: ef26102001
Revises: z8v9p0c1a2l3
"""
import os
import sys
from collections import defaultdict
from decimal import Decimal

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY, SCHEMA_FUEL, SCHEMA_REFDATA

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "ef26102001"
down_revision = "z8v9p0c1a2l3"
branch_labels = None
depends_on = None


def upgrade():
    versions_table = column_utils.database_versions_physical_table_name(op.get_bind(), SCHEMA_REFDATA)
    if versions_table is None:
        raise RuntimeError("Не найдена таблица версий БД")
    for name in ("gs_eco_fuel_snapshots", "gs_eco_fuel_submissions"):
        columns = [
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("database_version_id", sa.Integer(), sa.ForeignKey(f"{SCHEMA_REFDATA}.{versions_table}.id", ondelete="CASCADE"), nullable=False),
            sa.Column("year_number", sa.Integer(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_by", sa.String(255)),
            sa.Column("modified_by", sa.String(255)),
        ]
        if name == "gs_eco_fuel_snapshots":
            columns += [
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.UniqueConstraint("database_version_id", "year_number", name="uq_eco_fuel_snapshot_version_year"),
            ]
        else:
            columns += [
                sa.Column("status", sa.String(20), nullable=False),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
                sa.Column("reviewed_at", sa.DateTime(timezone=True)),
            ]
        op.create_table(name, *columns, schema=SCHEMA_ECOLOGY)
    op.create_index("ix_eco_fuel_submission_version_year_status", "gs_eco_fuel_submissions", ["database_version_id", "year_number", "status"], schema=SCHEMA_ECOLOGY)
    _seed_accepted_inputs()


def _seed_accepted_inputs():
    # Сохраняем действующие значения всех версий до включения режима акцепта.
    from app.ecology.services.operating_tes_constants import FUEL_MAIN_SUM_FIELDS, FUEL_EXTRA_SUM_FIELDS
    from app.ecology.services.operating_tes_fuel_input_services import _distribute, empty_fuel_bucket

    fields = [(field, "p") for field in FUEL_MAIN_SUM_FIELDS] + [(field, "x") for field in FUEL_EXTRA_SUM_FIELDS]
    sums = ", ".join(f'coalesce(sum({alias}."{field}"), 0) AS "{field}"' for field, alias in fields)
    rows = op.get_bind().execute(sa.text(f'''
        SELECT p.database_version_id, p.year_number, p.ved, u.name AS ues_name, r.name AS res_name, {sums}
        FROM "{SCHEMA_FUEL}".gs_fue_equipment_group_fuel_param p
        JOIN "{SCHEMA_FUEL}".gs_fue_equipment_groups g ON g.id = p.equipment_group_id
        LEFT JOIN "{SCHEMA_FUEL}".gs_fue_equipment_group_extra_fuel_param x
          ON x.equipment_group_id = p.equipment_group_id AND x.year_number = p.year_number
          AND x.database_version_id IS NOT DISTINCT FROM p.database_version_id
        LEFT JOIN "{SCHEMA_REFDATA}".gs_sys_regional_energy_systems r ON r.id = g.regional_energy_system_id
        LEFT JOIN "{SCHEMA_REFDATA}".gs_sys_union_energy_systems u ON u.id = r.id_union_energy_system
        WHERE g.d = 1 AND p.ved > 0 AND p.database_version_id IS NOT NULL
          AND p.database_version_id IS NOT DISTINCT FROM g.database_version_id
        GROUP BY p.database_version_id, p.year_number, p.ved, u.name, r.name
    ''')).mappings()
    grouped = defaultdict(lambda: defaultdict(empty_fuel_bucket))
    for row in rows:
        bucket = grouped[(row["database_version_id"], row["year_number"])]
        _distribute(bucket, int(row["ved"]), row["ues_name"], row["res_name"], {field: Decimal(row[field]) for field, _ in fields})
    table = sa.table("gs_eco_fuel_snapshots", sa.column("database_version_id", sa.Integer), sa.column("year_number", sa.Integer), sa.column("payload", sa.JSON), schema=SCHEMA_ECOLOGY)
    for (version_id, year), buckets in grouped.items():
        payload = {slug: {field: str(value) for field, value in values.items()} for slug, values in buckets.items()}
        op.get_bind().execute(table.insert().values(database_version_id=version_id, year_number=year, payload=payload))


def downgrade():
    op.drop_table("gs_eco_fuel_submissions", schema=SCHEMA_ECOLOGY)
    op.drop_table("gs_eco_fuel_snapshots", schema=SCHEMA_ECOLOGY)
