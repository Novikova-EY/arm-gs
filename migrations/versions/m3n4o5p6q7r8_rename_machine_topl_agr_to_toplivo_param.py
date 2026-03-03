"""rename machine_topl_agr to machine_toplivo_param

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-02-21 12:00:00.000000

Переименовывает таблицу gs_fue_machine_topl_agr в gs_fue_machine_toplivo_param,
модель MachineToplAgr -> MachineToplivoParam.
"""

from alembic import op
from config import SCHEMA_FUEL


# revision identifiers, used by Alembic.
revision = "m3n4o5p6q7r8"
down_revision = "l2m3n4o5p6q7"
branch_labels = None
depends_on = None

OLD_TABLE = "gs_fue_machine_topl_agr"
NEW_TABLE = "gs_fue_machine_toplivo_param"
OLD_CONSTRAINT = "uq_machine_topl_agr_machine_id"
NEW_CONSTRAINT = "uq_machine_toplivo_param_machine_id"
OLD_INDEX = "ix_gs_fue_machine_topl_agr_database_version_id"
NEW_INDEX = "ix_gs_fue_machine_toplivo_param_database_version_id"


def upgrade():
    # 1. Rename table
    op.rename_table(
        OLD_TABLE,
        NEW_TABLE,
        schema=SCHEMA_FUEL,
    )
    # 2. Rename unique constraint
    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.{NEW_TABLE} '
        f'RENAME CONSTRAINT {OLD_CONSTRAINT} TO {NEW_CONSTRAINT}'
    )
    # 3. Rename index
    op.execute(
        f'ALTER INDEX {SCHEMA_FUEL}.{OLD_INDEX} RENAME TO {NEW_INDEX}'
    )


def downgrade():
    # 1. Rename index back
    op.execute(
        f'ALTER INDEX {SCHEMA_FUEL}.{NEW_INDEX} RENAME TO {OLD_INDEX}'
    )
    # 2. Rename constraint back
    op.execute(
        f'ALTER TABLE {SCHEMA_FUEL}.{NEW_TABLE} '
        f'RENAME CONSTRAINT {NEW_CONSTRAINT} TO {OLD_CONSTRAINT}'
    )
    # 3. Rename table back
    op.rename_table(
        NEW_TABLE,
        OLD_TABLE,
        schema=SCHEMA_FUEL,
    )
