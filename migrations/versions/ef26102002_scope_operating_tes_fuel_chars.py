"""Независимые характеристики топлива по срезам расчёта действующих ТЭС.

Revision ID: ef26102002
Revises: ef26102001
"""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY

revision = "ef26102002"
down_revision = "ef26102001"
branch_labels = None
depends_on = None

_TABLE = "gs_eco_operating_tes_fuel_chars"
_OLD_UNIQUE = "uq_eco_ot_fuel_char_key_year_ver"
_NEW_UNIQUE = "uq_eco_ot_fuel_char_slice_key_year_ver"
_INDEX = "ix_gs_eco_gs_eco_operating_tes_fuel_chars_territory_slug"
# Фиксируем набор срезов на момент миграции, независимо от будущих изменений UI.
_SLICES = (
    "minen", "prompred", "severo-zapad", "centr", "srednyaya-volga", "yug",
    "ural", "sibir", "vostok", "isolated-dv", "nikolaevsky", "norilsk",
)


def upgrade():
    op.add_column(
        _TABLE,
        sa.Column("territory_slug", sa.String(40), nullable=False, server_default="vsego"),
        schema=SCHEMA_ECOLOGY,
    )
    op.drop_constraint(_OLD_UNIQUE, _TABLE, schema=SCHEMA_ECOLOGY, type_="unique")
    op.create_unique_constraint(
        _NEW_UNIQUE, _TABLE,
        ["territory_slug", "fuel_key", "year_number", "database_version_id"],
        schema=SCHEMA_ECOLOGY,
    )
    op.create_index(_INDEX, _TABLE, ["territory_slug"], schema=SCHEMA_ECOLOGY)
    table = sa.Table(_TABLE, sa.MetaData(), schema=SCHEMA_ECOLOGY, autoload_with=op.get_bind())
    columns = [column for column in table.c if column.name not in {"id", "territory_slug"}]
    for slug in _SLICES:
        op.get_bind().execute(table.insert().from_select(
            ["territory_slug", *[column.name for column in columns]],
            sa.select(sa.literal(slug), *columns).where(table.c.territory_slug == "vsego"),
        ))


def downgrade():
    table = sa.table(_TABLE, sa.column("territory_slug"), schema=SCHEMA_ECOLOGY)
    op.get_bind().execute(table.delete().where(table.c.territory_slug != "vsego"))
    op.drop_index(_INDEX, table_name=_TABLE, schema=SCHEMA_ECOLOGY)
    op.drop_constraint(_NEW_UNIQUE, _TABLE, schema=SCHEMA_ECOLOGY, type_="unique")
    op.drop_column(_TABLE, "territory_slug", schema=SCHEMA_ECOLOGY)
    op.create_unique_constraint(
        _OLD_UNIQUE, _TABLE, ["fuel_key", "year_number", "database_version_id"],
        schema=SCHEMA_ECOLOGY,
    )
