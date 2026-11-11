from decimal import Decimal

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.exc import SQLAlchemyError

from test_technical_characteristics import database, http_client, workbook_bytes
from test_technical_characteristic_machine_links import machine_factory
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.rational_structure.models import TechnicalInspectionCode, EquipmentTechnicalCharacteristic as Characteristic
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from app.rational_structure.services.technical_characteristic_machine_services import (
    get_machine_technical_inspection_codes, get_pgu_machine_technical_inspection_codes,
)


CODE = "001000465562"


def share_identity(source_id, target_id):
    external_code = db.session.scalar(select(Machine.external_code).where(Machine.id == source_id))
    db.session.execute(update(Machine).where(Machine.id == target_id).values(external_code=external_code))
    db.session.commit()


def add_part(parent_id, version, *, number="ГТ-1", id_ti=None, power=60):
    part_id = db.session.execute(PGUMachine.__table__.insert().values(
        id_parent_machine=parent_id, database_version_id=version, machine_number=number,
        machine_name="ПТ-60", id_ti=id_ti,
    )).inserted_primary_key[0]
    db.session.execute(PGUMachinePower.__table__.insert().values(
        id_pgu_machine=part_id, database_version_id=version, year_number=2023, p_ust=power,
    ))
    db.session.commit()
    return part_id


def test_auto_match_saves_only_code_in_all_versions_and_uses_it_for_future_excel(machine_factory):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2, brand="Другая марка", powers=())
    share_identity(source_id, target_id)
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert {(row.database_version_id, row.equipment_code, row.machine_id, row.pgu_machine_id)
            for row in db.session.scalars(select(TechnicalInspectionCode))} == {
        (1, CODE, source_id, None), (2, CODE, target_id, None),
    }
    assert get_machine_technical_inspection_codes(target_id, 2) == [CODE]
    assert {row.database_version_id for row in db.session.scalars(select(Characteristic))} == {1}
    counts = import_technical_characteristics(workbook_bytes(power=999, report_year=2024), 2, "tester", report_year=2024)
    assert counts["matched"] == 2
    rows = list(db.session.scalars(select(Characteristic).where(Characteristic.database_version_id == 2)))
    assert {(row.machine_id, row.report_year, row.installed_electric_power) for row in rows} == {
        (target_id, 2024, Decimal("999")),
    }
    assert all("по ранее сохраненному коду" in row.match_details["reason"] for row in rows)
    assert len(list(db.session.scalars(select(TechnicalInspectionCode)))) == 2


def test_legacy_manual_code_has_priority_over_parameter_match(machine_factory):
    known_id, _ = machine_factory(brand="Другая марка", powers=())
    other_id, _ = machine_factory()
    db.session.execute(Characteristic.__table__.insert().values(
        database_version_id=1, equipment_type="steam", equipment_code=CODE,
        report_year=2022, machine_id=known_id, match_status="matched",
    ))
    db.session.commit()
    counts = import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert counts["matched"] == 2
    assert {row.machine_id for row in db.session.scalars(select(Characteristic))} == {known_id}
    assert get_machine_technical_inspection_codes(other_id, 1) == []
    assert get_machine_technical_inspection_codes(known_id, 1) == [CODE]


def test_legacy_code_is_resolved_in_another_version_without_copying_parameters(machine_factory):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2, brand="Не совпадает", powers=())
    share_identity(source_id, target_id)
    db.session.execute(Characteristic.__table__.insert().values(
        database_version_id=1, equipment_type="steam", equipment_code=CODE,
        report_year=2022, machine_id=source_id, match_status="matched",
    ))
    db.session.commit()
    counts = import_technical_characteristics(workbook_bytes(power=123, report_year=2024), 2, "tester", report_year=2024)
    assert counts["matched"] == 2
    assert {row.machine_id for row in db.session.scalars(select(Characteristic).where(Characteristic.report_year == 2024))} == {target_id}
    assert len(list(db.session.scalars(select(Characteristic)))) == 3


def test_unknown_code_falls_back_to_parser_and_does_not_copy_to_unrelated_machine(machine_factory):
    source_id, _ = machine_factory()
    unrelated_id, _ = machine_factory(version=2)
    counts = import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert counts["matched"] == 2
    assert get_machine_technical_inspection_codes(source_id, 1) == [CODE]
    assert get_machine_technical_inspection_codes(unrelated_id, 2) == []


def test_conflicting_legacy_codes_are_ambiguous_even_when_parser_has_exact_match(machine_factory):
    first_id, _ = machine_factory()
    second_id, _ = machine_factory(brand="Другая марка", powers=())
    for year, machine_id in ((2021, first_id), (2022, second_id)):
        db.session.execute(Characteristic.__table__.insert().values(
            database_version_id=1, equipment_type="steam", equipment_code=CODE,
            report_year=year, machine_id=machine_id, match_status="matched",
        ))
    db.session.commit()
    counts = import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert counts["ambiguous"] == 2
    rows = list(db.session.scalars(select(Characteristic).where(Characteristic.report_year == 2023)))
    assert all(row.machine_id is None for row in rows)
    assert {candidate["machine_id"] for candidate in rows[0].match_details["candidates"]} == {first_id, second_id}
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []


@pytest.mark.parametrize("use_id_ti", [False, True])
def test_pgu_code_propagates_to_same_component_only(machine_factory, use_id_ti):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)
    source_part = add_part(source_id, 1, id_ti=77 if use_id_ti else None)
    target_part = add_part(target_id, 2, number="Другое обозначение" if use_id_ti else "ГТ-1",
                           id_ti=77 if use_id_ti else None, power=999)
    other_part = add_part(target_id, 2, number="ГТ-2", id_ti=88 if use_id_ti else None)
    counts = import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert counts["matched"] == 2
    assert {row.pgu_machine_id for row in db.session.scalars(select(Characteristic))} == {source_part}
    assert get_pgu_machine_technical_inspection_codes(target_part, 2) == [CODE]
    assert get_pgu_machine_technical_inspection_codes(other_part, 2) == []
    assert {row.pgu_machine_id for row in db.session.scalars(select(TechnicalInspectionCode))} == {source_part, target_part}
    assert {row.database_version_id for row in db.session.scalars(select(Characteristic))} == {1}
    counts = import_technical_characteristics(workbook_bytes(power=123, report_year=2024), 2, "tester", report_year=2024)
    assert counts["matched"] == 2
    assert {row.pgu_machine_id for row in db.session.scalars(select(Characteristic).where(Characteristic.database_version_id == 2))} == {target_part}


@pytest.mark.parametrize("problem", ["duplicate_parent", "duplicate_part", "different_id_ti", "blank_number"])
def test_ambiguous_or_different_cross_version_identity_is_not_filled(machine_factory, problem):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)
    source_part = None
    if problem == "duplicate_parent":
        duplicate_id, _ = machine_factory(version=2)
        share_identity(source_id, duplicate_id)
    else:
        source_part = add_part(source_id, 1, number="" if problem == "blank_number" else "ГТ-1",
                               id_ti=77 if problem == "different_id_ti" else None)
        add_part(target_id, 2, number="" if problem == "blank_number" else "ГТ-1",
                 id_ti=88 if problem == "different_id_ti" else None)
        if problem == "duplicate_part":
            add_part(target_id, 2)
    counts = import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert counts["matched"] == 2
    stored = list(db.session.scalars(select(TechnicalInspectionCode)))
    assert [(row.database_version_id, row.machine_id, row.pgu_machine_id) for row in stored] == [(1, source_id, source_part)]
    assert get_machine_technical_inspection_codes(target_id, 2) == []


def test_mapping_failure_rolls_back_codes_in_all_versions_and_excel(machine_factory):
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)

    def fail_after_write(connection, cursor, statement, parameters, context, executemany):
        if TechnicalInspectionCode.__tablename__ in statement and statement.lstrip().upper().startswith("INSERT"):
            raise SQLAlchemyError("code write failure")

    event.listen(db.engine, "after_cursor_execute", fail_after_write)
    try:
        with pytest.raises(SQLAlchemyError, match="code write failure"):
            import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    finally:
        event.remove(db.engine, "after_cursor_execute", fail_after_write)
    assert list(db.session.scalars(select(TechnicalInspectionCode))) == []
    assert list(db.session.scalars(select(Characteristic))) == []


def test_existing_assignment_in_target_version_is_not_overwritten(machine_factory):
    source_id, _ = machine_factory()
    counterpart_id, _ = machine_factory(version=2)
    other_id, _ = machine_factory(version=2, brand="Другая марка")
    share_identity(source_id, counterpart_id)
    db.session.add(TechnicalInspectionCode(
        database_version_id=2, equipment_code=CODE, machine_id=other_id,
    ))
    db.session.commit()
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert get_machine_technical_inspection_codes(counterpart_id, 2) == []
    assert get_machine_technical_inspection_codes(other_id, 2) == [CODE]
    counts = import_technical_characteristics(workbook_bytes(), 2, "tester", report_year=2023)
    assert counts["matched"] == 2
    assert {row.machine_id for row in db.session.scalars(select(Characteristic).where(Characteristic.database_version_id == 2))} == {other_id}


@pytest.mark.parametrize("pgu", [False, True])
@pytest.mark.parametrize("string_ids", [False, True])
def test_edit_saved_code_without_characteristics(http_client, machine_factory, pgu, string_ids):
    client, _ = http_client
    machine_id, _ = machine_factory()
    part_id = add_part(machine_id, 1) if pgu else None
    db.session.add(TechnicalInspectionCode(
        database_version_id=1, equipment_code=CODE, machine_id=machine_id, pgu_machine_id=part_id,
    ))
    db.session.commit()
    response = client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json={
        "machine_id": None if pgu else (str(machine_id) if string_ids else machine_id),
        "pgu_machine_id": str(part_id) if pgu and string_ids else part_id,
        "equipment_code": "0000123",
    })
    assert response.status_code == 200
    getter = get_pgu_machine_technical_inspection_codes if pgu else get_machine_technical_inspection_codes
    assert getter(part_id if pgu else machine_id, 1) == ["0000123"]
    assert list(db.session.scalars(select(Characteristic))) == []


@pytest.mark.parametrize("pgu", [False, True])
def test_card_string_ids_create_replace_and_clear_codes_across_versions(http_client, machine_factory, pgu):
    client, _ = http_client
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)
    source_part = add_part(source_id, 1) if pgu else None
    target_part = add_part(target_id, 2) if pgu else None
    previous_code = None

    for code in (CODE, "0000123", ""):
        payload = {
            "machine_id": None if pgu else str(source_id),
            "pgu_machine_id": str(source_part) if pgu else None,
            "equipment_code": code or None,
            "previous_code": previous_code,
        }
        response = client.patch(
            "/rational_structure/technical_characteristics/save_technical_inspection_code", json=payload,
        )
        assert response.status_code == 200
        assert response.get_json() == {"ok": True, "equipment_code": code}
        assert {(row.database_version_id, row.machine_id, row.pgu_machine_id, row.equipment_code)
                for row in db.session.scalars(select(TechnicalInspectionCode))} == (
            {(1, source_id, source_part, code), (2, target_id, target_part, code)} if code else set()
        )
        previous_code = code
    assert list(db.session.scalars(select(Characteristic))) == []


def test_code_storage_migration_upgrade_and_downgrade(database, monkeypatch, legacy_migration):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    migration = legacy_migration("rs26102601_add_technical_inspection_codes")
    with db.engine.begin() as connection:
        # SQLite has no information_schema; expose the version table in its test catalog.
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS information_schema")
        connection.execute(text(
            "CREATE TABLE information_schema.tables AS SELECT :schema AS table_schema, "
            "'gs_database_versions' AS table_name, 'BASE TABLE' AS table_type"
        ), {"schema": migration.SCHEMA_REFDATA})
        TechnicalInspectionCode.__table__.drop(connection)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        inspector = inspect(connection)
        columns = {column["name"] for column in inspector.get_columns(TechnicalInspectionCode.__tablename__)}
        assert columns == set(TechnicalInspectionCode.__table__.columns.keys())
        assert {index["name"] for index in inspector.get_indexes(TechnicalInspectionCode.__tablename__)} == {
            index.name for index in TechnicalInspectionCode.__table__.indexes
        }
        migration.downgrade()
        assert TechnicalInspectionCode.__tablename__ not in inspect(connection).get_table_names()
