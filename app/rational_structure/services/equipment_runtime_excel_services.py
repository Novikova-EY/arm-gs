import hashlib
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ERROR_CODES
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.services.calculation_workbook_services import load_calculation_context
from app.rational_structure.services.equipment_runtime_columns import runtime_columns
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook


def import_equipment_runtime(raw, version_id, filename, username):
    """Архивирует книгу прототипа; расчет страницы не использует сохраненные значения."""
    context = load_calculation_context(version_id, "equipment_runtime")
    if context["version"] is None:
        raise ValueError("Выберите версию базы данных перед загрузкой.")
    data = read_equipment_runtime_workbook(raw)
    workbook = context["workbook"]
    if workbook is None:
        workbook = CalculationWorkbook(database_version_id=version_id, kind="equipment_runtime", created_by=username)
        db.session.add(workbook)
    workbook.data = data
    workbook.source_filename = filename
    workbook.source_sha256 = hashlib.sha256(raw).hexdigest()
    db.session.commit()
    return len(data["calculation"]["rows"])


def export_equipment_runtime(context):
    """Экспорт всех отфильтрованных строк, без ограничения текущей страницей."""
    book = Workbook(write_only=True)
    for key, name in (("calculation", "Расчет"), ("summary", "Лист2")):
        sheet = book.create_sheet(name)
        columns = (runtime_columns(context["general_scheme_end_year"]) if key == "calculation"
                   else context["summary_table"]["columns"])
        rows = context["filtered_rows"] if key == context["sheet"] else (
            context["calculation_rows"] if key == "calculation" else context["summary_table"]["rows"])
        header_row = 1 if key == "calculation" else 2
        if header_row == 2:
            sheet.append([])
        sheet.freeze_panes = f"B{header_row + 1}"
        headers = []
        for column in columns:
            cell = WriteOnlyCell(sheet, value=column["label"])
            cell.data_type = "s"
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor=column.get("highlight_color") or "D1E7DD")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
            headers.append(cell)
        sheet.append(headers)
        for row in rows:
            cells = []
            for column in columns:
                value = row["values"].get(column["key"])
                cell = WriteOnlyCell(sheet, value=value)
                if isinstance(value, str):
                    cell.data_type = "s"
                if column.get("highlight_color"):
                    cell.fill = PatternFill("solid", fgColor=column["highlight_color"])
                if column["key"] in row["errors"]:
                    if value in ERROR_CODES:
                        cell.data_type = "e"
                    cell.fill = PatternFill("solid", fgColor="FFF3CD")
                cells.append(cell)
            sheet.append(cells)
        if columns:
            sheet.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{header_row + len(rows)}"
    stream = BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    return stream
