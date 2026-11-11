from decimal import Decimal
from threading import Lock
from types import SimpleNamespace

import pytest

from app.energy_consumption.services import energy_consumption_summary_services
from app.power_demand.services import demand_summary_services


@pytest.mark.parametrize("service, parameter, field", [
    (energy_consumption_summary_services, "energy_consumption_mln_kvt_ch", "energy_consumption_mln_kvt_ch"),
    (demand_summary_services, "max_power", "max_power_consumption_mw"),
], ids=["consumption", "demand"])
@pytest.mark.parametrize("summary_kind", ["ez", "oes"])
@pytest.mark.parametrize("selection", ["parent", "res", "both", "none"])
def test_territory_summary_keeps_demand_rows_and_source_tree(
    monkeypatch, service, parameter, field, summary_kind, selection
):
    # ORM relationships can reach session infrastructure that cannot be deep-copied.
    demand_row = SimpleNamespace(
        id=101,
        year_number=2024,
        **{field: Decimal("123.4")},
        related_state=SimpleNamespace(lock=Lock()),
    )
    parent_ids = (
        {"id_energy_zone": 7}
        if summary_kind == "ez"
        else {"id_union_energy_system": 7}
    )
    parameters = ((parameter, "Value"),)
    children = [
        service.SummaryEntity(
            label=f"RES {res_id}",
            depth=1,
            parameters=parameters,
            demand_rows=[demand_row],
            id_regional_energy_system=res_id,
            **parent_ids,
        )
        for res_id in (11, 12)
    ]
    parent = service.SummaryEntity(
        label="Parent",
        depth=0,
        parameters=parameters,
        demand_rows=[demand_row],
        entity_kind="group",
        children=children,
        **parent_ids,
    )
    entities = [parent]
    monkeypatch.setattr(service, "_prepare_summary_demand_bulk_load", lambda: None)
    monkeypatch.setattr(service, f"_build_{summary_kind}_raw_entities", lambda **kw: entities)
    if service is energy_consumption_summary_services:
        monkeypatch.setattr(service, "_gaes_charge_rows_for_entity", lambda *a, **kw: [])
        hooks = (
            "inject_siberia_energy_zone_summary_rows",
            "inject_east_energy_zone_summary_rows",
            "apply_chukotka_chersky_reference_summary_rows",
            "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        )
    else:
        hooks = ("_finalize_ez_summary_context", "_finalize_oes_summary_context", "_build_tites_entity")
    for name in hooks:
        monkeypatch.setattr(service, name, lambda *a, **kw: None)

    # Keep real pruning and flattening; capture their boundary to check row identity.
    flattened_entities = []
    flatten = service._flatten_entities

    def capture_flatten(nodes, *args, **kwargs):
        flattened_entities.extend(nodes)
        return flatten(nodes, *args, **kwargs)

    monkeypatch.setattr(service, "_flatten_entities", capture_flatten)
    selected_parents = [7] if selection in ("parent", "both") else []
    selected_res = [11] if selection in ("res", "both") else []
    if summary_kind == "ez":
        build = service.build_energy_zones_summary_context
        territory = {"ez_territory_ordered": (selected_parents, selected_res)}
    else:
        build = service.build_oes_summary_context
        territory = {"oes_territory_ordered": (selected_parents, selected_res, [], [])}

    # The unfiltered path normally flattens inside _build_summary_context.
    def build_context(**kwargs):
        return {
            "summary_rows": service._flatten_entities(kwargs["entities"], [2024], 1),
            "years": [2024],
        }

    monkeypatch.setattr(service, "_build_summary_context", build_context)
    context = build(
        1, start_year=2024, end_year=2024, filter_year_list=[2024], **territory
    )

    expected_labels = {
        "parent": ["Parent", "RES 11", "RES 12"],
        "res": ["RES 11"] if summary_kind == "ez" else ["Parent", "RES 11"],
        "both": ["Parent", "RES 11"],
        "none": ["Parent", "RES 11", "RES 12"],
    }[selection]
    rows = context["summary_rows"]
    assert [row["entity_label"] for row in rows] == expected_labels
    assert all(
        energy_consumption_summary_services._raw_year_values_from_summary_row(row, [2024])
        == {2024: Decimal("123.4")}
        for row in rows
    )
    assert all(row["year_row_ids"] == [101] for row in rows)

    def assert_row_identity(nodes):
        for node in nodes:
            assert node.demand_rows[0] is demand_row
            assert_row_identity(node.children)

    assert_row_identity(flattened_entities)
    assert entities == [parent]
    assert parent.children is children
    assert [child.id_regional_energy_system for child in children] == [11, 12]
    assert [child.depth for child in children] == [1, 1]
    assert_row_identity(entities)
    assert getattr(demand_row, field) == Decimal("123.4")
