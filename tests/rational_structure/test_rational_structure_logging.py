import pytest
from flask import g
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from test_technical_characteristics import database, http_client, workbook_bytes
from test_technical_characteristic_machine_links import machine_factory
from test_technical_inspection_codes import CODE, share_identity
from app.extensions import db
from app.logs.models.log_model import Log
from app.logs.services import logging_service, page_view_logging
from app.logs.services.logging_service import log_to_db as real_log_to_db
from app.rational_structure.models import EquipmentTechnicalCharacteristic as Characteristic, TechnicalInspectionCode
from app.rational_structure.routes import technical_characteristic_routes as routes
from app.rational_structure.services.technical_characteristic_import_services import import_technical_characteristics
from config import SCHEMA_LOGS


@pytest.fixture
def audit(http_client, monkeypatch):
    translations = dict(db.engine.get_execution_options()["schema_translate_map"])
    db.engine.update_execution_options(schema_translate_map={**translations, SCHEMA_LOGS: None})
    Log.__table__.create(db.engine)
    monkeypatch.setattr(logging_service, "log_to_db", real_log_to_db)
    monkeypatch.setattr(routes, "log_to_db", real_log_to_db)
    g.current_db_version = 1
    return http_client


def logs():
    return list(db.session.scalars(select(Log).order_by(Log.id)))


@pytest.mark.parametrize("path, title, tab", [
    ("/", "Рациональная структура", None),
    ("/technical_characteristics", "характеристики турбин", "Свод"),
    ("/technical_characteristics?equipment_type=steam", "характеристики турбин", "Паровые турбины"),
    ("/technical_characteristics?equipment_type=gas", "характеристики турбин", "Газовые турбины"),
    ("/technical_characteristics/hydro", "характеристики гидротурбин", None),
    ("/technical_characteristics/boilers/energy", "характеристики энергетических котлов", None),
    ("/technical_characteristics/boilers/water", "характеристики водогрейных котлов", None),
])
def test_page_and_tab_visits_are_recorded_once(audit, path, title, tab):
    client, _ = audit
    from jinja2 import ChoiceLoader, DictLoader

    client.application.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "<html><title>Технические характеристики</title><body>{% block content %}{% endblock %}</body></html>"}),
        client.application.jinja_loader,
    ])
    # The real application also runs the global HTML page logger.
    client.application.after_request(lambda response: (page_view_logging.maybe_log_page_view(response), response)[1])
    response = client.get("/rational_structure" + path)
    assert response.status_code == 200
    assert "Журнал изменений" not in response.get_data(as_text=True)
    record, = logs()
    assert record.action.startswith("Открыта страница:")
    assert title in record.action
    if tab:
        assert f"вкладка «{tab}»" in record.action
    assert "url=/rational_structure" in record.details
    assert record.username == "tester"
    assert record.database_version_id == 1
    assert record.module == "Рациональная структура"


def test_import_records_old_and_new_values_and_skips_identical_reimport(audit):
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    created = logs()
    assert len(created) == 2
    assert all(record.module == "Рациональная структура" for record in created)
    assert all(record.action.startswith("Добавлены") for record in created)
    assert all("код Техинспекции=001000465562" in record.details and "год=2023" in record.details for record in created)
    import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    assert len(logs()) == 2
    import_technical_characteristics(workbook_bytes(power=70), 1, "tester", report_year=2023)
    changed = logs()[2:]
    assert len(changed) == 2
    assert all("Установленная электрическая мощность, МВт: 60 → 70" in record.details for record in changed)
    assert all("Изменены" in record.action for record in changed)


@pytest.mark.parametrize("kind", ["hydro", "boiler_energy", "boiler_water"])
def test_import_audits_all_other_equipment_types(audit, kind):
    import_technical_characteristics(workbook_bytes(equipment_types=(kind,), report_year=2024), 1, "tester", report_year=2024)
    record, = logs()
    row, = db.session.scalars(select(Characteristic))
    assert record.entity_id == row.id
    assert record.entity_type == "rational_structure"
    assert "год=2024" in record.details


def test_manual_assignment_clear_and_noop_are_audited(audit, machine_factory):
    client, _ = audit
    source_id, _ = machine_factory()
    target_id, _ = machine_factory(version=2)
    share_identity(source_id, target_id)
    row = Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                         report_year=2024, match_status="partial")
    db.session.add(row)
    db.session.commit()
    payload = {"turbine_id": row.id, "machine_id": source_id}
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json=payload)
    assert response.status_code == 200
    records = logs()
    assert len(records) == 3  # Characteristic + remembered codes in both versions.
    assert f"ID агрегата: не указано → {source_id}" in records[0].details
    assert "Статус сопоставления: Частично → Совпало" in records[0].details
    assert any("версия БД=2" in record.details and f"machine_id={target_id}" in record.details for record in records)
    assert client.patch("/rational_structure/technical_characteristics/save_machine_id", json=payload).status_code == 200
    assert len(logs()) == 3
    payload["machine_id"] = ""
    assert client.patch("/rational_structure/technical_characteristics/save_machine_id", json=payload).status_code == 200
    records = logs()[3:]
    assert len(records) == 2
    assert f"ID агрегата: {source_id} → не указано" in records[0].details
    assert records[1].action == "Удалена связь кода Техинспекции"


def test_code_edit_records_previous_code_in_both_tables(audit, machine_factory):
    client, _ = audit
    machine_id, _ = machine_factory()
    db.session.add(Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                                  report_year=2024, match_status="matched", machine_id=machine_id))
    db.session.add(TechnicalInspectionCode(database_version_id=1, equipment_code=CODE, machine_id=machine_id))
    db.session.commit()
    payload = {"machine_id": machine_id, "equipment_code": "NEW-CODE"}
    assert client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json=payload).status_code == 200
    assert len(logs()) == 2
    assert all(f"Код оборудования: {CODE} → NEW-CODE" in record.details for record in logs())
    assert client.patch("/rational_structure/technical_characteristics/save_technical_inspection_code", json=payload).status_code == 200
    assert len(logs()) == 2


def test_failed_import_does_not_emit_successful_changes(audit):
    def fail_write(connection, cursor, statement, parameters, context, executemany):
        if Characteristic.__tablename__ in statement and statement.lstrip().upper().startswith("INSERT"):
            raise SQLAlchemyError("test failure")

    event.listen(db.engine, "after_cursor_execute", fail_write)
    try:
        with pytest.raises(SQLAlchemyError):
            import_technical_characteristics(workbook_bytes(), 1, "tester", report_year=2023)
    finally:
        event.remove(db.engine, "after_cursor_execute", fail_write)
    assert logs() == []
    assert list(db.session.scalars(select(Characteristic))) == []


def test_journal_paginates_filters_visits_and_excludes_other_modules(audit):
    client, _ = audit
    db.session.add_all([Log(username="tester", action=f"Изменение {i}", entity_type="rational_structure",
                            database_version_id=1) for i in range(55)])
    db.session.add(Log(username="tester", action="Чужое изменение", entity_type="station"))
    db.session.add(Log(username="tester", action="Открыта страница: Турбины", entity_type="rational_structure"))
    db.session.commit()
    first = client.get("/rational_structure/logs").get_json()
    assert len(first["logs"]) == 50
    assert first["has_more"] is True
    assert first["logs"][0]["action"] == "Изменение 54"
    assert first["logs"][0]["database_version"] == "v1"
    last = client.get("/rational_structure/logs?offset=50").get_json()
    assert len(last["logs"]) == 5
    assert last["has_more"] is False
    shown = client.get("/rational_structure/logs?show_page_events=true").get_json()
    assert shown["logs"][0]["action"] == "Открыта страница: Турбины"
    assert all(record["action"] != "Чужое изменение" for record in shown["logs"])
    assert len(logs()) == 57  # Fetching the journal is not itself a page visit.


def test_rejected_manual_edit_does_not_create_audit_entries(audit):
    client, _ = audit
    response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
        "turbine_id": 999999, "machine_id": "123",
    })
    assert response.status_code == 404
    assert logs() == []


def test_failed_manual_edit_does_not_create_audit_entries(audit, machine_factory):
    client, _ = audit
    machine_id, _ = machine_factory()
    row = Characteristic(database_version_id=1, equipment_type="steam", equipment_code=CODE,
                         report_year=2024, match_status="partial")
    db.session.add(row)
    db.session.commit()
    row_id = row.id

    def fail_write(connection, cursor, statement, parameters, context, executemany):
        if TechnicalInspectionCode.__tablename__ in statement and statement.lstrip().upper().startswith("INSERT"):
            raise SQLAlchemyError("test failure")

    event.listen(db.engine, "after_cursor_execute", fail_write)
    try:
        response = client.patch("/rational_structure/technical_characteristics/save_machine_id", json={
            "turbine_id": row_id, "machine_id": machine_id,
        })
    finally:
        event.remove(db.engine, "after_cursor_execute", fail_write)
    assert response.status_code == 500
    assert logs() == []
    db.session.expire_all()
    assert row.machine_id is None


def test_journal_requires_authentication(audit):
    client, _ = audit
    with client.session_transaction() as session:
        session.clear()
    assert client.get("/rational_structure/logs").status_code == 401
