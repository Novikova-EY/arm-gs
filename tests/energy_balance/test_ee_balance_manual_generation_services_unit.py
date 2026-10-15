# -*- coding: utf-8 -*-
"""Юнит-тесты ручного ввода выработки СНЭЭ / СЭС / ВЭС в плановых годах."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.energy_balance.services import ee_balance_manual_generation_services as manual_services
from app.energy_balance.services.ee_balance_manual_generation_services import (
    MANUAL_PLAN_GENERATION_KEYS,
    URAL_WITHOUT_TYUMEN_SLUG,
    _is_manual_plan_generation_row_for_sheet,
    is_manual_plan_generation_row_key,
    mark_manual_plan_generation_rows,
    overlay_manual_generation_inputs,
    update_ee_balance_manual_generation_value,
)


def test_manual_plan_generation_keys_cover_snee_not_ses_ves():
    assert "generation_snee" in MANUAL_PLAN_GENERATION_KEYS
    assert "generation_ses_ves" not in MANUAL_PLAN_GENERATION_KEYS
    assert is_manual_plan_generation_row_key("generation_snee")
    assert not is_manual_plan_generation_row_key("generation_ses_ves")
    assert not is_manual_plan_generation_row_key("generation_ses")
    assert not is_manual_plan_generation_row_key("generation_ves")
    assert is_manual_plan_generation_row_key("other", "СНЭЭ")
    assert not is_manual_plan_generation_row_key("other", "СЭС, ВЭС")
    assert not is_manual_plan_generation_row_key("generation_ges")
    assert not is_manual_plan_generation_row_key("generation_tes")
    assert not is_manual_plan_generation_row_key("installed_ses", "СЭС")
    assert not is_manual_plan_generation_row_key("installed_ves", "ВЭС")
    assert not is_manual_plan_generation_row_key("chiim_ses", "СЭС")


def test_overlay_manual_generation_keeps_other_years_and_rows():
    auto = {
        "centr": {
            "generation_snee": {2024: Decimal("3"), 2026: Decimal("4")},
            "generation_aes": {2026: Decimal("40")},
            "generation_tes": {2026: Decimal("80")},
            "generation_ses": {2026: Decimal("267.6")},
        }
    }
    manual = {
        "centr": {
            "generation_snee": {2026: Decimal("11")},
            "generation_ses_ves": {2026: Decimal("8")},
            "generation_tes": {2026: Decimal("90")},
        },
        "sibir": {"generation_tes": {2026: Decimal("70")}},
    }
    merged = overlay_manual_generation_inputs(
        auto, manual,
        sheets=[{"slug": "centr", "group": "oes"}, {"slug": "sibir", "group": "oes"}],
        plan_years=[2026],
    )
    assert merged["centr"]["generation_snee"][2024] == Decimal("3")
    assert merged["centr"]["generation_snee"][2026] == Decimal("11")
    assert "generation_ses_ves" not in merged["centr"] or 2026 not in (
        merged["centr"].get("generation_ses_ves") or {}
    )
    assert merged["centr"]["generation_aes"][2026] == Decimal("40")
    assert merged["centr"]["generation_ses"][2026] == Decimal("267.6")
    assert merged["centr"]["generation_tes"][2026] == Decimal("90")
    assert merged["sibir"]["generation_tes"][2026] == Decimal("70")


def test_manual_plan_generation_accepts_tyumen_res_and_ural_without_slug(monkeypatch):
    tyumen_sheet = {
        "slug": "res-2827",
        "group": "res",
        "sheet_name": "ЭС Тюменской области, Ханты-Мансийского и Ямало-Ненецкого автономных округов",
        "parent_slug": "oes-413",
    }
    ural_sheet = {"slug": "oes-413", "group": "oes", "sheet_name": "ОЭС Урала"}
    monkeypatch.setattr(
        manual_services,
        "get_power_balance_sheet",
        lambda slug: ural_sheet if slug == "oes-413" else tyumen_sheet,
    )

    assert _is_manual_plan_generation_row_for_sheet("res-2827", "generation_ges")
    assert _is_manual_plan_generation_row_for_sheet(
        URAL_WITHOUT_TYUMEN_SLUG, "generation_gaes"
    )


def test_update_manual_generation_rejects_empty_slug():
    with pytest.raises(ValueError, match="лист"):
        update_ee_balance_manual_generation_value("", "generation_snee", 2026, "1")


def test_update_manual_generation_rejects_other_row():
    with pytest.raises(ValueError, match="СНЭЭ"):
        update_ee_balance_manual_generation_value("centr", "generation_aes", 2026, "1")


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
                "centr", "generation_snee", 2026, "abc"
            )


def test_mark_manual_plan_generation_rows_only_plan_years_on_leaf_sheets():
    tables = {
        "centr": {
            "sheet": {"slug": "centr", "group": "oes", "layout": "oes_standard"},
            "rows": [
                {"key": "generation_snee", "label": "СНЭЭ", "formula": None},
                {"key": "generation_ses_ves", "label": "СЭС, ВЭС", "formula": None},
                {"key": "generation_tes", "label": "ТЭС", "formula": None},
            ],
        },
        "sibir": {
            "sheet": {"slug": "sibir", "group": "oes", "layout": "oes_sibir"},
            "rows": [
                {"key": "generation_tes", "label": "ТЭС", "formula": None},
                {
                    "key": "generation_tes",
                    "label": "ТЭС с формулой",
                    "formula": {"terms": []},
                },
            ],
        },
        "ees-rossii": {
            "sheet": {"slug": "ees-rossii", "layout": "ees_rossii"},
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
    sibir_tes, sibir_tes_formula = tables["sibir"]["rows"]
    assert snee["editable_values"] is True
    assert snee["editable_years"] == [2026, 2027]
    assert snee["value_save_kind"] == "generation"
    assert ses.get("editable_values") is not True
    assert tes["editable_values"] is True
    assert tes["editable_years"] == [2026, 2027]
    assert sibir_tes["editable_values"] is True
    assert sibir_tes["editable_years"] == [2026, 2027]
    assert sibir_tes["value_save_kind"] == "generation"
    assert sibir_tes_formula.get("editable_values") is not True
    assert ees.get("editable_values") is not True


@pytest.mark.parametrize("row_key", ["generation_tes", "generation_ges", "generation_gaes"])
@pytest.mark.parametrize("sheet", [
    {"slug": "centr", "group": "oes"},
    {"slug": "sibir", "group": "oes"},
    {"slug": "oes-999", "group": "oes"},
    {"slug": "2-sz-ees-vostok", "group": "sz", "layout": "oes_vostok"},
])
def test_oes_manual_generation_has_no_plan_auto_fallback(sheet, row_key):
    slug = sheet["slug"]
    automatic = {slug: {row_key: {
        2024: Decimal("10"), 2026: Decimal("99"), 2027: Decimal("100"),
    }}}
    manual = {slug: {row_key: {2024: Decimal("88"), 2026: Decimal("0")}}}
    merged = overlay_manual_generation_inputs(
        automatic, manual, sheets=[sheet], plan_years=[2026, 2027]
    )
    assert merged[slug][row_key] == {2024: Decimal("10"), 2026: Decimal("0")}
    merged[slug][row_key][2026] = Decimal("99")
    cleared = overlay_manual_generation_inputs(
        merged, {}, sheets=[sheet], plan_years=[2026, 2027]
    )
    assert cleared[slug][row_key] == {2024: Decimal("10")}


@pytest.mark.parametrize("row_key", ["generation_tes", "generation_ges", "generation_gaes"])
@pytest.mark.parametrize("sheet", [
    {"slug": "ees-rossii", "group": "ees", "layout": "ees_rossii"},
    {"slug": "1-sz-ees", "group": "sz", "layout": "sz1"},
    {"slug": "eu-255", "group": "eu", "layout": "oes_standard"},
])
def test_non_oes_generation_stays_automatic(sheet, row_key):
    slug = sheet["slug"]
    automatic = {slug: {row_key: {2026: Decimal("99")}}}
    merged = overlay_manual_generation_inputs(
        automatic, {slug: {row_key: {2026: Decimal("0")}}},
        sheets=[sheet], plan_years=[2026],
    )
    assert merged[slug][row_key][2026] == Decimal("99")
    tables = {slug: {"sheet": sheet, "rows": [{"key": row_key}]}}
    with patch(
        "app.energy_balance.services.ee_balance_manual_generation_services.classify_ee_balance_generation_years",
        return_value=([], [2026]),
    ):
        mark_manual_plan_generation_rows(tables, [2026])
    assert not tables[slug]["rows"][0].get("editable_values")


@pytest.mark.parametrize("row_key", ["generation_tes", "generation_ges", "generation_gaes"])
@pytest.mark.parametrize("sheet", [
    {"slug": "centr", "group": "oes"},
    {"slug": "sibir", "group": "oes"},
    {"slug": "oes-999", "group": "oes"},
    {"slug": "2-sz-ees-vostok", "group": "sz", "layout": "oes_vostok"},
    {"slug": URAL_WITHOUT_TYUMEN_SLUG, "group": "oes"},
    {
        "slug": "res-2827",
        "group": "res",
        "sheet_name": "ЭС Тюменской области, Ханты-Мансийского и Ямало-Ненецкого автономных округов",
        "parent_slug": "oes-413",
    },
])
def test_save_and_load_oes_manual_generation(monkeypatch, sheet, row_key):
    slug = sheet["slug"]
    stored = SimpleNamespace(
        sheet_slug=slug, row_key=row_key, year_number=2026,
        value_mln_kvtch=Decimal("55"), database_version_id=7,
    )
    records = [stored]
    query = MagicMock()
    query.filter.return_value.one_or_none.side_effect = lambda: records[0] if records else None
    query.all.side_effect = lambda: list(records)
    monkeypatch.setattr(manual_services, "db", SimpleNamespace(
        session=SimpleNamespace(delete=lambda record: records.remove(record)),
    ))
    monkeypatch.setattr(manual_services, "_value_query", lambda: query)
    monkeypatch.setattr(manual_services, "_ensure_tables", lambda: None)
    monkeypatch.setattr(manual_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(manual_services, "_version_id", lambda: 7)
    monkeypatch.setattr(
        manual_services,
        "get_power_balance_sheet",
        lambda wanted: (
            {"slug": "oes-413", "group": "oes", "sheet_name": "ОЭС Урала"}
            if wanted == "oes-413"
            else sheet
        ),
    )
    monkeypatch.setattr(
        manual_services, "classify_ee_balance_generation_years",
        lambda years: ([2024], [2026]),
    )
    saved = update_ee_balance_manual_generation_value(slug, row_key, 2026, "12,5")
    assert saved == {"year": 2026, "row_key": row_key, "value": Decimal("12.5")}
    assert stored.value_mln_kvtch == Decimal("12.5")
    assert stored.database_version_id == 7
    assert manual_services.load_ee_balance_manual_generation_inputs(
        [2026], sheets=[sheet]
    ) == {slug: {row_key: {2026: Decimal("12.5")}}}
    saved = update_ee_balance_manual_generation_value(slug, row_key, 2026, "0")
    assert saved["value"] == Decimal("0")
    assert stored.value_mln_kvtch == Decimal("0")
    with pytest.raises(ValueError, match="планов"):
        update_ee_balance_manual_generation_value(slug, row_key, 2024, "1")
    cleared = update_ee_balance_manual_generation_value(slug, row_key, 2026, "")
    assert cleared == {"year": 2026, "row_key": row_key, "value": None}
    assert manual_services.load_ee_balance_manual_generation_inputs([2026], sheets=[sheet]) == {}


@pytest.mark.parametrize("row_key", ["generation_tes", "generation_ges", "generation_gaes"])
@pytest.mark.parametrize("sheet", [
    {"slug": "ees-rossii", "group": "ees", "layout": "ees_rossii"},
    {"slug": "1-sz-ees", "group": "sz", "layout": "sz1"},
    {"slug": "eu-255", "group": "eu", "layout": "oes_standard"},
])
def test_save_generation_rejects_non_oes_sheets(monkeypatch, sheet, row_key):
    monkeypatch.setattr(manual_services, "get_power_balance_sheet", lambda slug: sheet)
    with pytest.raises(ValueError, match="ОЭС"):
        update_ee_balance_manual_generation_value(sheet["slug"], row_key, 2026, "1")
