# -*- coding: utf-8 -*-
"""CRUD пользовательских строк «Получение/Передача мощности»."""
from __future__ import annotations

from typing import Any

from app.energy_balance.models.power_balance_custom_flow_model import (
    CUSTOM_FLOW_DIRECTIONS,
    PowerBalanceCustomFlowRow,
    PowerBalanceCustomFlowValue,
)
from app.energy_balance.services import balance_custom_flow_services as _shared
from app.energy_balance.services.balance_custom_flow_services import CustomFlowConfig

__all__ = [
    "CUSTOM_FLOW_DIRECTIONS",
    "add_custom_flow_row",
    "custom_flow_row_key",
    "delete_custom_flow_row",
    "load_power_balance_custom_flows",
    "parse_custom_flow_row_id",
    "update_custom_flow_label",
    "update_custom_flow_value",
]

_CONFIG = CustomFlowConfig(
    row_model=PowerBalanceCustomFlowRow,
    value_model=PowerBalanceCustomFlowValue,
    value_field="value_mw",
    directions=CUSTOM_FLOW_DIRECTIONS,
    action="Изменения в балансе мощности, строки перетока",
)

custom_flow_row_key = _shared.custom_flow_row_key


def parse_custom_flow_row_id(row_key: str) -> int | None:
    return _shared.parse_custom_flow_row_id(row_key, CUSTOM_FLOW_DIRECTIONS)


def load_power_balance_custom_flows(sheets=None) -> dict[str, list[dict[str, Any]]]:
    """{sheet_slug: [{id, direction, label, sort_order, values, key}, ...]}."""
    return _shared.load_custom_flows(_CONFIG, sheets)


def add_custom_flow_row(
    slug: str,
    direction: str,
    label: str = "",
    parent_key: str | None = None,
    user: Any = None,
) -> dict[str, Any]:
    return _shared.add_custom_flow_row(
        _CONFIG, slug, direction, label, parent_key, user=user
    )


def delete_custom_flow_row(slug: str, row_id: int, user: Any = None) -> bool:
    return _shared.delete_custom_flow_row(_CONFIG, slug, row_id, user=user)


def update_custom_flow_label(
    slug: str, row_id: int, label: str, user: Any = None
) -> dict[str, Any] | None:
    return _shared.update_custom_flow_label(_CONFIG, slug, row_id, label, user=user)


def update_custom_flow_value(
    slug: str,
    row_id: int,
    year: int,
    raw_value: Any,
    user: Any = None,
) -> dict[str, Any]:
    return _shared.update_custom_flow_value(
        _CONFIG, slug, row_id, year, raw_value, user=user
    )
