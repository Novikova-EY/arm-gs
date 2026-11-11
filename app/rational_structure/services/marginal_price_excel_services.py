from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.cell import column_index_from_string

from app.rational_structure.services.marginal_price_services import (
    ANNUAL_ENERGY_FORMULA, TERRITORY_SHEETS, calculate_marginal_price_annual_energy,
)


def export_marginal_price_workbook(workbook):
    """Все территории и годы в формате, пригодном для повторного импорта."""
    book = Workbook()
    book.remove(book.active)
    book.properties.title = "Расчет замыкающей цены"
    for slug, name in TERRITORY_SHEETS.items():
        table = workbook.data[slug]
        sheet = book.create_sheet(name)
        sheet['A2'] = table['title']
        sheet['A2'].data_type = 's'
        sheet.freeze_panes = 'E5'
        for column in table['columns']:
            key = column['key']
            cell = sheet.cell(4, column_index_from_string(key), column['label'])
            cell.data_type = 's'
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='D1E7DD')
            cell.alignment = Alignment(wrap_text=True, vertical='center')
            sheet.column_dimensions[key].width = 38 if key == 'D' else 20
        sheet.row_dimensions[4].height = 90
        sheet['Q4'] = 'Годовая энергия, млн кВт·ч'
        sheet['Q4'].font = Font(bold=True)
        sheet['Q4'].fill = PatternFill('solid', fgColor='D1E7DD')
        sheet['Q4'].alignment = Alignment(wrap_text=True, horizontal='center', vertical='center')
        sheet['Q4'].comment = Comment(ANNUAL_ENERGY_FORMULA, 'АРМ ГС')
        for number, row in enumerate(calculate_marginal_price_annual_energy(table['rows']), 5):
            for key, value in row['values'].items():
                if key == 'Q':
                    continue
                cell = sheet.cell(number, column_index_from_string(key), value)
                if isinstance(value, (int, float, Decimal)):
                    cell.alignment = Alignment(horizontal='center', vertical='center')
                # Выгружаем сохраненные значения, не исполняя формулы и внешние ссылки.
                if isinstance(value, str) and cell.data_type != 'e':
                    cell.data_type = 's'
                if key in row['errors']:
                    cell.fill = PatternFill('solid', fgColor='FFF3CD')
            if row['annual_energy_rowspan']:
                cell = sheet.cell(number, 17, row['annual_energy'])
                cell.alignment = Alignment(horizontal='center', vertical='center')
                if row['annual_energy_error']:
                    cell.fill = PatternFill('solid', fgColor='FFF3CD')
                if row['annual_energy_rowspan'] > 1:
                    sheet.merge_cells(start_row=number, end_row=number + row['annual_energy_rowspan'] - 1,
                                      start_column=17, end_column=17)
        sheet.auto_filter.ref = f'A4:Z{4 + len(table["rows"])}'
    stream = BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    return stream
