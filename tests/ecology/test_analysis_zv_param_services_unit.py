# -*- coding: utf-8 -*-
"""Юнит-тесты параметров анализа ЗВ."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ecology.services.analysis_zv_param_services import (
    report_values_payload,
    seed_missing_analysis_zv_params_from_reports,
    upsert_analysis_zv_param_values,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import ZV_ECOLOGY_VALUE_FIELDS


def test_report_payload_fields():
    row = SimpleNamespace(
        solid_substances=1,
        sulfur_dioxide=2,
        carbon_monoxide=3,
        nitrogen_oxides=4,
        hydrocarbons=5,
        voc=6,
        other_gaseous_and_liquid=7,
    )
    payload = report_values_payload(row)
    assert tuple(payload) == ZV_ECOLOGY_VALUE_FIELDS
    assert payload == {
        "solid_substances": 1,
        "sulfur_dioxide": 2,
        "carbon_monoxide": 3,
        "nitrogen_oxides": 4,
        "hydrocarbons": 5,
        "voc": 6,
        "other_gaseous_and_liquid": 7,
    }


def test_seed_missing_returns_zero_for_non_zv_sheet():
    assert seed_missing_analysis_zv_params_from_reports("pg-vse") == 0
    assert seed_missing_analysis_zv_params_from_reports("") == 0


class _FakeQuery:
    def __init__(self, rows=None, entities=None):
        self._rows = rows or []
        self._entities = entities

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        return self

    def with_entities(self, *args, **kwargs):
        return _FakeQuery(entities=self._entities)

    def all(self):
        if self._entities is not None:
            return self._entities
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


def test_seed_missing_creates_absent_rows_only(monkeypatch):
    report = SimpleNamespace(
        station_numb=708,
        year_number=2017,
        solid_substances=1,
        sulfur_dioxide=2,
        carbon_monoxide=3,
        nitrogen_oxides=4,
        hydrocarbons=5,
        voc=6,
        other_gaseous_and_liquid=7,
    )
    report2 = SimpleNamespace(
        station_numb=709,
        year_number=2017,
        solid_substances=11,
        sulfur_dioxide=12,
        carbon_monoxide=13,
        nitrogen_oxides=14,
        hydrocarbons=15,
        voc=16,
        other_gaseous_and_liquid=17,
    )

    class FakeParamModel:
        query = _FakeQuery(
            entities=[SimpleNamespace(station_numb=708, year_number=2017)]
        )
        station_numb = object()
        year_number = object()
        database_version_id = object()

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeReportModel:
        query = _FakeQuery(rows=[report, report2])
        station_numb = object()
        year_number = object()
        database_version_id = object()

    session = MagicMock()
    fake_db = SimpleNamespace(session=session)

    monkeypatch.setattr("flask.has_app_context", lambda: True)
    monkeypatch.setattr(
        "app.common.services.database_version_filter.get_current_db_version_id",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.ecology.models.zv_param_calc_model.ZVParamCalc",
        FakeParamModel,
    )
    monkeypatch.setattr(
        "app.ecology.models.zv_report_gis_tek_model.ZVReportGisTek",
        FakeReportModel,
    )
    monkeypatch.setattr("app.extensions.db", fake_db)

    created = seed_missing_analysis_zv_params_from_reports("zv-bez-kot")
    assert created == 1
    assert session.add.call_count == 1
    added = session.add.call_args[0][0]
    assert added.kwargs["sheet_slug"] == "zv-bez-kot"
    assert added.kwargs["station_numb"] == 709
    assert added.kwargs["sulfur_dioxide"] == 12
    session.commit.assert_called_once()


def test_upsert_copies_report_values_and_applies_edit(monkeypatch):
    report = SimpleNamespace(
        solid_substances=1,
        sulfur_dioxide=2,
        carbon_monoxide=3,
        nitrogen_oxides=4,
        hydrocarbons=5,
        voc=6,
        other_gaseous_and_liquid=7,
    )
    created = []

    class FakeParamModel:
        query = _FakeQuery()
        station_numb = object()
        year_number = object()
        database_version_id = object()

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

    class FakeReportModel:
        query = _FakeQuery(rows=[report])
        database_version_id = object()

    session = MagicMock()
    monkeypatch.setattr(
        "app.common.services.database_version_filter.get_current_db_version_id",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.ecology.models.zv_param_calc_model.ZVParamCalc",
        FakeParamModel,
    )
    monkeypatch.setattr(
        "app.ecology.models.zv_report_gis_tek_model.ZVReportGisTek",
        FakeReportModel,
    )
    monkeypatch.setattr("app.extensions.db", SimpleNamespace(session=session))

    row = upsert_analysis_zv_param_values(
        "zv-vse", 708, 2017, {"sulfur_dioxide": "12,5"}
    )

    assert row is created[0]
    assert row.kwargs["sheet_slug"] == "zv-vse"
    assert row.kwargs["station_numb"] == 708
    assert row.kwargs["year_number"] == 2017
    assert row.kwargs["solid_substances"] == 1
    assert row.sulfur_dioxide == Decimal("12.5")
    session.add.assert_called_once_with(row)
    session.commit.assert_called_once()


def test_upsert_rejects_unknown_sheet():
    try:
        upsert_analysis_zv_param_values("pg-vse", 1, 2017, {"sulfur_dioxide": 1})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "zv-vse" in str(exc) or "sheet_slug" in str(exc)
