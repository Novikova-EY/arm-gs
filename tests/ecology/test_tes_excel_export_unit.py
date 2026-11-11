"""Проверки содержимого Excel и подключения выгрузки на расчетных страницах."""
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from flask import Flask, request
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
from flask_login import LoginManager
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from test_calculation_summary_unit import summary_data
from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services import tes_excel_export_services as export
from app.ecology.services import operating_tes_page_services as operating
from app.ecology.services import new_tes_page_services as new


@pytest.fixture
def export_data(summary_data, monkeypatch):
    def year_range(start=None, end=None):
        return list(range(int(start or 2026), int(end or 2027) + 1))

    for module in (export, operating, new):
        monkeypatch.setattr(module, 'get_year_columns', year_range)


def annual_starts(worksheet):
    return [cell.row for cell in worksheet['A'] if isinstance(cell.value, str) and ' год – ' in cell.value]


@pytest.mark.parametrize('summary,tabs', [(False, export.CALC_SHEETS), (True, export.CALCULATION_SUMMARY_TABS)])
def test_all_tabs_all_years_numeric_values_and_spacing(export_data, summary, tabs):
    stream = export.build_tes_excel_stream('vsego', {
        'start_year': '2026', 'end_year': '2027', 'view_year': '2027', 'rounding_digits': '1',
    }, summary=summary)
    workbook = load_workbook(stream)
    assert workbook.sheetnames == [tab.get('excel_sheet_name', tab['sheet_name'])[:31] for tab in tabs]
    for worksheet in workbook:
        starts = annual_starts(worksheet)
        assert len(starts) == 2
        assert worksheet.cell(starts[0], 1).value.startswith('2026 год')
        assert worksheet.cell(starts[1], 1).value.startswith('2027 год')
        for row in (starts[1] - 2, starts[1] - 1):
            assert all(cell.value is None for cell in worksheet[row])
        assert any(cell.value is not None for cell in worksheet[starts[1] - 3])
        header_row = next(cell.row for cell in worksheet['A'] if cell.value in ('Наименование', 'Вид топлива'))
        header_end = max([header_row] + [merged.max_row for merged in worksheet.merged_cells.ranges if merged.min_col == 1 and merged.min_row == header_row])
        assert worksheet.freeze_panes == f'B{header_end + 1}'
    fuel = workbook[tabs[0]['sheet_name']]
    starts = annual_starts(fuel)
    fuel_row = next(cell.row for cell in fuel['A'] if str(cell.value).startswith('Природный газ'))
    cell = fuel.cell(fuel_row, 2)
    assert cell.data_type == 'n'
    assert cell.value == pytest.approx(6.12 if summary else 1.04)
    assert cell.number_format == '#,##0.#'
    second = next(cell.row for cell in fuel['A'][starts[1]:] if str(cell.value).startswith('Природный газ'))
    assert fuel.cell(second, 2).value == pytest.approx(cell.value * 2)
    if summary:
        russia = workbook['Объемы выбросов по России']
        for title in ('Всего', 'Действующие ТЭС', 'Новые ТЭС – 100 МВт и более', 'Новые ТЭС – менее 100 МВт'):
            assert sum(cell.value == title for cell in russia['A']) == 2
        assert workbook['Удельные выбросы по России'].max_row > 30
        # В динамике годы тоже идут блоками, а не параллельными столбцами.
        assert workbook['Динамика изменения выбросов'].max_column == 2
        worksheet = workbook['Динамика удельных выбросов']
        assert worksheet.max_column == 2
        assert any(cell.data_type == 'n' for row in worksheet.iter_rows(min_col=2) for cell in row)
        context = export.build_calculation_summary_context('vsego', 'dynamics-specific', start_year=2026, end_year=2026)
        assert len(context['specific_emission_tables']) == 3
        for table in context['specific_emission_tables']:
            assert sum(cell.value == table['title'] for cell in worksheet['A']) == 2
    else:
        assert workbook['Характеристики'].max_column > 5
        ash = workbook['Зола']
        visible_territories = [
            column for column in operating.get_territory_columns()
            if column['slug'] not in {'minen', 'prompred'}
        ]
        assert ash.max_column == 1 + 2 * len(visible_territories)
        assert len(ash.merged_cells.ranges) > 0
        assert any(cell.value is not None for row in ash.iter_rows(min_col=2) for cell in row)
        volumes = workbook['Объемы выбросов действующих ТЭС']
        for table in operating.build_operating_tes_table_context('vsego', 'obemy', start_year=2026, end_year=2026)['specific_emission_tables']:
            assert sum(cell.value == table['title'] for cell in volumes['A']) == 2


def test_specific_emission_export_uses_screen_precision(export_data):
    args = {
        'start_year': '2026', 'end_year': '2026', 'rounding_digits': '1',
        'coefficient_rounding_digits': '2', 'specific_rounding_digits': '3',
    }
    context = operating.build_operating_tes_table_context(
        'vsego', 'obemy', **{key: int(value) for key, value in args.items()},
    )
    workbook = load_workbook(export.build_tes_excel_stream('vsego', args))
    worksheet = workbook['Объемы выбросов действующих ТЭС']
    specific_table = context['specific_emission_tables'][0]
    title_row = next(cell.row for cell in worksheet['A'] if cell.value == specific_table['title'])
    column_slug = context['value_columns'][0]['slug']
    data_index = next(
        index for index, row in enumerate(specific_table['rows'])
        if row['col_values_raw'].get(column_slug) not in (None, '')
    )
    row_number = title_row + 2 + data_index
    exported = worksheet.cell(row_number, 2)
    source_row = specific_table['rows'][data_index]
    assert exported.value == pytest.approx(float(source_row['col_values_raw'][column_slug]))
    assert exported.number_format == '#,##0.###'
    assert source_row['col_values'][column_slug] == operating.format_cell(
        float(source_row['col_values_raw'][column_slug]), 3,
    )

    ash = load_workbook(export.build_tes_excel_stream('vsego', args))['Зола']
    coefficient_row = next(cell.row for cell in ash['A'] if cell.value == 'КПД золоулавливания')
    total_row = next(cell.row for cell in ash['A'] if cell.value == 'ΣМотх.')
    assert ash.cell(coefficient_row, 2).number_format == '#,##0.##'
    assert ash.cell(total_row, 2).number_format == '#,##0.#'


@pytest.mark.parametrize('summary', [False, True])
def test_button_is_after_empty_rows_and_preserves_export_filters(export_data, summary):
    builder = export.build_calculation_summary_context if summary else export.build_operating_tes_table_context
    context = builder(
        'vsego', 'russia' if summary else 'obemy', start_year=2026, end_year=2027,
        rounding_digits=2, coefficient_rounding_digits=1, specific_rounding_digits=3,
    )
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}'}),
        FileSystemLoader(Path('app/templates')),
    ]))
    env.globals['get_reference_years'] = lambda: [2026, 2027]
    context['url_for'] = lambda endpoint, **values: '/' + endpoint + '?' + urlencode({key: value for key, value in values.items() if value is not None})
    with Flask(__name__).test_request_context('/'):
        html = env.get_template('ecology/operating_tes/operating_tes_table.html').render(
            **context, request=request, current_user=SimpleNamespace(is_authenticated=True), csrf_token='test',
        )
    assert html.index('id="otShowEmptyRowsToggle"') < html.index('id="otExportExcelBtn"') < html.index('<table')
    button = html.split('id="otExportExcelBtn"', 1)[1].split('</button>', 1)[0]
    assert 'Экспорт в Excel' in button
    reference = Path('app/templates/ecology/_gis_tek_filters.html').read_text(encoding='utf-8')
    reference_classes = reference.split('id="gisTekExportBtn"', 1)[0].rsplit('class="', 1)[1].split('"', 1)[0]
    assert f'class="{reference_classes}"' in button
    assert '<i class="bi bi-file-earmark-excel" aria-hidden="true"></i>' in button
    assert 'start_year=2026' in button and 'end_year=2027' in button
    assert 'rounding_digits=2' in button
    assert 'coefficient_rounding_digits=1' in button
    assert 'specific_rounding_digits=3' in button
    assert 'window.armGsExportExcel(exportButton, exportButton.dataset.exportUrl)' in html
    assert 'filename=js%2Fcommon%2Fexcel_export_fetch.js' in html


@pytest.mark.parametrize('prefix', ['operating_tes', 'calculation_summary'])
def test_download_routes_and_invalid_territory(export_data, prefix):
    app = Flask(__name__)
    app.config.update(TESTING=True, LOGIN_DISABLED=True)
    LoginManager(app).request_loader(lambda request: None)
    app.register_blueprint(ecology_bp, url_prefix='/ecology')
    client = app.test_client()
    response = client.get(f'/ecology/{prefix}/vsego/export.xlsx?start_year=2026&end_year=2027')
    assert response.status_code == 200
    assert response.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert 'attachment;' in response.headers['Content-Disposition']
    assert len(load_workbook(BytesIO(response.data)).sheetnames) == (10 if prefix == 'operating_tes' else 5)
    assert client.get(f'/ecology/{prefix}/invalid/export.xlsx').status_code == 404
    app.config['LOGIN_DISABLED'] = False
    assert client.get(f'/ecology/{prefix}/vsego/export.xlsx').status_code == 401


@pytest.mark.parametrize('tab', ['khar-topl', 'koeff', 'zola', 'sera', 'co', 'pg-tj'])
def test_multiline_headers_repeat_with_merges_in_each_year(export_data, tab):
    workbook = load_workbook(export.build_tes_excel_stream('vsego', {
        'start_year': 2026, 'end_year': 2027,
    }))
    sheet_name = next(sheet['sheet_name'] for sheet in export.CALC_SHEETS if sheet['slug'] == tab)
    worksheet = workbook[sheet_name[:31]]
    merged_ranges = {str(merged) for merged in worksheet.merged_cells.ranges}
    territory_columns = operating.build_operating_tes_table_context(
        'vsego', tab, start_year=2026, end_year=2026,
    )['territory_columns']
    for year_start in annual_starts(worksheet):
        top = year_start + 1
        bottom = top + 1
        assert f'A{top}:A{bottom}' in merged_ranges
        assert worksheet.cell(top, 1).value == ('Наименование' if tab == 'koeff' else 'Вид топлива')
        if tab == 'khar-topl':
            assert worksheet.cell(top, 2).value == 'Зольность'
            assert worksheet.cell(bottom, 2).value == 'Ap, %'
            assert worksheet.cell(top, 7).value == 'Низшая теплота сгорания'
            assert f'G{top}:H{top}' in merged_ranges
            assert worksheet.cell(bottom, 7).value == 'QH, кДж/кг'
            assert worksheet.cell(bottom, 8).value == 'QH, ккал/кг'
            assert f'M{top}:O{top}' in merged_ranges
        elif tab == 'koeff':
            assert worksheet.cell(top, 2).value == 'Всего\nВсе принадлежности'
            assert worksheet.cell(bottom, 2).value == str(2026 if year_start == 1 else 2027)
        else:
            for index, territory in enumerate(territory_columns):
                column = index * 2 + 2
                assert worksheet.cell(top, column).value == territory['sheet_name']
                assert f'{get_column_letter(column)}{top}:{get_column_letter(column + 1)}{top}' in merged_ranges
                assert worksheet.cell(bottom, column).value == ('МДж' if tab == 'pg-tj' else 'Перевод в натур. (BH)')
                assert worksheet.cell(bottom, column + 1).value == 'Мотх.'
        assert worksheet.cell(bottom + 1, 1).value is not None
        assert worksheet.cell(top, 2).alignment.wrap_text is True
        assert worksheet.cell(bottom, 2).fill.fgColor.rgb == '00D1E7DD'


def test_line_breaks_inside_single_row_headers_are_preserved(export_data):
    from openpyxl import Workbook

    context = operating.build_operating_tes_table_context('vsego', 'azot', start_year=2026, end_year=2026)
    worksheet = Workbook().active
    export._write_table(worksheet, 1, context, context['rows'])
    assert worksheet['B1'].value == 'Всего\nМотх.'
    assert worksheet['B1'].alignment.wrap_text is True
    assert worksheet['A2'].value == context['rows'][0]['label']


def test_zero_missing_negative_and_hidden_rows_are_preserved():
    from openpyxl import Workbook

    worksheet = Workbook().active
    context = {
        'sheet': {'layout': 'volumes'}, 'rounding_digits': 3,
        'value_columns': [{'slug': 'total', 'sheet_name': 'Всего'}],
    }
    export._write_table(worksheet, 1, context, [
        {'label': label, 'is_empty': True, 'col_values_raw': {'total': value}}
        for label, value in [('Ноль', '0'), ('Нет данных', ''), ('Отрицательное', '-1.23456789')]
    ])
    stream = BytesIO()
    worksheet.parent.save(stream)
    stream.seek(0)
    worksheet = load_workbook(stream).active
    assert worksheet['B2'].value == 0
    assert worksheet['B3'].value is None
    assert worksheet['B4'].value == pytest.approx(-1.23456789)
    assert worksheet['B4'].number_format == '#,##0.###'
