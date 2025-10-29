# -*- coding: utf-8 -*-
"""
Fix unique constraints for refdata.federal_districts to be per database_version_id

Revision ID: fix_fd_unique_20251029
Revises: g1d4b3c6e8f9
Create Date: 2025-10-29 08:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_fd_unique_20251029'
down_revision = 'g1d4b3c6e8f9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Удаляем старые глобальные уникальные ограничения, если существуют
    # Имя по умолчанию у PostgreSQL: <table>_<column>_key в схеме refdata
    for constraint_name in [
        'federal_districts_name_key',
        'federal_districts_name_full_key',
        'federal_districts_name_abr_key',
    ]:
        conn.execute(sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE c.conname = :cname AND n.nspname = 'refdata'
                ) THEN
                    ALTER TABLE refdata.federal_districts
                    DROP CONSTRAINT IF EXISTS """ + constraint_name + """;
                END IF;
            END$$;
            """
        ), {"cname": constraint_name})

    # Создаем композитные уникальные ограничения per-version
    op.create_unique_constraint(
        'uq_refdata_federal_districts_ver_name',
        'federal_districts',
        ['database_version_id', 'name'],
        schema='refdata'
    )
    op.create_unique_constraint(
        'uq_refdata_federal_districts_ver_name_full',
        'federal_districts',
        ['database_version_id', 'name_full'],
        schema='refdata'
    )
    op.create_unique_constraint(
        'uq_refdata_federal_districts_ver_name_abr',
        'federal_districts',
        ['database_version_id', 'name_abr'],
        schema='refdata'
    )


def downgrade():
    # Откат: удаляем новые композитные ограничения
    op.drop_constraint('uq_refdata_federal_districts_ver_name', 'federal_districts', type_='unique', schema='refdata')
    op.drop_constraint('uq_refdata_federal_districts_ver_name_full', 'federal_districts', type_='unique', schema='refdata')
    op.drop_constraint('uq_refdata_federal_districts_ver_name_abr', 'federal_districts', type_='unique', schema='refdata')

    # Восстанавливаем старые глобальные уникальные ограничения (не рекомендуется)
    op.create_unique_constraint('federal_districts_name_key', 'federal_districts', ['name'], schema='refdata')
    op.create_unique_constraint('federal_districts_name_full_key', 'federal_districts', ['name_full'], schema='refdata')
    op.create_unique_constraint('federal_districts_name_abr_key', 'federal_districts', ['name_abr'], schema='refdata')


