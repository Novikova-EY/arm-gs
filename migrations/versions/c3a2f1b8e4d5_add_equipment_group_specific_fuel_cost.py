"""add_equipment_group_specific_fuel_cost

Revision ID: c3a2f1b8e4d5
Revises: b2fee91e9f68
Create Date: 2026-03-12 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'c3a2f1b8e4d5'
down_revision = 'b2fee91e9f68'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_cost'


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
        sa.Column('gaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gaz_prir', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gazpp', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mazut', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('disel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maztop', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gtt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nft_proch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('torf', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('isk_gaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('domen_g', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('koks_g', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('prochgaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('proch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tvproch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('szh_gaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('inoe', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ugol', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('don', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('podm', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('pech', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('vork', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('intin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuzn', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuzngd', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznss', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznun', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ural', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('sver', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kizel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bashk', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kazah', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ekib', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maikub', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karag', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karajyra', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('teniz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kan', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nazar', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ibor', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('berez', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('per', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('irbei', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kansk', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('irkut', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('azey', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mug', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('cher', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tung', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('jer', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karab', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('hak', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tuv', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bur', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gusin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tugn', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('okino', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chit', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('har', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('urt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tataur', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tarbag', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zab_kam', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('amur', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('rai', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('erk', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ogodj', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('svo', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('urg', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ushum', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('prim', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bikin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('razdol', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('hankai', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('yakut', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('neru', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zyryan', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('pyak', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mag', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chukot', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('anad', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bering', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kamch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('sah', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ved', sa.Integer(), nullable=True),
        sa.Column('obl', sa.String(length=80), nullable=True),
        sa.Column('dep', sa.String(length=80), nullable=True),
        sa.Column('oes', sa.String(length=80), nullable=True),
        sa.Column('er', sa.String(length=80), nullable=True),
        sa.Column('numb1120', sa.Integer(), nullable=True),
        sa.Column('numb1', sa.Integer(), nullable=True),
        sa.Column('database_version_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['database_version_id'], ['gs_sys.gs_database_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['equipment_group_id'], ['gs_fue.gs_fue_equipment_groups.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('equipment_group_id', 'year_number', name='uq_equipment_group_specific_fuel_cost_group_year'),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)
