from io import BytesIO
import re

import pytest
from flask.templating import render_template
from openpyxl import Workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import TerritoryTechnology, TerritoryTransferSection
from app.rational_structure.services.territory_technology_excel_services import read_territory_inputs
from app.rational_structure.services.territory_technology_services import build_territory_technology_context, import_territory_inputs
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType


def workbook(*, power=600, bad_matrix=False, zone=1, duplicate=False):
    book = Workbook()
    sheet = book.active
    sheet.title = "Технологии"
    sheet["A1"] = "Тип"
    sheet["C1"] = "ЭЗ"
    data = ["АЭС", 1, zone, power, 1, 1, 1, 1, 1, 0, 324.87, 0, 0.30965, 0.30965, 11, 0.33, 0.14796, 0.14796, None, 0, 1, 0, 4]
    for col, value in enumerate(data, 1):
        sheet.cell(4, col, value)
        if duplicate:
            sheet.cell(5, col, value)
    sheet["U141"] = 0
    sheet["V165"] = "АЭС"
    matrix = book.create_sheet("МСК + МДП")
    for index in range(1, 14):
        name = f"{index}--Б"
        matrix.cell(1, index + 1, name)
        matrix.cell(1, index + 16, index)
        matrix.cell(index + 1, 1, index)
        matrix.cell(index + 1, 16, name)
        matrix.cell(index + 1, 32, index * 100)
        matrix.cell(index + 1, 33, index * 90)
        for other in range(1, 14):
            matrix.cell(index + 1, other + 1, int(other == index))
            matrix.cell(index + 1, other + 16, int(other <= index))
    if bad_matrix:
        matrix["Q14"] = 2
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


@pytest.fixture
def territory_database(database):
    for model in (YearFeature, EnergyZone, TechnologyType, EquipmentGroupType, TerritoryTechnology, TerritoryTransferSection):
        model.__table__.create(db.engine)
    for version in (1, 2):
        db.session.execute(EnergyZone.__table__.insert(), [
            {"database_version_id": version, "number": str(number), "name": f"Зона {version}-{number}"}
            for number in range(1, 15)
        ])
    db.session.commit()
    return database


def test_formula_uses_cached_result_without_recalculation():
    from zipfile import ZipFile
    source = BytesIO(workbook())
    target = BytesIO()
    with ZipFile(source) as original, ZipFile(target, "w") as result:
        for name in original.namelist():
            data = original.read(name)
            if name == "xl/worksheets/sheet1.xml":
                data = data.replace(b'<c r="D4" t="n"><v>600</v></c>',
                                    b'<c r="D4"><f>300+300</f><v>600</v></c>')
            result.writestr(name, data)
    technologies, _ = read_territory_inputs(target.getvalue())
    assert technologies[0]["unit_power"] == 600


def test_read_workbook_preserves_values_and_both_matrices():
    technologies, sections = read_territory_inputs(workbook())
    assert len(technologies) == 1
    row = technologies[0]
    assert (row["unit_power"], row["capital_cost"], row["co2_per_fuel"], row["co2_per_energy"]) == (600, 324.87, None, 0)
    assert (row["quantity_min"], row["quantity_mod"], row["quantity_max"]) == (1, 0, 4)
    assert len(sections) == 13
    assert sections[1]["zone_membership"]["1"] == 1
    assert sections[1]["zone_paths"]["1"] == 0
    assert (sections[1]["forward_limit"], sections[1]["reverse_limit"]) == (200, 180)


@pytest.mark.parametrize("options, message", [
    ({"power": "=300+300"}, "нет сохраненного результата"),
    ({"bad_matrix": True}, "ожидается 0 или 1"),
    ({"duplicate": True}, "Повтор технологии"),
])
def test_invalid_workbook_does_not_partially_update(territory_database, options, message):
    import_territory_inputs(workbook(), 1, "tester", "original.xlsx")
    with pytest.raises(ValueError, match=message):
        import_territory_inputs(workbook(**options), 1, "tester", "bad.xlsx")
    db.session.expire_all()
    assert db.session.scalar(select(TerritoryTechnology)).unit_power == 600
    assert len(list(db.session.scalars(select(TerritoryTransferSection)))) == 13


def test_reimport_is_idempotent_and_version_scoped(territory_database):
    first = import_territory_inputs(workbook(), 1, "tester", "original.xlsx")
    assert first == {"created": 14, "updated": 0, "technologies": 1, "sections": 13}
    import_territory_inputs(workbook(power=700), 2, "tester", "other.xlsx")
    updated = import_territory_inputs(workbook(power=800), 1, "tester", "update.xlsx")
    assert updated["created"] == 0 and updated["updated"] == 14
    assert {row.database_version_id: row.unit_power for row in db.session.scalars(select(TerritoryTechnology))} == {1: 800, 2: 700}


def test_unknown_zone_and_missing_version_do_not_write(territory_database):
    for version, options, message in ((None, {}, "Выберите версию"), (1, {"zone": 99}, "отсутствуют энергозоны")):
        with pytest.raises(ValueError, match=message):
            import_territory_inputs(workbook(**options), version, "tester", "test.xlsx")
    assert list(db.session.scalars(select(TerritoryTechnology))) == []
    assert list(db.session.scalars(select(TerritoryTransferSection))) == []


@pytest.mark.parametrize("params, expected", [
    ({}, 1),
    ({"rounding_digits": "invalid"}, 1),
    ({"rounding_digits": "5"}, 1),
    *[({"rounding_digits": str(digits)}, digits) for digits in (-1, 0, 1, 2, 3, 6)],
])
def test_rounding_defaults_to_one_digit_and_preserves_explicit_choice(territory_database, params, expected):
    context = build_territory_technology_context(MultiDict(params), 1)
    assert context["rounding_digits"] == expected


def test_page_filters_use_zone_from_current_version(territory_database):
    import_territory_inputs(workbook(), 1, "tester", "test.xlsx")
    import_territory_inputs(workbook(power=700), 2, "tester", "test.xlsx")
    context = build_territory_technology_context(MultiDict(), 1)
    assert len(context["rows"]) == 1 and context["rows"][0].unit_power == 600
    zone = next(zone for zone in context["zones"] if zone.number == "14")
    filtered = build_territory_technology_context(MultiDict({"energy_zone": str(zone.id)}), 1)
    assert filtered["rows"] == []
    assert filtered["matrix_zones"] == []
    from werkzeug.exceptions import BadRequest
    with pytest.raises(BadRequest):
        build_territory_technology_context(MultiDict({"energy_zone": str(zone.id)}), 2)


def test_http_import_rejects_stale_version_then_updates_selected_version(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, "log_to_db", lambda *args, **kwargs: None)
    client, _ = http_client
    territory_database.config["WTF_CSRF_ENABLED"] = False
    for version in (1, 2):
        import_territory_inputs(workbook(), version, "tester", "original.xlsx")
    for submitted_version, expected_power in (("2", 600), ("1", 900)):
        response = client.post("/rational_structure/territory_technologies/import", data={
            "database_version_id": submitted_version,
            "file": (BytesIO(workbook(power=900)), "new.xlsx"),
        })
        assert response.status_code == 302
        assert {row.database_version_id: row.unit_power for row in db.session.scalars(select(TerritoryTechnology))} == {1: expected_power, 2: 600}


def test_http_tables_render_and_import_requires_admin_and_csrf(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, "render_template", render_template)
    client, user = http_client
    import_territory_inputs(workbook(), 1, "tester", "test.xlsx")
    for sheet, expected in (("technologies", "АЭС"), ("transfers", "Матрица МСК")):
        response = client.get("/rational_structure/territory_technologies", query_string={"sheet": sheet})
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert expected in html and "Зона 2-" not in html
        scroll_start = html.index('<div class="page-table-scroll ')
        assert html.index('aria-label="Энергозоны"') < html.index('<h1') < scroll_start < html.index('<table')
        assert 'name="database_version_id" value="1"' in html
        assert 'name="csrf_token"' in html
    response = client.post("/rational_structure/territory_technologies/import", data={
        "database_version_id": "1", "file": (BytesIO(workbook(power=900)), "test.xlsx"),
    })
    assert response.status_code == 302
    assert db.session.scalar(select(TerritoryTechnology)).unit_power == 600
    user.has_admin = False
    assert client.post("/rational_structure/territory_technologies/import").status_code == 403


def test_technology_and_transfer_cells_save_without_changing_other_versions(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_cell_routes
    monkeypatch.setattr(territory_cell_routes, 'log_to_db', lambda *args, **kwargs: None)
    client, user = http_client
    territory_database.config['WTF_CSRF_ENABLED'] = False
    for version in (1, 2):
        import_territory_inputs(workbook(), version, 'tester', 'test.xlsx')
    tech = db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.database_version_id == 1))
    endpoint = '/rational_structure/territory_technologies/cell'
    payload = dict(database_version_id=1, sheet='technologies', row_id=tech.id, field='unit_power', value='750,25')
    assert client.patch(endpoint, json=payload).status_code == 200
    assert tech.unit_power == 750.25
    assert db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.database_version_id == 2)).unit_power == 600
    assert client.patch(endpoint, json=dict(payload, value='')).status_code == 200
    assert tech.unit_power is None
    assert client.patch(endpoint, json=dict(payload, field='database_version_id')).status_code == 400
    assert client.patch(endpoint, json=dict(payload, field='technology_number', value='1.5')).status_code == 400
    assert client.patch(endpoint, json=dict(payload, database_version_id=2)).status_code == 400
    other = db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.database_version_id == 2))
    assert client.patch(endpoint, json=dict(payload, row_id=other.id)).status_code == 404
    section = db.session.scalar(select(TerritoryTransferSection).where(TerritoryTransferSection.database_version_id == 1))
    payload = dict(database_version_id=1, sheet='transfers', row_id=section.id, field='forward_limit', value='500')
    assert client.patch(endpoint, json=payload).status_code == 200
    assert section.forward_limit == 500
    payload.update(field='zone_membership', zone_number='1', value='0')
    assert client.patch(endpoint, json=payload).status_code == 200
    assert section.zone_membership['1'] == 0
    assert section.zone_membership['2'] == 0
    assert client.patch(endpoint, json=dict(payload, value='2')).status_code == 400
    assert client.patch(endpoint, json=dict(payload, zone_number='99')).status_code == 400
    assert client.patch(endpoint, json=dict(payload, field='reverse_limit', value='')).status_code == 400
    user.has_admin = False
    assert client.patch(endpoint, json=payload).status_code == 403


def test_zone_subtabs_replace_dropdown_and_descriptive_text(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    import_territory_inputs(workbook(), 1, 'tester', 'test.xlsx')
    for sheet in ('technologies', 'transfers'):
        html = client.get('/rational_structure/territory_technologies', query_string={'sheet': sheet}).get_data(as_text=True)
        assert 'aria-label="Энергозоны"' in html and 'Все энергозоны</a>' in html
        zone_nav = re.search(r'<nav[^>]*aria-label="Энергозоны".*?</nav>', html, re.S).group()
        assert re.findall(r'>([^<>]+)</a>', zone_nav) == ['Все энергозоны'] + [str(number) for number in range(1, 15)]
        assert 'title="1 – Зона 1-1"' in zone_nav and 'Зона 2-' not in html
        assert '<select class="form-select w-auto" name="energy_zone"' not in html
        assert 'Версия БД:</strong>' not in html and 'Технологий:' not in html
        assert 'Пустые ячейки обозначены' not in html
        assert 'data-field="unit_power"' in html if sheet == 'technologies' else 'data-field="zone_membership"' in html


def test_technology_header_groups_match_excel_and_data_columns(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    import_territory_inputs(workbook(), 1, 'tester', 'test.xlsx')
    html = client.get('/rational_structure/territory_technologies').get_data(as_text=True)
    header = re.search(r'<thead[^>]*>(.*?)</thead>', html, re.S).group(1)
    header_rows = re.findall(r'<tr>(.*?)</tr>', header, re.S)
    assert len(header_rows) == 2
    groups = re.findall(r'<th scope="colgroup" colspan="(\d+)">(.*?)</th>', header_rows[0], re.S)
    assert groups == [
        ('4', 'КИУМ'),
        ('2', 'Топл. затраты,<br>руб./кВт·ч'),
        ('2', 'Вероятность простоя'),
        ('2', 'Эмиссия CO₂'),
        ('3', 'Количество единиц или МВт на 2042 год'),
    ]
    subheaders = re.findall(r'<th scope="col">(.*?)</th>', header_rows[1])
    assert subheaders == ['I', 'II', 'III', 'IV', 'ОЗП', 'ВЛП', 'ОЗП', 'ВЛП',
                          'кг/тут', 'г/кВт·ч', 'мин.', 'мод.', 'макс.']
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cell_count = len(re.findall(r'<(?:td|th)\b', body))
    standalone_count = header_rows[0].count('rowspan="2"')
    assert standalone_count + sum(int(span) for span, _ in groups) == cell_count
    assert standalone_count + len(subheaders) == cell_count


def test_technology_heading_identifies_selected_zone(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    zone = db.session.scalar(select(EnergyZone).where(EnergyZone.database_version_id == 1, EnergyZone.number == '2'))
    html = client.get('/rational_structure/territory_technologies', query_string={'energy_zone': zone.id}).get_data(as_text=True)
    assert '<h1 class="text-center mb-2">Технологии энергозоны 2 - Зона 1-2</h1>' in html


def test_transfer_matrices_follow_excel_axes_and_limit_positions(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    client, _ = http_client
    import_territory_inputs(workbook(), 1, 'tester', 'test.xlsx')
    section = db.session.scalar(select(TerritoryTransferSection).where(TerritoryTransferSection.name == '2--Б'))
    section.zone_paths = {**section.zone_paths, '1': 1}
    db.session.commit()
    html = client.get('/rational_structure/territory_technologies?sheet=transfers').get_data(as_text=True)
    paths = re.search(r'<table[^>]*data-transfer-matrix="paths".*?</table>', html, re.S).group()
    membership = re.search(r'<table[^>]*data-transfer-matrix="membership".*?</table>', html, re.S).group()
    assert html.index(paths) < html.index(membership)
    assert re.findall(r'<th scope="col">([^<]+)</th>', paths) == ['ЭЗ / сечение'] + [f'{number}--Б' for number in range(1, 14)]
    paths_body = re.search(r'<tbody>(.*?)</tbody>', paths, re.S).group(1)
    membership_body = re.search(r'<tbody>(.*?)</tbody>', membership, re.S).group(1)
    path_rows = re.findall(r'<tr>(.*?)</tr>', paths_body, re.S)
    membership_rows = re.findall(r'<tr>(.*?)</tr>', membership_body, re.S)
    assert len(path_rows) == len(membership_rows) == 13
    assert re.findall(r'<th scope="row"[^>]*>([^<]+)</th>', paths_body) == [str(number) for number in range(1, 14)]
    assert re.findall(r'<th scope="row">([^<]+)</th>', membership_body) == [f'{number}--Б' for number in range(1, 14)]
    # Несимметричные значения различают две матрицы и выявляют неверное транспонирование.
    assert re.findall(r'data-field="zone_paths" data-zone-number="1" data-raw="(\d)"', path_rows[0]) == ['1', '1'] + ['0'] * 11
    assert re.findall(r'data-field="zone_paths" data-zone-number="2" data-raw="(\d)"', path_rows[1]) == ['0', '1'] + ['0'] * 11
    assert re.findall(r'data-field="zone_membership" data-zone-number="\d+" data-raw="(\d)"', membership_rows[1]) == ['1', '1'] + ['0'] * 11
    assert membership_rows[1].index('data-field="zone_membership"') < membership_rows[1].index('data-field="forward_limit"') < membership_rows[1].index('data-field="reverse_limit"')
    assert re.search(r'data-limit-field="forward_limit" data-limit-sign="1">100,0</span>', paths)
    assert re.search(r'data-limit-field="reverse_limit" data-limit-sign="-1">-90,0</span>', paths)
