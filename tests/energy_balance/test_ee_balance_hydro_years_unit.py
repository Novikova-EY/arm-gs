from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import re

import pytest
from flask import Flask, g
from jinja2 import Environment
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401
import app.energy_consumption.models  # noqa: F401
import app.power_demand.models  # noqa: F401
import app.economics.models  # noqa: F401
import app.territories.models  # noqa: F401
import app.ecology.models  # noqa: F401
import app.rational_structure.models  # noqa: F401
from app.energy_balance.models.ee_balance_station_own_needs_coefficient_model import EeBalanceStationOwnNeedsCoefficient as Coefficient
from app.energy_balance.services import ee_balance_hydro_own_needs_services as service
from app.energy_balance.services.ee_balance_ves_ses_page_services import _hydro_metric_maps
from app.energy_balance.routes import ee_balance_routes as routes
from app.extensions import db


@pytest.fixture
def coefficients(monkeypatch):
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {table.schema: None for table in db.metadata.tables.values()}
    })
    Coefficient.__table__.create(engine)
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    monkeypatch.setattr(service, "_commit_with_retry", session.commit)
    with Flask(__name__).app_context():
        g.current_db_version = 7
        yield session
    session.remove()
    engine.dispose()


def test_yearly_save_reload_clear_preserves_other_years_and_versions(coefficients):
    coefficients.add_all([
        Coefficient(id_station=1, station_type_key="ges", coefficient=Decimal("0.025"), database_version_id=7),
        Coefficient(id_station=1, station_type_key="ges", year_number=2026, coefficient=Decimal("0.09"), database_version_id=8),
        Coefficient(id_station=2, station_type_key="ges", coefficient=Decimal("0.05"), database_version_id=7),
    ])
    coefficients.commit()
    assert service.load_hydro_own_needs_coefficients([1], "ges", [2026, 2027]) == {
        1: {2026: Decimal("0.025"), 2027: Decimal("0.025")}
    }
    service.save_hydro_own_needs_coefficient(1, "ges", "0,01", year=2026)
    service.save_hydro_own_needs_coefficient(1, "ges", "0,02", year=2027)
    coefficients.expire_all()
    assert service.load_hydro_own_needs_coefficients([1], "ges", [2026, 2027, 2028]) == {
        1: {2026: Decimal("0.01"), 2027: Decimal("0.02"), 2028: Decimal("0.025")}
    }
    service.save_hydro_own_needs_coefficient(1, "ges", "", year=2026)
    coefficients.expire_all()
    assert service.load_hydro_own_needs_coefficients([1, 2], "ges", [2026, 2027]) == {
        1: {2026: None, 2027: Decimal("0.02")},
        2: {2026: Decimal("0.05"), 2027: Decimal("0.05")},
    }
    assert coefficients.query(Coefficient).filter_by(database_version_id=8).one().coefficient == Decimal("0.09")
    service.save_hydro_own_needs_coefficient(1, "ges", "0", year=2026)
    assert service.load_hydro_own_needs_coefficients([1], "ges", [2026])[1][2026] == 0


def test_hydro_generation_uses_the_coefficient_of_each_year():
    maps = _hydro_metric_maps({2026: Decimal("1"), 2027: Decimal("2"), 2028: None},
                              {year: Decimal("100") for year in (2026, 2027, 2028)}, [2026, 2027, 2028], 1)
    assert maps["own_needs_display"] == {2026: "1,0", 2027: "2,0", 2028: ""}
    assert maps["delivery_display"] == {2026: "99,0", 2027: "98,0", 2028: ""}


@pytest.mark.parametrize("can_edit", [True, False])
def test_yearly_coefficient_cells_are_rendered_separately(can_edit):
    source = Path("app/templates/energy_balance/ee_balance/ee_balance_ves_ses.html").read_text(encoding="utf-8")
    macros = source[source.index("    {% macro ves_raw_attrs"):source.index("    <style>")]
    template = Environment(autoescape=True).from_string(macros + "{{ focus_extra_rows(row) }}")
    row = dict(kind="station", id=1, name="ГЭС", **_hydro_metric_maps(
        {2026: Decimal("1"), 2027: Decimal("2")}, {2026: 100, 2027: 100}, [2026, 2027], 1))
    html = template.render(row=row, years=[2026, 2027], owner_years=[], is_station_focus=True,
                           is_aes_focus=False, is_snee_focus=False, is_coefficient_focus=True,
                           split_hydro_own_needs=True, can_edit=can_edit)
    coefficient_row = re.search(r'<tr[^>]*data-ves-metric="own_needs_coefficient".*?</tr>', html, re.S).group()
    assert 'colspan=' not in coefficient_row
    assert coefficient_row.count('data-ves-col="own-needs-coefficient"') == 2
    assert coefficient_row.count('data-kind="coefficient"') == (2 if can_edit else 0)
    assert row["own_needs_coefficient_by_year_display"] == {2026: "1", 2027: "2"}


@pytest.fixture
def hydro_api(coefficients, monkeypatch):
    station = SimpleNamespace(id=1, name="ГЭС", station_type=SimpleNamespace(name="ГЭС"))
    query = Mock()
    query.options.return_value.get.return_value = station
    monkeypatch.setattr(routes, "Station", SimpleNamespace(query=query, station_type=routes.Station.station_type))
    monkeypatch.setattr(routes, "_can_edit_ves_ses_energy", lambda: True)
    app = Flask(__name__)
    app.secret_key = "test"
    return app


def test_api_requires_year_and_saves_only_that_year(coefficients, hydro_api):
    app = hydro_api
    payload = dict(station_id=1, kind="coefficient", value="0,03")
    with app.test_request_context("/", method="PATCH", json=payload):
        response, status = routes.ee_balance_ves_ses_value.__wrapped__()
        assert status == 400
    with app.test_request_context("/", method="PATCH", json={**payload, "year": 2026}):
        g.current_db_version = 7
        response = routes.ee_balance_ves_ses_value.__wrapped__()
        assert response.get_json()["year"] == 2026
        assert response.get_json()["display"] == "0,03"
    assert service.load_hydro_own_needs_coefficients([1], "ges", [2026, 2027]) == {
        1: {2026: Decimal("0.03"), 2027: None}
    }


@pytest.mark.parametrize("raw_value", ["0,03", "0"])
def test_api_extends_coefficient_through_displayed_end_year(coefficients, hydro_api, raw_value):
    for year in range(2025, 2033):
        coefficients.add(Coefficient(id_station=1, station_type_key="ges", year_number=year,
                                     coefficient=Decimal("0.09"), database_version_id=7))
    coefficients.add_all([
        Coefficient(id_station=2, station_type_key="ges", year_number=2028, coefficient=Decimal("0.08"), database_version_id=7),
        Coefficient(id_station=1, station_type_key="ges", year_number=2028, coefficient=Decimal("0.07"), database_version_id=8),
    ])
    coefficients.commit()
    with hydro_api.test_request_context("/", method="PATCH", json={
        "station_id": 1, "kind": "coefficient", "year": 2027, "start_year": 2026,
        "end_year": 2031, "value": raw_value,
    }):
        g.current_db_version = 7
        data = routes.ee_balance_ves_ses_value.__wrapped__().get_json()
    assert data["ok"]
    assert set(data["coefficient_updates"]) == {str(year) for year in range(2027, 2032)}
    coefficients.expire_all()
    expected = Decimal(raw_value.replace(",", "."))
    loaded = service.load_hydro_own_needs_coefficients([1], "ges", list(range(2025, 2033)))[1]
    assert loaded == {year: expected if 2027 <= year <= 2031 else Decimal("0.09") for year in range(2025, 2033)}
    assert coefficients.query(Coefficient).filter_by(id_station=2).one().coefficient == Decimal("0.08")
    assert coefficients.query(Coefficient).filter_by(database_version_id=8).one().coefficient == Decimal("0.07")


def test_api_clears_only_selected_year_even_with_prolongation_period(coefficients, hydro_api):
    service.save_hydro_own_needs_coefficient(1, "ges", "0.02", year=2026, end_year=2031)
    with hydro_api.test_request_context("/", method="PATCH", json={
        "station_id": 1, "kind": "coefficient", "year": 2028, "end_year": 2031, "value": "",
    }):
        g.current_db_version = 7
        data = routes.ee_balance_ves_ses_value.__wrapped__().get_json()
    assert data["coefficient_updates"] == {"2028": {"display": "", "raw": ""}}
    coefficients.expire_all()
    assert service.load_hydro_own_needs_coefficients([1], "ges", list(range(2026, 2032)))[1] == {
        year: None if year == 2028 else Decimal("0.02") for year in range(2026, 2032)
    }


@pytest.mark.parametrize("end_year,value", [(2025, "0.02"), (999999, "0.02"), ("bad", "0.02"), (2031, "-1"), (2031, "bad")])
def test_invalid_prolongation_request_does_not_save(coefficients, hydro_api, end_year, value):
    with hydro_api.test_request_context("/", method="PATCH", json={
        "station_id": 1, "kind": "coefficient", "year": 2026, "end_year": end_year, "value": value,
    }):
        g.current_db_version = 7
        response, status = routes.ee_balance_ves_ses_value.__wrapped__()
    assert status == 400
    assert coefficients.query(Coefficient).count() == 0
