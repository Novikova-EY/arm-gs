from io import BytesIO
from html import unescape
from decimal import Decimal
import re

import pytest
from flask.templating import render_template
from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database, runtime_bytes
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime, import_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import build_equipment_runtime_context, read_equipment_runtime_workbook


@pytest.mark.parametrize('pgu_part', [False, True])
def test_runtime_links_open_station_and_matching_aggregate_card(
        calculation_database, http_client, monkeypatch, pgu_part):
    from sqlalchemy import insert
    from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
    from app.rational_structure.routes import equipment_runtime_routes as routes

    if pgu_part:
        db.session.execute(insert(PGUMachine), {
            'id': 7, 'id_parent_machine': 1, 'machine_number': '1ГТ',
            'machine_name': 'Компонент <ПГУ>', 'database_version_id': 1,
        })
        db.session.commit()
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?column_G=ТЭЦ+Альфа')
    assert response.status_code == 200
    body = re.search(r'<tbody>(.*?)</tbody>', response.get_data(as_text=True), re.S).group(1)
    cells = dict(zip([key for key, _ in RUNTIME_COLUMNS], re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)))
    assert '<a href="/stations/1">ТЭЦ Альфа</a>' in cells['G']
    if pgu_part:
        assert '<a href="/stations/1/machines/1/parts/7">Компонент &lt;ПГУ&gt;</a>' in cells['L']
    else:
        assert '<a href="/stations/1/machines/1">Турбина Альфа</a>' in cells['L']
    assert '<a ' not in cells['H']


def test_runtime_missing_brand_stays_empty(calculation_database, http_client):
    context = build_equipment_runtime_context(MultiDict(), 1)
    context['rows'] = [context['rows'][0]]
    context['rows'][0]['values']['L'] = None
    with calculation_database.test_request_context('/rational_structure/equipment_runtime'):
        html = render_template('rational_structure/_calculation_table.html', **context)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = dict(zip([key for key, _ in RUNTIME_COLUMNS], re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)))
    assert cells['L'].strip() == '–'


def test_columns_are_fixed_order_even_without_data(calculation_database):
    expected = [key for key, _ in RUNTIME_COLUMNS]
    for version in (1, 2, None):
        context = build_equipment_runtime_context(MultiDict(), version)
        assert [column['key'] for column in context['table']['columns']] == expected
    assert len(expected) == 34
    assert 'D' not in expected
    assert dict(RUNTIME_COLUMNS)['K'] == 'Группа оборудования'
    assert expected[-2:] == ['BD', 'BF']
    assert 'BK' not in expected and 'BL' not in expected
    assert 'AS' in expected and 'BC' in expected
    assert 'I' not in expected and 'BB' not in expected


@pytest.mark.parametrize('value,expected', [
    (2025, '2025'), (2025.0, '2025'), (Decimal('2025.00'), '2025'),
    (Decimal('2025.5'), '2026'), (0, '0'), (None, '–'),
])
@pytest.mark.parametrize('rounding', [-1, 0, 2, 6])
def test_all_year_columns_render_without_grouping_and_other_numbers_keep_it(
        calculation_database, http_client, value, expected, rounding):
    year_keys = {'M', 'V', 'AP', 'AQ', 'AR', 'AS', 'AT', 'AU', 'AV', 'AW', 'AX', 'AY', 'AZ', 'BA', 'BC', 'planned_modernization_year'}
    context = build_equipment_runtime_context(MultiDict(), 1)
    columns = context['table']['columns']
    assert {column['key'] for column in columns if column['year']} == year_keys
    context['rows'] = [context['rows'][0]]
    context['rows'][0]['values'].update(dict.fromkeys(year_keys, value))
    context['rows'][0]['values'].update(N=1234567, AN=1234567, AO=1234567)
    context['rounding_digits'] = rounding
    with calculation_database.test_request_context('/rational_structure/equipment_runtime'):
        html = render_template('rational_structure/_calculation_table.html', **context)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = dict(zip([column['key'] for column in columns], re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)))
    assert all(cells[key].strip() == expected for key in year_keys)
    expected_number = '1 234 567' + (',' + '0' * rounding if rounding > 0 else '')
    assert all(cells[key].strip() == expected_number for key in ('N', 'AN', 'AO'))


@pytest.mark.parametrize('scheme_end', [2042, 2048])
def test_runtime_labels_tooltips_and_colors_match_export(calculation_database, http_client, monkeypatch, scheme_end):
    from app.rational_structure.services import equipment_runtime_services as services
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(services, 'get_general_scheme_end_year', lambda current_year: scheme_end)
    monkeypatch.setattr(routes, 'render_template', render_template)
    expected = {
        'AN': 'Среднегодовая наработка за три года, ч',
        'AO': 'Остаток до достижения двойного ресурса, ч/лет',
        'AP': 'Расчетный год демонтажа по ресурсу',
        'AQ': 'Год достижения первого нормативного ресурса',
        'AR': f'Расчетный год модернизации до {scheme_end + 1} года',
        'AS': 'Расчетный год модернизации с учетом СиПР',
        'planned_modernization_year': 'Плановый год модернизации',
        'AT': 'Плановый год окончательного вывода',
        'AU': 'Плановый год ввода оборудования',
        'AV': 'Плановый год вывода при замене',
        'AW': 'Год демонтажа угольного оборудования',
        'AX': 'Год демонтажа неугольного оборудования',
        'AY': 'Базовый год демонтажа',
        'AZ': 'Год демонтажа с учетом КОМ',
        'BA': 'Год демонтажа с учетом СиПР',
        'BC': 'Расчетный год демонтажа с учетом модернизации',
        'BD': 'Достигнут 70-летний срок эксплуатации – уголь',
        'BF': 'Достигнут двойной нормативный ресурс',
    }
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.findall(r'<th\b[^>]*scope="col"[^>]*>.*?</th>', html, re.S)
    keys = [key for key, _ in RUNTIME_COLUMNS]
    headers.sort(key=lambda header: keys.index(re.search(r'data-column-key="([^"]+)"', header).group(1)))
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    rows = [re.findall(r'<td\b([^>]*)>.*?</td>', row, re.S)
            for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', body, re.S)]
    for key, label in expected.items():
        header = headers[keys.index(key)]
        assert label in header
        assert f'aria-label="Формула: {label}"' in header
        button = re.search(r'<button\b[^>]*>', header).group()
        tooltip = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
        assert f'<p><strong>{label}</strong></p>' in tooltip
    response = client.get('/rational_structure/equipment_runtime/export')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    sheet = book['Расчет']
    for key, label in expected.items():
        assert sheet.cell(1, keys.index(key) + 1).value == label
    for key, color in (('AS', 'C6E0B4'), ('BC', 'FCE4D6')):
        index = keys.index(key)
        assert 'rs-runtime-highlight' in headers[index]
        assert f'--rs-runtime-column-bg: #{color}' in headers[index]
        assert rows
        for row in rows:
            assert 'rs-runtime-highlight' in row[index]
            assert f'--rs-runtime-column-bg: #{color}' in row[index]
        for row_index in range(1, sheet.max_row + 1):
            assert sheet.cell(row_index, index + 1).fill.fgColor.rgb == '00' + color
    assert all('rs-runtime-highlight' not in header for index, header in enumerate(headers)
               if keys[index] not in ('AS', 'BC'))
    book.close()
    restored = read_equipment_runtime_workbook(response.data)
    assert restored['calculation']['rows'][0]['values']['C'] == '002'
    assert 'AS' in restored['calculation']['rows'][0]['values']
    assert 'BC' in restored['calculation']['rows'][0]['values']


def test_export_error_fill_takes_priority_over_column_color(calculation_database):
    context = build_equipment_runtime_context(MultiDict(), 1)
    row = context['filtered_rows'][0]
    row['values']['BC'] = '#N/A'
    row['errors'].append('BC')
    book = load_workbook(export_equipment_runtime(context))
    index = [key for key, _ in RUNTIME_COLUMNS].index('BC') + 1
    cell = book['Расчет'].cell(2, index)
    assert cell.data_type == 'e'
    assert cell.fill.fgColor.rgb == '00FFF3CD'
    book.close()


def test_column_filters_multiple_values_empty_and_zero(calculation_database):
    context = build_equipment_runtime_context(MultiDict([('column_A', '1'), ('column_A', '2'), ('column_N', '0')]), 1)
    assert context['total'] == 2
    assert context['header_filter_args']['column_A'] == ['1', '2']
    assert build_equipment_runtime_context(MultiDict({'column_A': '2'}), 1)['rows'][0]['values']['C'] == '003'
    assert build_equipment_runtime_context(MultiDict({'column_F': '__empty__'}), 1)['total'] == 2
    assert build_equipment_runtime_context(MultiDict({'column_B': 'missing'}), 1)['total'] == 0
    assert build_equipment_runtime_context(MultiDict({'station': 'БЕТА'}), 1)['total'] == 1


def test_export_uses_visible_columns_and_all_filtered_rows(calculation_database):
    context = build_equipment_runtime_context(MultiDict({'per_page': '10', 'column_A': '2'}), 1)
    stream = export_equipment_runtime(context)
    book = load_workbook(stream, data_only=False)
    assert [cell.value for cell in book['Расчет'][1]] == [label for _, label in RUNTIME_COLUMNS]
    assert book['Расчет'].max_row == 2
    assert book['Расчет']['C2'].value == '003'
    assert book['Расчет']['J2'].value == 0
    book.close()
    restored = read_equipment_runtime_workbook(stream.getvalue())
    assert 'BK' not in restored['calculation']['rows'][0]['values']
    assert 'BL' not in restored['calculation']['rows'][0]['values']
    assert restored['calculation']['rows'][0]['errors'] == []
    assert restored['calculation']['rows'][0]['values']['AN'] == 0
    assert restored['summary']['rows'][0]['values']['B'] == 'Первый ресурс'
    assert 'D' not in restored['summary']['rows'][1]['values']


@pytest.mark.parametrize('year,expected', [(2024, 7840), (2025, 7791), (2030, 0)])
def test_runtime_page_renders_average_for_selected_year(calculation_database, http_client, monkeypatch, year, expected):
    from app.rational_structure.models import EquipmentTechnicalCharacteristic
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    db.session.add_all([
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='steam',
                                         report_year=report_year, operating_hours_year=hours, database_version_id=1)
        for report_year, hours in ((2022, 7938), (2023, 7905), (2024, 7677))
    ])
    db.session.commit()
    client, _ = http_client
    response = client.get(f'/rational_structure/equipment_runtime?year={year}&column_C=002&rounding_digits=0')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Источник и особенности расчета' not in html
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    formula_button = re.search(r'<button\b[^>]*aria-label="Формула: Среднегодовая наработка за три года, ч"[^>]*>', headers).group()
    assert 'bi-info-circle' in formula_button
    assert 'Средняя наработка = сумма ненулевых значений' in formula_button
    assert f'за {year - 2}–{year} годы' in formula_button
    assert 'Если ненулевых значений нет – результат 0' in formula_button
    assert headers.count('bi-info-circle') == 18
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    average_index = [key for key, _ in RUNTIME_COLUMNS].index('AN')
    assert re.sub(r'\s+', '', cells[average_index]) == str(expected)


@pytest.mark.parametrize('query,expected', [
    ('', 0), ('?rounding_digits=invalid', 0), ('?rounding_digits=5', 0),
    ('?rounding_digits=0', 0), ('?rounding_digits=2', 2), ('?rounding_digits=-1', -1),
    ('?rounding_digits=6', 6),
])
def test_runtime_rounding_default_and_explicit_choice(calculation_database, http_client, monkeypatch, query, expected):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    from app.rational_structure.services.calculation_workbook_services import calculation_rounding
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime' + query)
    assert response.status_code == 200
    rounding_select = re.search(r'<select\b[^>]*id="rs-rounding".*?</select>', response.get_data(as_text=True), re.S).group()
    selected = re.search(r'<option value="([^"]+)" selected[^>]*>([^<]+)</option>', rounding_select)
    assert int(selected.group(1)) == expected
    if expected == 0:
        assert selected.group(2) == 'Не округлять'
    assert calculation_rounding(MultiDict()) == 3  # другие расчетные страницы не меняют значение по умолчанию


@pytest.mark.parametrize('column_count', [28, 30, 31])
@pytest.mark.parametrize('modernization_year', [2043, 2049])
def test_previous_exports_with_removed_columns_remain_readable(column_count, modernization_year):
    old_labels = [
        'Средняя наработка за три года, ч', 'Остаток от двойного  ресурса',
        'Год демонтажа по ресурсу', 'Год достижения 1-ого ресурса',
        f'Модернизация до {modernization_year} года', 'Перенос модернизации по СИПР',
        'Год демонтажа в СИПР/ КОММод', 'Поставка по КОММод',
        'Год демонтажа под замену по КОММод', 'Демонтаж угольных', 'Демонтаж газовых',
        'Демонтаж ИТОГО', 'Перенос демонтажа по КОМ', 'Перенос демонтажа по СИПРУ',
        'Уходим от дублирования с модернизацией', 'Превысили два ресурса уголь',
        'Превысили два ресурса газ',
    ]
    compact_columns = [(key, label) for key, label in RUNTIME_COLUMNS if key not in {'M', 'S', 'T', 'U', 'V'}]
    columns = [*compact_columns[:11], *zip([key for key, _ in compact_columns[11:] if key != 'planned_modernization_year'], old_labels)]
    if column_count > 28:
        columns.extend([('BK', 'Перенос модернизации по СИПР'), ('BL', 'Уходим от дублирования')])
    if column_count == 31:
        columns.insert(3, ('D', 'Год предоставления отчетности'))
        columns = [(key, 'Технологии' if key == 'K' else label) for key, label in columns]
    book = Workbook()
    sheet = book.active
    sheet.title = 'Расчет'
    sheet.append([label for _, label in columns])
    values = {'C': '0002', 'G': 'Тестовая ТЭС', 'K': 'ПГУ', 'AN': 7840, 'AO': 15000,
              'AS': 2032, 'BC': 2040, 'BD': 'no', 'BF': 'yes'}
    if column_count > 28:
        values.update(BK=2032, BL=2040)
    if column_count == 31:
        values['D'] = 2024
    sheet.append([values.get(key) for key, _ in columns])
    summary = book.create_sheet('Лист2')
    summary.append([])
    summary.append(['№', 'Показатель', 'Единица измерения'])
    summary.append([1, 'Первый ресурс', 'ч'])
    stream = BytesIO()
    book.save(stream)
    book.close()
    data = read_equipment_runtime_workbook(stream.getvalue())
    for key, value in values.items():
        assert data['calculation']['rows'][0]['values'][key] == value


def test_pagination_does_not_limit_export(calculation_database):
    from app.generation.models.machine.machine_model import Machine
    for index in range(3, 14):
        db.session.execute(Machine.__table__.insert(), {
            'id': index, 'id_station': 1, 'machine_number': str(index), 'external_code': f'machine-{index}',
            'machine_name': f'Турбина {index}', 'database_version_id': 1})
    db.session.commit()
    context = build_equipment_runtime_context(MultiDict({'per_page': '10', 'page': '2', 'column_A': '1'}), 1)
    assert context['total'] == 12
    assert context['page'] == 2 and len(context['rows']) == 2
    book = load_workbook(export_equipment_runtime(context))
    assert book['Расчет'].max_row == 13
    book.close()


def test_export_does_not_execute_formula_like_text(calculation_database):
    context = build_equipment_runtime_context(MultiDict(), 1)
    context['filtered_rows'][0]['values']['G'] = '=HYPERLINK("https://example.invalid")'
    book = load_workbook(export_equipment_runtime(context), data_only=False)
    assert book['Расчет']['F2'].data_type == 's'
    book.close()


def test_import_is_version_scoped_and_invalid_file_keeps_existing_data(calculation_database):
    original = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    original_data = original.data
    with pytest.raises(ValueError):
        import_equipment_runtime(b'invalid', 1, 'invalid.xlsx', 'tester')
    assert original.data == original_data
    with pytest.raises(ValueError, match='Выберите версию'):
        import_equipment_runtime(runtime_bytes(), None, 'runtime.xlsx', 'tester')
    assert import_equipment_runtime(runtime_bytes(), 2, 'runtime.xlsx', 'tester') == 2
    assert build_equipment_runtime_context(MultiDict(), 2)['total'] == 0
    assert build_equipment_runtime_context(MultiDict(), 1)['total'] == 2


def test_runtime_page_has_same_controls_and_exact_columns(calculation_database, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    html = client.get('/rational_structure/equipment_runtime').get_data(as_text=True)
    assert 'rs-technical-page rs-data-page rs-sticky-toolbar-page' in html
    assert 'js/rational_structure/sticky_table_toolbar.js' in html
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    assert headers.count('scope="col"') == 34
    assert 'Столбец BK исходной книги' not in headers
    assert 'Столбец BL исходной книги' not in headers
    assert headers.count('Формула: Плановый год модернизации') == 1
    assert 'Год предоставления отчетности' not in headers
    assert 'Технологии' not in headers
    assert 'id="rs-year"' in html
    assert 'Все годы' not in html
    for key, label in RUNTIME_COLUMNS:
        assert label in headers
        assert f'data-filter-param="column_{key}"' in headers
    assert 'id="rsFiltersCollapse"' not in html
    assert 'placeholder="Название станции"' not in html
    assert 'placeholder="Название агрегата"' not in html
    assert 'placeholder="Станция, код или марка"' not in html
    filter_form = re.search(r'<form\b[^>]*id="rs-filter-form"[^>]*>.*?</form>', html, re.S).group()
    assert '<select' not in filter_form
    assert '<button' not in filter_form
    for text in ('Экспорт в Excel', 'Применить', 'Сбросить', 'Округл:', 'Показать:'):
        assert text in html
    assert html.count('Экспорт в Excel') == 1
    assert html.index('rs-table-toolbar') < html.index('Экспорт в Excel') < html.index('for="rs-rounding"')
    assert 'id="rsImportForm"' not in html
    assert 'Импорт' not in html
    assert 'aria-label="Анализ данных"' not in html
    assert 'aria-label="Листы расчета наработки"' not in html
    links = re.findall(r'<a\b[^>]*>(.*?)</a>', html, re.S)
    for label in ('Расчет наработки ЕГО', 'Расчет замыкающей цены', 'Расчет оборудования', 'Сводка по ресурсам'):
        assert all(label not in link for link in links)
    assert 'value="10"' in html


@pytest.mark.parametrize('path,column,value', [
    ('equipment_runtime', 'column_C', '002'),
    ('technical_characteristics', 'column_equipment_code', '"002"'),
])
def test_reporting_controls_keep_active_filters_without_search_row(calculation_database, http_client, monkeypatch, path, column, value):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get('/rational_structure/' + path, query_string={
        'year': '2024', column: value, 'station': 'Альфа', 'equipment_type': 'gas',
    })
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    form = re.search(r'<form\b[^>]*id="rs-filter-form"[^>]*>.*?</form>', html, re.S).group()
    assert f'type="hidden" name="{column}"' in form
    assert 'type="hidden" name="station" value="Альфа"' in form
    assert 'type="hidden" name="equipment_type" value="gas"' in form
    assert '<select' not in form and '<button' not in form
    assert 'id="rs-year" name="year" form="rs-filter-form"' in html
    assert 'id="rs-rounding" name="rounding_digits" form="rs-filter-form"' in html
    assert 'id="rs-per-page" name="per_page" form="rs-filter-form"' in html


def test_non_admin_has_export_but_no_import(calculation_database, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, user = http_client
    user.has_admin = False
    html = client.get('/rational_structure/equipment_runtime?sheet=summary').get_data(as_text=True)
    assert 'Экспорт в Excel' in html
    assert 'id="rsImportForm"' not in html
    assert 'Первый ресурс' in html


def test_import_http_permissions_csrf_and_upload(calculation_database, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'log_to_db', lambda *args, **kwargs: None)
    client, user = http_client
    user.has_admin = False
    assert client.post('/rational_structure/equipment_runtime/import').status_code == 403
    user.has_admin = True
    response = client.post('/rational_structure/equipment_runtime/import', data={'file': (BytesIO(runtime_bytes()), 'runtime.xlsx')})
    assert response.status_code == 302
    archived = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    assert archived.source_filename == 'source.xlsx'
    calculation_database.config['WTF_CSRF_ENABLED'] = False
    response = client.post('/rational_structure/equipment_runtime/import', data={'file': (BytesIO(runtime_bytes()), 'runtime.xlsx')})
    assert response.status_code == 302
    db.session.refresh(archived)
    assert archived.source_filename == 'runtime.xlsx'
    assert build_equipment_runtime_context(MultiDict(), 1)['workbook'] is None
    response = client.get('/rational_structure/equipment_runtime/export?column_A=2')
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    assert book['Расчет'].max_row == 2
    book.close()
