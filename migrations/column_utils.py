# -*- coding: utf-8 -*-
"""Утилиты для idempotent-миграций (PostgreSQL)."""
from sqlalchemy import text
from sqlalchemy.engine import Connection


def table_exists(conn: Connection, schema: str, table: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.tables
            where table_schema = :schema and table_name = :table
            """
        ),
        {"schema": schema, "table": table},
    ).fetchone()
    return row is not None


def incoming_foreign_key_count(conn: Connection, schema: str, table: str) -> int:
    """Число FK в других таблицах, ссылающихся на эту (confrelid)."""
    row = conn.execute(
        text(
            """
            select count(*)::int
            from pg_constraint c
            inner join pg_class cl on cl.oid = c.confrelid
            inner join pg_namespace n on n.oid = cl.relnamespace
            where c.contype = 'f'
              and n.nspname = :schema
              and cl.relname = :table
            """
        ),
        {"schema": schema, "table": table},
    ).scalar()
    return int(row or 0)


def refdata_table_name(conn: Connection, schema: str, table: str) -> str | None:
    """Имя справочника в gs_sys до/после b8c9d0e1f2a3.

    Пример: gs_regional_districts -> gs_sys_regional_districts.
    """
    if table_exists(conn, schema, table):
        return table
    if table.startswith("gs_"):
        renamed = "gs_sys_" + table[3:]
        if table_exists(conn, schema, renamed):
            return renamed
    return None


def table_has_column(conn: Connection, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def column_is_nullable(conn: Connection, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            select is_nullable
            from information_schema.columns
            where table_schema = :schema
              and table_name = :table
              and column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    if row is None:
        return False
    return (row[0] or "").upper() == "YES"


def database_versions_physical_table_name(conn: Connection, schema: str = "gs_sys") -> str | None:
    """Таблица версий БД для FK.

    После e0f1a2b3c4d5 базовая таблица — gs_sys_database_versions.
    Совместимый объект gs_database_versions из y2z3a4b5c6d7 может быть VIEW;
    CREATE TABLE … REFERENCES … недопустим к VIEW в PostgreSQL.
    """
    row = conn.execute(
        text(
            """
            select table_name
            from information_schema.tables
            where table_schema = :schema
              and table_type = 'BASE TABLE'
              and table_name in ('gs_sys_database_versions', 'gs_database_versions')
            order by case table_name when 'gs_sys_database_versions' then 0 else 1 end
            limit 1
            """
        ),
        {"schema": schema},
    ).fetchone()
    return row[0] if row else None


def station_prospective_place_aes_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_station_prospective_place_aes, до — station_prospective_place_aes."""
    if table_exists(conn, schema, "gs_gen_station_prospective_place_aes"):
        return "gs_gen_station_prospective_place_aes"
    if table_exists(conn, schema, "station_prospective_place_aes"):
        return "station_prospective_place_aes"
    return None


def machine_prospective_place_aes_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_machine_prospective_place_aes, до — machine_prospective_place_aes."""
    if table_exists(conn, schema, "gs_gen_machine_prospective_place_aes"):
        return "gs_gen_machine_prospective_place_aes"
    if table_exists(conn, schema, "machine_prospective_place_aes"):
        return "machine_prospective_place_aes"
    return None


def prospective_place_types_aes_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_gs_prospective_place_types, до — gs_prospective_place_types."""
    if table_exists(conn, schema, "gs_gen_gs_prospective_place_types"):
        return "gs_gen_gs_prospective_place_types"
    if table_exists(conn, schema, "gs_prospective_place_types"):
        return "gs_prospective_place_types"
    return None


def prospective_place_types_ges_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_gs_prospective_place_types_ges, до — gs_prospective_place_types_ges."""
    if table_exists(conn, schema, "gs_gen_gs_prospective_place_types_ges"):
        return "gs_gen_gs_prospective_place_types_ges"
    if table_exists(conn, schema, "gs_prospective_place_types_ges"):
        return "gs_prospective_place_types_ges"
    return None


def station_prospective_place_ges_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_station_prospective_place_ges, до — station_prospective_place_ges."""
    if table_exists(conn, schema, "gs_gen_station_prospective_place_ges"):
        return "gs_gen_station_prospective_place_ges"
    if table_exists(conn, schema, "station_prospective_place_ges"):
        return "station_prospective_place_ges"
    return None


def ges_tep_source_project_indicators_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_ges_tep_source_project_indicators, до — ges_tep_source_project_indicators."""
    if table_exists(conn, schema, "gs_gen_ges_tep_source_project_indicators"):
        return "gs_gen_ges_tep_source_project_indicators"
    if table_exists(conn, schema, "ges_tep_source_project_indicators"):
        return "ges_tep_source_project_indicators"
    return None


def prospective_place_types_gaes_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_gs_prospective_place_types_gaes, до — gs_prospective_place_types_gaes."""
    if table_exists(conn, schema, "gs_gen_gs_prospective_place_types_gaes"):
        return "gs_gen_gs_prospective_place_types_gaes"
    if table_exists(conn, schema, "gs_prospective_place_types_gaes"):
        return "gs_prospective_place_types_gaes"
    return None


def station_prospective_place_gaes_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_station_prospective_place_gaes, до — station_prospective_place_gaes."""
    if table_exists(conn, schema, "gs_gen_station_prospective_place_gaes"):
        return "gs_gen_station_prospective_place_gaes"
    if table_exists(conn, schema, "station_prospective_place_gaes"):
        return "station_prospective_place_gaes"
    return None


def gaes_tep_source_project_indicators_table_name(conn: Connection, schema: str) -> str | None:
    """После c2d3e4f5a6b7 — gs_gen_gaes_tep_source_project_indicators, до — gaes_tep_source_project_indicators."""
    if table_exists(conn, schema, "gs_gen_gaes_tep_source_project_indicators"):
        return "gs_gen_gaes_tep_source_project_indicators"
    if table_exists(conn, schema, "gaes_tep_source_project_indicators"):
        return "gaes_tep_source_project_indicators"
    return None


def gs_gen_stations_table_name(conn: Connection, schema: str) -> str | None:
    """После b1c2d3e4f5a6 — gs_gen_stations, до — stations."""
    if table_exists(conn, schema, "gs_gen_stations"):
        return "gs_gen_stations"
    if table_exists(conn, schema, "stations"):
        return "stations"
    return None


def pgu_machine_names_table_name(conn: Connection, schema: str) -> str | None:
    """После b1c2d3e4f5a6 — gs_gen_pgu_machine_names, до переименования — pgu_machine_names."""
    if table_exists(conn, schema, "gs_gen_pgu_machine_names"):
        return "gs_gen_pgu_machine_names"
    if table_exists(conn, schema, "pgu_machine_names"):
        return "pgu_machine_names"
    return None


def gs_pd_demand_params_physical_table_name(
    conn: Connection,
    schema: str,
    legacy_gs_table: str,
) -> str | None:
    """Фактическое имя таблицы *_demand_params в gs_pd до/после a7b8c9d0e1f2.

    До переименования: gs_energy_area_demand_params; после: gs_pd_energy_area_demand_params.
    Имена индексов часто остаются с прежним корнем (до rename), а относятся к уже
    переименованной таблице — нельзя создавать вторую таблицу со старым именем.

    Если таблицы нет, возвращает None.
    """
    if legacy_gs_table.startswith("gs_pd_"):
        if table_exists(conn, schema, legacy_gs_table):
            return legacy_gs_table
        stripped = legacy_gs_table[len("gs_pd_") :]
        legacy_alt = "gs_" + stripped
        if table_exists(conn, schema, legacy_alt):
            return legacy_alt
        return None
    if legacy_gs_table.startswith("gs_"):
        pd_name = "gs_pd_" + legacy_gs_table[len("gs_") :]
        if table_exists(conn, schema, pd_name):
            return pd_name
        if table_exists(conn, schema, legacy_gs_table):
            return legacy_gs_table
        return None
    return None


def machines_table_name(conn: Connection, schema: str) -> str | None:
    """После b1c2d3e4f5a6 — gs_gen_machines, до — machines."""
    if table_exists(conn, schema, "gs_gen_machines"):
        return "gs_gen_machines"
    if table_exists(conn, schema, "machines"):
        return "machines"
    return None


def pgu_machines_table_name(conn: Connection, schema: str) -> str | None:
    """Имя таблицы ПГУ: после b1c2d3e4f5a6 это gs_gen_pgu_machines, до — pgu_machines."""
    if table_exists(conn, schema, "gs_gen_pgu_machines"):
        return "gs_gen_pgu_machines"
    if table_exists(conn, schema, "pgu_machines"):
        return "pgu_machines"
    return None


def index_exists(conn: Connection, schema: str, index_name: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from pg_indexes
            where schemaname = :schema and indexname = :index_name
            """
        ),
        {"schema": schema, "index_name": index_name},
    ).fetchone()
    return row is not None


def constraint_exists(conn: Connection, schema: str, constraint_name: str) -> bool:
    row = conn.execute(
        text(
            """
            select 1
            from pg_constraint c
            join pg_namespace n on n.oid = c.connamespace
            where n.nspname = :schema and c.conname = :constraint_name
            """
        ),
        {"schema": schema, "constraint_name": constraint_name},
    ).fetchone()
    return row is not None
