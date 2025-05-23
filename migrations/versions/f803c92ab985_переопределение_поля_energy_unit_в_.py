"""переопределение поля energy_unit в модели machine

Revision ID: f803c92ab985
Revises: a66982ee17a3
Create Date: 2025-05-21 10:44:06.053814
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f803c92ab985'
down_revision = 'a66982ee17a3'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.alter_column('id_energy_unit',
            existing_type=mysql.INTEGER(),
            nullable=True
        )
        # Удалим ошибочный индекс, если он вдруг был создан (может потребоваться вручную до этого шага)
        # batch_op.drop_index('ix_stations_name')

        # Создаём составной уникальный индекс по name + id_regional_district
        batch_op.create_index(
            'uq_station_name_district',
            ['name', 'id_regional_district'],
            unique=True
        )

def downgrade():
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.drop_index('uq_station_name_district')
        batch_op.alter_column('id_energy_unit',
            existing_type=mysql.INTEGER(),
            nullable=False
        )
