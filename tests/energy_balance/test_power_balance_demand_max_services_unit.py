# -*- coding: utf-8 -*-
"""Юнит-тесты максимума потребления для балансов мощности (сводка ОЭС без НТ)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
from app.energy_balance.services.power_balance_demand_max_services import (
    load_power_balance_demand_max_inputs,
    year_values_from_max_power_rows,
)
from app.energy_balance.services.power_balance_page_services import build_power_balance_tables
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)


def _row(*, year, value, hist=False):
    return SimpleNamespace(
        is_historical_maximum=hist,
        year_number=year,
        max_power_consumption_mw=value,
    )


def test_year_values_skip_hist_empty_and_out_of_range():
    rows = [
        _row(year=None, value=Decimal("9"), hist=True),
        _row(year=2026, value=Decimal("100.5")),
        _row(year=2027, value=None),
        _row(year=2028, value=Decimal("2")),
        _row(year=2030, value=Decimal("8")),
    ]
    assert year_values_from_max_power_rows(rows, [2026, 2027, 2028]) == {
        2026: Decimal("100.5"),
        2028: Decimal("2"),
    }


def test_load_ues_without_nt_max_power():
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

    def fake_block(model, fk, parent_id, display_perimeter_variant_code=None):
        captured["model"] = model
        captured["fk"] = fk
        captured["parent_id"] = parent_id
        captured["code"] = display_perimeter_variant_code
        return [_row(year=2026, value=Decimal("77"))]

    with patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows_for_summary_block",
        fake_block,
    ):
        inputs = load_power_balance_demand_max_inputs([2026], sheets=sheets)

    assert captured["model"] is UnionEnergySystemDemandParameter
    assert captured["fk"] == "id_union_energy_system"
    assert captured["parent_id"] == 10
    assert captured["code"] == CODE_WITHOUT_NT
    assert inputs["centr"]["demand_max"][2026] == Decimal("77")


def test_load_ees_without_nt_from_energy_system_type():
    sheets = [
        {
            "slug": "ees-rossii",
            "layout": "ees_rossii",
            "group": "ees",
            "sheet_name": "ЕЭС России",
            "territory": {"kind": "est", "id": 3, "name": "ЕЭС России"},
        }
    ]

    def fake_block(model, fk, parent_id, display_perimeter_variant_code=None):
        assert model is EnergySystemTypeDemandParameter
        assert fk == "id_energy_system_type"
        assert parent_id == 3
        assert display_perimeter_variant_code == CODE_WITHOUT_NT
        return [_row(year=2026, value=Decimal("500"))]

    with patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows_for_summary_block",
        fake_block,
    ):
        inputs = load_power_balance_demand_max_inputs([2026], sheets=sheets)
    assert inputs["ees-rossii"]["demand_max"][2026] == Decimal("500")


def test_kaliningrad_uses_stored_variant_not_without_nt_pair():
    sheets = [
        {
            "slug": "kaliningradskaya-sz-ees",
            "layout": "kaliningrad",
            "group": "sz",
            "sheet_name": "Калининградская СЗ ЕЭС",
            "territory": {
                "kind": "sa",
                "id": 8,
                "name": "Синхронная зона Калининградской области",
            },
        }
    ]
    captured = {}

    def fake_peek(model, fk, parent_id):
        assert model is SynchronousAreaDemandParameter
        return "stored_kal"

    def fake_rows(model, fk, parent_id, perimeter_variant_code=None):
        captured["code"] = perimeter_variant_code
        return [_row(year=2026, value=Decimal("12"))]

    with patch(
        "app.energy_balance.services.power_balance_demand_max_services.peek_stored_perimeter_variant_code_for_parent",
        fake_peek,
    ), patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows",
        fake_rows,
    ), patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows_for_summary_block",
        side_effect=AssertionError("Калининград не должен идти через блок без НТ"),
    ):
        inputs = load_power_balance_demand_max_inputs([2026], sheets=sheets)

    assert captured["code"] == "stored_kal"
    assert inputs["kaliningradskaya-sz-ees"]["demand_max"][2026] == Decimal("12")


def test_sz2_demand_resolves_tweaked_sa_name_without_territory():
    sheets = [
        {
            "slug": "2-sz-ees-vostok",
            "layout": "oes_vostok",
            "group": "sz",
            "sheet_name": "2-ая СЗ",
            "territory": {},
        }
    ]

    def fake_block(model, fk, parent_id, display_perimeter_variant_code=None):
        assert model is SynchronousAreaDemandParameter
        assert fk == "id_synchronous_area"
        assert parent_id == 22
        return [_row(year=2026, value=Decimal("9"))]

    with patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_synchronous_area_list_full",
        return_value=[
            SimpleNamespace(
                id=22,
                name="2-ая СЗ",
                name_full="Вторая синхронная зона",
                number="2",
            )
        ],
    ), patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows_for_summary_block",
        fake_block,
    ):
        inputs = load_power_balance_demand_max_inputs([2026], sheets=sheets)

    assert inputs["2-sz-ees-vostok"]["demand_max"][2026] == Decimal("9")


def test_load_energy_unit_max_power_for_tites_sheet():
    sheets = [
        {
            "slug": "eu-105",
            "layout": "oes_standard",
            "group": "eu",
            "sheet_name": "Анадырский энергорайон",
            "territory": {"kind": "eu", "id": 105, "name": "Анадырский энергорайон"},
        }
    ]
    captured = {}

    def fake_block(model, fk, parent_id, display_perimeter_variant_code=None):
        captured["model"] = model
        captured["fk"] = fk
        captured["parent_id"] = parent_id
        captured["code"] = display_perimeter_variant_code
        return [_row(year=2026, value=Decimal("18.5"))]

    with patch(
        "app.energy_balance.services.power_balance_demand_max_services.get_demand_rows_for_summary_block",
        fake_block,
    ):
        inputs = load_power_balance_demand_max_inputs([2026], sheets=sheets)

    assert captured["model"] is EnergyUnitDemandParameter
    assert captured["fk"] == "id_energy_unit"
    assert captured["parent_id"] == 105
    assert captured["code"] == CODE_WITHOUT_NT
    assert inputs["eu-105"]["demand_max"][2026] == Decimal("18.5")


def test_tables_fill_demand_max_from_loader():
    with patch(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_installed_capacity_inputs",
        return_value={},
    ), patch(
        "app.energy_balance.services.power_balance_page_services.load_power_balance_demand_max_inputs",
        return_value={"centr": {"demand_max": {2026: Decimal("10.456")}}},
    ):
        tables = build_power_balance_tables([2026], rounding_digits=1)
    row = next(item for item in tables["centr"]["rows"] if item["key"] == "demand_max")
    assert row["year_values"][2026] == "10,5"
    demand_total = next(item for item in tables["centr"]["rows"] if item["key"] == "demand_total")
    assert demand_total["year_values"][2026] == "10,5"
