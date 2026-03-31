"""fix_machine_fuel_param_note_column_type

Revision ID: 99c688ce3393
Revises: 5f943277b415
Create Date: 2026-03-12 11:59:13.570714

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99c688ce3393'
down_revision = '5f943277b415'
branch_labels = None
depends_on = None


def upgrade():
    # Столбец note в БД может быть INTEGER (из старой схемы) — приводим к VARCHAR(255)
    # USING note::text — корректно для INTEGER и для уже VARCHAR
    op.execute(
        "ALTER TABLE gs_fue.gs_fue_machine_fuel_param "
        "ALTER COLUMN note TYPE VARCHAR(255) USING note::text"
    )


def downgrade():
    # Откат: VARCHAR -> INTEGER (только если значения — целые числа)
    op.alter_column(
        "gs_fue_machine_fuel_param",
        "note",
        existing_type=sa.String(length=255),
        type_=sa.INTEGER(),
        existing_nullable=True,
        schema="gs_fue",
        postgresql_using="note::integer",
    )
