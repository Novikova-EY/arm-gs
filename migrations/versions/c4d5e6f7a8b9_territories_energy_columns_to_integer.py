"""territories_energy: obl, alph, dep, oes, er, terr_belyaev, teo90, fo -> Integer

Revision ID: c4d5e6f7a8b9
Revises: a9b8c7d6e5f4
Create Date: 2026-03-11

Меняет тип колонок obl, alph, dep, oes, er, terr_belyaev, teo90, fo
в gs_fue_em_territories_energy с VARCHAR на INTEGER.
Удаляет FK dep, oes, er, fo (ссылались на external_id String).
"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUE_EM


revision = "c4d5e6f7a8b9"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_territories_energy"
SCHEMA = SCHEMA_FUE_EM

# FK constraints to drop (column names were renamed dep_topl->dep etc., constraint names stayed)
FK_NAMES = [
    "fk_territories_energy_dep_topl",
    "fk_territories_energy_oes_topl",
    "fk_territories_energy_er_topl",
    "fk_territories_energy_fo_topl",
]

COLUMNS_TO_INTEGER = ["obl", "alph", "dep", "oes", "er", "terr_belyaev", "teo90", "fo"]


def _constraint_exists(conn, name):
    r = conn.execute(
        sa.text(
            """
            SELECT 1 FROM information_schema.table_constraints
            WHERE constraint_schema = :schema
              AND table_name = :table
              AND constraint_name = :name
            """
        ),
        {"schema": SCHEMA, "table": TABLE, "name": name},
    ).scalar()
    return r is not None


def upgrade():
    conn = op.get_bind()

    # 1. Drop FK constraints
    for fk_name in FK_NAMES:
        if _constraint_exists(conn, fk_name):
            op.drop_constraint(
                fk_name,
                TABLE,
                type_="foreignkey",
                schema=SCHEMA,
            )

    # 2. Alter columns: VARCHAR -> INTEGER (numeric strings convert, non-numeric -> NULL)
    for col in COLUMNS_TO_INTEGER:
        op.execute(
            sa.text(
                f"""
                ALTER TABLE {SCHEMA}.{TABLE}
                ALTER COLUMN {col} TYPE INTEGER
                USING (
                    CASE
                        WHEN {col} IS NULL OR TRIM({col}) = '' THEN NULL
                        WHEN {col} ~ '^-?[0-9]+$' THEN {col}::integer
                        ELSE NULL
                    END
                )
                """
            )
        )


def downgrade():
    # 1. Alter columns back: INTEGER -> VARCHAR
    for col in COLUMNS_TO_INTEGER:
        op.execute(
            sa.text(
                f"""
                ALTER TABLE {SCHEMA}.{TABLE}
                ALTER COLUMN {col} TYPE VARCHAR(255)
                USING ({col}::text)
                """
            )
        )

    # 2. Resize dep, oes, er, fo to String(80) and recreate FK constraints
    for col in ["dep", "oes", "er", "fo"]:
        op.execute(
            sa.text(
                f"""
                ALTER TABLE {SCHEMA}.{TABLE}
                ALTER COLUMN {col} TYPE VARCHAR(80)
                """
            )
        )

    with op.batch_alter_table(TABLE, schema=SCHEMA) as batch_op:
        batch_op.create_foreign_key(
            "fk_territories_energy_dep_topl",
            "gs_fue_em_department",
            ["dep"],
            ["external_id"],
            referent_schema=SCHEMA,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_oes_topl",
            "gs_fue_em_union_energy_system",
            ["oes"],
            ["external_id"],
            referent_schema=SCHEMA,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_er_topl",
            "gs_fue_em_economic_region",
            ["er"],
            ["external_id"],
            referent_schema=SCHEMA,
        )
        batch_op.create_foreign_key(
            "fk_territories_energy_fo_topl",
            "gs_fue_em_federal_district",
            ["fo"],
            ["external_id"],
            referent_schema=SCHEMA,
        )
