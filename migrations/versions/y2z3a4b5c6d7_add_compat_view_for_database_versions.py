# -*- coding: utf-8 -*-
"""Add compatibility view gs_sys.gs_database_versions.

Revision ID: y2z3a4b5c6d7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-28
"""
from alembic import op

revision = "y2z3a4b5c6d7"
down_revision = "u1v2w3x4y5z6"
branch_labels = None
depends_on = None


def upgrade():
    # После переименования таблицы в gs_sys_database_versions
    # часть кода и старых ссылок ожидает legacy-имя gs_database_versions.
    # Создаем совместимый updatable VIEW только когда:
    # - новая таблица существует
    # - legacy-объект отсутствует
    op.execute(
        """
        DO $$
        DECLARE
            old_regclass regclass;
            new_regclass regclass;
        BEGIN
            SELECT to_regclass('gs_sys.gs_database_versions') INTO old_regclass;
            SELECT to_regclass('gs_sys.gs_sys_database_versions') INTO new_regclass;

            IF new_regclass IS NOT NULL AND old_regclass IS NULL THEN
                EXECUTE
                    'CREATE VIEW gs_sys.gs_database_versions AS ' ||
                    'SELECT * FROM gs_sys.gs_sys_database_versions';
            END IF;
        END $$;
        """
    )


def downgrade():
    # Удаляем только compatibility VIEW (если это именно VIEW).
    op.execute(
        """
        DO $$
        DECLARE
            rel_kind "char";
        BEGIN
            SELECT c.relkind
              INTO rel_kind
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'gs_sys'
               AND c.relname = 'gs_database_versions';

            IF rel_kind = 'v' THEN
                EXECUTE 'DROP VIEW gs_sys.gs_database_versions';
            END IF;
        END $$;
        """
    )
