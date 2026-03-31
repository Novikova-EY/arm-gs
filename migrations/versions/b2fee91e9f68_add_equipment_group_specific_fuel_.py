"""add_equipment_group_specific_fuel_consumption

Revision ID: b2fee91e9f68
Revises: 99c688ce3393
Create Date: 2026-03-12 15:47:30.026867

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'b2fee91e9f68'
down_revision = '99c688ce3393'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_consumption'


def _table_exists(connection):
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": TABLE},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn):
        return
    op.create_table(TABLE,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('equipment_group_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=512), nullable=True),
    sa.Column('year_number', sa.Integer(), nullable=True),
    sa.Column('k', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('y', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('btp', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('sntp', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('bk', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('numb1120', sa.Integer(), nullable=True),
    sa.Column('snk', sa.Numeric(precision=20, scale=6), nullable=True),
    sa.Column('database_version_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['database_version_id'], ['gs_sys.gs_database_versions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['equipment_group_id'], ['gs_fue.gs_fue_equipment_groups.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('equipment_group_id', 'year_number', name='uq_equipment_group_specific_fuel_consumption_group_year'),
    schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)
