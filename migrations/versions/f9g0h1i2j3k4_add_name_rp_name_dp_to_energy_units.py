"""add name_rp and name_dp to gs_energy_units

Revision ID: f9g0h1i2j3k4
Revises: a2b3c4d5e6f7
Create Date: 2026-02-12 00:00:00.000000

Добавляет поля name_rp (полное наименование в родительном падеже)
и name_dp (полное наименование в дательном падеже) в таблицу gs_energy_units (схема refdata).
"""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_REFDATA


revision = "f9g0h1i2j3k4"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Добавляем колонки как nullable (чтобы не упасть на существующих строках)
    op.add_column(
        "gs_energy_units",
        sa.Column("name_rp", sa.String(length=255), nullable=True),
        schema=SCHEMA_REFDATA,
    )
    op.add_column(
        "gs_energy_units",
        sa.Column("name_dp", sa.String(length=255), nullable=True),
        schema=SCHEMA_REFDATA,
    )

    # 2) Заполняем существующие строки из name
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_REFDATA}.gs_energy_units
            SET name_rp = COALESCE(name_rp, name),
                name_dp = COALESCE(name_dp, name)
            WHERE name_rp IS NULL OR name_dp IS NULL
            """
        )
    )

    # 3) Делаем NOT NULL
    op.alter_column(
        "gs_energy_units",
        "name_rp",
        existing_type=sa.String(length=255),
        nullable=False,
        schema=SCHEMA_REFDATA,
    )
    op.alter_column(
        "gs_energy_units",
        "name_dp",
        existing_type=sa.String(length=255),
        nullable=False,
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_energy_units", "name_dp", schema=SCHEMA_REFDATA)
    op.drop_column("gs_energy_units", "name_rp", schema=SCHEMA_REFDATA)
