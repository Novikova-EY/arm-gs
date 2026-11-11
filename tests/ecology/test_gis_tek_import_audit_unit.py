"""Аудит импорта: сохраненные значения до/после, создание, очистка и откат."""
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, registry

from app.ecology.services import ecology_logging_services as audit
from app.ecology.services import gis_tek_import_services as importer
from app.ecology.services.gis_tek_constants import REPORT_PG, REPORT_ZV, SHEET_NAMES, VALUE_COLUMNS


@pytest.fixture(params=[REPORT_PG, REPORT_ZV])
def import_env(request, monkeypatch):
    kind = request.param
    mapper_registry = registry()
    table = importer.REPORT_MODELS[kind].__table__
    engine = create_engine("sqlite://")
    records = []
    with engine.connect() as connection:
        connection.exec_driver_sql(f"ATTACH DATABASE ':memory:' AS {table.schema}")
        model = type("Report", (), {})
        mapper_registry.map_imperatively(model, table)
        table.create(connection)
        connection.commit()
        with Session(connection) as session:
            model.query = session.query(model)
            monkeypatch.setitem(importer.REPORT_MODELS, kind, model)
            monkeypatch.setattr(importer, "db", SimpleNamespace(session=session))
            monkeypatch.setattr(importer, "get_current_db_version_id", lambda: 1)
            monkeypatch.setattr(importer, "_load_equipment_groups_by_numb", lambda v: {})
            monkeypatch.setattr(importer, "_known_year_numbers", lambda v: {2026})
            monkeypatch.setattr("app.ecology.services.analysis_pg_param_services.seed_missing_analysis_pg_params_from_reports", lambda slug: 0)

            def save_log(user, action, details, **kwargs):
                records.append(dict(user=user, action=action, details=details, **kwargs))

            monkeypatch.setattr(audit, "log_to_db", save_log)
            monkeypatch.setattr(importer, "log_to_db", save_log)
            field = "gas_consumption_tce" if kind == REPORT_PG else "sulfur_dioxide"
            yield SimpleNamespace(kind=kind, model=model, session=session,
                                  records=records, field=field)
    engine.dispose()
    mapper_registry.dispose()


def workbook(env, amount, name="Станция"):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET_NAMES[env.kind]
    sheet.append([None] * 5)
    sheet.append([None, SHEET_NAMES[env.kind]])
    sheet.append(["№_станции", "Год", "Электростанция (ГИС ТЭК)", "Тип станции",
                  dict(VALUE_COLUMNS[env.kind])[env.field]])
    sheet.append([708, 2026, name, "ТЭЦ", amount])
    buf = BytesIO()
    book.save(buf)
    return buf.getvalue()


def changes(env):
    return [r for r in env.records if r["action"].startswith("Изменение:")]


def test_import_logs_created_updated_cleared_and_unchanged_values(import_env):
    env = import_env
    result = importer.import_gis_tek_from_xlsx_bytes(workbook(env, 10), env.kind, "import-user")
    assert result["created"] == 1
    assert env.model.query.one().__dict__[env.field] == 10
    created = changes(env)
    assert len(created) == 1
    assert "было не указано → стало 10" in created[0]["details"]
    assert created[0]["user"] == "import-user"
    assert all(r["entity_type"] == "ecology" for r in env.records)
    assert "год=2026" in created[0]["details"]
    assert "numb1120)=708" in created[0]["details"]

    env.records.clear()
    result = importer.import_gis_tek_from_xlsx_bytes(workbook(env, 12.5, "Новое имя"), env.kind, "import-user")
    assert result["updated"] == 1
    assert env.model.query.one().__dict__[env.field] == 12.5
    assert "было 10 → стало 12,5" in changes(env)[0]["details"]
    assert "было Станция → стало Новое имя" in changes(env)[0]["details"]

    env.records.clear()
    result = importer.import_gis_tek_from_xlsx_bytes(workbook(env, 12.5, "Новое имя"), env.kind, "import-user")
    assert result["updated"] == 0
    assert changes(env) == []

    env.records.clear()
    importer.import_gis_tek_from_xlsx_bytes(workbook(env, None, "Новое имя"), env.kind, "import-user")
    assert getattr(env.model.query.one(), env.field) is None
    assert "было 12,5 → стало не указано" in changes(env)[0]["details"]


def test_failed_import_does_not_log_unsaved_changes(import_env, monkeypatch):
    env = import_env
    importer.import_gis_tek_from_xlsx_bytes(workbook(env, 10), env.kind, "import-user")
    env.records.clear()

    def fail_commit():
        raise IntegrityError("INSERT", {}, Exception("constraint"))

    monkeypatch.setattr(env.session, "commit", fail_commit)
    with pytest.raises(ValueError, match="Ошибка сохранения"):
        importer.import_gis_tek_from_xlsx_bytes(workbook(env, 99), env.kind, "import-user")
    assert getattr(env.model.query.one(), env.field) == 10
    assert env.records == []
