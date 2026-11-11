import hashlib
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.get_services.years.years_get_services import normalize_start_end_years
from app.extensions import db
from app.rational_structure.models.calculation_workbook_model import CalculationWorkbook
from app.rational_structure.services.marginal_price_matching_services import match_marginal_price_tables
from app.rational_structure.services.calculation_workbook_services import (
    calculation_rounding, load_calculation_context, open_calculation_workbook,
    read_calculation_table, require_choice,
)

ANNUAL_ENERGY_FORMULA = (
    'Годовая энергия = сумма значений «Энергия периода, млн кВт·ч» всех строк данной территории за один год. '
    'Суммируются исходные значения без округления; округление применяется только к результату на экране. '
    'Если энергия хотя бы одного периода отсутствует или содержит ошибку, годовая энергия не рассчитывается.'
)

TERRITORY_SHEETS = {
    "europe": "Европ.часть", "south": "Юг", "ural": "Урал", "siberia": "Сибирь", "east": "Восток",
}


def read_marginal_price_workbook(raw):
    values = open_calculation_workbook(raw, data_only=True)
    try:
        formulas = open_calculation_workbook(raw, data_only=False)
        try:
            if not set(TERRITORY_SHEETS.values()).issubset(values.sheetnames):
                raise ValueError("В книге замыкающей цены нужны листы: " + ", ".join(TERRITORY_SHEETS.values()))
            tables = {}
            for slug, name in TERRITORY_SHEETS.items():
                sheet = values[name]
                table = read_calculation_table(
                    sheet, formulas[name], header_row=4, start_row=5, end_column=26, required_column=2,
                    labels={"A": "Год", "C": "Цена 1 кВт·ч, руб.", "D": "Название станции",
                            "P": "Энергия периода, млн кВт·ч", "Q": "Годовая энергия, млн кВт·ч"},
                    integer_columns=("A", "B", "H", "I", "J"), text_columns=("D",), carry_columns=("A",),
                )
                table["title"] = sheet["A2"].value or name
                if not table["rows"]:
                    raise ValueError(f"Лист «{name}» не содержит расчетных периодов.")
                for row in table["rows"]:
                    year = row["values"]["A"]
                    if isinstance(year, bool) or not isinstance(year, (int, float)) or not 1900 <= year <= 2200 or int(year) != year:
                        raise ValueError(f"Лист «{name}», строка {row['source_row']}: укажите корректный расчетный год.")
                    for key, value in row['values'].items():
                        if isinstance(value, float):
                            # JSON не поддерживает Decimal; дроби храним десятичным текстом.
                            row['values'][key] = str(_price_decimal(value))
                tables[slug] = table
            return tables
        finally:
            formulas.close()
    finally:
        values.close()


def import_marginal_price_workbook(raw, version_id, username, filename):
    if version_id is None:
        raise ValueError("Выберите версию базы данных перед загрузкой.")
    if db.session.get(DatabaseVersion, version_id) is None:
        raise ValueError("Выбранная версия базы данных не найдена.")
    data = match_marginal_price_tables(read_marginal_price_workbook(raw), version_id)
    try:
        workbook = db.session.scalar(select(CalculationWorkbook).where(
            CalculationWorkbook.database_version_id == version_id,
            CalculationWorkbook.kind == "marginal_price",
        ).with_for_update())
        if workbook is None:
            workbook = CalculationWorkbook(database_version_id=version_id, kind="marginal_price",
                                           created_by=username)
            db.session.add(workbook)
        workbook.source_filename = filename
        workbook.source_sha256 = hashlib.sha256(raw).hexdigest()
        workbook.data = data
        workbook.modified_by = username
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return {"territories": len(data), "rows": sum(len(table["rows"]) for table in data.values()),
            "errors": sum(table["error_count"] for table in data.values())}


def _price_decimal(value):
    if isinstance(value, float):
        # Excel хранит 15 значащих цифр; более длинный хвост double не является данными.
        value = format(value, '.15g')
    try:
        number = parse_decimal_from_display(value)
    except InvalidOperation:
        return None
    return number if number is not None and number.is_finite() else None


def calculate_marginal_price_annual_energy(rows):
    decimal_rows = []
    for row in rows:
        values = dict(row['values'])
        for key, value in values.items():
            if key != 'D' and key not in row['errors'] and isinstance(value, (str, float)):
                number = _price_decimal(value)
                if number is not None:
                    values[key] = number
        decimal_rows.append({**row, 'values': values})
    rows = decimal_rows
    energy_by_year = defaultdict(list)
    for row in rows:
        value = None if 'P' in row['errors'] else _price_decimal(row['values'].get('P'))
        energy_by_year[int(row['values']['A'])].append(value)
    totals = {year: sum(values, Decimal(0)) if all(value is not None for value in values) else None
              for year, values in energy_by_year.items()}
    result = []
    for year, group in groupby(rows, key=lambda row: int(row['values']['A'])):
        year_rows = list(group)
        for index, row in enumerate(year_rows):
            result.append({**row, 'annual_energy': totals[year], 'annual_energy_error': totals[year] is None,
                           'annual_energy_rowspan': len(year_rows) if index == 0 else 0})
    return result


def build_marginal_price_context(args, version_id):
    context = load_calculation_context(version_id, "marginal_price")
    data = match_marginal_price_tables(context["workbook"].data, version_id) if context["workbook"] else {}
    territory = args.get("territory", "europe")
    require_choice(territory, TERRITORY_SHEETS, "Территория")
    table = data.get(territory, {"title": TERRITORY_SHEETS[territory], "columns": [], "rows": [], "error_count": 0})
    years = sorted({int(row["values"]["A"]) for row in table["rows"]})
    legacy_year = args.get("year") if "start_year" not in args and "end_year" not in args else None
    start = args.get("start_year") or legacy_year or (str(years[0]) if years else "")
    end = args.get("end_year") or legacy_year or (str(years[-1]) if years else "")
    choices = [str(value) for value in years]
    require_choice(start, choices, "Год начала")
    require_choice(end, choices, "Год конца")
    start_year, end_year = normalize_start_end_years(int(start), int(end)) if years else (None, None)
    rows = calculate_marginal_price_annual_energy([
        row for row in table["rows"] if start_year <= int(row["values"]["A"]) <= end_year
    ])
    price_rounding_digits = calculation_rounding(args, default=2, param="price_rounding_digits")
    columns = []
    for column in table["columns"]:
        if column["key"] == "A":
            continue
        if column["key"] == "C":
            columns.append({**column, "rounding_digits": price_rounding_digits})
        elif column["key"] == "D":
            columns.append({**column, "label": "Название группы оборудования"})
            columns.append({"key": "station", "label": "Название станции", "text": True, "integer": False})
        else:
            columns.append({**column, "formula_help": ANNUAL_ENERGY_FORMULA} if column["key"] == "Q" else column)
    if rows and not any(column["key"] == "Q" for column in columns):
        columns.append({"key": "Q", "label": "Годовая энергия, млн кВт·ч", "integer": False,
                        "text": False, "formula_help": ANNUAL_ENERGY_FORMULA})
    table = {**table, "columns": columns}
    context.update(table=table, rows=rows, total=len(rows), territories=TERRITORY_SHEETS,
                   territory=territory, years=years, start_year=start_year, end_year=end_year,
                   rounding_digits=calculation_rounding(args, default=-1),
                   price_rounding_digits=price_rounding_digits, active_calculation="marginal_price")
    return context
