from types import SimpleNamespace

from flask import render_template
import pytest

from app.generation.services.station_services import external_code_check_services as service
from test_external_code_equipment_groups import storage, add, group
from test_external_code_cell_status_unit import app


def station(station_id, groups=(), ungrouped=(), district="Область"):
    return SimpleNamespace(
        id=station_id, name=f"Станция {station_id}", external_code=f"station-{station_id}",
        regional_district=SimpleNamespace(name=district) if district is not None else None,
        external_codes_by_version={37: f"station-{station_id}"},
        external_code_record_ids_by_version={37: station_id},
        external_code_equipment_groups=list(groups), external_code_ungrouped_machines=list(ungrouped),
        machines=[machine for node in groups for machine in node.machines] + list(ungrouped),
    )


def machine(machine_id, name=None):
    return SimpleNamespace(
        id=machine_id, external_code=f"machine-{machine_id}", machine_group="", machine_number="1",
        display_name=name or f"Турбина {machine_id}", pgu_machines=[],
        external_codes_by_version={37: f"machine-{machine_id}"},
        external_code_record_ids_by_version={37: machine_id},
    )


def node(group_id, member_ids, machines=(), code="shared-code"):
    return SimpleNamespace(
        id=group_id, name=f"Группа {group_id}", name_ext=None, numb=group_id,
        external_code=code, main=None, database_version_id=37, station_ids=tuple(member_ids),
        duplicate_code_count=1, external_codes_by_version={20: code, 37: code},
        external_code_record_ids_by_version={20: group_id + 100, 37: group_id}, machines=list(machines),
    )


def render_blocks(app, stations):
    with app.test_request_context():
        return app.jinja_env.from_string("""
            {% for station in stations %}
                {% include 'generation/stations/_external_code_display_blocks.html' %}
            {% endfor %}
        """).render(stations=stations, external_code_display_blocks=service.build_external_code_check_blocks(stations),
                    database_versions=[{"id": 20, "version_number": "ТОПЛИВО"},
                                       {"id": 37, "version_number": "РАБОЧАЯ"}])


def test_shared_group_precedes_stations_and_each_station_keeps_its_machines(app):
    first = station(1, [node(11, [1, 2], [machine(101), machine(102)])])
    second = station(2, [node(11, [1, 2], [machine(201)])])
    unrelated = station(3)
    html = render_blocks(app, [first, unrelated, second])
    assert html.index("Группа 11") < html.index("Станция 1") < html.index("Турбина 101")
    assert html.index("Турбина 102") < html.index("Станция 2") < html.index("Турбина 201")
    assert html.index("Турбина 201") < html.index("Станция 3")
    assert html.count('href="/group/11"') == 1
    assert html.count('href="/station/1"') == html.count('href="/station/2"') == 1
    assert 'href="/machine/1/101"' in html
    assert 'href="/machine/2/201"' in html
    assert 'href="/machine/1/201"' not in html
    assert "table-warning" not in html
    assert "ps-4" in html


def test_single_station_groups_keep_old_order_and_duplicate_codes_do_not_join_groups(app):
    first = station(1, [node(11, [1], [machine(101)])])
    second = station(2, [node(12, [2], [machine(201)])])
    html = render_blocks(app, [first, second])
    assert html.index("Станция 1") < html.index("Группа 11") < html.index("Турбина 101")
    assert html.index("Станция 2") < html.index("Группа 12") < html.index("Турбина 201")
    assert html.count("external-code-equipment-group-row") == 2


def test_filter_to_one_station_does_not_add_unmatched_members_and_keeps_shared_parent(app):
    selected = station(2, [node(11, [1, 2], [machine(201)])])
    html = render_blocks(app, [selected])
    assert html.index("Группа 11") < html.index("Станция 2") < html.index("Турбина 201")
    assert "Станция 1" not in html


def test_shared_groups_do_not_hide_local_groups_or_ungrouped_machines(app):
    first = station(1, [node(11, [1, 2], [machine(101)]), node(12, [1], [machine(102)])], [machine(103)])
    second = station(2, [node(11, [1, 2], [machine(201)])])
    html = render_blocks(app, [first, second])
    for machine_id in (101, 102, 103, 201):
        assert html.count(f"Турбина {machine_id}") == 1
    assert html.count('href="/group/11"') == html.count('href="/group/12"') == 1
    assert "Агрегаты без связи" in html
    assert first.external_code_equipment_groups[0].machines[0].id == 101
    assert len(first.external_code_equipment_groups) == 2


def test_multiple_shared_groups_render_separately_with_correct_machine_links(app):
    first = station(1, [node(11, [1, 2], [machine(101)]), node(12, [1, 2], [machine(102)])])
    second = station(2, [node(11, [1, 2], [machine(201)]), node(12, [1, 2], [machine(202)])])
    html = render_blocks(app, [first, second])
    assert html.index("Группа 11") < html.index("Турбина 101") < html.index("Турбина 201")
    assert html.index("Турбина 201") < html.index("Группа 12") < html.index("Турбина 102") < html.index("Турбина 202")
    for station_id, machine_id in ((1, 101), (1, 102), (2, 201), (2, 202)):
        assert html.count(f'href="/machine/{station_id}/{machine_id}"') == 1


def test_shared_group_keeps_empty_station_in_its_members(app):
    html = render_blocks(app, [station(1, [node(11, [1, 2])]), station(2, [node(11, [1, 2], [machine(201)])])])
    assert html.index("Группа 11") < html.index("Станция 1") < html.index("Станция 2")
    assert html.count("external-code-station-row") == 2


def test_attachment_loads_all_member_links_without_adding_other_station_machines(storage):
    group(storage, 11, 37, station_id=1)
    add(storage, service.EquipmentGroupSetStation, id=120, station_id=2,
        database_version_id=37, equipment_group_type_id=10)
    add(storage, service.EquipmentGroupSet, equipment_group_id=11, equipment_group_set_station_id=120)
    view = station(1)
    view.database_version_id = 37
    service._attach_equipment_groups_for_check(view, [SimpleNamespace(id=1)], [37], False, "")
    assert len(view.external_code_equipment_groups) == 1
    assert view.external_code_equipment_groups[0].station_ids == (1, 2)
    assert view.external_code_equipment_groups[0].machines == []
    assert not storage.dirty
    assert not storage.new


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("unbound_type_id", [None, 10])
def test_attachment_ignores_links_without_station_and_preserves_group_layout(storage, shared, unbound_type_id):
    group(storage, 11, 37, station_id=1)
    if shared:
        add(storage, service.EquipmentGroupSetStation, id=120, station_id=2,
            database_version_id=37, equipment_group_type_id=10)
        add(storage, service.EquipmentGroupSet, equipment_group_id=11, equipment_group_set_station_id=120)
    add(storage, service.EquipmentGroupSetStation, id=130, station_id=None,
        database_version_id=37, equipment_group_type_id=unbound_type_id)
    add(storage, service.EquipmentGroupSet, equipment_group_id=11, equipment_group_set_station_id=130)
    storage.commit()

    view = station(1)
    view.database_version_id = 37
    service._attach_equipment_groups_for_check(view, [SimpleNamespace(id=1)], [37], False, "")

    assert len(view.external_code_equipment_groups) == 1
    attached = view.external_code_equipment_groups[0]
    assert attached.station_ids == ((1, 2) if shared else (1,))
    assert attached.external_code_record_ids_by_version == {37: 11}
    blocks = service.build_external_code_check_blocks([view])[1]
    assert len(blocks) == 1
    assert blocks[0].equipment_group is (attached if shared else None)
    assert storage.get(service.EquipmentGroupSetStation, 130).station_id is None
    assert not storage.dirty
    assert not storage.new


def test_pagination_finds_shared_groups_through_versioned_station_families(storage):
    for station_id, version, code, name in ((1, 20, "first", "Первая"), (2, 20, "second", "Вторая"),
                                           (3, 37, "first", "Первая"), (4, 37, "second", "Вторая")):
        add(storage, service.Station, id=station_id, database_version_id=version, external_code=code, name=name)
    group(storage, 11, 20, station_id=1)
    add(storage, service.EquipmentGroupSetStation, id=120, station_id=2,
        database_version_id=20, equipment_group_type_id=10)
    add(storage, service.EquipmentGroupSet, equipment_group_id=11, equipment_group_set_station_id=120)
    storage.commit()
    selected = storage.query(service.Station).filter(service.Station.id.in_([3, 4])).order_by(service.Station.id).all()
    assert service.shared_equipment_group_station_ids(selected) == [{3, 4}]
    assert service.shared_equipment_group_station_ids(selected[:1]) == []
    assert not storage.dirty


@pytest.mark.parametrize("members,expected", [
    ([], [(0, 2), (2, 4), (4, 6)]),
    ([{2, 3}], [(0, 3), (3, 5), (5, 6)]),
    ([{1, 4}], [(0, 4), (4, 6)]),
    ([{1, 3}, {3, 5}], [(0, 5), (5, 6)]),
    ([{1, 99}], [(0, 2), (2, 4), (4, 6)]),
])
def test_page_ranges_do_not_split_groups_or_repeat_stations(members, expected):
    stations = [station(i, district=f"Область {i}") for i in range(1, 7)]
    ranges = service.external_code_check_page_ranges(stations, 2, members)
    assert ranges == expected
    assert [item.id for start, end in ranges for item in stations[start:end]] == list(range(1, 7))


def test_page_ranges_preserve_district_boundaries_and_close_group_chains():
    stations = [station(i, district="Первая" if i <= 3 else "Вторая" if i <= 5 else "Третья") for i in range(1, 7)]
    assert service.external_code_check_page_ranges(stations, 2, []) == [(0, 3), (3, 5), (5, 6)]
    assert service.external_code_check_page_ranges(stations, 2, [{3, 4}]) == [(0, 5), (5, 6)]
    assert service.external_code_check_page_ranges([], 10, []) == []
    assert service.external_code_check_page_ranges([station(1, district=None), station(2, district=None)], 1, []) == [(0, 2)]
    with pytest.raises(ValueError):
        service.external_code_check_page_ranges(stations, 0, [])
