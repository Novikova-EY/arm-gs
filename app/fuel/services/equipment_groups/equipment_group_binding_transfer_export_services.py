"""Excel export of the displayed preview, without reloading or changing bindings."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


REPORT_COLUMNS = (
    ("key", "Ключ строки", 20),
    ("station", "Станция", 35),
    ("equipment", "Агрегат / связь", 35),
    ("current_group", "Сейчас в текущей версии", 45),
    ("source_group", "Из источника", 45),
    ("current_group_external_code", "external_code группы – текущая версия", 42),
    ("source_group_external_code", "external_code группы – источник", 42),
    ("current_type_ref_uuid", "ref_uuid типа – текущая версия", 42),
    ("source_type_ref_uuid", "ref_uuid типа – источник", 42),
    ("current_station_link", "Связь со станцией – текущая версия", 65),
    ("source_station_link", "Связь со станцией – источник", 65),
    ("reason", "Результат анализа", 75),
)
STATUS_LABELS = {"ready": "Можно перенести", "conflict": "Замена", "blocked": "Нельзя перенести", "same": "Уже совпадает"}


def export_binding_transfer_report(report):
    if not isinstance(report, dict):
        raise ValueError("Отсутствуют данные отчета.")
    rows, selected = report.get("rows"), report.get("selected_keys")
    if (not isinstance(rows, list) or len(rows) > 50000 or not isinstance(selected, list)
            or any(not isinstance(key, str) for key in selected) or type(report.get("completed")) is not bool):
        raise ValueError("Некорректные строки или параметры отчета.")
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("status"), str) or row["status"] not in STATUS_LABELS
                or any(not isinstance(row.get(key), str) for key, _, _ in REPORT_COLUMNS)):
            raise ValueError("Некорректная строка отчета.")
    keys = [row["key"] for row in rows]
    if len(keys) != len(set(keys)) or not set(selected) <= set(keys):
        raise ValueError("Выбранные строки отсутствуют в отчете или дублируются ключи.")
    texts = [report.get("source"), report.get("target")] + [row[key] for row in rows for key, _, _ in REPORT_COLUMNS]
    if any(not isinstance(value, str) or len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value) for value in texts):
        raise ValueError("Текст отчета содержит недопустимые для Excel символы или превышает размер ячейки.")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Сопоставление связей"
    sheet.append(["Снимок предварительного анализа связей"])
    sheet.append(["Версия-источник", report["source"]])
    sheet.append(["Текущая версия", report["target"]])
    sheet.append(["Перенос выбранных строк завершен", "Да" if report["completed"] else "Нет"])
    sheet.append(["Выбрано", "Статус", *(title for _, title, _ in REPORT_COLUMNS)])
    selected = set(selected)
    fills = {"conflict": PatternFill("solid", fgColor="FFF3CD"), "blocked": PatternFill("solid", fgColor="E2E3E5")}
    for row in rows:
        sheet.append(["Да" if row["key"] in selected else "Нет", STATUS_LABELS[row["status"]],
                      *(row[key] for key, _, _ in REPORT_COLUMNS)])
        if row["status"] in fills:
            for cell in sheet[sheet.max_row]:
                cell.fill = fills[row["status"]]
    for cells in sheet:
        for cell in cells:
            # Identifiers and database names must never be interpreted as formulas.
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for cell in sheet[5]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D1E7DD")
    for index, width in enumerate([12, 24, *(width for _, _, width in REPORT_COLUMNS)], 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "D6"
    sheet.auto_filter.ref = f"A5:{get_column_letter(sheet.max_column)}{sheet.max_row}"
    sheet.print_title_rows = "1:5"
    sheet.page_setup.orientation = "landscape"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
