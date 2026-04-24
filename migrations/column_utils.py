# -*- coding: utf-8 -*-
"""Утилиты для idempotent-миграций (PostgreSQL)."""
from sqlalchemy import text
from sqlalchemy.engine import Connection


def table_exists(conn: Connection, schema: str, table: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.tables
            where table_schema = :schema and table_name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def table_has_column(conn: Connection, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def column_is_nullable(conn: Connection, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            select is_nullable
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    if row is None:
        return False
    return (row[0] or "").upper() == "YES"


def index_exists(conn: Connection, schema: str, index_name: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from pg_indexes
            where schemaname = :schema and indexname = :index_name
            """
        ),
        {"schema": schema, "index_name": index_name},
    ).fetchone()
    return row is not None
