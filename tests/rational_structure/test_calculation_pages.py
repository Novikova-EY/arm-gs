from decimal import Decimal
from io import BytesIO

import pytest
from flask.templating import render_template
from openpyxl import Workbook
from werkzeug.datastructures import MultiDict

from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook, build_equipment_runtime_context
from app.rational_structure.services.marginal_price_services import read_marginal_price_workbook, build_marginal_price_context, TERRITORY_SHEETS


def runtime_bytes():
    book = Workbook()
    sheet = book.active
    sheet.title = "Расчет"
    for col, label in ((1, "Энергозона"), (3, "Код оборудования"), (4, "Год отчетности"),
                       (7, "Станция"), (40, "Средняя наработка")):
        sheet.cell(1, col, label)
    for index, (zone, station) in enumerate(((1, "ТЭЦ Альфа"), (2, "ТЭЦ Бета")), 2):
        for col, value in ((1, zone), (3, f"00{index}"), (4, 2024), (7, station), (14, 0), (40, 7840), (63, "#N/A")):
            sheet.cell(index, col, value)
    summary = book.create_sheet("Лист2")
    summary["D2"] = 2025
    summary["B3"] = "Первый ресурс"
    summary["B4"] = "К-200"
    summary["C4"] = "МВт"
    summary["D4"] = 420
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def price_bytes():
    book = Workbook()
    book.remove(book.active)
    for name in TERRITORY_SHEETS.values():
        sheet = book.create_sheet(name)
        sheet["A2"] = "ОЭС " + name
        sheet["B4"] = "Номер ступени"
        sheet["C4"] = "Цена"
        sheet["D4"] = "Станция"
        sheet["Q4"] = "Годовая энергия"
        for row, year, step in ((5, 2042, 1), (6, None, 2), (7, 2041, 1)):
            for col, value in ((1, year), (2, step), (3, 1.23456789), (4, name + " станция"), (16, 100), (17, 200 if row != 6 else None)):
                sheet.cell(row, col, value)
        sheet.merge_cells("A5:A6")
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def test_worktime_preserves_codes_zeros_errors_and_summary():
    data = read_equipment_runtime_workbook(runtime_bytes())
    row = data["calculation"]["rows"][0]
    assert row["values"]["C"] == "002"
    assert row["values"]["N"] == 0
    assert row["values"]["BK"] == "#N/A"
    assert row["errors"] == ["BK"]
    assert data["calculation"]["error_count"] == 2
    assert data["summary"]["rows"][1]["values"]["D"] == 420


def test_cached_empty_string_is_not_an_excel_error():
    from zipfile import ZipFile
    from xml.etree import ElementTree as ET
    from app.rational_structure.services.calculation_workbook_services import open_calculation_workbook, read_calculation_table
    book = Workbook()
    sheet = book.active
    sheet.append(["Название", "Значение"])
    sheet.append(["Пустой результат", '=IF(1=1,"",5)'])
    sheet.append(["Нет сохраненного результата", "=1+2"])
    source = BytesIO()
    book.save(source)
    book.close()
    result = BytesIO()
    namespace = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with ZipFile(source) as original, ZipFile(result, "w") as output:
        for name in original.namelist():
            data = original.read(name)
            if name == "xl/worksheets/sheet1.xml":
                root = ET.fromstring(data)
                root.find('.//s:c[@r="B2"]', namespace).set("t", "str")
                data = ET.tostring(root)
            output.writestr(name, data)
    values = open_calculation_workbook(result.getvalue(), data_only=True)
    formulas = open_calculation_workbook(result.getvalue(), data_only=False)
    try:
        table = read_calculation_table(values.active, formulas.active, header_row=1, start_row=2,
                                       end_column=2, required_column=1)
        assert table["rows"][0]["values"]["B"] is None
        assert table["rows"][0]["errors"] == []
        assert table["rows"][1]["errors"] == ["B"]
    finally:
        values.close()
        formulas.close()


def test_price_carries_merged_year_to_all_periods_and_keeps_precision():
    data = read_marginal_price_workbook(price_bytes())
    assert set(data) == set(TERRITORY_SHEETS)
    assert [row["values"]["A"] for row in data["east"]["rows"]] == [2042, 2042, 2041]
    assert data["east"]["rows"][0]["values"]["C"] == '1.23456789'
    assert data["east"]["rows"][1]["values"]["Q"] is None


@pytest.mark.parametrize("reader", [read_equipment_runtime_workbook, read_marginal_price_workbook])
def test_invalid_book_is_actionable_error(reader):
    with pytest.raises(ValueError, match="Не удалось прочитать"):
        reader(b"not an xlsx")


@pytest.fixture
def calculation_database(database):
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.station.station_model import Station
    from app.rational_structure.models import TechnicalInspectionCode
    from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
    from app.refdata.models.fuels.fuel_model import Fuel
    from app.refdata.models.years.year_feature_model import YearFeature
    from app.refdata.models.years.year_service_model import YearService
    from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from config import SCHEMA_FUEL

    schema_map = dict(db.engine.get_execution_options()['schema_translate_map'], **{SCHEMA_FUEL: None})
    db.engine.update_execution_options(schema_translate_map=schema_map)
    for model in (YearFeature, YearService, CalculationWorkbook, Fuel, StationType, EnergyZone, RegionalDistrict, EquipmentGroupType,
                  MachineFuelParam, EquipmentGroup, EquipmentGroupSet, EquipmentGroupSetStation, EquipmentGroupFuelParam):
        model.__table__.create(db.engine)
    db.session.execute(StationType.__table__.insert(), {'id': 1, 'name': 'ТЭС', 'database_version_id': 1})
    for index, label in enumerate(('Альфа', 'Бета'), 1):
        db.session.execute(EnergyZone.__table__.insert(), {
            'id': index, 'number': str(index), 'name': f'Энергозона {index}', 'database_version_id': 1})
        db.session.execute(RegionalDistrict.__table__.insert(), {
            'id': index, 'name': f'Регион {label}', 'name_full': label, 'name_rp': label, 'name_dp': label,
            'id_energy_zone': index, 'database_version_id': 1})
        db.session.execute(Station.__table__.insert(), {
            'id': index, 'name': f'ТЭЦ {label}', 'external_code': f'station-{index}',
            'id_station_type': 1, 'id_regional_district': index, 'database_version_id': 1})
        db.session.execute(Machine.__table__.insert(), {
            'id': index, 'id_station': index, 'machine_number': str(index), 'external_code': f'machine-{index}',
            'machine_name': f'Турбина {label}', 'database_version_id': 1})
        db.session.add_all([
            MachinePower(id_machine=index, year_number=2024, p_ust=0, database_version_id=1),
            TechnicalInspectionCode(machine_id=index, equipment_code=f'00{index + 1}', database_version_id=1),
        ])
    for kind, data in (("equipment_runtime", read_equipment_runtime_workbook(runtime_bytes())),
                       ("marginal_price", read_marginal_price_workbook(price_bytes()))):
        db.session.add(CalculationWorkbook(database_version_id=1, kind=kind, source_filename="source.xlsx",
                                           source_sha256="0" * 64, data=data))
    db.session.commit()
    return database


def test_worktime_filters_pagination_and_version_isolation(calculation_database):
    context = build_equipment_runtime_context(MultiDict( {"energy_zone": "2", "search": "бета", "year": "2024"}), 1)
    assert context["total"] == 1
    assert context["rows"][0]["values"]["G"] == "ТЭЦ Бета"
    assert build_equipment_runtime_context(MultiDict({"page": "999"}), 1)["page"] == 1
    assert build_equipment_runtime_context(MultiDict(), 2)["rows"] == []
    assert build_equipment_runtime_context(MultiDict(), None)["workbook"] is None


def test_price_filters_year_territory_and_version_isolation(calculation_database):
    context = build_marginal_price_context(MultiDict({"territory": "east", "year": "2042"}), 1)
    assert len(context["rows"]) == 2
    assert (context["start_year"], context["end_year"]) == (2042, 2042)
    assert context["rows"][0]["values"]["D"] == "Восток станция"
    assert build_marginal_price_context(MultiDict({"year": "2041"}), 1)["total"] == 1
    assert build_marginal_price_context(MultiDict(), 2)["rows"] == []


@pytest.mark.parametrize("builder,args", [
    (build_equipment_runtime_context, {"energy_zone": "999"}),
    (build_equipment_runtime_context, {"sheet": "invalid"}),
    (build_marginal_price_context, {"territory": "invalid"}),
    (build_marginal_price_context, {"year": "1900"}),
    (build_marginal_price_context, {"start_year": "1900"}),
    (build_marginal_price_context, {"end_year": "not-a-year"}),
])
def test_invalid_filters_return_bad_request(calculation_database, builder, args):
    from werkzeug.exceptions import BadRequest
    with pytest.raises(BadRequest):
        builder(MultiDict(args), 1)


@pytest.mark.parametrize("path,expected", [
    ("equipment_runtime", "ТЭЦ Альфа"), ("equipment_runtime?sheet=summary", "Первый ресурс"),
    ("marginal_price?territory=east&year=2042", "Восток станция"),
])
def test_real_templates_render_source_values_and_styles(calculation_database, http_client, monkeypatch, path, expected):
    from app.rational_structure.routes import equipment_runtime_routes, marginal_price_routes
    monkeypatch.setattr(equipment_runtime_routes, "render_template", render_template)
    monkeypatch.setattr(marginal_price_routes, "render_template", render_template)
    client, _ = http_client
    response = client.get("/rational_structure/" + path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert expected in html
    assert 'class="table-success"' in html
    if path.startswith('equipment_runtime'):
        assert 'Источник и особенности расчета' not in html
        assert '<details' not in html
    else:
        assert "Источник и особенности расчета" not in html
        assert "Версия БД:" not in html
        assert "Годовая энергия:" not in html
        assert "Загруженный файл:" not in html
        assert "Дата загрузки:" not in html
        assert "Все пять территорий и расчетные годы" not in html
        assert 'data-bs-target="#marginal-price-import"' in html
        assert 'class="collapse mb-3" id="marginal-price-import"' in html
        assert 'Выгрузить в Excel' in html
    if path == "equipment_runtime":
        assert "#N/A" not in html
        assert 'class="alert alert-warning"' not in html


def test_marginal_territory_buttons_replace_calculation_navigation(calculation_database, http_client, monkeypatch):
    import re
    from urllib.parse import parse_qs, urlsplit
    from app.rational_structure.routes import marginal_price_routes

    monkeypatch.setattr(marginal_price_routes, "render_template", render_template)
    client, _ = http_client
    html = client.get("/rational_structure/marginal_price?territory=east&start_year=2041&end_year=2042&rounding_digits=6&price_rounding_digits=3").get_data(as_text=True)
    navs = re.findall(r'<nav\b[^>]*aria-label="Территории расчета замыкающей цены"[^>]*>(.*?)</nav>', html, re.S)
    assert len(navs) == 1
    links = re.findall(r'<a\b([^>]*)>(.*?)</a>', navs[0], re.S)
    assert [label for _, label in links] == ['Европейская часть', 'Юг', 'Урал', 'Сибирь', 'Восток']
    for (attributes, _), slug in zip(links, TERRITORY_SHEETS):
        assert 'fs-5 text-nowrap flex-shrink-0' in attributes
        href = re.search(r'href="([^"]+)"', attributes).group(1).replace('&amp;', '&')
        assert parse_qs(urlsplit(href).query) == {'territory': [slug], 'start_year': ['2041'], 'end_year': ['2042'], 'rounding_digits': ['6'], 'price_rounding_digits': ['3']}
        assert ('aria-current="page"' in attributes) == (slug == 'east')
    assert html.index(navs[0]) < html.index('<h1')
    assert not re.search(r'<a\b[^>]*>\s*Расчет (?:наработки ЕГО|замыкающей цены)\s*</a>', html)
    assert 'Модуль «Рациональная структура»' in html


@pytest.mark.parametrize('args,expected_years,bounds', [
    ({}, [2042, 2042, 2041], (2041, 2042)),
    ({'start_year': '2041', 'end_year': '2042'}, [2042, 2042, 2041], (2041, 2042)),
    ({'start_year': '2042', 'end_year': '2042'}, [2042, 2042], (2042, 2042)),
    ({'start_year': '2041', 'end_year': '2041'}, [2041], (2041, 2041)),
    ({'start_year': '2042', 'end_year': '2041'}, [2042, 2042, 2041], (2041, 2042)),
    ({'start_year': '2042'}, [2042, 2042], (2042, 2042)),
    ({'end_year': '2041'}, [2041], (2041, 2041)),
    ({'year': '2041', 'start_year': '2042', 'end_year': '2042'}, [2042, 2042], (2042, 2042)),
])
def test_marginal_period_keeps_file_order_and_includes_boundaries(calculation_database, args, expected_years, bounds):
    context = build_marginal_price_context(MultiDict(args), 1)
    assert [row['values']['A'] for row in context['rows']] == expected_years
    assert (context['start_year'], context['end_year']) == bounds
    assert context['total'] == len(expected_years)
    assert [row['source_row'] for row in context['rows']] == sorted(row['source_row'] for row in context['rows'])


def test_marginal_period_controls_above_header_and_vertical_years(calculation_database, http_client, monkeypatch):
    import re
    from app.rational_structure.routes import marginal_price_routes

    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    html = client.get('/rational_structure/marginal_price?start_year=2041&end_year=2042').get_data(as_text=True)
    assert 'Год начала:' in html and 'Год конца:' in html
    assert 'Расчетный год:' not in html
    for field, year in [('start_year', 2041), ('end_year', 2042)]:
        select = re.search(r'<select[^>]*name="' + field + r'"[^>]*>(.*?)</select>', html, re.S).group(1)
        assert re.search(r'<option value="' + str(year) + r'"\s+selected', select)
        assert html.index('id="' + field + '"') < html.index('<thead')
    tbody = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', tbody, re.S)
    headings = re.findall(r'<tr class="rs-year-heading"><th scope="rowgroup" colspan="(\d+)"><strong>(\d+)</strong></th></tr>', tbody)
    visible_columns = re.findall(r'data-column-key="([^"]+)"', html)
    assert [year for _, year in headings] == ['2042', '2041']
    assert all(int(span) == len(visible_columns) for span, _ in headings)
    assert 'A' not in visible_columns
    data_rows = [row for row in rows if '<td' in row]
    values = [re.sub(r'\s+', '', re.search(r'<td\b[^>]*>(.*?)</td>', row, re.S).group(1)) for row in data_rows]
    assert values == ['1', '2', '1']
    assert [len(re.findall(r'<td\b', row)) for row in data_rows] == [len(visible_columns), len(visible_columns) - 1, len(visible_columns)]
    assert re.findall(r'rowspan="(\d+)" data-annual-energy-year="(\d+)"', tbody) == [('2', '2042'), ('1', '2041')]
    assert 'aria-label="Формула: Годовая энергия, млн кВт·ч"' in html
    assert 'text-end' not in tbody
    assert tbody.index('<strong>2042</strong>') < tbody.index('<td') < tbody.index('<strong>2041</strong>')
    assert html.index('id="calculation-filter-form"') < html.index('Найдено строк:')
    assert re.search(r'<option value="-1"\s+selected>Целое число</option>', html)
    assert html.count('form="calculation-filter-form"') >= 2


@pytest.mark.parametrize('args,expected', [({}, -1), ({'rounding_digits': '3'}, 3), ({'rounding_digits': '0'}, 0)])
def test_marginal_display_rounding_and_hidden_year_do_not_change_saved_data(calculation_database, args, expected):
    context = build_marginal_price_context(MultiDict(args), 1)
    assert context['rounding_digits'] == expected
    assert 'A' not in {column['key'] for column in context['table']['columns']}
    saved = context['workbook'].data['europe']
    assert 'A' in {column['key'] for column in saved['columns']}
    assert context['rows'][0]['values']['A'] == 2042
    assert context['rows'][0]['values']['C'] == Decimal('1.23456789')
    assert saved['rows'][0]['values']['C'] == '1.23456789'


def test_hub_groups_report_analysis_input_and_result_buttons(http_client):
    import re
    client, _ = http_client
    html = client.get("/rational_structure/").get_data(as_text=True)
    sections = re.findall(r"<section\b[^>]*>(.*?)</section>", html, re.S)
    assert len(sections) == 4
    assert "Отчетные данные" in sections[0] and sections[0].count("<a ") == 4
    assert "Анализ данных" in sections[1] and sections[1].count("<a ") == 2
    assert '/equipment_runtime"' in sections[1] and '/marginal_price"' in sections[1]
    assert "Исходные значения для рассчета" in sections[2] and sections[2].count("<a ") == 2
    assert "Рассчитанные значения" in sections[3] and sections[3].count("<a ") == 2
    assert "<table " not in sections[3]
    assert "<button " not in sections[3]
    assert '/calculated_values/technologies"' in sections[3]
    assert '/calculated_values/powers"' in sections[3]
    assert html.index("<hr ") > html.index("Расчет замыкающей цены")
    assert html.index("<hr ") < html.index('aria-label="Исходные значения для рассчета"')
