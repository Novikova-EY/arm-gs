# -*- coding: utf-8 -*-
from app.generation.services.station_services.null_district_duplicate_cleanup_services import (
    DuplicateStation,
)


def _dup(**overrides) -> DuplicateStation:
    data = dict(
        id=29366,
        name="ГПЭС Вынгапуровского ГПЗ",
        external_code="29c63291-67b2-57e9-b0f6-d80a3d4c4c60",
        database_version_id=37,
        version_number="СиПР 2026-2031 (РАБОЧАЯ)",
        kto="777301",
        machines=0,
        boilers=0,
        generations=7,
        gaes=0,
        eg_links=0,
        eg_sets=0,
        keeper_ids=[29726],
        keeper_codes=["4de433b3-e98d-5804-9f2f-7b32293c3a16"],
        keeper_rd_names=["Ямало-Ненецкий АО"],
    )
    data.update(overrides)
    return DuplicateStation(**data)


def test_empty_ghost_is_deletable():
    item = _dup(generations=0)
    assert item.blocked_reason is None
    assert item.keeper_id == 29726


def test_ghost_with_generation_only_is_deletable():
    item = _dup()
    assert item.blocked_reason is None


def test_ghost_with_machines_is_blocked():
    item = _dup(machines=5)
    assert item.blocked_reason == "есть агрегаты"
    assert item.keeper_id == 29726


def test_ghost_with_boilers_is_blocked():
    item = _dup(boilers=1)
    assert item.blocked_reason == "есть котлы"


def test_ambiguous_keepers_with_children_are_blocked():
    item = _dup(
        keeper_ids=[29726, 29300],
        keeper_codes=["a", "b"],
        keeper_rd_names=["ЯНАО", "ХМАО"],
    )
    assert item.blocked_reason == "несколько одноимённых станций с субъектом в той же версии"
    assert item.keeper_id is None


def test_ambiguous_keepers_without_children_are_deletable():
    item = _dup(
        generations=0,
        keeper_ids=[80, 1210],
        keeper_codes=["a", "b"],
        keeper_rd_names=["г. Санкт-Петербург", "Кемеровская область – Кузбасс"],
    )
    assert item.blocked_reason is None
    assert item.keeper_id is None
