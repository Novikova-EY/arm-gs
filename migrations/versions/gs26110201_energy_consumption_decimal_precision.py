"""Preserve Excel decimal precision in energy consumption values."""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ENERGY_CONSUMPTION

revision = "gs26110201"
down_revision = "gs26102901"
branch_labels = None
depends_on = None

_TABLES = (
    "gs_ec_centralized_zone_consumption_params",
    "gs_ec_ees_consumption_params",
    "gs_ec_ees_russia_consumption_params",
    "gs_ec_energy_area_consumption_params",
    "gs_ec_energy_system_type_consumption_params",
    "gs_ec_energy_unit_consumption_params",
    "gs_ec_energy_zone_consumption_params",
    "gs_ec_regional_energy_system_consumption_params",
    "gs_ec_synchronous_area_consumption_params",
    "gs_ec_union_energy_system_consumption_params",
    "gs_ec_federal_district_consumption_params",
    "gs_ec_regional_district_consumption_params",
    "gs_ec_russia_federation_consumption_params",
)
_COLUMNS = ("energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch")


def upgrade():
    for table in _TABLES:
        for column in _COLUMNS:
            op.alter_column(
                table, column, schema=SCHEMA_ENERGY_CONSUMPTION,
                existing_type=sa.Numeric(25, 16), type_=sa.Numeric(), existing_nullable=True,
            )


def downgrade():
    # A downgrade must not silently round values imported with the new precision.
    connection = op.get_bind()
    for table in _TABLES:
        for column in _COLUMNS:
            incompatible = connection.execute(sa.text(
                f'SELECT 1 FROM "{SCHEMA_ENERGY_CONSUMPTION}"."{table}" '
                f'WHERE "{column}" != round("{column}", 16) '
                f'OR abs("{column}") >= 1000000000 LIMIT 1'
            )).first()
            if incompatible is not None:
                raise ValueError("Нельзя уменьшить точность: значения потребления не помещаются в NUMERIC(25, 16).")
    for table in _TABLES:
        for column in _COLUMNS:
            op.alter_column(
                table, column, schema=SCHEMA_ENERGY_CONSUMPTION,
                existing_type=sa.Numeric(), type_=sa.Numeric(25, 16), existing_nullable=True,
            )
