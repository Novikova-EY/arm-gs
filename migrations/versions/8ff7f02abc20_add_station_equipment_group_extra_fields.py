"""add station equipment group extra fields

Revision ID: 8ff7f02abc20
Revises: b42547847dca
Create Date: 2026-01-19 13:11:05.752613

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ff7f02abc20'
down_revision = 'b42547847dca'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('station_equipment_groups', sa.Column('name', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('niv', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('comp', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('main', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('d', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('r', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('form', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('type', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('vedomstvo', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('obl', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('dep', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('oes', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('er', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('fo', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('numb', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('tm', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('n1', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('n2', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('p1', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('p2', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('ordnumb', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('addr', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('note', sa.String(length=1000), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('codegor', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('be', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('gk', sa.String(length=255), nullable=True), schema='gs_gen')
    op.add_column('station_equipment_groups', sa.Column('gkf', sa.String(length=255), nullable=True), schema='gs_gen')


def downgrade():
    op.drop_column('station_equipment_groups', 'gkf', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'gk', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'be', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'codegor', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'note', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'addr', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'ordnumb', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'p2', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'p1', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'n2', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'n1', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'tm', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'numb', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'fo', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'er', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'oes', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'dep', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'obl', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'vedomstvo', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'type', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'form', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'r', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'd', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'main', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'comp', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'niv', schema='gs_gen')
    op.drop_column('station_equipment_groups', 'name', schema='gs_gen')
