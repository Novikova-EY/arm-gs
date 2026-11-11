from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from app.generation.services.station_services import external_code_check_services as service
from app.generation.services.station_services.filters_services import build_external_code_sql_filter


@pytest.fixture
def storage(monkeypatch):
    for module in (
        "app.power_demand.models", "app.economics.models", "app.electrical_intensity.models",
        "app.energy_consumption.models", "app.energy_balance.models", "app.territories.models",
        "app.ecology.models", "app.rational_structure.models",
    ):
        import_module(module)
    engine = create_engine("sqlite://")
    models = (
        service.Station, service.Machine, service.EquipmentGroup,
        service.EquipmentGroupSetStation, service.EquipmentGroupSet, service.MachineFuelParam,
        service.DatabaseVersion, service.RegionalDistrict, service.GenCompany,
    )
    with engine.begin() as connection:
        for schema in ("gs_gen", "gs_fue", "gs_sys"):
            connection.exec_driver_sql(f"ATTACH DATABASE ':memory:' AS {schema}")
        for model in models:
            model.__table__.create(connection)
    app = Flask(__name__)
    app.secret_key = "test"
    with Session(engine) as session, app.test_request_context():
        monkeypatch.setattr(service, "db", SimpleNamespace(session=session, func=func))
        yield session
    engine.dispose()


def add(storage, model, **values):
    if "version" in model.__table__.c:
        values.setdefault("version", 1)
    storage.execute(model.__table__.insert().values(**values))


def group(storage, group_id, version, code="group-code", numb=100, station_id=None, type_id=10, name="Группа 1"):
    add(storage, service.EquipmentGroup, id=group_id, database_version_id=version,
        external_code=code, numb=numb, name=name)
    if station_id is not None:
        link_id = group_id * 10
        add(storage, service.EquipmentGroupSetStation, id=link_id, station_id=station_id,
            database_version_id=version, equipment_group_type_id=type_id)
        add(storage, service.EquipmentGroupSet, equipment_group_id=group_id,
            equipment_group_set_station_id=link_id)


def station_view(machines=()):
    return SimpleNamespace(id=2, name="Станция", external_code="station-code", database_version_id=2,
                           regional_district=None, machines=list(machines),
                           external_codes_by_version={2: "station-code"},
                           external_code_record_ids_by_version={2: 2}, external_code_mismatch=False)


def attach(station, identity_code_only=False, code_filter=""):
    service._attach_equipment_groups_for_check(
        station, [SimpleNamespace(id=1), SimpleNamespace(id=2)], [1, 2, 3], identity_code_only, code_filter,
    )
    return station.external_code_equipment_groups


def test_groups_compare_versions_and_preserve_missing_cells_without_writing(storage):
    group(storage, 11, 1, station_id=1)
    group(storage, 22, 2, station_id=2)
    storage.commit()
    nodes = attach(station_view())
    assert len(nodes) == 1
    assert nodes[0].id == 22
    assert nodes[0].external_code == "group-code"
    assert nodes[0].external_codes_by_version == {1: "group-code", 2: "group-code", 3: ""}
    assert nodes[0].external_code_record_ids_by_version == {1: 11, 2: 22, 3: None}
    assert nodes[0].external_code_mismatch is True
    assert not storage.dirty
    assert not storage.new


def test_public_attachment_includes_group_codes_and_leaves_data_unchanged(storage, monkeypatch):
    for station_id in (1, 2):
        add(storage, service.Station, id=station_id, database_version_id=station_id,
            name="Станция", external_code="station-code")
        group(storage, station_id * 11, station_id, station_id=station_id)
    storage.commit()
    station = station_view()
    family = storage.query(service.Station).order_by(service.Station.id).all()
    monkeypatch.setattr(service, "_station_family_for_check", lambda *args, **kwargs: family)
    service.attach_external_codes_by_version([station], [{"id": 1}, {"id": 2}])
    assert station.external_code_record_ids_by_version == {1: 1, 2: 2}
    assert station.external_code_equipment_groups[0].external_code_record_ids_by_version == {1: 11, 2: 22}
    assert station.external_code_equipment_groups[0].external_code_mismatch is False
    assert not storage.dirty


def test_uuid_station_selection_displays_server_group_once(storage, monkeypatch):
    from app.generation.services.station_services import station_services
    from app.common.services import database_version_filter

    monkeypatch.setattr(station_services, "db", SimpleNamespace(session=storage, func=func))
    monkeypatch.setattr(station_services, "get_current_year", lambda: 2026)
    monkeypatch.setattr(database_version_filter, "get_current_db_version_id", lambda: 37)
    for station_id, version, group_id in ((7524, 20, 28875), (29560, 37, 29239)):
        add(storage, service.Station, id=station_id, database_version_id=version,
            name="Омская ТЭЦ-3", external_code="dd2d4db3-8e89-5599-8ad7-eb7f8ecf126e")
        group(storage, group_id, version, code="bfe5a284-dd74-5dc1-9e44-4a2cc907c4c2",
              numb=587, station_id=station_id, name="Омская ТЭЦ-3")
    storage.commit()
    result = station_services.get_stations_list(
        return_ids_only=True, external_code_check=True,
        external_code_filter="bfe5a284-dd74-5dc1-9e44-4a2cc907c4c2",
    )
    assert result["total_count"] == 1
    assert result["station_ids"] == [29560]
    station = SimpleNamespace(id=29560, database_version_id=37, machines=[])
    service._attach_equipment_groups_for_check(
        station, storage.query(service.Station).all(), [20, 37], True,
        "bfe5a284-dd74-5dc1-9e44-4a2cc907c4c2",
    )
    assert len(station.external_code_equipment_groups) == 1
    assert station.external_code_equipment_groups[0].external_code_record_ids_by_version == {
        20: 28875, 37: 29239,
    }
    assert not storage.dirty
    assert not storage.new


def test_legacy_number_matches_different_codes_but_uuid_search_does_not(storage):
    group(storage, 11, 1, code="old-code", station_id=1)
    group(storage, 22, 2, code="new-code", station_id=2)
    nodes = attach(station_view())
    assert len(nodes) == 1
    assert nodes[0].external_codes_by_version[1] == "old-code"
    assert nodes[0].external_codes_by_version[2] == "new-code"
    assert nodes[0].external_code_mismatch is True
    nodes = attach(station_view(), identity_code_only=True, code_filter="old-code")
    assert len(nodes) == 1
    assert nodes[0].external_code_record_ids_by_version[2] is None


def test_group_name_fallback_is_limited_to_same_station_family(storage):
    group(storage, 11, 1, code="old-code", numb=None, station_id=1)
    group(storage, 22, 2, code="new-code", numb=None, station_id=2)
    group(storage, 99, 3, code="other-station", numb=None, station_id=99)
    nodes = attach(station_view())
    assert len(nodes) == 1
    assert nodes[0].external_code_record_ids_by_version == {1: 11, 2: 22, 3: None}


def test_groups_only_in_another_version_and_without_machines_remain_visible(storage):
    group(storage, 11, 1, station_id=1)
    group(storage, 99, 2, code="other", numb=999, station_id=99)
    nodes = attach(station_view())
    assert len(nodes) == 1
    assert nodes[0].id == 11
    assert nodes[0].external_code_record_ids_by_version[2] is None
    assert nodes[0].machines == []


def test_duplicate_codes_in_one_version_remain_separate_and_ambiguous_matches_are_empty(storage):
    group(storage, 11, 1, station_id=1)
    group(storage, 12, 1, station_id=1, type_id=11)
    group(storage, 22, 2, station_id=2)
    nodes = attach(station_view())
    current = next(node for node in nodes if node.id == 22)
    assert current.external_code_record_ids_by_version[1] is None
    assert {node.id for node in nodes} == {11, 12, 22}
    assert {node.external_code_record_ids_by_version[1] for node in nodes} == {11, 12, None}
    assert [node.external_code_record_ids_by_version[2] for node in nodes].count(22) == 1
    assert {node.id for node in nodes if node.duplicate_code_count == 2} == {11, 12}


@pytest.mark.parametrize("identity_code_only", [False, True])
def test_legacy_duplicates_are_excluded_without_losing_named_records_or_machines(storage, identity_code_only):
    group(storage, 11, None, station_id=1)
    group(storage, 12, None, station_id=1, type_id=11)
    group(storage, 22, 2, station_id=2)
    group(storage, 33, 3, station_id=3)
    machine = SimpleNamespace(id=100, database_version_id=2, id_station=2, id_equipment_group=10,
                              machine_fuel_param=SimpleNamespace(equipment_group_id=22))
    station = station_view([machine])
    service._attach_equipment_groups_for_check(
        station, [SimpleNamespace(id=i) for i in (1, 2, 3)], [2, 3], identity_code_only, "",
    )
    nodes = station.external_code_equipment_groups
    assert len(nodes) == 1
    current = nodes[0]
    assert current.id == 22
    assert current.external_code_record_ids_by_version == {2: 22, 3: 33}
    assert current.duplicate_code_count == 1
    assert storage.query(service.EquipmentGroup).count() == 4
    assert current.machines == [machine]
    assert station.external_code_ungrouped_machines == []
    assert not storage.dirty
    assert not storage.new


def test_legacy_rows_are_not_rendered_and_named_cells_appear_once(storage):
    group(storage, 11, None, station_id=1)
    group(storage, 12, None, station_id=1, type_id=11)
    group(storage, 22, 2, station_id=2)
    station = station_view()
    service._attach_equipment_groups_for_check(
        station, [SimpleNamespace(id=1), SimpleNamespace(id=2)], [2], False, "",
    )
    templates = Path(__file__).resolve().parents[2] / "app/templates"
    app = Flask(__name__, template_folder=str(templates))
    app.add_url_rule("/station/<int:station_id>", "station_bp.station_details", lambda: "")
    app.add_url_rule("/group/<int:equipment_group_id>", "fuel_bp.equipment_group_edit", lambda: "")
    app.add_url_rule("/transfer/page", "fuel_bp.equipment_group_binding_transfer_page", lambda: "")
    with app.test_request_context():
        html = render_template(
            "generation/stations/external_code_station_rows.html", station=station,
            database_versions=[{"id": 2, "version_number": "Target"}],
        )
    assert html.count('data-record-id="22"') == 1
    assert 'data-record-id="11"' not in html
    assert 'data-record-id="12"' not in html
    assert "external-code-duplicate-note" not in html
    assert "Без версии" not in html
    assert "destination_version_id=None" not in html
    assert 'Перенести группу и связи в «Без версии»' not in html


def test_machines_use_catalog_binding_rules_and_unassigned_machines_are_preserved(storage):
    group(storage, 22, 2, station_id=2)
    group(storage, 23, 2, code="second-group", numb=101, station_id=2, type_id=11)
    machines = [
        SimpleNamespace(id=1, database_version_id=2, id_station=2, id_equipment_group=10,
                        machine_fuel_param=SimpleNamespace(equipment_group_id=22)),
        SimpleNamespace(id=2, database_version_id=2, id_station=2, id_equipment_group=10,
                        machine_fuel_param=SimpleNamespace(equipment_group_id=23)),
        SimpleNamespace(id=3, database_version_id=2, id_station=2, id_equipment_group=11,
                        machine_fuel_param=SimpleNamespace(equipment_group_id=None)),
        SimpleNamespace(id=4, database_version_id=2, id_station=2, id_equipment_group=None,
                        machine_fuel_param=None),
    ]
    station = station_view(machines)
    nodes = attach(station)
    assert {node.id: [m.id for m in node.machines] for node in nodes} == {22: [1], 23: [3]}
    assert [m.id for m in station.external_code_ungrouped_machines] == [2, 4]
    nodes = attach(station, identity_code_only=True, code_filter="machine-code")
    assert {node.id for node in nodes} == {22, 23}


def test_explicit_group_binding_works_when_station_link_has_no_type(storage):
    group(storage, 22, 2, station_id=2, type_id=None)
    machine = SimpleNamespace(id=1, database_version_id=2, id_station=2, id_equipment_group=None,
                              machine_fuel_param=SimpleNamespace(equipment_group_id=22))
    station = station_view([machine])
    nodes = attach(station)
    assert nodes[0].machines == [machine]
    assert station.external_code_ungrouped_machines == []


def test_machine_attachment_loads_type_and_explicit_group_without_fuel_param_dependency(storage):
    add(storage, service.Station, id=2, name="Станция", external_code="station-code", database_version_id=2)
    for machine_id in (1, 2):
        add(storage, service.Machine, id=machine_id, external_code=f"machine-{machine_id}",
            machine_number=str(machine_id), machine_name="Турбина", id_station=2,
            id_equipment_group=10, database_version_id=2)
    add(storage, service.MachineFuelParam, machine_id=1, equipment_group_id=22)
    storage.commit()
    station = storage.get(service.Station, 2)
    service.attach_machines_for_external_code_check([station])
    assert len(station.machines) == 2
    assert station.machines[0].id_equipment_group == 10
    assert station.machines[0].machine_fuel_param.equipment_group_id == 22
    assert station.machines[1].machine_fuel_param.equipment_group_id is None
    assert not storage.dirty


def test_uuid_filter_finds_station_through_group_only_on_check_page(storage):
    for station_id in (1, 2):
        add(storage, service.Station, id=station_id, database_version_id=2,
            name=f"Station {station_id}", external_code=f"station-{station_id}")
    group(storage, 22, 2, code="target-code", station_id=2)
    condition = build_external_code_sql_filter({"external_code_filter": "target", "external_code_check": True})
    assert storage.query(service.Station.id).filter(condition).all() == [(2,)]
    usual_condition = build_external_code_sql_filter({"external_code_filter": "target"})
    assert storage.query(service.Station.id).filter(usual_condition).all() == []


def test_groups_only_without_version_are_excluded_even_with_named_station_link(storage):
    group(storage, 11, None, station_id=2)
    assert attach(station_view()) == []
    assert storage.query(service.EquipmentGroup).count() == 1


@pytest.mark.parametrize("entity", ["machine", "group"])
def test_uuid_search_ignores_unversioned_children_of_named_station(storage, entity):
    add(storage, service.Station, id=2, database_version_id=2, name="Station", external_code="station-code")
    if entity == "machine":
        add(storage, service.Machine, id=11, id_station=2, database_version_id=None,
            external_code="legacy-code", machine_number="1", machine_name="Turbine")
    else:
        group(storage, 11, None, code="legacy-code", station_id=2)
    condition = build_external_code_sql_filter({"external_code_filter": "legacy-code", "external_code_check": True})
    assert storage.query(service.Station.id).filter(condition).all() == []


def test_machine_attachment_excludes_unversioned_machines_without_deleting(storage):
    add(storage, service.Station, id=2, database_version_id=2, name="Station", external_code="station-code")
    for machine_id, version in ((1, None), (2, 2)):
        add(storage, service.Machine, id=machine_id, id_station=2, database_version_id=version,
            external_code="machine-code", machine_number="1", machine_name="Turbine")
    storage.commit()
    station = storage.get(service.Station, 2)
    service.attach_machines_for_external_code_check([station])
    assert [machine.id for machine in station.machines] == [2]
    assert storage.query(service.Machine).count() == 2
    assert not storage.dirty


def test_group_external_code_can_be_updated_in_its_own_version(storage):
    group(storage, 11, 1, code="shared-code")
    group(storage, 22, 2, code="old-code")
    storage.commit()
    result = service.update_external_codes_from_check_page([
        {"entity_type": "equipment_group", "record_id": 22, "new_external_code": " shared-code "},
    ])
    assert result["ok"] is True
    assert result["updated"] == 1
    assert storage.get(service.EquipmentGroup, 22).external_code == "shared-code"
    assert storage.get(service.EquipmentGroup, 11).external_code == "shared-code"


def test_group_duplicate_code_rejects_whole_batch(storage):
    group(storage, 22, 2, code="old-code")
    group(storage, 23, 2, code="used-code")
    storage.commit()
    result = service.update_external_codes_from_check_page([
        {"entity_type": "equipment_group", "record_id": 22, "new_external_code": "unused-code"},
        {"entity_type": "equipment_group", "record_id": 22, "new_external_code": "used-code"},
    ])
    assert result["ok"] is False
    assert result["updated"] == 0
    assert storage.get(service.EquipmentGroup, 22).external_code == "old-code"


def test_station_rows_render_colored_group_before_its_machines(storage):
    group(storage, 22, 2, station_id=2)
    machine = SimpleNamespace(
        id=1, database_version_id=2, id_station=2, id_equipment_group=10,
        machine_fuel_param=SimpleNamespace(equipment_group_id=22), machine_group="", machine_number="1",
        pgu_machines=[], display_name="Турбина", machine_name="Турбина",
        external_codes_by_version={1: "machine-code"}, external_code_record_ids_by_version={1: 1},
        external_code="machine-code", external_code_mismatch=False,
    )
    station = station_view([machine])
    attach(station)
    templates = Path(__file__).resolve().parents[2] / "app/templates"
    app = Flask(__name__, template_folder=str(templates))
    app.add_url_rule("/station/<int:station_id>", "station_bp.station_details", lambda: "")
    app.add_url_rule("/machine/<int:station_id>/<int:machine_id>", "station_bp.machine_details", lambda: "")
    app.add_url_rule("/group/<int:equipment_group_id>", "fuel_bp.equipment_group_edit", lambda: "")
    app.add_url_rule("/transfer/page", "fuel_bp.equipment_group_binding_transfer_page", lambda: "")
    with app.test_request_context():
        html = render_template("generation/stations/external_code_station_rows.html", station=station,
                               database_versions=[{"id": 1, "version_number": "Source"}, {"id": 2, "version_number": "Target"}])
    assert html.index("external-code-station-row") < html.index("external-code-equipment-group-row") < html.index("external-code-machine-row")
    assert 'href="/group/22"' in html
    assert 'data-entity-type="equipment_group"' in html
    assert 'data-record-id="22"' in html
    assert "table-warning" not in html
    assert "external-code-missing" in html
    assert html.count("external-code-machine-row") == 1
    assert '/transfer/page?source_version_id=2&amp;destination_version_id=1&amp;group_id=22&amp;create_missing=1' in html
    assert 'Перенести группу и связи в «Source»' in html
    assert 'Перенести группу и связи в «Target»' not in html


def test_version_columns_exclude_null_without_creating_database_version(storage, monkeypatch):
    model = service.DatabaseVersion
    add(storage, model, id=2, version_number="Target")
    add(storage, model, id=1, version_number="Source")
    storage.commit()
    monkeypatch.setattr(service, "DatabaseVersion", SimpleNamespace(
        query=storage.query(model), id=model.id,
    ))
    versions = service.get_database_versions_for_check()
    assert versions == [
        {"id": 1, "version_number": "Source"},
        {"id": 2, "version_number": "Target"},
    ]
    assert storage.query(model).count() == 2
    assert not storage.new


def test_unversioned_records_are_excluded_from_cells_and_code_maps(storage):
    for station_id, version in ((1, None), (2, 2)):
        add(storage, service.Station, id=station_id, name="Станция", database_version_id=version,
            external_code="station-code")
        add(storage, service.Machine, id=station_id, id_station=station_id, database_version_id=version,
            external_code="machine-code", machine_number="1", machine_name="Турбина")
        group(storage, station_id * 11, version, station_id=station_id)
    storage.commit()
    station = storage.get(service.Station, 2)
    service.attach_machines_for_external_code_check([station])
    station_map, machine_map = service.attach_external_codes_by_version([station], [{"id": None}, {"id": 2}])
    assert station.external_codes_by_version == {2: "station-code"}
    assert station.external_code_record_ids_by_version == {2: 2}
    assert station.machines[0].external_code_record_ids_by_version == {2: 2}
    assert station.external_code_equipment_groups[0].external_code_record_ids_by_version == {2: 22}
    assert station_map == {"station-code": {2: "station-code"}}
    assert machine_map == {"machine-code": {2: "machine-code"}}
    assert not station.external_code_mismatch
    assert not station.machines[0].external_code_mismatch
    assert not storage.dirty


def test_station_only_without_version_is_not_found_by_uuid(storage):
    add(storage, service.Station, id=1, name="Станция", external_code="legacy-code", database_version_id=None)
    storage.commit()
    condition = build_external_code_sql_filter({"external_code_filter": "legacy-code", "external_code_check": True})
    assert storage.query(service.Station.id).filter(condition).all() == []
    usual = build_external_code_sql_filter({"external_code_filter": "legacy-code"})
    assert storage.query(service.Station.id).filter(usual).all() == [(1,)]


@pytest.mark.parametrize(("codes", "expected"), [
    ({None: "", 1: "code", 2: "code"}, False),
    ({None: "code", 1: "code", 2: "code"}, False),
    ({None: "legacy-code", 1: "code", 2: "code"}, True),
    ({None: "", 1: "code", 2: ""}, True),
])
def test_optional_legacy_column_does_not_hide_real_mismatches(codes, expected):
    assert service._has_mismatch("code", codes) is expected


def test_legacy_code_update_checks_conflicts_only_among_unversioned_records(storage):
    for station_id, version, code in ((1, None, "legacy"), (2, None, "used"), (3, 3, "named-code")):
        add(storage, service.Station, id=station_id, name=f"Station {station_id}",
            external_code=code, database_version_id=version)
    storage.commit()
    result = service.update_external_codes_from_check_page([
        {"entity_type": "station", "record_id": 1, "new_external_code": "used"},
    ])
    assert not result["ok"]
    assert storage.get(service.Station, 1).external_code == "legacy"
    result = service.update_external_codes_from_check_page([
        {"entity_type": "station", "record_id": 1, "new_external_code": "named-code"},
    ])
    assert result["ok"]
    assert storage.get(service.Station, 1).external_code == "named-code"
    assert storage.get(service.Station, 1).database_version_id is None


def test_unversioned_cell_renders_code_record_id_and_missing_record_explanation(storage):
    templates = Path(__file__).resolve().parents[2] / "app/templates"
    app = Flask(__name__, template_folder=str(templates))
    with app.test_request_context():
        html = app.jinja_env.get_template("generation/stations/external_code_cell.html").module.external_code_cell(
            "station", {"id": None, "version_number": "Без версии"}, "legacy-code", 253, "legacy-code",
        )
        missing = app.jinja_env.get_template("generation/stations/external_code_cell.html").module.external_code_cell(
            "station", {"id": None, "version_number": "Без версии"}, "", None, "legacy-code",
        )
    assert 'value="legacy-code"' in html
    assert 'data-record-id="253"' in html
    assert 'data-version-id=""' in html
    assert "Без версии" in html
    assert "Нет записи без версии БД" in missing
    assert "external-code-input" not in missing


@pytest.mark.parametrize("target_station_id", [2, 3])
def test_copy_existing_machine_requires_same_station_without_moving_or_duplicating(storage, monkeypatch, target_station_id):
    from scripts import copy_decentralized_zone_stations_and_equipment_groups_to_all_versions as copier

    for machine_id, station_id, version in ((1, 1, 1), (2, 2, 2)):
        add(storage, service.Machine, id=machine_id, id_station=station_id, database_version_id=version,
            external_code="machine-code", machine_number="1", machine_name="Турбина")
    storage.commit()
    model = service.Machine
    monkeypatch.setattr(copier, "Machine", SimpleNamespace(
        query=storage.query(model), id=model.id, external_code=model.external_code,
        database_version_id=model.database_version_id,
    ))
    source = storage.get(model, 1)
    if target_station_id == 2:
        target, created = copier._copy_machine(source, target_station_id, 2, None)
        assert target.id == 2
        assert not created
    else:
        with pytest.raises(ValueError, match="Конфликт привязки агрегата"):
            copier._copy_machine(source, target_station_id, 2, None)
    assert storage.get(model, 2).id_station == 2
    assert storage.query(model).count() == 2
    assert not storage.dirty
    assert not storage.new
