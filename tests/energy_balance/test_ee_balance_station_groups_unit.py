from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment
from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401
import app.energy_consumption.models  # noqa: F401
import app.power_demand.models  # noqa: F401
import app.economics.models  # noqa: F401
import app.territories.models  # noqa: F401
import app.ecology.models  # noqa: F401

from app.extensions import db
from app.energy_balance.models.ee_balance_station_group_value_model import EeBalanceStationGroupValue
from app.generation.models.station.station_group_model import StationGroup
from app.energy_balance.routes import ee_balance_routes as routes

from app.energy_balance.services import ee_balance_station_group_services as persistence
from app.energy_balance.services.ee_balance_ves_ses_page_services import (
    _accumulate_station, _blank_total, _finalize_total, _station_group_payload,
    _station_payload, _ves_ses_station_row_sort_key,
)


def member(station_id, energy, *, hydro=False):
    row = _station_payload(
        SimpleNamespace(id=station_id, name=f"Станция {station_id}",
                        station_type=SimpleNamespace(name="ГЭС" if hydro else "АЭС")),
        [2026], {2026: Decimal(energy)}, {}, {2026: Decimal("10")},
        None, {}, {}, [], 1, commission_year=None, current_year=None,
    )
    row["coefficient_metrics_enabled"] = hydro
    return row


def group_payload(values=None, *, hydro=False):
    return _station_group_payload(
        SimpleNamespace(id=7, name="Общая группа"),
        [member(1, "100", hydro=hydro), member(2, "200", hydro=hydro)],
        values or {}, [2026], 1,
    )


def stored(energy=None, own_needs=None, percent=None):
    return {(7, 2026): SimpleNamespace(
        energy=Decimal(energy) if energy is not None else None,
        own_needs=Decimal(own_needs) if own_needs is not None else None,
        own_needs_percent=Decimal(percent) if percent is not None else None,
    )}


@pytest.fixture
def group_values_db(monkeypatch, app):
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {table.schema: None for table in db.metadata.tables.values()}
    })
    StationGroup.__table__.create(engine)
    EeBalanceStationGroupValue.__table__.create(engine)
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    monkeypatch.setattr(persistence, "_commit_with_retry", session.commit)
    with Flask(__name__).app_context():
        g.current_db_version = 7
        yield session
    session.remove()
    engine.dispose()


def test_values_are_independent_by_page_year_group_and_version(group_values_db):
    group = SimpleNamespace(id=7, name="Общая группа")
    for page, year, kind, value in [
        ("aes", 2026, "energy", "100"), ("ges", 2026, "energy", "200"),
        ("ses-ves", 2026, "energy", "300"), ("aes", 2027, "energy", "400"),
        ("aes", 2026, "own_needs", "5"),
    ]:
        persistence.save_group_value(group, page, year, kind, value, user=None)
    with pytest.raises(ValueError, match="автоматически"):
        persistence.save_group_value(group, "aes", 2026, "own_needs_percent", "10", user=None)
    persistence.save_group_value(group, "aes", 2026, "own_needs", "", user=None)
    persistence.save_group_value(group, "aes", 2026, "own_needs_percent", "7,25", user=None)
    persistence.save_group_value(group, "ges", 2026, "energy", "0", user=None)
    g.current_db_version = 8
    persistence.save_group_value(group, "aes", 2026, "energy", "900", user=None)
    g.current_db_version = 7
    group_values_db.expire_all()
    aes = persistence.load_group_values([7], "aes", [2026, 2027])
    assert aes[(7, 2026)].energy == Decimal("100")
    assert aes[(7, 2026)].own_needs is None
    assert aes[(7, 2026)].own_needs_percent == Decimal("7.25")
    assert aes[(7, 2027)].energy == Decimal("400")
    assert persistence.load_group_values([7], "ges", [2026])[(7, 2026)].energy == 0
    assert persistence.load_group_values([7], "ses-ves", [2026])[(7, 2026)].energy == 300
    assert persistence.load_group_values([8], "aes", [2026]) == {}
    persistence.save_group_value(group, "aes", 2026, "energy", "", user=None)
    assert persistence.load_group_values([7], "aes", [2026])[(7, 2026)].energy is None
    g.current_db_version = 8
    assert persistence.load_group_values([7], "aes", [2026])[(7, 2026)].energy == 900


def test_api_denies_edits_without_permission(monkeypatch):
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: False)
    with Flask(__name__).test_request_context("/", method="PATCH", json={}):
        response, status = routes.ee_balance_station_group_value.__wrapped__()
    assert status == 403
    assert response.get_json()["ok"] is False


def test_api_saves_scoped_group_values_and_rejects_other_versions(group_values_db, monkeypatch):
    group_values_db.add(StationGroup(id=7, name="Группа", database_version_id=7))
    group_values_db.commit()
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: True)
    app = Flask(__name__)
    app.secret_key = "test"
    payload = dict(group_id=7, page_key="ses-ves", year=2026, kind="energy", value="123,25", rounding_digits=1)
    with app.test_request_context("/", method="PATCH", json=payload):
        g.current_db_version = 7
        response = routes.ee_balance_station_group_value.__wrapped__()
        assert response.get_json()["display"] == "123,3"
        assert response.get_json()["raw"] == "123,25"
    assert persistence.load_group_values([7], "ses-ves", [2026])[(7, 2026)].energy == Decimal("123.25")
    with app.test_request_context("/", method="PATCH", json=payload):
        g.current_db_version = 8
        response, status = routes.ee_balance_station_group_value.__wrapped__()
        assert status == 404
    with app.test_request_context("/", method="PATCH", json={**payload, "kind": "owner"}):
        g.current_db_version = 7
        response, status = routes.ee_balance_station_group_value.__wrapped__()
        assert status == 400


def test_group_defaults_to_member_generation_and_capacity_but_has_its_own_needs():
    row = group_payload()
    assert row["energy"] == {2026: Decimal("300")}
    assert row["capacity"] == {2026: Decimal("20")}
    assert row["own_needs"] == {2026: None}
    assert row["energy_stored"] == {2026: False}
    assert len(row["members"]) == 2


@pytest.mark.parametrize("hydro", [False, True])
def test_totals_use_group_override_once_then_ungrouped_stations(hydro):
    row = group_payload(stored("500", "25"), hydro=hydro)
    total = _blank_total([2026])
    _accumulate_station(total, row)
    _accumulate_station(total, member(3, "40", hydro=hydro))
    result = _finalize_total(total, [2026], 1, "Всего", "russia_total")
    assert result["energy_raw"] == {2026: "540"}
    assert result["capacity_raw"] == {2026: "30"}
    assert row["own_needs_display"] == {2026: "5,0"}
    assert row["delivery_display"] == {2026: "475,0"}
    assert row["members"][0]["energy"][2026] == Decimal("100")


def test_manual_group_percent_is_applied_to_unrounded_generation_and_totals():
    row = group_payload(stored("0.1578", percent="7.25"))
    assert row["own_needs"][2026] == Decimal("0.0114405")
    assert row["own_needs_energy_display"] == {2026: "0,0"}
    assert row["own_needs_energy_raw"] == {2026: "0,0114405"}
    assert row["delivery"][2026] == Decimal("0.1463595")
    assert row["own_needs_percent_calculated"] == {2026: False}
    total = _blank_total([2026])
    _accumulate_station(total, row)
    result = _finalize_total(total, [2026], 3, "Всего", "russia_total")
    assert result["own_needs_energy_raw"] == {2026: "0,0114405"}


def test_zero_group_override_is_not_replaced_by_member_sum():
    row = group_payload(stored("0", "0"))
    assert row["energy"] == {2026: Decimal("0")}
    assert row["energy_stored"] == {2026: True}


def test_groups_sort_before_ungrouped_stations():
    rows = [member(1, "100"), group_payload()]
    assert sorted(rows, key=_ves_ses_station_row_sort_key)[0]["is_group"]


@pytest.mark.parametrize("page_key,kind,value", [
    ("gaes", "energy", "1"), ("aes", "owner", "1"),
    ("aes", "energy", "-1"), ("ges", "own_needs_percent", "101"),
    ("ses-ves", "own_needs", "NaN"),
])
def test_group_save_rejects_invalid_inputs_before_database_access(page_key, kind, value):
    with pytest.raises(ValueError):
        persistence.save_group_value(SimpleNamespace(id=7, name="Группа"),
                                     page_key, 2026, kind, value, user=None)


def test_group_percent_is_locked_when_own_needs_energy_is_stored(monkeypatch):
    monkeypatch.setattr(persistence, "load_group_values", lambda *args: stored("100", "5"))
    with pytest.raises(ValueError, match="автоматически"):
        persistence.save_group_value(SimpleNamespace(id=7, name="Группа"),
                                     "ges", 2026, "own_needs_percent", "7", user=None)


@pytest.mark.parametrize("hydro,focus", [(False, False), (True, True)])
def test_group_uses_aes_editors_also_on_ges_and_renewables_pages(hydro, focus):
    source = Path("app/templates/energy_balance/ee_balance/ee_balance_ves_ses.html").read_text(encoding="utf-8")
    macros = source[source.index("    {% macro ves_raw_attrs"):source.index("    <style>")]
    template = Environment(autoescape=True).from_string(macros + "{{ focus_extra_rows(row) }}")
    html = template.render(row={"kind": "station", **group_payload(stored("100", "5"), hydro=hydro)},
        years=[2026], owner_years=[], is_aes_focus=False, is_station_focus=focus,
        is_snee_focus=False, is_coefficient_focus=hydro, split_hydro_own_needs=hydro,
        can_edit=True)
    assert 'data-kind="own_needs"' in html
    assert 'data-kind="own_needs_percent"' in html
    assert 'data-kind="coefficient"' not in html
    assert 'data-is-group="1"' in html


@pytest.mark.parametrize("page_key", ["aes", "ges", "ses-ves"])
@pytest.mark.parametrize("value", ["5", "0"])
def test_group_percent_prolongs_to_end_preserving_locked_years_and_other_values(group_values_db, page_key, value):
    group = SimpleNamespace(id=7, name="Группа")
    for year, percent in [(2025, "1"), (2026, value), (2027, "3"), (2028, "9"), (2030, "8")]:
        persistence.save_group_value(group, page_key, year, "own_needs_percent", percent, user=None)
    persistence.save_group_value(group, page_key, 2027, "own_needs", "2", user=None)
    persistence.save_group_value(group, page_key, 2028, "energy", "100", user=None)
    persistence.save_group_value(group, page_key, 2026, "own_needs_percent", value, user=None, end_year=2029)
    group_values_db.expire_all()
    rows = persistence.load_group_values([7], page_key, range(2025, 2031))
    assert [rows[(7, year)].own_needs_percent for year in range(2025, 2031)] == [
        Decimal("1"), Decimal(value), Decimal("3"), Decimal(value), Decimal(value), Decimal("8")
    ]
    assert rows[(7, 2027)].own_needs == Decimal("2")
    assert rows[(7, 2028)].energy == Decimal("100")
    persistence.save_group_value(group, page_key, 2026, "own_needs_percent", "", user=None, end_year=2029)
    group_values_db.expire_all()
    rows = persistence.load_group_values([7], page_key, range(2026, 2030))
    assert rows[(7, 2026)].own_needs_percent is None
    assert rows[(7, 2028)].own_needs_percent == Decimal(value)
    assert rows[(7, 2029)].own_needs_percent == Decimal(value)


def test_group_percent_prolongation_rolls_back_all_years_on_failure(group_values_db, monkeypatch):
    group = SimpleNamespace(id=7, name="Группа")
    persistence.save_group_value(group, "ges", 2026, "own_needs_percent", "1", user=None)
    persistence.save_group_value(group, "ges", 2027, "own_needs_percent", "2", user=None)

    def fail_commit():
        group_values_db.flush()
        raise RuntimeError("Save failed")

    monkeypatch.setattr(persistence, "_commit_with_retry", fail_commit)
    with pytest.raises(RuntimeError, match="Save failed"):
        persistence.save_group_value(group, "ges", 2026, "own_needs_percent", "5", user=None, end_year=2028)
    rows = persistence.load_group_values([7], "ges", range(2026, 2029))
    assert rows[(7, 2026)].own_needs_percent == Decimal("1")
    assert rows[(7, 2027)].own_needs_percent == Decimal("2")
    assert (7, 2028) not in rows


def test_api_prolongs_group_percent_and_returns_only_editable_year_updates(group_values_db, monkeypatch):
    group = StationGroup(id=7, name="Группа", database_version_id=7)
    group_values_db.add(group)
    group_values_db.commit()
    persistence.save_group_value(group, "ges", 2027, "own_needs", "2", user=None)
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: True)
    app = Flask(__name__)
    app.secret_key = "test"
    payload = dict(group_id=7, page_key="ges", year=2026, end_year=2028,
                   kind="own_needs_percent", value="7,25", rounding_digits=1)
    with app.test_request_context("/", method="PATCH", json=payload):
        g.current_db_version = 7
        response = routes.ee_balance_station_group_value.__wrapped__()
        assert response.get_json()["own_needs_percent_updates"] == {
            "2026": {"display": "7,3", "raw": "7,25"},
            "2028": {"display": "7,3", "raw": "7,25"},
        }
    group_values_db.expire_all()
    rows = persistence.load_group_values([7], "ges", range(2026, 2029))
    assert rows[(7, 2026)].own_needs_percent == Decimal("7.25")
    assert rows[(7, 2027)].own_needs_percent is None
    assert rows[(7, 2028)].own_needs_percent == Decimal("7.25")
    with app.test_request_context("/", method="PATCH", json={**payload, "value": ""}):
        g.current_db_version = 7
        response = routes.ee_balance_station_group_value.__wrapped__()
        assert response.get_json()["own_needs_percent_updates"] == {"2026": {"display": "", "raw": ""}}
    assert persistence.load_group_values([7], "ges", [2028])[(7, 2028)].own_needs_percent == Decimal("7.25")


@pytest.mark.parametrize("end_year", [2025, 2201, "bad"])
def test_api_rejects_invalid_group_percent_period(monkeypatch, end_year):
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: True)
    with Flask(__name__).test_request_context("/", method="PATCH", json=dict(
        group_id=7, page_key="ges", year=2026, end_year=end_year, kind="own_needs_percent", value="5"
    )):
        response, status = routes.ee_balance_station_group_value.__wrapped__()
    assert status == 400
    assert response.get_json()["ok"] is False
