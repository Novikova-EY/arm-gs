# -*- coding: utf-8 -*-
"""Копирование и удаление версионных данных всех модулей.

Ядро generation/refdata по-прежнему копируется поэтапно в
``database_version_services._copy_version_data_staged``. Этот модуль:

- копирует остальные таблицы с ``database_version_id`` (топливо, экология,
  спрос, потребление, баланс, экономика, электроёмкость, территории,
  перспективные площадки и т.д.) с перепривязкой FK на новые id;
- копирует «спутниковые» таблицы без ``database_version_id``, которые
  ссылаются на версионные строки (например ``gs_fue_equipment_group_sets``);
- при удалении версии чистит все такие таблицы, а не только generation/refdata.
"""
from __future__ import annotations

import re
from collections import defaultdict, deque

from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from config import (
    SCHEMA_ECOLOGY,
    SCHEMA_ECONOMICS,
    SCHEMA_ELECTRICAL_INTENSITY,
    SCHEMA_ENERGY_BALANCE,
    SCHEMA_ENERGY_CONSUMPTION,
    SCHEMA_FUEL,
    SCHEMA_FUE_EM,
    SCHEMA_GENERATION,
    SCHEMA_POWER_DEMAND,
    SCHEMA_REFDATA,
    SCHEMA_TERRITORIES,
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

VERSION_REGISTRY_TABLES = frozenset(
    {
        "gs_database_versions",
        "gs_sys_database_versions",
    }
)

_IDENT_BATCH = 1000


def versioned_data_schemas() -> tuple[str, ...]:
    """Схемы прикладных данных (без auth/logs)."""
    return (
        SCHEMA_REFDATA,
        SCHEMA_GENERATION,
        SCHEMA_FUEL,
        SCHEMA_FUE_EM,
        SCHEMA_POWER_DEMAND,
        SCHEMA_ENERGY_CONSUMPTION,
        SCHEMA_ENERGY_BALANCE,
        SCHEMA_ECONOMICS,
        SCHEMA_ELECTRICAL_INTENSITY,
        SCHEMA_TERRITORIES,
        SCHEMA_ECOLOGY,
    )


def year_copy_tables() -> set[tuple[str, str]]:
    return {
        (SCHEMA_REFDATA, "gs_sys_years"),
        (SCHEMA_REFDATA, "gs_sys_year_features"),
        (SCHEMA_REFDATA, "gs_sys_year_service"),
    }


def history_snapshot_tables() -> set[tuple[str, str]]:
    return {
        (SCHEMA_REFDATA, "gs_sys_refdata_entities"),
        (SCHEMA_REFDATA, "gs_sys_refdata_entity_years"),
    }


def shared_not_per_version_tables() -> set[tuple[str, str]]:
    """Справочники, общие для всех версий: копировать/удалять вместе с версией нельзя."""
    return {
        (SCHEMA_REFDATA, "gs_sys_perimeter_variants"),
        (SCHEMA_REFDATA, "gs_sys_entity_perimeter_bindings"),
    }


def core_staged_copy_tables() -> set[tuple[str, str]]:
    """Таблицы, которые уже копирует ``_copy_version_data_staged``."""
    ref = SCHEMA_REFDATA
    gen = SCHEMA_GENERATION
    return {
        (ref, "gs_sys_station_types"),
        (ref, "gs_sys_machine_types"),
        (ref, "gs_sys_tes_types"),
        (ref, "gs_sys_tes_machine_types"),
        (ref, "gs_sys_pgu_tes_machine_types"),
        (ref, "gs_sys_condition_types"),
        (ref, "gs_sys_technology_types"),
        (ref, "gs_sys_electricity_production_cost_types"),
        (ref, "gs_sys_economic_activity_types"),
        (ref, "gs_sys_technology_availabilities"),
        (ref, "gs_sys_energy_system_types"),
        (ref, "gs_sys_fuel_types"),
        (ref, "gs_sys_fuels"),
        (ref, "gs_sys_companies"),
        (ref, "gs_sys_equipment_groups"),
        (ref, "gs_sys_union_energy_systems"),
        (ref, "gs_sys_synchronous_areas"),
        (ref, "gs_sys_energy_zones"),
        (ref, "gs_sys_federal_districts"),
        (ref, "gs_sys_regional_districts"),
        (ref, "gs_sys_regional_energy_systems"),
        (ref, "gs_sys_energy_areas"),
        (ref, "gs_sys_energy_units"),
        (ref, "gs_sys_regional_district_regional_energy_system"),
        (gen, "gs_gen_station_groups"),
        (gen, "gs_gen_documents_kommod"),
        (gen, "gs_gen_stations"),
        (gen, "gs_gen_machines"),
        (gen, "gs_gen_boilers"),
        (gen, "gs_gen_machine_powers"),
        (gen, "gs_gen_machine_fuels"),
        (gen, "gs_gen_machine_tes_types"),
        (gen, "gs_gen_machine_names"),
        (gen, "gs_gen_pgu_machines"),
        (gen, "gs_gen_pgu_machine_powers"),
    }


def copy_skip_tables() -> set[tuple[str, str]]:
    return (
        core_staged_copy_tables()
        | year_copy_tables()
        | history_snapshot_tables()
        | shared_not_per_version_tables()
        | equipment_group_yearly_param_tables()
    )


def equipment_group_yearly_param_tables() -> set[tuple[str, str]]:
    """Годовые параметры ГО: в новую версию не копируются, копируются только сами группы."""
    fue = SCHEMA_FUEL
    return {
        (fue, "gs_fue_equipment_group_fuel_param"),
        (fue, "gs_fue_equipment_group_natural_fuel"),
        (fue, "gs_fue_equipment_group_extra_fuel_param"),
        (fue, "gs_fue_equipment_group_heat_and_tariffs"),
        (fue, "gs_fue_equipment_group_electricity_production_cost"),
        (fue, "gs_fue_equipment_group_fuel_formula"),
        (fue, "gs_fue_equipment_group_specific_fuel_consumption"),
        (fue, "gs_fue_equipment_group_specific_fuel_price"),
        (fue, "gs_fue_equipment_group_specific_fuel_cost"),
        (fue, "gs_fue_equipment_group_coefficient_results"),
    }


def delete_skip_tables() -> set[tuple[str, str]]:
    return shared_not_per_version_tables()


def _qi(name: str) -> str:
    if not name or not _IDENT_RE.match(name):
        raise ValueError(f"Некорректный SQL-идентификатор: {name!r}")
    return name


def _table_key(schema: str, table: str) -> str:
    return f"{schema}.{table}"


def topo_sort_tables(
    tables: list[tuple[str, str]],
    fks_by_table: dict[tuple[str, str], list[tuple[str, str, str]]],
) -> list[tuple[str, str]]:
    """Родители раньше детей. Self-FK в порядок не входят."""
    table_set = set(tables)
    incoming: dict[tuple[str, str], int] = {t: 0 for t in tables}
    outgoing: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)

    for child in tables:
        seen_parents = set()
        for _col, parent_schema, parent_table in fks_by_table.get(child, []):
            parent = (parent_schema, parent_table)
            if parent == child or parent not in table_set or parent in seen_parents:
                continue
            seen_parents.add(parent)
            outgoing[parent].append(child)
            incoming[child] += 1

    queue = deque(t for t in tables if incoming[t] == 0)
    ordered: list[tuple[str, str]] = []
    while queue:
        node = queue.popleft()
        ordered.append(node)
        for child in outgoing.get(node, []):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)

    leftover = [t for t in tables if t not in ordered]
    ordered.extend(leftover)
    return ordered


def filter_versioned_tables_for_copy(
    versioned_tables: list[tuple[str, str]],
    *,
    copy_mode: str = "full",
) -> list[tuple[str, str]]:
    skip = copy_skip_tables()
    refdata_only = (copy_mode or "full").lower() == "refdata_only"
    result = []
    for schema, table in versioned_tables:
        if table in VERSION_REGISTRY_TABLES:
            continue
        if (schema, table) in skip:
            continue
        if refdata_only and schema != SCHEMA_REFDATA:
            continue
        result.append((schema, table))
    return result


def filter_versioned_tables_for_delete(
    versioned_tables: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    skip = delete_skip_tables()
    result = []
    for schema, table in versioned_tables:
        if table in VERSION_REGISTRY_TABLES:
            continue
        if (schema, table) in skip:
            continue
        result.append((schema, table))
    return result


def list_versioned_tables(schemas: tuple[str, ...] | None = None) -> list[tuple[str, str]]:
    schemas = schemas or versioned_data_schemas()
    rows = db.session.execute(
        text(
            """
            SELECT c.table_schema, c.table_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema
             AND t.table_name = c.table_name
            WHERE c.column_name = 'database_version_id'
              AND t.table_type = 'BASE TABLE'
              AND c.table_schema = ANY(:schemas)
            ORDER BY c.table_schema, c.table_name
            """
        ),
        {"schemas": list(schemas)},
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _list_fk_rows(schemas: tuple[str, ...], *, single_column_only: bool):
    sql = """
        SELECT
            src_ns.nspname AS table_schema,
            src_cls.relname AS table_name,
            src_att.attname AS column_name,
            dst_ns.nspname AS foreign_schema,
            dst_cls.relname AS foreign_table
        FROM pg_constraint con
        JOIN pg_class src_cls ON src_cls.oid = con.conrelid
        JOIN pg_namespace src_ns ON src_ns.oid = src_cls.relnamespace
        JOIN pg_class dst_cls ON dst_cls.oid = con.confrelid
        JOIN pg_namespace dst_ns ON dst_ns.oid = dst_cls.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS src_cols(attnum, ord) ON true
        JOIN pg_attribute src_att
          ON src_att.attrelid = src_cls.oid
         AND src_att.attnum = src_cols.attnum
        WHERE con.contype = 'f'
          AND src_ns.nspname = ANY(:schemas)
          AND dst_cls.relname <> ALL(:registry)
    """
    if single_column_only:
        sql += " AND array_length(con.conkey, 1) = 1"
    sql += " ORDER BY src_ns.nspname, src_cls.relname, src_att.attname"
    return db.session.execute(
        text(sql),
        {"schemas": list(schemas), "registry": list(VERSION_REGISTRY_TABLES)},
    ).fetchall()


def list_single_column_fks(
    schemas: tuple[str, ...] | None = None,
) -> dict[tuple[str, str], list[tuple[str, str, str]]]:
    """{ (schema, table): [(column, foreign_schema, foreign_table), ...] }."""
    schemas = schemas or versioned_data_schemas()
    result: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for schema, table, column, foreign_schema, foreign_table in _list_fk_rows(
        schemas, single_column_only=True
    ):
        result[(schema, table)].append((column, foreign_schema, foreign_table))
    return dict(result)


def list_fk_dependencies(
    schemas: tuple[str, ...] | None = None,
) -> dict[tuple[str, str], list[tuple[str, str, str]]]:
    """Все FK, включая составные (для порядка copy/delete)."""
    schemas = schemas or versioned_data_schemas()
    result: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    seen: set[tuple[str, str, str, str, str]] = set()
    for schema, table, column, foreign_schema, foreign_table in _list_fk_rows(
        schemas, single_column_only=False
    ):
        key = (schema, table, column, foreign_schema, foreign_table)
        if key in seen:
            continue
        seen.add(key)
        result[(schema, table)].append((column, foreign_schema, foreign_table))
    return dict(result)


def list_table_columns(schema: str, table: str) -> list[str]:
    rows = db.session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = :table_name
              AND COALESCE(is_generated, 'NEVER') <> 'ALWAYS'
            ORDER BY ordinal_position
            """
        ),
        {"schema_name": schema, "table_name": table},
    ).fetchall()
    return [row[0] for row in rows]


def discover_satellite_tables(
    versioned_tables: list[tuple[str, str]],
    fks_by_table: dict[tuple[str, str], list[tuple[str, str, str]]],
) -> dict[tuple[str, str], list[tuple[str, str, str]]]:
    """Таблицы без database_version_id, ссылающиеся на версионные."""
    versioned = set(versioned_tables)
    skip = delete_skip_tables() | copy_skip_tables()
    satellites: dict[tuple[str, str], list[tuple[str, str, str]]] = {}
    for child, fks in fks_by_table.items():
        if child in versioned or child in skip:
            continue
        if child[1] in VERSION_REGISTRY_TABLES:
            continue
        parent_fks = [
            (col, pschema, ptable)
            for col, pschema, ptable in fks
            if (pschema, ptable) in versioned
        ]
        if parent_fks:
            satellites[child] = parent_fks
    return satellites


def _logger():
    try:
        return current_app.logger
    except Exception:
        import logging

        return logging.getLogger(__name__)


def _fill_mapping_temp(temp_name: str, mapping: dict[int, int]) -> None:
    db.session.execute(text(f"DROP TABLE IF EXISTS {temp_name}"))
    db.session.execute(
        text(
            f"""
            CREATE TEMP TABLE {temp_name} (
                old_id INTEGER PRIMARY KEY,
                new_id INTEGER NOT NULL
            )
            """
        )
    )
    rows = [{"old_id": old_id, "new_id": new_id} for old_id, new_id in mapping.items()]
    insert_sql = text(
        f"INSERT INTO {temp_name} (old_id, new_id) VALUES (:old_id, :new_id) "
        "ON CONFLICT (old_id) DO NOTHING"
    )
    for i in range(0, len(rows), _IDENT_BATCH):
        db.session.execute(insert_sql, rows[i : i + _IDENT_BATCH])


def _ensure_mapping_temps(
    id_mappings: dict[str, dict[int, int]],
    temps: dict[str, str],
) -> None:
    for key, mapping in id_mappings.items():
        if key in temps or not mapping:
            continue
        temp_name = f"tmp_vmap_{len(temps)}"
        _qi(temp_name)
        _fill_mapping_temp(temp_name, mapping)
        temps[key] = temp_name


def _copy_versioned_table(
    schema: str,
    table: str,
    source_version_id,
    target_version_id,
    id_mappings: dict[str, dict[int, int]],
    fks: list[tuple[str, str, str]],
    mapping_temps: dict[str, str],
    user,
) -> tuple[int, dict[int, int]]:
    schema = _qi(schema)
    table = _qi(table)
    columns = list_table_columns(schema, table)
    if not columns:
        return 0, {}
    has_id = "id" in columns
    copy_columns = [c for c in columns if c not in ("id", "database_version_id")]
    if not copy_columns:
        return 0, {}

    _ensure_mapping_temps(id_mappings, mapping_temps)

    select_parts = []
    joins = []
    used_aliases = set()
    self_fks = []
    for col in copy_columns:
        col = _qi(col)
        fk_match = next((fk for fk in fks if fk[0] == col), None)
        if fk_match:
            _c, foreign_schema, foreign_table = fk_match
            if (foreign_schema, foreign_table) == (schema, table):
                self_fks.append(col)
                select_parts.append(f"s.{col}")
                continue
            map_key = _table_key(foreign_schema, foreign_table)
            temp_name = mapping_temps.get(map_key)
            if temp_name:
                alias = f"m_{col}"
                if alias in used_aliases:
                    alias = f"m_{col}_{len(used_aliases)}"
                alias = _qi(alias)
                used_aliases.add(alias)
                joins.append(f"LEFT JOIN {temp_name} {alias} ON {alias}.old_id = s.{col}")
                select_parts.append(f"COALESCE({alias}.new_id, s.{col}) AS {col}")
                continue
        select_parts.append(f"s.{col}")

    if source_version_id is None:
        where_clause = "s.database_version_id IS NULL"
        params = {"target_version_id": target_version_id}
    else:
        where_clause = "s.database_version_id = :source_version_id"
        params = {
            "source_version_id": source_version_id,
            "target_version_id": target_version_id,
        }

    order_clause = "ORDER BY s.id" if has_id else ""
    returning = "RETURNING id" if has_id else ""
    cols_sql = ", ".join(copy_columns)
    select_sql = ", ".join(select_parts)
    joins_sql = "\n".join(joins)

    copy_sql = text(
        f"""
        WITH source_data AS (
            SELECT {select_sql}
                   {", s.id AS old_id" if has_id else ""}
            FROM {schema}.{table} s
            {joins_sql}
            WHERE {where_clause}
            {order_clause}
        )
        INSERT INTO {schema}.{table} ({cols_sql}, database_version_id)
        SELECT {cols_sql}, :target_version_id
        FROM source_data
        {returning}
        """
    )
    result = db.session.execute(copy_sql, params)
    new_ids = [row[0] for row in result] if has_id else []
    db.session.flush()

    mapping: dict[int, int] = {}
    if has_id:
        old_ids = [
            row[0]
            for row in db.session.execute(
                text(
                    f"""
                    SELECT id FROM {schema}.{table} s
                    WHERE {where_clause}
                    ORDER BY id
                    """
                ),
                params,
            )
        ]
        if len(old_ids) == len(new_ids):
            mapping = dict(zip(old_ids, new_ids))
        else:
            min_len = min(len(old_ids), len(new_ids))
            mapping = dict(zip(old_ids[:min_len], new_ids[:min_len]))
            _logger().warning(
                "Несоответствие ID при копировании %s.%s: старых=%s новых=%s",
                schema,
                table,
                len(old_ids),
                len(new_ids),
            )

        if mapping:
            map_key = _table_key(schema, table)
            id_mappings[map_key] = mapping
            temp_name = f"tmp_vmap_{len(mapping_temps)}"
            _qi(temp_name)
            _fill_mapping_temp(temp_name, mapping)
            mapping_temps[map_key] = temp_name

        for self_col in self_fks:
            _remap_self_fk(schema, table, self_col, mapping, target_version_id)

    copied = len(new_ids) if has_id else result.rowcount or 0
    if copied:
        log_to_db(
            user,
            f"Скопированы данные таблицы {schema}.{table}",
            f"Из версии {source_version_id} в версию {target_version_id}: {copied} записей",
            entity_type="database_version",
            entity_id=target_version_id,
        )
    return copied, mapping


def _remap_self_fk(schema, table, fk_column, mapping, target_version_id) -> None:
    if not mapping:
        return
    temp_name = f"tmp_self_{_qi(fk_column)}_{int(target_version_id)}"
    _qi(temp_name)
    _fill_mapping_temp(temp_name, mapping)
    db.session.execute(
        text(
            f"""
            UPDATE {schema}.{table} t
            SET {fk_column} = m.new_id
            FROM {temp_name} m
            WHERE t.database_version_id = :target_version_id
              AND t.{fk_column} = m.old_id
              AND t.{fk_column} IS DISTINCT FROM m.new_id
            """
        ),
        {"target_version_id": target_version_id},
    )
    db.session.execute(text(f"DROP TABLE IF EXISTS {temp_name}"))


def _copy_satellite_table(
    schema: str,
    table: str,
    parent_fks: list[tuple[str, str, str]],
    id_mappings: dict[str, dict[int, int]],
    mapping_temps: dict[str, str],
    target_version_id,
    user,
) -> tuple[int, dict[int, int]]:
    schema = _qi(schema)
    table = _qi(table)
    columns = list_table_columns(schema, table)
    if not columns:
        return 0, {}
    has_id = "id" in columns
    copy_columns = [c for c in columns if c != "id"]
    if not copy_columns:
        return 0, {}

    _ensure_mapping_temps(id_mappings, mapping_temps)

    parent_temps = []
    for col, pschema, ptable in parent_fks:
        map_key = _table_key(pschema, ptable)
        temp_name = mapping_temps.get(map_key)
        if temp_name:
            parent_temps.append((_qi(col), temp_name, map_key))
    if not parent_temps:
        return 0, {}

    select_parts = []
    joins = []
    used_aliases = set()
    for col in copy_columns:
        col = _qi(col)
        parent_match = next((p for p in parent_temps if p[0] == col), None)
        if parent_match:
            alias = _qi(f"m_{col}")
            if alias in used_aliases:
                alias = _qi(f"m_{col}_{len(used_aliases)}")
            used_aliases.add(alias)
            joins.append(f"LEFT JOIN {parent_match[1]} {alias} ON {alias}.old_id = s.{col}")
            select_parts.append(f"COALESCE({alias}.new_id, s.{col}) AS {col}")
        else:
            select_parts.append(f"s.{col}")

    where_parts = [f"s.{col} IN (SELECT old_id FROM {temp})" for col, temp, _k in parent_temps]
    old_id_select = ", s.id AS old_id" if has_id else ""
    order_clause = "ORDER BY s.id" if has_id else ""
    returning = "RETURNING id" if has_id else ""

    copy_sql = text(
        f"""
        WITH source_data AS (
            SELECT {", ".join(select_parts)}{old_id_select}
            FROM {schema}.{table} s
            {" ".join(joins)}
            WHERE {" OR ".join(where_parts)}
            {order_clause}
        )
        INSERT INTO {schema}.{table} ({", ".join(copy_columns)})
        SELECT {", ".join(copy_columns)}
        FROM source_data
        ON CONFLICT DO NOTHING
        {returning}
        """
    )
    result = db.session.execute(copy_sql)
    new_ids = [row[0] for row in result] if has_id else []
    db.session.flush()
    mapping: dict[int, int] = {}
    copied = len(new_ids) if has_id else result.rowcount or 0
    if has_id and new_ids:
        old_ids = [
            row[0]
            for row in db.session.execute(
                text(
                    f"""
                    SELECT s.id
                    FROM {schema}.{table} s
                    WHERE {" OR ".join(where_parts)}
                    ORDER BY s.id
                    """
                )
            )
        ]
        min_len = min(len(old_ids), len(new_ids))
        mapping = dict(zip(old_ids[:min_len], new_ids[:min_len]))
        if mapping:
            map_key = _table_key(schema, table)
            id_mappings[map_key] = mapping
            temp_name = f"tmp_vmap_{len(mapping_temps)}"
            _qi(temp_name)
            _fill_mapping_temp(temp_name, mapping)
            mapping_temps[map_key] = temp_name

    if copied:
        log_to_db(
            user,
            f"Скопированы данные спутниковой таблицы {schema}.{table}",
            f"В версию {target_version_id}: {copied} записей",
            entity_type="database_version",
            entity_id=target_version_id,
        )
    return copied, mapping


def copy_remaining_module_tables(
    source_version_id,
    target_version_id,
    user,
    id_mappings: dict[str, dict[int, int]],
    copy_mode: str = "full",
) -> int:
    """Копирует данные модулей, не покрытые поэтапным копированием generation/refdata."""
    log_to_db(
        user,
        "Копирование данных остальных модулей версии",
        f"Из версии {source_version_id} в версию {target_version_id}, режим={copy_mode}",
        entity_type="database_version",
        entity_id=target_version_id,
    )
    versioned = list_versioned_tables()
    fks_by_table = list_single_column_fks()
    fks_for_topo = list_fk_dependencies()
    to_copy = filter_versioned_tables_for_copy(versioned, copy_mode=copy_mode)
    satellites = discover_satellite_tables(versioned, fks_by_table)
    if (copy_mode or "full").lower() == "refdata_only":
        remaining_set = set(to_copy)
        satellites = {
            child: fks
            for child, fks in satellites.items()
            if all((ps, pt) in remaining_set or _table_key(ps, pt) in id_mappings for _c, ps, pt in fks)
            and child[0] == SCHEMA_REFDATA
        }

    copy_nodes = list(dict.fromkeys(to_copy + list(satellites.keys())))
    ordered = topo_sort_tables(copy_nodes, fks_for_topo)
    mapping_temps: dict[str, str] = {}
    _ensure_mapping_temps(id_mappings, mapping_temps)

    total_copied = 0
    versioned_set = set(to_copy)
    for schema, table in ordered:
        try:
            with db.session.begin_nested():
                if (schema, table) in versioned_set:
                    copied, _mapping = _copy_versioned_table(
                        schema,
                        table,
                        source_version_id,
                        target_version_id,
                        id_mappings,
                        fks_by_table.get((schema, table), []),
                        mapping_temps,
                        user,
                    )
                elif (schema, table) in satellites:
                    copied, _mapping = _copy_satellite_table(
                        schema,
                        table,
                        satellites[(schema, table)],
                        id_mappings,
                        mapping_temps,
                        target_version_id,
                        user,
                    )
                else:
                    continue
                total_copied += copied
                if copied:
                    _logger().info(
                        "Скопирована таблица %s.%s: %s записей",
                        schema,
                        table,
                        copied,
                    )
        except Exception as exc:
            _logger().error("Ошибка копирования таблицы %s.%s: %s", schema, table, exc)
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                str(exc),
                entity_type="database_version",
                entity_id=target_version_id,
            )

    log_to_db(
        user,
        "Копирование данных остальных модулей завершено",
        f"Из версии {source_version_id} в версию {target_version_id}: {total_copied} записей",
        entity_type="database_version",
        entity_id=target_version_id,
    )
    return total_copied


def _delete_from_versioned_table(schema: str, table: str, version_id) -> int:
    schema = _qi(schema)
    table = _qi(table)
    result = db.session.execute(
        text(f"DELETE FROM {schema}.{table} WHERE database_version_id = :version_id"),
        {"version_id": version_id},
    )
    db.session.commit()
    return result.rowcount or 0


def _delete_from_satellite_table(
    schema: str,
    table: str,
    parent_fks: list[tuple[str, str, str]],
    version_id,
) -> int:
    schema = _qi(schema)
    table = _qi(table)
    conditions = []
    for col, pschema, ptable in parent_fks:
        col = _qi(col)
        pschema = _qi(pschema)
        ptable = _qi(ptable)
        conditions.append(
            f"{col} IN (SELECT id FROM {pschema}.{ptable} WHERE database_version_id = :version_id)"
        )
    if not conditions:
        return 0
    result = db.session.execute(
        text(f"DELETE FROM {schema}.{table} WHERE {' OR '.join(conditions)}"),
        {"version_id": version_id},
    )
    db.session.commit()
    return result.rowcount or 0


def delete_all_module_data_for_version(version_id, user) -> int:
    """Удаляет версионные данные всех модулей, включая спутниковые таблицы."""
    log_to_db(
        user,
        f"Начало удаления данных всех модулей версии БД ID={version_id}",
        "Версионные таблицы и спутники (FK на версионные строки)",
        entity_type="database_version",
        entity_id=version_id,
    )
    versioned = filter_versioned_tables_for_delete(list_versioned_tables())
    fks_by_table = list_single_column_fks()
    fks_for_topo = list_fk_dependencies()
    satellites = discover_satellite_tables(versioned, fks_by_table)

    nodes = list(dict.fromkeys(versioned + list(satellites.keys())))
    ordered = list(reversed(topo_sort_tables(nodes, fks_for_topo)))
    versioned_set = set(versioned)

    pending = list(ordered)
    total_deleted = 0
    max_rounds = max(3, len(pending) + 1)
    for _round in range(max_rounds):
        if not pending:
            break
        failed = []
        progressed = False
        for schema, table in pending:
            try:
                if (schema, table) in versioned_set:
                    deleted = _delete_from_versioned_table(schema, table, version_id)
                elif (schema, table) in satellites:
                    deleted = _delete_from_satellite_table(
                        schema, table, satellites[(schema, table)], version_id
                    )
                else:
                    continue
                total_deleted += deleted
                progressed = True
                if deleted:
                    _logger().info(
                        "Удалено %s записей из %s.%s для версии %s",
                        deleted,
                        schema,
                        table,
                        version_id,
                    )
            except Exception as exc:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                failed.append((schema, table))
                _logger().warning(
                    "Не удалось удалить %s.%s для версии %s: %s",
                    schema,
                    table,
                    version_id,
                    exc,
                )
                log_to_db(
                    user,
                    f"Ошибка удаления данных из таблицы {schema}.{table}",
                    f"Версия {version_id}: {exc}",
                    entity_type="database_version",
                    entity_id=version_id,
                )
        if not failed:
            pending = []
            break
        if not progressed:
            break
        pending = failed

    log_to_db(
        user,
        f"Удаление данных всех модулей версии БД ID={version_id} завершено",
        f"Всего удалено записей: {total_deleted}",
        entity_type="database_version",
        entity_id=version_id,
    )
    return total_deleted
