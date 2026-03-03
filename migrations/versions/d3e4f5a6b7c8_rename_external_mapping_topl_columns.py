"""rename _topl columns in Cities and TerritoriesEnergy external mapping

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-26

Переименовывает в gs_fue_em_cities: code_topl->code, name_topl->name.
Переименовывает в gs_fue_em_territories_energy: *_topl -> короткие имена.
"""

from alembic import op
from config import SCHEMA_FUE_EM


revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

SCHEMA = SCHEMA_FUE_EM

CITIES_RENAMES = [("code_topl", "code"), ("name_topl", "name")]

TERRITORIES_RENAMES = [
    ("name_topl", "name_ext"),
    ("ao_topl", "ao"),
    ("obl_topl", "obl"),
    ("alph_topl", "alph"),
    ("dep_topl", "dep"),
    ("oes_topl", "oes"),
    ("er_topl", "er"),
    ("terr_belyaev_topl", "terr_belyaev"),
    ("teo90_topl", "teo90"),
    ("fo_topl", "fo"),
    ("abbr_topl", "abbr"),
    ("reu_topl", "reu"),
    ("pter_topl", "pter"),
    ("keyword_topl", "keyword"),
]


def upgrade():
    for old_name, new_name in CITIES_RENAMES:
        op.alter_column(
            "gs_fue_em_cities",
            old_name,
            new_column_name=new_name,
            schema=SCHEMA,
        )
    for old_name, new_name in TERRITORIES_RENAMES:
        op.alter_column(
            "gs_fue_em_territories_energy",
            old_name,
            new_column_name=new_name,
            schema=SCHEMA,
        )


def downgrade():
    for old_name, new_name in CITIES_RENAMES:
        op.alter_column(
            "gs_fue_em_cities",
            new_name,
            new_column_name=old_name,
            schema=SCHEMA,
        )
    for old_name, new_name in TERRITORIES_RENAMES:
        op.alter_column(
            "gs_fue_em_territories_energy",
            new_name,
            new_column_name=old_name,
            schema=SCHEMA,
        )
