"""Принадлежность в территориальных срезах коэффициентов ТЭС.

Revision ID: ef26102003
Revises: ef26102002
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY

revision = "ef26102003"
down_revision = "ef26102002"
branch_labels = None
depends_on = None

_TABLE = "gs_eco_operating_tes_coefficients"


def upgrade():
    op.add_column(_TABLE, sa.Column(
        "affiliation", sa.String(20), nullable=False, server_default="all"
    ), schema=SCHEMA_ECOLOGY)
    op.drop_constraint("uq_eco_ot_coeff_terr_year_kind_ver", _TABLE, schema=SCHEMA_ECOLOGY, type_="unique")
    op.create_unique_constraint(
        "uq_eco_ot_coeff_slice_year_kind_ver", _TABLE,
        ["territory_slug", "affiliation", "year_number", "kind", "database_version_id"],
        schema=SCHEMA_ECOLOGY,
    )
    table = sa.Table(_TABLE, sa.MetaData(), schema=SCHEMA_ECOLOGY, autoload_with=op.get_bind())
    columns = [column for column in table.c if column.name not in {"id", "affiliation"}]
    # Общие срезы принадлежности уже представлены строками minen/prompred.
    for affiliation in ("minen", "prompred"):
        op.get_bind().execute(table.insert().from_select(
            ["affiliation", *[column.name for column in columns]],
            sa.select(sa.literal(affiliation), *columns).where(
                table.c.affiliation == "all",
                table.c.territory_slug.not_in(["vsego", "minen", "prompred"]),
            ),
        ))


def downgrade():
    table = sa.table(_TABLE, sa.column("affiliation"), schema=SCHEMA_ECOLOGY)
    op.get_bind().execute(table.delete().where(table.c.affiliation != "all"))
    op.drop_constraint("uq_eco_ot_coeff_slice_year_kind_ver", _TABLE, schema=SCHEMA_ECOLOGY, type_="unique")
    op.drop_column(_TABLE, "affiliation", schema=SCHEMA_ECOLOGY)
    op.create_unique_constraint(
        "uq_eco_ot_coeff_terr_year_kind_ver", _TABLE,
        ["territory_slug", "year_number", "kind", "database_version_id"], schema=SCHEMA_ECOLOGY,
    )
