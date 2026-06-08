# -*- coding: utf-8 -*-
"""Комментарии к таблице gs_sys.gs_sys_economic_activity_types.

Revision ID: t4u5v6w7x8y9
Revises: s2t3u4v5w6x7
Create Date: 2026-06-08
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "t4u5v6w7x8y9"
down_revision = "s2t3u4v5w6x7"
branch_labels = None
depends_on = None

_COMMON_COLUMNS = {
    "id": "Уникальный идентификатор записи",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
    "ref_uuid": "Стабильный UUID записи справочника (единый между версиями БД)",
    "version": "Номер версии записи (оптимистическая блокировка)",
}

_SCHEMA_COMMENTS: dict[str, dict[str, dict[str, str]]] = {
    "gs_sys": {
        "gs_sys_economic_activity_types": {
            "_table": "Справочник видов экономической деятельности (ВЭД)",
            "display_order": "Порядок отображения",
            "name": "Вид экономической деятельности",
            "name_2": "Вид экономической деятельности_2",
        },
    },
}


def _comment_on_table(conn, schema: str, table: str, comment: str | None) -> None:
    if not column_utils.table_exists(conn, schema, table):
        return
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(
    conn, schema: str, table: str, column: str, comment: str | None
) -> None:
    if not column_utils.table_has_column(conn, schema, table, column):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def _apply_comments(conn, schema_comments: dict[str, dict[str, dict[str, str]]], clear: bool) -> None:
    for schema, tables in schema_comments.items():
        for table, comments in tables.items():
            table_comment = None if clear else comments.get("_table")
            _comment_on_table(conn, schema, table, table_comment)

            merged_columns = {**_COMMON_COLUMNS, **comments}
            for column, comment in merged_columns.items():
                if column == "_table":
                    continue
                column_comment = None if clear else comment
                _comment_on_column(conn, schema, table, column, column_comment)


def upgrade():
    conn = op.get_bind()
    _apply_comments(conn, _SCHEMA_COMMENTS, clear=False)


def downgrade():
    conn = op.get_bind()
    _apply_comments(conn, _SCHEMA_COMMENTS, clear=True)
