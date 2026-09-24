# -*- coding: utf-8 -*-
"""Копирование/удаление версии затрагивает данные всех модулей."""

from __future__ import annotations

from unittest.mock import MagicMock

from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_POWER_DEMAND, SCHEMA_REFDATA
from app.common.services import database_version_module_sync as sync


def test_topo_sort_puts_parents_before_children() -> None:
    tables = [("a", "t1"), ("a", "t2"), ("a", "t3")]
    fks = {
        ("a", "t3"): [("parent_id", "a", "t2")],
        ("a", "t2"): [("parent_id", "a", "t1")],
    }
    ordered = sync.topo_sort_tables(tables, fks)
    assert ordered.index(("a", "t1")) < ordered.index(("a", "t2"))
    assert ordered.index(("a", "t2")) < ordered.index(("a", "t3"))


def test_topo_sort_ignores_self_fk() -> None:
    tables = [("a", "nodes")]
    fks = {("a", "nodes"): [("parent_id", "a", "nodes")]}
    assert sync.topo_sort_tables(tables, fks) == tables


def test_copy_filter_copies_equipment_groups_but_not_yearly_params() -> None:
    versioned = [
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_fuel_param"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_natural_fuel"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_specific_fuel_cost"),
    ]
    result = sync.filter_versioned_tables_for_copy(versioned, copy_mode="full")
    assert (SCHEMA_FUEL, "gs_fue_equipment_groups") in result
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations") in result
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_fuel_param") not in result
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_natural_fuel") not in result
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_specific_fuel_cost") not in result


def test_copy_filter_skips_core_years_history_and_registry() -> None:
    versioned = [
        (SCHEMA_GENERATION, "gs_gen_stations"),
        (SCHEMA_GENERATION, "gs_gen_pgu_machine_names"),
        (SCHEMA_REFDATA, "gs_sys_years"),
        (SCHEMA_REFDATA, "gs_sys_refdata_entities"),
        (SCHEMA_REFDATA, "gs_database_versions"),
        (SCHEMA_REFDATA, "gs_sys_perimeter_variants"),
        (SCHEMA_POWER_DEMAND, "gs_pd_federal_district_demand_params"),
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
    ]
    result = sync.filter_versioned_tables_for_copy(versioned, copy_mode="full")
    assert (SCHEMA_GENERATION, "gs_gen_pgu_machine_names") in result
    assert (SCHEMA_POWER_DEMAND, "gs_pd_federal_district_demand_params") in result
    assert (SCHEMA_FUEL, "gs_fue_equipment_groups") in result
    assert (SCHEMA_GENERATION, "gs_gen_stations") not in result
    assert (SCHEMA_REFDATA, "gs_sys_years") not in result
    assert (SCHEMA_REFDATA, "gs_sys_refdata_entities") not in result
    assert (SCHEMA_REFDATA, "gs_sys_perimeter_variants") not in result


def test_copy_filter_refdata_only_keeps_refdata_extras() -> None:
    versioned = [
        (SCHEMA_REFDATA, "gs_sys_departments"),
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_POWER_DEMAND, "gs_pd_federal_district_demand_params"),
    ]
    result = sync.filter_versioned_tables_for_copy(versioned, copy_mode="refdata_only")
    assert result == [(SCHEMA_REFDATA, "gs_sys_departments")]


def test_delete_filter_keeps_years_and_history_skips_shared() -> None:
    versioned = [
        (SCHEMA_REFDATA, "gs_sys_years"),
        (SCHEMA_REFDATA, "gs_sys_refdata_entities"),
        (SCHEMA_REFDATA, "gs_sys_perimeter_variants"),
        (SCHEMA_REFDATA, "gs_database_versions"),
        (SCHEMA_POWER_DEMAND, "gs_pd_federal_district_demand_params"),
        (SCHEMA_GENERATION, "gs_gen_stations"),
    ]
    result = sync.filter_versioned_tables_for_delete(versioned)
    assert (SCHEMA_REFDATA, "gs_sys_years") in result
    assert (SCHEMA_REFDATA, "gs_sys_refdata_entities") in result
    assert (SCHEMA_POWER_DEMAND, "gs_pd_federal_district_demand_params") in result
    assert (SCHEMA_GENERATION, "gs_gen_stations") in result
    assert (SCHEMA_REFDATA, "gs_sys_perimeter_variants") not in result
    assert (SCHEMA_REFDATA, "gs_database_versions") not in result


def test_discover_satellites_of_versioned_parents() -> None:
    versioned = [
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
    ]
    fks = {
        (SCHEMA_FUEL, "gs_fue_equipment_group_sets"): [
            ("equipment_group_id", SCHEMA_FUEL, "gs_fue_equipment_groups"),
            (
                "equipment_group_set_station_id",
                SCHEMA_FUEL,
                "gs_fue_equipment_group_type_stations",
            ),
        ],
        (SCHEMA_FUEL, "gs_fue_equipment_groups"): [
            ("regional_district_id", SCHEMA_REFDATA, "gs_sys_regional_districts"),
        ],
    }
    satellites = sync.discover_satellite_tables(versioned, fks)
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_sets") in satellites
    assert (SCHEMA_FUEL, "gs_fue_equipment_groups") not in satellites


def test_copy_remaining_copies_module_tables_in_fk_order(monkeypatch) -> None:
    copied: list[tuple[str, str]] = []

    monkeypatch.setattr(
        sync,
        "list_versioned_tables",
        lambda: [
            (SCHEMA_FUEL, "gs_fue_equipment_groups"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_fuel_param"),
        ],
    )
    monkeypatch.setattr(
        sync,
        "list_single_column_fks",
        lambda: {
            (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"): [
                ("station_id", SCHEMA_GENERATION, "gs_gen_stations")
            ]
        },
    )
    monkeypatch.setattr(
        sync,
        "list_fk_dependencies",
        lambda: {
            (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"): [
                ("station_id", SCHEMA_GENERATION, "gs_gen_stations")
            ]
        },
    )

    def _fake_copy_versioned(schema, table, *args, **kwargs):
        copied.append((schema, table))
        return (2, {1: 10})

    monkeypatch.setattr(sync, "_copy_versioned_table", _fake_copy_versioned)
    monkeypatch.setattr(sync, "_ensure_mapping_temps", lambda *a, **k: None)
    monkeypatch.setattr(sync, "log_to_db", lambda *a, **k: None)
    monkeypatch.setattr(sync, "_logger", lambda: MagicMock())

    nested = MagicMock()
    nested.__enter__ = MagicMock(return_value=None)
    nested.__exit__ = MagicMock(return_value=False)
    fake_session = MagicMock()
    fake_session.begin_nested.return_value = nested
    monkeypatch.setattr(sync.db, "session", fake_session)

    total = sync.copy_remaining_module_tables(1, 2, "tester", {}, copy_mode="full")

    assert copied == [
        (SCHEMA_FUEL, "gs_fue_equipment_groups"),
        (SCHEMA_FUEL, "gs_fue_equipment_group_type_stations"),
    ]
    assert (SCHEMA_FUEL, "gs_fue_equipment_group_fuel_param") not in copied
    assert total == 4


def test_delete_all_modules_deletes_satellites_before_parents(monkeypatch) -> None:
    deleted: list[tuple[str, str]] = []

    monkeypatch.setattr(
        sync,
        "list_versioned_tables",
        lambda: [(SCHEMA_FUEL, "gs_fue_equipment_groups")],
    )
    monkeypatch.setattr(
        sync,
        "list_single_column_fks",
        lambda: {
            (SCHEMA_FUEL, "gs_fue_equipment_group_sets"): [
                ("equipment_group_id", SCHEMA_FUEL, "gs_fue_equipment_groups")
            ]
        },
    )
    monkeypatch.setattr(
        sync,
        "list_fk_dependencies",
        lambda: {
            (SCHEMA_FUEL, "gs_fue_equipment_group_sets"): [
                ("equipment_group_id", SCHEMA_FUEL, "gs_fue_equipment_groups")
            ]
        },
    )
    monkeypatch.setattr(
        sync,
        "_delete_from_versioned_table",
        lambda schema, table, version_id: deleted.append((schema, table)) or 3,
    )
    monkeypatch.setattr(
        sync,
        "_delete_from_satellite_table",
        lambda schema, table, parent_fks, version_id: deleted.append((schema, table)) or 1,
    )
    monkeypatch.setattr(sync, "log_to_db", lambda *a, **k: None)
    monkeypatch.setattr(sync, "_logger", lambda: MagicMock())

    total = sync.delete_all_module_data_for_version(7, "tester")

    assert deleted[0] == (SCHEMA_FUEL, "gs_fue_equipment_group_sets")
    assert deleted[1] == (SCHEMA_FUEL, "gs_fue_equipment_groups")
    assert total == 4
