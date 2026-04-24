"""add_prospective_place_type

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-03-19

Создает справочник gs_prospective_place_types (основная площадка, резервная площадка)
и связь с machine_prospective_place_aes.
"""
from alembic import op
import sqlalchemy as sa


revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE_TYPES = "gs_prospective_place_types"
TABLE_MACHINE = "machine_prospective_place_aes"


def upgrade():
    # 1. Создаем таблицу справочника типов площадок
    op.create_table(
        TABLE_TYPES,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA_REF,
    )
    op.create_index(
        "ix_gs_prospective_place_types_name",
        TABLE_TYPES,
        ["name"],
        unique=True,
        schema=SCHEMA_REF,
    )

    # 2. Вставляем значения по умолчанию
    op.execute(
        f"INSERT INTO {SCHEMA_REF}.{TABLE_TYPES} (name) VALUES ('основная площадка'), ('резервная площадка')"
    )

    # 3. Добавляем FK в machine_prospective_place_aes
    op.add_column(
        TABLE_MACHINE,
        sa.Column("id_prospective_place_type", sa.Integer(), nullable=True),
        schema=SCHEMA_GEN,
    )
    op.create_index(
        "ix_machine_prospective_place_aes_id_prospective_place_type",
        TABLE_MACHINE,
        ["id_prospective_place_type"],
        schema=SCHEMA_GEN,
    )
    op.create_foreign_key(
        "fk_machine_prospective_place_aes_prospective_place_type",
        TABLE_MACHINE,
        TABLE_TYPES,
        ["id_prospective_place_type"],
        ["id"],
        source_schema=SCHEMA_GEN,
        referent_schema=SCHEMA_REF,
        ondelete="RESTRICT",
    )

    # 4. Удаляем старое поле site_type
    op.drop_column(TABLE_MACHINE, "site_type", schema=SCHEMA_GEN)


def downgrade():
    # 1. Восстанавливаем site_type
    op.add_column(
        TABLE_MACHINE,
        sa.Column("site_type", sa.String(length=255), nullable=True),
        schema=SCHEMA_GEN,
    )

    # 2. Удаляем FK и колонку id_prospective_place_type
    op.drop_constraint(
        "fk_machine_prospective_place_aes_prospective_place_type",
        TABLE_MACHINE,
        schema=SCHEMA_GEN,
        type_="foreignkey",
    )
    op.drop_index(
        "ix_machine_prospective_place_aes_id_prospective_place_type",
        table_name=TABLE_MACHINE,
        schema=SCHEMA_GEN,
    )
    op.drop_column(TABLE_MACHINE, "id_prospective_place_type", schema=SCHEMA_GEN)

    # 3. Удаляем таблицу справочника
    op.drop_index("ix_gs_prospective_place_types_name", table_name=TABLE_TYPES, schema=SCHEMA_REF)
    op.drop_table(TABLE_TYPES, schema=SCHEMA_REF)
