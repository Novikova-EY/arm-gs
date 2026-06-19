# -*- coding: utf-8 -*-
"""Юнит-тесты разбора Excel для импорта выпуска продукции."""

from __future__ import annotations

from app.economics.services import product_output_import_services as pois


def test_ved_lookup_resolves_name_2_label():
    ved_lookup = {
        pois._normalize_label("Добыча полезных ископаемых"): 10,
        pois._normalize_label(
            "Рудная и нерудная добыча; добыча полезных ископаемых"
        ): 10,
    }
    assert (
        pois._resolve_ved_id("Добыча полезных ископаемых", ved_lookup) == 10
    )


def test_ved_lookup_maps_fd_total_label_to_total_product_output():
    ved_lookup = {
        pois._normalize_label("Всего выпуск продукции"): 1,
    }
    ved_lookup[pois._normalize_label("Всего")] = 1
    assert pois._resolve_ved_id("Всего выпуск продукции", ved_lookup) == 1
    assert pois._resolve_ved_id("Всего", ved_lookup) == 1


def test_resolve_ved_prefix_match_for_long_official_name():
    ved_lookup = {
        pois._normalize_label(
            "Обеспечение электрической энергией, газом и паром"
        ): 5,
    }
    long_label = (
        "Обеспечение электрической энергией, газом и паром; "
        "Кондиционирование воздуха."
    )
    assert pois._resolve_ved_id(long_label, ved_lookup) == 5
