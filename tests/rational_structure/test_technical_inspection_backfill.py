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
from scripts.backfill_technical_inspection_codes import backfill


def characteristic(version, year, **kwargs):
    row = Characteristic(database_version_id=version, report_year=year, equipment_type="steam",
                         equipment_code=CODE, installed_electric_power=Decimal(str(year)), **kwargs)
    db.session.add(row)
    db.session.commit()
    return row


@pytest.mark.parametrize("pgu", [False, True])
def test_backfill_preview_apply_and_repeat_preserve_parameters(machine_factory, pgu):
    source, _ = machine_factory()
    target, _ = machine_factory(version=2)
    share_identity(source, target)
    source_part = add_part(source, 1) if pgu else None
    target_part = add_part(target, 2) if pgu else None
    verified = characteristic(1, 2024, machine_id=source, pgu_machine_id=source_part, match_status="matched")
    old_year = characteristic(1, 2023, match_status="partial")
    other_version = characteristic(2, 2023, match_status="unmatched")
    preview = backfill()
    assert preview["applied"] is False
    assert preview["created"] == 2
    assert preview["linked_rows"] == 2
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []
    assert old_year.machine_id is None
    assert other_version.machine_id is None
    applied = backfill(apply=True)
    assert applied["created"] == 2
    assert applied["linked_rows"] == 2
    assert (old_year.machine_id, old_year.pgu_machine_id, old_year.match_status) == (source, source_part, "matched")
    assert (other_version.machine_id, other_version.pgu_machine_id, other_version.match_status) == (target, target_part, "matched")
    assert verified.machine_id == source
    assert [(row.report_year, row.installed_electric_power) for row in (verified, old_year, other_version)] == [
        (2024, Decimal("2024")), (2023, Decimal("2023")), (2023, Decimal("2023")),
    ]
    repeated = backfill(apply=True)
    assert repeated["created"] == repeated["linked_rows"] == 0
    assert len(list(db.session.scalars(select(Characteristic)))) == 3


def test_backfill_reports_conflicting_codes_without_overwriting(machine_factory):
    first, _ = machine_factory()
    second, _ = machine_factory()
    characteristic(1, 2024, machine_id=first, match_status="matched")
    characteristic(1, 2023, machine_id=second, match_status="matched")
    report = backfill(apply=True)
    assert report["created"] == 0
    assert report["conflicts"][0]["equipment_code"] == CODE
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []


def test_backfill_failure_rolls_back_all_changes(machine_factory):
    source, _ = machine_factory()
    characteristic(1, 2024, machine_id=source, match_status="matched")
    old_year = characteristic(1, 2023, match_status="partial")

    def fail(connection, cursor, statement, parameters, context, executemany):
        if TechnicalInspectionCode.__tablename__ in statement and statement.lstrip().upper().startswith("INSERT"):
            raise SQLAlchemyError("backfill failure")

    event.listen(db.engine, "after_cursor_execute", fail)
    try:
        with pytest.raises(SQLAlchemyError, match="backfill failure"):
            backfill(apply=True)
    finally:
        event.remove(db.engine, "after_cursor_execute", fail)
    assert old_year.machine_id is None
    assert old_year.match_status == "partial"
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []


@pytest.mark.parametrize("pgu", [False, True])
def test_manual_card_code_without_excel_is_saved_in_all_versions(http_client, machine_factory, pgu):
    client, _ = http_client
    source, _ = machine_factory()
    target, _ = machine_factory(version=2)
    share_identity(source, target)
    source_part = add_part(source, 1) if pgu else None
    target_part = add_part(target, 2) if pgu else None
    response = client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json={
        "machine_id": source, "pgu_machine_id": source_part, "equipment_code": CODE,
    })
    assert response.status_code == 200
    assert {(row.database_version_id, row.machine_id, row.pgu_machine_id, row.equipment_code)
            for row in db.session.scalars(select(TechnicalInspectionCode))} == {
        (1, source, source_part, CODE), (2, target, target_part, CODE),
    }
    assert list(db.session.scalars(select(Characteristic))) == []


def test_manual_assignment_links_existing_years_and_versions_without_changing_parameters(http_client, machine_factory):
    client, _ = http_client
    source, _ = machine_factory()
    target, _ = machine_factory(version=2)
    share_identity(source, target)
    current = characteristic(1, 2024, match_status="partial")
    old_year = characteristic(1, 2023, match_status="unmatched")
    other_version = characteristic(2, 2023, match_status="partial")
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": current.id, "machine_id": source,
    })
    assert response.status_code == 200
    assert (old_year.machine_id, old_year.match_status) == (source, "matched")
    assert (other_version.machine_id, other_version.match_status) == (target, "matched")
    assert old_year.installed_electric_power == other_version.installed_electric_power == Decimal("2023")
    assert len(list(db.session.scalars(select(Characteristic)))) == 3


def test_import_uses_each_record_year_for_fallback_and_leaves_other_versions_untouched(machine_factory):
    source, _ = machine_factory()
    target, _ = machine_factory(version=2)
    share_identity(source, target)
    foreign = characteristic(2, 2023, match_status="partial")
    raw = workbook_bytes(extra_rows=[{
        "report_year": 2024, "installed_electric_power": 80, "equipment_code": "another-code",
    }])
    counts = import_technical_characteristics(raw, 1, "tester", report_year=2025)
    assert counts["matched"] == 4
    imported = list(db.session.scalars(select(Characteristic).where(Characteristic.database_version_id == 1)))
    assert {(row.report_year, row.machine_id, row.installed_electric_power) for row in imported} == {
        (2023, source, Decimal("60")), (2024, source, Decimal("80")),
    }
    assert foreign.machine_id is None
    assert foreign.match_status == "partial"
    assert foreign.installed_electric_power == Decimal("2023")


@pytest.mark.parametrize("replacement", ["new-001", ""])
def test_card_code_change_or_clear_propagates_without_rewriting_excel(http_client, machine_factory, replacement):
    client, _ = http_client
    source, _ = machine_factory()
    target, _ = machine_factory(version=2)
    share_identity(source, target)
    original = characteristic(1, 2024, machine_id=source, match_status="matched")
    backfill(apply=True)
    response = client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json={
        "machine_id": source, "equipment_code": replacement, "previous_code": CODE,
    })
    assert response.status_code == 200
    stored = list(db.session.scalars(select(TechnicalInspectionCode)))
    assert {(row.database_version_id, row.machine_id, row.equipment_code) for row in stored} == (
        {(1, source, replacement), (2, target, replacement)} if replacement else set()
    )
    assert original.equipment_code == CODE
    assert original.installed_electric_power == Decimal("2024")
    assert original.machine_id is None
    assert original.match_status == "not_checked"


def test_manual_reassignment_replaces_source_binding_and_all_its_years(http_client, machine_factory):
    client, _ = http_client
    original, _ = machine_factory()
    selected, _ = machine_factory()
    current = characteristic(1, 2024, machine_id=original, match_status="matched")
    old_year = characteristic(1, 2023, machine_id=original, match_status="matched")
    backfill(apply=True)
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": current.id, "machine_id": selected,
    })
    assert response.status_code == 200
    stored = db.session.scalar(select(TechnicalInspectionCode))
    assert stored.machine_id == selected
    assert current.machine_id == old_year.machine_id == selected


@pytest.mark.parametrize("code", ["x" * 101, 123, ["code"]])
def test_card_rejects_invalid_code_without_writing(http_client, machine_factory, code):
    client, _ = http_client
    machine_id, _ = machine_factory()
    response = client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json={
        "machine_id": machine_id, "equipment_code": code,
    })
    assert response.status_code == 400
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []
