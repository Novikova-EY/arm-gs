from io import BytesIO
import re

import pytest
from flask.templating import render_template
from openpyxl import load_workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import TerritoryInput, TerritoryDiscountRate
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs,
)
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_service_model import YearService


@pytest.fixture
def territory_database(database):
    YearFeature.__table__.create(db.engine)
    YearService.__table__.create(db.engine)
    db.session.add_all([Year(number=year, database_version_id=1) for year in range(2026, 2043)])
    EnergyZone.__table__.create(db.engine)
    TerritoryInput.__table__.create(db.engine)
    TerritoryDiscountRate.__table__.create(db.engine)
    # Core INSERT не запускает PostgreSQL-специфичную проверку UUID справочника.
    db.session.execute(EnergyZone.__table__.insert(), [
        dict(id=1, database_version_id=1, number="1", name="Зона первая", ref_uuid="zone-1"),
        dict(id=2, database_version_id=1, number="2", name="Зона вторая", ref_uuid="zone-2"),
        dict(id=3, database_version_id=2, number="1", name="Другая версия", ref_uuid="zone-3"),
    ])
    db.session.commit()
    return database


def posted_table(context):
    form = MultiDict({"database_version_id": str(context["version_id"])})
    for row in context["rows"]:
        if not row["section"]:
            for year, value in zip(context["years"], row["cells"]):
                form[f"value_{row['key']}_{year}"] = value
            form[f"note_{row['key']}"] = row["note"]
    return form


def test_template_has_all_years_and_resource_groups(territory_database):
    context = build_territory_input_context(1, None)
    assert context["selected_zone"].id == 1
    assert context["years"] == list(range(2025, 2043))
    equipment = build_territory_input_context(1, None, sheet="equipment")
    labels = {row["label"] for row in equipment["rows"]}
    assert {"Первый ресурс", "Второй ресурс"} <= labels
    assert "ЧЧИМ" in {row["label"] for row in context["rows"]}
    assert [row["number"] for row in equipment["rows"] if row["number"]] == ["18"] * 4
    year_keys = {row["key"] for row in context["rows"]}
    equipment_keys = {row["key"] for row in equipment["rows"]}
    assert year_keys.isdisjoint(equipment_keys)
    assert year_keys | equipment_keys == {row["key"] for row in context["all_rows"]}
    assert {str(index) for index in range(29, 70)} <= equipment_keys
    assert {str(index) for index in range(117, 240)} <= equipment_keys
    assert all(row["section"] for row in context["all_rows"] if not row["unit"])
    assert all(value == "" for row in context["all_rows"] for value in row["cells"])


def test_tabs_save_independently_without_losing_other_rows(territory_database):
    equipment = build_territory_input_context(1, 1, sheet="equipment")
    form = posted_table(equipment)
    equipment_rows = [row for row in equipment["rows"] if not row["section"]]
    for index, row in enumerate(equipment_rows):
        form[f"value_{row['key']}_2025"] = str(index + 1)
        form[f"note_{row['key']}"] = f"Оборудование {index}"
    save_territory_inputs(equipment, form, "tester")
    stored_equipment = db.session.scalar(select(TerritoryInput)).rows
    equipment_keys = {row["key"] for row in equipment["rows"]}
    before = [row for index, row in enumerate(stored_equipment) if str(index) in equipment_keys]

    years = build_territory_input_context(1, 1)
    form = posted_table(years)
    form["value_6_2025"] = "123"
    form["note_6"] = "Потребление"
    save_territory_inputs(years, form, "tester")
    saved = db.session.scalar(select(TerritoryInput))
    assert before == [row for index, row in enumerate(saved.rows) if str(index) in equipment_keys]
    assert len(saved.rows) == len(years["all_rows"])

    equipment = build_territory_input_context(1, 1, sheet="equipment")
    form = posted_table(equipment)
    first = '164'
    form[f"value_{first}_2025"] = "0"
    save_territory_inputs(equipment, form, "tester")
    reloaded_years = build_territory_input_context(1, 1)
    assert reloaded_years["rows"][6]["cells"][0] == "123"
    assert reloaded_years["rows"][6]["note"] == "Потребление"
    assert next(row for row in build_territory_input_context(1, 1, sheet="equipment")["rows"]
                if row['key'] == first)['cells'][0] == '0'


def test_save_reload_clear_and_isolate_zone_and_version(territory_database):
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form["value_6_2025"] = "1 234,5678"
    form["value_6_2026"] = "0"
    form["note_6"] = "Примечание"
    save_territory_inputs(context, form, "tester")
    saved = build_territory_input_context(1, 1)
    assert saved["rows"][6]["cells"][:2] == ["1234.5678", "0"]
    assert saved["rows"][6]["note"] == "Примечание"
    assert build_territory_input_context(1, 2)["rows"][6]["cells"][0] == ""
    assert build_territory_input_context(2, 3)["rows"][6]["cells"][0] == ""
    assert [zone.id for zone in saved["zones"]] == [1, 2]
    form["value_6_2025"] = ""
    save_territory_inputs(saved, form, "tester")
    assert build_territory_input_context(1, 1)["rows"][6]["cells"][:2] == ["", "0"]
    assert len(list(db.session.scalars(select(TerritoryInput)))) == 1


@pytest.mark.parametrize("value", ["ошибка", "NaN", "Infinity", "=1+1", "1e16", "1e9999"])
def test_bad_number_does_not_save_partial_table(territory_database, value):
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form["value_6_2025"] = "100"
    form["value_8_2025"] = value
    with pytest.raises(ValueError, match="введите число"):
        save_territory_inputs(context, form, "tester")
    assert db.session.scalar(select(TerritoryInput)) is None


def test_existing_excel_data_keeps_precision_and_unitless_totals(territory_database):
    context = build_territory_input_context(1, 1)
    source_rows = [{key: row[key] for key in ("number", "label", "unit", "note", "section", "values")}
                   for row in context["all_rows"]]
    source_rows[0]["values"] = ["25371.880178047006"] + [None] * 17
    heading = next(row for row in source_rows if not row["unit"])
    heading["values"] = [125.5] + [None] * 17
    db.session.add(TerritoryInput(database_version_id=1, energy_zone_id=1, years=context["years"],
                                 rows=source_rows, source_filename="existing.xlsx"))
    db.session.commit()
    loaded = build_territory_input_context(1, 1)
    total = next(row for row in loaded["rows"] if row["label"] == heading["label"])
    assert not total["section"]
    assert total["cells"][0] == "125.5"
    save_territory_inputs(loaded, posted_table(loaded), "tester")
    assert build_territory_input_context(1, 1)["rows"][0]["cells"][0] == "25371.880178047006"


def test_database_failure_rolls_back(territory_database, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form["value_6_2025"] = "123"

    def fail_commit():
        raise SQLAlchemyError("storage unavailable")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        save_territory_inputs(context, form, "tester")
    assert db.session.scalar(select(TerritoryInput)) is None


def test_stale_version_and_incomplete_form_are_rejected(territory_database):
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form["database_version_id"] = "2"
    with pytest.raises(ValueError, match="Версия БД изменилась"):
        save_territory_inputs(context, form, "tester")
    form["database_version_id"] = "1"
    del form["value_6_2025"]
    with pytest.raises(ValueError, match="неполная таблица"):
        save_territory_inputs(context, form, "tester")
    with pytest.raises(ValueError, match="не найдена"):
        build_territory_input_context(1, 3)
    assert build_territory_input_context(None, None)["zones"] == []


@pytest.fixture
def territory_client(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_data_routes as routes
    from app.rational_structure.services import territory_summary_services, territory_transfer_services, territory_equipment_services
    monkeypatch.setattr(territory_equipment_services, '_territory_machine_ids',
                        lambda version_id, **kwargs: {row['machine_id'] for row in
                            territory_equipment_services.load_territory_equipment_sources(version_id)[0]})
    monkeypatch.setattr(territory_equipment_services, 'load_territory_equipment_sources',
                        lambda version_id: ([], [], [], [], 2024))
    monkeypatch.setattr(territory_equipment_services, 'load_territory_station_types',
                        lambda version_id: ['АЭС', 'ГЭС', 'ТЭС', 'ВЭС', 'СЭС', 'ГАЭС', 'СНЭЭ'])
    monkeypatch.setattr(territory_equipment_services, 'load_territory_station_power_totals',
                        lambda version_id, zone_id, years: {
                            label: [0] * len(years)
                            for labels in territory_equipment_services.TERRITORY_STATION_POWER_LABELS.values()
                            for label in labels})
    monkeypatch.setattr(territory_transfer_services, "load_territory_transfer_rows", lambda version_id, zone_id, years: {
        key: {"cells": [""] * len(years), "details": []} for key in ("7", "9")
    })
    monkeypatch.setattr(territory_summary_services, "load_territory_summary_values", lambda version_id, zone_id, years: {
        "has_gaes": False, **{key: [None] * len(years) for key in
        ("consumption", "consumption_with_gaes", "max_power", "combined", "hours")},
    })
    monkeypatch.setattr(routes, "render_template", render_template)
    monkeypatch.setattr(routes, "log_to_db", lambda *args, **kwargs: None)
    from app.rational_structure.routes import territory_cell_routes
    monkeypatch.setattr(territory_cell_routes, "log_to_db", lambda *args, **kwargs: None)
    return http_client


def test_http_render_save_export_and_access(territory_client):
    client, user = territory_client
    response = client.get("/rational_structure/territory_inputs?energy_zone_id=1")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '<h1 class="text-center mb-2">Исходные данные по энергозоне 1 - Зона первая</h1>' in html
    scroll_start = html.index('<div class="page-table-scroll ')
    assert html.index('aria-label="Энергозоны"') < html.index('<h1') < scroll_start < html.index('<table')
    assert html.index('id="territory-year-form"') < scroll_start
    zone_nav = re.search(r'<nav[^>]*aria-label="Энергозоны".*?</nav>', html, re.S).group()
    assert re.findall(r'>([^<>]+)</a>', zone_nav) == ['ЕЭС России', '1', '2']
    assert 'title="1 – Зона первая"' in zone_nav and 'Другая версия' not in html
    assert 'value_6_2025' in html and 'value_6_2042' in html
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    form = posted_table(build_territory_input_context(1, 1))
    form["csrf_token"] = token
    form["value_6_2025"] = "125,5"
    form["note_6"] = "=HYPERLINK(\"bad\")"
    response = client.post("/rational_structure/territory_inputs?energy_zone_id=1", data=form)
    assert response.status_code == 302
    assert build_territory_input_context(1, 1)["rows"][6]["cells"][0] == "125.5"
    response = client.get("/rational_structure/territory_inputs/export?energy_zone_id=1")
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        assert book.active["D9"].value == 125.5
        assert book.active["V9"].data_type == "s"
        assert book.active["V9"].value.startswith("=HYPERLINK")
        assert book.active["U2"].value == 2042
    finally:
        book.close()
    user.has_admin = False
    response = client.get("/rational_structure/territory_inputs?energy_zone_id=1")
    assert 'name="value_6_2025"' not in response.get_data(as_text=True)
    assert client.post("/rational_structure/territory_inputs?energy_zone_id=1", data=form).status_code == 403
    assert client.get("/rational_structure/territory_inputs?energy_zone_id=3").status_code == 404
    assert client.get("/rational_structure/territory_inputs?energy_zone_id=bad").status_code == 400


def test_equipment_tab_renders_saves_and_exports_only_point_18(territory_client):
    client, _ = territory_client
    years_html = client.get("/rational_structure/territory_inputs?energy_zone_id=1").get_data(as_text=True)
    assert "Первый ресурс" not in years_html and "Второй ресурс" not in years_html
    query = {"sheet": "equipment", "energy_zone_id": 1}
    response = client.get("/rational_structure/territory_inputs", query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Первый ресурс" in html and "Второй ресурс" in html
    assert '<h1 class="text-center mb-2">Состав генерирующего оборудования энергозоны 1 - Зона первая</h1>' in html
    scroll_start = html.index('<div class="page-table-scroll ')
    assert html.index('aria-label="Энергозоны"') < html.index('<h1') < scroll_start < html.index('<table')
    assert html.index('id="territory-year-form"') < scroll_start
    assert 'name="value_6_2025"' not in html
    assert 'name="value_164_2025"' in html
    assert 'name="sheet" value="equipment"' in html
    assert 'sheet=equipment' in html
    assert '/territory_technologies' not in html
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    form = posted_table(build_territory_input_context(1, 1, sheet="equipment"))
    form["csrf_token"] = token
    form["value_164_2025"] = "600"
    response = client.post("/rational_structure/territory_inputs?energy_zone_id=1&sheet=equipment", data=form)
    assert response.status_code == 302
    assert "sheet=equipment" in response.headers["Location"]
    response = client.get("/rational_structure/territory_inputs/export", query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        exported = list(book.active.iter_rows(min_row=3, values_only=True))
        assert [row[3] for row in exported if row[1] == 'ГЭС до 50 МВт'] == [None, 600, None, None]
        numbers = [row[0] for row in book.active.iter_rows(min_row=3, values_only=True) if row[0]]
        assert numbers == ["18"] * 4
        assert book.active.max_row == 46 + 4 * 2 * 2
        assert sum(row[1] == 'Без группы оборудования' for row in exported) == 4 * 2 * 2
    finally:
        book.close()
    response = client.get("/rational_structure/territory_inputs/export?energy_zone_id=1")
    book = load_workbook(BytesIO(response.data))
    try:
        assert "18" not in [row[0] for row in book.active.iter_rows(min_row=3, values_only=True)]
    finally:
        book.close()
    assert client.get("/rational_structure/territory_inputs?sheet=unknown").status_code == 400
    assert client.get("/rational_structure/territory_inputs/export?sheet=unknown").status_code == 400


def test_inline_save_updates_only_target_cell_and_preserves_other_tabs(territory_client):
    client, _ = territory_client
    html = client.get('/rational_structure/territory_inputs?energy_zone_id=1').get_data(as_text=True)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    headers = {'X-CSRFToken': token}
    payload = dict(database_version_id=1, energy_zone_id=1, sheet='years', row_key='6', year=2025,
                   field='value', value='123,4567890123')
    endpoint = '/rational_structure/territory_inputs/cell'
    assert client.patch(endpoint, json=payload).status_code == 400
    response = client.patch(endpoint, json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json['value'] == '123.4567890123'
    payload.update(sheet='equipment', row_key='164', value='600')
    assert client.patch(endpoint, json=payload, headers=headers).status_code == 200
    payload.update(sheet='years', row_key='6', field='note', value='Комментарий')
    assert client.patch(endpoint, json=payload, headers=headers).status_code == 200
    context = build_territory_input_context(1, 1)
    assert context['rows'][6]['cells'][0] == '123.4567890123'
    assert context['rows'][6]['note'] == 'Комментарий'
    assert next(row for row in build_territory_input_context(1, 1, sheet='equipment')['rows']
                if row['key'] == '164')['cells'][0] == '600'
    assert build_territory_input_context(1, 2)['rows'][6]['cells'][0] == ''
    payload.update(field='value', value='')
    assert client.patch(endpoint, json=payload, headers=headers).status_code == 200
    assert build_territory_input_context(1, 1)['rows'][6]['cells'][0] == ''
    assert build_territory_input_context(1, 1)['rows'][6]['note'] == 'Комментарий'


def test_inline_save_rejects_wrong_version_fields_and_invalid_numbers(territory_client):
    client, user = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    base = dict(database_version_id=1, energy_zone_id=1, sheet='years', row_key='6', year=2025,
                field='value', value='10')
    for change in ({'database_version_id': 2}, {'energy_zone_id': 3}, {'row_key': '30'},
                   {'year': 2099}, {'field': 'database_version_id'}, {'value': 'NaN'},
                   {'value': '=1+1'}, {'sheet': []}, {'field': []}, {'value': True},
                   {'field': 'note', 'value': 'x' * 2001}):
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(base, **change))
        assert response.status_code in (400, 404)
    assert db.session.scalar(select(TerritoryInput)) is None
    user.has_admin = False
    assert client.patch('/rational_structure/territory_inputs/cell', json=base).status_code == 403


def test_inline_database_failure_is_reported_without_saving(territory_client, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False

    def fail():
        raise SQLAlchemyError('offline')

    monkeypatch.setattr(db.session, 'commit', fail)
    response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
        database_version_id=1, energy_zone_id=1, sheet='years', row_key='6', year=2025, field='value', value='10'))
    assert response.status_code == 500 and not response.json['ok']
    assert db.session.scalar(select(TerritoryInput)) is None


def test_year_toolbar_features_range_and_zone_subtabs(territory_client):
    client, _ = territory_client
    feature = YearFeature(name='план', database_version_id=1)
    other_feature = YearFeature(name='чужой признак', database_version_id=2)
    db.session.add_all([feature, other_feature])
    db.session.flush()
    for year in db.session.scalars(select(Year).where(Year.database_version_id == 1, Year.number.in_([2025, 2026]))):
        year.id_year_feature = feature.id
    db.session.commit()
    response = client.get('/rational_structure/territory_inputs?energy_zone_id=1&sheet=equipment&start_year=2026&end_year=2025&view_year=2026')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Год начала:' in html and 'Год конца:' in html and 'Пустые строки' in html
    assert 'aria-label="Годы периода"' not in html
    assert 'data-year="2026">2026<div class="small fw-normal">план</div>' in html
    assert 'чужой признак' not in html
    assert 'data-year="2026"' in html
    assert 'name="value_164_2026"' in html and 'name="value_164_2025"' not in html
    zone_nav = re.search(r'<nav[^>]*aria-label="Энергозоны".*?</nav>', html, re.S).group()
    assert re.findall(r'>([^<>]+)</a>', zone_nav) == ['ЕЭС России', '1', '2']
    assert 'title="2 – Зона вторая"' in zone_nav
    assert '<select id="territory-zone"' not in html
    assert '>Сохранить</button>' not in html
    assert 'Таблица по Excel-шаблону' not in html
    assert 'start_year=2025' in html and 'end_year=2026' in html
    response = client.get('/rational_structure/territory_inputs/export?energy_zone_id=1&start_year=2025&end_year=2026&view_year=2026')
    book = load_workbook(BytesIO(response.data))
    try:
        assert book.active['D2'].value == 2026
        assert book.active['E2'].value == 'Примечание'
    finally:
        book.close()


def test_http_csrf_and_validation_preserve_data(territory_client):
    client, _ = territory_client
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    assert client.post("/rational_structure/territory_inputs?energy_zone_id=1", data=form).status_code == 302
    html = client.get("/rational_structure/territory_inputs?energy_zone_id=1").get_data(as_text=True)
    form["csrf_token"] = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    form["value_6_2025"] = "введенное значение"
    response = client.post("/rational_structure/territory_inputs?energy_zone_id=1", data=form)
    assert response.status_code == 400
    assert "введенное значение" in response.get_data(as_text=True)
    assert db.session.scalar(select(TerritoryInput)) is None
