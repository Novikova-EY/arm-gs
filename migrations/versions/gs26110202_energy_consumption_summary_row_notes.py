"""Store independent notes for manual and calculated consumption rows."""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ENERGY_CONSUMPTION

revision = "gs26110202"
down_revision = "gs26110201"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy installations can deploy this additive table before rebasing migration history.
    if sa.inspect(op.get_bind()).has_table("gs_ec_summary_row_notes", schema=SCHEMA_ENERGY_CONSUMPTION):
        return
    op.create_table(
        "gs_ec_summary_row_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("database_version_id", sa.Integer(), nullable=False),
        sa.Column("row_key", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(255)),
        sa.Column("modified_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("database_version_id", "row_key", name="uq_ec_summary_row_note_version_key"),
        schema=SCHEMA_ENERGY_CONSUMPTION,
    )


def downgrade():
    op.drop_table("gs_ec_summary_row_notes", schema=SCHEMA_ENERGY_CONSUMPTION)
