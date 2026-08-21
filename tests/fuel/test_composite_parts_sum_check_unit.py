# -*- coding: utf-8 -*-
"""Unit-tests: контроль Σ частей vs родитель (Access Проверка-суммы-частей)."""
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.equipment_groups.composite_parts_sum_check_services import (
    COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD,
    build_composite_parts_sum_mismatch_for_station_block,
    compare_parent_to_children_sum,
)


def _param(**kwargs):
    data = {"id": kwargs.pop("id", 1), "year_number": kwargs.pop("year_number", 2024)}
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_compare_flags_when_abs_delta_gt_threshold():
    parent = _param(id=10, e=100, q=50, mazut=10)
    child1 = _param(id=11, e=40, q=20, mazut=3)
    child2 = _param(id=12, e=40, q=20, mazut=3)  # Σe=80, Σq=40, Σmazut=6
    mm = compare_parent_to_children_sum(parent, [child1, child2], attrs=("e", "q", "mazut"))
    assert set(mm) == {"e", "q", "mazut"}
    assert mm["e"]["parent"] == Decimal("100")
    assert mm["e"]["children_sum"] == Decimal("80")
    assert mm["e"]["delta"] == Decimal("20")
    assert "у родителя 100" in mm["e"]["message"]
    assert "сумма по группам 80" in mm["e"]["message"]


def test_compare_no_flag_within_threshold():
    parent = _param(e=Decimal("100.4"))
    child = _param(e=Decimal("100.0"))  # |Δ|=0.4 ≤ 0.5
    mm = compare_parent_to_children_sum(parent, [child], attrs=("e",))
    assert mm == {}


def test_compare_flags_at_just_over_threshold():
    parent = _param(e=Decimal("100.51"))
    child = _param(e=Decimal("100.0"))
    mm = compare_parent_to_children_sum(parent, [child], attrs=("e",))
    assert "e" in mm
    assert abs(mm["e"]["delta"]) > COMPOSITE_PARTS_SUM_MISMATCH_THRESHOLD


def test_compare_treats_null_as_zero():
    parent = _param(e=10, q=None)
    child = _param(e=None, q=5)
    mm = compare_parent_to_children_sum(parent, [child], attrs=("e", "q"))
    assert mm["e"]["delta"] == Decimal("10")
    assert mm["q"]["delta"] == Decimal("-5")


def test_compare_skips_synthetic_parent_without_id():
    parent = SimpleNamespace(year_number=2024, ved=0, e=100)  # stub «…, всего»
    child = _param(e=40)
    assert compare_parent_to_children_sum(parent, [child], attrs=("e",)) == {}


def test_compare_skips_when_parent_ved_gt_zero():
    parent = _param(ved=2, e=100, q=50)
    child = _param(ved=0, e=40, q=10)
    assert compare_parent_to_children_sum(parent, [child], attrs=("e", "q")) == {}


def test_compare_flags_when_parent_ved_zero():
    parent = _param(ved=0, e=100)
    child = _param(ved=2, e=40)
    mm = compare_parent_to_children_sum(parent, [child], attrs=("e",))
    assert "e" in mm
    assert mm["e"]["children_sum"] == Decimal("40")


def test_station_block_mismatch_keyed_by_parent_year():
    parent_eg = SimpleNamespace(id=1, main=None, comp=1, numb=100)
    child_eg = SimpleNamespace(id=2, main=100, comp=None, numb=101)
    sb = {
        "has_composite_structure": True,
        "composite_parent_eg_id": 1,
        "group_blocks": [
            {
                "equipment_group": parent_eg,
                "is_composite_parent": True,
                "is_composite_child": False,
                "rows": [(parent_eg, _param(id=10, year_number=2024, ved=0, e=100, q=10))],
            },
            {
                "equipment_group": child_eg,
                "is_composite_parent": False,
                "is_composite_child": True,
                "rows": [(child_eg, _param(id=11, year_number=2024, e=55, q=10))],
            },
        ],
    }
    result = build_composite_parts_sum_mismatch_for_station_block(
        sb, attrs=("e", "q"), rounding_digits=1
    )
    assert "1:2024" in result
    assert "e" in result["1:2024"]
    assert "q" not in result["1:2024"]  # 10 − 10 = 0
    assert result["1:2024"]["e"]["children_sum"] == Decimal("55")


def test_station_block_skips_year_when_parent_ved_gt_zero():
    parent_eg = SimpleNamespace(id=1, main=None, comp=1, numb=100)
    child_eg = SimpleNamespace(id=2, main=100, comp=None, numb=101)
    sb = {
        "has_composite_structure": True,
        "composite_parent_eg_id": 1,
        "group_blocks": [
            {
                "equipment_group": parent_eg,
                "is_composite_parent": True,
                "is_composite_child": False,
                "rows": [
                    (parent_eg, _param(id=10, year_number=2024, ved=2, e=100)),
                    (parent_eg, _param(id=12, year_number=2025, ved=0, e=100)),
                ],
            },
            {
                "equipment_group": child_eg,
                "is_composite_parent": False,
                "is_composite_child": True,
                "rows": [
                    (child_eg, _param(id=11, year_number=2024, ved=0, e=55)),
                    (child_eg, _param(id=13, year_number=2025, ved=2, e=55)),
                ],
            },
        ],
    }
    result = build_composite_parts_sum_mismatch_for_station_block(
        sb, attrs=("e",), rounding_digits=1
    )
    assert "1:2024" not in result
    assert "1:2025" in result
    assert "e" in result["1:2025"]
