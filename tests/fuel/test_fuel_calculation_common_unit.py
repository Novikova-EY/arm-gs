# -*- coding: utf-8 -*-
from urllib.parse import parse_qs

from app.fuel.routes.fuel_calculation_common import (
    fuel_calculation_tep_edit_query_string,
)


def test_tep_edit_qs_start_is_base_end_is_calc():
    qs = fuel_calculation_tep_edit_query_string(
        base_year=2024,
        calc_year=2026,
        args={
            "union_energy_system_filter": "113",
            "start_year": "2026",
            "base_year": "",
            "tes_type_filter": "",
        },
    )
    parsed = parse_qs(qs)
    assert parsed["start_year"] == ["2024"]
    assert parsed["end_year"] == ["2026"]
    assert parsed["base_year"] == ["2024"]
    assert parsed["union_energy_system_filter"] == ["113"]
    assert "tes_type_filter" not in parsed


def test_tep_edit_qs_without_base_uses_calc_for_both():
    qs = fuel_calculation_tep_edit_query_string(
        base_year=None,
        calc_year=2026,
        args={"union_energy_system_filter": "113"},
    )
    parsed = parse_qs(qs)
    assert parsed["start_year"] == ["2026"]
    assert parsed["end_year"] == ["2026"]
    assert "base_year" not in parsed
