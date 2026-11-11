import re

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from test_territory_technologies import database, territory_database, workbook
from app.api.routes.exchange_api_routes import exchange_api_bp
from app.api.services import rational_struct_import_to_java_exchange_services as service
from app.api.services.output_documents_excel_export_services import (
    build_dataset_excel_bytes,
    load_output_document_payload_for_excel,
)
from app.extensions import db
from app.rational_structure.models import TerritoryTechnology
from app.rational_structure.services.territory_technology_services import import_territory_inputs
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


@pytest.fixture
def technologies(territory_database, monkeypatch):
    import_territory_inputs(workbook(), 1, "tester", "technologies.xlsx")
    import_territory_inputs(workbook(power=999), 2, "tester", "other.xlsx")
    db.session.execute(TechnologyType.__table__.insert(), {
        "id": 10, "name": "АЭС", "database_version_id": 1,
    })
    record = db.session.scalar(select(TerritoryTechnology).where(
        TerritoryTechnology.database_version_id == 1,
    ))
    record.technology_type_id = 10
    record.fuel_category = "other"
    record.minimum_power = 0.25
    record.co2_per_fuel = 123
    record.co2_per_energy = 10.43
    db.session.commit()
    monkeypatch.setattr(service, "get_current_year_info", lambda version_id: {"current_year": 2025})
    return record


def test_dataset_matches_contract_and_source_values(technologies):
    payload = service.load_rational_struct_import_to_java_dataset(version_id=1, year=2026)
    assert payload["dataset"] == "rational_struct_import_to_java"
    assert payload["database_version"] == payload["version"] == 1
    assert payload["version_number"] == "v1"
    assert len(payload["rows"]) == 1
    row = dict(payload["rows"][0])
    assert payload["comment"] == (
        "Год - значение, для которого производится расчет рац. структуры, например, 2026. "
        "По умолчанию используется год окончания периода Генеральной схемы "
        "со страницы /refdata/ выбранной версии БД. "
        "Исходное приближенное значение отсутствует в АРМ ГС и передается как null. "
        "external_code - отсутствует в АРМ ГС и передается как null"
    )
    assert row == {
        "Тип технологии": "АЭС",
        "Тип топлива для технологии": "атомное",
        "Год": 2026,
        "Код энергозоны (код, используемый при задании исходных данных)": 1,
        "Ред., МВт": 600,
        "Рmin, МВт": 150,
        "КИУМ по квартально (1)": 1,
        "КИУМ по квартально (2)": 1,
        "КИУМ по квартально (3)": 1,
        "КИУМ по квартально (4)": 1,
        "СКО, о.е.": 0,
        "Капитальные затраты, млн. руб./МВт": 324.87,
        "Затраты на модернизацию, млн руб./МВт": 0,
        "Топл.затраты (ОЗП), руб./кВт.ч": 0.30965,
        "Топл.затраты (ВЛП), руб./кВт.ч": 0.30965,
        "Усл.пост.затраты, млн руб./МВт.год": 11,
        "Затраты на передачу ЕНЭС, руб./кВт.ч": 0.33,
        "Вер-ть простоя (ОЗП)": 0.14796,
        "Вер-ть простоя (ВЛП)": 0.14796,
        "Эмиссия СО2": 10.43,
        "Количество единиц или МВт на год конца ПДП. Мин.": 1,
        "Количество единиц или МВт на год конца ПДП. Мод.": 0,
        "Количество единиц или МВт на год конца ПДП. Макс.": 4,
        "Исходное приближенное значение": None,
        "external_code": None,
    }


@pytest.mark.parametrize("filters, expected_years", [
    ({}, [2042]),
    ({"year": 2026}, [2026]),
    ({"start_year": 2042, "end_year": 2042}, [2042]),
    ({"start_year": 2043}, []),
    ({"end_year": 2041}, []),
])
def test_calculation_year_and_range_filter(technologies, filters, expected_years):
    payload = service.load_rational_struct_import_to_java_dataset(version_id=1, **filters)
    assert [row["Год"] for row in payload["rows"]] == expected_years


@pytest.mark.parametrize("current_year, expected_year", [(2025, 2042), (2029, 2042), (2030, 2048), (0, None)])
def test_default_year_matches_general_scheme_period(technologies, monkeypatch, current_year, expected_year):
    monkeypatch.setattr(service, "get_current_year_info", lambda version_id: {
        "current_year": current_year, "sipr_end": 2031,
    })
    payload = service.load_rational_struct_import_to_java_dataset(version_id=1)
    assert [row["Год"] for row in payload["rows"]] == ([expected_year] if expected_year else [])


def test_empty_version_has_no_mock_rows(territory_database):
    assert service.load_rational_struct_import_to_java_dataset(version_id=1, year=2026)["rows"] == []


@pytest.mark.parametrize("fuel, expected", [("gas", "газ"), ("coal", "уголь"), (None, "")])
def test_fuel_reference_and_full_technology_name(technologies, fuel, expected):
    technologies.name = "ТЭЦ-130 ата_газ"
    technologies.fuel_category = fuel
    row = service.build_rational_struct_import_row(technologies, 2026)
    assert row["Тип технологии"] == "ТЭЦ-130 ата_газ"
    assert row["Тип топлива для технологии"] == expected


def test_null_and_zero_values_are_not_replaced(technologies):
    technologies.minimum_power = None
    technologies.capital_cost = None
    technologies.co2_per_energy = None
    row = service.build_rational_struct_import_row(technologies, 2026)
    assert row["Рmin, МВт"] is None
    assert row["Капитальные затраты, млн. руб./МВт"] is None
    assert row["Эмиссия СО2"] is None
    assert row["Количество единиц или МВт на год конца ПДП. Мод."] == 0
    technologies.minimum_power = 0
    assert service.build_rational_struct_import_row(technologies, 2026)["Рmin, МВт"] == 0
    technologies.unit_power = None
    assert service.build_rational_struct_import_row(technologies, 2026)["Рmin, МВт"] is None


def test_external_code_is_null_regardless_of_technology_and_zone(technologies):
    assert service.build_rational_struct_import_row(technologies, 2026)["external_code"] is None
    technologies.unit_power = 700
    technologies.name = "Другая технология"
    technologies.energy_zone.ref_uuid = "00000000-0000-0000-0000-000000000002"
    assert service.build_rational_struct_import_row(technologies, 2030)["external_code"] is None


def test_api_exports_selected_version_and_handles_unknown_version(technologies, territory_database):
    territory_database.register_blueprint(exchange_api_bp, url_prefix="/api")
    client = territory_database.test_client()
    response = client.get("/api/datasets/1/rational_struct_import_to_java?year=2026")
    assert response.status_code == 200
    assert response.json["rows"][0]["Ред., МВт"] == 600
    assert response.json["rows"][0]["Год"] == 2026
    assert response.json["rows"][0]["external_code"] is None
    other = client.get("/api/datasets/2/rational_struct_import_to_java?year=2026")
    assert other.status_code == 200
    assert other.json["rows"][0]["Ред., МВт"] == 999
    missing = client.get("/api/datasets/999/rational_struct_import_to_java")
    assert missing.status_code == 404
    assert missing.json["error"] == "unknown_database_version"


def test_excel_uses_same_dataset_and_preserves_numeric_values(technologies):
    payload = load_output_document_payload_for_excel("rational_struct_import_to_java", database_version=1)
    workbook = load_workbook(build_dataset_excel_bytes(payload))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    values = dict(zip(headers, [cell.value for cell in sheet[2]]))
    assert sheet.max_row == 2
    assert values["Рmin, МВт"] == 150
    assert values["Год"] == 2042
    assert values["Эмиссия СО2"] == 10.43
    assert values["Исходное приближенное значение"] is None
    assert "external_code" in headers
    assert values["external_code"] is None


@pytest.mark.parametrize("selected_version_id", [1, None])
@pytest.mark.parametrize("is_admin", [True, False])
def test_transfer_page_renders_active_json_and_excel_links(territory_database, selected_version_id, is_admin):
    from pathlib import Path
    from types import SimpleNamespace

    from flask.templating import render_template
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

    from app.api.routes.database_versions_api_routes import database_versions_api_bp
    from app.api.services.output_documents_catalog import build_output_document_groups
    from app.start.routes.start_routes import start_bp
    from app.rational_structure.routes import rational_structure_module_bp

    territory_database.register_blueprint(rational_structure_module_bp, url_prefix="/rational_structure")
    territory_database.register_blueprint(exchange_api_bp, url_prefix="/api")
    territory_database.register_blueprint(database_versions_api_bp, url_prefix="/api")
    territory_database.register_blueprint(start_bp)
    territory_database.jinja_loader = ChoiceLoader([
        DictLoader({"hub_base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(Path(__file__).resolve().parents[2] / "app" / "templates"),
    ])
    with territory_database.test_request_context():
        html = render_template(
            "output_documents_transfer.html",
            current_user=SimpleNamespace(is_authenticated=True, is_admin=is_admin),
            versions=[{"database_version": 1, "version_number": "v1"}] if selected_version_id else [],
            selected_version_id=selected_version_id,
            json_groups=build_output_document_groups(),
        )
    upcoming = {
        'daymonth_info', 'general_info', 'generation_machines_changes',
        'generation_stations_changes', 'hour_info', 'month_info',
    }
    future = {
        'line_capital_investments', 'newlines_building',
        'substations_customers_info', 'substations_load_info',
        'substations_overload_transformer', 'substations_transformer_info',
    }
    assert html.count('class="home-outline__soon-mark"') == len(upcoming) + len(future) + 1
    assert re.search(
        r'load_forecast\.json<span class="home-outline__soon-mark"[^>]*>'
        r'<i class="bi bi-files" aria-hidden="true"></i>Дубль</span>',
        html,
    )
    for dataset in future:
        assert re.search(
            re.escape(dataset + '.json')
            + r'<span class="home-outline__soon-mark"[^>]*>'
            + r'<i class="bi bi-calendar-event" aria-hidden="true"></i>Перспектива</span>',
            html,
        )
    for dataset in upcoming:
        assert re.search(
            re.escape(dataset + '.json')
            + r'<span class="home-outline__soon-mark"[^>]*>'
            + r'<i class="bi bi-clock" aria-hidden="true"></i>Скоро</span>',
            html,
        )
    sections = re.findall(r'<section\b[^>]*>.*?</section>', html, re.DOTALL)
    sipr_index = next(i for i, section in enumerate(sections) if 'gs_sipr' in section)
    import_section = sections[sipr_index + 1]
    assert 'IMPORT_GS_TO_EE' in import_section
    assert 'import_gs_to_ee_zam_cena.json' in import_section
    assert 'Скоро' not in import_section
    if selected_version_id:
        assert 'href="/api/datasets/1/import_gs_to_ee_zam_cena"' in import_section
    else:
        assert 'aria-disabled="true"' in import_section
        assert '/api/datasets/1/import_gs_to_ee_zam_cena' not in html
    if selected_version_id and is_admin:
        assert ('href="/output_documents_transfer/export_excel/'
                'import_gs_to_ee_zam_cena?database_version=1"') in import_section
        assert 'class="output-doc-excel-btn output-doc-excel"' in import_section
    if selected_version_id:
        assert 'href="/api/datasets/1/general_info"' in html
        assert 'href="/api/datasets/1/load_forecast"' in html
        for dataset in future:
            link = next(
                link for link in re.findall(r'<a\b[^>]*>.*?</a>', html, re.DOTALL)
                if f'href="/api/datasets/1/{dataset}"' in link
            )
            assert 'class="home-outline__tile output-doc-dataset output-doc-future"' in link
            assert 'aria-disabled' not in link
            assert 'is-disabled' not in link
        assert html.count('class="home-outline__tile output-doc-dataset output-doc-future"') == len(future)
        assert 'href="/api/datasets/1/rational_struct_import_to_java"' in html
    if selected_version_id and is_admin:
        assert ('href="/output_documents_transfer/export_excel/'
                'rational_struct_import_to_java?database_version=1"') in html
    if not is_admin:
        assert 'class="output-doc-excel-btn' not in html

    section = html.split('rational_struct_calc', 1)[1].split('</section>', 1)[0]
    assert section.count('href="/rational_structure/calculated_values/') == 2
    filenames = re.findall(r'<span>(rational_struct_[^<]+\.json)</span>', section)
    assert filenames == [
        'rational_struct_export_from_java_powers.json',
        'rational_struct_export_from_java_technologies.json',
        'rational_struct_functionals.json',
        'rational_struct_import_to_java.json',
        'rational_struct_k0.json',
        'rational_struct_load_graf_import_to_java.json',
        'rational_struct_zones.json',
    ]
    for dataset in (
        'rational_struct_functionals',
        'rational_struct_k0', 'rational_struct_load_graf_import_to_java',
        'rational_struct_zones',
    ):
        mock_button = next(
            link for link in re.findall(r'<a\b[^>]*>.*?</a>', section, re.DOTALL)
            if f'href="/static/mocks/{dataset}.json"' in link
        )
        assert 'class="home-outline__tile output-doc-mock"' in mock_button
        assert 'is-disabled' not in mock_button
        assert 'aria-disabled' not in mock_button
        assert 'target="_blank"' in mock_button
        assert 'data-dataset=' not in mock_button
        assert f'/export_excel/{dataset}' not in section
    links = re.findall(r'<a\b[^>]*>.*?</a>', section, re.DOTALL)
    for key in ('powers', 'technologies'):
        dataset = f'rational_struct_export_from_java_{key}'
        api_url = 'http://10.31.224.135:8080/api/v1/external-sync/views/ge_stage/v_' + dataset
        wide_button = next(link for link in links if f'href="{api_url}"' in link)
        interface_button = next(
            link for link in links
            if f'href="/rational_structure/calculated_values/{key}"' in link
        )
        assert 'class="home-outline__tile output-doc-result"' in wide_button
        assert 'output-doc-mock' not in wide_button
        assert f'<span>{dataset}.json</span>' in wide_button
        assert 'class="output-doc-interface-btn"' in interface_button
        assert 'bi-table' in interface_button
        assert 'aria-label="Открыть интерфейс приема данных:' in interface_button
        for button in (wide_button, interface_button):
            assert 'target="_blank"' in button
            assert 'rel="noopener noreferrer"' in button
            assert 'data-no-preloader' in button
            assert 'data-dataset=' not in button
