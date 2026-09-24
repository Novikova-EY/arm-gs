# -*- coding: utf-8 -*-
"""Юнит-тесты помесячного прогноза выработки ГЭС/ГАЭС."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.generation.prospective_places.services.hydro_energy_forecast_services import (
    build_hydro_forecast_view,
    empty_hydro_forecast_by_scenario,
    hydro_forecast_field_name,
    save_hydro_forecast_from_form,
    sum_months,
)
from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
    HYDRO_MONTH_ORDER,
    PLACE_KIND_GES,
    SCENARIO_LOW_95,
    SCENARIO_MEDIUM_50,
)


def test_hydro_month_order_is_calendar_year():
    assert HYDRO_MONTH_ORDER == tuple(range(1, 13))


def test_sum_months_ignores_empty():
    assert sum_months({5: "10,5", 6: None, 7: "1.5"}) == Decimal("12.0")
    assert sum_months({}) is None


def test_hydro_forecast_field_name():
    assert hydro_forecast_field_name(SCENARIO_LOW_95, 5) == "hydro_gen_low_95_5"


@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.load_hydro_forecast_by_scenario"
)
def test_build_hydro_forecast_view_year_total(mock_load):
    mock_load.return_value = {
        SCENARIO_LOW_95: {m: (Decimal("1") if m == 5 else None) for m in HYDRO_MONTH_ORDER},
        SCENARIO_MEDIUM_50: {m: None for m in HYDRO_MONTH_ORDER},
    }
    view = build_hydro_forecast_view(PLACE_KIND_GES, 10, rounding_digits=1)
    assert view["scenarios"][0]["title"].startswith("Маловодные")
    assert view["scenarios"][0]["year_total"] == Decimal("1")
    assert view["month_names"][1] == "Январь"
    assert view["month_order"][0] == 1


@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.db"
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.log_to_db"
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.quick_fix_seq"
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.set_db_version_on_create"
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.get_current_db_version_id",
    return_value=37,
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.filter_by_db_version",
    side_effect=lambda q, _m: q,
)
@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.ProspectivePlaceHydroEnergyForecast"
)
def test_save_hydro_forecast_creates_row(
    mock_model,
    _filter,
    _ver,
    mock_set_ver,
    mock_fix,
    mock_log,
    mock_db,
):
    mock_model.query.filter.return_value = MagicMock(all=MagicMock(return_value=[]))
    created = []

    def _ctor(**kwargs):
        obj = SimpleNamespace(**kwargs)
        created.append(obj)
        return obj

    mock_model.side_effect = _ctor

    form = {
        "hydro_gen_low_95_5": "69,2",
        "hydro_gen_low_95_5_orig": "",
    }
    changes = save_hydro_forecast_from_form(
        SimpleNamespace(id=1),
        place_kind=PLACE_KIND_GES,
        place_id=10,
        form_data=form,
        entity_type="prospective_place_ges",
    )
    assert changes
    assert created
    assert created[0].month_number == 5
    assert created[0].scenario == SCENARIO_LOW_95
    mock_db.session.commit.assert_called_once()
    mock_log.assert_called_once()


def test_empty_hydro_forecast_by_scenario_has_both():
    data = empty_hydro_forecast_by_scenario()
    assert set(data) == {SCENARIO_LOW_95, SCENARIO_MEDIUM_50}
    assert set(data[SCENARIO_LOW_95]) == set(HYDRO_MONTH_ORDER)


def test_hydro_forecast_owner_none_for_other_types():
    from app.generation.prospective_places.services.hydro_energy_forecast_services import (
        hydro_forecast_owner_for_station,
    )
    from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
        PLACE_KIND_STATION,
    )

    tes = SimpleNamespace(
        id=3,
        external_code="abc",
        station_type=SimpleNamespace(name="ТЭС"),
    )
    assert hydro_forecast_owner_for_station(tes) is None

    ges = SimpleNamespace(
        id=9,
        external_code="",
        station_type=SimpleNamespace(name="ГЭС"),
    )
    assert hydro_forecast_owner_for_station(ges) == (PLACE_KIND_STATION, 9)

    gaes = SimpleNamespace(
        id=4,
        external_code=None,
        station_type=SimpleNamespace(name="ГАЭС"),
    )
    assert hydro_forecast_owner_for_station(gaes) == (PLACE_KIND_STATION, 4)


@patch(
    "app.generation.prospective_places.services.hydro_energy_forecast_services.StationProspectivePlaceGES"
)
def test_hydro_forecast_owner_uses_linked_ges_place(mock_model):
    from app.generation.prospective_places.services.hydro_energy_forecast_services import (
        hydro_forecast_owner_for_station,
    )

    place = SimpleNamespace(id=22, database_version_id=7)
    mock_model.query.filter.return_value.order_by.return_value.all.return_value = [place]
    station = SimpleNamespace(
        id=9,
        external_code="uuid-1",
        database_version_id=7,
        station_type=SimpleNamespace(name="ГЭС"),
    )
    assert hydro_forecast_owner_for_station(station) == (PLACE_KIND_GES, 22)
