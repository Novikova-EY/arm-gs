"""link_natural_fuel_year_and_codes

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-07-23 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "x9y0z1a2b3c4"
down_revision = "w8x9y0z1a2b3"
branch_labels = None
depends_on = None

SCHEMA = "gs_fue"
TABLE = "gs_fue_equipment_group_natural_fuel"
FK_YEAR = "fk_equipment_group_natural_fuel_year_ver"


def _column_type(connection, column_name: str) -> str | None:
    row = connection.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND column_name = :col"
        ),
        {"schema": SCHEMA, "table": TABLE, "col": column_name},
    ).fetchone()
    return row[0] if row else None


def _fk_exists(connection) -> bool:
    row = connection.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = :schema AND table_name = :table "
            "AND constraint_name = :name AND constraint_type = 'FOREIGN KEY'"
        ),
        {"schema": SCHEMA, "table": TABLE, "name": FK_YEAR},
    ).fetchone()
    return row is not None


def upgrade():
    conn = op.get_bind()

    for col in ("obl", "dep", "oes", "er"):
        dtype = _column_type(conn, col)
        if dtype in ("character varying", "varchar", "text"):
            op.execute(
                text(
                    f"ALTER TABLE {SCHEMA}.{TABLE} "
                    f"ALTER COLUMN {col} TYPE INTEGER "
                    f"USING NULLIF(TRIM({col}::text), '')::integer"
                )
            )
            op.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS "
                    f"ix_gs_fue_equipment_group_natural_fuel_{col} "
                    f"ON {SCHEMA}.{TABLE} ({col})"
                )
            )

    if not _fk_exists(conn):
        # orphan year pairs cannot get FK; leave as-is if none, else fail clearly
        orphans = conn.execute(
            text(
                f"""
                SELECT COUNT(*) FROM {SCHEMA}.{TABLE} nf
                WHERE nf.year_number IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM gs_sys.gs_sys_years y
                    WHERE y.number = nf.year_number
                      AND y.database_version_id IS NOT DISTINCT FROM nf.database_version_id
                  )
                """
            )
        ).scalar()
        if orphans:
            raise RuntimeError(
                f"Нельзя добавить FK на Year: {orphans} строк в {TABLE} "
                "без пары (year_number, database_version_id) в gs_sys_years."
            )
        op.create_foreign_key(
            FK_YEAR,
            TABLE,
            "gs_sys_years",
            ["year_number", "database_version_id"],
            ["number", "database_version_id"],
            source_schema=SCHEMA,
            referent_schema="gs_sys",
            ondelete="RESTRICT",
        )


def downgrade():
    conn = op.get_bind()
    if _fk_exists(conn):
        op.drop_constraint(FK_YEAR, TABLE, schema=SCHEMA, type_="foreignkey")

    for col in ("obl", "dep", "oes", "er"):
        dtype = _column_type(conn, col)
        if dtype == "integer":
            op.execute(
                text(
                    f"ALTER TABLE {SCHEMA}.{TABLE} "
                    f"ALTER COLUMN {col} TYPE VARCHAR(80) "
                    f"USING {col}::varchar(80)"
                )
            )
