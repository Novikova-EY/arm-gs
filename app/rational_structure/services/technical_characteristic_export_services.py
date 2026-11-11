from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.utils import get_column_letter

from app.extensions import db


def export_technical_characteristics(context: dict) -> BytesIO:
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Технические характеристики")
    sheet.freeze_panes = "B2"
    # turbine_type and equipment_kind removed from table
    columns = context["columns"]
    labels = [label for _, label, _ in columns] + context["extra_labels"]

    def append(values):
        cells = []
        for value in values:
            cell = WriteOnlyCell(sheet, value=value)
            if isinstance(value, str):
                cell.data_type = "s"
            cells.append(cell)
        sheet.append(cells)

    append(labels)
    count = 1
    for row in db.session.scalars(context["statement"].execution_options(yield_per=500)):
        append([
            *(getattr(row, attr) for attr, _, _ in columns),
            *(row.extra_values.get(label) for label in context["extra_labels"]),
        ])
        count += 1
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(labels))}{count}"
    stream = BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    return stream
