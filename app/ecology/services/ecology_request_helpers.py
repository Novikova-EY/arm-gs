# -*- coding: utf-8 -*-
"""Общие helpers для разбора query/request-аргументов в модуле экологии."""

from __future__ import annotations

from typing import Any

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def arg_values(args: Any, key: str) -> list[Any]:
    """Значения аргумента: поддержка getlist (Flask/Werkzeug MultiDict)."""
    if args is None:
        return []
    getlist = getattr(args, "getlist", None)
    if callable(getlist):
        values = getlist(key)
    else:
        value = args.get(key) if hasattr(args, "get") else None
        if isinstance(value, (list, tuple)):
            values = list(value)
        elif value in (None, ""):
            values = []
        else:
            values = [value]
    return [item for item in values if item not in (None, "")]


def parse_truthy_arg(
    args: Any,
    key: str,
    *,
    casefold: bool = False,
    use_getlist: bool = False,
) -> bool:
    """True, если аргумент key — truthy-строка (1/true/yes/on)."""
    if use_getlist:
        values = arg_values(args, key)
        if not values:
            return False
        raw = str(values[0]).strip()
    else:
        raw_val = args.get(key) if args is not None and hasattr(args, "get") else None
        if raw_val is None:
            return False
        raw = str(raw_val).strip()
    if casefold:
        raw = raw.lower()
    return raw in _TRUTHY
