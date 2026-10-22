# -*- coding: utf-8 -*-
"""Общие helpers для текстового поиска в модуле экологии."""

from __future__ import annotations

from typing import Any


def text_contains(
    needle: str,
    haystack: Any,
    *,
    treat_em_dash_as_empty: bool = False,
    reject_empty_needle: bool = False,
    blank_as_empty: bool = False,
) -> bool:
    """Подстрока needle в haystack без учёта регистра (casefold)."""
    if blank_as_empty:
        if haystack is None:
            text = ""
        elif isinstance(haystack, str) and not haystack.strip():
            text = ""
        else:
            text = str(haystack).strip()
    else:
        text = str(haystack or "").strip()

    if reject_empty_needle and not needle:
        return False
    if not text or (treat_em_dash_as_empty and text == "–"):
        return False
    return needle.casefold() in text.casefold()
