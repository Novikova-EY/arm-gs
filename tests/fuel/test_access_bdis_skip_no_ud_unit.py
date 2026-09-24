# -*- coding: utf-8 -*-
"""Access Кнопка27: нет удельных в [byear, cyear] → skip1, часы не переписываем."""
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    _access_bdis_skip_no_specific,
)


def test_no_specific_is_skip1():
    assert _access_bdis_skip_no_specific(None) is True


def test_specific_row_is_not_skip1():
    assert _access_bdis_skip_no_specific(object()) is False
