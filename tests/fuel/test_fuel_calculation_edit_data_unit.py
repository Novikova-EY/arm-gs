# -*- coding: utf-8 -*-
from decimal import Decimal
from types import SimpleNamespace

from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    _MissingYearFuelParam,
    _copy_access_station_snk_snt,
    _merge_expanded_rows_with_loaded_params,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    displayed_fuel_param_snk,
    displayed_fuel_param_snt,
)


def test_copy_snk_snt_uses_formula_not_stored_wrong_scale():
    source = SimpleNamespace(
        sn_ee=Decimal("77.918291"),
        e=Decimal("1897.868006"),
        snk=Decimal("4105.569552"),
        sn_te=Decimal("57.869512"),
        q=Decimal("1575.867"),
        sn_t=Decimal("36722.33"),
    )
    target = SimpleNamespace(sn_ee=Decimal("0"), sn_te=Decimal("0"), snk=None, sn_t=None)
    _copy_access_station_snk_snt(target, source)
    assert target.snk == displayed_fuel_param_snk(source)
    assert target.sn_t == displayed_fuel_param_snt(source)
    assert abs(target.snk - Decimal("4.10557")) < Decimal("0.001")
    assert target.sn_ee is None
    assert target.sn_te is None


def test_copy_snk_snt_falls_back_to_stored_when_no_numerators():
    source = SimpleNamespace(
        sn_ee=None,
        e=Decimal("1000"),
        snk=Decimal("4.1"),
        sn_te=None,
        q=Decimal("100"),
        sn_t=Decimal("51.4"),
    )
    target = SimpleNamespace(sn_ee=None, sn_te=None, snk=None, sn_t=None)
    _copy_access_station_snk_snt(target, source)
    assert target.snk == Decimal("4.1")
    assert target.sn_t == Decimal("51.4")
    assert target.sn_ee is None
    assert target.sn_te is None


def test_copy_snk_snt_does_not_clear_nonzero_numerators():
    source = SimpleNamespace(
        sn_ee=None, e=None, snk=Decimal("4.1"), sn_te=None, q=None, sn_t=Decimal("50")
    )
    target = SimpleNamespace(
        sn_ee=Decimal("10"), sn_te=Decimal("5"), snk=None, sn_t=None
    )
    _copy_access_station_snk_snt(target, source)
    assert target.snk == Decimal("4.1")
    assert target.sn_t == Decimal("50")
    assert target.sn_ee == Decimal("10")
    assert target.sn_te == Decimal("5")


def test_copy_snk_snt_only_if_empty_keeps_nonzero_target():
    source = SimpleNamespace(
        sn_ee=None, e=None, snk=Decimal("4.1"), sn_te=None, q=None, sn_t=Decimal("50")
    )
    target = SimpleNamespace(
        sn_ee=None, sn_te=None, snk=Decimal("9"), sn_t=Decimal("80")
    )
    _copy_access_station_snk_snt(target, source, only_if_empty=True)
    assert target.snk == Decimal("9")
    assert target.sn_t == Decimal("80")


def test_merge_reattaches_real_param_over_missing_year():
    eg = SimpleNamespace(id=28297)
    missing = _MissingYearFuelParam(2026)
    real = SimpleNamespace(year_number=2026, ved=0, nust=360)
    loaded = {(28297, 2026): real}
    rows = [(eg, missing), (eg, _MissingYearFuelParam(2025))]
    out = _merge_expanded_rows_with_loaded_params(rows, loaded)
    assert out[0][1] is real
    assert isinstance(out[1][1], _MissingYearFuelParam)
    assert out[1][1].year_number == 2025


def test_merge_interval_expands_display_range_without_db():
    from werkzeug.datastructures import MultiDict

    from app.fuel.routes.calculation.fuel_calculation_edit_data_routes import (
        _merge_interval_onto_md,
    )

    md = MultiDict([("start_year", "2024"), ("end_year", "2025")])
    _merge_interval_onto_md(md, y_min=2026, y_max=2031)
    assert md["start_year"] == "2024"
    assert md["end_year"] == "2031"


def test_missing_year_placeholder_is_skipped_by_snk_overlay():
    """overlay_snk_calc_from_fuel_params: if not cons — пустой год без SNK из ТЭП."""
    from app.fuel.services.calculation.fuel_calculation_specific_consumption_edit_data_services import (
        _MissingYearSpecificFuelParam,
    )

    missing = _MissingYearSpecificFuelParam(2027)
    assert not missing
    assert missing.snk_calc is None
