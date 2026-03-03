"""add created_by/modified_by to generation, fuel, auth, logs, refdata tables

Revision ID: e6f7a8b9c0d1
Revises: b42547847dca
Create Date: 2026-02-18 10:00:00.000000

Миграция добавляет поля аудита (created_by, modified_by) во все таблицы
моделей, которые ранее не имели AuditMixin:
- generation: stations, machines, pgu_machines, station_powers, machine_powers,
  pgu_machine_powers, machine_names, machine_tes_types, machine_fuels,
  station_groups, boilers, documents_kommod
- fuel: gs_fue_equipment_group_sets, gs_fue_equipment_group_set_stations,
  все таблицы gs_fue_em_*
- auth: users, roles
- refdata: gs_database_versions
- logs: logs
"""

from alembic import op
import sqlalchemy as sa
from config import (
    SCHEMA_AUTH,
    SCHEMA_FUE_EM,
    SCHEMA_FUEL,
    SCHEMA_GENERATION,
    SCHEMA_LOGS,
    SCHEMA_REFDATA,
)


# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "b42547847dca"
branch_labels = None
depends_on = None


def _add_audit_columns(table_name: str, schema: str) -> None:
    """Добавить created_by / modified_by в указанную таблицу."""
    op.add_column(
        table_name,
        sa.Column("created_by", sa.String(length=255), nullable=True),
        schema=schema,
    )
    op.add_column(
        table_name,
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        schema=schema,
    )


def _drop_audit_columns(table_name: str, schema: str) -> None:
    """Удалить created_by / modified_by из указанной таблицы."""
    op.drop_column(table_name, "modified_by", schema=schema)
    op.drop_column(table_name, "created_by", schema=schema)


def upgrade():
    # --- SCHEMA_GENERATION ---
    gen_tables = [
        "stations",
        "machines",
        "pgu_machines",
        "station_powers",
        "machine_powers",
        "pgu_machine_powers",
        "machine_names",
        "machine_tes_types",
        "machine_fuels",
        "station_groups",
        "boilers",
        "documents_kommod",
    ]
    for t in gen_tables:
        _add_audit_columns(t, SCHEMA_GENERATION)

    # --- SCHEMA_FUEL ---
    fuel_tables = [
        "gs_fue_equipment_group_sets",
        "gs_fue_equipment_group_set_stations",
    ]
    for t in fuel_tables:
        _add_audit_columns(t, SCHEMA_FUEL)

    # --- SCHEMA_FUE_EM ---
    fue_em_tables = [
        "gs_fue_em_equipment_group",
        "gs_fue_em_cities",
        "gs_fue_em_gen_company_branch",
        "gs_fue_em_gen_company",
        "gs_fue_em_economic_region",
        "gs_fue_em_territories_energy",
        "gs_fue_em_federal_district",
        "gs_fue_em_union_energy_system",
        "gs_fue_em_business_unit",
        "gs_fue_em_department",
    ]
    for t in fue_em_tables:
        _add_audit_columns(t, SCHEMA_FUE_EM)

    # --- SCHEMA_AUTH ---
    _add_audit_columns("users", SCHEMA_AUTH)
    _add_audit_columns("roles", SCHEMA_AUTH)

    # --- SCHEMA_REFDATA ---
    _add_audit_columns("gs_database_versions", SCHEMA_REFDATA)

    # --- SCHEMA_LOGS ---
    _add_audit_columns("logs", SCHEMA_LOGS)


def downgrade():
    # --- SCHEMA_LOGS ---
    _drop_audit_columns("logs", SCHEMA_LOGS)

    # --- SCHEMA_REFDATA ---
    _drop_audit_columns("gs_database_versions", SCHEMA_REFDATA)

    # --- SCHEMA_AUTH ---
    _drop_audit_columns("roles", SCHEMA_AUTH)
    _drop_audit_columns("users", SCHEMA_AUTH)

    # --- SCHEMA_FUE_EM ---
    for t in reversed(
        [
            "gs_fue_em_equipment_group",
            "gs_fue_em_cities",
            "gs_fue_em_gen_company_branch",
            "gs_fue_em_gen_company",
            "gs_fue_em_economic_region",
            "gs_fue_em_territories_energy",
            "gs_fue_em_federal_district",
            "gs_fue_em_union_energy_system",
            "gs_fue_em_business_unit",
            "gs_fue_em_department",
        ]
    ):
        _drop_audit_columns(t, SCHEMA_FUE_EM)

    # --- SCHEMA_FUEL ---
    for t in reversed(
        [
            "gs_fue_equipment_group_sets",
            "gs_fue_equipment_group_set_stations",
        ]
    ):
        _drop_audit_columns(t, SCHEMA_FUEL)

    # --- SCHEMA_GENERATION ---
    for t in reversed(
        [
            "stations",
            "machines",
            "pgu_machines",
            "station_powers",
            "machine_powers",
            "pgu_machine_powers",
            "machine_names",
            "machine_tes_types",
            "machine_fuels",
            "station_groups",
            "boilers",
            "documents_kommod",
        ]
    ):
        _drop_audit_columns(t, SCHEMA_GENERATION)
