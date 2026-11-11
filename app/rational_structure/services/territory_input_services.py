import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.common.services.help_services import parse_decimal_from_display
from app.extensions import db
from app.rational_structure.models.territory_input_model import TerritoryInput
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone


TERRITORY_DISCOUNT_RATE_ROW_KEY = "24"
TERRITORY_LINKED_ROW_KEYS = frozenset(str(index) for index in (*range(6), 7, 9, 24))
TERRITORY_STATION_POWER_LABELS = {
    'ГЭС': ('ГЭС до 50 МВт', 'ГЭС более 50 МВт'),
    'ВЭС': ('ВЭС',),
    'СЭС': ('СЭС',),
    'ГАЭС': ('ГАЭС',),
    'СНЭЭ': ('СНЭЭ',),
}

TERRITORY_INPUT_SHEETS = {
    "years": "Показатели по годам",
    "equipment": "Состав генерирующего оборудования",
}


@lru_cache(maxsize=1)
def territory_template():
    with Path(__file__).with_name("territory_input_template.json").open(encoding="utf-8") as source:
        return json.load(source)


@lru_cache(maxsize=1)
def territory_thermal_row_keys():
    keys = set()
    thermal = False
    for index, row in enumerate(territory_template()['rows']):
        if row['label'] == 'агрегаты КЭС до 90 МВт (газ)':
            thermal = True
        if thermal:
            keys.add(str(index))
        if row['label'] == 'прочие':
            thermal = False
    return frozenset(keys)


@lru_cache(maxsize=1)
def territory_nuclear_row_keys():
    keys = set()
    nuclear = False
    for index, row in enumerate(territory_template()['rows']):
        if row['label'] == 'РБМК-1000, ВВЭР-1000':
            nuclear = True
        if nuclear:
            keys.add(str(index))
        if row['label'] == 'прочее':
            nuclear = False
    return frozenset(keys)


@lru_cache(maxsize=1)
def territory_station_power_row_keys():
    labels = {label for group in TERRITORY_STATION_POWER_LABELS.values() for label in group}
    keys = set()
    block = 0
    for index, row in enumerate(territory_template()['rows']):
        if str(row['number']).strip() == '18':
            block += 1
        # В шаблоне состав после мероприятий идет первым, исходный состав – вторым.
        if block in (1, 2) and row['label'] in labels:
            keys.add(str(index))
    return frozenset(keys)


@lru_cache(maxsize=1)
def territory_calculated_equipment_row_keys():
    totals = {str(index) for index, row in enumerate(territory_template()['rows'])
              if str(row['number']).strip() == '18'}
    return totals | territory_thermal_row_keys() | territory_nuclear_row_keys() | territory_station_power_row_keys()


def build_territory_input_context(version_id, zone_id, sheet="years"):
    if sheet not in TERRITORY_INPUT_SHEETS:
        raise ValueError("Неизвестная вкладка исходных данных.")
    zones = [] if version_id is None else list(db.session.scalars(
        select(EnergyZone).where(EnergyZone.database_version_id == version_id)
        .order_by(EnergyZone.number, EnergyZone.name)
    ))
    zones.sort(key=lambda zone: (0, int(zone.number)) if zone.number.isdigit() else (1, zone.number))
    if zone_id == 0:
        contexts = [build_territory_input_context(version_id, zone.id, sheet) for zone in zones if zone.id > 0]
        years = sorted({year for context in contexts for year in context['years']}) or territory_template()['years']
        return dict(version_id=version_id, zones=zones, selected_zone=None, is_ees=True,
                    zone_contexts=contexts, rows=sum_territory_rows(contexts, years), all_rows=[],
                    sheet=sheet, input_sheets=TERRITORY_INPUT_SHEETS, years=years, updated_at=None)
    if zone_id is not None:
        zone = next((item for item in zones if item.id == zone_id), None)
        if zone is None:
            raise ValueError("Энергозона не найдена в текущей версии БД.")
    else:
        zone = zones[0] if zones else None
    record = None if zone is None else db.session.scalar(select(TerritoryInput).where(
        TerritoryInput.database_version_id == version_id, TerritoryInput.energy_zone_id == zone.id,
    ))
    template = territory_template()
    years = record.years if record else template["years"]
    source_rows = record.rows if record else template["rows"]
    rows = []
    all_rows = []
    equipment_block = False
    for index, source in enumerate(source_rows):
        if str(source["number"]).strip():
            equipment_block = str(source["number"]).strip() == "18"
        # У некоторых итоговых строк Excel нет единицы, но есть годовые значения.
        section = not source["unit"] and all(value is None for value in source["values"])
        row = dict(source, key=str(index), section=section,
                   cells=[str(value) if value is not None else "" for value in source["values"]])
        all_rows.append(row)
        if equipment_block == (sheet == "equipment"):
            rows.append(row)
    return dict(version_id=version_id, zones=zones, selected_zone=zone, rows=rows, all_rows=all_rows,
                is_ees=False, sheet=sheet, input_sheets=TERRITORY_INPUT_SHEETS,
                years=years, updated_at=record.updated_at if record else None)


def sum_territory_rows(contexts, years):
    """Суммируем одноименные строки по годам, сохраняя пустые значения и точность."""
    templates = {}
    values = []
    for context in contexts:
        zone_values = {}
        values.append(zone_values)
        for row in context['rows']:
            if row.get('parent_key'):
                continue
            key = row['key']
            templates.setdefault(key, row)
            zone_values[key] = dict(zip(context['years'], row['cells']))
    result = []
    has_gaes = '0_with_gaes' in templates
    for key, template in templates.items():
        cells = []
        for year in years:
            numbers = []
            for zone_values in values:
                source = zone_values.get(key)
                if source is None and key == '0_with_gaes':
                    source = zone_values.get('0')
                raw = (source or {}).get(year, '')
                if raw != '':
                    numbers.append(Decimal(raw))
            cells.append(str(sum(numbers, Decimal(0))) if numbers else '')
        row = dict(template, cells=cells, note='', readonly=True, collapsible=False,
                   section=template['section'] and not any(value != '' for value in cells),
                   formula='Сумма значений по всем энергозонам.' if not template['section'] else '')
        if has_gaes and key == '0':
            row.update(number='1.1', label='Годовое потребление электрической энергии без ГАЭС')
        result.append(row)
    # Виртуальная строка с ГАЭС может впервые встретиться не в первой энергозоне.
    if has_gaes:
        gaes = next(row for row in result if row['key'] == '0_with_gaes')
        result.remove(gaes)
        result.insert(next(index for index, row in enumerate(result) if row['key'] == '0') + 1, gaes)
    return result


def parse_territory_value(raw):
    if not isinstance(raw, str) or len(raw) > 100:
        raise ValueError("Введите число длиной не более 100 символов.")
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = parse_decimal_from_display(raw)
    except InvalidOperation:
        value = None
    if value is None or not value.is_finite() or value.copy_abs() >= Decimal("1e16"):
        raise ValueError("Введите число (конечное, по модулю меньше 10¹⁶).")
    return str(value)


def save_territory_inputs(context, form, username):
    if context["selected_zone"] is None:
        raise ValueError("Выберите энергозону.")
    if form.get("database_version_id") != str(context["version_id"]):
        raise ValueError("Версия БД изменилась. Обновите страницу перед сохранением.")
    saved_rows = []
    visible_keys = {row["key"] for row in context["rows"]}
    for row in context["all_rows"]:
        saved_row = {key: row[key] for key in ("number", "label", "unit", "note", "section")}
        saved_row["values"] = list(row["values"])
        saved_rows.append(saved_row)
        if row["section"] or row["key"] not in visible_keys or row["key"] == TERRITORY_DISCOUNT_RATE_ROW_KEY:
            continue
        values = list(row["values"])
        if row["key"] not in TERRITORY_LINKED_ROW_KEYS | territory_calculated_equipment_row_keys():
            values = []
            for year in context["years"]:
                name = f"value_{row['key']}_{year}"
                if name not in form:
                    raise ValueError("Получена неполная таблица. Обновите страницу и повторите сохранение.")
                raw = form[name].strip()
                if not raw:
                    values.append(None)
                    continue
                try:
                    value = parse_territory_value(raw)
                except ValueError as exc:
                    raise ValueError(f"{row['label']}, {year}: введите число.") from exc
                values.append(value)
        note = form.get(f"note_{row['key']}", "").strip()
        if len(note) > 2000:
            raise ValueError(f"{row['label']}: примечание длиннее 2000 символов.")
        saved_row["note"] = note
        saved_row["values"] = values
    zone = context["selected_zone"]
    record = db.session.scalar(select(TerritoryInput).where(
        TerritoryInput.database_version_id == context["version_id"], TerritoryInput.energy_zone_id == zone.id,
    ))
    if record is None:
        record = TerritoryInput(database_version_id=context["version_id"], energy_zone_id=zone.id,
                                source_filename="Исходные данные по территориям.xlsx", created_by=username)
        db.session.add(record)
    record.years = list(context["years"])
    record.rows = saved_rows
    record.modified_by = username
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
