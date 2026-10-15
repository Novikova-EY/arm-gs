# -*- coding: utf-8 -*-
"""Общие ключи порядка отображения для страниц модуля «Балансы электрической энергии и мощности»."""

from __future__ import annotations

def display_order_sort_key(
    display_order: int | None,
    name: str | None,
    tie_breaker: int,
) -> tuple:
    """Ключ сортировки: display_order, наименование без учёта регистра, id."""
    return (
        1 if display_order is None else 0,
        display_order if display_order is not None else 10**9,
        (name or "").strip().casefold(),
        tie_breaker,
    )
