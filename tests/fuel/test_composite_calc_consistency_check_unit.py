# -*- coding: utf-8 -*-
"""Unit-tests: защита от энергии составной станции на «не том» уровне."""
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.composite_calc_consistency_check_services import (
    ENERGY_NONEMPTY_THRESHOLD,
    KIND_BOTH_LEVELS_ACTIVE,
    KIND_ENERGY_ON_INACTIVE_CHILD,
    classify_composite_cluster_energy_level,
    equipment_group_ids_for_composite_energy_level_issues,
    flash_text_for_composite_energy_level_issues,
    oes_code_from_groups,
)


def _parent(**kwargs):
    data = {"id": 1, "numb": 66, "main": None, "comp": 1, "name": "ТЭЦ-14 Первомайская"}
    data.update(kwargs)
    return SimpleNamespace(**data)


def _child(**kwargs):
    data = {"id": 2, "numb": 1083, "main": 66, "comp": None, "name": "Первомайская ПГУ"}
    data.update(kwargs)
    return SimpleNamespace(**data)


def _param(**kwargs):
    data = {"year_number": 2026, "ved": None, "e": None}
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_flags_parent_in_filter_empty_e_energy_on_ved0_child():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=None),
        children=[(_child(), _param(ved=0, e=Decimal("2021.15")))],
    )
    assert issue is not None
    assert issue["kind"] == KIND_ENERGY_ON_INACTIVE_CHILD
    assert issue["parent_numb"] == 66
    assert issue["child_e_sum"] == Decimal("2021.15")
    assert "ved=0" in issue["message"]
    assert issue["children"][0]["numb"] == 1083
    assert issue["children"][0]["main"] == 66


def test_no_flag_when_parent_has_energy_even_if_child_has_stale_e():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=Decimal("2004")),
        children=[(_child(), _param(ved=0, e=Decimal("2021")))],
    )
    assert issue is None


def test_no_flag_station_only_parent_with_e_inactive_empty_children():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=Decimal("2004")),
        children=[(_child(), _param(ved=0, e=None))],
    )
    assert issue is None


def test_no_flag_when_parent_ved0_not_participating():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=0, e=None),
        children=[(_child(), _param(ved=0, e=Decimal("2021")))],
    )
    assert issue is None


def test_flags_both_levels_active():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=Decimal("10")),
        children=[(_child(), _param(ved=2, e=Decimal("100")))],
    )
    assert issue is not None
    assert issue["kind"] == KIND_BOTH_LEVELS_ACTIVE
    assert "двойного" in issue["message"]


def test_both_levels_takes_priority_over_empty_parent():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=None),
        children=[(_child(), _param(ved=1, e=Decimal("100")))],
    )
    assert issue["kind"] == KIND_BOTH_LEVELS_ACTIVE


def test_threshold_ignores_tiny_child_energy():
    tiny = ENERGY_NONEMPTY_THRESHOLD
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=None),
        children=[(_child(), _param(ved=0, e=tiny))],
    )
    assert issue is None

    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=None),
        children=[(_child(), _param(ved=0, e=tiny + Decimal("0.01")))],
    )
    assert issue is not None
    assert issue["kind"] == KIND_ENERGY_ON_INACTIVE_CHILD


def test_skips_non_composite_parent():
    plain = SimpleNamespace(id=9, numb=77, main=None, comp=None, name="Обычная")
    issue = classify_composite_cluster_energy_level(
        parent_group=plain,
        parent_param=_param(ved=2, e=None),
        children=[(_child(), _param(ved=0, e=Decimal("10")))],
    )
    assert issue is None


def test_oes_code_from_groups_requires_single_oes():
    assert oes_code_from_groups([]) is None
    assert oes_code_from_groups([SimpleNamespace(oes=3), SimpleNamespace(oes=3)]) == 3
    assert oes_code_from_groups([SimpleNamespace(oes=None), SimpleNamespace(oes=3)]) == 3
    assert oes_code_from_groups([SimpleNamespace(oes=2), SimpleNamespace(oes=3)]) is None


def test_flash_and_ids_helpers():
    issue = classify_composite_cluster_energy_level(
        parent_group=_parent(),
        parent_param=_param(ved=2, e=None),
        children=[(_child(id=2), _param(ved=0, e=Decimal("10")))],
    )
    text = flash_text_for_composite_energy_level_issues([issue])
    assert text is not None
    assert "Первомайская" in text
    assert "66" in text
    ids = equipment_group_ids_for_composite_energy_level_issues([issue])
    assert ids == [1, 2]
    assert flash_text_for_composite_energy_level_issues([]) is None
