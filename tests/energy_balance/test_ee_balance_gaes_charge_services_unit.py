# -*- coding: utf-8 -*-
"""Юнит-тесты заряда ГАЭС для балансов электрической энергии."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from app.energy_balance.services.ee_balance_gaes_charge_services import (
    GAES_CHARGE_ROW_KEY,
    load_ee_balance_gaes_charge_inputs,
    year_values_from_gaes_charge_station_rows,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)


def test_year_values_sum_stations_and_skip_empty():
    rows = (
        (1, "ГАЭС-1", ((2026, Decimal("10.5")), (2027, None), (2028, Decimal("2")))),
        (2, "ГАЭС-2", ((2026, Decimal("1.5")), (2030, Decimal("8")))),
        (3, "ГАЭС-3", ()),
    )
    assert year_values_from_gaes_charge_station_rows(rows, [2026, 2027, 2028]) == {
        2026: Decimal("12.0"),
        2027: Decimal("0"),
        2028: Decimal("2"),
    }


def test_year_values_empty_when_no_station_values():
    assert year_values_from_gaes_charge_station_rows((), [2026]) == {}
    assert year_values_from_gaes_charge_station_rows(
        ((1, "ГАЭС", ()),),
        [2026],
    ) == {}


def test_load_ues_gaes_charge_from_summary_stations():
    sheets = [
        {
            "slug": "centr",
            "layout": "oes_standard",
            "group": "oes",
            "sheet_name": "Центр",
            "territory": {"kind": "ues", "id": 10, "name": "ОЭС Центра"},
        }
    ]
    captured = {}

    def fake_raw(version_id, model_name, fk, parent_id, years):
        captured["model_name"] = model_name
        captured["fk"] = fk
        captured["parent_id"] = parent_id
        captured["years"] = years
        return ((7, "Загорская ГАЭС", ((2026, Decimal("4.2")),)),)

    with patch(
        "app.energy_balance.services.ee_balance_gaes_charge_services.resolve_demand_max_territory",
        return_value={"kind": "ues", "id": 10, "name": "ОЭС Центра"},
    ), patch(
        "app.energy_balance.services.ee_balance_gaes_charge_services.get_current_version",
        return_value=46,
    ), patch(
        "app.energy_consumption.services.energy_consumption_summary_services._gaes_charge_raw_station_values_for_entity",
        fake_raw,
    ):
        inputs = load_ee_balance_gaes_charge_inputs([2026], sheets=sheets)

    assert captured["model_name"] == UnionEnergySystemEnergyConsumptionParameter.__name__
    assert captured["fk"] == "id_union_energy_system"
    assert captured["parent_id"] == 10
    assert captured["years"] == (2026,)
    assert inputs["centr"][GAES_CHARGE_ROW_KEY][2026] == Decimal("4.2")
