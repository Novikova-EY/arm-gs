# -*- coding: utf-8 -*-
"""Юнит-тесты столбца «Примечание» листов баланса."""

from __future__ import annotations

import pytest

from app.energy_balance.services.balance_sheet_note_services import (
    BALANCE_KIND_EE,
    BALANCE_KIND_POWER,
    NOTE_MAX_LENGTH,
    attach_balance_sheet_notes,
    update_balance_sheet_note,
)


def test_update_note_rejects_empty_slug():
    with pytest.raises(ValueError, match="лист"):
        update_balance_sheet_note(BALANCE_KIND_POWER, "", "demand_max", "текст")


def test_update_note_rejects_empty_row_key():
    with pytest.raises(ValueError, match="строка"):
        update_balance_sheet_note(BALANCE_KIND_POWER, "centr", "", "текст")


def test_update_note_rejects_unknown_kind():
    with pytest.raises(ValueError, match="тип баланса"):
        update_balance_sheet_note("other", "centr", "demand_max", "текст")


def test_attach_notes_fills_matching_row_keys(monkeypatch):
    tables = {
        "centr": {
            "rows": [
                {"key": "demand_max"},
                {"key": "export"},
                {
                    "key": "sibir__custom_flow_1",
                    "custom_origin_slug": "sibir",
                    "custom_origin_key": "custom_flow_1",
                },
            ]
        },
        "sibir": {"rows": [{"key": "custom_flow_1"}]},
    }
    monkeypatch.setattr(
        "app.energy_balance.services.balance_sheet_note_services.load_balance_sheet_notes",
        lambda kind, slugs=None: {
            "centr": {"demand_max": "Комментарий"},
            "sibir": {"custom_flow_1": "Переток"},
        },
    )
    attach_balance_sheet_notes(tables, BALANCE_KIND_EE)
    by_key = {row["key"]: row["note"] for row in tables["centr"]["rows"]}
    assert by_key["demand_max"] == "Комментарий"
    assert by_key["export"] == ""
    assert by_key["sibir__custom_flow_1"] == "Переток"
    assert tables["sibir"]["rows"][0]["note"] == "Переток"


def test_note_max_length_constant():
    assert NOTE_MAX_LENGTH == 4000
    assert BALANCE_KIND_POWER == "power"
    assert BALANCE_KIND_EE == "ee"
