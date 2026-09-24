# -*- coding: utf-8 -*-
"""Юнит-тесты параметров анализа ПГ."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.ecology.services.analysis_pg_param_services import (
    report_values_payload,
    seed_missing_analysis_pg_params_from_reports,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import PG_ECOLOGY_VALUE_FIELDS


def test_report_payload_fields():
    row = SimpleNamespace(
        gas_consumption_tce=1,
        co2_from_gas_t=2,
        oil_fuel_consumption_tce=3,
        co2_from_oil_fuel_t=4,
        solid_fuel_consumption_tce=5,
        co2_from_solid_fuel_t=6,
    )
    payload = report_values_payload(row)
    assert tuple(payload) == PG_ECOLOGY_VALUE_FIELDS
    assert payload == {
        "gas_consumption_tce": 1,
        "co2_from_gas_t": 2,
        "oil_fuel_consumption_tce": 3,
        "co2_from_oil_fuel_t": 4,
        "solid_fuel_consumption_tce": 5,
        "co2_from_solid_fuel_t": 6,
    }


def test_seed_missing_returns_zero_for_non_pg_sheet():
    assert seed_missing_analysis_pg_params_from_reports("zv-vse") == 0
    assert seed_missing_analysis_pg_params_from_reports("") == 0


def test_seed_missing_creates_absent_rows_only(monkeypatch):
    report = SimpleNamespace(
        station_numb=708,
        year_number=2017,
        gas_consumption_tce=10,
        co2_from_gas_t=20,
        oil_fuel_consumption_tce=30,
        co2_from_oil_fuel_t=40,
        solid_fuel_consumption_tce=50,
        co2_from_solid_fuel_t=60,
    )
    report2 = SimpleNamespace(
        station_numb=709,
        year_number=2017,
        gas_consumption_tce=11,
        co2_from_gas_t=21,
        oil_fuel_consumption_tce=31,
        co2_from_oil_fuel_t=41,
        solid_fuel_consumption_tce=51,
        co2_from_solid_fuel_t=61,
    )

    class FakeQuery:
        def __init__(self, rows=None, entities=None):
            self._rows = rows or []
            self._entities = entities

        def filter(self, *args, **kwargs):
            return self

        def filter_by(self, **kwargs):
            return self

        def with_entities(self, *args, **kwargs):
            return FakeQuery(entities=self._entities)

        def all(self):
            if self._entities is not None:
                return self._entities
            return self._rows

    class FakeParamModel:
        query = FakeQuery(
            entities=[SimpleNamespace(station_numb=708, year_number=2017)]
        )
        station_numb = object()
        year_number = object()
        database_version_id = object()

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeReportModel:
        query = FakeQuery(rows=[report, report2])
        station_numb = object()
        year_number = object()
        database_version_id = object()

    session = MagicMock()
    fake_db = SimpleNamespace(session=session)

    monkeypatch.setattr(
        "flask.has_app_context",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.common.services.database_version_filter.get_current_db_version_id",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.ecology.models.pg_param_calc_model.PGParamCalc",
        FakeParamModel,
    )
    monkeypatch.setattr(
        "app.ecology.models.pg_report_gis_tek_model.PGReportGisTek",
        FakeReportModel,
    )
    monkeypatch.setattr("app.extensions.db", fake_db)

    created = seed_missing_analysis_pg_params_from_reports("pg-bez-kot")
    assert created == 1
    assert session.add.call_count == 1
    added = session.add.call_args[0][0]
    assert added.kwargs["sheet_slug"] == "pg-bez-kot"
    assert added.kwargs["station_numb"] == 709
    assert added.kwargs["gas_consumption_tce"] == 11
    session.commit.assert_called_once()
