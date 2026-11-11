"""Аудит проверяется реальными ORM-транзакциями без рабочей БД приложения."""
import sys
import json
from decimal import Decimal

import pytest
from flask import Flask, g, session as flask_session
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, registry

from app.common.models.audit_mixin import AuditMixin

from app.extensions import db
from app.logs.models.log_model import Log
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter as Consumption,
)
from app.energy_consumption.models.formula_text.energy_consumption_summary_formula_text_model import (
    EnergyConsumptionSummaryFormulaText as Formula,
)
from app.electrical_intensity.models.russia_federation_electrical_intensity_year_parameter_model import (
    RussiaFederationElectricalIntensityYearParameter as Intensity,
)
from app.electrical_intensity.models.russia_federation_electrical_intensity_coefficient_model import (
    RussiaFederationElectricalIntensityCoefficient as Coefficient,
)
from app.economics.models.federal_district_eat_consumption_parameter_model import (
    FederalDistrictEATConsumptionParameter as VedConsumption,
)
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption as GaesCharge,
)
from app.energy_consumption.services.consumption_change_logging import init_consumption_change_logging
from app.electrical_intensity.services import electrical_intensity_logging as ei_logging


_MODELS = {"Log": Log, "Consumption": Consumption, "Formula": Formula,
           "Intensity": Intensity, "Coefficient": Coefficient,
           "VedConsumption": VedConsumption, "GaesCharge": GaesCharge}


@pytest.fixture
def audit_env(monkeypatch):
    # Реальные таблицы, но отдельный registry: связи других разделов здесь не нужны.
    mappings = registry()
    for name, model in _MODELS.items():
        isolated = type(model.__name__, (AuditMixin,), {"__module__": model.__module__})
        mappings.map_imperatively(isolated, model.__table__)
        monkeypatch.setattr(sys.modules[__name__], name, isolated)
    monkeypatch.setattr(ei_logging, "Log", Log)
    init_consumption_change_logging()
    init_consumption_change_logging()  # Повторное создание Flask app не дублирует события.
    schemas = {table.schema: None for table in db.metadata.tables.values() if table.schema}
    engine = create_engine("sqlite://", execution_options={"schema_translate_map": schemas})
    for name in _MODELS:
        model = getattr(sys.modules[__name__], name)
        model.__table__.create(engine)
    app = Flask(__name__)
    app.secret_key = "test"
    with app.test_request_context("/energy_consumption/summary/cell", method="POST"):
        flask_session["username"] = "auditor"
        g.current_db_version = 9
        with Session(engine) as orm:
            yield orm, engine
    engine.dispose()
    mappings.dispose()


def records(orm):
    return orm.execute(select(Log.__table__).order_by(Log.id)).mappings().all()


def test_create_update_delete_with_exact_values_and_row_version(audit_env):
    orm, _ = audit_env
    row = Consumption(year_number=2026, database_version_id=3,
                      energy_consumption_mln_kvt_ch=Decimal("12.125"), note="Исходное")
    orm.add(row)
    orm.commit()
    row.energy_consumption_mln_kvt_ch = Decimal("13.0625")
    row.note = None
    row.perimeter_variant_code = "test_variant"
    orm.commit()
    orm.delete(row)
    orm.commit()

    logs = records(orm)
    assert [log["action"].split()[0] for log in logs] == ["Создание", "Изменение", "Удаление"]
    assert all(log["username"] == "auditor" and log["database_version_id"] == 3 for log in logs)
    assert all(log["module"] == "Спрос" for log in logs)
    update = json.loads(logs[1]["details"])
    assert update["контекст"]["year_number"] == 2026
    assert update["url"] == "/energy_consumption/summary/cell?"
    changes = update["изменения"]
    assert Decimal(changes["energy_consumption_mln_kvt_ch"]["было"]) == Decimal("12.125")
    assert Decimal(changes["energy_consumption_mln_kvt_ch"]["стало"]) == Decimal("13.0625")
    assert changes["note"] == {"было": "Исходное", "стало": None}
    assert changes["perimeter_variant_code"] == {"было": None, "стало": "test_variant"}
    deleted = json.loads(logs[2]["details"])
    assert Decimal(deleted["изменения"]["energy_consumption_mln_kvt_ch"]["было"]) == Decimal("13.0625")
    assert deleted["изменения"]["energy_consumption_mln_kvt_ch"]["стало"] is None


def test_no_log_for_unchanged_or_only_audit_fields(audit_env):
    orm, _ = audit_env
    row = Consumption(year_number=2026, energy_consumption_mln_kvt_ch=Decimal("1.25"))
    orm.add(row)
    orm.commit()
    # Значение присвоено после expire_on_commit: старое значение надо читать из БД.
    row.energy_consumption_mln_kvt_ch = Decimal("1.2500")
    row.modified_by = "technical"
    orm.commit()
    assert len(records(orm)) == 1


@pytest.mark.parametrize("operation", ["insert", "update", "delete"])
def test_rollback_reverts_audit_together_with_data(audit_env, operation):
    orm, _ = audit_env
    row = Consumption(year_number=2026, note="До")
    if operation != "insert":
        orm.add(row)
        orm.commit()
    baseline = len(records(orm))
    if operation == "insert":
        orm.add(row)
    elif operation == "update":
        row.note = "После"
    else:
        orm.delete(row)
    orm.flush()
    assert len(records(orm)) == baseline + 1
    orm.rollback()
    assert len(records(orm)) == baseline
    if operation != "insert":
        assert orm.get(Consumption, row.id).note == "До"


@pytest.mark.parametrize("key,module", [
    ("ei_coefficient_a", "Долгосрочный прогноз потребления"),
    ("unknown_test_formula", "Спрос"),
])
def test_formula_save_and_reset_audit(audit_env, key, module):
    orm, _ = audit_env
    formula = Formula(formula_key=key, formula_text="a + b")
    orm.add(formula)
    orm.commit()
    formula.formula_text = "a – b\nКомментарий"
    orm.commit()
    orm.delete(formula)
    orm.commit()
    logs = records(orm)
    assert len(logs) == 3
    assert all(log["module"] == module and log["database_version_id"] == 9 for log in logs)
    assert json.loads(logs[1]["details"])["изменения"]["formula_text"] == {
        "было": "a + b", "стало": "a – b\nКомментарий",
    }


def test_import_and_computed_cells_audit_each_version(audit_env):
    orm, _ = audit_env
    for version in (3, 4):
        orm.add(Intensity(row_kind="graph_point", year_number=2026,
                          parameter_value=Decimal("0.1234567890"), database_version_id=version))
        orm.add(Coefficient(coefficient_a=Decimal("0.000123456789"), database_version_id=version))
    orm.commit()
    logs = records(orm)
    assert len(logs) == 4
    assert {log["database_version_id"] for log in logs} == {3, 4}
    assert all(log["module"] == "Долгосрочный прогноз потребления" for log in logs)
    for log in logs:
        context = json.loads(log["details"])["контекст"]
        if "coefficient_a" in context:
            assert Decimal(context["coefficient_a"]) == Decimal("0.000123456789")
        else:
            assert Decimal(context["parameter_value"]) == Decimal("0.1234567890")


def test_linked_ved_and_gaes_changes_are_audited(audit_env):
    orm, _ = audit_env
    ved = VedConsumption(id_federal_district=1, id_economic_activity_type=2,
                         year_number=2026, database_version_id=3,
                         energy_consumption_mln_kvt_ch=Decimal("1.5"))
    gaes = GaesCharge(id_station=10, year_number=2026, database_version_id=3,
                      charge_consumption=Decimal("2.5"))
    orm.add_all([ved, gaes])
    orm.commit()
    ved.energy_consumption_mln_kvt_ch = Decimal("2.5")
    gaes.charge_consumption = None
    orm.commit()
    logs = records(orm)
    assert len(logs) == 4
    assert {log["module"] for log in logs} == {"Экономика", "Спрос"}
    changes = [json.loads(log["details"])["изменения"] for log in logs[2:]]
    assert any(change.get("charge_consumption", {}).get("стало", "missing") is None for change in changes)
    assert any("energy_consumption_mln_kvt_ch" in change for change in changes)


@pytest.mark.parametrize("is_import", [False, True])
def test_ei_operation_summary_rolls_back(audit_env, monkeypatch, is_import):
    orm, _ = audit_env
    monkeypatch.setattr(ei_logging.db, "session", orm)
    if is_import:
        ei_logging.log_electrical_intensity_excel_import("auditor", {"cells_written": 2}, database_version_id=3)
    else:
        ei_logging.log_electrical_intensity_cell_change("auditor", detail_chunks=["точка графика"], database_version_id=3)
    orm.flush()
    assert len(records(orm)) == 1
    orm.rollback()
    assert records(orm) == []
