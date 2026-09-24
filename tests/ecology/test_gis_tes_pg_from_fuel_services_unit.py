# -*- coding: utf-8 -*-
"""Юнит-тесты: состав групп анализа ПГ из модуля Топливо."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.ecology.services.gis_tes_pg_from_fuel_services import (
    _eg_display_name,
    _eg_display_numb,
    _is_boiler_group,
    _territory_filters_to_fuel_filters,
    _type_name_is_boiler,
)


def test_eg_display_helpers():
    eg = SimpleNamespace(numb=708, name="ТЭЦ-1", name_ext=None, id=11)
    param = SimpleNamespace(numb1120=708, year_number=2017)
    assert _eg_display_numb(eg, param) == 708
    assert _eg_display_name(eg) == "ТЭЦ-1"
    assert _type_name_is_boiler("Котельная")
    assert _type_name_is_boiler("котельная (пар)")
    assert not _type_name_is_boiler("ТЭЦ")
    assert _is_boiler_group(SimpleNamespace(id=99, name="ТЭЦ"), {99})
    assert not _is_boiler_group(SimpleNamespace(id=6, name="Котельная №1"), set())


def test_territory_filters_mapping():
    mapped = _territory_filters_to_fuel_filters(
        {
            "energy_system_type_filter": [1],
            "numb1120_filter": [708],
            "station_name_filter": "ТЭЦ",
            "ved_filter": "industry",
        }
    )
    assert mapped["energy_system_type_filter"] == [1]
    assert mapped["numb1120_filter"] == [708]
    assert mapped["equipment_group_name_filter"] == "ТЭЦ"
    assert "ved_filter" not in mapped


def test_collect_pg_groups_from_fuel_builds_rows(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    param = SimpleNamespace(
        numb1120=708,
        year_number=2017,
        ved=1,
        nust=10,
        e=20,
        q=30,
        ugol=None,
        mazut=None,
        gaz=1,
        isk_gaz=None,
        proch=None,
        torf=None,
    )

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {"rows": [(eg, param)], "numb1120_filter_choices": [708]},
    )
    monkeypatch.setattr(
        fced,
        "_expand_fuel_param_rows_for_year_interval",
        lambda rows, start, end: rows,
    )
    monkeypatch.setattr(
        egfps,
        "build_equipment_group_fuel_params_hierarchy",
        lambda rows, **kwargs: [
            {
                "est_id": 1,
                "est_name": "ЕЭС",
                "ues_list": [
                    {
                        "ues_id": 2,
                        "ues_name": "ОЭС",
                        "res_list": [
                            {
                                "res_id": 3,
                                "res_name": "РЭС",
                                "station_blocks": [
                                    {
                                        "group_blocks": [
                                            {
                                                "equipment_group": eg,
                                                "rows": [(eg, param)],
                                                "is_composite_parent": False,
                                                "is_composite_child": True,
                                                "show_composite_cluster": True,
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False)
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(
        cmp,
        "load_fuel_indicators_by_numb_year",
        lambda numbs, years: {
            (708, 2017): {
                "energy_system_type_id": 1,
                "est_name": "ЕЭС",
                "ues_id": 2,
                "ues": "ОЭС",
                "res_id": 3,
                "res_name": "РЭС",
                "station_name": "ТЭЦ-1",
                "ved": 1,
                "nust": 10,
                "e": 20,
                "q": 30,
                "gaz_estest_tce": 1000,
                "gaz_all_tce": 1000,
            }
        },
    )
    monkeypatch.setattr(
        cmp,
        "load_pg_ecology_overlay_by_numb_year",
        lambda *a, **k: {
            (708, 2017): {
                "gas_consumption_tce": 900,
                "co2_from_gas_t": 1800,
                "oil_fuel_consumption_tce": 0,
                "co2_from_oil_fuel_t": 0,
                "solid_fuel_consumption_tce": 0,
                "co2_from_solid_fuel_t": 0,
            }
        },
    )

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
        {"key": "NUST", "numeric": True, "source_index": 3},
        {"key": "GAZ_ESTEST", "numeric": True, "source_index": 4},
        {"key": "GAZ_ek", "numeric": True, "source_index": 5},
        {"key": "CO2_gaz", "numeric": True, "source_index": 6},
        {"key": "CO2", "numeric": True, "source_index": 7},
    ]
    visible = list(source_columns)

    groups, choices = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible,
        digits=1,
    )
    assert choices == [708]
    assert len(groups) == 1
    assert groups[0]["numb"] == 708
    assert groups[0]["is_composite_child"] is True
    assert groups[0]["show_composite_cluster"] is True
    assert groups[0]["rows"][0]["year"] == 2017
    by_key = {col["key"]: groups[0]["rows"][0]["cells"][i] for i, col in enumerate(visible)}
    assert by_key["NAME"] == "ТЭЦ-1"
    assert by_key["GAZ_ek"].replace(" ", "") == "900"
    assert by_key["CO2_gaz"].replace(" ", "") == "1800"


def test_pg_bez_kot_excludes_boilers(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg_ok = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    eg_boiler = SimpleNamespace(id=99, numb=999, name="ТЭЦ-котельная-тест", name_ext=None)
    param_ok = SimpleNamespace(numb1120=708, year_number=2017, ved=1)
    param_boiler = SimpleNamespace(numb1120=999, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {
            "rows": [(eg_ok, param_ok), (eg_boiler, param_boiler)],
            "numb1120_filter_choices": [708, 999],
        },
    )
    monkeypatch.setattr(fced, "_expand_fuel_param_rows_for_year_interval", lambda rows, start, end: rows)

    def _hierarchy(rows, **kwargs):
        blocks = []
        for eg, param in rows:
            blocks.append(
                {
                    "equipment_group": eg,
                    "rows": [(eg, param)],
                    "is_composite_parent": False,
                    "is_composite_child": False,
                    "show_composite_cluster": False,
                }
            )
        return [
            {
                "est_id": 1,
                "est_name": "ЕЭС",
                "ues_list": [
                    {
                        "ues_id": 2,
                        "ues_name": "ОЭС",
                        "res_list": [
                            {
                                "res_id": 3,
                                "res_name": "РЭС",
                                "station_blocks": [{"group_blocks": blocks}],
                            }
                        ],
                    }
                ],
            }
        ]

    monkeypatch.setattr(egfps, "build_equipment_group_fuel_params_hierarchy", _hierarchy)
    monkeypatch.setattr(egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False)
    monkeypatch.setattr(mod, "get_boiler_equipment_group_ids", lambda version_id=None: {99})
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
    ]
    groups, _ = mod.collect_pg_groups_from_fuel(
        "pg-bez-kot",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=source_columns,
        digits=1,
    )
    assert [g["numb"] for g in groups] == [708]


def test_zv_bez_kot_excludes_boilers(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg_ok = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    eg_boiler = SimpleNamespace(id=99, numb=999, name="ТЭЦ-котельная-тест", name_ext=None)
    param_ok = SimpleNamespace(numb1120=708, year_number=2017, ved=1)
    param_boiler = SimpleNamespace(numb1120=999, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {
            "rows": [(eg_ok, param_ok), (eg_boiler, param_boiler)],
            "numb1120_filter_choices": [708, 999],
        },
    )
    monkeypatch.setattr(fced, "_expand_fuel_param_rows_for_year_interval", lambda rows, start, end: rows)

    def _hierarchy(rows, **kwargs):
        blocks = []
        for eg, param in rows:
            blocks.append(
                {
                    "equipment_group": eg,
                    "rows": [(eg, param)],
                    "is_composite_parent": False,
                    "is_composite_child": False,
                    "show_composite_cluster": False,
                }
            )
        return [
            {
                "est_id": 1,
                "est_name": "ЕЭС",
                "ues_list": [
                    {
                        "ues_id": 2,
                        "ues_name": "ОЭС",
                        "res_list": [
                            {
                                "res_id": 3,
                                "res_name": "РЭС",
                                "station_blocks": [{"group_blocks": blocks}],
                            }
                        ],
                    }
                ],
            }
        ]

    monkeypatch.setattr(egfps, "build_equipment_group_fuel_params_hierarchy", _hierarchy)
    monkeypatch.setattr(egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False)
    monkeypatch.setattr(mod, "get_boiler_equipment_group_ids", lambda version_id=None: {99})
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_zv_ecology_overlay_by_numb_year", lambda *a, **k: {})

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
    ]
    groups, _ = mod.collect_pg_groups_from_fuel(
        "zv-bez-kot",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=source_columns,
        digits=1,
    )
    assert [g["numb"] for g in groups] == [708]


def test_collect_zv_groups_from_fuel_builds_rows(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    param = SimpleNamespace(numb1120=708, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {"rows": [(eg, param)], "numb1120_filter_choices": [708]},
    )
    monkeypatch.setattr(fced, "_expand_fuel_param_rows_for_year_interval", lambda rows, start, end: rows)
    monkeypatch.setattr(
        egfps,
        "build_equipment_group_fuel_params_hierarchy",
        lambda rows, **kwargs: [
            {
                "est_id": 1,
                "est_name": "ЕЭС",
                "ues_list": [
                    {
                        "ues_id": 2,
                        "ues_name": "ОЭС",
                        "res_list": [
                            {
                                "res_id": 3,
                                "res_name": "РЭС",
                                "station_blocks": [
                                    {
                                        "group_blocks": [
                                            {
                                                "equipment_group": eg,
                                                "rows": [(eg, param)],
                                                "is_composite_parent": False,
                                                "is_composite_child": False,
                                                "show_composite_cluster": False,
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False)
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(
        cmp,
        "load_zv_ecology_overlay_by_numb_year",
        lambda *a, **k: {
            (708, 2017): {
                "solid_substances": 11,
                "sulfur_dioxide": 22,
                "carbon_monoxide": 3,
                "nitrogen_oxides": 4,
                "hydrocarbons": 5,
                "voc": 6,
                "other_gaseous_and_liquid": 7,
            }
        },
    )

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
        {"key": "TVERD_V", "numeric": True, "source_index": 3},
        {"key": "SO2_gaz", "numeric": True, "source_index": 4},
        {"key": "GAZ and ZHID", "numeric": True, "source_index": 5},
        {"key": "VIBROS_ekol", "numeric": True, "source_index": 6},
        {"key": "CO_gaz", "numeric": True, "source_index": 7},
        {"key": "NOx_gaz", "numeric": True, "source_index": 8},
        {"key": "UGLEVOD", "numeric": True, "source_index": 9},
        {"key": "LOS", "numeric": True, "source_index": 10},
        {"key": "PROCH_ekol", "numeric": True, "source_index": 11},
    ]
    visible = list(source_columns)
    groups, choices = mod.collect_pg_groups_from_fuel(
        "zv-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible,
        digits=1,
    )
    assert choices == [708]
    assert len(groups) == 1
    by_key = {col["key"]: groups[0]["rows"][0]["cells"][i] for i, col in enumerate(visible)}
    assert by_key["NAME"] == "ТЭЦ-1"
    assert by_key["TVERD_V"].replace(" ", "") == "11"
    assert by_key["SO2_gaz"].replace(" ", "") == "22"
    assert by_key["GAZ and ZHID"].replace(" ", "") == "47"
    assert by_key["VIBROS_ekol"].replace(" ", "") == "58"


def test_ecology_hub_has_zv_totals_tile():
    text = Path("app/templates/ecology/ecology_start.html").read_text(encoding="utf-8")
    assert "sheet_slug='pg-vse'" in text
    assert "sheet_slug='zv-vse'" in text
    assert "Загрязняющие вещества (ЗВ)<br />агрегационные суммы" in text


def test_ecology_hub_has_enabled_new_tes_calc_tile():
    text = Path("app/templates/ecology/ecology_start.html").read_text(encoding="utf-8")
    assert "ecology_bp.new_tes_table" in text
    assert "Расчет по новым ТЭС" in text
    assert "Расчет по действующим ТЭС" in text
    assert "hub_tile_disabled" not in text


def test_collect_pg_groups_hydrate_false_then_fill(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    param = SimpleNamespace(numb1120=708, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {"rows": [(eg, param)], "numb1120_filter_choices": [708]},
    )
    monkeypatch.setattr(
        egfps,
        "build_equipment_group_fuel_params_hierarchy",
        lambda rows, **kwargs: [
            {
                "est_id": 1,
                "est_name": "ЕЭС",
                "ues_list": [
                    {
                        "ues_id": 2,
                        "ues_name": "ОЭС",
                        "res_list": [
                            {
                                "res_id": 3,
                                "res_name": "РЭС",
                                "station_blocks": [
                                    {
                                        "group_blocks": [
                                            {
                                                "equipment_group": eg,
                                                "rows": [(eg, param)],
                                                "is_composite_parent": False,
                                                "is_composite_child": False,
                                                "show_composite_cluster": False,
                                            }
                                        ]
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    )
    monkeypatch.setattr(egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False)
    monkeypatch.setattr(mod, "get_boiler_equipment_group_ids", lambda version_id=None: set())
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
    ]
    groups, _ = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2018,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=source_columns,
        digits=1,
        hydrate=False,
    )
    assert len(groups) == 1
    assert groups[0]["rows"] == []
    assert groups[0]["numb"] == 708

    mod.fill_pg_group_year_rows(
        groups[:1],
        sheet_slug="pg-vse",
        start_year=2017,
        end_year=2018,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=source_columns,
        digits=1,
    )
    assert [row["year"] for row in groups[0]["rows"]] == [2017, 2018]

