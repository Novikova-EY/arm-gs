from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_territory_inputs(context):
    book = Workbook()
    sheet = book.active
    sheet.title = "Исходные данные"
    zone = context["selected_zone"]
    sheet.append(['ЕЭС России' if context.get('is_ees') else f"Энергозона {zone.number}: {zone.name}"])
    sheet.append(["№ п/п", "Показатель", "Единица измерения", *context["years"], "Примечание"])
    sheet.sheet_properties.outlinePr.summaryBelow = False
    rows = list(context['rows'])
    if context.get('export_equipment_check'):
        rows.extend(context.get('equipment_verification_rows', []))
    for row in rows:
        sheet.append([row["number"], row["label"], row["unit"],
                      *[Decimal(value) if value != "" else None for value in row["cells"]], row["note"]])
        # Названия из справочников и примечания выгружаются текстом, а не формулами Excel.
        sheet.cell(sheet.max_row, 2).data_type = "s"
        sheet.cell(sheet.max_row, len(context["years"]) + 4).data_type = "s"
        if row.get('equipment_parent'):
            sheet.row_dimensions[sheet.max_row].outlineLevel = 1
        if row["section"] or row.get('equipment_rollup'):
            for cell in sheet[sheet.max_row]:
                cell.fill = PatternFill("solid", fgColor="EFF7FF" if row.get("subsection") else "DCE6F1")
                cell.font = Font(bold=True)
        if row.get('equipment_verification'):
            for index, error in enumerate(row['verification_errors'], 4):
                if error:
                    cell = sheet.cell(sheet.max_row, index)
                    cell.fill = PatternFill('solid', fgColor='F8D7DA')
                    cell.font = Font(color='DC3545', bold=True)
    for row in sheet.iter_rows(min_row=3, min_col=4, max_col=len(context["years"]) + 3):
        for cell in row:
            cell.number_format = "0.########"
    for row in sheet:
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.column_dimensions["A"].width = 9
    sheet.column_dimensions["B"].width = 65
    sheet.column_dimensions["C"].width = 20
    for column in range(4, len(context["years"]) + 5):
        sheet.column_dimensions[get_column_letter(column)].width = 18
    sheet.freeze_panes = "D3"
    stream = BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    return stream
