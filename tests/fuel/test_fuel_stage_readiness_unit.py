# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.distribution.distribution_stage_services import (
    D03,
    sum_e_of_distribution_processed_rows,
)


def _row(ved, e):
    return SimpleNamespace(ved=ved, e=e)


def test_sum_skips_groups_without_specific_even_if_ewtp_leftover_e():
    """
    После Распред ΣE=Ераспред по 79 группам с удельником.
    14 групп без ТЭП сохраняют скопированное E — их нельзя включать в допуск «Топливо».
    """
    processed_e = Decimal("64547.1")
    leftover_e = Decimal("1200")
    by_key = {
        (1, 2026): _row(2, processed_e),
        (2, 2026): _row(2, leftover_e),
    }
    total, counted = sum_e_of_distribution_processed_rows(
        [1, 2],
        cyear=2026,
        by_key=by_key,
        group_ids_with_specific={1},
    )
    assert counted == 1
    assert total == processed_e
    assert abs(processed_e - total) <= D03
    coeff_preview_sum = processed_e + leftover_e
    assert abs(processed_e - coeff_preview_sum) > D03


def test_sum_skips_ved_zero_parent_shell():
    by_key = {
        (10, 2026): _row(0, Decimal("500")),
        (11, 2026): _row(2, Decimal("100")),
    }
    total, counted = sum_e_of_distribution_processed_rows(
        [10, 11],
        cyear=2026,
        by_key=by_key,
        group_ids_with_specific={10, 11},
    )
    assert counted == 1
    assert total == Decimal("100")


def test_sum_counts_all_processed_rows():
    by_key = {
        (1, 2026): _row(1, Decimal("10.1")),
        (2, 2026): _row(2, Decimal("20.2")),
        (3, 2026): _row(4, Decimal("30.0")),
    }
    total, counted = sum_e_of_distribution_processed_rows(
        [1, 2, 3],
        cyear=2026,
        by_key=by_key,
        group_ids_with_specific={1, 2, 3},
    )
    assert counted == 3
    assert total == Decimal("60.3")
