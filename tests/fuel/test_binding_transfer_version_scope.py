"""Version isolation for equipment-group binding transfers."""
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select, update

from test_equipment_group_binding_transfer import (
    snapshot, storage, transfer_client, seed, post, build, machine_row,
)
from app.fuel.services.equipment_groups import equipment_group_binding_transfer_services as service
from app.fuel.routes import equipment_group_binding_transfer_routes as routes


INVALID_VERSIONS = [
    (None, 2), (1, None), (None, None), (True, 2), (1, False),
    (0, 2), (1, 0), (-1, 2), (1, -1), ("1", 2), (1, "2"), (1, 1),
]


@pytest.mark.parametrize("source,target", INVALID_VERSIONS)
@pytest.mark.parametrize("operation", ["snapshot", "plan", "apply"])
def test_service_rejects_invalid_versions_before_any_sql(snapshot, monkeypatch, source, target, operation):
    plan = build(snapshot)
    execute = Mock(side_effect=AssertionError("Invalid versions must not reach SQL"))
    monkeypatch.setattr(service, "db", SimpleNamespace(session=SimpleNamespace(execute=execute)))
    with pytest.raises(ValueError):
        if operation == "snapshot":
            service.load_transfer_snapshot(source, target)
        elif operation == "plan":
            service.TransferPlan(snapshot, source, target)
        else:
            plan.source, plan.target = source, target
            service.apply_transfer_plan(plan, ["machine:1"], "editor")
    execute.assert_not_called()


@pytest.mark.parametrize("version", [None, 3])
@pytest.mark.parametrize("entity", ["stations", "machines", "types", "groups"])
def test_matching_codes_in_other_versions_never_replace_target(snapshot, version, entity):
    target = next(row for row in snapshot[entity] if row["database_version_id"] == 2)
    target["database_version_id"] = version
    assert machine_row(build(snapshot))["status"] == "blocked"


@pytest.mark.parametrize("version", [None, 3])
@pytest.mark.parametrize("entity", ["stations", "machines", "types", "groups"])
def test_matching_codes_in_other_versions_do_not_make_target_ambiguous(snapshot, version, entity):
    other = copy.deepcopy(next(row for row in snapshot[entity] if row["database_version_id"] == 2))
    other.update(id=99, database_version_id=version)
    snapshot[entity].append(other)
    row = machine_row(build(snapshot))
    assert row["status"] == "ready"
    assert row["target_machine_id"] == 2


@pytest.mark.parametrize("version", [None, 3])
@pytest.mark.parametrize("side", [0, 1])
def test_wrong_version_fuel_param_blocks_binding_instead_of_relabelling(snapshot, version, side):
    snapshot["params"][side]["database_version_id"] = version
    assert machine_row(build(snapshot))["status"] == "blocked"


@pytest.mark.parametrize("field", service.GROUP_REF_FIELDS)
@pytest.mark.parametrize("version", [None, 3])
def test_group_references_are_resolved_only_in_target_version(snapshot, field, version):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["groups"][0][field] = 11
    snapshot[field] = [
        dict(id=11, database_version_id=1, ref_uuid="reference"),
        dict(id=22, database_version_id=version, ref_uuid="reference"),
    ]
    assert machine_row(build(snapshot, True))["status"] == "blocked"


@pytest.mark.parametrize("field,value", [
    ("source_version_id", None), ("source_version_id", "null"),
    ("destination_version_id", None), ("destination_version_id", "null"),
])
def test_api_rejects_null_versions_before_loading(transfer_client, field, value):
    client, _, load, apply = transfer_client
    payload = dict(action="preview", source_version_id=1, destination_version_id=2)
    payload[field] = value
    response = post(client, payload)
    assert response.status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


@pytest.mark.parametrize("field", ["source", "target"])
@pytest.mark.parametrize("value", [None, True, 0, "2"])
def test_signed_invalid_version_is_rejected_before_loading(transfer_client, field, value):
    client, _, load, apply = transfer_client
    preview = post(client, dict(action="preview", source_version_id=1, destination_version_id=2))
    payload = routes._signer().loads(preview.json["token"])
    payload[field] = value
    token = routes._signer().dumps(payload)
    load.reset_mock()
    response = post(client, dict(action="apply", token=token, keys=["machine:1"]))
    assert response.status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


def test_null_request_destination_cannot_replace_signed_target(transfer_client):
    client, _, load, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1, destination_version_id=2)).json["token"]
    response = post(client, dict(action="apply", token=token, keys=["machine:1"],
                                 destination_version_id=None, target_version_id=None))
    assert response.status_code == 200
    load.assert_called_with(1, 2, lock=True)
    assert apply.call_args.args[0].target == 2


def test_current_null_version_cannot_load_or_apply(transfer_client, monkeypatch):
    client, _, load, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    load.reset_mock()
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: None)
    assert client.get("/transfer").status_code == 400
    assert post(client, dict(action="preview", source_version_id=1)).status_code == 400
    assert post(client, dict(action="apply", token=token, keys=["machine:1"])).status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


def test_real_transfer_leaves_null_and_third_version_rows_untouched(storage, snapshot):
    for version, offset in ((None, 100), (3, 200)):
        for name in ("stations", "machines", "types", "groups", "params", "station_links", "sets"):
            row = copy.deepcopy(snapshot[name][1])
            row["id"] += offset
            if "name" in row:
                row["name"] += f" {offset}"
            if "database_version_id" in row:
                row["database_version_id"] = version
            for key in ("id_station", "station_id", "machine_id", "equipment_group_id", "equipment_group_set_station_id"):
                if row.get(key) is not None:
                    row[key] += offset
            for key in ("id_equipment_group", "equipment_group_type_id"):
                if row.get(key) is not None:
                    row[key] += offset
            snapshot[name].append(row)
    # A real target group must be created even if an unversioned group has the same code and number.
    snapshot["groups"] = [r for r in snapshot["groups"] if r["database_version_id"] != 2]
    snapshot["sets"] = [r for r in snapshot["sets"] if r["id"] != 2]
    snapshot["station_links"] = [r for r in snapshot["station_links"] if r["id"] != 2]
    snapshot["params"] = [r for r in snapshot["params"] if r["id"] != 2]
    seed(storage, snapshot)
    before = {name: [dict(r) for r in storage.execute(select(table)).mappings()]
              for name, table in service.TABLES.items()}
    actual = service.load_transfer_snapshot(1, 2)
    for name in ("stations", "machines", "types", "groups", "station_links"):
        assert all(r["database_version_id"] in (1, 2) for r in actual[name])
    plan = service.TransferPlan(actual, 1, 2, True).build()
    result = service.apply_transfer_plan(plan, ["machine:1"], "editor")
    assert result["groups"] == 1
    for name, table in service.TABLES.items():
        original_ids = [r["id"] for r in before[name]]
        after = [dict(r) for r in storage.execute(select(table).where(table.c.id.in_(original_ids))).mappings()]
        assert after == before[name]
        if "database_version_id" in table.c:
            new_versions = storage.execute(select(table.c.database_version_id).where(
                table.c.id.not_in(original_ids))).scalars().all()
            assert all(version == 2 for version in new_versions)
    assert result["station_links"] == 1
    target_groups = storage.execute(select(service.TABLES["groups"]).where(
        service.TABLES["groups"].c.database_version_id == 2)).mappings().all()
    assert len(target_groups) == 1
    assert target_groups[0]["external_code"] == "group"
    target_param = storage.execute(select(service.TABLES["params"]).where(
        service.TABLES["params"].c.machine_id == 2)).mappings().one()
    assert target_param["database_version_id"] == 2
    assert target_param["equipment_group_id"] == target_groups[0]["id"]
    assert storage.execute(select(service.Log.__table__.c.database_version_id)).scalar_one() == 2


@pytest.mark.parametrize("entity,key", [("machines", "type:1"), ("params", "machine:1")])
@pytest.mark.parametrize("version", [None, 3])
def test_update_cannot_touch_record_that_left_target_version(storage, snapshot, entity, key, version):
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    plan = build(service.load_transfer_snapshot(1, 2))
    table = service.TABLES[entity]
    storage.execute(update(table).where(table.c.id == 2).values(database_version_id=version))
    storage.commit()
    before = storage.execute(select(table).where(table.c.id == 2)).mappings().one()
    with pytest.raises(ValueError, match="целевой версии"):
        service.apply_transfer_plan(plan, [key], "editor")
    storage.rollback()
    after = storage.execute(select(table).where(table.c.id == 2)).mappings().one()
    assert after == before
    assert storage.execute(select(service.Log.__table__)).first() is None
