from decimal import Decimal
import re

import pytest
from flask import render_template
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from test_technical_characteristics import database, http_client, workbook_bytes
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_name_model import PGUMachineName
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TurbineTechnicalCharacteristic as Turbine
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_machine_services import (
    get_machine_technical_inspection_codes, load_machine_candidates, load_pgu_machine_candidates,
)
from app.refdata.models.gen_companies.gen_company_model import GenCompany


@pytest.fixture
def machine_factory(database):
    for model in (EquipmentGroup, MachineFuelParam):
        model.__table__.create(db.engine, checkfirst=True)

    def create(*, version=1, owner_version=1, station_version=None, brand="ПТ-60",
               powers=((2023, 60), (2024, 80)), names=()):
        # Core inserts обходят ORM listeners UUID, обращающиеся к посторонним таблицам.
        owner_id = db.session.execute(select(GenCompany.id).where(GenCompany.name == "АО Тест")).scalar_one_or_none()
        if owner_id is None:
            owner_id = db.session.execute(GenCompany.__table__.insert().values(
                name="АО Тест", database_version_id=owner_version,
            )).inserted_primary_key[0]
        station_id = db.session.execute(Station.__table__.insert().values(
            external_code=f"station-{version}-{brand}", name="Тестовая ТЭЦ",
            database_version_id=version if station_version is None else station_version,
        )).inserted_primary_key[0]
        machine_id = db.session.execute(Machine.__table__.insert().values(
            external_code=f"machine-{station_id}", machine_number="10ПТ", machine_name=brand,
            id_station=station_id, id_gen_company=owner_id, database_version_id=version,
        )).inserted_primary_key[0]
        for year, power in powers:
            db.session.execute(MachinePower.__table__.insert().values(
                id_machine=machine_id, year_number=year, p_ust=power, database_version_id=version,
            ))
        for year, name in names:
            db.session.execute(MachineName.__table__.insert().values(
                id_machine=machine_id, year_number=year, name=name, database_version_id=version,
            ))
        db.session.commit()
        return machine_id, station_id

    return create


def test_import_links_two_codes_to_one_machine_and_deduplicates_years(machine_factory):
    machine_id, _ = machine_factory()
    raw = workbook_bytes(extra_rows=[{"equipment_code": "001000465563"}])
    counts = import_technical_characteristics(raw, 1, "tester", report_year=2023)
    assert counts == {"created": 4, "updated": 0, "steam": 2, "gas": 2, "matched": 4, "partial": 0, "ambiguous": 0, "unmatched": 0}
    counts = import_technical_characteristics(raw, 1, "tester", report_year=2023)
    assert counts == {"created": 0, "updated": 4, "steam": 2, "gas": 2, "matched": 4, "partial": 0, "ambiguous": 0, "unmatched": 0}
    import_technical_characteristics(workbook_bytes(
        report_year=2024, power=80, extra_rows=[{"equipment_code": "001000465563"}],
    ), 1, "tester", report_year=2024)
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 8
    assert {(row.machine_id, row.match_status) for row in rows} == {(machine_id, "matched")}
    assert {row.report_year for row in rows} == {2023, 2024}
    assert all(row.match_details["candidates"][0]["machine_id"] == machine_id for row in rows)
    assert get_machine_technical_inspection_codes(machine_id, 1) == ["001000465562", "001000465563"]


@pytest.mark.parametrize("year, power, status", [
    (2023, 60, "matched"), (2024, 80, "matched"),
    (2024, 60, "partial"), (2025, 60, "partial"),
])
def test_matching_uses_power_of_selected_year(machine_factory, year, power, status):
    machine_id, _ = machine_factory()
    import_technical_characteristics(workbook_bytes(report_year=year, power=power), 1, "tester", report_year=year)
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 2
    assert {row.match_status for row in rows} == {status}
    assert {row.machine_id for row in rows} == {machine_id if status == "matched" else None}
    if status == "partial":
        assert all("installed_electric_power" in row.match_details["differing_fields"] for row in rows)
        assert get_machine_technical_inspection_codes(machine_id, 1) == []


@pytest.mark.parametrize("endpoint", ["technical_characteristics", "technical_characteristics/export"])
def test_page_and_export_handle_different_matching_details(http_client, machine_factory, endpoint):
    client, _ = http_client
    machine_factory()
    import_technical_characteristics(workbook_bytes(extra_rows=[
        {"equipment_code": "partial-code", "installed_electric_power": 70},
    ]), 1, "tester", report_year=2023)
    rows = list(db.session.scalars(select(Turbine)))
    assert {row.match_status for row in rows} == {"matched", "partial"}
    assert next(row.match_details for row in rows if row.match_status == "matched") != next(
        row.match_details for row in rows if row.match_status == "partial"
    )
    response = client.get(f"/rational_structure/{endpoint}", query_string={"year": 2023})
    assert response.status_code == 200
    if endpoint == "technical_characteristics":
        html = response.get_data(as_text=True)
        assert 'data-match-status="matched"' in html
        assert 'data-match-status="partial"' in html
        assert "partial-code" in html
    else:
        assert "attachment" in response.headers["Content-Disposition"]


@pytest.mark.parametrize("base_brand, annual_name", [("Старая марка", "ПТ-60"), ("ПТ-60", "   ")])
def test_annual_name_overrides_base_and_blank_falls_back(machine_factory, base_brand, annual_name):
    machine_id, _ = machine_factory(brand=base_brand, names=((2023, annual_name), (2024, "Другая марка")))
    candidates = load_machine_candidates(1, 2023)
    assert len(candidates) == 1
    assert candidates[0]["equipment_brand"] == "ПТ-60"
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert {(row.machine_id, row.match_status) for row in db.session.scalars(select(Turbine))} == {(machine_id, "matched")}


@pytest.mark.parametrize("owner_version, status", [(1, "matched"), (None, "matched"), (2, "matched")])
def test_owner_is_current_version_or_shared(machine_factory, owner_version, status):
    machine_id, _ = machine_factory(owner_version=owner_version)
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    rows = list(db.session.scalars(select(Turbine)))
    assert {row.match_status for row in rows} == {status}
    assert {row.machine_id for row in rows} == {machine_id if status == "matched" else None}


def test_candidates_exclude_foreign_machine_station_and_annual_versions(machine_factory):
    machine_id, _ = machine_factory(powers=())
    machine_factory(version=2)
    machine_factory(station_version=2)
    db.session.execute(MachinePower.__table__.insert().values(
        id_machine=machine_id, year_number=2023, p_ust=60, database_version_id=2,
    ))
    db.session.execute(MachineName.__table__.insert().values(
        id_machine=machine_id, year_number=2023, name="Чужая марка", database_version_id=2,
    ))
    db.session.commit()
    candidates = load_machine_candidates(1, 2023)
    assert len(candidates) == 1
    assert candidates[0]["machine_id"] == machine_id
    assert candidates[0]["equipment_brand"] == "ПТ-60"
    assert candidates[0]["installed_electric_power"] is None
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert {(row.machine_id, row.match_status) for row in db.session.scalars(select(Turbine))} == {(None, "partial")}


@pytest.mark.parametrize("status", ["partial", "ambiguous", "unmatched"])
def test_non_exact_import_does_not_assign_machine_or_codes(machine_factory, status):
    machine_id, _ = machine_factory(version=2 if status == "unmatched" else 1)
    if status == "ambiguous":
        machine_factory()
    import_technical_characteristics(workbook_bytes(power=70 if status == "partial" else 60),
                                     1, "tester", report_year=2023)
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == 2
    assert {(row.machine_id, row.match_status) for row in rows} == {(None, status)}
    assert get_machine_technical_inspection_codes(machine_id, 1) == []


def test_reimport_preserves_known_code_link_when_parameters_change(machine_factory):
    machine_id, _ = machine_factory()
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert get_machine_technical_inspection_codes(machine_id, 1) == ["001000465562"]
    counts = import_technical_characteristics(workbook_bytes(power=70), 1, "tester", report_year=2023)
    assert counts == {"created": 0, "updated": 2, "steam": 1, "gas": 1, "matched": 2, "partial": 0, "ambiguous": 0, "unmatched": 0}
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert {(row.machine_id, row.match_status, row.installed_electric_power) for row in rows} == {
        (machine_id, "matched", Decimal("70")),
    }
    assert all(row.match_details["differing_fields"] == [] for row in rows)
    assert get_machine_technical_inspection_codes(machine_id, 1) == ["001000465562"]


def test_code_query_filters_status_record_version_and_machine_version(machine_factory):
    machine_id, _ = machine_factory()
    foreign_machine_id, _ = machine_factory(version=2)
    records = [
        {"equipment_code": code, "machine_id": machine_id, "match_status": status, "database_version_id": 1}
        for code, status in (("accepted", "matched"), ("partial", "partial"), ("ambiguous", "ambiguous"),
                             ("unmatched", "unmatched"), ("not-checked", "not_checked"))
    ]
    records.extend([
        {"equipment_code": "foreign-record", "machine_id": machine_id, "match_status": "matched", "database_version_id": 2},
        {"equipment_code": "foreign-machine", "machine_id": foreign_machine_id, "match_status": "matched", "database_version_id": 1},
    ])
    for record in records:
        db.session.execute(Turbine.__table__.insert().values(equipment_type="steam", report_year=2023, **record))
    db.session.commit()
    assert get_machine_technical_inspection_codes(machine_id, 1) == ["accepted"]
    assert get_machine_technical_inspection_codes(machine_id, 2) == []
    assert get_machine_technical_inspection_codes(machine_id, None) == []
    assert get_machine_technical_inspection_codes(foreign_machine_id, 1) == []


@pytest.mark.parametrize("existing", [False, True])
def test_sql_failure_rolls_back_imported_links_and_updates(machine_factory, existing):
    machine_id, _ = machine_factory()
    if existing:
        import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    table_name = Turbine.__tablename__

    def fail_after_write(connection, cursor, statement, parameters, context, executemany):
        if table_name in statement and statement.lstrip().upper().startswith(("INSERT", "UPDATE")):
            raise SQLAlchemyError("failure after database write")

    event.listen(db.engine, "after_cursor_execute", fail_after_write)
    try:
        with pytest.raises(SQLAlchemyError, match="failure after database write"):
            import_technical_characteristics(workbook_bytes(power=70), 1, "tester", report_year=2023)
    finally:
        event.remove(db.engine, "after_cursor_execute", fail_after_write)
    db.session.expire_all()
    rows = list(db.session.scalars(select(Turbine)))
    assert len(rows) == (2 if existing else 0)
    assert all(row.machine_id == machine_id and row.match_status == "matched" for row in rows)
    assert all(row.installed_electric_power == Decimal("60") for row in rows)
    assert get_machine_technical_inspection_codes(machine_id, 1) == (["001000465562"] if existing else [])


@pytest.mark.parametrize("status", ["matched", "partial", "ambiguous", "unmatched", "not_checked"])
def test_table_renders_matching_status_details_and_candidate_links(http_client, machine_factory, status):
    client, _ = http_client
    machine_id, station_id = machine_factory(version=2 if status == "unmatched" else 1)
    other_machine_id = None
    if status == "ambiguous":
        other_machine_id, other_station_id = machine_factory()
    if status == "not_checked":
        db.session.add(Turbine(database_version_id=1, turbine_type="steam", equipment_code="unchecked",
                               report_year=2023, extra_values={"Температура газов, °C": "525"}))
        db.session.commit()
    else:
        import_technical_characteristics(workbook_bytes(power=70 if status == "partial" else 60),
                                         1, "tester", report_year=2023)
    response = client.get("/rational_structure/technical_characteristics", query_string={"year": 2023})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.findall(r"<th\b[^>]*>(.*?)</th>", re.search(r"<thead\b.*?</thead>", html, re.S).group(), re.S)
    # match_details column removed; header order: equipment_code, match_status, machine_id, rest_columns
    assert not any("Сопоставление с агрегатом" in header for header in headers)
    assert "Температура газов, °C" in headers[-1]
    body = re.search(r"<tbody>(.*?)</tbody>", html, re.S).group(1)
    rows = re.findall(r"(<tr\b[^>]*>)(.*?)</tr>", body, re.S)
    assert len(rows) == (1 if status == "not_checked" else 2)
    for tag, content in rows:
        assert f'data-match-status="{status}"' in tag
        if status != "matched":
            assert f"rs-match-{status}" in tag
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", content, re.S)
        # cells: equipment_code, match_status, machine_id, rest_columns..., extra_labels
        # extra_labels is last, so "Температура газов, °C" is cells[-1]
        assert cells[-1].strip() == "525"
        if status == "matched":
            # machine_id is cells[2] - now an input field
            assert f'value="{machine_id}"' in cells[2]
            assert 'class="form-control form-control-sm machine-id-input"' in cells[2]
        if status in ("partial", "ambiguous"):
            # tooltip content lives in match_status cell (cells[1])
            assert "installed_electric_power" in cells[1] or "ID агрегата" in cells[1]
        if other_machine_id is not None:
            # ambiguous candidates are shown in match_status cell (cells[1])
            assert f"ID агрегата: {other_machine_id}" in cells[1]


def test_machine_card_fragment_renders_both_codes_with_html_escaping(http_client, database):
    with database.test_request_context():
        html = render_template(
            "generation/stations/_machine_technical_inspection_codes.html",
            technical_inspection_codes=["001000465562", '<script>alert("x")</script>&'],
        )
    assert "001000465562" in html
    assert "&lt;script&gt;" in html and "&lt;/script&gt;&amp;" in html
    assert "<script>" not in html


def test_pgu_components_are_candidates_and_parent_is_excluded(machine_factory):
    parent_id, _ = machine_factory(brand="ПГУ-450")
    pgu_id = db.session.execute(PGUMachine.__table__.insert().values(
        id_parent_machine=parent_id, machine_number="ГТ1", machine_name="ГТ-150",
        database_version_id=1,
    )).inserted_primary_key[0]
    db.session.execute(PGUMachineName.__table__.insert().values(
        id_pgu_machine=pgu_id, year_number=2023, name="ГТ-150", database_version_id=1,
    ))
    db.session.execute(PGUMachinePower.__table__.insert().values(
        id_pgu_machine=pgu_id, year_number=2023, p_ust=150, database_version_id=1,
    ))
    db.session.commit()

    machines = load_machine_candidates(1, 2023)
    assert all(candidate["machine_id"] != parent_id for candidate in machines)

    pgu_candidates = load_pgu_machine_candidates(1, 2023)
    assert len(pgu_candidates) == 1
    assert pgu_candidates[0]["machine_id"] == parent_id
    assert pgu_candidates[0]["pgu_machine_id"] == pgu_id
    assert pgu_candidates[0]["equipment_brand"] == "ГТ-150"
    assert pgu_candidates[0]["installed_electric_power"] == Decimal("150")


def test_save_machine_id_parses_pgu_component(http_client, machine_factory):
    client, _ = http_client
    parent_id, _ = machine_factory(brand="ПГУ-450")
    pgu_id = db.session.execute(PGUMachine.__table__.insert().values(
        id_parent_machine=parent_id, machine_number="ГТ1", machine_name="ГТ-150",
        database_version_id=1,
    )).inserted_primary_key[0]
    db.session.commit()

    turbine = Turbine(database_version_id=1, turbine_type="gas", equipment_code="g-code", report_year=2023)
    db.session.add(turbine)
    db.session.commit()

    response = client.patch(
        "/rational_structure/technical_characteristics/save_machine_id",
        json={"turbine_id": turbine.id, "machine_id": f"{parent_id}/{pgu_id}", "station_id": None},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["machine_id"] == parent_id
    assert data["pgu_machine_id"] == pgu_id
    assert data["match_status"] == "matched"

    db.session.expire_all()
    saved = db.session.get(Turbine, turbine.id)
    assert saved.machine_id == parent_id
    assert saved.pgu_machine_id == pgu_id
    assert saved.match_status == "matched"

