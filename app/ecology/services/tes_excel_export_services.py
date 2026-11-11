"""Выгрузка расчетных вкладок ТЭС с последовательными годовыми блоками."""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.common.services.excel_numeric_cell import excel_number_format_trimmed, parse_excel_numeric
from app.ecology.services.calculation_summary_services import (
    CALCULATION_SUMMARY_TABS,
    build_calculation_summary_context,
)
from app.ecology.services.operating_tes_constants import CALC_SHEETS
from app.ecology.services.operating_tes_page_services import (
    build_operating_tes_table_context,
    coefficient_territory_slug,
    get_year_columns,
)

_HEADER_FILL = PatternFill('solid', fgColor='D1E7DD')


def build_tes_excel_stream(territory_slug, args, *, summary=False):
    builder = build_calculation_summary_context if summary else build_operating_tes_table_context
    tabs = CALCULATION_SUMMARY_TABS if summary else CALC_SHEETS
    years = get_year_columns(args.get('start_year'), args.get('end_year'))
    filters = {
        key: args.get(key)
        for key in ('rounding_digits', 'coefficient_rounding_digits', 'specific_rounding_digits')
    }
    if not summary:
        filters['affiliation'] = args.get('affiliation', 'all')
    workbook = Workbook()
    workbook.remove(workbook.active)
    for tab in tabs:
        worksheet = workbook.create_sheet(tab.get('excel_sheet_name', tab['sheet_name'])[:31])
        next_row = 1
        for year in years:
            # Даже вкладки с годами в столбцах экспортируются годовыми блоками.
            tab_territory = coefficient_territory_slug(territory_slug) if tab.get('layout') == 'coeff' else territory_slug
            context = builder(
                tab_territory, tab['slug'], start_year=year, end_year=year,
                view_year=year, **filters,
            )
            if context is None:
                raise ValueError('Некорректные параметры расчета')
            worksheet.cell(next_row, 1, f'{year} год – {context["page_title"]}').font = Font(bold=True, size=14)
            next_row += 1
            tables = []
            if not context.get('specific_emissions_only'):
                tables.append((
                    {'title': context.get('main_table_title'), 'rows': context['rows']},
                    context['rounding_digits'],
                ))
            tables.extend(
                (table, context['rounding_digits'])
                for table in context.get('summary_volume_tables', [])
            )
            tables.extend(
                (table, context.get('specific_rounding_digits', context['rounding_digits']))
                for table in context.get('specific_emission_tables', [])
            )
            for table, table_rounding_digits in tables:
                if table.get('title'):
                    worksheet.cell(next_row, 1, table['title']).font = Font(bold=True)
                    next_row += 1
                next_row = _write_table(
                    worksheet, next_row, context, table['rows'],
                    rounding_digits=table_rounding_digits,
                )
            next_row += 2
        worksheet.column_dimensions['A'].width = 65
        for column in range(2, worksheet.max_column + 1):
            worksheet.column_dimensions[get_column_letter(column)].width = 22
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return stream


def _write_header(worksheet, start_row, context):
    layout = context['sheet']['layout']
    view = context.get('emission_view') or {}
    pair = view.get('kind') == 'pair'
    range_header = context.get('year_columns_mode') and not context.get('dynamics_territories')
    height = 2 if layout == 'chars' or pair or range_header else 1

    def header_cell(row, column, title, *, rowspan=1, colspan=1):
        for cells in worksheet.iter_rows(
            min_row=row, max_row=row + rowspan - 1,
            min_col=column, max_col=column + colspan - 1,
        ):
            for cell in cells:
                cell.font = Font(bold=True)
                cell.fill = _HEADER_FILL
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        worksheet.cell(row, column, title)
        if rowspan > 1 or colspan > 1:
            worksheet.merge_cells(
                start_row=row, end_row=row + rowspan - 1,
                start_column=column, end_column=column + colspan - 1,
            )

    header_cell(start_row, 1, 'Вид топлива' if layout == 'chars' or view else 'Наименование', rowspan=height)
    if layout == 'chars':
        column = 2
        for group in context['char_header_groups']:
            header_cell(start_row, column, group['title'], colspan=len(group['keys']), rowspan=group.get('rowspan', 1))
            column += len(group['keys'])
        for index, column in enumerate(context['char_columns'], 2):
            if not column.get('hide_short'):
                header_cell(start_row + 1, index, column['short'])
    elif pair:
        for index, column in enumerate(context['value_columns']):
            header_cell(start_row, index * 2 + 2, column['sheet_name'], colspan=2)
            left_title = view['left_title']
            if left_title == 'Перевод в натур.':
                left_title += ' (BH)'
            header_cell(start_row + 1, index * 2 + 2, left_title)
            header_cell(start_row + 1, index * 2 + 3, view['right_title'])
    elif range_header:
        column_index = 2
        for territory in context['territory_columns']:
            title = territory['sheet_name']
            if layout == 'coeff':
                title += '\n' + {'minen': 'Станции отрасли', 'prompred': 'Промпредприятия'}.get(context.get('affiliation'), 'Все принадлежности')
            header_cell(start_row, column_index, title, colspan=len(context['years']))
            column_index += len(context['years'])
        for index, column in enumerate(context['value_columns'], 2):
            title = str(column['year'])
            feature = context.get('year_features', {}).get(column['year'])
            if feature:
                title += '\n' + feature
            header_cell(start_row + 1, index, title)
    else:
        for index, column in enumerate(context['value_columns'], 2):
            title = column['sheet_name']
            if view.get('metric_formula_html'):
                title += '\nМотх.'
            feature = context.get('year_features', {}).get(column.get('year'))
            if feature:
                title += '\n' + feature
            header_cell(start_row, index, title)
    for row in range(start_row, start_row + height):
        worksheet.row_dimensions[row].height = 60 if layout == 'chars' else 45
    return start_row + height


def _write_table(worksheet, start_row, context, rows, *, rounding_digits=None):
    layout = context['sheet']['layout']
    pair = (context.get('emission_view') or {}).get('kind') == 'pair'
    columns = context['value_columns']
    next_row = _write_header(worksheet, start_row, context)
    if worksheet.freeze_panes is None:
        worksheet.freeze_panes = f'B{next_row}'
    for row in rows:
        label = row['label']
        if row.get('unit'):
            label += f', {row["unit"]}'
        cell = worksheet.cell(next_row, 1, label)
        cell.font = Font(bold=row.get('kind') == 'total', italic=row.get('italic', False))
        cell.alignment = Alignment(wrap_text=True, indent=row.get('indent', 0))
        merges = []
        if layout == 'chars':
            values = [row['char_values'][context['view_year']][column['key']] for column in context['char_columns']]
        elif pair:
            values = []
            for column in columns:
                slug = column['slug']
                raw = row['col_values_raw']
                if row.get('span_pair'):
                    merges.append(len(values) + 2)
                    values.extend([raw.get(slug), None])
                else:
                    values.extend([raw.get(f'{slug}:l'), raw.get(f'{slug}:r')])
        else:
            values = [row['col_values_raw'].get(column['slug']) for column in columns]
        digits = context['rounding_digits'] if rounding_digits is None else rounding_digits
        if row.get('emitted_key'):
            digits = context['coefficient_rounding_digits']
        for index, value in enumerate(values, 2):
            cell = worksheet.cell(next_row, index, parse_excel_numeric(value))
            cell.number_format = excel_number_format_trimmed(digits)
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.font = Font(bold=row.get('kind') == 'total')
        for column in merges:
            worksheet.merge_cells(start_row=next_row, end_row=next_row, start_column=column, end_column=column + 1)
        next_row += 1
    return next_row
