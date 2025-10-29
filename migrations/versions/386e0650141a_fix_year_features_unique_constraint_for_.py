"""fix_year_features_unique_constraint_for_versioning

Revision ID: 386e0650141a
Revises: 556bf0fa1b58
Create Date: 2025-10-24 11:59:17.379471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '386e0650141a'
down_revision = '556bf0fa1b58'
branch_labels = None
depends_on = None


def upgrade():
    # Идемпотентные операции: дроп индекса, если существует, и создание нового, если отсутствует
    bind = op.get_bind()
    old_idx_exists = bind.execute(sa.text(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'refdata'
          AND tablename = 'year_features'
          AND indexname = 'ix_refdata_year_features_name'
        """
    )).fetchone() is not None
    if old_idx_exists:
        op.drop_index('ix_refdata_year_features_name', table_name='year_features', schema='refdata')

    new_idx_exists = bind.execute(sa.text(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'refdata'
          AND tablename = 'year_features'
          AND indexname = 'ix_refdata_year_features_name_database_version_id'
        """
    )).fetchone() is not None
    if not new_idx_exists:
        op.create_index('ix_refdata_year_features_name_database_version_id', 'year_features', ['name', 'database_version_id'], unique=True, schema='refdata')


def downgrade():
    bind = op.get_bind()
    new_idx_exists = bind.execute(sa.text(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'refdata'
          AND tablename = 'year_features'
          AND indexname = 'ix_refdata_year_features_name_database_version_id'
        """
    )).fetchone() is not None
    if new_idx_exists:
        op.drop_index('ix_refdata_year_features_name_database_version_id', table_name='year_features', schema='refdata')

    old_idx_exists = bind.execute(sa.text(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'refdata'
          AND tablename = 'year_features'
          AND indexname = 'ix_refdata_year_features_name'
        """
    )).fetchone() is not None
    if not old_idx_exists:
        op.create_index('ix_refdata_year_features_name', 'year_features', ['name'], unique=True, schema='refdata')
