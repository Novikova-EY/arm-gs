# -*- coding: utf-8 -*-
"""gs_pd: префикс gs_pd_ в именах таблиц параметров нагрузки (power demand)

Revision ID: a7b8c9d0e1f2
Revises: c2d3e4f5a6b7
Create Date: 2026-04-24

Переименование таблиц в схеме gs_pd: gs_*_demand_params -> gs_pd_*_demand_params
(модели app/power_demand/models).
"""
import os
import sys

from alembic import op

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "a7b8c9d0e1f2"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"

_RENAMES = [
    ("gs_centralized_zone_demand_params", "gs_pd_centralized_zone_demand_params"),
    ("gs_ees_demand_params", "gs_pd_ees_demand_params"),
    ("gs_ees_russia_demand_params", "gs_pd_ees_russia_demand_params"),
    ("gs_ees_russia_with_nt_demand_params", "gs_pd_ees_russia_with_nt_demand_params"),
    ("gs_energy_area_demand_params", "gs_pd_energy_area_demand_params"),
    ("gs_energy_system_type_demand_params", "gs_pd_energy_system_type_demand_params"),
    ("gs_energy_unit_demand_params", "gs_pd_energy_unit_demand_params"),
    ("gs_energy_zone_demand_params", "gs_pd_energy_zone_demand_params"),
    ("gs_federal_district_demand_params", "gs_pd_federal_district_demand_params"),
    ("gs_regional_district_demand_params", "gs_pd_regional_district_demand_params"),
    ("gs_regional_energy_system_demand_params", "gs_pd_regional_energy_system_demand_params"),
    ("gs_russia_federation_demand_params", "gs_pd_russia_federation_demand_params"),
    ("gs_russia_federation_with_nt_demand_params", "gs_pd_russia_federation_with_nt_demand_params"),
    ("gs_synchronous_area_demand_params", "gs_pd_synchronous_area_demand_params"),
    ("gs_union_energy_system_demand_params", "gs_pd_union_energy_system_demand_params"),
]


def upgrade():
    conn = op.get_bind()
    for old, new in _RENAMES:
        if column_utils.table_exists(conn, SCHEMA_PD, old) and not column_utils.table_exists(conn, SCHEMA_PD, new):
            op.rename_table(old, new, schema=SCHEMA_PD)


def downgrade():
    conn = op.get_bind()
    for old, new in reversed(_RENAMES):
        if column_utils.table_exists(conn, SCHEMA_PD, new) and not column_utils.table_exists(conn, SCHEMA_PD, old):
            op.rename_table(new, old, schema=SCHEMA_PD)
