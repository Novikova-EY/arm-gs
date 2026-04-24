#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Разделение общих EquipmentGroup между выбранными станциями.

Сценарий нужен для исправления ситуации, когда одна и та же итоговая группа
оборудования (EquipmentGroup) оказалась связана сразу с несколькими станциями.
Это приводит к тому, что субъект/РЭС и карточка группы "скачут" между станциями.

Что делает:
1. Находит EquipmentGroup, которые среди указанных station_id привязаны более чем
   к одной станции.
2. Оставляет исходную группу за одной "хозяйской" станцией.
3. Для остальных станций создает клон группы, копирует в него дочерние записи
   (FuelParam / ExtraFuelParam / SpecificFuel* / FuelFormula / CoefficientResult)
   и переназначает соответствующий EquipmentGroupSet на клон.
4. Пересчитывает regional_district_id / regional_energy_system_id через
   EquipmentGroup._populate_regional_ids().
5. Обновляет external_code под текущую импортную формулу, чтобы следующий импорт
   не создавал новые дубли по старым кодам.

Запуск:
    python scripts/split_shared_equipment_groups_between_stations.py --station-ids 6455 7487 --dry-run
    python scripts/split_shared_equipment_groups_between_stations.py --station-ids 6455 7487 --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, select

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_coefficient_result_model import (
    EquipmentGroupCoefficientResult,
)
from app.fuel.services.fuel_imports.import_fuel_db_equipment_groups_services import (
    _generate_stable_external_code_equipment_group,
)
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from config import SCHEMA_FUEL, SCHEMA_GENERATION


DETAIL_MODELS = [
    EquipmentGroupFuelParam,
    EquipmentGroupExtraFuelParam,
    EquipmentGroupSpecificFuelConsumption,
    EquipmentGroupSpecificFuelCost,
    EquipmentGroupSpecificFuelPrice,
    EquipmentGroupFuelFormula,
    EquipmentGroupCoefficientResult,
]


def _table_exists(model) -> bool:
    inspector = inspect(db.engine)
    table = model.__table__
    return inspector.has_table(table.name, schema=table.schema)


def _print_db_target() -> None:
    url = db.engine.url
    print("Целевая БД (должна совпадать с подключением в pgAdmin):")
    print(f"  driver:   {url.drivername}")
    print(f"  host:     {url.host}")
    print(f"  port:     {url.port}")
    print(f"  database: {url.database}")
    print(f"  user:     {url.username}")
    print(f"  stations: {SCHEMA_GENERATION}.gs_gen_stations")
    print(f"  groups:   {SCHEMA_FUEL}.gs_fue_equipment_groups")
    print()


def _group_link_entries(group_id: int) -> list[dict]:
    rows = (
        db.session.query(EquipmentGroupSet, EquipmentGroupSetStation, Station, EquipmentGroupType)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .join(EquipmentGroupType, EquipmentGroupType.id == EquipmentGroupSetStation.equipment_group_type_id)
        .filter(EquipmentGroupSet.equipment_group_id == group_id)
        .order_by(Station.id.asc(), EquipmentGroupSetStation.equipment_group_type_id.asc())
        .all()
    )
    result = []
    for set_v2, link, station, group_type in rows:
        result.append(
            {
                "set_id": set_v2.id,
                "link_id": link.id,
                "station_id": station.id,
                "station_name": station.name,
                "station_external_code": station.external_code,
                "station_rd_id": station.id_regional_district,
                "station_res_id": station.id_regional_energy_system,
                "group_type_id": group_type.id,
                "group_type_name": group_type.name,
                "group_type_ref_uuid": getattr(group_type, "ref_uuid", None),
                "version_id": link.database_version_id,
            }
        )
    return result


def _target_external_code(group: EquipmentGroup, entry: dict) -> str:
    type_key = entry["group_type_ref_uuid"] or entry["group_type_name"] or str(entry["group_type_id"])
    return _generate_stable_external_code_equipment_group(
        (entry["station_external_code"] or "").strip(),
        type_key,
        group.numb,
    )


def _choose_owner_entry(group: EquipmentGroup, entries: list[dict]) -> tuple[dict, str]:
    exact = [
        entry
        for entry in entries
        if entry["station_rd_id"] == group.regional_district_id
        and entry["station_res_id"] == group.regional_energy_system_id
    ]
    if len(exact) == 1:
        return exact[0], "точное совпадение по субъекту и РЭС"

    rd_only = [
        entry for entry in entries
        if group.regional_district_id is not None
        and entry["station_rd_id"] == group.regional_district_id
    ]
    if len(rd_only) == 1:
        return rd_only[0], "совпадение по субъекту"

    res_only = [
        entry for entry in entries
        if group.regional_energy_system_id is not None
        and entry["station_res_id"] == group.regional_energy_system_id
    ]
    if len(res_only) == 1:
        return res_only[0], "совпадение по РЭС"

    return sorted(entries, key=lambda item: (item["station_id"], item["group_type_id"]))[0], "fallback по минимальному station_id"


def _build_group_clone(source: EquipmentGroup, *, external_code: str) -> EquipmentGroup:
    skip = {"id", "external_code", "created_at", "updated_at"}
    values = {}
    for column in EquipmentGroup.__table__.columns:
        if column.name in skip:
            continue
        values[column.name] = getattr(source, column.name)
    clone = EquipmentGroup(**values)
    clone.external_code = external_code
    db.session.add(clone)
    db.session.flush()
    return clone


def _copy_detail_rows(model, source_group_id: int, target_group_id: int) -> int:
    table = model.__table__
    rows = db.session.execute(
        select(table).where(table.c.equipment_group_id == source_group_id)
    ).all()
    inserted = 0
    for row in rows:
        data = dict(row._mapping)
        data.pop("id", None)
        data.pop("created_at", None)
        data.pop("updated_at", None)
        data.pop("version", None)
        data["equipment_group_id"] = target_group_id
        db.session.execute(table.insert().values(**data))
        inserted += 1
    return inserted


def _group_by_station(entries: list[dict]) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for entry in entries:
        grouped[entry["station_id"]].append(entry)
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Разделение общих EquipmentGroup между выбранными станциями."
    )
    parser.add_argument(
        "--station-ids",
        nargs="+",
        type=int,
        required=True,
        help="Список station_id, между которыми ищем склеенные EquipmentGroup",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать план, без изменений в БД",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение перед применением",
    )
    args = parser.parse_args()

    target_station_ids = sorted(set(args.station_ids))
    if len(target_station_ids) < 2:
        raise SystemExit("Нужно передать как минимум два station_id в --station-ids")

    app = create_app()
    with app.app_context():
        _print_db_target()

        available_detail_models = [model for model in DETAIL_MODELS if _table_exists(model)]

        shared_group_ids = []
        all_group_ids = (
            db.session.query(EquipmentGroupSet.equipment_group_id)
            .join(
                EquipmentGroupSetStation,
                EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
            )
            .filter(EquipmentGroupSetStation.station_id.in_(target_station_ids))
            .distinct()
            .all()
        )
        for (group_id,) in all_group_ids:
            entries = _group_link_entries(group_id)
            station_ids_for_group = {
                entry["station_id"] for entry in entries if entry["station_id"] in target_station_ids
            }
            if len(station_ids_for_group) > 1:
                shared_group_ids.append(group_id)

        if not shared_group_ids:
            print("Общих EquipmentGroup между указанными станциями не найдено.")
            return

        print("=" * 90)
        print("Разделение общих EquipmentGroup между станциями")
        print("=" * 90)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Станции: {target_station_ids}")
        print(f"Найдено общих групп: {len(shared_group_ids)}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        if not args.dry_run and not args.yes:
            confirm = input("Продолжить разделение групп? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Отменено.")
                return

        total_clones = 0
        total_sets_reassigned = 0
        total_detail_rows_copied = 0
        total_groups_updated = 0

        for group_id in sorted(shared_group_ids):
            group = EquipmentGroup.query.get(group_id)
            if not group:
                continue

            entries = [entry for entry in _group_link_entries(group_id) if entry["station_id"] in target_station_ids]
            by_station = _group_by_station(entries)
            if len(by_station) <= 1:
                continue

            owner_entry, owner_reason = _choose_owner_entry(group, entries)
            print(
                f"EquipmentGroup id={group.id} name={group.name!r} numb={group.numb} "
                f"-> владелец station_id={owner_entry['station_id']} ({owner_reason})"
            )
            for entry in entries:
                marker = "KEEP" if entry["set_id"] == owner_entry["set_id"] else "CLONE"
                print(
                    f"  [{marker}] set_id={entry['set_id']} station_id={entry['station_id']} "
                    f"type_id={entry['group_type_id']} version={entry['version_id']} "
                    f"target_external_code={_target_external_code(group, entry)}"
                )

            if args.dry_run:
                for model in available_detail_models:
                    table = model.__table__
                    rows_count = db.session.execute(
                        select(table.c.id).where(table.c.equipment_group_id == group.id)
                    ).all()
                    if rows_count:
                        print(f"    copy {table.name}: {len(rows_count)} rows per clone")
                print()
                continue

            owner_target_external_code = _target_external_code(group, owner_entry)
            if group.external_code != owner_target_external_code:
                group.external_code = owner_target_external_code
                total_groups_updated += 1

            for entry in entries:
                if entry["set_id"] == owner_entry["set_id"]:
                    continue

                clone_external_code = _target_external_code(group, entry)
                existing = EquipmentGroup.query.filter(
                    EquipmentGroup.external_code == clone_external_code,
                    EquipmentGroup.database_version_id == group.database_version_id,
                ).first()
                if existing and existing.id != group.id:
                    raise RuntimeError(
                        "Найден existing EquipmentGroup с target external_code="
                        f"{clone_external_code} (id={existing.id}) для station_id={entry['station_id']}. "
                        "Сценарий не знает, как безопасно объединить его автоматически."
                    )

                clone = _build_group_clone(group, external_code=clone_external_code)
                total_clones += 1

                for model in available_detail_models:
                    copied = _copy_detail_rows(model, group.id, clone.id)
                    total_detail_rows_copied += copied

                set_v2 = EquipmentGroupSet.query.get(entry["set_id"])
                set_v2.equipment_group_id = clone.id
                db.session.add(set_v2)
                clone._populate_regional_ids()
                total_sets_reassigned += 1
                total_groups_updated += 1

            group._populate_regional_ids()
            db.session.add(group)

            print()

        if args.dry_run:
            print(f"[DRY-RUN] Будет создано клонов групп: {total_clones or 'по 1 на каждую строку CLONE выше'}")
            print("[DRY-RUN] Для применения запустите скрипт без --dry-run и с --yes.")
            return

        db.session.commit()
        print()
        print(f"Создано клонов EquipmentGroup: {total_clones}")
        print(f"Переназначено EquipmentGroupSet: {total_sets_reassigned}")
        print(f"Скопировано detail rows: {total_detail_rows_copied}")
        print(f"Обновлено EquipmentGroup (external_code/region): {total_groups_updated}")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
