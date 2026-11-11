from datetime import date, datetime
from io import BytesIO
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from werkzeug.exceptions import BadRequest

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.rational_structure.models.calculation_workbook_model import CalculationWorkbook


def open_calculation_workbook(raw, *, data_only):
    try:
        return load_workbook(BytesIO(raw), data_only=data_only, read_only=True, keep_links=False)
    except (BadZipFile, InvalidFileException, ParseError, OSError, KeyError) as exc:
        raise ValueError("Не удалось прочитать расчетную книгу .xlsx.") from exc


def read_calculation_table(sheet, formulas, *, header_row, start_row, end_column, required_column,
                           labels=None, integer_columns=(), text_columns=(), carry_columns=()):
    headers = next(sheet.iter_rows(min_row=header_row, max_row=header_row, max_col=end_column, values_only=True))
    columns = []
    for index, value in enumerate(headers, 1):
        key = get_column_letter(index)
        label = (labels or {}).get(key, value)
        columns.append({"key": key, "label": str(label).strip() if label is not None else key,
                        "integer": key in integer_columns, "text": key in text_columns})
    rows, carried = [], {}
    values_iter = sheet.iter_rows(min_row=start_row, max_col=end_column)
    formulas_iter = formulas.iter_rows(min_row=start_row, max_col=end_column)
    for number, (values, formula_cells) in enumerate(zip(values_iter, formulas_iter), start_row):
        if values[required_column - 1].value in (None, ""):
            continue
        row = {"source_row": number, "values": {}, "formulas": {}, "errors": []}
        for column, cell, formula_cell in zip(columns, values, formula_cells):
            key, value = column["key"], cell.value
            if key in carry_columns:
                if value is not None:
                    carried[key] = value
                value = carried.get(key)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            if column["text"] and value is not None:
                value = str(value)
            row["values"][key] = value
            if formula_cell.data_type == "f":
                row["formulas"][key] = formula_cell.value
                # Excel хранит результат формулы "" как пустую ячейку типа str.
                if value is None and cell.data_type != "str":
                    row["errors"].append(key)
            if cell.data_type == "e":
                row["errors"].append(key)
        rows.append(row)
    # Не показываем полностью пустые технические столбцы Excel.
    columns = [column for column in columns if any(
        row["values"][column["key"]] is not None or column["key"] in row["formulas"] for row in rows)]
    return {"name": sheet.title, "columns": columns, "rows": rows,
            "error_count": sum(len(row["errors"]) for row in rows)}


def load_calculation_context(version_id, kind):
    version = db.session.get(DatabaseVersion, version_id) if version_id is not None else None
    workbook = db.session.scalar(select(CalculationWorkbook).where(
        CalculationWorkbook.database_version_id == version_id, CalculationWorkbook.kind == kind)) if version else None
    return {"version": version, "version_id": version_id, "workbook": workbook}


def calculation_rounding(args, *, default=3, param="rounding_digits"):
    digits = args.get(param, default, type=int)
    return digits if digits in (-1, 0, 1, 2, 3, 6) else default


def require_choice(value, choices, label):
    if value and value not in choices:
        raise BadRequest(f"Некорректное значение фильтра «{label}».")
