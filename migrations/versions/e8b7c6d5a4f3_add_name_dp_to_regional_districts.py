"""add name_dp to gs_regional_districts

Revision ID: e8b7c6d5a4f3
Revises: d5e6f7a8b9c0
Create Date: 2025-12-25 00:00:00.000000

Добавляет поле name_dp (полное наименование в дательном падеже)
в таблицу gs_regional_districts (схема refdata / gs_sys).
"""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "e8b7c6d5a4f3"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Добавляем колонку как nullable (чтобы не упасть на существующих строках)
    op.add_column(
        "gs_regional_districts",
        sa.Column("name_dp", sa.String(length=255), nullable=True),
        schema=SCHEMA_REFDATA,
    )

    # 2) Заполняем существующие строки (fallback: name_full -> name)
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA_REFDATA}.gs_regional_districts
            SET name_dp = COALESCE(name_dp, name_full, name)
            WHERE name_dp IS NULL
            """
        )
    )

    # 3) Делаем NOT NULL
    op.alter_column(
        "gs_regional_districts",
        "name_dp",
        existing_type=sa.String(length=255),
        nullable=False,
        schema=SCHEMA_REFDATA,
    )


def downgrade():
    op.drop_column("gs_regional_districts", "name_dp", schema=SCHEMA_REFDATA)


