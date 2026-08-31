# -*- coding: utf-8 -*-
"""Юнит-тесты потребления ЭЭ для балансов электрической энергии."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
from app.energy_balance.services.ee_balance_consumption_services import (
    load_ee_balance_consumption_inputs,
    year_values_from_consumption_rows,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)


def _row(*, year, value):
    return SimpleNamespace(
        year_number=year,
        energy_consumption_mln_kvt_ch=value,
    )


def test_year_values_skip_empty_and_out_of_range():
    rows = [
        _row(year=None, value=Decimal("9")),
        _row(year=2026, value=Decimal("100.5")),
        _row(year=2027, value=None),
        _row(year=2028, value=Decimal("2")),
        _row(year=2030, value=Decimal("8")),
    ]
    assert year_values_from_consumption_rows(rows, [2026, 2027, 2028]) == {
        2026: Decimal("100.5"),
        2028: Decimal("2"),
    }


def test_load_ues_without_nt_consumption():
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

    def fake_rows(model, fk, parent_id, perimeter_variant_code=None):
        captured["model"] = model
        captured["fk"] = fk
        captured["parent_id"] = parent_id
        captured.setdefault("codes", []).append(perimeter_variant_code)
        return [_row(year=2026, value=Decimal("77"))]

    with patch(
        "app.energy_balance.services.ee_balance_consumption_services.resolve_demand_max_territory",
        return_value={"kind": "ues", "id": 10, "name": "ОЭС Центра"},
    ), patch(
        "app.energy_balance.services.ee_balance_consumption_services.get_demand_rows",
        fake_rows,
    ):
        inputs = load_ee_balance_consumption_inputs([2026], sheets=sheets)

    assert captured["model"] is UnionEnergySystemEnergyConsumptionParameter
    assert captured["fk"] == "id_union_energy_system"
    assert captured["parent_id"] == 10
    assert CODE_WITHOUT_NT in captured["codes"]
    assert inputs["centr"]["consumption"][2026] == Decimal("77")


def test_load_energy_unit_consumption_for_tites_sheet():
    sheets = [
        {
            "slug": "eu-104",
            "layout": "oes_standard",
            "group": "eu",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "territory": {
                "kind": "eu",
                "id": 104,
                "name": "Чаун-Билибинский энергорайон",
            },
        }
    ]
    captured = {}

    def fake_rows(model, fk, parent_id, perimeter_variant_code=None):
        captured["model"] = model
        captured["fk"] = fk
        captured["parent_id"] = parent_id
        captured.setdefault("codes", []).append(perimeter_variant_code)
        if perimeter_variant_code is None:
            return [_row(year=2026, value=Decimal("41"))]
        if perimeter_variant_code in {"o1", "o1_without_nt"}:
            return [_row(year=2026, value=Decimal("999"))]
        return []

    with patch(
        "app.energy_balance.services.ee_balance_consumption_services.resolve_demand_max_territory",
        return_value={
            "kind": "eu",
            "id": 104,
            "name": "Чаун-Билибинский энергорайон",
        },
    ), patch(
        "app.energy_balance.services.ee_balance_consumption_services.get_demand_rows",
        fake_rows,
    ):
        inputs = load_ee_balance_consumption_inputs([2026], sheets=sheets)

    assert captured["model"] is EnergyUnitEnergyConsumptionParameter
    assert captured["fk"] == "id_energy_unit"
    assert captured["parent_id"] == 104
    assert None in captured["codes"]
    assert "o1" not in captured["codes"]
    assert "o1_without_nt" not in captured["codes"]
    assert inputs["eu-104"]["consumption"][2026] == Decimal("41")


def test_tites_eu_consumption_does_not_fall_back_to_o1():
    sheets = [
        {
            "slug": "eu-104",
            "layout": "oes_standard",
            "group": "eu",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "territory": {
                "kind": "eu",
                "id": 104,
                "name": "Чаун-Билибинский энергорайон",
            },
        }
    ]

    def fake_rows(model, fk, parent_id, perimeter_variant_code=None):
        code = str(perimeter_variant_code or "")
        if "o1" in code.replace("о", "o"):
            return [_row(year=2026, value=Decimal("999"))]
        return []

    with patch(
        "app.energy_balance.services.ee_balance_consumption_services.resolve_demand_max_territory",
        return_value={
            "kind": "eu",
            "id": 104,
            "name": "Чаун-Билибинский энергорайон",
        },
    ), patch(
        "app.energy_balance.services.ee_balance_consumption_services.get_demand_rows",
        fake_rows,
    ):
        inputs = load_ee_balance_consumption_inputs([2026], sheets=sheets)

    assert "eu-104" not in inputs
