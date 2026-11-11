from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _format_sheet(sheet, header_rows, rounding_digits):
    number_format = "General" if rounding_digits == 0 else "0" + ("." + "0" * rounding_digits if rounding_digits > 0 else "")
    for row in sheet:
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
            elif isinstance(cell.value, (Decimal, float)):
                cell.number_format = number_format
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if cell.row <= header_rows:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="D1E7DD")
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in range(1, header_rows + 1):
        sheet.row_dimensions[row].height = 48 if row == 1 and header_rows == 2 else 30
    for column in range(1, sheet.max_column + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 18


def export_territory_technologies(context):
    book = Workbook()
    book.properties.title = "Технологии и МСК + МДП"
    book.properties.subject = f"Версия БД {context['version_id']}"
    if context["sheet"] == "technologies":
        sheet = book.active
        sheet.title = "Технологии"
        for column, label in enumerate(("ЭЗ", "Название технологии", "Тип №"), 1):
            sheet.cell(1, column, label)
            sheet.merge_cells(start_row=1, start_column=column, end_row=2, end_column=column)
        column = 4
        groups = context["technology_header_groups"]
        for index, (label, subheaders) in enumerate(groups):
            if index == len(groups) - 1 and context["year_features"].get(2042):
                label += "\n" + context["year_features"][2042]
            sheet.cell(1, column, label)
            if subheaders:
                sheet.merge_cells(start_row=1, start_column=column, end_row=1,
                                  end_column=column + len(subheaders) - 1)
                for offset, subheader in enumerate(subheaders):
                    sheet.cell(2, column + offset, subheader)
            else:
                sheet.merge_cells(start_row=1, start_column=column, end_row=2, end_column=column)
            column += len(subheaders) or 1
        for row in context["rows"]:
            sheet.append([row.energy_zone.number, row.name, row.technology_number,
                          *[getattr(row, field) for field, _ in context["columns"]]])
        _format_sheet(sheet, 2, context["rounding_digits"])
        sheet.column_dimensions["B"].width = 35
        sheet.freeze_panes = "D3"
    else:
        paths = book.active
        paths.title = "Матрица путей"
        zones, sections = context["matrix_zones"], context["sections"]
        paths.append(["ЭЗ / сечение", *[row.name for row in sections]])
        for zone in zones:
            paths.append([zone.number, *[row.zone_paths.get(zone.number) for row in sections]])
        if sections:
            paths.append(["ПР", *[row.forward_limit for row in sections]])
            paths.append(["ОБР", *[-row.reverse_limit for row in sections]])
        membership = book.create_sheet("Матрица МСК и МДП")
        membership.append(["Сечение / ЭЗ", *[zone.number for zone in zones], "ПР", "ОБР"])
        for row in sections:
            membership.append([row.name, *[row.zone_membership.get(zone.number) for zone in zones],
                               row.forward_limit, row.reverse_limit])
        for sheet in (paths, membership):
            _format_sheet(sheet, 1, context["rounding_digits"])
            sheet.column_dimensions["A"].width = 30
            sheet.freeze_panes = "B2"
    stream = BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    return stream
