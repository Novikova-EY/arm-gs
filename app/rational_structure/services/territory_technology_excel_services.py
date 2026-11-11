from functools import partial
from io import BytesIO
from zipfile import BadZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.common.services.excel_numeric_cell import parse_excel_numeric
from app.rational_structure.services.territory_technology_columns import TECHNOLOGY_COLUMNS


def _number(cell, sheet, *, cached_book, required=False, integer=False, binary=False):
    raw = cell.value
    if cell.data_type == "f":
        raw = cached_book[sheet.title][cell.coordinate].value
        if raw is None:
            raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: у формулы нет сохраненного результата. Пересчитайте и сохраните книгу в Excel.")
    if raw in (None, "") and not required:
        return None
    value = parse_excel_numeric(raw)
    if value is None or cell.data_type == "e":
        raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: ожидается число.")
    if integer and (not value.is_integer() or value < 1):
        raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: ожидается положительный целый номер.")
    if binary and value not in (0, 1):
        raise ValueError(f"Лист «{sheet.title}», {cell.coordinate}: ожидается 0 или 1.")
    return int(value) if integer or binary else value


def read_territory_inputs(raw):
    try:
        book = load_workbook(BytesIO(raw), data_only=False)
        cached_book = load_workbook(BytesIO(raw), data_only=True)
    except (BadZipFile, InvalidFileException, ParseError, OSError, KeyError) as exc:
        raise ValueError("Не удалось прочитать книгу .xlsx.") from exc
    number = partial(_number, cached_book=cached_book)
    try:
        if not {"Технологии", "МСК + МДП"}.issubset(book.sheetnames):
            raise ValueError("В книге нужны листы «Технологии» и «МСК + МДП».")
        sheet = book["Технологии"]
        if sheet["A1"].value != "Тип" or sheet["C1"].value != "ЭЗ":
            raise ValueError("Лист «Технологии»: структура столбцов не соответствует шаблону.")
        technologies, seen = [], set()
        for row in sheet.iter_rows(min_row=4, max_col=23):
            # Ниже основной таблицы находятся вспомогательные списки в U:W.
            if all(cell.value is None for cell in row[:3]):
                continue
            name = str(row[0].value or "").strip()
            if not name or row[0].data_type in ("f", "e"):
                raise ValueError(f"Лист «Технологии», A{row[0].row}: не задано название технологии.")
            zone = str(number(row[2], sheet, required=True, integer=True))
            key = (zone, name)
            if key in seen:
                raise ValueError(f"Повтор технологии «{name}» в энергозоне {zone}.")
            seen.add(key)
            record = {"name": name, "zone_number": zone, "source_row": row[0].row,
                      "technology_number": number(row[1], sheet, required=True, integer=True)}
            record.update({field: number(cell, sheet) for (field, _), cell in zip(TECHNOLOGY_COLUMNS, row[3:23])})
            technologies.append(record)
        if not technologies:
            raise ValueError("Лист «Технологии» не содержит данных.")

        sheet = book["МСК + МДП"]
        zone_columns = {}
        for col in range(17, 30):
            zone = str(number(sheet.cell(1, col), sheet, required=True, integer=True))
            if zone in zone_columns:
                raise ValueError(f"Лист «МСК + МДП»: повтор энергозоны {zone}.")
            zone_columns[zone] = col
        path_rows = {}
        for row in range(2, 15):
            zone = str(number(sheet.cell(row, 1), sheet, required=True, integer=True))
            if zone in path_rows:
                raise ValueError(f"Лист «МСК + МДП»: повтор строки энергозоны {zone}.")
            path_rows[zone] = row
        if path_rows.keys() != zone_columns.keys():
            raise ValueError("Лист «МСК + МДП»: номера энергозон в матрицах не совпадают.")
        sections, names = [], set()
        for row in range(2, 15):
            name = str(sheet.cell(row, 16).value or "").strip()
            path_col = row
            if not name or name != sheet.cell(1, path_col).value or name in names:
                raise ValueError(f"Лист «МСК + МДП», строка {row}: названия сечений не совпадают или повторяются.")
            names.add(name)
            sections.append({
                "name": name, "source_row": row,
                "zone_membership": {zone: number(sheet.cell(row, col), sheet, required=True, binary=True)
                                    for zone, col in zone_columns.items()},
                "zone_paths": {zone: number(sheet.cell(r, path_col), sheet, required=True, binary=True)
                               for zone, r in path_rows.items()},
                "forward_limit": number(sheet.cell(row, 32), sheet, required=True),
                "reverse_limit": number(sheet.cell(row, 33), sheet, required=True),
            })
        return technologies, sections
    finally:
        book.close()
        cached_book.close()
