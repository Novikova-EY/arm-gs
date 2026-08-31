# -*- coding: utf-8 -*-
"""Юнит-тесты ручного ввода выработки СНЭЭ / СЭС / ВЭС в плановых годах."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.energy_balance.services.ee_balance_manual_generation_services import (
    MANUAL_PLAN_GENERATION_KEYS,
    is_manual_plan_generation_row_key,
    mark_manual_plan_generation_rows,
    overlay_manual_generation_inputs,
    update_ee_balance_manual_generation_value,
)


def test_manual_plan_generation_keys_cover_snee_ses_ves():
    assert "generation_snee" in MANUAL_PLAN_GENERATION_KEYS
    assert "generation_ses_ves" in MANUAL_PLAN_GENERATION_KEYS
    assert is_manual_plan_generation_row_key("generation_snee")
    assert is_manual_plan_generation_row_key("generation_ses_ves")
    assert is_manual_plan_generation_row_key("generation_ses")
    assert is_manual_plan_generation_row_key("generation_ves")
    assert is_manual_plan_generation_row_key("other", "СНЭЭ")
    assert is_manual_plan_generation_row_key("other", "СЭС, ВЭС")
    assert not is_manual_plan_generation_row_key("generation_ges")
    assert not is_manual_plan_generation_row_key("generation_tes")


def test_overlay_manual_generation_keeps_other_years_and_rows():
    auto = {
        "centr": {
            "generation_snee": {2024: Decimal("3"), 2026: Decimal("4")},
            "generation_aes": {2026: Decimal("40")},
        }
    }
    manual = {
        "centr": {
            "generation_snee": {2026: Decimal("11")},
            "generation_ses_ves": {2026: Decimal("8")},
        }
    }
    merged = overlay_manual_generation_inputs(auto, manual)
    assert merged["centr"]["generation_snee"][2024] == Decimal("3")
    assert merged["centr"]["generation_snee"][2026] == Decimal("11")
    assert merged["centr"]["generation_ses_ves"][2026] == Decimal("8")
    assert merged["centr"]["generation_aes"][2026] == Decimal("40")


def test_update_manual_generation_rejects_empty_slug():
    with pytest.raises(ValueError, match="лист"):
        update_ee_balance_manual_generation_value("", "generation_snee", 2026, "1")


def test_update_manual_generation_rejects_other_row():
    with pytest.raises(ValueError, match="СНЭЭ"):
        update_ee_balance_manual_generation_value("centr", "generation_tes", 2026, "1")


def test_update_manual_generation_rejects_non_plan_year():
    with patch(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        return_value=([2024], [2026]),
    ):
        with pytest.raises(ValueError, match="планов"):
            update_ee_balance_manual_generation_value(
                "centr", "generation_snee", 2024, "1"
            )


def test_update_manual_generation_rejects_bad_number():
    with patch(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        return_value=([], [2026]),
    ):
        with pytest.raises(ValueError, match="число"):
            update_ee_balance_manual_generation_value(
                "centr", "generation_ses_ves", 2026, "abc"
            )


def test_mark_manual_plan_generation_rows_only_plan_years_on_leaf_sheets():
    tables = {
        "centr": {
            "sheet": {"layout": "oes_standard"},
            "rows": [
                {"key": "generation_snee", "label": "СНЭЭ", "formula": None},
                {"key": "generation_ses_ves", "label": "СЭС, ВЭС", "formula": None},
                {"key": "generation_tes", "label": "ТЭС", "formula": None},
            ],
        },
        "ees-rossii": {
            "sheet": {"layout": "ees_rossii"},
            "rows": [
                {
                    "key": "generation_snee",
                    "label": "СНЭЭ",
                    "formula": {"terms": [{"slug": "centr", "row_key": "generation_snee"}]},
                }
            ],
        },
    }
    with patch(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        return_value=([2024], [2026, 2027]),
    ):
        mark_manual_plan_generation_rows(tables, [2024, 2026, 2027])

    snee = tables["centr"]["rows"][0]
    ses = tables["centr"]["rows"][1]
    tes = tables["centr"]["rows"][2]
    ees = tables["ees-rossii"]["rows"][0]
    assert snee["editable_values"] is True
    assert snee["editable_years"] == [2026, 2027]
    assert snee["value_save_kind"] == "generation"
    assert ses["editable_values"] is True
    assert ses["editable_years"] == [2026, 2027]
    assert tes.get("editable_values") is not True
    assert ees.get("editable_values") is not True
