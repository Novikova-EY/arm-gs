from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import ee_balance_ves_ses_page_services as aes_page_services
from app.energy_balance.services.ee_balance_hydro_own_needs_services import (
    save_hydro_own_needs_coefficient,
)
from app.energy_balance.services.ee_balance_ves_ses_page_services import (
    _aes_delivery_energy,
    _aes_metric_maps,
    _aes_own_needs_percent,
    _accumulate_station,
    _blank_total,
    _finalize_total,
    _hydro_metric_maps,
)


def test_aes_own_needs_and_delivery_use_generation_and_capacity():
    capacity = Decimal("1000")
    generation = Decimal("7000")
    own_needs_percent = capacity / generation * Decimal(100)

    assert _aes_own_needs_percent(capacity, generation) == own_needs_percent
    assert _aes_delivery_energy(capacity, generation) == generation - (
        own_needs_percent / generation * Decimal(100)
    )


def test_focus_page_type_ids_are_separated_by_technology(monkeypatch):
    monkeypatch.setattr(
        aes_page_services,
        "get_station_type_list_full",
        lambda: [
            SimpleNamespace(id=1, name="АЭС"),
            SimpleNamespace(id=2, name="АЭС плавучая"),
            SimpleNamespace(id=3, name="ТЭС"),
            SimpleNamespace(id=4, name="ГЭС"),
            SimpleNamespace(id=5, name="ГАЭС"),
        ],
    )

    assert aes_page_services.aes_station_type_ids() == [1, 2]
    assert aes_page_services.ges_station_type_ids() == [4]
    assert aes_page_services.gaes_station_type_ids() == [5]


def test_hydro_coefficient_save_rejects_unknown_type_and_negative_values():
    with pytest.raises(ValueError, match="только для ГЭС и ГАЭС"):
        save_hydro_own_needs_coefficient(1, "aes", "0.1")
    with pytest.raises(ValueError, match="неотрицательным"):
        save_hydro_own_needs_coefficient(1, "ges", "-0.1")


def test_hydro_metrics_use_station_coefficient_for_each_year():

    maps = _hydro_metric_maps(
        Decimal("0.025"),
        {2024: Decimal("800"), 2025: Decimal("1000")},
        [2024, 2025],
        digits=1,
    )

    assert maps["own_needs"][2024] == Decimal("20.000")
    assert maps["own_needs_display"] == {2024: "20,0", 2025: "25,0"}
    assert maps["delivery_display"] == {2024: "780,0", 2025: "975,0"}
    assert maps["own_needs_coefficient_display"] == "0,025"


def test_hydro_totals_sum_station_coefficient_results():
    years = [2025]
    total = _blank_total(years)
    for coefficient, generation in (
        (Decimal("0.01"), Decimal("1000")),
        (Decimal("0.02"), Decimal("2000")),
    ):
        metrics = _hydro_metric_maps(coefficient, {2025: generation}, years, digits=1)
        _accumulate_station(
            total,
            {
                "capacity": {2025: None},
                "energy": {2025: generation},
                "owner": {},
                "min_value": None,
                **metrics,
            },
        )

    row = _finalize_total(total, years, 1, "ОЭС — всего", "ues_total")

    assert row["own_needs_display"] == {2025: "50,0"}
    assert row["delivery_display"] == {2025: "2 950,0"}


def test_gaes_charge_values_are_summed_for_totals():
    years = [2025]
    total = _blank_total(years)
    for charge in (Decimal("12.5"), Decimal("7.25")):
        _accumulate_station(
            total,
            {
                "capacity": {2025: None},
                "energy": {2025: None},
                "owner": {},
                "gaes_charge": {2025: charge},
                "gaes_charge_enabled": True,
                "min_value": None,
            },
        )

    row = _finalize_total(total, years, 2, "ГАЭС России", "russia_total")

    assert row["gaes_charge_enabled"] is True
    assert row["gaes_charge_display"] == {2025: "19,75"}


def test_hydro_metrics_are_blank_without_a_coefficient():
    maps = _hydro_metric_maps(None, {2025: Decimal("1000")}, [2025], digits=1)

    assert maps["own_needs_display"] == {2025: ""}
    assert maps["delivery_display"] == {2025: ""}
    assert maps["own_needs_coefficient_display"] == ""


def test_aes_metrics_are_empty_when_inputs_are_missing_or_generation_is_zero():
    assert _aes_own_needs_percent(None, Decimal("10")) is None
    assert _aes_delivery_energy(Decimal("1"), Decimal("0")) is None
    assert _aes_metric_maps(
        {2025: Decimal("5")}, {2025: Decimal("0")}, [2025], digits=1
    ) == {
        "own_needs_display": {2025: ""},
        "own_needs_raw": {2025: ""},
        "delivery_display": {2025: ""},
        "delivery_raw": {2025: ""},
    }
