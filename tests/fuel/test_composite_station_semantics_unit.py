# -*- coding: utf-8 -*-
"""Unit-tests: Access filter ved → FuelParam.ved; семантика составных станций."""
from types import SimpleNamespace

from app.fuel.services.adapters.access_filter_adapter import AccessFilterAdapter
from app.fuel.services.equipment_groups.composite_display_cluster_services import (
    build_display_clusters,
)
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    territorial_ids_for_equipment_group,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    COMPOSITE_PARENT_GROUP_TYPE_LABEL,
    classify_station_groups,
    equipment_group_type_display_name,
    fuel_param_ved_participates,
    is_composite_child_group,
    is_composite_parent_group,
    resolve_params_detail_level_for_year,
    should_edit_fuel_param_row,
    should_show_station_summary_for_detail_level,
)


def test_access_filter_skips_ved_in_group_expression():
    expr = AccessFilterAdapter.build_expression("(oes=3) and (ved>0)")
    assert expr is not None
    # В group-expression нет ved — иначе при компиляции тянули бы vedomstvo.
    compiled = str(expr)
    assert "vedomstvo" not in compiled.lower()


def test_access_filter_builds_ved_on_fuel_param():
    ved_expr = AccessFilterAdapter.build_ved_expression("(oes=3) and (ved>0)")
    assert ved_expr is not None
    assert AccessFilterAdapter.filter_has_ved_condition("(oes=3) and (ved>0)")
    assert not AccessFilterAdapter.filter_has_ved_condition("(oes=3)")


def test_composite_parent_child_flags():
    parent = SimpleNamespace(main=None, comp=1, niv=None, numb=100, id=1)
    child = SimpleNamespace(main=100, comp=None, niv=1, numb=101, id=2)
    assert is_composite_parent_group(parent)
    assert is_composite_child_group(child)
    assert not is_composite_parent_group(child)


def test_equipment_group_type_display_name_parent_is_station():
    parent = SimpleNamespace(main=0, comp=1)
    child = SimpleNamespace(main=100, comp=None)
    group_type = SimpleNamespace(name="ТЭЦ-130 ата")
    assert equipment_group_type_display_name(parent, group_type) == COMPOSITE_PARENT_GROUP_TYPE_LABEL
    assert equipment_group_type_display_name(parent, group_type) == "станция"
    assert equipment_group_type_display_name(child, group_type) == "ТЭЦ-130 ата"
    assert equipment_group_type_display_name(child, None) == "—"
    p, children = classify_station_groups([parent, child])
    assert p is parent
    assert children == [child]


def test_classify_no_station_fallback_for_plain_multi():
    """Несколько EG без MAIN/COMP больше не считаются составной станцией."""
    a = SimpleNamespace(main=None, comp=None, numb=1, id=10)
    b = SimpleNamespace(main=None, comp=None, numb=2, id=11)
    parent, children = classify_station_groups([a, b])
    assert parent is None
    assert children == []


def test_display_clusters_by_main():
    parent = SimpleNamespace(main=None, comp=1, numb=100, id=1, name_ext="Parent TEC")
    child = SimpleNamespace(main=100, comp=None, numb=101, id=2, name_ext="Group A")
    plain = SimpleNamespace(main=None, comp=None, numb=200, id=3, name_ext="Other")
    blocks = [
        {"equipment_group": parent, "rows": []},
        {"equipment_group": child, "rows": []},
        {"equipment_group": plain, "rows": []},
    ]
    eg_to_stations = {
        1: [(10, "Station X")],
        2: [(10, "Station X")],
        3: [(20, "Station Y")],
    }
    clusters = build_display_clusters(
        blocks, eg_to_stations, allow_station_composite_fallback=False
    )
    by_key = {c["cluster_key"]: c for c in clusters}
    assert "composite:100" in by_key
    assert by_key["composite:100"]["treat_as_composite"] is True
    assert len(by_key["composite:100"]["group_blocks"]) == 2
    assert by_key["composite:100"]["station_name"] == "Parent TEC"


def test_display_clusters_uses_parent_by_numb_for_title():
    child_a = SimpleNamespace(main=119, comp=None, numb=1383, id=2, name_ext="Child A")
    child_b = SimpleNamespace(main=119, comp=None, numb=1384, id=3, name_ext="Child B")
    parent = SimpleNamespace(main=None, comp=1, numb=119, id=1, name_ext="Владимирская ТЭЦ-2")
    blocks = [
        {"equipment_group": child_a, "rows": []},
        {"equipment_group": child_b, "rows": []},
    ]
    eg_to_stations = {
        2: [(10, "Station X")],
        3: [(10, "Station X")],
        1: [(10, "Station X")],
    }
    clusters = build_display_clusters(
        blocks,
        eg_to_stations,
        allow_station_composite_fallback=False,
        parent_by_numb={119: parent},
    )
    assert len(clusters) == 1
    c = clusters[0]
    assert c["cluster_key"] == "composite:119"
    assert c["station_name"] == "Владимирская ТЭЦ-2"
    assert c["composite_parent_eg_id"] == 1
    assert c["treat_as_composite"] is True
    assert len(c["group_blocks"]) == 2  # родитель не в rows — только дети



def test_display_clusters_lone_parent_not_composite():
    """Одиночный comp=1 без детей — не treat_as_composite и не composite-ключ."""
    parent = SimpleNamespace(main=None, comp=1, numb=1, id=1, name_ext="Arkhangelsk")
    blocks = [{"equipment_group": parent, "rows": []}]
    clusters = build_display_clusters(
        blocks, {}, allow_station_composite_fallback=False
    )
    assert len(clusters) == 1
    assert clusters[0]["treat_as_composite"] is False
    assert clusters[0]["cluster_key"] == "eg:1"
    assert not str(clusters[0]["cluster_key"]).startswith("composite:")


def test_display_clusters_lone_parent_shares_station_with_plain():
    """
    Мурманская ТЭЦ (comp=1 без детей) + Котельные на той же Station —
    один station-кластер, без дубля composite:/station:.
    """
    parent = SimpleNamespace(
        main=None, comp=1, numb=16, id=22769, name_ext="Мурманская ТЭЦ"
    )
    boiler = SimpleNamespace(
        main=None, comp=None, numb=1022, id=29026, name_ext="Котельные Южная и Восточная"
    )
    blocks = [
        {"equipment_group": parent, "rows": []},
        {"equipment_group": boiler, "rows": []},
    ]
    eg_to_stations = {
        22769: [(35738, "Мурманская ТЭЦ")],
        29026: [(35738, "Мурманская ТЭЦ")],
    }
    clusters = build_display_clusters(
        blocks, eg_to_stations, allow_station_composite_fallback=False
    )
    assert len(clusters) == 1
    c = clusters[0]
    assert c["cluster_key"] == "station:35738"
    assert c["treat_as_composite"] is False
    assert {gb["equipment_group"].id for gb in c["group_blocks"]} == {22769, 29026}


def test_enrich_puts_total_on_parent():
    from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
        enrich_station_blocks_composite_display,
    )

    parent = SimpleNamespace(main=None, comp=1, numb=100, id=1, name="Parent")
    child_a = SimpleNamespace(main=100, comp=None, numb=101, id=2, name="A")
    child_b = SimpleNamespace(main=100, comp=None, numb=102, id=3, name="B")
    station_blocks = [
        {
            "station_id": 10,
            "station_name": "Parent",
            "group_blocks": [
                {
                    "equipment_group": child_a,
                    "rows": [(child_a, SimpleNamespace(nust=10, year_number=2024, ved=1))],
                },
                {
                    "equipment_group": child_b,
                    "rows": [(child_b, SimpleNamespace(nust=20, year_number=2024, ved=2))],
                },
            ],
            "station_summary": {},
            "is_virtual": False,
            "suppress_station_summary": False,
            "composite_parent_eg_id": 1,
            "treat_as_composite": True,
        }
    ]

    def compute_summary(rows):
        total = 0
        for _eg, p in rows:
            total += getattr(p, "nust", 0) or 0
        return {"nust": total}

    enrich_station_blocks_composite_display(
        station_blocks,
        compute_summary,
        parent_by_numb={100: parent},
        fuel_params_detail_mode=False,
    )
    sb = station_blocks[0]
    assert sb["suppress_station_summary"] is True
    assert sb["station_summary"]["nust"] == 30
    assert len(sb["group_blocks"]) == 3  # parent injected
    parent_gb = sb["group_blocks"][0]
    assert parent_gb["is_composite_total_row"] is True
    assert parent_gb["use_station_summary"] is True
    assert parent_gb["equipment_group"] is parent
    assert 2024 in sb["station_summary_by_year"]
    assert sb["station_summary_by_year"][2024]["nust"] == 30


def test_station_summary_by_year_omits_year_without_participating_ved():
    """Год без строк ved>0 не должен получать сумму «за все годы»."""
    from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
        enrich_station_blocks_composite_display,
    )

    parent = SimpleNamespace(main=None, comp=1, numb=66, id=1, name="Parent")
    child = SimpleNamespace(main=66, comp=None, numb=1083, id=2, name="PGU")
    station_blocks = [
        {
            "station_id": 10,
            "station_name": "Parent",
            "group_blocks": [
                {
                    "equipment_group": child,
                    "rows": [
                        (child, SimpleNamespace(nust=360, year_number=2024, ved=2)),
                        (child, SimpleNamespace(nust=None, year_number=2025, ved=None)),
                        (child, SimpleNamespace(nust=360, year_number=2026, ved=2)),
                    ],
                },
            ],
            "station_summary": {},
            "is_virtual": False,
            "suppress_station_summary": False,
            "composite_parent_eg_id": 1,
            "treat_as_composite": True,
        }
    ]

    def compute_summary(rows):
        total = 0
        any_val = False
        for _eg, p in rows:
            v = getattr(p, "nust", None)
            if v is not None:
                total += v
                any_val = True
        return {"nust": total} if any_val else {}

    enrich_station_blocks_composite_display(
        station_blocks,
        compute_summary,
        parent_by_numb={66: parent},
        fuel_params_detail_mode=True,
    )
    by_year = station_blocks[0]["station_summary_by_year"]
    assert 2024 in by_year
    assert 2026 in by_year
    assert 2025 not in by_year
    assert by_year[2024]["nust"] == 360


def test_ved_participates():
    assert fuel_param_ved_participates(1)
    assert fuel_param_ved_participates(4)
    assert not fuel_param_ved_participates(0)
    assert not fuel_param_ved_participates(None)


def test_detail_level_by_year():
    parent_p = SimpleNamespace(ved=0)
    child_a = SimpleNamespace(ved=1)
    child_b = SimpleNamespace(ved=2)
    assert (
        resolve_params_detail_level_for_year(
            parent_param=parent_p, child_params=[child_a, child_b]
        )
        == "by_groups"
    )
    assert (
        resolve_params_detail_level_for_year(
            parent_param=SimpleNamespace(ved=1), child_params=[SimpleNamespace(ved=0)]
        )
        == "station_only"
    )


def test_edit_and_summary_rules():
    parent = SimpleNamespace(main=None, comp=1, id=1)
    child = SimpleNamespace(main=100, comp=None, id=2)
    assert should_edit_fuel_param_row(
        detail_level="by_groups",
        equipment_group=child,
        has_composite_structure=True,
    )
    assert not should_edit_fuel_param_row(
        detail_level="by_groups",
        equipment_group=parent,
        has_composite_structure=True,
    )
    assert should_edit_fuel_param_row(
        detail_level="station_only",
        equipment_group=parent,
        has_composite_structure=True,
    )
    assert should_show_station_summary_for_detail_level(
        "by_groups", participating_group_count=2
    )
    assert not should_show_station_summary_for_detail_level(
        "station_only", participating_group_count=1
    )


def test_enrich_parent_edit_allowed_like_regular_group():
    from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
        enrich_station_blocks_composite_display,
    )

    parent = SimpleNamespace(main=None, comp=1, numb=100, id=1, name="Parent")
    child = SimpleNamespace(main=100, comp=None, numb=101, id=2, name="A")
    station_blocks = [
        {
            "station_id": 10,
            "station_name": "Parent",
            "group_blocks": [
                {
                    "equipment_group": parent,
                    "rows": [
                        (parent, SimpleNamespace(id=10, year_number=2024, ved=2, e=100)),
                        (parent, SimpleNamespace(id=12, year_number=2025, ved=0, e=100)),
                    ],
                },
                {
                    "equipment_group": child,
                    "rows": [
                        (child, SimpleNamespace(id=11, year_number=2024, ved=2, e=40)),
                        (child, SimpleNamespace(id=13, year_number=2025, ved=2, e=40)),
                    ],
                },
            ],
            "station_summary": {},
            "is_virtual": False,
            "suppress_station_summary": False,
            "composite_parent_eg_id": 1,
            "treat_as_composite": True,
        }
    ]

    def compute_summary(rows):
        return {"e": sum((getattr(p, "e", 0) or 0) for _eg, p in rows)}

    enrich_station_blocks_composite_display(
        station_blocks,
        compute_summary,
        parent_by_numb={100: parent},
        fuel_params_detail_mode=True,
    )
    parent_gb = next(
        gb for gb in station_blocks[0]["group_blocks"] if gb.get("is_composite_parent")
    )
    assert parent_gb["is_composite_total_row"] is True
    assert parent_gb["edit_allowed_by_year"][2024] is True
    assert parent_gb["edit_allowed_by_year"][2025] is True


def _territory_chain(est_id=1, ues_id=311, res_id=2039):
    ues = SimpleNamespace(id=ues_id, id_energy_system_type=est_id)
    res = SimpleNamespace(id=res_id, union_energy_system=ues)
    return res


def test_child_without_res_inherits_parent_territory():
    """67/68 без РЭС не должны уходить в «Не указано» отдельно от родителя 66."""
    parent_res = _territory_chain()
    parent = SimpleNamespace(
        main=None, comp=1, numb=66, id=1, regional_energy_system=parent_res
    )
    child = SimpleNamespace(
        main=66, comp=None, numb=67, id=2, regional_energy_system=None
    )
    assert territorial_ids_for_equipment_group(
        child, parent_by_numb={66: parent}
    ) == (1, 311, 2039)
    assert territorial_ids_for_equipment_group(
        parent, parent_by_numb={66: parent}
    ) == (1, 311, 2039)


def test_child_own_res_is_not_replaced_by_parent():
    parent_res = _territory_chain(res_id=2039)
    child_res = _territory_chain(est_id=2, ues_id=20, res_id=100)
    parent = SimpleNamespace(
        main=None, comp=1, numb=66, id=1, regional_energy_system=parent_res
    )
    child = SimpleNamespace(
        main=66, comp=None, numb=67, id=2, regional_energy_system=child_res
    )
    assert territorial_ids_for_equipment_group(
        child, parent_by_numb={66: parent}
    ) == (2, 20, 100)


def test_plain_group_without_res_stays_unspecified():
    plain = SimpleNamespace(
        main=None, comp=None, numb=200, id=3, regional_energy_system=None
    )
    assert territorial_ids_for_equipment_group(plain, parent_by_numb={}) == (
        -1,
        -1,
        -1,
    )


def test_standalone_uses_obl_mapping_res_not_unspecified():
    """Калининградская ТЭЦ-1 без FK РЭС идёт в ветку по obl, не в «Не указано»."""
    ues = SimpleNamespace(id=410, id_energy_system_type=207)
    res = SimpleNamespace(id=2775, union_energy_system=ues)
    group = SimpleNamespace(
        main=None,
        comp=1,
        numb=89,
        id=29080,
        regional_energy_system=None,
        regional_district=None,
        territories_energy_external_mapping=SimpleNamespace(
            regional_district=None,
            regional_energy_system=res,
            regional_district_ref_uuid="rd-uuid",
            regional_energy_system_ref_uuid="res-uuid",
        ),
    )
    assert territorial_ids_for_equipment_group(group, parent_by_numb={}) == (
        207,
        410,
        2775,
    )


def test_standalone_uses_district_res_when_fk_empty():
    """Standalone без FK РЭС, но с субъектом — первая РЭС субъекта, не «Не указано»."""
    ues = SimpleNamespace(id=410, id_energy_system_type=207)
    res = SimpleNamespace(id=2775, union_energy_system=ues)
    rd = SimpleNamespace(id=3082, regional_energy_systems=[res])
    group = SimpleNamespace(
        main=None,
        comp=1,
        numb=88,
        id=29071,
        regional_energy_system=None,
        regional_district=rd,
        territories_energy_external_mapping=None,
    )
    assert territorial_ids_for_equipment_group(group, parent_by_numb={}) == (
        207,
        410,
        2775,
    )


def test_child_inherits_parent_obl_mapping_territory():
    """Дочерняя без РЭС наследует obl-ветку родителя, не отдельный блок «Не указано»."""
    ues = SimpleNamespace(id=311, id_energy_system_type=162)
    res = SimpleNamespace(id=2046, union_energy_system=ues)
    parent = SimpleNamespace(
        main=None,
        comp=1,
        numb=66,
        id=1,
        regional_energy_system=None,
        regional_district=None,
        territories_energy_external_mapping=SimpleNamespace(
            regional_district=None,
            regional_energy_system=res,
        ),
    )
    child = SimpleNamespace(
        main=66,
        comp=None,
        numb=67,
        id=2,
        regional_energy_system=None,
        regional_district=None,
        territories_energy_external_mapping=None,
    )
    assert territorial_ids_for_equipment_group(
        child, parent_by_numb={66: parent}
    ) == (162, 311, 2046)
