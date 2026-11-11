"""Durable history for the shared data refresh control."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_LOGS

revision = "gs26110301"
down_revision = "gs26110202"
branch_labels = None
depends_on = None


def upgrade():
    state = op.create_table(
        "gs_data_refresh_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("epoch", sa.String(36), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        schema=SCHEMA_LOGS,
    )
    op.bulk_insert(state, [{"id": 1, "epoch": str(uuid4()), "revision": 0}])
    op.create_table(
        "gs_data_refresh_events",
        sa.Column("revision", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("operation_id", sa.String(36), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("scope_known", sa.Boolean(), nullable=False),
        sa.Column("consumption", sa.Boolean(), nullable=False),
        sa.Column("demand", sa.Boolean(), nullable=False),
        sa.Column("balance", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        schema=SCHEMA_LOGS,
    )
    op.create_index("ix_refresh_event_version_revision", "gs_data_refresh_events", ["database_version_id", "revision"], schema=SCHEMA_LOGS)
    op.create_index("ix_refresh_event_operation", "gs_data_refresh_events", ["operation_id"], schema=SCHEMA_LOGS)


def downgrade():
    op.drop_table("gs_data_refresh_events", schema=SCHEMA_LOGS)
    op.drop_table("gs_data_refresh_state", schema=SCHEMA_LOGS)
