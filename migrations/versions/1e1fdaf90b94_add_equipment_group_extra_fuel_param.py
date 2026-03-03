"""add_equipment_group_extra_fuel_param

Revision ID: 1e1fdaf90b94
Revises: b5c6d7e8f9a0
Create Date: 2026-02-26 14:18:15.665177

"""
from alembic import op
import sqlalchemy as sa


revision = '1e1fdaf90b94'
down_revision = 'b5c6d7e8f9a0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gs_fue_equipment_group_extra_fuel_param',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_equipment_group_set', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=512), nullable=True),
        sa.Column('year_number', sa.Integer(), nullable=True),
        sa.Column('gaz_prir', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gazpp', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('disel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maztop', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gtt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nft_proch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('domen_g', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('koks_g', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('prochgaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tvproch', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('szh_gaz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('inoe', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nazar', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ibor', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('berez', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('per', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('irbei', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kansk', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gusin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tugn', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('okino', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('azey', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mug', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('cher', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('jer', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karab', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('vork', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('intin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('sver', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kizel', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('har', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('urt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tataur', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tarbag', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zab_kam', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('rai', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('erk', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ogodj', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('svo', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bikin', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('razdol', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('hankai', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('neru', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zyryan', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('pyak', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuzngd', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznt', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznss', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznun', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bering', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('anad', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ekib', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maikub', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karag', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karajyra', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('teniz', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('numb1120', sa.Integer(), nullable=True),
        sa.Column('numb1', sa.Integer(), nullable=True),
        sa.Column('database_version_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['database_version_id'], ['gs_sys.gs_database_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['id_equipment_group_set'], ['gs_fue.gs_fue_equipment_group_sets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id_equipment_group_set', 'year_number', name='uq_equipment_group_extra_fuel_param_set_year'),
        schema='gs_fue'
    )
    op.create_index('ix_eg_extra_fuel_param_eg_set', 'gs_fue_equipment_group_extra_fuel_param', ['id_equipment_group_set'], unique=False, schema='gs_fue')
    op.create_index('ix_eg_extra_fuel_param_year', 'gs_fue_equipment_group_extra_fuel_param', ['year_number'], unique=False, schema='gs_fue')
    op.create_index('ix_eg_extra_fuel_param_numb1120', 'gs_fue_equipment_group_extra_fuel_param', ['numb1120'], unique=False, schema='gs_fue')


def downgrade():
    op.drop_table('gs_fue_equipment_group_extra_fuel_param', schema='gs_fue')
