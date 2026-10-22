# -*- coding: utf-8 -*-
r"""Постанционная сверка «Руст» ЕЭС/ТЭС за 2024 год с выгрузкой в Excel.

Запуск:
    $env:PYTHONPATH = (Get-Location).Path
    .venv\Scripts\python.exe scripts\compare_fuel_generation_rust_2024.py 2024

Лист «Станции ЕЭС ТЭС» содержит станции, входящие в генерационную сводку ЕЭС/ТЭС.
Топливная группа относится к станции только при единственной действующей связи; группы
с нулём или несколькими связанными станциями вынесены в лист деталей, чтобы не
приписывать/не удваивать их мощность произвольно.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from sqlalchemy import and_, func, or_

from app import create_app
from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    resolve_composite_parents_by_numb,
    territorial_ids_for_equipment_group,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType

ZERO = Decimal(0)


def dec(value) -> Decimal:
    return ZERO if value is None else Decimal(value)


def fuel_version_match():
    return or_(
        and_(
            EquipmentGroupFuelParam.database_version_id
            == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )


def load_station_scope(version_id: int | None, year: int) -> dict[int, dict]:
    stations: dict[int, dict] = {}
    for station in Station.query.filter(Station.database_version_id == version_id).all():
        station_type = station.station_type.name if station.station_type else ""
        energy_system_type = station.energy_system_type or ""
        if station_type != "ТЭС" or "ЕЭС" not in energy_system_type.upper():
            continue
        stations[station.id] = {
            "station_id": station.id,
            "station_name": station.name or "",
            "station_type": station_type,
            "energy_system_type": energy_system_type,
            "fuel_active": ZERO,
            "fuel_zero": ZERO,
            "fuel_parent_zero": ZERO,
            "active_rows": 0,
            "zero_rows": 0,
            "parent_rows": 0,
            "group_ids": set(),
            "numbs": set(),
            "generation": ZERO,
            "machines_with_year_power": 0,
            "machines_without_year_power": 0,
        }

    generation_rows = (
        db.session.query(
            Machine.id_station,
            func.count(MachinePower.id),
            func.sum(MachinePower.p_ust),
        )
        .select_from(MachinePower)
        .join(Machine, Machine.id == MachinePower.id_machine)
        .filter(
            Machine.database_version_id == version_id,
            Machine.is_archived.isnot(True),
            MachinePower.year_number == year,
            or_(
                MachinePower.database_version_id == version_id,
                MachinePower.database_version_id.is_(None),
            ),
        )
        .group_by(Machine.id_station)
        .all()
    )
    for station_id, count, total in generation_rows:
        if station_id in stations:
            stations[station_id]["machines_with_year_power"] = int(count or 0)
            stations[station_id]["generation"] = dec(total)

    machine_counts = (
        db.session.query(Machine.id_station, func.count(Machine.id))
        .filter(
            Machine.database_version_id == version_id,
            Machine.is_archived.isnot(True),
        )
        .group_by(Machine.id_station)
        .all()
    )
    for station_id, count in machine_counts:
        if station_id in stations:
            info = stations[station_id]
            info["machines_without_year_power"] = int(count or 0) - info["machines_with_year_power"]
    return stations


def load_fuel_rows(year: int, version_id: int | None):
    rows = (
        db.session.query(EquipmentGroup, EquipmentGroupFuelParam)
        .select_from(EquipmentGroupFuelParam)
        .join(
            EquipmentGroup,
            and_(
                EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
                fuel_version_match(),
            ),
        )
        .filter(
            EquipmentGroupFuelParam.year_number == year,
            EquipmentGroup.database_version_id == version_id,
        )
        .all()
    )
    return rows, resolve_composite_parents_by_numb(rows, database_version_id=version_id)


def load_group_station_links(version_id: int | None) -> dict[int, dict[int, dict]]:
    rows = (
        db.session.query(
            EquipmentGroupSet.equipment_group_id,
            Station,
            StationType.name,
        )
        .select_from(EquipmentGroupSet)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
        )
        .join(Station, Station.id == EquipmentGroupSetStation.station_id)
        .outerjoin(StationType, StationType.id == Station.id_station_type)
        .filter(
            EquipmentGroupSetStation.database_version_id == version_id,
            Station.database_version_id == version_id,
        )
        .all()
    )
    links: dict[int, dict[int, dict]] = defaultdict(dict)
    for group_id, station, station_type in rows:
        links[group_id][station.id] = {
            "name": station.name or "",
            "station_type": station_type or "",
            "est": station.energy_system_type or "",
        }
    return links


def fuel_row_values(year: int, version_id: int | None, stations: dict[int, dict]):
    rows, parents = load_fuel_rows(year, version_id)
    links = load_group_station_links(version_id)
    fuel_details = []
    ees_summary = {"active": ZERO, "zero": ZERO, "rows_active": 0, "rows_zero": 0}

    for eg, param in rows:
        est_id, _ues_id, _res_id = territorial_ids_for_equipment_group(eg, parents)
        if est_id != 207:  # ЕЭС России; тот же текущий справочник, что на странице.
            continue
        active = fuel_param_row_participates(param)
        value = dec(param.nust)
        if active:
            ees_summary["active"] += value
            ees_summary["rows_active"] += 1
        else:
            ees_summary["zero"] += value
            ees_summary["rows_zero"] += 1

        group_links = links.get(eg.id, {})
        link_ids = sorted(group_links)
        if len(link_ids) == 0:
            disposition = "Нет связи с электростанцией"
            station_id = None
        elif len(link_ids) > 1:
            disposition = "Неоднозначная связь: несколько станций"
            station_id = None
        else:
            station_id = link_ids[0]
            target = stations.get(station_id)
            if target is None:
                disposition = "Связанная станция вне среза ЕЭС/ТЭС"
                station_id = None
            else:
                disposition = "Однозначно связана с ЕЭС/ТЭС"
                target["group_ids"].add(eg.id)
                if eg.numb is not None:
                    target["numbs"].add(int(eg.numb))
                if active:
                    target["fuel_active"] += value
                    target["active_rows"] += 1
                else:
                    target["fuel_zero"] += value
                    target["zero_rows"] += 1
                    if int(eg.comp or 0) == 1 and int(eg.main or 0) == 0:
                        target["fuel_parent_zero"] += value
                        target["parent_rows"] += 1

        station_labels = [
            f"{sid}: {group_links[sid]['name']} [{group_links[sid]['station_type']}; {group_links[sid]['est']}]"
            for sid in link_ids
        ]
        fuel_details.append({
            "group_id": eg.id,
            "numb": eg.numb,
            "name": eg.name_ext or eg.name or "",
            "comp": eg.comp,
            "main": eg.main,
            "ved": param.ved,
            "nust": value,
            "participates": active,
            "est_id": est_id,
            "links_count": len(link_ids),
            "station_id": station_id,
            "station_links": "\n".join(station_labels),
            "disposition": disposition,
        })

    return fuel_details, ees_summary


def write_workbook(path: Path, year: int, version_id: int | None, stations: dict[int, dict], fuel_details: list[dict], ees_fuel: dict):
    import xlsxwriter

    workbook = xlsxwriter.Workbook(str(path))
    header = workbook.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "text_wrap": True, "valign": "vcenter"})
    title = workbook.add_format({"bold": True, "font_size": 14})
    note = workbook.add_format({"text_wrap": True, "valign": "top"})
    text = workbook.add_format({"border": 1, "valign": "top"})
    number = workbook.add_format({"border": 1, "num_format": "#,##0.000"})
    difference = workbook.add_format({"border": 1, "num_format": "#,##0.000", "bg_color": "#FCE4D6"})
    percent = workbook.add_format({"border": 1, "num_format": "0.00%"})
    bold = workbook.add_format({"bold": True, "border": 1})
    bold_number = workbook.add_format({"bold": True, "border": 1, "num_format": "#,##0.000"})

    station_list = sorted(stations.values(), key=lambda s: s["station_name"].casefold())
    gen_total = sum((s["generation"] for s in station_list), ZERO)
    mapped_active = sum((s["fuel_active"] for s in station_list), ZERO)
    mapped_zero = sum((s["fuel_zero"] for s in station_list), ZERO)
    mapped_all = mapped_active + mapped_zero
    active_coverage = sum(bool(s["active_rows"]) for s in station_list)
    no_fuel = sum(not s["group_ids"] for s in station_list)
    zero_gen = sum(s["generation"] == 0 for s in station_list)

    summary = workbook.add_worksheet("Итоги")
    summary.set_column(0, 0, 54)
    summary.set_column(1, 1, 22)
    summary.set_column(2, 2, 94)
    summary.write(0, 0, "Постанционная сверка «Руст» – ЕЭС/ТЭС", title)
    summary.write(1, 0, f"Год: {year}; версия БД: {version_id}")
    summary.write_row(3, 0, ["Показатель", "Значение", "Комментарий"], header)
    summary_rows = [
        ("Генерация: сумма p_ust по ЕЭС/ТЭС, МВт", gen_total, "Неархивные агрегаты, привязанные к станциям текущей версии; проверено по агрегации страницы generation/totals_summary."),
        ("Топливо: официальный итог ЕЭС, только ved>0, МВт", ees_fuel["active"], "Сумма NUST всех групп ЕЭС, как в fuel/totals_summary; страница не ограничивает итог типом станции ТЭС."),
        ("Топливо: официальный итог ЕЭС, все ved, МВт", ees_fuel["active"] + ees_fuel["zero"], "Диагностическая сумма: добавляет ved<=0/NULL; потенциально включает родителя вместе с дочерними группами."),
        ("Топливо ЕЭС: строки ved<=0/NULL, МВт", ees_fuel["zero"], "Не участвуют в официальной сводке. Требуют отдельной проверки на составных станциях."),
        ("Станции ЕЭС/ТЭС", len(station_list), "Постанционный список совпадает по границам с категорией ЕЭС/ТЭС генерационной сводки."),
        ("ЕЭС/ТЭС без связанной топливной группы", no_fuel, "По текущим связям EquipmentGroup -> EquipmentGroupSet -> EquipmentGroupSetStation -> Station."),
        ("ЕЭС/ТЭС с Руст генерации = 0 за год", zero_gen, "Станция может иметь агрегаты, но без записи MachinePower за выбранный год."),
        ("Топливо, однозначно привязанное к ЕЭС/ТЭС: ved>0, МВт", mapped_active, "Только группы ЕЭС с единственной связью на станцию из среза ЕЭС/ТЭС. Общие/непривязанные группы вынесены отдельно."),
        ("Топливо, однозначно привязанное к ЕЭС/ТЭС: все ved, МВт", mapped_all, "Сумма привязанных ved>0 и ved<=0/NULL; не эквивалентна официальному итогу из-за возможных родительских оболочек."),
        ("Расхождение поколения и привязанного топлива ved>0, МВт", gen_total - mapped_active, "Генерация минус только однозначно распределённые активные топливные группы."),
        ("Официальный fuel ЕЭС ved>0 минус однозначно привязанный ЕЭС/ТЭС, МВт", ees_fuel["active"] - mapped_active, "Группы без привязки, с неоднозначной привязкой или привязанные не к станции ЕЭС/ТЭС."),
    ]
    for row_index, (label, value, comment) in enumerate(summary_rows, start=4):
        summary.write(row_index, 0, label, text)
        summary.write_number(row_index, 1, float(value), number) if isinstance(value, Decimal) else summary.write_number(row_index, 1, value, text)
        summary.write(row_index, 2, comment, note)
    summary.write(16, 0, "Сопоставление страниц", header)
    summary.merge_range(17, 0, 18, 2, "На генерационной странице можно сравнить ЕЭС → ТЭС. На топливной странице итог ЕЭС включает все участвующие группы ЕЭС и не имеет фильтра типа станции, поэтому официальный итог топлива не является строгой суммой именно ТЭС.\n\nДля станций топливная группа учитывается только при единственной действующей связи. Неоднозначные связи не распределяются автоматически.", note)
    summary.freeze_panes(4, 0)

    sheet = workbook.add_worksheet("Станции ЕЭС ТЭС")
    columns = [
        ("station_id", "ID станции"), ("station_name", "Электростанция"),
        ("generation", "Руст генерации p_ust, МВт"),
        ("fuel_active", "Руст топлива nust (ved>0), МВт"),
        ("fuel_zero", "Руст топлива nust (ved<=0/NULL), МВт"),
        ("fuel_all", "Топливо, все строки, МВт"),
        ("delta_active", "Генерация − топливо ved>0, МВт"),
        ("delta_active_pct", "Разница, % от генерации"),
        ("delta_all", "Генерация − топливо (все строки), МВт"),
        ("active_rows", "Строк ved>0"), ("zero_rows", "Строк ved<=0/NULL"),
        ("parent_zero", "Родительские ved=0, МВт"),
        ("group_ids", "ID топливных групп"), ("numbs", "NUMB групп"),
        ("machines_with_year_power", "Агрегатов с мощностью за год"),
        ("machines_without_year_power", "Агрегатов без мощности за год"),
    ]
    sheet.write_row(0, 0, [col[1] for col in columns], header)
    sheet.freeze_panes(1, 2)
    sheet.autofilter(0, 0, len(station_list), len(columns) - 1)
    sheet.set_column(0, 0, 12)
    sheet.set_column(1, 1, 43)
    sheet.set_column(2, 8, 19)
    sheet.set_column(9, 11, 16)
    sheet.set_column(12, 13, 24)
    sheet.set_column(14, 15, 22)

    for row_index, station in enumerate(station_list, start=1):
        generation = station["generation"]
        fuel_active = station["fuel_active"]
        fuel_zero = station["fuel_zero"]
        values = {
            "station_id": station["station_id"],
            "station_name": station["station_name"],
            "generation": generation,
            "fuel_active": fuel_active,
            "fuel_zero": fuel_zero,
            "fuel_all": fuel_active + fuel_zero,
            "delta_active": generation - fuel_active,
            "delta_active_pct": (generation - fuel_active) / generation if generation else None,
            "delta_all": generation - fuel_active - fuel_zero,
            "active_rows": station["active_rows"],
            "zero_rows": station["zero_rows"],
            "parent_zero": station["fuel_parent_zero"],
            "group_ids": ", ".join(map(str, sorted(station["group_ids"]))),
            "numbs": ", ".join(map(str, sorted(station["numbs"]))),
            "machines_with_year_power": station["machines_with_year_power"],
            "machines_without_year_power": station["machines_without_year_power"],
        }
        for col_index, (key, _label) in enumerate(columns):
            value = values[key]
            if isinstance(value, Decimal):
                fmt = difference if key in {"delta_active", "delta_all"} and value != 0 else number
                sheet.write_number(row_index, col_index, float(value), fmt)
            elif key == "delta_active_pct":
                if value is None:
                    sheet.write_blank(row_index, col_index, None, text)
                else:
                    sheet.write_number(row_index, col_index, float(value), percent)
            else:
                sheet.write(row_index, col_index, value, text)

    total_row = len(station_list) + 1
    sheet.write(total_row, 1, "ИТОГО ЕЭС/ТЭС", bold)
    for col_index, value in (
        (2, gen_total),
        (3, mapped_active),
        (4, mapped_zero),
        (5, mapped_all),
        (6, gen_total - mapped_active),
        (8, gen_total - mapped_all),
    ):
        sheet.write_number(total_row, col_index, float(value), bold_number)
    sheet.write_number(
        total_row, 7,
        float((gen_total - mapped_active) / gen_total) if gen_total else 0.0,
        percent,
    )

    group_sheet = workbook.add_worksheet("Группы ЕЭС – детализация")
    group_headers = ["ID группы", "NUMB", "Название группы", "COMP", "MAIN", "VED", "NUST, МВт", "Участвует в сводке", "Кол-во связанных станций", "Связанные станции", "Статус привязки"]
    group_sheet.write_row(0, 0, group_headers, header)
    group_sheet.freeze_panes(1, 2)
    group_sheet.autofilter(0, 0, len(fuel_details), len(group_headers) - 1)
    group_sheet.set_column(0, 1, 12)
    group_sheet.set_column(2, 2, 52)
    group_sheet.set_column(3, 7, 17)
    group_sheet.set_column(8, 8, 24)
    group_sheet.set_column(9, 9, 86)
    group_sheet.set_column(10, 10, 40)
    for row_index, item in enumerate(fuel_details, start=1):
        group_sheet.write_row(row_index, 0, [
            item["group_id"], item["numb"], item["name"], item["comp"], item["main"],
            item["ved"], float(item["nust"]), "Да" if item["participates"] else "Нет",
            item["links_count"], item["station_links"], item["disposition"],
        ], text)
        group_sheet.write_number(row_index, 6, float(item["nust"]), number)
        if item["links_count"] > 1:
            group_sheet.set_row(row_index, 36)

    method = workbook.add_worksheet("Методика")
    method.set_column(0, 0, 38)
    method.set_column(1, 1, 110)
    method.write_row(0, 0, ["Аспект", "Правило / замечание"], header)
    method_rows = [
        ("Год / версия", f"{year} / {version_id}"),
        ("Срез генерации", "Station.energy_system_type содержит ЕЭС, тип станции ТЭС; сумма MachinePower.p_ust по Machine.is_archived != true."),
        ("Срез топливного итога", "Топливные строки текущей версии, текущий год; распределение по ЕЭС через territorial_ids_for_equipment_group, как в fuel/totals_summary."),
        ("Официальный фильтр топлива", "В расчёт входит FuelParam.ved > 0. Строки с ved <= 0 или NULL показаны отдельно и не добавляются в официальный итог."),
        ("Постанционная связь", "EquipmentGroup → EquipmentGroupSet → EquipmentGroupSetStation → Station. Учитываются только текущая версия станции и связи текущей версии."),
        ("Несколько станций у одной группы", "Такая группа не включена в постанционную сумму; её ссылки и мощность остаются на листе детализации. Иначе мощность группы задваивалась бы."),
        ("Группы вне ЕЭС/ТЭС", "Остаются в официальном топливном итоге ЕЭС, но не приписываются станциям на листе ЕЭС/ТЭС."),
        ("Составные станции", "Родитель comp=1/main=0 и дочерние группы показаны раздельно. Нельзя считать все строки одновременно без проверки, иначе возможен двойной счёт."),
        ("Округление", "Суммы сохранены с точностью до 0,001 МВт; внутри БД используются исходные Decimal значения."),
    ]
    for row_index, (label, detail) in enumerate(method_rows, start=1):
        method.write(row_index, 0, label, text)
        method.write(row_index, 1, detail, note)
        method.set_row(row_index, 38)

    workbook.close()


def main() -> None:
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
    app = create_app()
    with app.app_context():
        version_id = get_current_db_version_id()
        stations = load_station_scope(version_id, year)
        fuel_details, ees_fuel = fuel_row_values(year, version_id, stations)
        output = Path(__file__).resolve().parents[1] / "exports" / f"fuel_generation_rust_reconciliation_{year}.xlsx"
        output.parent.mkdir(parents=True, exist_ok=True)
        write_workbook(output, year, version_id, stations, fuel_details, ees_fuel)

        gen_total = sum((s["generation"] for s in stations.values()), ZERO)
        mapped_active = sum((s["fuel_active"] for s in stations.values()), ZERO)
        mapped_zero = sum((s["fuel_zero"] for s in stations.values()), ZERO)
        print(f"version={version_id} year={year} EES_TES_stations={len(stations)}")
        print(f"generation_EES_TES={gen_total}")
        print(f"fuel_EES_active={ees_fuel['active']} fuel_EES_all={ees_fuel['active'] + ees_fuel['zero']}")
        print(f"fuel_uniquely_linked_EES_TES_active={mapped_active} all={mapped_active + mapped_zero}")
        print(f"written: {output}")


if __name__ == "__main__":
    main()
