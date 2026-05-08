"""add_prospective_place_type

Revision ID: q9r0s1t2u3v4
Revises: p8q9r0s1t2u3
Create Date: 2026-03-19

Создает справочник gs_prospective_place_types (основная площадка, резервная площадка)
и связь с machine_prospective_place_aes.
"""
import os
import sys

from alembic import op
import sqlalchemy as sa

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "q9r0s1t2u3v4"
down_revision = "p8q9r0s1t2u3"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
SCHEMA_REF = "gs_sys"
TABLE_TYPES = "gs_prospective_place_types"
TABLE_MACHINE = "machine_prospective_place_aes"


def upgrade():
    conn = op.get_bind()
    table_machine = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    if table_machine is None:
        return
    table_types = column_utils.prospective_place_types_aes_table_name(conn, SCHEMA_REF)

    # 1. Создаем таблицу справочника типов площадок
    if table_types is None:
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
        if not column_utils.index_exists(conn, SCHEMA_REF, "ix_gs_prospective_place_types_name"):
            op.create_index(
                "ix_gs_prospective_place_types_name",
                TABLE_TYPES,
                ["name"],
                unique=True,
                schema=SCHEMA_REF,
            )
        table_types = TABLE_TYPES

    # 2. Вставляем значения по умолчанию
    op.execute(
        f"INSERT INTO {SCHEMA_REF}.{table_types} (name) VALUES ('основная площадка'), ('резервная площадка') ON CONFLICT DO NOTHING"
    )

    # 3. Добавляем FK в machine_prospective_place_aes
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "id_prospective_place_type"):
        op.add_column(
            table_machine,
            sa.Column("id_prospective_place_type", sa.Integer(), nullable=True),
            schema=SCHEMA_GEN,
        )
    if not column_utils.index_exists(conn, SCHEMA_GEN, "ix_machine_prospective_place_aes_id_prospective_place_type"):
        op.create_index(
            "ix_machine_prospective_place_aes_id_prospective_place_type",
            table_machine,
            ["id_prospective_place_type"],
            schema=SCHEMA_GEN,
        )
    if not column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_machine_prospective_place_aes_prospective_place_type"):
        op.create_foreign_key(
            "fk_machine_prospective_place_aes_prospective_place_type",
            table_machine,
            table_types,
            ["id_prospective_place_type"],
            ["id"],
            source_schema=SCHEMA_GEN,
            referent_schema=SCHEMA_REF,
            ondelete="RESTRICT",
        )

    # 4. Удаляем старое поле site_type
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "site_type"):
        op.drop_column(table_machine, "site_type", schema=SCHEMA_GEN)


def downgrade():
    conn = op.get_bind()
    table_machine = column_utils.machine_prospective_place_aes_table_name(conn, SCHEMA_GEN)
    table_types = column_utils.prospective_place_types_aes_table_name(conn, SCHEMA_REF)
    if table_machine is None or table_types is None:
        return
    # 1. Восстанавливаем site_type
    if not column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "site_type"):
        op.add_column(
            table_machine,
            sa.Column("site_type", sa.String(length=255), nullable=True),
            schema=SCHEMA_GEN,
        )

    # 2. Удаляем FK и колонку id_prospective_place_type
    if column_utils.constraint_exists(conn, SCHEMA_GEN, "fk_machine_prospective_place_aes_prospective_place_type"):
        op.drop_constraint(
            "fk_machine_prospective_place_aes_prospective_place_type",
            table_machine,
            schema=SCHEMA_GEN,
            type_="foreignkey",
        )
    if column_utils.index_exists(conn, SCHEMA_GEN, "ix_machine_prospective_place_aes_id_prospective_place_type"):
        op.drop_index(
            "ix_machine_prospective_place_aes_id_prospective_place_type",
            table_name=table_machine,
            schema=SCHEMA_GEN,
        )
    if column_utils.table_has_column(conn, SCHEMA_GEN, table_machine, "id_prospective_place_type"):
        op.drop_column(table_machine, "id_prospective_place_type", schema=SCHEMA_GEN)

    # 3. Удаляем таблицу справочника
    if column_utils.index_exists(conn, SCHEMA_REF, "ix_gs_prospective_place_types_name"):
        op.drop_index("ix_gs_prospective_place_types_name", table_name=table_types, schema=SCHEMA_REF)
    op.drop_table(table_types, schema=SCHEMA_REF)
