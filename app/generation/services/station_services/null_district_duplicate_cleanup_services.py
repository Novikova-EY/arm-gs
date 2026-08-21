# -*- coding: utf-8 -*-
"""Поиск и удаление станций-дубликатов без субъекта РФ.

Дубликат: в той же версии БД есть одноимённая станция с заполненным субъектом,
а у этой записи id_regional_district IS NULL. Такие «призраки» попадают
в семейство на странице проверки external_code и дают ложный жёлтый.

Станции с агрегатами или котлами не удаляются.
Связанные выработки / заряд ГАЭС / связи типов ГО переносятся на «живую»
станцию той же версии или удаляются, если у неё уже есть такая строка.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection


@dataclass(frozen=True)
class CleanupSchemas:
    gen: str = "gs_gen"
    ref: str = "gs_sys"
    fue: str = "gs_fue"
    bem: str = "gs_bem"


@dataclass
class DuplicateStation:
    id: int
    name: str
    external_code: str
    database_version_id: int | None
    version_number: str
    kto: str | None
    machines: int
    boilers: int
    generations: int
    gaes: int
    eg_links: int
    eg_sets: int
    keeper_ids: list[int]
    keeper_codes: list[str]
    keeper_rd_names: list[str]

    @property
    def has_movable_children(self) -> bool:
        return bool(self.generations or self.gaes or self.eg_links or self.eg_sets)

    @property
    def blocked_reason(self) -> str | None:
        if self.machines:
            return "есть агрегаты"
        if self.boilers:
            return "есть котлы"
        if len(self.keeper_ids) != 1 and self.has_movable_children:
            return "несколько одноимённых станций с субъектом в той же версии"
        return None

    @property
    def keeper_id(self) -> int | None:
        if len(self.keeper_ids) != 1:
            return None
        return self.keeper_ids[0]


@dataclass
class CleanupReport:
    duplicates: list[DuplicateStation] = field(default_factory=list)
    deleted_station_ids: list[int] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    moved_generations: int = 0
    deleted_generations: int = 0
    moved_gaes: int = 0
    deleted_gaes: int = 0
    moved_eg_sets: int = 0
    deleted_eg_sets: int = 0
    deleted_eg_links: int = 0
    reassigned_eg_links: int = 0


def schemas_from_env() -> CleanupSchemas:
    from config import (
        SCHEMA_ENERGY_BALANCE,
        SCHEMA_FUEL,
        SCHEMA_GENERATION,
        SCHEMA_REFDATA,
    )

    return CleanupSchemas(
        gen=SCHEMA_GENERATION,
        ref=SCHEMA_REFDATA,
        fue=SCHEMA_FUEL,
        bem=SCHEMA_ENERGY_BALANCE,
    )


def _as_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [int(item) for item in value if item is not None]
    return [int(value)]


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def find_null_district_name_duplicates(
    conn: Connection,
    schemas: CleanupSchemas | None = None,
) -> list[DuplicateStation]:
    schemas = schemas or schemas_from_env()
    sql = text(
        f"""
        WITH null_st AS (
            SELECT
                s.id,
                s.name,
                lower(btrim(s.name)) AS name_key,
                s.external_code,
                s.database_version_id,
                s.kto
            FROM {schemas.gen}.gs_gen_stations s
            WHERE s.id_regional_district IS NULL
              AND btrim(COALESCE(s.name, '')) <> ''
        ),
        keepers AS (
            SELECT
                s.id,
                lower(btrim(s.name)) AS name_key,
                s.external_code,
                s.database_version_id,
                s.id_regional_district
            FROM {schemas.gen}.gs_gen_stations s
            WHERE s.id_regional_district IS NOT NULL
              AND btrim(COALESCE(s.name, '')) <> ''
        )
        SELECT
            n.id,
            n.name,
            n.external_code,
            n.database_version_id,
            COALESCE(v.version_number, n.database_version_id::text) AS version_number,
            n.kto,
            (SELECT COUNT(*) FROM {schemas.gen}.gs_gen_machines m WHERE m.id_station = n.id) AS machines,
            (SELECT COUNT(*) FROM {schemas.gen}.gs_gen_boilers b WHERE b.id_station = n.id) AS boilers,
            (SELECT COUNT(*) FROM {schemas.bem}.gs_bem_station_energy_generations g WHERE g.id_station = n.id) AS generations,
            (SELECT COUNT(*) FROM {schemas.gen}.gs_gen_station_gaes_charge_consumptions g WHERE g.id_station = n.id) AS gaes,
            (SELECT COUNT(*) FROM {schemas.fue}.gs_fue_equipment_group_type_stations l WHERE l.station_id = n.id) AS eg_links,
            (
                SELECT COUNT(*)
                FROM {schemas.fue}.gs_fue_equipment_group_sets st
                JOIN {schemas.fue}.gs_fue_equipment_group_type_stations l
                  ON l.id = st.equipment_group_set_station_id
                WHERE l.station_id = n.id
            ) AS eg_sets,
            ARRAY_AGG(k.id ORDER BY k.id) AS keeper_ids,
            ARRAY_AGG(k.external_code ORDER BY k.id) AS keeper_codes,
            ARRAY_AGG(COALESCE(rd.name, k.id_regional_district::text) ORDER BY k.id) AS keeper_rd_names
        FROM null_st n
        JOIN keepers k
          ON k.name_key = n.name_key
         AND k.database_version_id IS NOT DISTINCT FROM n.database_version_id
        LEFT JOIN {schemas.ref}.gs_database_versions v ON v.id = n.database_version_id
        LEFT JOIN {schemas.ref}.gs_sys_regional_districts rd ON rd.id = k.id_regional_district
        GROUP BY
            n.id, n.name, n.external_code, n.database_version_id, v.version_number, n.kto
        ORDER BY n.name, n.database_version_id, n.id
        """
    )
    return _duplicate_rows_from_result(conn.execute(sql))


def _duplicate_rows_from_result(result) -> list[DuplicateStation]:
    rows = []
    for raw in result:
        mapping = dict(raw._mapping)
        rows.append(
            DuplicateStation(
                id=int(mapping["id"]),
                name=str(mapping["name"] or ""),
                external_code=str(mapping["external_code"] or ""),
                database_version_id=mapping["database_version_id"],
                version_number=str(mapping["version_number"] or ""),
                kto=mapping["kto"],
                machines=int(mapping["machines"] or 0),
                boilers=int(mapping["boilers"] or 0),
                generations=int(mapping["generations"] or 0),
                gaes=int(mapping["gaes"] or 0),
                eg_links=int(mapping["eg_links"] or 0),
                eg_sets=int(mapping["eg_sets"] or 0),
                keeper_ids=_as_int_list(mapping["keeper_ids"]),
                keeper_codes=_as_str_list(mapping["keeper_codes"]),
                keeper_rd_names=_as_str_list(mapping["keeper_rd_names"]),
            )
        )
    return rows


def _move_or_delete_year_rows(
    conn: Connection,
    table: str,
    station_column: str,
    ghost_id: int,
    keeper_id: int,
    extra_key_columns: Iterable[str] = (),
) -> tuple[int, int]:
    """Переносит строки на keeper; при конфликте ключа удаляет строку-дубликат."""
    key_columns = ["year_number", "database_version_id", *extra_key_columns]
    conflict = " AND ".join(
        f"k.{column} IS NOT DISTINCT FROM g.{column}" for column in key_columns
    )
    moved = conn.execute(
        text(
            f"""
            UPDATE {table} AS g
            SET {station_column} = :keeper_id
            WHERE g.{station_column} = :ghost_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM {table} AS k
                  WHERE k.{station_column} = :keeper_id
                    AND {conflict}
              )
            """
        ),
        {"ghost_id": ghost_id, "keeper_id": keeper_id},
    ).rowcount
    deleted = conn.execute(
        text(f"DELETE FROM {table} WHERE {station_column} = :ghost_id"),
        {"ghost_id": ghost_id},
    ).rowcount
    return int(moved or 0), int(deleted or 0)


def _reassign_equipment_group_links(
    conn: Connection,
    schemas: CleanupSchemas,
    ghost_id: int,
    keeper_id: int,
) -> tuple[int, int, int, int]:
    """Возвращает (moved_sets, deleted_sets, reassigned_links, deleted_links)."""
    links = list(
        conn.execute(
            text(
                f"""
                SELECT id, equipment_group_type_id, database_version_id
                FROM {schemas.fue}.gs_fue_equipment_group_type_stations
                WHERE station_id = :ghost_id
                """
            ),
            {"ghost_id": ghost_id},
        )
    )
    moved_sets = 0
    deleted_sets = 0
    reassigned_links = 0
    deleted_links = 0

    for link in links:
        ghost_link_id = int(link.id)
        keeper_link = conn.execute(
            text(
                f"""
                SELECT id
                FROM {schemas.fue}.gs_fue_equipment_group_type_stations
                WHERE station_id = :keeper_id
                  AND equipment_group_type_id IS NOT DISTINCT FROM :type_id
                  AND database_version_id IS NOT DISTINCT FROM :version_id
                ORDER BY id
                LIMIT 1
                """
            ),
            {
                "keeper_id": keeper_id,
                "type_id": link.equipment_group_type_id,
                "version_id": link.database_version_id,
            },
        ).first()

        if keeper_link is None:
            conn.execute(
                text(
                    f"""
                    UPDATE {schemas.fue}.gs_fue_equipment_group_type_stations
                    SET station_id = :keeper_id
                    WHERE id = :link_id
                    """
                ),
                {"keeper_id": keeper_id, "link_id": ghost_link_id},
            )
            reassigned_links += 1
            continue

        keeper_link_id = int(keeper_link.id)
        moved = conn.execute(
            text(
                f"""
                UPDATE {schemas.fue}.gs_fue_equipment_group_sets AS g
                SET equipment_group_set_station_id = :keeper_link_id
                WHERE g.equipment_group_set_station_id = :ghost_link_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {schemas.fue}.gs_fue_equipment_group_sets AS k
                      WHERE k.equipment_group_set_station_id = :keeper_link_id
                        AND k.equipment_group_id = g.equipment_group_id
                  )
                """
            ),
            {
                "keeper_link_id": keeper_link_id,
                "ghost_link_id": ghost_link_id,
            },
        ).rowcount
        moved_sets += int(moved or 0)
        deleted = conn.execute(
            text(
                f"""
                DELETE FROM {schemas.fue}.gs_fue_equipment_group_sets
                WHERE equipment_group_set_station_id = :ghost_link_id
                """
            ),
            {"ghost_link_id": ghost_link_id},
        ).rowcount
        deleted_sets += int(deleted or 0)
        conn.execute(
            text(
                f"""
                DELETE FROM {schemas.fue}.gs_fue_equipment_group_type_stations
                WHERE id = :ghost_link_id
                """
            ),
            {"ghost_link_id": ghost_link_id},
        )
        deleted_links += 1

    leftover = conn.execute(
        text(
            f"""
            DELETE FROM {schemas.fue}.gs_fue_equipment_group_type_stations
            WHERE station_id = :ghost_id
            """
        ),
        {"ghost_id": ghost_id},
    ).rowcount
    deleted_links += int(leftover or 0)
    return moved_sets, deleted_sets, reassigned_links, deleted_links


def cleanup_null_district_duplicates(
    conn: Connection,
    duplicates: list[DuplicateStation] | None = None,
    schemas: CleanupSchemas | None = None,
    apply: bool = False,
) -> CleanupReport:
    schemas = schemas or schemas_from_env()
    report = CleanupReport(
        duplicates=duplicates if duplicates is not None else find_null_district_name_duplicates(conn, schemas)
    )

    for item in report.duplicates:
        reason = item.blocked_reason
        if reason:
            report.skipped.append((item.id, reason))
            continue
        keeper_id = item.keeper_id
        if keeper_id is None and item.has_movable_children:
            report.skipped.append((item.id, "нет однозначной станции-оригинала"))
            continue
        if not apply:
            report.deleted_station_ids.append(item.id)
            continue

        if keeper_id is None:
            conn.execute(
                text(f"DELETE FROM {schemas.gen}.gs_gen_stations WHERE id = :station_id"),
                {"station_id": item.id},
            )
            report.deleted_station_ids.append(item.id)
            continue

        moved_g, deleted_g = _move_or_delete_year_rows(
            conn,
            f"{schemas.bem}.gs_bem_station_energy_generations",
            "id_station",
            item.id,
            keeper_id,
            extra_key_columns=("month_number",),
        )
        report.moved_generations += moved_g
        report.deleted_generations += deleted_g

        moved_gaes, deleted_gaes = _move_or_delete_year_rows(
            conn,
            f"{schemas.gen}.gs_gen_station_gaes_charge_consumptions",
            "id_station",
            item.id,
            keeper_id,
        )
        report.moved_gaes += moved_gaes
        report.deleted_gaes += deleted_gaes

        moved_sets, deleted_sets, reassigned_links, deleted_links = _reassign_equipment_group_links(
            conn, schemas, item.id, keeper_id
        )
        report.moved_eg_sets += moved_sets
        report.deleted_eg_sets += deleted_sets
        report.reassigned_eg_links += reassigned_links
        report.deleted_eg_links += deleted_links

        conn.execute(
            text(f"DELETE FROM {schemas.gen}.gs_gen_stations WHERE id = :station_id"),
            {"station_id": item.id},
        )
        report.deleted_station_ids.append(item.id)

    return report
