from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b76c1114a0a0'
down_revision = '9faaee2b3798'
branch_labels = None
depends_on = None


def upgrade():
    # Ограничение уже есть в базе, поэтому ничего не делаем
    pass


def downgrade():
    # При откате можно удалить ограничение, если оно есть
    with op.batch_alter_table('stations') as batch_op:
        batch_op.drop_constraint(
            'uq_station_name_district',
            type_='unique'
        )
