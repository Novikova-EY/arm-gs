from decimal import Decimal
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from test_technical_characteristics import csrf_token, database, http_client, workbook_bytes
from test_technical_characteristic_machine_links import machine_factory
from test_technical_inspection_codes import share_identity
from app.extensions import db
from app.rational_structure.equipment_types import EQUIPMENT_TYPES
from app.rational_structure.models import EquipmentTechnicalCharacteristic as Characteristic, TechnicalInspectionCode
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_machine_services import get_machine_technical_inspection_codes

CODE = "001000465562"


def import_kind(equipment_type, *, report_year=2023, version_id=1, row_data=None):
    return import_technical_characteristics(
        workbook_bytes(equipment_types=(equipment_type,), report_year=report_year, row_data=row_data),
        version_id, "tester", report_year=report_year,
    )


@pytest.mark.parametrize("equipment_type, expected", [
    ("hydro", {"design_head": Decimal("91.2"), "installed_electric_power": Decimal("60"),
               "standard_service_life": "40"}),
    ("boiler_energy", {"steam_capacity": Decimal("420"), "fuel_project": "Уголь",
                       "fuel_main": "Уголь", "fuel_reserve": "Мазут",
                       "efficiency_gross": Decimal("88.56"), "heat_output": Decimal("979082")}),
    ("boiler_water", {"heat_power": Decimal("100"), "water_consumption": Decimal("2140"),
                      "operation_mode": "Пиковый", "standard_service_life": "16"}),
])
def test_import_stores_typed_fields_of_new_equipment_kinds(database, equipment_type, expected):
    counts = import_kind(equipment_type)
    assert counts[equipment_type] == 1
    row = db.session.scalar(select(Characteristic))
    assert row.equipment_type == equipment_type
    assert row.equipment_kind == EQUIPMENT_TYPES[equipment_type]
    assert {field: getattr(row, field) for field in expected} == expected
    assert row.extra_values == {}


def test_import_reads_all_five_equipment_sheets_and_reimports_selected_year(database):
    kinds = tuple(EQUIPMENT_TYPES)
    raw = workbook_bytes(equipment_types=kinds, report_year=2024)
    first = import_technical_characteristics(raw, 1, "tester", report_year=2024)
    assert first["created"] == 5
    assert {kind: first[kind] for kind in kinds} == dict.fromkeys(kinds, 1)
    import_technical_characteristics(raw, 2, "tester", report_year=2024)
    import_technical_characteristics(
        workbook_bytes(equipment_types=kinds, report_year=2023), 1, "tester", report_year=2023,
    )
    updated = workbook_bytes(equipment_types=kinds, report_year=2024, row_data={
        "hydro": {"design_head": "92,5"}, "boiler_energy": {"steam_capacity": 500},
        "boiler_water": {"heat_power": 120},
    })
    second = import_technical_characteristics(updated, 1, "tester", report_year=2024)
    assert (second["created"], second["updated"]) == (0, 5)
    rows = list(db.session.scalars(select(Characteristic)))
    assert len(rows) == 15
    for row in rows:
        changed = row.database_version_id == 1 and row.report_year == 2024
        if row.equipment_type == "hydro":
            assert row.design_head == Decimal("92.5" if changed else "91.2")
        elif row.equipment_type == "boiler_energy":
            assert row.steam_capacity == (500 if changed else 420)
        elif row.equipment_type == "boiler_water":
            assert row.heat_power == (120 if changed else 100)


def test_invalid_boiler_sheet_does_not_partially_import_other_types(database):
    raw = workbook_bytes(equipment_types=tuple(EQUIPMENT_TYPES), report_year=2024,
                         row_data={"boiler_water": {"heat_power": "не число"}})
    with pytest.raises(ValueError, match="ожидается число"):
        import_technical_characteristics(raw, 1, "tester", report_year=2024)
    assert list(db.session.scalars(select(Characteristic))) == []


def test_hydro_import_matches_aggregate_and_keeps_code_in_all_versions(machine_factory):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2, brand="Другая марка", powers=())
    share_identity(source_id, target_id)
    counts = import_kind("hydro")
    assert counts["matched"] == 1
    row = db.session.scalar(select(Characteristic))
    assert (row.machine_id, row.match_status) == (source_id, "matched")
    assert row.match_details["candidates"][0]["station_name"] == "Тестовая ТЭЦ"
    assert get_machine_technical_inspection_codes(source_id, 1) == [CODE]
    assert get_machine_technical_inspection_codes(target_id, 2) == [CODE]
    assert {(code.database_version_id, code.machine_id) for code in db.session.scalars(select(TechnicalInspectionCode))} == {
        (1, source_id), (2, target_id),
    }


@pytest.mark.parametrize("equipment_type", ["boiler_energy", "boiler_water"])
def test_boilers_are_not_matched_with_aggregates(machine_factory, equipment_type):
    machine_id, _ = machine_factory(brand="ПТ-60")
    counts = import_kind(equipment_type, row_data={equipment_type: {"equipment_brand": "ПТ-60"}})
    assert counts[equipment_type] == 1
    assert counts["matched"] == counts["unmatched"] == counts["partial"] == 0
    row = db.session.scalar(select(Characteristic))
    assert (row.machine_id, row.pgu_machine_id, row.match_status) == (None, None, "not_checked")
    assert row.match_details == {}
    assert get_machine_technical_inspection_codes(machine_id, 1) == []


def test_hydro_page_shows_matching_controls(http_client):
    client, _ = http_client
    import_kind("hydro")
    response = client.get("/rational_structure/technical_characteristics/hydro", query_string={"year": 2023})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Гидротурбины" in html
    assert "Расчетный напор, м" in html
    assert "Установленная мощность, МВт" in html
    assert CODE in html
    assert 'id="rs-match-status"' in html
    assert 'class="form-control form-control-sm machine-id-input"' in html


@pytest.mark.parametrize("section, title, header", [
    ("boiler_energy", "Энергетические котлы", "Паропроизводительность, т/ч"),
    ("boiler_water", "Водогрейные котлы", "Тепловая мощность, Гкал/ч"),
])
def test_boiler_pages_hide_matching_controls(http_client, section, title, header):
    client, _ = http_client
    import_kind(section)
    response = client.get(f"/rational_structure/technical_characteristics/boilers/{section.removeprefix('boiler_')}",
                          query_string={"year": 2023})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert title in html
    assert header in html
    assert CODE in html
    assert "machine-id-input" not in html
    assert 'id="rs-match-status"' not in html
    assert "Статус сопоставления" not in html


def test_export_contains_only_rows_of_selected_page(http_client):
    client, _ = http_client
    import_kind("hydro")
    import_kind("boiler_water")
    response = client.get("/rational_structure/technical_characteristics/export",
                          query_string={"section": "hydro", "year": 2023})
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    sheet = book.active
    assert sheet.max_row == 2
    labels = [cell.value for cell in sheet[1]]
    assert "Расчетный напор, м" in labels
    assert "Тепловая мощность, Гкал/ч" not in labels
    assert sheet.cell(2, 1).value == CODE
    book.close()


def test_import_from_hydro_page_returns_to_hydro_page(http_client, csrf_token):
    client, _ = http_client
    response = client.post("/rational_structure/technical_characteristics/import", data={
        "csrf_token": csrf_token, "year": "2023", "section": "hydro",
        "file": (BytesIO(workbook_bytes(equipment_types=("hydro",))), "data.xlsx"),
    })
    assert response.status_code == 302
    target = urlsplit(response.headers["Location"])
    assert target.path == "/rational_structure/technical_characteristics/hydro"
    assert parse_qs(target.query)["year"] == ["2023"]
    assert db.session.scalar(select(Characteristic)).equipment_type == "hydro"


@pytest.mark.parametrize("kind, path", [
    ("hydro", "/hydro"), ("boiler_energy", "/boilers/energy"), ("boiler_water", "/boilers/water"),
])
def test_http_import_reports_new_equipment_count_for_2024(http_client, csrf_token, kind, path):
    client, _ = http_client
    response = client.post("/rational_structure/technical_characteristics/import", data={
        "csrf_token": csrf_token, "year": "2024", "section": kind,
        "file": (BytesIO(workbook_bytes(equipment_types=(kind,), report_year=2024)), "data.xlsx"),
    })
    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/rational_structure/technical_characteristics" + path
    row, = db.session.scalars(select(Characteristic))
    assert (row.equipment_type, row.report_year) == (kind, 2024)
    with client.session_transaction() as session:
        assert any(category == "success" and f"{EQUIPMENT_TYPES[kind]}: 1" in message
                   for category, message in session["_flashes"])


def test_manual_matching_is_rejected_for_boilers(http_client, machine_factory):
    client, _ = http_client
    machine_id, _ = machine_factory()
    row = Characteristic(database_version_id=1, equipment_type="boiler_water",
                         equipment_code=CODE, report_year=2024)
    db.session.add(row)
    db.session.commit()
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": row.id, "machine_id": machine_id,
    })
    assert response.status_code == 400
    db.session.expire_all()
    assert (row.machine_id, row.match_status) == (None, "not_checked")
