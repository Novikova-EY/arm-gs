# -*- coding: utf-8 -*-
from app.fuel.services.calculation.ensure_calculation_year_data_services import (
    heat_seed_target_years,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    _HEAT_FUEL_PARAM_COPY_ATTRS,
)


def test_heat_seed_target_years_skips_base():
    assert heat_seed_target_years(2024, 2026) == [2025, 2026]


def test_heat_seed_target_years_same_year():
    assert heat_seed_target_years(2024, 2024) == []


def test_qotr_is_copied_from_access_station_row():
    assert "qotr" in _HEAT_FUEL_PARAM_COPY_ATTRS
    assert "q" in _HEAT_FUEL_PARAM_COPY_ATTRS


def test_apply_hat_q_fills_empty_keeps_qotr(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from app.fuel.services.calculation import fuel_calculation_edit_data_services as svc

    fp = SimpleNamespace(q=None, qotr=Decimal("900"))

    monkeypatch.setattr(
        svc,
        "_bulk_fuel_params_by_group_and_years",
        lambda ids, years, version_id: {(28293, 2026): fp},
    )
    monkeypatch.setattr(
        svc,
        "_bulk_heat_and_tariffs_q_by_group_and_years",
        lambda ids, years, version_id: {(28293, 2026): Decimal("1749.1")},
    )

    n = svc.apply_heat_and_tariffs_q_for_groups([28293], [2026], 37)
    assert n == 1
    assert fp.q == Decimal("1749.1")
    assert fp.qotr == Decimal("900")


def test_apply_hat_q_does_not_overwrite_imported_q(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from app.fuel.services.calculation import fuel_calculation_edit_data_services as svc

    fp = SimpleNamespace(q=Decimal("1525"), qotr=Decimal("900"))
    monkeypatch.setattr(
        svc,
        "_bulk_fuel_params_by_group_and_years",
        lambda ids, years, version_id: {(1, 2026): fp},
    )
    monkeypatch.setattr(
        svc,
        "_bulk_heat_and_tariffs_q_by_group_and_years",
        lambda ids, years, version_id: {(1, 2026): Decimal("947.29")},
    )
    assert svc.apply_heat_and_tariffs_q_for_groups([1], [2026], 37) == 0
    assert fp.q == Decimal("1525")


def test_apply_hat_q_skips_when_already_equal(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from app.fuel.services.calculation import fuel_calculation_edit_data_services as svc

    fp = SimpleNamespace(q=Decimal("1749.1"), qotr=Decimal("900"))
    monkeypatch.setattr(
        svc,
        "_bulk_fuel_params_by_group_and_years",
        lambda ids, years, version_id: {(1, 2026): fp},
    )
    monkeypatch.setattr(
        svc,
        "_bulk_heat_and_tariffs_q_by_group_and_years",
        lambda ids, years, version_id: {(1, 2026): Decimal("1749.1")},
    )
    assert svc.apply_heat_and_tariffs_q_for_groups([1], [2026], 37) == 0
    assert fp.q == Decimal("1749.1")


def test_apply_hat_q_skips_year_without_scheme(monkeypatch):
    from decimal import Decimal
    from types import SimpleNamespace

    from app.fuel.services.calculation import fuel_calculation_edit_data_services as svc

    fp = SimpleNamespace(q=Decimal("1575.867"), qotr=Decimal("900"))
    monkeypatch.setattr(
        svc,
        "_bulk_fuel_params_by_group_and_years",
        lambda ids, years, version_id: {(1, 2026): fp},
    )
    monkeypatch.setattr(
        svc,
        "_bulk_heat_and_tariffs_q_by_group_and_years",
        lambda ids, years, version_id: {},
    )
    assert svc.apply_heat_and_tariffs_q_for_groups([1], [2026], 37) == 0
    assert fp.q == Decimal("1575.867")
    assert fp.qotr == Decimal("900")
