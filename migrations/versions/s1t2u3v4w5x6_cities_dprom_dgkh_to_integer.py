"""cities dprom_ao, dgkh_ao: String(255) -> Integer

Revision ID: s1t2u3v4w5x6
Revises: l1m2n3o4p5q6
Create Date: 2026-02-27

Меняет тип dprom_ao, dgkh_ao в gs_fue_em_cities с String(255) на Integer.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_FUE_EM


revision = "s1t2u3v4w5x6"
down_revision = "l1m2n3o4p5q6"
branch_labels = None
depends_on = None

TABLE = "gs_fue_em_cities"
SCHEMA = SCHEMA_FUE_EM


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns_info = {c["name"]: c for c in inspector.get_columns(TABLE, schema=SCHEMA)}

    for col in ("dprom_ao", "dgkh_ao"):
        col_type = str(columns_info.get(col, {}).get("type", ""))
        if "INT" in col_type.upper():
            continue  # уже Integer
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.String(255),
            type_=sa.Integer(),
            schema=SCHEMA,
            postgresql_using=(
                "NULLIF(REGEXP_REPLACE(TRIM(" + col + "::text), '[^0-9-]', '', 'g'), '')::integer"
            ),
        )


def downgrade():
    for col in ("dprom_ao", "dgkh_ao"):
        op.alter_column(
            TABLE,
            col,
            existing_type=sa.Integer(),
            type_=sa.String(255),
            schema=SCHEMA,
            postgresql_using=col + "::varchar(255)",
        )
