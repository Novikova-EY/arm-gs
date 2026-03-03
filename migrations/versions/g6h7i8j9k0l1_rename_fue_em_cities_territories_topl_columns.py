"""rename _topl columns in gs_fue_em_cities and gs_fue_em_territories_energy

Revision ID: g6h7i8j9k0l1
Revises: f5a6b7c8d9e0
Create Date: 2026-02-27

Переименовывает code_topl->code, name_topl->name в gs_fue_em_cities.
Переименовывает *_topl в gs_fue_em_territories_energy.
Идемпотентно: выполняется только если старые колонки ещё есть.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUE_EM


revision = "g6h7i8j9k0l1"
down_revision = "f5a6b7c8d9e0"
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


def _column_exists(conn, table, col):
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(table, schema=SCHEMA)]
    return col in cols


def upgrade():
    conn = op.get_bind()
    # gs_fue_em_cities
    if _column_exists(conn, "gs_fue_em_cities", "code_topl"):
        for old_name, new_name in CITIES_RENAMES:
            if _column_exists(conn, "gs_fue_em_cities", old_name):
                op.alter_column(
                    "gs_fue_em_cities",
                    old_name,
                    new_column_name=new_name,
                    schema=SCHEMA,
                )
    # gs_fue_em_territories_energy
    if _column_exists(conn, "gs_fue_em_territories_energy", "name_topl"):
        for old_name, new_name in TERRITORIES_RENAMES:
            if _column_exists(conn, "gs_fue_em_territories_energy", old_name):
                op.alter_column(
                    "gs_fue_em_territories_energy",
                    old_name,
                    new_column_name=new_name,
                    schema=SCHEMA,
                )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "gs_fue_em_cities", "code"):
        for old_name, new_name in CITIES_RENAMES:
            if _column_exists(conn, "gs_fue_em_cities", new_name):
                op.alter_column(
                    "gs_fue_em_cities",
                    new_name,
                    new_column_name=old_name,
                    schema=SCHEMA,
                )
    if _column_exists(conn, "gs_fue_em_territories_energy", "name_ext"):
        for old_name, new_name in TERRITORIES_RENAMES:
            if _column_exists(conn, "gs_fue_em_territories_energy", new_name):
                op.alter_column(
                    "gs_fue_em_territories_energy",
                    new_name,
                    new_column_name=old_name,
                    schema=SCHEMA,
                )
