"""Add territory and affiliation slices to operating TES fuel characteristics."""
from alembic import op
import sqlalchemy as sa

from config import SCHEMA_ECOLOGY

revision = "gs26110601"
down_revision = "gs26110301"
branch_labels = None
depends_on = None

_TABLE = "gs_eco_operating_tes_fuel_chars"
_TERRITORIES = (
    "vsego", "severo-zapad", "centr", "srednyaya-volga", "yug", "ural",
    "sibir", "vostok", "tites-sibir", "tites-vostok", "decentralized-zone",
)
_AFFILIATIONS = ("all", "minen", "prompred")
_FIELDS = (
    "ash", "ash_share", "q_mech", "sulfur", "sulfur_share", "qh_kj", "qh_kcal",
    "bj", "k_co2", "r_chem", "q_chem", "tut_per_t", "tj_per_kt", "t_co2_per_tj",
)


def _insert_select(select_sql):
    fields = ", ".join(f'"{field}"' for field in _FIELDS)
    op.get_bind().execute(sa.text(
        f'INSERT INTO "{SCHEMA_ECOLOGY}"."{_TABLE}" '
        f'("territory_slug", "affiliation", "fuel_key", "year_number", {fields}, '
        '"note", "source_key", "database_version_id") '
        f'{select_sql} ON CONFLICT DO NOTHING'
    ))


def upgrade():
    op.add_column(
        _TABLE,
        sa.Column("affiliation", sa.String(length=20), server_default="all", nullable=False),
        schema=SCHEMA_ECOLOGY,
    )
    op.drop_constraint(
        "uq_eco_ot_fuel_char_slice_key_year_ver", _TABLE, schema=SCHEMA_ECOLOGY,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_eco_ot_fuel_char_slice_key_year_ver",
        _TABLE,
        ["territory_slug", "affiliation", "fuel_key", "year_number", "database_version_id"],
        schema=SCHEMA_ECOLOGY,
    )
    op.create_index(
        f"ix_{_TABLE}_affiliation", _TABLE, ["affiliation"], schema=SCHEMA_ECOLOGY
    )

    table = f'"{SCHEMA_ECOLOGY}"."{_TABLE}"'
    affiliation_values = ", ".join(f"('{value}')" for value in _AFFILIATIONS)
    source_fields = ", ".join(f'source."{field}"' for field in _FIELDS)
    _insert_select(
        f'SELECT source."territory_slug", affiliation.value, source."fuel_key", '
        f'source."year_number", {source_fields}, source."note", source."source_key", '
        f'source."database_version_id" FROM {table} AS source '
        f'CROSS JOIN (VALUES {affiliation_values}) AS affiliation(value) '
        'WHERE source."affiliation" = \'all\''
    )

    territory_values = ", ".join(f"('{value}')" for value in _TERRITORIES)
    _insert_select(
        f'SELECT territory.value, affiliation.value, source."fuel_key", '
        f'source."year_number", {source_fields}, source."note", source."source_key", '
        f'source."database_version_id" FROM {table} AS source '
        f'CROSS JOIN (VALUES {territory_values}) AS territory(value) '
        f'CROSS JOIN (VALUES {affiliation_values}) AS affiliation(value) '
        'WHERE source."territory_slug" = \'vsego\' AND source."affiliation" = \'all\''
    )


def downgrade():
    connection = op.get_bind()
    table = f'"{SCHEMA_ECOLOGY}"."{_TABLE}"'
    comparisons = " OR ".join(
        f'sliced."{field}" IS DISTINCT FROM generic."{field}"'
        for field in (*_FIELDS, "note", "source_key")
    )
    incompatible = connection.execute(sa.text(
        f'SELECT 1 FROM {table} AS sliced '
        f'LEFT JOIN {table} AS generic ON generic."territory_slug" = sliced."territory_slug" '
        'AND generic."affiliation" = \'all\' AND generic."fuel_key" = sliced."fuel_key" '
        'AND generic."year_number" = sliced."year_number" '
        'AND generic."database_version_id" IS NOT DISTINCT FROM sliced."database_version_id" '
        f'WHERE sliced."affiliation" != \'all\' AND '
        f'(generic."id" IS NULL OR {comparisons}) LIMIT 1'
    )).first()
    if incompatible is not None:
        raise ValueError(
            "Cannot remove affiliation-specific characteristic values without losing data."
        )
    connection.execute(sa.text(
        f'DELETE FROM {table} WHERE "affiliation" != \'all\''
    ))
    op.drop_index(f"ix_{_TABLE}_affiliation", table_name=_TABLE, schema=SCHEMA_ECOLOGY)
    op.drop_constraint(
        "uq_eco_ot_fuel_char_slice_key_year_ver", _TABLE, schema=SCHEMA_ECOLOGY,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_eco_ot_fuel_char_slice_key_year_ver",
        _TABLE,
        ["territory_slug", "fuel_key", "year_number", "database_version_id"],
        schema=SCHEMA_ECOLOGY,
    )
    op.drop_column(_TABLE, "affiliation", schema=SCHEMA_ECOLOGY)
