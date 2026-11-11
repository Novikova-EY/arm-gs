from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.worksheet import Worksheet

from app.common.services.excel_numeric_cell import parse_excel_numeric
from app.fuel.services.fuel_imports.excel_import_helpers import normalize_import_column_name
from app.rational_structure.services.technical_characteristic_columns import ALL_COLUMNS, HEADER_FIELDS, SHEET_TYPES


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip() or None


def _headers(sheet: Worksheet) -> tuple[int, dict[int, str], dict[int, str]]:
    header_row = None
    for row in sheet.iter_rows(max_row=min(sheet.max_row, 30)):
        names = {normalize_import_column_name(cell.value): cell.column for cell in row}
        if "код_оборудования" in names and "год_предоставления_отчетности" in names:
            header_row = row[0].row
            code_column = names["код_оборудования"]
            year_column = names["год_предоставления_отчетности"]
            break
    if header_row is None:
        raise ValueError(f"Лист «{sheet.title}»: не найдены код оборудования и год отчетности.")

    merged = [area for area in sheet.merged_cells.ranges if area.min_row <= header_row + 4 and area.max_row >= header_row]
    header_end = max([header_row] + [area.max_row for area in merged if area.min_row <= header_row])
    while header_end < min(sheet.max_row, header_row + 5):
        next_row = list(sheet.iter_rows(min_row=header_end + 1, max_row=header_end + 1))[0]
        if next_row[code_column - 1].value is not None or next_row[year_column - 1].value is not None:
            break
        if any(isinstance(cell.value, (int, float)) for cell in next_row):
            break
        header_end += 1

    fields, extras = {}, {}
    for column in range(1, sheet.max_column + 1):
        parts = []
        for row_number in range(header_row, header_end + 1):
            value = sheet.cell(row_number, column).value
            if value is None:
                for area in merged:
                    if area.min_row <= row_number <= area.max_row and area.min_col <= column <= area.max_col:
                        value = sheet.cell(area.min_row, area.min_col).value
                        break
            part = " ".join(str(value).split()) if value is not None else ""
            if part and part not in parts:
                parts.append(part)
        if not parts:
            continue
        label = " / ".join(parts)
        field = HEADER_FIELDS.get(normalize_import_column_name(label))
        if field is None:
            field = HEADER_FIELDS.get(normalize_import_column_name(parts[-1]))
        if field:
            if field in fields.values():
                raise ValueError(f"Лист «{sheet.title}»: неоднозначный столбец «{label}».")
            fields[column] = field
        else:
            if label in extras.values():
                raise ValueError(f"Лист «{sheet.title}»: повторяется заголовок «{label}».")
            extras[column] = label
    return header_end, fields, extras


def read_technical_characteristics(raw: bytes, report_year: int | None = None) -> list[dict]:
    """Читает все годы; report_year оставлен для совместимости существующих вызовов."""
    try:
        workbook = load_workbook(BytesIO(raw), data_only=False)
    except (BadZipFile, InvalidFileException, ParseError, OSError, KeyError) as exc:
        raise ValueError("Не удалось прочитать книгу .xlsx. Проверьте формат файла.") from exc
    try:
        sheets = {normalize_import_column_name(name): name for name in workbook.sheetnames}
        available = {name: kind for name, kind in SHEET_TYPES.items()
                     if normalize_import_column_name(name) in sheets}
        if not available:
            raise ValueError("В книге отсутствуют листы оборудования: " + ", ".join(SHEET_TYPES))
        turbine_sheets = {name for name, kind in SHEET_TYPES.items() if kind in ("steam", "gas")}
        missing = turbine_sheets - available.keys()
        if missing and turbine_sheets.intersection(available):
            raise ValueError("В книге отсутствуют листы: " + ", ".join(sorted(missing)))
        records, seen = [], set()
        kinds = {attr: kind for attr, _, kind in ALL_COLUMNS}
        for sheet_name, turbine_type in available.items():
            sheet = workbook[sheets[normalize_import_column_name(sheet_name)]]
            header_end, fields, extras = _headers(sheet)
            year_column = next(column for column, field in fields.items() if field == "report_year")
            for cells in sheet.iter_rows(min_row=header_end + 1):
                if all(cell.value is None for cell in cells):
                    continue
                year_cell = cells[year_column - 1]
                year = parse_excel_numeric(year_cell.value)
                if year is None or not year.is_integer() or not 1900 <= year <= 2200:
                    raise ValueError(f"Лист «{sheet.title}», {year_cell.coordinate}: некорректный год отчетности.")
                record = {"turbine_type": turbine_type, "extra_values": {}}
                for cell in cells:
                    value = cell.value
                    field = fields.get(cell.column)
                    if field is None and cell.column not in extras:
                        if value is not None:
                            raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: у данных нет заголовка.")
                        continue
                    if cell.data_type in ("f", "e"):
                        raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: замените формулы и ошибки значениями.")
                    if field is None:
                        record["extra_values"][extras[cell.column]] = _text(value)
                        continue
                    kind = kinds[field]
                    if kind == "text":
                        record[field] = _text(value)
                        continue
                    if _text(value) in (None, "-", "–"):
                        record[field] = None
                        continue
                    number = parse_excel_numeric(value)
                    if number is None or (kind == "integer" and not number.is_integer()):
                        raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: ожидается число, получено «{value}».")
                    record[field] = int(number) if kind == "integer" else Decimal(str(number))
                code, year = record.get("equipment_code"), record.get("report_year")
                if not code or len(code) > 100 or year is None or not 1900 <= year <= 2200:
                    raise ValueError(f"Лист «{sheet.title}», строка {cells[0].row}: некорректный код оборудования или год отчетности.")
                key = (turbine_type, code, year)
                if key in seen:
                    raise ValueError(f"Лист «{sheet.title}», строка {cells[0].row}: повтор кода {code} за {year} год.")
                seen.add(key)
                records.append(record)
        if not records:
            raise ValueError("На листах оборудования нет данных. Данные не загружены.")
        return records
    finally:
        workbook.close()
