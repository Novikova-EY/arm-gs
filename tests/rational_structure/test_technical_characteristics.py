from io import BytesIO
from decimal import Decimal
from html import unescape
import json
import re
from urllib.parse import parse_qs, urlsplit
from importlib import import_module

import pytest
from flask import Flask
from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

for module in ("electrical_intensity", "economics", "energy_consumption", "energy_balance", "power_demand", "ecology", "territories"):
    import_module(f"app.{module}.models")

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_name_model import PGUMachineName
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TechnicalInspectionCode, TurbineTechnicalCharacteristic as Turbine
from app.rational_structure.services.technical_characteristic_columns import COLUMNS
from app.rational_structure.services.technical_characteristic_excel_services import read_technical_characteristics
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_page_services import build_technical_characteristic_context
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.years.year_model import Year
from app.common.services.help_services import format_decimal_for_display, format_number_trim_trailing
from config import END_YEAR, START_YEAR, SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA

REAL_SESSION = db.session


def workbook_bytes(*, power=60, duplicate=False, invalid_gas=False, missing_gas=False,
                   formula=False, report_year=2023, extra_rows=(), equipment_types=None, row_data=None):
    if equipment_types is not None:
        return equipment_workbook_bytes(equipment_types, report_year, row_data)
    book = Workbook()
    book.remove(book.active)
    for name in ("Турбины паровые", "Турбины газовые"):
        if missing_gas and name == "Турбины газовые":
            continue
        sheet = book.create_sheet(name)
        for column, (_, label, _) in enumerate(COLUMNS, 1):
            parts = label.split(" / ")
            sheet.cell(1, column, parts[0])
            if len(parts) > 1:
                sheet.cell(2, column, parts[1])
            else:
                sheet.merge_cells(start_row=1, end_row=3, start_column=column, end_column=column)
        sheet.merge_cells("N1:O1")
        sheet.merge_cells("AB1:AD1")
        sheet.cell(1, 38, "Температура газов, °C")
        sheet.merge_cells("AL1:AL3")
        data = {
            "equipment_code": "001000465562", "report_year": report_year,
            "equipment_kind": "Паровые турбины" if name.endswith("паровые") else "Газовые турбины",
            "subject_name": "АО Тест", "station_name": "Тестовая ТЭЦ", "station_number": "10ПТ",
            "equipment_brand": "ПТ-60", "installed_electric_power": power,
            "total_heat_power": 131, "district_heat_power": 55,
            "electricity_generation": 0, "standard_service_life": "40 (220000)",
            "extension_count": 2, "extension_decision": "31, 30.11.2021", "assigned_service_life": "276476",
        }
        if invalid_gas and name.endswith("газовые"):
            data["installed_electric_power"] = "не число"
        if formula:
            data["installed_electric_power"] = "=30+30"
        for column, (attr, _, _) in enumerate(COLUMNS, 1):
            if attr in data:
                sheet.cell(4, column, data[attr])
        sheet.cell(4, 38, 525)
        if duplicate:
            sheet.append([cell.value for cell in sheet[4]])
        for overrides in extra_rows:
            row = dict(data, **overrides)
            sheet.append([row.get(attr) for attr, _, _ in COLUMNS] + [525])
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def equipment_workbook_bytes(equipment_types, report_year, row_data):
    from app.rational_structure.equipment_types import EQUIPMENT_TYPES, SHEET_TYPES
    from app.rational_structure.services.technical_characteristic_columns import columns_for_equipment

    book = Workbook()
    book.remove(book.active)
    for equipment_type in equipment_types:
        name = next(name for name, kind in SHEET_TYPES.items() if kind == equipment_type)
        sheet = book.create_sheet(name)
        columns = columns_for_equipment(equipment_type)
        sheet.append([label for _, label, _ in columns])
        data = {
            "equipment_code": "001000465562", "report_year": report_year,
            "equipment_kind": EQUIPMENT_TYPES[equipment_type],
            "subject_name": "АО Тест", "station_name": "Тестовая ТЭЦ",
            "station_number": "10ПТ", "equipment_brand": "ПТ-60",
            "installed_electric_power": 60, "design_head": "91,2",
            "steam_capacity": 420, "fuel_project": "Уголь", "fuel_main": "Уголь",
            "fuel_reserve": "Мазут", "efficiency_gross": "88,56", "heat_output": 979082,
            "heat_power": 100, "water_consumption": 2140, "operation_mode": "Пиковый",
            "standard_service_life": "16" if equipment_type == "boiler_water" else "40",
        }
        data.update((row_data or {}).get(equipment_type, {}))
        sheet.append([data.get(attr) for attr, _, _ in columns])
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def test_read_both_sheets_with_merged_headers():
    steam, gas = read_technical_characteristics(workbook_bytes(power="60,25"), 2023)
    assert (steam["turbine_type"], gas["turbine_type"]) == ("steam", "gas")
    assert steam["equipment_code"] == "001000465562"
    assert steam["station_number"] == "10ПТ"
    assert steam["installed_electric_power"] == Decimal("60.25")
    assert (steam["total_heat_power"], steam["district_heat_power"]) == (131, 55)
    assert steam["electricity_generation"] == 0
    assert steam["standard_service_life"] == "40 (220000)"
    assert steam["extension_count"] == 2
    assert steam["extension_decision"] == "31, 30.11.2021"
    assert steam["assigned_service_life"] == "276476"
    assert gas["extra_values"]["Температура газов, °C"] == "525"


@pytest.mark.parametrize("options, message", [
    ({"missing_gas": True}, "отсутствуют листы"),
    ({"duplicate": True}, "повтор кода"),
    ({"invalid_gas": True}, "ожидается число"),
    ({"formula": True}, "замените формулы"),
])
def test_invalid_workbook_reports_error(options, message):
    with pytest.raises(ValueError, match=message):
        read_technical_characteristics(workbook_bytes(**options), 2023)


def test_invalid_zip_is_user_error():
    with pytest.raises(ValueError, match="Не удалось прочитать"):
        read_technical_characteristics(b"not excel", 2023)


@pytest.fixture
def database(monkeypatch):
    app = Flask(__name__)
    app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://", SQLALCHEMY_ENGINE_OPTIONS={
        "execution_options": {"schema_translate_map": {
            SCHEMA_RATIONAL_STRUCTURE: None, SCHEMA_REFDATA: None, SCHEMA_GENERATION: None, SCHEMA_FUEL: None,
        }},
    })
    monkeypatch.setattr(db, "session", REAL_SESSION)
    db.init_app(app)
    with app.app_context():
        for model in (DatabaseVersion, Year, GenCompany, Station, Machine, MachineName, MachinePower,
                      PGUMachine, PGUMachineName, PGUMachinePower, Turbine, TechnicalInspectionCode):
            model.__table__.create(db.engine)
        db.session.add_all([DatabaseVersion(id=1, version_number="v1"), DatabaseVersion(id=2, version_number="v2")])
        db.session.add_all([Year(number=year, database_version_id=1) for year in (2023, 2024, 2025)])
        db.session.add(Year(number=2099, database_version_id=2))
        db.session.commit()
        yield app
        db.session.remove()


def test_reimport_updates_all_file_years_without_duplicates_and_isolates_versions(database):
    raw = workbook_bytes(extra_rows=[{"report_year": 2024, "installed_electric_power": 80}])
    first = import_technical_characteristics(raw, 1, "tester", report_year=2023)
    assert first == {"created": 4, "updated": 0, "steam": 2, "gas": 2, "matched": 0, "partial": 0, "ambiguous": 0, "unmatched": 4}
    assert {row.report_year for row in db.session.scalars(select(Turbine))} == {2023, 2024}
    import_technical_characteristics(raw, 2, "tester")
    updated = workbook_bytes(power=70, extra_rows=[{"report_year": 2024, "installed_electric_power": 999}])
    second = import_technical_characteristics(updated, 1, "tester", report_year=2023)
    assert second == {"created": 0, "updated": 4, "steam": 2, "gas": 2, "matched": 0, "partial": 0, "ambiguous": 0, "unmatched": 4}
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 8
    assert {(row.database_version_id, row.report_year, row.turbine_type): row.installed_electric_power
            for row in rows} == {
        (version, year, kind): Decimal(str(power))
        for version, year, power in ((1, 2023, 70), (1, 2024, 999), (2, 2023, 60), (2, 2024, 80))
        for kind in ("steam", "gas")
    }


@pytest.mark.parametrize("existing", [False, True])
def test_bad_second_sheet_does_not_write_first_sheet(database, existing):
    if existing:
        import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    with pytest.raises(ValueError, match="ожидается число"):
        import_technical_characteristics(workbook_bytes(power=70, invalid_gas=True), 1, "tester", report_year=2023)
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == (2 if existing else 0)
    assert all(row.installed_electric_power == Decimal("60") for row in rows)


def test_import_requires_version(database):
    with pytest.raises(ValueError, match="Выберите версию"):
        import_technical_characteristics(workbook_bytes(), None, "tester", report_year=2023)
    assert list(db.session.scalars(select(Turbine))) == []


def test_combined_page_filters_and_pagination(database):
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    import_technical_characteristics(workbook_bytes(), 2, "tester", report_year=2023)
    combined = build_technical_characteristic_context(MultiDict(), 1)
    assert combined["pagination"].total == 2
    assert combined["per_page"] == 25
    assert combined["selected_year"] == 2023
    assert {row.turbine_type for row in combined["pagination"].items} == {"steam", "gas"}
    filters = MultiDict({"turbine_type": "gas", "year": "2023", "station": "Тестовая", "search": "001000", "per_page": "9999"})
    filtered = build_technical_characteristic_context(filters, 1)
    assert filtered["pagination"].total == 1
    assert filtered["pagination"].items[0].turbine_type == "gas"
    assert filtered["per_page"] == 25
    assert filtered["years"] == [2023, 2024, 2025]
    assert "report_year" not in [column[0] for column in filtered["columns"]]
    assert "report_year" not in [column["key"] for column in filtered["header_columns"]]
    assert "Температура газов, °C" in filtered["extra_labels"]
    no_match = build_technical_characteristic_context(MultiDict({"subject": "%"}), 1)
    assert no_match["pagination"].total == 0
    assert build_technical_characteristic_context(MultiDict(), None)["pagination"].total == 0


@pytest.fixture
def http_client(database, monkeypatch):
    from pathlib import Path
    from flask import g
    from flask.templating import render_template
    from flask_login import LoginManager, UserMixin
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from app.rational_structure.routes import rational_structure_module_bp
    from app.rational_structure.routes import technical_characteristic_routes as routes

    class TestUser(UserMixin):
        id = "1"
        username = "tester"
        has_admin = True

    user = TestUser()
    database.config.update(TESTING=True, SECRET_KEY="test-only", WTF_CSRF_ENABLED=True)
    login = LoginManager(database)
    login.user_loader(lambda identity: user)
    database.before_request(lambda: setattr(g, "current_db_version", 1))
    database.register_blueprint(rational_structure_module_bp, url_prefix="/rational_structure")
    database.add_url_rule(
        "/stations/<int:station_id>/machines/<int:machine_id>",
        endpoint="station_bp.machine_details", view_func=lambda station_id, machine_id: "",
    )
    database.add_url_rule(
        "/stations/<int:station_id>/machines/<int:machine_id>/parts/<int:pgu_machine_id>",
        endpoint="station_bp.pgu_machine_details", view_func=lambda station_id, machine_id, pgu_machine_id: "",
    )
    database.add_url_rule(
        "/stations/<int:station_id>",
        endpoint="station_bp.station_details", view_func=lambda station_id: "",
    )
    database.add_url_rule(
        "/fuel/equipment_group/<int:equipment_group_id>",
        endpoint="fuel_bp.equipment_group_details", view_func=lambda equipment_group_id: "",
    )
    database.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).resolve().parents[2] / "app" / "templates")),
    ])
    database.jinja_env.filters["format_decimal"] = format_decimal_for_display
    database.jinja_env.filters["trim_decimal"] = format_number_trim_trailing
    monkeypatch.setattr(routes, "render_template", render_template)
    monkeypatch.setattr(routes, "log_to_db", lambda *args, **kwargs: None)
    client = database.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client, user


def test_http_page_renders_combined_table(http_client):
    client, _ = http_client
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    response = client.get("/rational_structure/technical_characteristics")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Паровые турбины" in html
    assert "Газовые турбины" in html
    assert "001000465562" in html
    assert "Температура газов, °C" in html
    assert 'name="csrf_token"' in html
    assert 'role="tab"' not in html
    assert 'id="rsFiltersCollapse"' not in html
    assert 'rs-sticky-toolbar-page' in html
    assert 'js/rational_structure/sticky_table_toolbar.js' in html
    assert "Фильтры / Поиск" not in html
    assert 'aria-controls="rsImportExportCollapse"' in html
    assert 'aria-label="Поиск по имени станции"' not in html
    assert 'aria-label="Поиск по названию агрегата"' not in html
    assert 'class="rs-filter-row mb-2"' not in html
    # turbine_type and equipment_kind columns removed from table
    assert html.count('data-value-type="text"') == len(COLUMNS) + 1
    assert 'data-filter-param="extra_Температура газов, °C"' in html
    assert 'data-filter-param="column_report_year"' not in html
    year_label = next(label for attr, label, _ in COLUMNS if attr == "report_year")
    assert year_label not in re.search(r"<thead\b.*?</thead>", html, re.S).group()
    year_select = re.search(r'<select\b[^>]*id="rs-year"[^>]*>.*?</select>', html, re.S)
    assert year_select is not None
    assert 'form="rs-filter-form"' in year_select.group()
    assert 'name="year"' in year_select.group()
    assert re.search(r'<option\b[^>]*value="2023"[^>]*selected', year_select.group())
    filter_form = re.search(r'<form\b[^>]*id="rs-filter-form"[^>]*>.*?</form>', html, re.S).group()
    assert 'id="rs-year"' not in filter_form
    assert '<select' not in filter_form
    assert '<button' not in filter_form
    assert html.index("rs-table-toolbar") < year_select.start() < html.index("<table")
    import_form = re.search(r'<form\b[^>]*id="rsImportForm"[^>]*>.*?</form>', html, re.S).group()
    import_year = re.search(r'<input\b[^>]*id="rs-import-year"[^>]*>', import_form).group()
    assert 'method="post"' in import_form
    assert all(attribute in import_year for attribute in ('type="hidden"', 'name="year"', 'value="2023"'))
    file_input = re.search(r'<input\b[^>]*id="rs-file"[^>]*>', import_form).group()
    assert all(attribute in file_input for attribute in ('class="d-none"', 'name="file"', 'accept=".xlsx"', 'required'))
    import_button = re.search(r'<button\b[^>]*id="rs-import-button"[^>]*>.*?</button>', import_form, re.S).group()
    assert 'type="button"' in import_button
    assert 'bi bi-upload' in import_button
    assert 'bi bi-file-earmark-excel' in html
    assert 'data-bs-target="#rsImportForm"' not in html
    assert 'Загрузить Excel' not in import_form


def test_http_upload_requires_admin(http_client):
    client, user = http_client
    user.has_admin = False
    response = client.post("/rational_structure/technical_characteristics/import")
    assert response.status_code == 403
    assert list(db.session.scalars(select(Turbine))) == []


def test_http_upload_requires_csrf(http_client):
    client, _ = http_client
    response = client.post("/rational_structure/technical_characteristics/import", data={
        "year": "2023", "file": (BytesIO(workbook_bytes()), "data.xlsx"),
    })
    assert response.status_code == 302
    assert list(db.session.scalars(select(Turbine))) == []


def test_database_failure_rolls_back(database, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    def fail_commit():
        raise SQLAlchemyError("test database failure")

    monkeypatch.setattr(db.session, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert list(db.session.scalars(select(Turbine))) == []


def test_station_and_aggregate_search_are_combined(database):
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    for aggregate in ("ПТ-60", "10ПТ"):
        context = build_technical_characteristic_context(MultiDict({"station": "Тестовая", "aggregate": aggregate}), 1)
        assert context["pagination"].total == 2
    for filters in ({"station": "Другая", "aggregate": "ПТ-60"}, {"station": "Тестовая", "aggregate": "%"}):
        assert build_technical_characteristic_context(MultiDict(filters), 1)["pagination"].total == 0


def test_column_filters_combine_multiple_values_numbers_and_extra_fields(database):
    import_technical_characteristics(workbook_bytes(power="60,25"), 1, "tester", report_year=2023)
    import_technical_characteristics(workbook_bytes(power=80), 2, "tester", report_year=2023)
    filters = MultiDict([
        ("column_installed_electric_power", json.dumps("60.25")),
        ("column_electricity_generation", json.dumps("0")),
        ("extra_Температура газов, °C", json.dumps("525")),
    ])
    context = build_technical_characteristic_context(filters, 1)
    assert context["pagination"].total == 2
    filters.add("column_station_name", json.dumps("Тестовая ТЭЦ", ensure_ascii=False))
    assert build_technical_characteristic_context(filters, 1)["pagination"].total == 2
    # turbine_type filter is now via buttons at top, not column filter
    # filters.setlist("column_turbine_type", [json.dumps("gas")])
    # assert [row.turbine_type for row in build_technical_characteristic_context(filters, 1)["pagination"].items] == ["gas"]
    filters.setlist("column_installed_electric_power", [json.dumps("80")])
    assert build_technical_characteristic_context(filters, 1)["pagination"].total == 0


def test_empty_column_values_and_unknown_filter_do_not_broaden_results(database):
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    steam = db.session.scalar(select(Turbine).where(Turbine.turbine_type == "steam"))
    steam.installed_electric_power = None
    steam.extra_values = {}
    db.session.commit()
    filters = MultiDict({"column_installed_electric_power": "null", "extra_Температура газов, °C": "null"})
    assert [row.turbine_type for row in build_technical_characteristic_context(filters, 1)["pagination"].items] == ["steam"]
    filters = MultiDict({"column_installed_electric_power": "not-a-number"})
    assert build_technical_characteristic_context(filters, 1)["pagination"].total == 0


def test_header_choices_sort_json_as_text_and_keep_numeric_order(database):
    details = [{"candidates": [], "differing_fields": ["station_name"]}, {},
               {"candidates": [], "differing_fields": ["installed_electric_power"]}, {}]
    for index, (power, year, detail) in enumerate(zip(
        [100, None, 2, 10], [2000, None, 1980, 1990], details,
    )):
        db.session.add(Turbine(
            database_version_id=1, turbine_type="steam", equipment_code=str(index),
            report_year=2024, installed_electric_power=power, commissioning_year=year,
            match_details=detail,
        ))
    db.session.commit()
    context = build_technical_characteristic_context(MultiDict({"year": "2024"}), 1)
    headers = {column["key"]: column for column in context["header_columns"]}
    assert [label for _, label in headers["installed_electric_power"]["options"]] == ["(Пустые)", "2", "10", "100"]
    assert [label for _, label in headers["commissioning_year"]["options"]] == ["(Пустые)", "1980", "1990", "2000"]


def test_header_choices_cover_all_pages_and_ignore_other_years_and_versions(database):
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam", equipment_code=str(index), report_year=2024,
                station_name=f"ТЭЦ-{index:03}", equipment_brand="ПТ-60")
        for index in range(55)
    ])
    db.session.add(Turbine(database_version_id=2, turbine_type="steam", equipment_code="other", report_year=2024, station_name="Чужая ТЭЦ"))
    db.session.add(Turbine(database_version_id=1, turbine_type="steam", equipment_code="other-year", report_year=2023,
                           station_name="Прошлогодняя ТЭЦ", extra_values={"Старое поле": "2023"}))
    db.session.commit()
    context = build_technical_characteristic_context(MultiDict(), 1)
    assert len(context["pagination"].items) == 25
    assert "Старое поле" not in context["extra_labels"]
    stations = next(column for column in context["header_columns"] if column["key"] == "station_name")
    assert len(stations["options"]) == 55
    assert "ТЭЦ-054" in [label for token, label in stations["options"]]
    filtered = build_technical_characteristic_context(MultiDict({"column_station_name": json.dumps("ТЭЦ-054", ensure_ascii=False)}), 1)
    assert [row.station_name for row in filtered["pagination"].items] == ["ТЭЦ-054"]


def test_pagination_and_search_preserve_multivalue_header_filters(http_client):
    client, _ = http_client
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam" if index % 2 else "gas",
                equipment_code=str(index), report_year=2024,
                station_name="Тестовая ТЭЦ", equipment_brand="ПТ-60")
        for index in range(55)
    ])
    db.session.commit()
    tokens = [json.dumps("steam"), json.dumps("gas")]
    response = client.get("/rational_structure/technical_characteristics", query_string=MultiDict([
        ("column_turbine_type", token) for token in tokens
    ] + [("station", "Тестовая"), ("aggregate", "ПТ-60"), ("year", "2024"),
         ("rounding_digits", "3"), ("per_page", "25"), ("page", "2")]))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    navigations = list(re.finditer(r'<nav\b[^>]*aria-label="Навигация по страницам"[^>]*>.*?</nav>', html, re.S))
    assert len(navigations) == 2
    assert navigations[0].end() < html.index("<table")
    assert navigations[1].start() > html.index("</table>")
    page_links = [unescape(link) for link in re.findall(r'class="page-link" href="([^"]+)"', html)]
    assert {parse_qs(urlsplit(link).query)["page"][0] for link in page_links} == {"1", "2", "3"}
    for link in page_links:
        params = parse_qs(urlsplit(link).query)
        assert urlsplit(link).path == "/rational_structure/technical_characteristics"
        assert params["column_turbine_type"] == tokens
        assert params["station"] == ["Тестовая"]
        assert params["aggregate"] == ["ПТ-60"]
        assert params["year"] == ["2024"]
        assert params["rounding_digits"] == ["3"]
        assert params["per_page"] == ["25"]
        assert len(params["page"]) == 1
    # turbine_type column removed from table, filter is now via buttons at top
    # assert html.count('type="hidden" name="column_turbine_type"') == 2
    assert len(re.findall(r"<tr\b", re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1))) == 25
    last_link = next(link for link in page_links if parse_qs(urlsplit(link).query)["page"] == ["3"])
    last_page = client.get(last_link)
    assert last_page.status_code == 200
    body = re.search(r"<tbody>(.*?)</tbody>", last_page.get_data(as_text=True), re.S).group(1)
    assert len(re.findall(r"<tr\b", body)) == 5


def test_excel_export_includes_all_filtered_rows_and_keeps_text_safe(http_client):
    client, user = http_client
    user.has_admin = False
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam", equipment_code=f"00{index}", report_year=2024,
                station_name="Тестовая ТЭЦ", equipment_brand="=1+1", installed_electric_power=Decimal("60.25"),
                extra_values={"Дополнительное поле": "=2+2"})
        for index in range(55)
    ])
    db.session.add(Turbine(database_version_id=1, turbine_type="gas", equipment_code="excluded", report_year=2024))
    db.session.add(Turbine(database_version_id=2, turbine_type="steam", equipment_code="other-version", report_year=2024))
    db.session.add(Turbine(database_version_id=1, turbine_type="steam", equipment_code="other-year", report_year=2025))
    db.session.commit()
    response = client.get("/rational_structure/technical_characteristics/export", query_string={
        "turbine_type": "steam", "page": 2, "year": 2024, "rounding_digits": -1,
    })
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    book = load_workbook(BytesIO(response.data))
    sheet = book.active
    assert sheet.max_row == 56
    assert sheet.auto_filter.ref == "A1:AJ56"
    # Export columns: COLUMNS without report_year and equipment_kind
    export_columns = [c for c in COLUMNS if c[0] not in ("report_year", "equipment_kind")]
    assert [sheet.cell(1, index + 1).value for index in range(len(export_columns))] == [label for _, label, _ in export_columns]
    # report_year is no longer exported
    # First column is equipment_code (A), second is subject_name (B)
    assert sheet["A2"].data_type == "s"
    assert sheet["A2"].value.startswith("00")
    brand_column = next(index + 1 for index, (attr, _, _) in enumerate(export_columns) if attr == "equipment_brand")
    power_column = next(index + 1 for index, (attr, _, _) in enumerate(export_columns) if attr == "installed_electric_power")
    assert sheet.cell(2, brand_column).value == "=1+1"
    assert sheet.cell(2, brand_column).data_type == "s"
    assert sheet.cell(2, power_column).value == 60.25
    assert sheet.cell(2, sheet.max_column).value == "=2+2"
    assert sheet.cell(2, sheet.max_column).data_type == "s"
    book.close()


@pytest.mark.parametrize("selected_year", [None, 2023, 2024, 2025])
def test_parser_reads_all_years_with_repeated_equipment_codes(selected_year):
    raw = workbook_bytes(extra_rows=[{"report_year": 2024, "installed_electric_power": 80}])
    records = read_technical_characteristics(raw, selected_year)
    assert len(records) == 4
    assert {(row["report_year"], row["installed_electric_power"]) for row in records} == {
        (2023, Decimal("60")), (2024, Decimal("80")),
    }


@pytest.mark.parametrize("options", [{"invalid_gas": True}, {"formula": True}, {"duplicate": True}])
def test_errors_in_any_file_year_block_entire_import(database, options):
    raw = workbook_bytes(**options, extra_rows=[{"report_year": 2024, "installed_electric_power": 80}])
    with pytest.raises(ValueError):
        import_technical_characteristics(raw, 1, "tester", report_year=2024)
    assert list(db.session.scalars(select(Turbine))) == []


@pytest.mark.parametrize("invalid_fields", [
    {"equipment_code": None}, {"equipment_code": "x" * 101},
    {"installed_electric_power": "не число"}, {"installed_electric_power": "=30+30"},
    {"installed_electric_power": "#DIV/0!"}, {"commissioning_year": 1.5},
])
def test_invalid_fields_in_other_year_block_import(database, invalid_fields):
    raw = workbook_bytes(extra_rows=[dict(invalid_fields, report_year=2024)])
    with pytest.raises(ValueError):
        import_technical_characteristics(raw, 1, "tester", report_year=2023)
    assert list(db.session.scalars(select(Turbine))) == []


@pytest.mark.parametrize("existing", [False, True])
def test_missing_selected_year_does_not_limit_import(database, existing):
    if existing:
        import_technical_characteristics(workbook_bytes(), 1, "tester")
    raw = workbook_bytes(power=99, extra_rows=[{"report_year": 2024}])
    counts = import_technical_characteristics(raw, 1, "tester", report_year=2025)
    assert counts["created"] == (2 if existing else 4)
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 4
    assert {row.report_year for row in rows} == {2023, 2024}
    assert all(row.installed_electric_power == Decimal("99") for row in rows)


def test_services_do_not_require_report_year(database):
    raw = workbook_bytes()
    assert len(read_technical_characteristics(raw)) == 2
    assert import_technical_characteristics(raw, 1, "tester")["created"] == 2


@pytest.mark.parametrize("year", [None, "", "invalid", "2024.5", "1899", "2201"])
def test_default_year_uses_latest_data_of_current_version(database, year):
    for report_year in (2023, 2026):
        import_technical_characteristics(workbook_bytes(report_year=report_year), 1, "tester", report_year=report_year)
    import_technical_characteristics(workbook_bytes(report_year=2098), 2, "tester", report_year=2098)
    context = build_technical_characteristic_context(MultiDict({} if year is None else {"year": year}), 1)
    assert context["selected_year"] == 2026
    assert context["filters"]["year"] == "2026"
    assert context["years"] == [2023, 2024, 2025, 2026]
    assert context["pagination"].total == 2
    assert {row.report_year for row in context["pagination"].items} == {2026}
    assert not context["has_active_filters"]


@pytest.mark.parametrize("year", [1900, 2023, 2025, 2200])
def test_explicit_year_filters_data_and_joins_year_choices(database, year):
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    context = build_technical_characteristic_context(MultiDict({"year": str(year)}), 1)
    assert context["selected_year"] == year
    assert context["filters"]["year"] == str(year)
    assert context["years"] == sorted({2023, 2024, 2025, year})
    assert context["pagination"].total == (2 if year == 2023 else 0)
    assert all(row.report_year == year for row in context["pagination"].items)


def test_empty_data_uses_start_year_and_versioned_reference_years(database):
    first = build_technical_characteristic_context(MultiDict(), 1)
    second = build_technical_characteristic_context(MultiDict(), 2)
    assert first["selected_year"] == second["selected_year"] == START_YEAR
    assert first["years"] == sorted({2023, 2024, 2025, START_YEAR})
    assert second["years"] == sorted({2099, START_YEAR})
    assert first["pagination"].total == second["pagination"].total == 0


def test_empty_reference_uses_config_range_plus_data_and_selected_year(database):
    db.session.execute(Year.__table__.delete().where(Year.database_version_id == 2))
    db.session.commit()
    empty = build_technical_characteristic_context(MultiDict(), 2)
    assert empty["selected_year"] == START_YEAR
    assert empty["years"] == list(range(START_YEAR, END_YEAR + 1))
    import_technical_characteristics(workbook_bytes(report_year=2199), 2, "tester", report_year=2199)
    context = build_technical_characteristic_context(MultiDict({"year": "2200"}), 2)
    assert context["years"] == sorted(set(range(START_YEAR, END_YEAR + 1)) | {2199, 2200})
    assert context["selected_year"] == 2200
    assert context["pagination"].total == 0


@pytest.mark.parametrize("value, expected", [(None, 25), ("10", 10), ("25", 25), ("50", 50),
                                            ("100", 100), ("0", 25), ("9999", 25), ("bad", 25)])
def test_per_page_options_limit_actual_rows(database, value, expected):
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam", equipment_code=str(index), report_year=2024)
        for index in range(105)
    ])
    db.session.commit()
    context = build_technical_characteristic_context(MultiDict({} if value is None else {"per_page": value}), 1)
    assert context["per_page"] == expected
    assert context["per_page_param"] == str(expected)
    assert context["pagination"].total == 105
    assert len(context["pagination"].items) == expected


def test_all_rows_is_not_capped_at_one_thousand(database):
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam", equipment_code=str(index), report_year=2024)
        for index in range(1005)
    ])
    db.session.add(Turbine(database_version_id=1, turbine_type="steam", equipment_code="other-year", report_year=2023))
    db.session.add(Turbine(database_version_id=2, turbine_type="steam", equipment_code="other-version", report_year=2024))
    db.session.commit()
    context = build_technical_characteristic_context(MultiDict({"year": "2024", "per_page": "all", "page": "99"}), 1)
    assert context["per_page"] is None
    assert context["per_page_param"] == "all"
    assert context["current_page"] == context["total_pages"] == 1
    assert context["pagination"].total == 1005
    assert len(context["pagination"].items) == 1005
    assert {row.equipment_code for row in context["pagination"].items} == {str(index) for index in range(1005)}


@pytest.mark.parametrize("value, expected", [(None, 1), ("-1", -1), ("0", 0), ("1", 1),
                                            ("2", 2), ("3", 3), ("-2", 1), ("4", 1), ("bad", 1)])
def test_rounding_context_accepts_only_supported_values(database, value, expected):
    context = build_technical_characteristic_context(MultiDict({} if value is None else {"rounding_digits": value}), 1)
    assert context["rounding_digits"] == expected


@pytest.fixture
def csrf_token(http_client):
    client, _ = http_client
    response = client.get("/rational_structure/technical_characteristics", query_string={"year": 2024})
    assert response.status_code == 200
    field = re.search(r'<input\b[^>]*name="csrf_token"[^>]*>', response.get_data(as_text=True))
    assert field is not None
    return unescape(re.search(r'value="([^"]+)"', field.group()).group(1))


@pytest.mark.parametrize("year", [None, "", "invalid", "2023.5", "1899", "2201"])
def test_http_upload_does_not_require_year_with_valid_csrf(http_client, csrf_token, year):
    client, _ = http_client
    data = {"csrf_token": csrf_token, "file": (BytesIO(workbook_bytes()), "data.xlsx")}
    if year is not None:
        data["year"] = year
    response = client.post("/rational_structure/technical_characteristics/import", data=data)
    assert response.status_code == 302
    assert len(list(db.session.scalars(select(Turbine)))) == 2
    with client.session_transaction() as session:
        assert any(category == "success" and "все годы файла" in message
                   for category, message in session["_flashes"])


@pytest.mark.parametrize("year, power", [(2023, Decimal("60")), (2024, Decimal("80"))])
def test_http_upload_imports_all_years_and_preserves_filter_in_redirect(http_client, csrf_token, year, power):
    client, _ = http_client
    raw = workbook_bytes(extra_rows=[{"report_year": 2024, "installed_electric_power": 80}])
    response = client.post("/rational_structure/technical_characteristics/import", data={
        "csrf_token": csrf_token, "year": str(year), "file": (BytesIO(raw), "data.xlsx"),
    })
    assert response.status_code == 302
    target = urlsplit(response.headers["Location"])
    assert target.path == "/rational_structure/technical_characteristics"
    assert parse_qs(target.query)["year"] == [str(year)]
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 4
    assert {(row.database_version_id, row.report_year, row.turbine_type, row.installed_electric_power)
            for row in rows} == {(1, yr, kind, Decimal(str(value)))
                                 for yr, value in ((2023, 60), (2024, 80)) for kind in ("steam", "gas")}
    with client.session_transaction() as session:
        assert any(category == "success" and "все годы файла" in message
                   for category, message in session["_flashes"])
    page = client.get(response.headers["Location"])
    assert page.status_code == 200
    import_year = re.search(r'<input\b[^>]*id="rs-import-year"[^>]*>', page.get_data(as_text=True)).group()
    assert f'value="{year}"' in import_year


def test_http_missing_filter_year_still_updates_file_years(http_client, csrf_token):
    client, _ = http_client
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    response = client.post("/rational_structure/technical_characteristics/import", data={
        "csrf_token": csrf_token, "year": "2025", "file": (BytesIO(workbook_bytes(power=99)), "data.xlsx"),
    })
    assert response.status_code == 302
    assert parse_qs(urlsplit(response.headers["Location"]).query)["year"] == ["2025"]
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 2
    assert {(row.report_year, row.installed_electric_power) for row in rows} == {(2023, Decimal("99"))}
    with client.session_transaction() as session:
        assert any(category == "success" and "все годы файла" in message
                   for category, message in session["_flashes"])


@pytest.mark.parametrize("rounding, expected", [(None, "60,3"), (-1, "60"), (0, "60,2501"),
                                               (1, "60,3"), (2, "60,25"), (3, "60,250")])
def test_html_rounding_does_not_change_database_decimals(http_client, rounding, expected):
    client, _ = http_client
    original = Decimal("60.2501")
    import_technical_characteristics(workbook_bytes(power=str(original)), 1, "tester", report_year=2023)
    args = {"year": 2023}
    if rounding is not None:
        args["rounding_digits"] = rounding
    response = client.get("/rational_structure/technical_characteristics", query_string=args)
    assert response.status_code == 200
    body = re.search(r"<tbody>(.*?)</tbody>", response.get_data(as_text=True), re.S).group(1)
    # New column order: equipment_code(0), match_status(1), machine_id(2), then rest of COLUMNS
    # installed_electric_power is at index 9 in COLUMNS (0-based), after removing equipment_code(0), report_year(1), equipment_kind(2) -> index 6 in rest_columns
    # Total index = 3 (first 3 columns) + 6 = 9
    power_index = 9
    table_rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, re.S)
    assert len(table_rows) == 2
    for row in table_rows:
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)
        assert unescape(cells[power_index]).strip() == expected
    db.session.expire_all()
    values = list(db.session.scalars(select(Turbine.installed_electric_power)))
    assert values == [original, original]
    assert all(isinstance(value, Decimal) for value in values)


@pytest.mark.parametrize("year, station", [(None, "Станция-2024"), (2023, "Станция-2023"), (2025, None)])
def test_http_year_filter_excludes_other_years_and_versions(http_client, year, station):
    client, _ = http_client
    db.session.add_all([
        Turbine(database_version_id=1, turbine_type="steam", equipment_code="same-code",
                report_year=report_year, station_name=f"Станция-{report_year}")
        for report_year in (2023, 2024)
    ])
    db.session.add(Turbine(database_version_id=2, turbine_type="steam", equipment_code="same-code",
                           report_year=2099, station_name="Станция-другой-версии"))
    db.session.commit()
    response = client.get("/rational_structure/technical_characteristics", query_string={} if year is None else {"year": year})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
    for name in ("Станция-2023", "Станция-2024", "Станция-другой-версии"):
        assert (name in body) == (name == station)
    if station is None:
        assert "Нет данных" in body
    year_select = re.search(r'<select\b[^>]*id="rs-year"[^>]*>.*?</select>', html, re.S).group()
    assert set(re.findall(r'<option\b[^>]*value="([^"]*)"', year_select)) == {"2023", "2024", "2025"}
    assert re.search(rf'<option\b[^>]*value="{2024 if year is None else year}"[^>]*selected', year_select)
    assert 'column_report_year' not in html
