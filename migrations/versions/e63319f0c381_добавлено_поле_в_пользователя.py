"""добавлено поле в пользователя

Revision ID: e63319f0c381
Revises: a9667d18cfb3
Create Date: 2025-08-13 17:51:23.261570

"""
from alembic import op
import sqlalchemy as sa
SCHEMA = "auth"  # если у тебя схема другая — поменяй

# revision identifiers, used by Alembic.
revision = 'e63319f0c381'
down_revision = 'a9667d18cfb3'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Добавляем колонку как nullable=True
    op.add_column(
        'roles',
        sa.Column('name_full', sa.String(length=50), nullable=True),
        schema=SCHEMA
    )

    # 2) Заполняем существующие строки значением из name
    op.execute(f'UPDATE "{SCHEMA}".roles SET name_full = name')

    # 3) Делаем NOT NULL
    op.alter_column(
        'roles', 'name_full',
        existing_type=sa.String(length=50),
        nullable=False,
        schema=SCHEMA
    )

    # 4) Уникальность и индекс (как в модели)
    op.create_unique_constraint(
        'uq_roles_name_full', 'roles', ['name_full'], schema=SCHEMA
    )
    op.create_index(
        'ix_roles_name_full', 'roles', ['name_full'], unique=False, schema=SCHEMA
    )

def downgrade():
    op.drop_index('ix_roles_name_full', table_name='roles', schema=SCHEMA)
    op.drop_constraint('uq_roles_name_full', 'roles', type_='unique', schema=SCHEMA)
    op.drop_column('roles', 'name_full', schema=SCHEMA)