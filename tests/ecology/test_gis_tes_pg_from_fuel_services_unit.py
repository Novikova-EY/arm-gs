# -*- coding: utf-8 -*-
"""Юнит-тесты: состав групп анализа ПГ из модуля Топливо."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from decimal import Decimal

import pytest

from app.ecology.services.gis_tes_pg_from_fuel_services import (
    _eg_display_name,
    _eg_display_numb,
    _boiler_without_parent_group,
    _rows_without_boilers,
    _territory_filters_to_fuel_filters,
)


def _patch_station_links(monkeypatch, linked_numbs=None):
    """Привязка групп к станциям «Генерации»: по умолчанию — все запрошенные NUMB."""
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp

    linked = None if linked_numbs is None else set(linked_numbs)

    def _links(numbs):
        return {
            numb: [{"id": 500 + int(numb), "name": f"Станция {numb}"}]
            for numb in numbs
            if linked is None or numb in linked
        }

    monkeypatch.setattr(cmp, "load_generation_station_links_by_numb", _links)


@pytest.fixture(autouse=True)
def _station_links_for_composition_tests(monkeypatch):
    """Состав групп в тестах — как на странице: группы привязаны к станциям."""
    _patch_station_links(monkeypatch)


def test_drop_groups_without_station(monkeypatch):
    """Группы без привязки к станции «Генерации» убираются (сводной хватает подгруппы)."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod

    groups = [
        {"numb": 89, "member_numbs": [89, 997, 998]},
        {"numb": 708},
        {"numb": 999},
    ]
    _patch_station_links(monkeypatch, {997, 708})

    kept, hidden = mod._drop_groups_without_station(groups)

    assert [group["numb"] for group in kept] == [89, 708]
    assert hidden == {999}


def test_eg_display_helpers():
    eg = SimpleNamespace(numb=708, name="ТЭЦ-1", name_ext=None, id=11)
    param = SimpleNamespace(numb1120=708, year_number=2017)
    assert _eg_display_numb(eg, param) == 708
    assert _eg_display_numb(SimpleNamespace(numb=None), param) == 708
    assert _eg_display_name(eg) == "ТЭЦ-1"
    assert _eg_display_name(SimpleNamespace(name=None, name_ext="ТЭЦ-1")) == "ТЭЦ-1"


def test_boiler_without_parent_group_requires_main():
    # "С котельными" показываем только котельные в составе станции: MAIN заполнен.
    assert _boiler_without_parent_group(SimpleNamespace(main=None, comp=None))
    assert _boiler_without_parent_group(SimpleNamespace(main=0, comp=None))
    # Оболочка станции, разбитой на группы: COMP=1 и пустой MAIN — тоже вне состава.
    assert _boiler_without_parent_group(SimpleNamespace(main=None, comp=1))
    # Котельная в составе станции: MAIN = код родителя.
    assert not _boiler_without_parent_group(SimpleNamespace(main=708, comp=None))
    assert not _boiler_without_parent_group(SimpleNamespace(main="708", comp=None))


def test_rows_without_boilers_drops_hidden_numbs():
    station = (SimpleNamespace(id=1, numb=708), SimpleNamespace(numb1120=708))
    standalone_boiler = (SimpleNamespace(id=2, numb=999), SimpleNamespace(numb1120=999))
    station_boiler = (SimpleNamespace(id=3, numb=3595), SimpleNamespace(numb1120=3595))

    assert _rows_without_boilers(
        [station, standalone_boiler, station_boiler],
        {999},
    ) == [station, station_boiler]
    assert _rows_without_boilers([standalone_boiler], set()) == [standalone_boiler]


def test_groups_without_boilers_drops_station_block(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod

    # Блок станции с EG-котельной всплывает при сборке иерархии уже после отбора строк.
    groups = [{"numb": 708}, {"numb": 170}, {"numb": None}]

    assert mod._groups_without_boilers(groups, {170}) == [{"numb": 708}, {"numb": None}]


def test_hidden_boiler_numbs_follow_tab_rule(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod

    monkeypatch.setattr(mod, "_boiler_numbs", lambda version_id=None: {38, 999})
    monkeypatch.setattr(mod, "_boiler_numbs_without_parent", lambda version_id=None: {38})

    # «С котельными» — котельные в составе станции, «Без котельных» — все котельные.
    assert mod.hidden_boiler_numbs_for_sheet("pg-vse", 1) == {38}
    assert mod.hidden_boiler_numbs_for_sheet("zv-vse", 1) == {38}
    assert mod.hidden_boiler_numbs_for_sheet("pg-bez-kot", 1) == {38, 999}
    assert mod.hidden_boiler_numbs_for_sheet("zv-bez-kot", 1) == {38, 999}
    assert mod.hidden_boiler_numbs_for_sheet("pg-other", 1) == set()


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
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: set(),
    )
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


def test_pg_rows_fill_station_generation_columns(monkeypatch):
    """Столбцы «Руст, МВт» и «Выработка ЭЭ (Генерация)» заполняются из модуля «Генерация»."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1 (котельная)", name_ext=None)
    param = SimpleNamespace(numb1120=708, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(mod, "hidden_boiler_numbs_for_sheet", lambda sheet_slug, version_id=None: set())
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
                "station_name": "ТЭЦ-1 (котельная)",
                "ved": 1,
                "nust": 100,
                "e": 500,
                "q": 30,
            }
        },
    )
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(
        cmp,
        "load_station_generation_overlay",
        lambda numbs, years: {
            "names_by_numb": {708: "ТЭЦ-1"},
            "station_links_by_numb": {708: [{"id": 501, "name": "ТЭЦ-1"}]},
            "values_by_numb_year": {
                (708, 2017): {
                    "nust_generation": Decimal("100.0"),
                    "W_en_generation": Decimal("500.5"),
                }
            },
        },
    )

    visible = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
        {"key": "NUST", "numeric": True, "source_index": 3},
        {"key": "nust_generation", "numeric": True, "source_index": 4},
        {"key": "W_en", "numeric": True, "source_index": 5},
        {"key": "W_en_generation", "numeric": True, "source_index": 6},
    ]
    source_columns = [dict(column) for column in visible]

    groups, _ = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible,
        digits=1,
    )
    assert len(groups) == 1
    assert groups[0]["station_links"] == [{"id": 501, "name": "ТЭЦ-1"}]
    row = groups[0]["rows"][0]
    by_key = {column["key"]: row["cells"][index] for index, column in enumerate(visible)}
    assert by_key["NAME"] == "ТЭЦ-1"
    assert by_key["NUST"] == "100"
    assert by_key["nust_generation"] == "100"
    assert by_key["W_en"] == "500"
    assert by_key["W_en_generation"] == "500,5"
    keys = [column["key"] for column in visible]
    assert row["cell_mismatch"][keys.index("nust_generation")] is False
    assert row["cell_mismatch"][keys.index("W_en_generation")] is True


def test_pg_vse_hides_groups_without_station(monkeypatch):
    """Группа без привязки к станции «Генерации» на «С котельными» не показывается."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg_linked = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    eg_orphan = SimpleNamespace(id=12, numb=89, name="Калининградская ТЭЦ-1", name_ext=None)
    param_linked = SimpleNamespace(numb1120=708, year_number=2017, ved=1)
    param_orphan = SimpleNamespace(numb1120=89, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: set(),
    )
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {
            "rows": [(eg_linked, param_linked), (eg_orphan, param_orphan)],
            "numb1120_filter_choices": [89, 708],
        },
    )
    monkeypatch.setattr(
        egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False
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
                                            for eg, param in rows
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
    monkeypatch.setattr(
        aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0
    )
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_station_generation_overlay", lambda numbs, years: {})
    _patch_station_links(monkeypatch, {708})

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
    ]
    groups, choices = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=source_columns,
        digits=1,
    )

    assert [group["numb"] for group in groups] == [708]
    assert choices == [708]


def test_pg_rows_fill_station_affiliation_column(monkeypatch):
    """Столбец «Принадлежность» заполняется значениями страниц ГИС ТЭК."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1 (котельная)", name_ext=None)
    param = SimpleNamespace(numb1120=708, year_number=2017, ved=1)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(mod, "hidden_boiler_numbs_for_sheet", lambda sheet_slug, version_id=None: set())
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
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(
        cmp,
        "load_fuel_indicators_by_numb_year",
        lambda numbs, years: {
            (708, 2017): {
                "est_name": "ЕЭС",
                "ues_id": 2,
                "ues": "ОЭС",
                "res_id": 3,
                "res_name": "РЭС",
                "station_name": "ТЭЦ-1 (котельная)",
                "ved": 1,
                "nust": 100,
                "e": 500,
                "q": 30,
            }
        },
    )
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_station_generation_overlay", lambda numbs, years: {})
    monkeypatch.setattr(
        cmp,
        "load_station_affiliations_by_numb_year",
        lambda numbs, years: {(708, 2017): "отрасль"},
    )

    visible = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
        {"key": "Teplo", "numeric": True, "source_index": 3},
        {"key": "station_affiliation", "numeric": False, "source_index": 4},
    ]
    source_columns = [dict(column) for column in visible]

    groups, _ = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible,
        digits=1,
    )
    assert len(groups) == 1
    row = groups[0]["rows"][0]
    by_key = {column["key"]: row["cells"][index] for index, column in enumerate(visible)}
    assert by_key["station_affiliation"] == "отрасль"


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
    monkeypatch.setattr(
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: {999},
    )
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
    monkeypatch.setattr(
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: {999},
    )
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


def test_with_boilers_tabs_keep_only_station_boilers(monkeypatch):
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.fuel.services.calculation.fuel_calculation_edit_data_services as fced
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    eg_station = SimpleNamespace(id=11, numb=708, name="ТЭЦ-1", name_ext=None)
    eg_standalone = SimpleNamespace(id=99, numb=999, name="Котельные Коми", name_ext=None)
    eg_station_boiler = SimpleNamespace(id=100, numb=3595, name="ТЭЦ-11 (котельная)", name_ext=None)
    rows_in = [
        (eg_station, SimpleNamespace(numb1120=708, year_number=2017, ved=1)),
        (eg_standalone, SimpleNamespace(numb1120=999, year_number=2017, ved=1)),
        (eg_station_boiler, SimpleNamespace(numb1120=3595, year_number=2017, ved=1)),
    ]

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {"rows": rows_in, "numb1120_filter_choices": [708, 999, 3595]},
    )
    monkeypatch.setattr(fced, "_expand_fuel_param_rows_for_year_interval", lambda rows, start, end: rows)
    # Как и настоящий сборощик, возвращает блоки всех групп из rows_in — в том числе тех,
    # чьи строки уже отфильтрованы (без отбора по группам такая станция всплывёт).
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
                                                "is_composite_child": eg is eg_station_boiler,
                                                "show_composite_cluster": False,
                                            }
                                            for eg, param in rows_in
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
    # «С котельными» убирает котельные вне станции (999), «Без котельных» — все котельные.
    monkeypatch.setattr(mod, "_boiler_numbs", lambda version_id=None: {999, 3595})
    monkeypatch.setattr(mod, "_boiler_numbs_without_parent", lambda version_id=None: {999})
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(cmp, "load_fuel_indicators_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_pg_ecology_overlay_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(cmp, "load_zv_ecology_overlay_by_numb_year", lambda *a, **k: {})

    source_columns = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
    ]
    expected = {
        "pg-vse": ([708, 3595], [708, 3595]),
        "zv-vse": ([708, 3595], [708, 3595]),
        "pg-bez-kot": ([708], [708]),
        "zv-bez-kot": ([708], [708]),
    }
    for slug, page in expected.items():
        groups, choices = mod.collect_pg_groups_from_fuel(
            slug,
            start_year=2017,
            end_year=2017,
            territory_filters={},
            source_columns=source_columns,
            visible_columns=source_columns,
            digits=1,
        )
        assert [g["numb"] for g in groups] == page[0]
        assert choices == page[1]


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
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: set(),
    )
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
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: set(),
    )
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
    monkeypatch.setattr(
        mod,
        "hidden_boiler_numbs_for_sheet",
        lambda sheet_slug, version_id=None: set(),
    )
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


def test_merge_composite_groups_rolls_children_into_parent(monkeypatch):
    """Подгруппы составной станции складываются в одну строку с кодом головы."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod

    parent = SimpleNamespace(id=1, numb=69, name="Автовская ТЭЦ", main=None, comp=1)
    child_a = SimpleNamespace(id=2, numb=70, name="Автовская (90 ата)", main=69, comp=None)
    child_b = SimpleNamespace(id=3, numb=71, name="Автовская (130 ата)", main=69, comp=None)
    # MAIN заполнен, но голова — не составная станция (котельная в составе ТЭС).
    plain = SimpleNamespace(id=4, numb=708, name="ТЭЦ-1", main=None, comp=None)
    plain_boiler = SimpleNamespace(id=5, numb=720, name="ТЭЦ-1 (котельная)", main=708, comp=None)

    monkeypatch.setattr(
        mod,
        "_equipment_groups_by_numb",
        lambda numbs, version_id: {69: parent, 708: plain},
    )
    groups = [
        {"id": 70, "numb": 70, "equipment_group": child_a, "rows": []},
        {"id": 708, "numb": 708, "equipment_group": plain, "rows": []},
        {"id": 71, "numb": 71, "equipment_group": child_b, "rows": []},
        {"id": 720, "numb": 720, "equipment_group": plain_boiler, "rows": []},
    ]

    merged = mod.merge_composite_groups(groups, version_id=1)

    assert [group["numb"] for group in merged] == [69, 708, 720]
    assert merged[0]["member_numbs"] == [69, 70, 71]
    assert merged[0]["equipment_group"] is parent
    assert merged[0]["is_composite_parent"] is True
    assert merged[0]["meta"]["station_name"] == "Автовская ТЭЦ"
    # Фильтр numb1120 предлагает код головы, а не подгрупп.
    assert mod.numb_choices_with_parents([70, 71, 708, 720], merged) == [69, 708, 720]


def test_composite_filled_row_sums_subgroups_only():
    """Сводная строка: числовые статьи — сумма подгрупп, станционные — один раз."""
    from app.ecology.services.gis_tes_pg_from_fuel_services import _composite_filled_row

    columns = [
        {"key": "NAME", "numeric": False},
        {"key": "numb1120", "numeric": True},
        {"key": "Year", "numeric": True},
        {"key": "NUST", "numeric": True},
        {"key": "nust_generation", "numeric": True},
        {"key": "station_affiliation", "numeric": False},
        {"key": "GAZ_ek", "numeric": True},
    ]
    parent = ["Автовская ТЭЦ", 69, 2023, None, 328, None, Decimal("767471.9")]
    child_a = ["Автовская (90 ата)", 70, 2023, 82, 328, "отрасль", None]
    child_b = ["Автовская (130 ата)", 71, 2023, 246, 328, None, None]

    row = _composite_filled_row(parent, [child_a, child_b], columns)

    assert row[0] == "Автовская ТЭЦ"
    assert row[1] == 69
    assert row[3] == Decimal("328")
    # «Генерация» — станционный показатель: не утраивается.
    assert row[4] == 328
    assert row[5] == "отрасль"
    # У подгрупп параметров ПГ нет — остаётся значение головы.
    assert row[6] == Decimal("767471.9")


def test_collect_pg_groups_rolls_composite_subgroups(monkeypatch):
    """Страница ПГ: составная станция — одна строка с кодом головы и суммой подгрупп."""
    from app.ecology.services import gis_tes_pg_from_fuel_services as mod
    import app.fuel.services.equipment_groups.equipment_group_fuel_params_services as egfps
    import app.ecology.services.analysis_pg_param_services as aps
    import app.ecology.services.gis_tes_fuel_comparison_services as cmp
    import app.common.services.database_version_filter as dvf

    parent = SimpleNamespace(id=1, numb=69, name="Автовская ТЭЦ", name_ext=None, main=None, comp=1)
    child_a = SimpleNamespace(id=2, numb=70, name="Автовская (90 ата)", name_ext=None, main=69)
    child_b = SimpleNamespace(id=3, numb=71, name="Автовская (130 ата)", name_ext=None, main=69)
    param_a = SimpleNamespace(numb1120=70, year_number=2017, ved=2)
    param_b = SimpleNamespace(numb1120=71, year_number=2017, ved=2)

    monkeypatch.setattr(dvf, "get_current_db_version_id", lambda: 1)
    monkeypatch.setattr(
        mod, "hidden_boiler_numbs_for_sheet", lambda sheet_slug, version_id=None: set()
    )
    monkeypatch.setattr(
        mod, "_equipment_groups_by_numb", lambda numbs, version_id: {69: parent}
    )
    monkeypatch.setattr(
        egfps,
        "get_equipment_groups_with_fuel_params_data",
        lambda **kwargs: {
            "rows": [(child_a, param_a), (child_b, param_b)],
            "numb1120_filter_choices": [70, 71],
        },
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
                                            for eg, param in rows
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
    monkeypatch.setattr(
        egfps, "should_suppress_aggregate_rows_for_filters", lambda filters: False
    )
    monkeypatch.setattr(aps, "seed_missing_analysis_pg_params_from_reports", lambda *a, **k: 0)
    monkeypatch.setattr(
        cmp,
        "load_fuel_indicators_by_numb_year",
        lambda numbs, years: {
            (69, 2017): {
                "ues_id": 2,
                "ues": "ОЭС",
                "res_id": 3,
                "res_name": "РЭС",
                "station_name": "Автовская ТЭЦ",
                "ved": 0,
                "nust": 328,
                "e": 1305,
                "q": 30,
                "gaz_all_tce": Decimal("791592"),
            },
            (70, 2017): {
                "ues_id": 2,
                "ues": "ОЭС",
                "res_id": 3,
                "res_name": "РЭС",
                "station_name": "Автовская (90 ата)",
                "ved": 2,
                "q": 10,
                "gaz_all_tce": Decimal("314327.419"),
            },
            (71, 2017): {
                "ues_id": 2,
                "ues": "ОЭС",
                "res_id": 3,
                "res_name": "РЭС",
                "station_name": "Автовская (130 ата)",
                "ved": 2,
                "q": 20,
                "gaz_all_tce": Decimal("386884.574"),
            },
        },
    )
    monkeypatch.setattr(
        cmp,
        "load_pg_ecology_overlay_by_numb_year",
        lambda *a, **k: {(69, 2017): {"gas_consumption_tce": Decimal("767471.9")}},
    )
    monkeypatch.setattr(cmp, "load_station_affiliations_by_numb_year", lambda *a, **k: {})
    monkeypatch.setattr(
        cmp,
        "load_station_generation_overlay",
        lambda numbs, years: {
            "names_by_numb": {},
            "station_links_by_numb": {},
            "values_by_numb_year": {
                (70, 2017): {"nust_generation": Decimal("328")},
                (71, 2017): {"nust_generation": Decimal("328")},
            },
        },
    )

    visible = [
        {"key": "NAME", "numeric": False, "source_index": 0},
        {"key": "numb1120", "numeric": True, "source_index": 1},
        {"key": "Year", "numeric": True, "source_index": 2},
        {"key": "NUST", "numeric": True, "source_index": 3},
        {"key": "nust_generation", "numeric": True, "source_index": 4},
        {"key": "Teplo", "numeric": True, "source_index": 5},
        {"key": "GAZ_All", "numeric": True, "source_index": 6},
        {"key": "GAZ_ek", "numeric": True, "source_index": 7},
    ]
    source_columns = [dict(column) for column in visible]

    groups, choices = mod.collect_pg_groups_from_fuel(
        "pg-vse",
        start_year=2017,
        end_year=2017,
        territory_filters={},
        source_columns=source_columns,
        visible_columns=visible,
        digits=1,
    )

    assert choices == [69]
    assert [group["numb"] for group in groups] == [69]
    row = groups[0]["rows"][0]
    by_key = {column["key"]: row["cells"][index] for index, column in enumerate(visible)}
    assert by_key["NAME"] == "Автовская ТЭЦ"
    assert by_key["numb1120"] == "69"
    # Сумма подгрупп, а не собственное (сводное) значение головы.
    assert by_key["Teplo"] == "30"
    assert by_key["GAZ_All"].replace("\u00a0", " ").replace(" ", "") == "701212"
    assert by_key["nust_generation"] == "328"
    assert by_key["GAZ_ek"].replace("\u00a0", " ").replace(" ", "") == "767471,9"


