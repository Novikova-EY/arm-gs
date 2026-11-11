import re
from decimal import Decimal

from openpyxl.utils import get_column_letter
from sqlalchemy import select

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.rational_structure.models import EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_machine_services import load_runtime_machine_rows
from app.rational_structure.services.equipment_runtime_summary_services import build_runtime_summary
from app.refdata.models.years.year_model import Year
from app.refdata.services.year_management_services import get_current_year_info, get_general_scheme_end_year
from config import END_YEAR, START_YEAR

from app.rational_structure.services.equipment_runtime_columns import RUNTIME_CHARACTERISTIC_FIELDS, runtime_columns
from app.rational_structure.services.calculation_workbook_services import (
    calculation_rounding, open_calculation_workbook,
    read_calculation_table, require_choice,
)


_PREVIOUS_RUNTIME_LABELS = {
    "AN": "Средняя наработка за три года, ч",
    "AO": "Остаток от двойного  ресурса",
    "AP": "Год демонтажа по ресурсу",
    "AQ": "Год достижения 1-ого ресурса",
    "AR": "Модернизация до 2043 года",
    "AS": "Перенос модернизации по СИПР",
    "AT": "Год демонтажа в СИПР/ КОММод",
    "AU": "Поставка по КОММод",
    "AV": "Год демонтажа под замену по КОММод",
    "AW": "Демонтаж угольных",
    "AX": "Демонтаж газовых",
    "AY": "Демонтаж ИТОГО",
    "AZ": "Перенос демонтажа по КОМ",
    "BA": "Перенос демонтажа по СИПРУ",
    "BC": "Уходим от дублирования с модернизацией",
    "BD": "Превысили два ресурса уголь",
    "BF": "Превысили два ресурса газ",
}


_RUNTIME_LABEL_ALIASES = {
    "AS": ("Год модернизации с учетом СиПР",),
    "BC": ("Плановый год демонтажа с учетом модернизации",),
}


def _matches_runtime_headers(headers, columns):
    return len(headers) == len(columns) and all(
        isinstance(header, str) and re.fullmatch(
            r"(?:Расчетный год модернизации|Модернизация) до [0-9]{4} года", header
        ) if column["key"] == "AR" else header in (column["label"], *_RUNTIME_LABEL_ALIASES.get(column["key"], ()))
        for header, column in zip(headers, columns)
    )


def read_equipment_runtime_workbook(raw):
    values = open_calculation_workbook(raw, data_only=True)
    try:
        formulas = open_calculation_workbook(raw, data_only=False)
        try:
            if not {"Расчет", "Лист2"}.issubset(values.sheetnames):
                raise ValueError("В книге наработки нужны листы «Расчет» и «Лист2».")
            exported_headers = [cell.value for cell in next(values["Расчет"].iter_rows(min_row=1, max_row=1))]
            export_columns = runtime_columns()
            compact_columns = [column for column in export_columns if column["key"] not in RUNTIME_CHARACTERISTIC_FIELDS]
            card_columns = [dict(column, key="planned_modernization_year", label="Плановый год модернизации")
                            if column["key"] == "AS" else column
                            for column in export_columns if column["key"] != "planned_modernization_year"]
            compact_card_columns = [column for column in card_columns if column["key"] not in RUNTIME_CHARACTERISTIC_FIELDS]
            old_columns = [dict(column, label=_PREVIOUS_RUNTIME_LABELS.get(column["key"], column["label"]))
                           for column in compact_columns if column["key"] != "planned_modernization_year"]
            previous_columns = old_columns + [
                {"key": "BK", "label": "Перенос модернизации по СИПР", "text": False, "integer": True},
                {"key": "BL", "label": "Уходим от дублирования", "text": False, "integer": True},
            ]
            legacy_columns = [dict(column, label="Технологии") if column["key"] == "K" else column
                              for column in previous_columns]
            legacy_columns.insert(3, {"key": "D", "label": "Год предоставления отчетности",
                                      "text": False, "integer": True})
            matched_columns = next((columns for columns in (export_columns, compact_columns, card_columns, compact_card_columns, old_columns, previous_columns, legacy_columns)
                                    if _matches_runtime_headers(exported_headers, columns)), None)
            is_table_export = matched_columns is not None
            if is_table_export:
                export_columns = matched_columns
            integer_columns = ("A", "D", "M", "V", "W", "X", "Y", "AA", "AC", "AF", "AH", "AJ",
                               "AP", "AQ", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ", "BA", "BC", "BK", "BL")
            text_columns = ("B", "C", "E", "F", "G", "H", "I", "J", "K", "L", "AD", "AG", "AI", "AK", "AL", "AM", "BB", "BD", "BF")
            if is_table_export:
                integer_columns = tuple(get_column_letter(i) for i, column in enumerate(export_columns, 1) if column["integer"])
                text_columns = tuple(get_column_letter(i) for i, column in enumerate(export_columns, 1) if column["text"])
            calculation = read_calculation_table(
                values["Расчет"], formulas["Расчет"], header_row=1, start_row=2,
                end_column=len(export_columns) if is_table_export else 64,
                required_column=next(i for i, column in enumerate(export_columns, 1) if column["key"] == "G") if is_table_export else 3,
                labels={"BE": "Превышение двух ресурсов уголь, лет", "BG": "Превышение двух ресурсов газ, ч / лет",
                        "BB": "Проверка переноса демонтажа (???)"},
                integer_columns=integer_columns, text_columns=text_columns,
            )
            if is_table_export:
                mapping = {get_column_letter(index): column["key"] for index, column in enumerate(export_columns, 1)}
                for row in calculation["rows"]:
                    row["values"] = {mapping[key]: value for key, value in row["values"].items() if key in mapping}
                    row["formulas"] = {mapping[key]: value for key, value in row["formulas"].items() if key in mapping}
                    row["errors"] = [mapping[key] for key in row["errors"] if key in mapping]
                calculation["columns"] = export_columns
                calculation["error_count"] = sum(len(row["errors"]) for row in calculation["rows"])
            summary = read_calculation_table(
                values["Лист2"], formulas["Лист2"], header_row=2, start_row=3,
                end_column=len(next(values["Лист2"].iter_rows(min_row=2, max_row=2))), required_column=2,
                labels={"A": "№", "B": "Показатель", "C": "Единица измерения"},
                integer_columns=("A",), text_columns=("B", "C"),
            )
            if not calculation["rows"]:
                raise ValueError("В книге нет строк расчета наработки оборудования.")
            return {"calculation": calculation, "summary": summary}
        finally:
            formulas.close()
    finally:
        values.close()


def runtime_filter_value(value):
    if value is None or value == "":
        return "__empty__"
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def build_equipment_runtime_context(args, version_id):
    version = db.session.get(DatabaseVersion, version_id) if version_id is not None else None
    context = {"version": version, "version_id": version_id, "workbook": None}
    sheet = args.get("sheet", "calculation")
    require_choice(sheet, ("calculation", "summary"), "Лист")
    data_years = set()
    reference_years = set()
    if version_id is not None:
        data_years.update(db.session.scalars(select(EquipmentTechnicalCharacteristic.report_year).where(
            EquipmentTechnicalCharacteristic.database_version_id == version_id)))
        reference_years.update(db.session.scalars(select(Year.number).where(Year.database_version_id == version_id)))
    year = args.get("year", type=int)
    if year is None or not 1900 <= year <= 2200:
        year = max(data_years) if data_years else START_YEAR
    years = sorted((reference_years or set(range(START_YEAR, END_YEAR + 1))) | data_years | {year})
    year_info = get_current_year_info(version_id) if version_id is not None else {}
    current_year = year_info.get("current_year")
    general_scheme_end_year = get_general_scheme_end_year(current_year)
    sipr_end_year = year_info.get("sipr_end") or None
    source_rows = load_runtime_machine_rows(version_id, year, general_scheme_end_year, sipr_end_year)
    zones = sorted({runtime_filter_value(row["values"]["A"]) for row in source_rows if row["values"].get("A") is not None},
                   key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
    zone = args.get("energy_zone", "")
    require_choice(zone, zones, "Энергозона")
    search = args.get("search", "").strip()
    filters = {key: args.get(key, "").strip() for key in ("subject", "station", "aggregate", "equipment_type")}
    rows = [row for row in source_rows if (not zone or runtime_filter_value(row["values"].get("A")) == zone)
            and (not search or any(search.casefold() in str(row["values"].get(key, "")).casefold()
                                   for key in ("B", "C", "F", "G", "H", "L")))]
    for param, keys in (("subject", ("F",)), ("station", ("G",)),
                        ("aggregate", ("H", "L")), ("equipment_type", ("E",))):
        if filters[param]:
            rows = [row for row in rows if any(filters[param].casefold() in
                    str(row["values"].get(key) or "").casefold() for key in keys)]
    runtime_rows = rows
    table = ({"name": "Расчет", "columns": runtime_columns(general_scheme_end_year), "rows": rows, "error_count": 0}
             if sheet == "calculation" else build_runtime_summary(rows, year, general_scheme_end_year))
    rows = table["rows"]
    header_columns, header_filter_args = [], {}
    for column in table["columns"]:
        param = "column_" + column["key"]
        selected = args.getlist(param)
        values = {runtime_filter_value(row["values"].get(column["key"])) for row in rows}
        header_columns.append(dict(column, param=param, selected=selected,
                                   options=[(value, "Пусто" if value == "__empty__" else value) for value in sorted(values | set(selected))]))
        if selected:
            header_filter_args[param] = selected
    for column in header_columns:
        if column["selected"]:
            rows = [row for row in rows if runtime_filter_value(row["values"].get(column["key"])) in column["selected"]]
    filtered_rows = rows
    summary_table = (build_runtime_summary(rows, year, general_scheme_end_year)
                     if sheet == "calculation" else table)
    visible_keys = {column["key"] for column in table["columns"]}
    table["error_count"] = sum(len(set(row["errors"]) & visible_keys) for row in rows)
    per_page = args.get("per_page", "50")
    if per_page not in ("10", "25", "50", "100", "all"):
        per_page = "50"
    total = len(rows)
    pages = max(1, (total + int(per_page) - 1) // int(per_page)) if per_page != "all" else 1
    page = min(max(args.get("page", 1, type=int), 1), pages)
    if per_page != "all":
        rows = rows[(page - 1) * int(per_page):page * int(per_page)]
    context.update(table=table, rows=rows, total=total, zones=zones, years=years, selected_zone=zone,
                   current_year=current_year, general_scheme_end_year=general_scheme_end_year, sipr_end_year=sipr_end_year,
                   selected_year=year, search=search, sheet=sheet, per_page=per_page, page=page, pages=pages,
                   rounding_digits=calculation_rounding(args, default=0), active_calculation="equipment_runtime",
                   filters=filters, header_columns=header_columns, header_filter_args=header_filter_args,
                   filtered_rows=filtered_rows, calculation_rows=runtime_rows, summary_table=summary_table,
                   current_page=page, total_pages=pages,
                   equipment_types=sorted({str(row["values"]["E"]) for row in source_rows if row["values"].get("E")}))
    return context
