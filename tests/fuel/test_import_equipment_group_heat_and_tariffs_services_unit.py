# -*- coding: utf-8 -*-
"""Unit tests for heat/tariffs Excel wide→long unpivot."""

import pandas as pd

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.fuel.services.fuel_imports.import_equipment_group_heat_and_tariffs_services import (
    _apply_column_aliases,
    _orm_session,
    _unpivot_wide_access_df,
)


def test_unpivot_wide_access_merges_q_and_tarif():
    df = pd.DataFrame(
        [
            {
                "kod_goroda": 10,
                "name_goroda": "Архангельск",
                "var_razv": 1,
                "name_ETO": "Архангельская ТЭЦ",
                "NUMB1120": 1,
                "NDvST": 1,
                "dannie": "Q",
                "2024": 100.0,
                "2025": 110.0,
            },
            {
                "kod_goroda": 10,
                "name_goroda": "Архангельск",
                "var_razv": 1,
                "name_ETO": "Архангельская ТЭЦ",
                "NUMB1120": 1,
                "NDvST": 1,
                "dannie": "TARIF",
                "2024": 2000.0,
                "2025": 2100.0,
            },
        ]
    )
    df = _apply_column_aliases(df)
    long_df = _unpivot_wide_access_df(df)
    assert len(long_df) == 2
    row_2024 = long_df[long_df["year_number"] == 2024].iloc[0]
    assert float(row_2024["q"]) == 100.0
    assert float(row_2024["tarif"]) == 2000.0
    assert int(row_2024["numb1120"]) == 1
    assert row_2024["name_eto"] == "Архангельская ТЭЦ"


def test_orm_session_unwraps_scoped_session():
    inner = SimpleNamespace(expire_on_commit=True)
    scoped = MagicMock(spec=["__call__"])
    scoped.return_value = inner
    fake_db = SimpleNamespace(session=scoped)
    with patch(
        "app.fuel.services.fuel_imports.import_equipment_group_heat_and_tariffs_services.db",
        fake_db,
    ):
        assert _orm_session() is inner
        inner.expire_on_commit = False
        assert inner.expire_on_commit is False


def test_orm_session_keeps_real_session():
    sess = SimpleNamespace(expire_on_commit=True)
    fake_db = SimpleNamespace(session=sess)
    with patch(
        "app.fuel.services.fuel_imports.import_equipment_group_heat_and_tariffs_services.db",
        fake_db,
    ):
        assert _orm_session() is sess
