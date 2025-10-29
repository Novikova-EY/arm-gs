# -*- coding: utf-8 -*-
"""
Fix unique constraints for refdata.regional_districts to be per database_version_id

Revision ID: fix_rd_unique_20251029
Revises: dcb7ade888b9
Create Date: 2025-10-29 08:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_rd_unique_20251029'
down_revision = 'dcb7ade888b9'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Удаляем старые глобальные уникальные ограничения, если существуют
    for constraint_name in [
        'regional_districts_name_key',
        'regional_districts_name_full_key',
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
                    ALTER TABLE refdata.regional_districts
                    DROP CONSTRAINT IF EXISTS """ + constraint_name + """;
                END IF;
            END$$;
            """
        ), {"cname": constraint_name})

    # Создаём композитные уникальные ограничения per-version
    op.create_unique_constraint(
        'uq_refdata_regional_districts_ver_name',
        'regional_districts',
        ['database_version_id', 'name'],
        schema='refdata'
    )
    op.create_unique_constraint(
        'uq_refdata_regional_districts_ver_name_full',
        'regional_districts',
        ['database_version_id', 'name_full'],
        schema='refdata'
    )


def downgrade():
    op.drop_constraint('uq_refdata_regional_districts_ver_name', 'regional_districts', type_='unique', schema='refdata')
    op.drop_constraint('uq_refdata_regional_districts_ver_name_full', 'regional_districts', type_='unique', schema='refdata')

    op.create_unique_constraint('regional_districts_name_key', 'regional_districts', ['name'], schema='refdata')
    op.create_unique_constraint('regional_districts_name_full_key', 'regional_districts', ['name_full'], schema='refdata')


