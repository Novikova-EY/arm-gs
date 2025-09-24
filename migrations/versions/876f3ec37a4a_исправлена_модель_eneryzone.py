"""исправлена модель eneryzone

Revision ID: 876f3ec37a4a
Revises: 33bc86c53bdc
Create Date: 2025-09-22 10:13:57.633529

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '876f3ec37a4a'
down_revision = '33bc86c53bdc'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('energy_zones', schema='refdata')}
    if 'id_regional_district' in cols:
        # если раньше были FK/индекс — удалите их по вашим именам (если есть)
        # op.drop_constraint('fk_energy_zones_regional_district', 'energy_zones',
        #                   schema='refdata', type_='foreignkey')
        # op.drop_index('ix_energy_zones_id_regional_district',
        #               table_name='energy_zones', schema='refdata')

        # на случай, если колонка была NOT NULL — сделаем nullable
        with op.batch_alter_table('energy_zones', schema='refdata') as batch_op:
            batch_op.alter_column('id_regional_district', existing_type=sa.Integer(), nullable=True)
        # теперь удаляем колонку
        with op.batch_alter_table('energy_zones', schema='refdata') as batch_op:
            batch_op.drop_column('id_regional_district')

def downgrade():
    with op.batch_alter_table('energy_zones', schema='refdata') as batch_op:
        batch_op.add_column(sa.Column('id_regional_district', sa.Integer(), nullable=True))
    # при необходимости — восстановить индекс/FK