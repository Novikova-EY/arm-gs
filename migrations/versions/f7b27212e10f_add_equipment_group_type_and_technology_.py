"""add equipment_group_type and technology_type fields

Revision ID: f7b27212e10f
Revises: 843ddbe65156
Create Date: 2025-10-02 16:46:48.930815

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7b27212e10f'
down_revision = '843ddbe65156'
branch_labels = None
depends_on = None
from sqlalchemy.dialects import postgresql
SCHEMA = "refdata"

def upgrade():
    bind = op.get_bind()

    # 1) Явно создаём ENUM в схеме refdata (если ещё нет)
    tech_enum = postgresql.ENUM(
        "открытая", "закрытая", "перспективная",
        name="technology_type_enum",
        schema=SCHEMA,
        create_type=True,
    )
    tech_enum.create(bind, checkfirst=True)

    # 2) Добавляем колонку equipment_group_type (обычная строка)
    op.add_column(
        "equipment_groups",
        sa.Column(
            "equipment_group_type",
            sa.String(length=50),
            nullable=True,
            comment="Тип группы оборудования",
        ),
        schema=SCHEMA,
    )

    # 3) Добавляем колонку technology_type, ЯВНО указывая схему типа
    #    (обходит любые проблемы с search_path и генерацией)
    op.execute(
        f'ALTER TABLE {SCHEMA}.equipment_groups '
        f'ADD COLUMN technology_type {SCHEMA}.technology_type_enum NULL'
    )
    # при желании можно дописать COMMENT:
    op.execute(
        f"COMMENT ON COLUMN {SCHEMA}.equipment_groups.technology_type IS 'Тип технологии'"
    )

def downgrade():
    # 1) Удаляем колонку
    op.drop_column("equipment_groups", "technology_type", schema=SCHEMA)
    op.drop_column("equipment_groups", "equipment_group_type", schema=SCHEMA)

    # 2) Удаляем тип, ЕСЛИ он больше нигде не используется
    tech_enum = postgresql.ENUM(
        "открытая", "закрытая", "перспективная",
        name="technology_type_enum",
        schema=SCHEMA,
    )
    tech_enum.drop(op.get_bind(), checkfirst=True)