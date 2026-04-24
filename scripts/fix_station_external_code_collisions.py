#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Исправляет legacy-коллизии external_code у Station.

Сценарий обновляет только те семейства станций, где один и тот же текущий
external_code используется для разных "логических" станций:
    station name/name_so/name_combined + субъект РФ.

Каскадные изменения:
1. Обновляет Station.external_code для затронутых станций.
2. Пересчитывает Machine.external_code для агрегатов этих станций.
3. Пересчитывает EquipmentGroup.external_code только для station-linked групп,
   у которых текущий код уже соответствует "импортной" формуле от
   station_external_code. Неимпортные группы не трогаются.

Запуск:
    python scripts/fix_station_external_code_collisions.py [--dry-run] [--yes] [--sync-all]

    По умолчанию исправляются только legacy-коллизии (один external_code на разные субъекты).
    --sync-all: пересчитать external_code у всех станций по текущей формуле (после смены
    алгоритма, например добавления ref_uuid в ключ); тяжёлая операция, каскад на Machine/EG.
"""

import argparse
import os
import sys
import uuid
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.machine.machine_model import (
    Machine,
    _normalize_machine_key_part,
    _normalize_machine_name_for_key,
)
from app.generation.models.station.station_model import (
    Station,
    _build_regional_district_key,
    _station_key,
)
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


def _count_sql_multi_ref_external_codes() -> int:
    """Сколько значений external_code закрывают несколько разных ref_uuid (как в pgAdmin)."""
    q = text(
        f"""
        SELECT COUNT(*) FROM (
            SELECT s.external_code
            FROM {SCHEMA_GENERATION}.gs_gen_stations s
            LEFT JOIN {SCHEMA_REFDATA}.gs_sys_regional_districts rd
                ON rd.id = s.id_regional_district
            WHERE trim(COALESCE(s.external_code, '')) <> ''
            GROUP BY s.external_code
            HAVING COUNT(DISTINCT COALESCE(rd.ref_uuid::text, 'NO_SUBJECT')) > 1
        ) t
        """
    )
    row = db.session.execute(q).scalar()
    return int(row or 0)


def _print_db_target() -> None:
    """Печатает фактическое подключение — сверьте host/database с pgAdmin перед применением."""
    url = db.engine.url
    print("Целевая БД (должна совпадать с подключением в pgAdmin):")
    print(f"  driver:   {url.drivername}")
    print(f"  host:     {url.host}")
    print(f"  port:     {url.port}")
    print(f"  database: {url.database}")
    print(f"  user:     {url.username}")
    print(f"  stations: {SCHEMA_GENERATION}.gs_gen_stations")
    print(f"  subjects: {SCHEMA_REFDATA}.gs_sys_regional_districts")
    print()


def _make_uuid5(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _semantic_key_from_sql(
    name,
    name_so,
    name_combined,
    region_number,
    rd_name,
    rd_name_full,
    ref_uuid,
) -> str:
    """
    Тот же ключ, что и при генерации в Station (субъект из строк JOIN, не из ORM).
    В district_key включается ref_uuid субъекта (как в station_model), иначе разные
    субъекты могут схлопываться при совпадении num/краткого name в справочнике.
    """
    district_key = _build_regional_district_key(
        region_number=region_number,
        name=rd_name,
        name_full=rd_name_full,
        ref_uuid=ref_uuid,
    )
    return _station_key(name, name_so, name_combined, district_key)


def _machine_target_external_code(machine: Machine, station_external_code: str) -> str:
    num = _normalize_machine_key_part(machine.machine_number)
    name = _normalize_machine_name_for_key(machine.machine_name)
    if name:
        ident = f"name|{name}"
    elif machine.date_exploitation is not None:
        ident = f"exploitation|{machine.date_exploitation}"
    else:
        ident = "name|"
    key = f"machine|station|{station_external_code}|num|{num}|{ident}"
    return _make_uuid5(key)


def _equipment_group_import_external_code(
    station_external_code: str | None,
    type_key: str | None,
    numb: int | str | None,
) -> str:
    key = (
        f"import|equipment_group|station|{station_external_code or ''}"
        f"|type|{type_key or ''}|numb|{numb or ''}"
    )
    return _make_uuid5(key)


def _build_station_update_plan_sql(sync_all: bool = False) -> tuple[dict[int, str], list[dict], list[dict], int]:
    """Строит план по тем же JOIN, что и ручной SQL в pgAdmin (без ORM regional_district)."""
    station_updates: dict[int, str] = {}
    collision_groups: list[dict] = []
    unresolved_within_same_key: list[dict] = []

    q = text(
        f"""
        SELECT
            s.id AS station_id,
            s.database_version_id AS database_version_id,
            s.external_code AS external_code,
            s.name AS name,
            s.name_so AS name_so,
            s.name_combined AS name_combined,
            rd.region_number AS region_number,
            rd.name AS rd_name,
            rd.name_full AS rd_name_full,
            rd.ref_uuid AS subject_ref_uuid
        FROM {SCHEMA_GENERATION}.gs_gen_stations s
        LEFT JOIN {SCHEMA_REFDATA}.gs_sys_regional_districts rd
            ON rd.id = s.id_regional_district
        """
    )
    rows = db.session.execute(q).fetchall()

    def _m(row) -> dict:
        return dict(row._mapping)

    # Как в SQL: HAVING COUNT(DISTINCT COALESCE(rd.ref_uuid::text, 'NO_SUBJECT')) > 1
    refs_by_ext: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        m = _m(row)
        ext = (m.get("external_code") or "").strip()
        if not ext:
            continue
        ru = m.get("subject_ref_uuid")
        bucket = str(ru).strip().lower() if ru else "NO_SUBJECT"
        refs_by_ext[ext].add(bucket)

    sql_bad_exts = {ext for ext, refs in refs_by_ext.items() if len(refs) > 1}

    rows_by_external_code: dict[str, list] = defaultdict(list)
    for row in rows:
        m = _m(row)
        ext = (m.get("external_code") or "").strip()
        if ext:
            rows_by_external_code[ext].append(row)

    def _sk_from_m(m: dict) -> str:
        return _semantic_key_from_sql(
            m.get("name"),
            m.get("name_so"),
            m.get("name_combined"),
            m.get("region_number"),
            m.get("rd_name"),
            m.get("rd_name_full"),
            m.get("subject_ref_uuid"),
        )

    def _append_unresolved_for_target(target_code: str, semantic_key: str, members: list) -> None:
        versions = defaultdict(list)
        for row in members:
            mm = _m(row)
            versions[mm["database_version_id"]].append(mm["station_id"])
        duplicate_versions = {
            version_id: ids
            for version_id, ids in versions.items()
            if len(ids) > 1
        }
        if duplicate_versions:
            unresolved_within_same_key.append(
                {
                    "target_external_code": target_code,
                    "semantic_key": semantic_key,
                    "versions": duplicate_versions,
                }
            )

    if sync_all:
        # При смене формулы ключа (например, добавлен ref_uuid) привести все станции к uuid5(semantic_key).
        targets_to_rows: dict[str, list] = defaultdict(list)
        for row in rows:
            mm = _m(row)
            sk = _sk_from_m(mm)
            target_code = _make_uuid5(sk)
            targets_to_rows[target_code].append(row)
            if (mm.get("external_code") or "").strip() != target_code:
                station_updates[mm["station_id"]] = target_code

        for target_code, members in targets_to_rows.items():
            sample = _m(members[0])
            sk = _sk_from_m(sample)
            _append_unresolved_for_target(target_code, sk, members)

        for external_code, group_rows in rows_by_external_code.items():
            semantic_groups: dict[str, list] = defaultdict(list)
            for row in group_rows:
                semantic_groups[_sk_from_m(_m(row))].append(row)
            if len(semantic_groups) > 1:
                collision_groups.append(
                    {
                        "external_code": external_code,
                        "station_ids": sorted(_m(r)["station_id"] for r in group_rows),
                        "semantic_groups": {
                            semantic_key: sorted(_m(r)["station_id"] for r in members)
                            for semantic_key, members in semantic_groups.items()
                        },
                    }
                )

        return station_updates, collision_groups, unresolved_within_same_key, len(sql_bad_exts)

    for external_code, group_rows in rows_by_external_code.items():
        semantic_groups: dict[str, list] = defaultdict(list)
        for row in group_rows:
            mm = _m(row)
            semantic_groups[_sk_from_m(mm)].append(row)

        multi_ref = external_code in sql_bad_exts

        if not multi_ref and len(semantic_groups) <= 1:
            continue

        collision_groups.append(
            {
                "external_code": external_code,
                "station_ids": sorted(_m(r)["station_id"] for r in group_rows),
                "sql_multi_ref": multi_ref,
                "semantic_groups": {
                    semantic_key: sorted(_m(r)["station_id"] for r in members)
                    for semantic_key, members in semantic_groups.items()
                },
            }
        )

        if multi_ref:
            # Один и тот же uuid5(sk) на разных субъектах, если sk схлопнулся — добиваем ref_uuid.
            raw_targets: dict[int, str] = {}
            for row in group_rows:
                mm = _m(row)
                raw_targets[mm["station_id"]] = _make_uuid5(_sk_from_m(mm))
            by_target: dict[str, list[int]] = defaultdict(list)
            for sid, t in raw_targets.items():
                by_target[t].append(sid)
            need_suffix = any(len(v) > 1 for v in by_target.values())

            for row in group_rows:
                mm = _m(row)
                sk = _sk_from_m(mm)
                if need_suffix:
                    ru = (mm.get("subject_ref_uuid") or "NULL").strip().lower()
                    target_code = _make_uuid5(f"{sk}|ref_uuid|{ru}")
                else:
                    target_code = _make_uuid5(sk)
                if (mm.get("external_code") or "").strip() != target_code:
                    station_updates[mm["station_id"]] = target_code

            targets_to_rows_mr: dict[str, list] = defaultdict(list)
            for row in group_rows:
                mm = _m(row)
                sk = _sk_from_m(mm)
                if need_suffix:
                    ru = (mm.get("subject_ref_uuid") or "NULL").strip().lower()
                    tcode = _make_uuid5(f"{sk}|ref_uuid|{ru}")
                else:
                    tcode = _make_uuid5(sk)
                targets_to_rows_mr[tcode].append(row)
            for tcode, members in targets_to_rows_mr.items():
                sk0 = _sk_from_m(_m(members[0]))
                _append_unresolved_for_target(tcode, sk0, members)
        else:
            for semantic_key, members in semantic_groups.items():
                target_code = _make_uuid5(semantic_key)
                for row in members:
                    mm = _m(row)
                    if (mm.get("external_code") or "").strip() != target_code:
                        station_updates[mm["station_id"]] = target_code
                _append_unresolved_for_target(target_code, semantic_key, members)

    return station_updates, collision_groups, unresolved_within_same_key, len(sql_bad_exts)


def _build_machine_update_plan(station_updates: dict[int, str]) -> dict[int, str]:
    if not station_updates:
        return {}

    machine_updates: dict[int, str] = {}
    machines = (
        Machine.query.filter(Machine.id_station.in_(list(station_updates.keys())))
        .all()
    )
    for machine in machines:
        target_station_code = station_updates.get(machine.id_station)
        if not target_station_code:
            continue
        target_code = _machine_target_external_code(machine, target_station_code)
        if (machine.external_code or "").strip() != target_code:
            machine_updates[machine.id] = target_code

    return machine_updates


def _build_equipment_group_update_plan(
    station_updates: dict[int, str],
) -> tuple[dict[int, str], list[dict], list[dict]]:
    if not station_updates:
        return {}, [], []

    impacted_group_ids = [
        row[0]
        for row in (
            db.session.query(EquipmentGroupSet.equipment_group_id)
            .join(
                EquipmentGroupSetStation,
                EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
            )
            .filter(EquipmentGroupSetStation.station_id.in_(list(station_updates.keys())))
            .distinct()
            .all()
        )
    ]
    if not impacted_group_ids:
        return {}, [], []

    rows = (
        db.session.query(
            EquipmentGroup.id,
            EquipmentGroup.external_code,
            EquipmentGroup.numb,
            EquipmentGroupSetStation.station_id,
            Station.external_code,
            EquipmentGroupSetStation.equipment_group_type_id,
            EquipmentGroupType.ref_uuid,
            EquipmentGroupType.name,
        )
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .outerjoin(EquipmentGroupType, EquipmentGroupType.id == EquipmentGroupSetStation.equipment_group_type_id)
        .filter(EquipmentGroup.id.in_(impacted_group_ids))
        .all()
    )

    by_group_id: dict[int, dict] = {}
    for row in rows:
        group_id = row[0]
        current_group_code = (row[1] or "").strip()
        numb = row[2]
        station_id = row[3]
        current_station_code = (row[4] or "").strip()
        equipment_group_type_id = row[5]
        ref_uuid = row[6]
        type_name = row[7]
        type_key = ref_uuid or type_name or str(equipment_group_type_id)
        target_station_code = station_updates.get(station_id, current_station_code)

        old_expected_code = _equipment_group_import_external_code(
            current_station_code,
            type_key,
            numb,
        )
        new_expected_code = _equipment_group_import_external_code(
            target_station_code,
            type_key,
            numb,
        )

        payload = by_group_id.setdefault(
            group_id,
            {
                "current_code": current_group_code,
                "old_expected_codes": set(),
                "new_expected_codes": set(),
                "station_ids": set(),
                "type_keys": set(),
            },
        )
        payload["old_expected_codes"].add(old_expected_code)
        payload["new_expected_codes"].add(new_expected_code)
        payload["station_ids"].add(station_id)
        payload["type_keys"].add(type_key)

    equipment_group_updates: dict[int, str] = {}
    non_import_groups: list[dict] = []
    ambiguous_groups: list[dict] = []

    for group_id, payload in by_group_id.items():
        current_code = payload["current_code"]
        old_expected_codes = payload["old_expected_codes"]
        new_expected_codes = payload["new_expected_codes"]

        if current_code not in old_expected_codes:
            non_import_groups.append(
                {
                    "equipment_group_id": group_id,
                    "current_code": current_code,
                    "station_ids": sorted(payload["station_ids"]),
                }
            )
            continue

        if len(new_expected_codes) != 1:
            ambiguous_groups.append(
                {
                    "equipment_group_id": group_id,
                    "current_code": current_code,
                    "candidate_codes": sorted(new_expected_codes),
                    "station_ids": sorted(payload["station_ids"]),
                }
            )
            continue

        target_code = next(iter(new_expected_codes))
        if current_code != target_code:
            equipment_group_updates[group_id] = target_code

    return equipment_group_updates, non_import_groups, ambiguous_groups


def _print_diagnose() -> None:
    """Сводка по БД: совпадает ли логика «плохих» кодов с SQL и что с примером имени."""
    q_rows = text(
        f"""
        SELECT
            s.id AS station_id,
            s.external_code AS external_code,
            s.name AS name,
            rd.ref_uuid AS subject_ref_uuid
        FROM {SCHEMA_GENERATION}.gs_gen_stations s
        LEFT JOIN {SCHEMA_REFDATA}.gs_sys_regional_districts rd
            ON rd.id = s.id_regional_district
        WHERE s.name ILIKE :pat
        ORDER BY s.id
        LIMIT 30
        """
    )
    sample = db.session.execute(q_rows, {"pat": "%\u0426\u0435\u043d\u0442\u0440\u0430\u043b\u044c\u043d\u0430\u044f \u0422\u042d\u0426%"}).fetchall()
    print("Диагностика (пример: имя ILIKE '%Центральная ТЭЦ%', до 30 строк):")
    if not sample:
        print("  строк не найдено")
    else:
        ext_codes = {dict(r._mapping).get("external_code") for r in sample}
        refs = {dict(r._mapping).get("subject_ref_uuid") for r in sample}
        print(f"  строк: {len(sample)}, разных external_code: {len(ext_codes)}, разных ref_uuid: {len(refs)}")
        for r in sample[:8]:
            m = dict(r._mapping)
            print(
                f"  id={m.get('station_id')} ext={str(m.get('external_code'))[:36]}... "
                f"ref={(str(m.get('subject_ref_uuid'))[:8] if m.get('subject_ref_uuid') else 'NULL')}..."
            )
    print()


def _print_station_examples(station_updates: dict[int, str]) -> None:
    if not station_updates:
        return
    stations = Station.query.filter(Station.id.in_(list(station_updates.keys()))).all()
    by_id = {station.id: station for station in stations}
    print("Примеры Station:")
    for station_id in list(sorted(station_updates.keys()))[:10]:
        station = by_id.get(station_id)
        if not station:
            continue
        district_name = getattr(getattr(station, "regional_district", None), "name", None)
        print(
            f"  Station id={station.id} db_ver={station.database_version_id} "
            f"name={station.name!r} region={district_name!r}"
        )
        print(f"    old: {(station.external_code or '').strip()}")
        print(f"    new: {station_updates[station_id]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Исправление коллизий Station.external_code с учетом субъекта РФ."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план изменений, без записи в БД",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Не запрашивать подтверждение перед записью",
    )
    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="Пересчитать external_code у всех станций по текущей формуле (после смены ключа)",
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Дополнительно: пример строк «Центральная ТЭЦ» и сводка по ref_uuid (почему может быть 0)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        _print_db_target()
        if args.diagnose:
            _print_diagnose()
        sql_multi_ref_groups = _count_sql_multi_ref_external_codes()
        (
            station_updates,
            collision_groups,
            unresolved_within_same_key,
            sql_bad_from_rows,
        ) = _build_station_update_plan_sql(sync_all=args.sync_all)
        machine_updates = _build_machine_update_plan(station_updates)
        equipment_group_updates, non_import_groups, ambiguous_groups = _build_equipment_group_update_plan(
            station_updates
        )

        print("=" * 80)
        print("Исправление legacy-коллизий Station.external_code")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        if args.sync_all:
            print("[SYNC-ALL] Будет пересчитан external_code у всех станций по текущей формуле ключа")
        print(
            "Контроль SQL: число external_code, у которых несколько разных ref_uuid субъекта: "
            f"{sql_multi_ref_groups}"
        )
        print(
            "Тот же критерий по загруженным строкам stations (должно совпадать с числом выше): "
            f"{sql_bad_from_rows}"
        )
        print(f"Групп-коллизий по Station.external_code: {len(collision_groups)}")
        print(f"Station к обновлению: {len(station_updates)}")
        print(f"Machine к обновлению: {len(machine_updates)}")
        print(f"EquipmentGroup к обновлению: {len(equipment_group_updates)}")
        print(f"EquipmentGroup пропущено как не-импортные: {len(non_import_groups)}")
        print(f"EquipmentGroup пропущено как неоднозначные: {len(ambiguous_groups)}")
        print(f"Неустраненные коллизии в пределах одной semantic key: {len(unresolved_within_same_key)}")
        print()

        if not station_updates:
            print("Коллизии, требующие исправления, не найдены.")
            if sql_multi_ref_groups == 0 and sql_bad_from_rows == 0:
                print(
                    "Подсказка: в этой базе нет одного и того же external_code на разные субъекты "
                    "(или вы подключены не к той БД, что в pgAdmin — сверьте host/database выше)."
                )
            return

        _print_station_examples(station_updates)

        if non_import_groups:
            print()
            print("Примеры пропущенных не-импортных EquipmentGroup:")
            for row in non_import_groups[:5]:
                print(
                    f"  EquipmentGroup id={row['equipment_group_id']} "
                    f"stations={row['station_ids']} current={row['current_code']}"
                )

        if ambiguous_groups:
            print()
            print("Примеры неоднозначных EquipmentGroup:")
            for row in ambiguous_groups[:5]:
                print(
                    f"  EquipmentGroup id={row['equipment_group_id']} "
                    f"stations={row['station_ids']} candidates={row['candidate_codes']}"
                )

        if unresolved_within_same_key:
            print()
            print("Внимание: найдены потенциальные дубликаты в пределах одной semantic key:")
            for row in unresolved_within_same_key[:5]:
                print(
                    f"  target={row['target_external_code']} versions={row['versions']}"
                )

        if args.dry_run:
            print()
            print("Dry-run завершен.")
            return

        if not args.yes:
            confirm = input("\nПрименить изменения? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Отменено.")
                return

        try:
            if station_updates:
                for station in Station.query.filter(Station.id.in_(list(station_updates.keys()))).all():
                    station.external_code = station_updates[station.id]

            if machine_updates:
                for machine in Machine.query.filter(Machine.id.in_(list(machine_updates.keys()))).all():
                    machine.external_code = machine_updates[machine.id]

            if equipment_group_updates:
                for group in EquipmentGroup.query.filter(EquipmentGroup.id.in_(list(equipment_group_updates.keys()))).all():
                    group.external_code = equipment_group_updates[group.id]

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        print()
        print(f"Обновлено Station: {len(station_updates)}")
        print(f"Обновлено Machine: {len(machine_updates)}")
        print(f"Обновлено EquipmentGroup: {len(equipment_group_updates)}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
