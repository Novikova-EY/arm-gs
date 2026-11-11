"""Add an explicit exclusion marker to electrical-intensity year rows."""

from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ELECTRICAL_INTENSITY

revision = "gs26110602"
down_revision = "gs26110601"
branch_labels = None
depends_on = None

_TABLES = (
    "gs_ei_federal_district_electrical_intensity_year_params",
    "gs_ei_russia_federation_electrical_intensity_year_params",
)
_COLUMN = "is_excluded_from_calculation"


def upgrade():
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                _COLUMN,
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            ),
            schema=SCHEMA_ELECTRICAL_INTENSITY,
        )


def downgrade():
    for table in reversed(_TABLES):
        op.drop_column(table, _COLUMN, schema=SCHEMA_ELECTRICAL_INTENSITY)
