# -*- coding: utf-8 -*-
"""Дубликаты параметров нагрузки gs_pd: слияние gs_* → gs_pd_* и удаление легаси-таблиц.

Revision ID: z3a4b5c6d7e8
Revises: c8d9e0f1a2b3
Create Date: 2026-05-12

Локально после a7b8c9d0e1f2 остаётся только таблица с префиксом gs_pd_.
На некоторых БД переименование не выполнилось (уже существовала целевая таблица), и
родились параллельно gs_energy_*_demand_params и gs_pd_energy_*_demand_params.
Модели app/power_demand/models смотрят только на gs_pd_*.

Стратегия: для каждой пары выполнить INSERT в gs_pd_* тех строк из gs_*, ключ которых
(сущность + версия БД + режим исторического макс./год) ещё не представлен в gs_pd_*,
затем DROP легаси-таблицы.
"""

import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402


revision = "z3a4b5c6d7e8"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None

SCHEMA_PD = "gs_pd"


# Короткое имя легаси-таблицы без gs_pd_; второй элемент — колонка FK на справочник или None.
_LEGACY_AND_ENTITY_FK: tuple[tuple[str, str | None], ...] = (
    ("gs_centralized_zone_demand_params", None),
    ("gs_ees_demand_params", None),
    ("gs_ees_russia_demand_params", None),
    ("gs_ees_russia_with_nt_demand_params", None),
    ("gs_energy_area_demand_params", "id_energy_area"),
    ("gs_energy_system_type_demand_params", "id_energy_system_type"),
    ("gs_energy_unit_demand_params", "id_energy_unit"),
    ("gs_energy_zone_demand_params", "id_energy_zone"),
    ("gs_federal_district_demand_params", "id_federal_district"),
    ("gs_regional_district_demand_params", "id_regional_district"),
    ("gs_regional_energy_system_demand_params", "id_regional_energy_system"),
    ("gs_russia_federation_demand_params", None),
    ("gs_russia_federation_with_nt_demand_params", None),
    ("gs_synchronous_area_demand_params", "id_synchronous_area"),
    ("gs_union_energy_system_demand_params", "id_union_energy_system"),
)


def _pd_name(legacy: str) -> str:
    """gs_energy_area_demand_params -> gs_pd_energy_area_demand_params."""
    assert legacy.startswith("gs_"), legacy
    return "gs_pd_" + legacy[len("gs_") :]


def _common_columns_except_id(connection, schema: str, legacy: str, pd_table: str) -> list[str]:
    rows = connection.execute(
        text(
            """
            SELECT c1.column_name
            FROM information_schema.columns c1
            INNER JOIN information_schema.columns c2
              ON c1.column_name = c2.column_name
            WHERE c1.table_schema = :schema AND c1.table_name = :t_old
              AND c2.table_schema = :schema AND c2.table_name = :t_new
              AND c1.column_name <> 'id'
            ORDER BY c1.ordinal_position
            """
        ),
        {"schema": schema, "t_old": legacy, "t_new": pd_table},
    ).fetchall()
    return [r[0] for r in rows]


def _merge_old_into_new(
    connection,
    legacy: str,
    pd_table: str,
    entity_fk_col: str | None,
) -> None:
    cols = _common_columns_except_id(connection, SCHEMA_PD, legacy, pd_table)
    if not cols:
        return
    fq = SCHEMA_PD.replace('"', '""')
    leg = legacy.replace('"', '""')
    pn = pd_table.replace('"', '""')
    quoted_cols = ", ".join(f'"{c}"' for c in cols)
    select_exprs = ", ".join(f'o."{c}"' for c in cols)
    fk_sql = ""
    if entity_fk_col:
        fk_sql = f'AND n."{entity_fk_col}" = o."{entity_fk_col}"'
    stmt = text(
        f'''
        INSERT INTO "{fq}"."{pn}" ({quoted_cols})
        SELECT {select_exprs}
        FROM "{fq}"."{leg}" o
        WHERE NOT EXISTS (
            SELECT 1
            FROM "{fq}"."{pn}" n
            WHERE COALESCE(n.database_version_id, 0) = COALESCE(o.database_version_id, 0)
              AND n.is_historical_maximum IS NOT DISTINCT FROM o.is_historical_maximum
              AND (
                    n.is_historical_maximum = true
                    OR n.year_number IS NOT DISTINCT FROM o.year_number
                  )
              {fk_sql}
        )
        '''
    )
    connection.execute(stmt)


def upgrade() -> None:
    conn = op.get_bind()
    for legacy, entity_fk in _LEGACY_AND_ENTITY_FK:
        if not column_utils.table_exists(conn, SCHEMA_PD, legacy):
            continue
        pd_tbl = _pd_name(legacy)
        if column_utils.table_exists(conn, SCHEMA_PD, pd_tbl):
            _merge_old_into_new(conn, legacy, pd_tbl, entity_fk)
            op.drop_table(legacy, schema=SCHEMA_PD)
        else:
            op.rename_table(legacy, pd_tbl, schema=SCHEMA_PD)


def downgrade() -> None:
    """
    Откат не восстанавливает удалённые дубликаты gs_* без полного дампа данных.
    """
    raise NotImplementedError("irreversible: legacy gs_* demand_params tables merged and dropped")

