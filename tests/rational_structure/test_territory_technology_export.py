from io import BytesIO
import re

import pytest
from flask import g
from flask.templating import render_template
from openpyxl import load_workbook
from sqlalchemy import select

from test_territory_technologies import database, http_client, territory_database, workbook
from app.extensions import db
from app.rational_structure.models import TerritoryTechnology, TerritoryTransferSection
from app.rational_structure.services.territory_technology_services import import_territory_inputs
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone


ENDPOINT = "/rational_structure/territory_technologies/export"


@pytest.mark.parametrize("rounding, number_format", [(0, "General"), (-1, "0"), (1, "0.0"), (3, "0.000"), (6, "0.000000")])
def test_export_technologies_keeps_values_and_groups_headers(territory_database, http_client, rounding, number_format):
    client, user = http_client
    user.has_admin = False
    import_territory_inputs(workbook(power=123.456789), 1, "tester", "test.xlsx")
    import_territory_inputs(workbook(power=999), 2, "tester", "other.xlsx")
    response = client.get(ENDPOINT, query_string={"rounding_digits": rounding})
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment;" in response.headers["Content-Disposition"]
    assert "territory_technologies_all_zones_v1.xlsx" in response.headers["Content-Disposition"]
    book = load_workbook(BytesIO(response.data))
    sheet = book["Технологии"]
    assert sheet.max_row == 3 and sheet.max_column == 23
    assert [sheet.cell(1, col).value for col in range(1, 4)] == ["ЭЗ", "Название технологии", "Тип №"]
    assert (sheet["A3"].value, sheet["B3"].value, sheet["C3"].value) == ("1", "АЭС", 1)
    assert sheet["D3"].value == 123.456789
    assert sheet["D3"].data_type == "n" and sheet["D3"].number_format == number_format
    assert sheet["T3"].value == 0 and sheet["S3"].value is None
    merges = {str(item) for item in sheet.merged_cells.ranges}
    assert {"F1:I1", "M1:N1", "Q1:R1", "S1:T1", "U1:W1"} <= merges
    assert [sheet.cell(2, col).value for col in range(6, 10)] == ["I", "II", "III", "IV"]
    assert sheet["U1"].value == "Количество единиц или МВт на 2042 год"
    assert sheet.freeze_panes == "D3"
    book.close()


def test_export_respects_selected_energy_zone_and_empty_selection(territory_database, http_client):
    client, _ = http_client
    for zone, power in ((1, 100), (2, 200)):
        import_territory_inputs(workbook(zone=zone, power=power), 1, "tester", "test.xlsx")
    zones = {zone.number: zone for zone in db.session.scalars(select(EnergyZone).where(EnergyZone.database_version_id == 1))}
    for number, expected_rows in (("2", 3), ("14", 2)):
        response = client.get(ENDPOINT, query_string={"energy_zone": zones[number].id})
        assert response.status_code == 200
        book = load_workbook(BytesIO(response.data))
        sheet = book.active
        assert sheet.max_row == expected_rows
        if number == "2":
            assert sheet["A3"].value == "2" and sheet["D3"].value == 200
        book.close()


@pytest.mark.parametrize("name", ['=HYPERLINK("https://example.com","test")', "#N/A"])
def test_export_keeps_technology_names_as_text(territory_database, http_client, name):
    client, _ = http_client
    import_territory_inputs(workbook(), 1, "tester", "test.xlsx")
    row = db.session.scalar(select(TerritoryTechnology))
    row.name = name
    db.session.commit()
    response = client.get(ENDPOINT)
    book = load_workbook(BytesIO(response.data), data_only=False)
    assert book.active["B3"].value == name
    assert book.active["B3"].data_type == "s"
    book.close()


@pytest.mark.parametrize("selected_zone", [False, True])
def test_export_transfer_matrices_follow_visible_axes_and_limit_signs(territory_database, http_client, selected_zone):
    client, _ = http_client
    import_territory_inputs(workbook(), 1, "tester", "test.xlsx")
    section = db.session.scalar(select(TerritoryTransferSection).order_by(TerritoryTransferSection.source_row))
    section.name = "=1+1"
    db.session.commit()
    query = {"sheet": "transfers"}
    if selected_zone:
        query["energy_zone"] = db.session.scalar(select(EnergyZone.id).where(
            EnergyZone.database_version_id == 1, EnergyZone.number == "2"))
    response = client.get(ENDPOINT, query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    assert book.sheetnames == ["Матрица путей", "Матрица МСК и МДП"]
    paths, membership = book.worksheets
    assert paths.max_column == 14
    assert paths.max_row == (4 if selected_zone else 16)
    assert membership.max_column == (4 if selected_zone else 16)
    assert membership.max_row == 14
    assert paths["B1"].value == "=1+1" and paths["B1"].data_type == "s"
    assert membership["A2"].value == "=1+1" and membership["A2"].data_type == "s"
    zone_numbers = ["2"] if selected_zone else [str(number) for number in range(1, 14)]
    assert [paths.cell(row, 1).value for row in range(2, len(zone_numbers) + 2)] == zone_numbers
    assert [membership.cell(1, col).value for col in range(2, len(zone_numbers) + 2)] == zone_numbers
    for index, row in enumerate(db.session.scalars(select(TerritoryTransferSection).order_by(TerritoryTransferSection.source_row)), 2):
        assert paths.cell(paths.max_row - 1, index).value == row.forward_limit
        assert paths.cell(paths.max_row, index).value == -row.reverse_limit
        assert membership.cell(index, membership.max_column).value == row.reverse_limit
        for offset, zone in enumerate(zone_numbers, 2):
            assert paths.cell(offset, index).value == row.zone_paths[zone]
            assert membership.cell(index, offset).value == row.zone_membership[zone]
    book.close()


def test_export_rejects_missing_version_foreign_zone_and_anonymous_user(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    client, _ = http_client
    foreign_zone = db.session.scalar(select(EnergyZone.id).where(EnergyZone.database_version_id == 2))
    assert client.get(ENDPOINT, query_string={"energy_zone": foreign_zone}).status_code == 400
    assert client.get(ENDPOINT, query_string={"sheet": "unknown"}).status_code == 400
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: None)
    assert client.get(ENDPOINT).status_code == 400
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 999)
    assert client.get(ENDPOINT).status_code == 400
    with client.session_transaction() as session:
        session.clear()
    g.pop("_login_user", None)
    assert client.get(ENDPOINT).status_code == 401


def test_toolbar_places_rounding_on_right_and_passes_filters_to_export(territory_database, http_client, monkeypatch):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, "render_template", render_template)
    client, user = http_client
    for sheet in ("technologies", "transfers"):
        html = client.get("/rational_structure/territory_technologies", query_string={
            "sheet": sheet, "rounding_digits": 6,
        }).get_data(as_text=True)
        toolbar = html[html.index('<div class="d-flex flex-wrap align-items-center gap-2 rs-data-controls">'):html.index('<div class="collapse mb-3"')]
        assert toolbar.index("Импорт из Excel") < toolbar.index("Выгрузить в Excel") < toolbar.index("Округление:")
        assert 'class="d-flex align-items-center gap-2 ms-auto flex-shrink-0"' in toolbar
        assert 'download data-export-saved-cells' in toolbar
        export_href = re.search(r'href="([^"]*/export[^"]*)"', toolbar).group(1)
        assert f"sheet={sheet}" in export_href and "rounding_digits=6" in export_href
        assert html.index('id="territory-import"') < html.index('<div class="page-table-scroll ')
    user.has_admin = False
    html = client.get("/rational_structure/territory_technologies").get_data(as_text=True)
    assert "Импорт из Excel" not in html and "Выгрузить в Excel" in html and "Округление:" in html
