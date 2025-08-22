"""добавлено поле в субъект (исправлено)

Revision ID: ae91a94fbde3
Revises: 94fa19439b16
Create Date: 2025-08-21 12:18:20.885243

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
SCHEMA = "refdata"

# revision identifiers, used by Alembic.
revision = 'ae91a94fbde3'
down_revision = '94fa19439b16'
branch_labels = None
depends_on = None


def upgrade():
    # 1) добавляем столбец
    op.add_column(
        'regional_districts',
        sa.Column('region_id', sa.Integer(), nullable=True),
        schema=SCHEMA,
    )
    # 2) создаём индекс
    op.create_index(
        op.f('ix_refdata_regional_districts_region_id'),
        'regional_districts',
        ['region_id'],
        unique=False,
        schema=SCHEMA,
    )


def downgrade():
    # порядок обратный: сначала индекс, потом колонка
    op.drop_index(
        op.f('ix_refdata_regional_districts_region_id'),
        table_name='regional_districts',
        schema=SCHEMA,
    )
    op.drop_column('regional_districts', 'region_id', schema=SCHEMA)