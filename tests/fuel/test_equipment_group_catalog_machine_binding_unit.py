from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.fuel.services.stations import stations_equipment_groups_services as service


@pytest.mark.parametrize(
    "bound_group, machine_type, link_type, expected",
    [
        (1, 10, None, True),
        (1, None, None, True),
        (2, 10, None, False),
        (None, 10, None, False),
        (None, None, None, False),
        (1, 10, 10, True),
        (2, 10, 10, False),
        (1, 11, 10, False),
        (None, 10, 10, True),
    ],
)
def test_explicit_group_binding_works_without_station_link_type(
    bound_group, machine_type, link_type, expected,
):
    machine = SimpleNamespace(
        id_equipment_group=machine_type,
        machine_fuel_param=SimpleNamespace(equipment_group_id=bound_group),
    )
    assert service._machine_belongs_to_fuel_equipment_group(machine, 1, link_type) is expected


@pytest.fixture
def catalog(monkeypatch):
    own = SimpleNamespace(
        id=62353, machine_number="1", id_equipment_group=1055, database_version_id=37,
        machine_fuel_param=SimpleNamespace(equipment_group_id=17280),
    )
    foreign = SimpleNamespace(
        id=62354, machine_number="2", id_equipment_group=1055, database_version_id=37,
        machine_fuel_param=SimpleNamespace(equipment_group_id=31577),
    )
    old_version = SimpleNamespace(
        id=1, machine_number="3", id_equipment_group=1055, database_version_id=20,
        machine_fuel_param=SimpleNamespace(equipment_group_id=17280),
    )
    station = SimpleNamespace(id=28379, name="Архангельская ТЭЦ", machines=[own, foreign, old_version])
    head = SimpleNamespace(
        id=17280, numb=1, name="Архангельская ТЭЦ (ТЭЦ-130 ата)", comp=1, main=None,
        database_version_id=37,
    )
    child = SimpleNamespace(
        id=31577, numb=1958, name="Архангельская ТЭЦ(тепл)", comp=None, main=1,
        database_version_id=37,
    )
    null_link = SimpleNamespace(
        station_id=station.id, station=station, database_version_id=37,
        equipment_group_type_id=None, equipment_group_type=None,
        equipment_group_links_v2=[SimpleNamespace(equipment_group=head)],
    )
    typed_link = SimpleNamespace(
        station_id=station.id, station=station, database_version_id=37,
        equipment_group_type_id=1055, equipment_group_type=SimpleNamespace(id=1055, name="type"),
        equipment_group_links_v2=[SimpleNamespace(equipment_group=child)],
    )
    head.equipment_group_links_v2 = [SimpleNamespace(equipment_group_set_station=null_link)]
    child.equipment_group_links_v2 = [SimpleNamespace(equipment_group_set_station=typed_link)]
    group_model = MagicMock()
    group_model.query.filter.return_value.options.return_value.order_by.return_value.all.return_value = [head, child]
    link_model = MagicMock()
    link_model.query.filter.return_value.filter.return_value.options.return_value.all.return_value = [null_link, typed_link]
    monkeypatch.setattr(service, "EquipmentGroup", group_model)
    monkeypatch.setattr(service, "EquipmentGroupSetStation", link_model)
    monkeypatch.setattr(service, "selectinload", MagicMock())
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: 37)
    monkeypatch.setattr(service, "_eg_station_regional_district_consistent", lambda *args: True)
    monkeypatch.setattr(service, "_station_matches_selected_territory_filters", lambda *args: True)
    monkeypatch.setattr(service, "_equipment_group_sort_key", lambda group: group.id if group else 0)
    monkeypatch.setattr(
        "app.generation.services.station_services.station_services._apply_machine_display_names",
        lambda machines: None,
    )
    return station, head, child, own, foreign, null_link, typed_link


@pytest.mark.parametrize("builder", ["build_equipment_group_blocks_from_eg_ids", "build_equipment_group_blocks_from_model"])
def test_catalog_shows_returned_machine_under_numb_one(catalog, builder):
    station, head, child, own, foreign, *_ = catalog
    args = ([head.id, child.id], [station]) if builder.endswith("from_model") else ([head.id, child.id],)
    blocks = getattr(service, builder)(*args)
    machines_by_group = {
        block["equipment_group"].numb: [
            machine.id
            for entry in block["station_entries"]
            for link in entry["links"]
            for machine in link["machines"]
        ]
        for block in blocks
    }
    assert machines_by_group == {1: [own.id], 1958: [foreign.id]}


@pytest.mark.parametrize("with_child_link", [False, True])
def test_station_tree_does_not_duplicate_returned_machine(catalog, with_child_link):
    station, head, child, own, foreign, null_link, typed_link = catalog
    if not with_child_link:
        typed_link.equipment_group_links_v2 = []
        station.machines = [own]
    tree = service.build_station_equipment_groups_v2([station], version_id=37)
    nodes = tree[station.id]["groups"]
    head_node = next(node for node in nodes if node["equipment_group"] == head)
    assert [m.id for link in head_node["links"] for m in link["machines"]] == [own.id]
    all_ids = [m.id for node in nodes for link in node["links"] for m in link["machines"]]
    assert all_ids.count(own.id) == 1
