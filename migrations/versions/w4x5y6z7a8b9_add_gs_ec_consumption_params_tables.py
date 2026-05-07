# -*- coding: utf-8 -*-
"""Схема gs_ec и таблицы параметров потребления электроэнергии (*_consumption_params).

Revision ID: w4x5y6z7a8b9
Revises: f7e8d9c0b1a2
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "w4x5y6z7a8b9"
down_revision = "f7e8d9c0b1a2"
branch_labels = None
depends_on = None

SCHEMA_EC = "gs_ec"
SCHEMA_REFDATA = "gs_sys"

# (table_name, fk_column_or_None, ref_table_without_schema_or_None)
TABLE_SPECS: tuple[tuple[str, str | None, str | None], ...] = (
    ("gs_ec_centralized_zone_consumption_params", None, None),
    ("gs_ec_ees_consumption_params", None, None),
    ("gs_ec_ees_russia_consumption_params", None, None),
    ("gs_ec_ees_russia_with_nt_consumption_params", None, None),
    ("gs_ec_russia_federation_consumption_params", None, None),
    ("gs_ec_russia_federation_with_nt_consumption_params", None, None),
    ("gs_ec_energy_area_consumption_params", "id_energy_area", "gs_sys_energy_areas"),
    ("gs_ec_energy_system_type_consumption_params", "id_energy_system_type", "gs_sys_energy_system_types"),
    ("gs_ec_energy_unit_consumption_params", "id_energy_unit", "gs_sys_energy_units"),
    ("gs_ec_energy_zone_consumption_params", "id_energy_zone", "gs_sys_energy_zones"),
    ("gs_ec_federal_district_consumption_params", "id_federal_district", "gs_sys_federal_districts"),
    ("gs_ec_regional_district_consumption_params", "id_regional_district", "gs_sys_regional_districts"),
    ("gs_ec_regional_energy_system_consumption_params", "id_regional_energy_system", "gs_sys_regional_energy_systems"),
    ("gs_ec_synchronous_area_consumption_params", "id_synchronous_area", "gs_sys_synchronous_areas"),
    ("gs_ec_union_energy_system_consumption_params", "id_union_energy_system", "gs_sys_union_energy_systems"),
)


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _table_exists(connection, schema: str, table: str) -> bool:
    r = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return r.fetchone() is not None


def _short_prefix(table: str) -> str:
    """Короткий префикс для имён индексов (лимит PostgreSQL 63 символа)."""
    return table.replace("gs_ec_", "").replace("_consumption_params", "")[:24]


def upgrade():
    conn = op.get_bind()
    if not _schema_exists(conn, SCHEMA_EC):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_EC}"'))

    numeric = sa.Numeric(precision=25, scale=16)

    for table, fk_col, ref_tbl in TABLE_SPECS:
        if _table_exists(conn, SCHEMA_EC, table):
            continue

        cols = [
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        ]
        fks: list = []

        if fk_col and ref_tbl:
            cols.append(sa.Column(fk_col, sa.Integer(), nullable=False))
            fks.append(
                sa.ForeignKeyConstraint(
                    [fk_col],
                    [f"{SCHEMA_REFDATA}.{ref_tbl}.id"],
                    ondelete="RESTRICT",
                ),
            )

        cols.extend(
            [
                sa.Column("year_number", sa.Integer(), nullable=True),
                sa.Column("energy_consumption_mln_kvt_ch", numeric, nullable=True),
                sa.Column("energy_consumption_sipr_mln_kvt_ch", numeric, nullable=True),
                sa.Column("note", sa.Text(), nullable=True),
                sa.Column("created_by", sa.String(length=255), nullable=True),
                sa.Column("modified_by", sa.String(length=255), nullable=True),
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("now()"),
                    nullable=False,
                ),
                sa.Column(
                    "updated_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("now()"),
                    nullable=False,
                ),
                sa.Column("database_version_id", sa.Integer(), nullable=True),
            ]
        )
        fks.append(
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
                ondelete="SET NULL",
            ),
        )

        op.create_table(
            table,
            *cols,
            *fks,
            sa.PrimaryKeyConstraint("id"),
            schema=SCHEMA_EC,
        )

        pfx = _short_prefix(table)
        if fk_col:
            op.create_index(
                f"ix_gs_ec_{pfx}_{fk_col[:12]}",
                table,
                [fk_col],
                unique=False,
                schema=SCHEMA_EC,
            )
        op.create_index(
            f"ix_gs_ec_{pfx}_year",
            table,
            ["year_number"],
            unique=False,
            schema=SCHEMA_EC,
        )
        op.create_index(
            f"ix_gs_ec_{pfx}_dbver",
            table,
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_EC,
        )

        # Одна строка на (сущность,) год и версию БД; отдельно — не более одной строки с year_number IS NULL.
        if fk_col:
            op.execute(
                sa.text(
                    f"""
                    CREATE UNIQUE INDEX uq_gs_ec_{pfx}_year
                    ON "{SCHEMA_EC}"."{table}" (
                        {fk_col},
                        year_number,
                        COALESCE(database_version_id, 0)
                    )
                    WHERE year_number IS NOT NULL
                    """
                )
            )
            op.execute(
                sa.text(
                    f"""
                    CREATE UNIQUE INDEX uq_gs_ec_{pfx}_nullyear
                    ON "{SCHEMA_EC}"."{table}" (
                        {fk_col},
                        COALESCE(database_version_id, 0)
                    )
                    WHERE year_number IS NULL
                    """
                )
            )
        else:
            op.execute(
                sa.text(
                    f"""
                    CREATE UNIQUE INDEX uq_gs_ec_{pfx}_year
                    ON "{SCHEMA_EC}"."{table}" (
                        year_number,
                        COALESCE(database_version_id, 0)
                    )
                    WHERE year_number IS NOT NULL
                    """
                )
            )
            op.execute(
                sa.text(
                    f"""
                    CREATE UNIQUE INDEX uq_gs_ec_{pfx}_nullyear
                    ON "{SCHEMA_EC}"."{table}" (
                        COALESCE(database_version_id, 0)
                    )
                    WHERE year_number IS NULL
                    """
                )
            )


def downgrade():
    conn = op.get_bind()
    for table, _, _ in reversed(TABLE_SPECS):
        if _table_exists(conn, SCHEMA_EC, table):
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{SCHEMA_EC}"."{table}" CASCADE'))
    # схему gs_ec не удаляем — могут появиться другие объекты
