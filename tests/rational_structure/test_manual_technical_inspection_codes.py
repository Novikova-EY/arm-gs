from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from test_technical_characteristics import database, http_client, workbook_bytes
from test_technical_characteristic_machine_links import machine_factory
from test_technical_inspection_codes import CODE, add_part, share_identity
from app.extensions import db
from app.rational_structure.models import TechnicalInspectionCode, EquipmentTechnicalCharacteristic as Characteristic
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_machine_services import (
    get_machine_technical_inspection_codes, get_pgu_machine_technical_inspection_codes,
)


@pytest.mark.parametrize("pgu", [False, True])
def test_manual_assignment_saves_code_in_all_versions_without_copying_parameters(http_client, machine_factory, pgu):
    client, _ = http_client
    source_id, station_id = machine_factory()
    target_id, _ = machine_factory(version=2, brand="Другая марка", powers=())
    share_identity(source_id, target_id)
    source_part = add_part(source_id, 1, id_ti=77) if pgu else None
    target_part = add_part(target_id, 2, id_ti=77, number="Новое обозначение") if pgu else None
    row = Characteristic(database_version_id=1, equipment_type="gas" if pgu else "steam",
                  equipment_code=CODE, report_year=2024, match_status="partial",
                  installed_electric_power=Decimal("70"), extra_values={"Параметр": "значение"})
    db.session.add(row)
    db.session.commit()
    payload = {"turbine_id": row.id, "station_id": station_id,
               "machine_id": f"{source_id}/{source_part}" if pgu else str(source_id)}
    for _ in range(2):
        response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json=payload)
        assert response.status_code == 200
        assert response.get_json()["match_status"] == "matched"
    db.session.expire_all()
    assert (row.machine_id, row.pgu_machine_id, row.match_status) == (source_id, source_part, "matched")
    assert row.installed_electric_power == Decimal("70")
    assert row.extra_values == {"Параметр": "значение"}
    assert {(code.database_version_id, code.equipment_code, code.machine_id, code.pgu_machine_id)
            for code in db.session.scalars(select(TechnicalInspectionCode))} == {
        (1, CODE, source_id, source_part), (2, CODE, target_id, target_part),
    }
    getter = get_pgu_machine_technical_inspection_codes if pgu else get_machine_technical_inspection_codes
    assert getter(target_part if pgu else target_id, 2) == [CODE]
    assert len(list(db.session.scalars(select(Characteristic)))) == 1
    counts = import_technical_characteristics(workbook_bytes(power=999, report_year=2024),
                                             2, "tester", report_year=2024)
    assert counts["matched"] == 2
    imported = list(db.session.scalars(select(Characteristic).where(Characteristic.database_version_id == 2)))
    assert {(item.machine_id, item.pgu_machine_id) for item in imported} == {(target_id, target_part)}


@pytest.mark.parametrize("problem", ["ambiguous_identity", "existing_assignment"])
def test_manual_assignment_does_not_overwrite_conflicting_or_ambiguous_other_version(
        http_client, machine_factory, problem):
    client, _ = http_client
    source_id, _ = machine_factory()
    counterpart_id, _ = machine_factory(version=2)
    other_id, _ = machine_factory(version=2)
    share_identity(source_id, counterpart_id)
    if problem == "ambiguous_identity":
        share_identity(source_id, other_id)
    else:
        db.session.add(TechnicalInspectionCode(database_version_id=2, equipment_code=CODE, machine_id=other_id))
    row = Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                  report_year=2024, match_status="partial")
    db.session.add(row)
    db.session.commit()
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": row.id, "machine_id": source_id,
    })
    assert response.status_code == 200
    assert get_machine_technical_inspection_codes(source_id, 1) == [CODE]
    assert get_machine_technical_inspection_codes(counterpart_id, 2) == []
    assert get_machine_technical_inspection_codes(other_id, 2) == ([CODE] if problem == "existing_assignment" else [])


def test_manual_assignment_failure_rolls_back_link_and_codes_in_all_versions(http_client, machine_factory):
    client, _ = http_client
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)
    row = Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                  report_year=2024, match_status="partial", match_details={"reason": "Исходное сопоставление"})
    db.session.add(row)
    db.session.commit()
    row_id = row.id

    def fail_after_write(connection, cursor, statement, parameters, context, executemany):
        if TechnicalInspectionCode.__tablename__ in statement and statement.lstrip().upper().startswith("INSERT"):
            raise SQLAlchemyError("code write failure")

    event.listen(db.engine, "after_cursor_execute", fail_after_write)
    try:
        response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
            "turbine_id": row_id, "machine_id": source_id,
        })
    finally:
        event.remove(db.engine, "after_cursor_execute", fail_after_write)
    assert response.status_code == 500
    db.session.expire_all()
    assert (row.machine_id, row.pgu_machine_id, row.match_status) == (None, None, "partial")
    assert row.match_details == {"reason": "Исходное сопоставление"}
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []


def test_rejected_foreign_version_machine_does_not_save_code(http_client, machine_factory):
    client, _ = http_client
    foreign_id, _ = machine_factory(version=2)
    row = Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                  report_year=2024, match_status="partial")
    db.session.add(row)
    db.session.commit()
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": row.id, "machine_id": foreign_id,
    })
    assert response.status_code == 404
    assert row.machine_id is None
    assert row.match_status == "partial"
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []
