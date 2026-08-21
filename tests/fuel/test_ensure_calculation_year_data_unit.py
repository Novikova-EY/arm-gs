# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.calculation import ensure_calculation_year_data_services as ensure_svc
from app.fuel.services.calculation import fuel_calculation_edit_data_services as edit_svc
from app.fuel.services.calculation.ensure_calculation_year_data_services import (
    _eg_ids_with_year,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    _prefer_matching_db_version,
)


def test_prefer_matching_db_version_picks_current():
    other = SimpleNamespace(database_version_id=1)
    current = SimpleNamespace(database_version_id=37)
    assert _prefer_matching_db_version([other, current], 37) is current


def test_prefer_matching_db_version_falls_back_to_any_row():
    other = SimpleNamespace(database_version_id=1)
    assert _prefer_matching_db_version([other], 37) is other


def test_prefer_matching_db_version_empty():
    assert _prefer_matching_db_version([], 37) is None


class _Query:
    def __init__(self, calls: list):
        self.calls = calls

    def filter(self, *args):
        self.calls.append(args)
        return self

    def all(self):
        return [(17333,)]


class _Session:
    def __init__(self, calls: list):
        self.calls = calls

    def query(self, *_a, **_k):
        return _Query(self.calls)


def test_fuel_param_year_existence_ignores_database_version(monkeypatch):
    calls: list = []
    monkeypatch.setattr(ensure_svc.db, "session", _Session(calls))
    result = _eg_ids_with_year(EquipmentGroupFuelParam, [17333], 2026, 37)
    assert result == {17333}
    assert len(calls) == 1


def test_specific_consumption_year_existence_ignores_database_version(monkeypatch):
    calls: list = []
    monkeypatch.setattr(ensure_svc.db, "session", _Session(calls))
    _eg_ids_with_year(EquipmentGroupSpecificFuelConsumption, [17333], 2026, 37)
    assert len(calls) == 1


def test_formula_year_existence_filters_database_version(monkeypatch):
    calls: list = []
    monkeypatch.setattr(ensure_svc.db, "session", _Session(calls))
    _eg_ids_with_year(EquipmentGroupFuelFormula, [17333], 2026, 37)
    assert len(calls) == 2


def test_get_fuel_param_reuses_row_from_other_version(monkeypatch):
    existing = SimpleNamespace(
        equipment_group_id=17333, year_number=2026, database_version_id=1
    )

    class _ParamQuery:
        def filter_by(self, **_kwargs):
            return self

        def all(self):
            return [existing]

    class _DummyParam:
        query = _ParamQuery()

    monkeypatch.setattr(edit_svc, "EquipmentGroupFuelParam", _DummyParam)
    assert edit_svc._get_fuel_param_for_group_year(17333, 2026, 37) is existing


def test_ensure_does_not_copy_specific_consumption(monkeypatch):
    monkeypatch.setattr(
        ensure_svc, "get_equipment_group_ids_for_fuel_params_filters", lambda *a, **k: [1]
    )
    monkeypatch.setattr(
        ensure_svc, "copy_heat_fuel_param_columns_for_filters", lambda *a, **k: (0, 0, 1)
    )
    monkeypatch.setattr(
        ensure_svc, "apply_heat_and_tariffs_q_for_existing_rows", lambda *a, **k: 0
    )
    monkeypatch.setattr(
        ensure_svc, "fill_snk_snt_from_source_year_for_existing_rows", lambda *a, **k: 0
    )

    result = ensure_svc.ensure_calculation_year_data_from_base(
        {}, base_year=2024, calc_year=2026
    )
    assert result["specific"] == (0, 0, 0)
    assert result["formulas"] == (0, 0, 0)
    assert "copy_specific_fuel_consumption_between_years_for_filters" not in dir(
        ensure_svc
    )
    assert "copy_fuel_formulas_between_years_for_filters" not in dir(ensure_svc)


def test_ensure_does_not_copy_formulas_when_calc_year_missing(monkeypatch):
    """Копия 2024→2026 перекрыла бы Access 2025 при Seek year ≤ cyear."""
    monkeypatch.setattr(
        ensure_svc, "get_equipment_group_ids_for_fuel_params_filters", lambda *a, **k: [1]
    )
    monkeypatch.setattr(
        ensure_svc, "copy_heat_fuel_param_columns_for_filters", lambda *a, **k: (0, 0, 1)
    )
    monkeypatch.setattr(
        ensure_svc, "apply_heat_and_tariffs_q_for_existing_rows", lambda *a, **k: 0
    )
    monkeypatch.setattr(
        ensure_svc, "fill_snk_snt_from_source_year_for_existing_rows", lambda *a, **k: 0
    )
    monkeypatch.setattr(ensure_svc, "_needs_year_copy", lambda *a, **k: True)

    result = ensure_svc.ensure_calculation_year_data_from_base(
        {}, base_year=2024, calc_year=2026
    )
    assert result["formulas"] == (0, 0, 0)
    assert result["did_anything"] is False
