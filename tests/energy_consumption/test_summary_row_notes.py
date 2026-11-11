from copy import deepcopy
from importlib import import_module

import pytest
from flask import Flask
from sqlalchemy import create_engine, select
from sqlalchemy.orm import scoped_session, sessionmaker

from app.extensions import db
from app.logs.models.log_model import Log
from app.energy_consumption.models.summary_row_note_model import EnergyConsumptionSummaryRowNote as Note
from app.energy_consumption.services import summary_row_note_services as notes


@pytest.fixture
def note_database(monkeypatch):
    for module in ("electrical_intensity", "economics", "energy_consumption", "energy_balance", "power_demand", "ecology", "territories", "rational_structure"):
        import_module(f"app.{module}.models")
    schemas = {table.schema: None for table in db.metadata.tables.values() if table.schema}
    engine = create_engine("sqlite://", execution_options={"schema_translate_map": schemas})
    Note.__table__.create(engine)
    Log.__table__.create(engine)
    orm = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", orm)
    monkeypatch.setattr("app.common.services.database_version_services.get_current_version", lambda: 7)
    invalidations = []

    def invalidate(**kwargs):
        assert not orm().in_transaction()
        invalidations.append(kwargs["version_id"])

    monkeypatch.setattr("app.energy_consumption.services.ec_display_cache.invalidate_energy_consumption_display_caches", invalidate)
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context():
        yield orm, invalidations
    orm.remove()
    engine.dispose()


def rows():
    base = dict(entity_label="Энергосистема", entity_kind="group",
                demand_model_name="UnionEnergySystemEnergyConsumptionParameter",
                parent_fk_column="id_union_energy_system", parent_id=2,
                perimeter_variant_code="without_nt", entity_note_text="Старое примечание")
    return [dict(base, parameter_key="energy_consumption_mln_kvt_ch"),
            dict(base, parameter_key="energy_consumption_yoy_growth_pct", pd_ec_formula_derived_row=True),
            dict(base, parameter_key="energy_consumption_sipr_mln_kvt_ch", perimeter_variant_code="with_nt")]


def test_notes_are_independent_for_each_parameter_perimeter_and_version(note_database):
    orm, invalidations = note_database
    source = rows()
    keys = [notes.summary_row_note_key(row) for row in source]
    assert len(set(keys)) == 3
    original_values = deepcopy(source)
    notes.save_summary_row_note(keys[0], "Ручная строка", version_id=7, user="editor")
    notes.save_summary_row_note(keys[1], "Расчетная строка\r\nПояснение", version_id=7, user="editor")
    notes.save_summary_row_note(keys[0], "Другая версия", version_id=8, user="editor")
    notes.attach_summary_row_notes({"summary_rows": source})
    assert [row["entity_note_text"] for row in source] == [
        "Ручная строка", "Расчетная строка\nПояснение", "Старое примечание",
    ]
    assert all(row["show_entity_note_cell"] for row in source)
    assert len(list(orm.scalars(select(Note)))) == 3
    assert invalidations == [7, 7, 8]
    for before, after in zip(original_values, source):
        assert before["parameter_key"] == after["parameter_key"]


def test_clearing_note_does_not_restore_legacy_note_on_reload(note_database):
    orm, _ = note_database
    row = rows()[0]
    key = notes.summary_row_note_key(row)
    notes.save_summary_row_note(key, "Текст", version_id=7, user="editor")
    notes.save_summary_row_note(key, "", version_id=7, user="editor")
    notes.attach_summary_row_notes({"summary_rows": [row]})
    assert row["entity_note_text"] == ""
    assert len(list(orm.scalars(select(Note)))) == 1


@pytest.mark.parametrize("key,value,version", [
    ("invalid", "text", 7), ("a" * 64, "text", None),
    ("a" * 64, "x" * 4001, 7), ("a" * 64, None, 7),
])
def test_invalid_note_does_not_write_or_invalidate(note_database, key, value, version):
    orm, invalidations = note_database
    with pytest.raises(ValueError):
        notes.save_summary_row_note(key, value, version_id=version, user="editor")
    assert list(orm.scalars(select(Note))) == []
    assert invalidations == []


def test_synthetic_row_keys_are_stable_across_year_filters_and_distinct_by_entity():
    row = dict(entity_kind="verification", entity_label="Проверка А", parameter_key="energy_consumption_mln_kvt_ch")
    key = notes.summary_row_note_key(row)
    assert key == notes.summary_row_note_key(dict(row, year_values=["10"], show_entity_cell=False))
    assert key != notes.summary_row_note_key(dict(row, entity_label="Проверка Б"))


@pytest.mark.parametrize("allowed,version,status", [(True, 7, 200), (True, 8, 400), (False, 7, 403)])
def test_note_endpoint_checks_permission_and_current_version(note_database, app, monkeypatch, allowed, version, status):
    from app.energy_consumption.routes import energy_consumption_summary_routes as routes
    from types import SimpleNamespace

    app.register_blueprint(routes.energy_consumption_bp, url_prefix="/energy_consumption")
    monkeypatch.setattr(routes, "can_edit_energy_consumption", lambda user: allowed)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace(username="editor"))
    monkeypatch.setattr(routes, "get_current_version", lambda: 7)
    response = app.test_client().post("/energy_consumption/summary/note", json={
        "row_key": "a" * 64, "value": "Note", "database_version_id": version,
    })
    assert response.status_code == status
    orm, invalidations = note_database
    stored = list(orm.scalars(select(Note)))
    assert len(stored) == (1 if status == 200 else 0)
    assert invalidations == ([7] if status == 200 else [])
