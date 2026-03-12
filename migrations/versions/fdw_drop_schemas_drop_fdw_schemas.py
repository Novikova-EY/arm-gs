"""drop fdw_* schemas (временные FDW-схемы)

Revision ID: fdw_drop_schemas
Revises: c4d5e6f7a8b9
Create Date: 2026-03-11

Удаляет все схемы с префиксом fdw_ (fdw_gs_fue_em и др.).
"""
from alembic import op
from sqlalchemy import text


revision = "fdw_drop_schemas"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        text(
            """
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name LIKE 'fdw_%'
            """
        )
    )
    schemas = [row[0] for row in result]
    for schema in schemas:
        op.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


def downgrade():
    # Восстановление fdw_ схем не предусмотрено — они были временными
    pass
