import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask, g
from flask_login import LoginManager
from jinja2 import ChoiceLoader, DictLoader
from sqlalchemy import create_engine, insert, select, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models.user_model import User
from app.fuel.services.equipment_groups import equipment_group_binding_transfer_services as service
from app.fuel.routes import equipment_group_binding_transfer_routes as routes


def station(pk, version, code="station"):
    return dict(id=pk, database_version_id=version, external_code=code, name="Station")


def machine(pk, version, station_id, type_id, code="machine"):
    return dict(id=pk, database_version_id=version, external_code=code, id_station=station_id,
                id_equipment_group=type_id, machine_number="1", machine_name="Turbine")


def group(pk, version, code="group", numb=100, **changes):
    return dict(id=pk, database_version_id=version, external_code=code, name="Group", name_ext=None,
                numb=numb, main=None, comp=None, regional_district_id=None, regional_energy_system_id=None,
                energy_unit_id=None, **changes)


@pytest.fixture
def snapshot():
    return dict(
        stations=[station(1, 1), station(2, 2)],
        machines=[machine(1, 1, 1, 10), machine(2, 2, 2, 20)],
        types=[dict(id=10, database_version_id=1, ref_uuid="type", name="Source type"),
               dict(id=20, database_version_id=2, ref_uuid="type", name="Target type")],
        groups=[group(1, 1), group(2, 2)],
        params=[dict(id=1, machine_id=1, database_version_id=1, equipment_group_id=1, numb1120=100, note="Source"),
                dict(id=2, machine_id=2, database_version_id=2, equipment_group_id=None, numb1120=None, note="Keep")],
        station_links=[dict(id=1, station_id=1, equipment_group_type_id=10, database_version_id=1),
                       dict(id=2, station_id=2, equipment_group_type_id=20, database_version_id=2)],
        sets=[dict(id=1, equipment_group_id=1, equipment_group_set_station_id=1),
              dict(id=2, equipment_group_id=2, equipment_group_set_station_id=2)],
        regional_district_id=[], regional_energy_system_id=[], energy_unit_id=[],
    )


def build(snapshot, create=False):
    return service.TransferPlan(snapshot, 1, 2, create).build()


def machine_row(plan):
    return next(r for r in plan.rows if r["kind"] == "machine")


def test_empty_binding_is_ready_and_source_is_not_mutated(snapshot):
    before = copy.deepcopy(snapshot)
    plan = build(snapshot)
    assert machine_row(plan)["status"] == "ready"
    assert machine_row(plan)["target_machine_id"] == 2
    assert next(r for r in plan.rows if r["kind"] == "link")["status"] == "same"
    assert snapshot == before


@pytest.mark.parametrize("entity", ["machines", "stations", "types", "groups"])
@pytest.mark.parametrize("version", [1, 2])
def test_duplicate_identity_blocks_instead_of_selecting_first(snapshot, entity, version):
    duplicate = copy.deepcopy(next(r for r in snapshot[entity] if r["database_version_id"] == version))
    duplicate["id"] = 90
    snapshot[entity].append(duplicate)
    assert machine_row(build(snapshot))["status"] == "blocked"


@pytest.mark.parametrize("entity", ["machines", "stations", "types", "groups"])
def test_missing_identity_is_not_guessed_from_names(snapshot, entity):
    snapshot[entity] = [r for r in snapshot[entity] if r["database_version_id"] != 2]
    assert machine_row(build(snapshot))["status"] == "blocked"


def test_existing_different_binding_is_an_explicit_conflict(snapshot):
    snapshot["groups"].append(group(3, 2, "other", 200))
    snapshot["params"][1]["equipment_group_id"] = 3
    assert machine_row(build(snapshot))["status"] == "conflict"


def test_already_matching_binding_is_idempotent(snapshot):
    snapshot["params"][1].update(equipment_group_id=2, numb1120=100)
    assert machine_row(build(snapshot))["status"] == "same"


@pytest.mark.parametrize("source_code,target_code", [(100, 99), (99, 100), (99, 99), (100, None)])
def test_matching_bindings_are_not_transferred_to_repair_service_codes(snapshot, source_code, target_code):
    snapshot["params"][0]["numb1120"] = source_code
    snapshot["params"][1].update(equipment_group_id=2, numb1120=target_code)
    before = copy.deepcopy(snapshot)
    row = machine_row(build(snapshot))
    assert row["status"] == "same"
    assert "Служебный код" in row["reason"]
    assert "не изменяется" in row["reason"]
    assert "будет использован" not in row["reason"]
    assert snapshot == before


def test_matching_binding_with_missing_station_link_explains_what_is_added(snapshot):
    snapshot["params"][1].update(equipment_group_id=2, numb1120=100)
    snapshot["sets"].pop()
    row = machine_row(build(snapshot))
    assert row["status"] == "ready"
    assert "Явная группа совпадает" in row["reason"]
    assert "недостающую связь" in row["reason"]


def test_matching_binding_with_wrong_service_code_cannot_be_applied(storage, snapshot):
    snapshot["params"][1].update(equipment_group_id=2, numb1120=99)
    seed(storage, snapshot)
    with pytest.raises(ValueError, match="нельзя перенести"):
        service.apply_transfer_plan(build(snapshot), ["machine:1"], "tester")
    params = service.TABLES["params"]
    assert storage.execute(select(params.c.numb1120).where(params.c.id == 2)).scalar_one() == 99
    assert storage.execute(select(service.Log.__table__)).first() is None


def test_different_type_is_ready_for_automatic_replacement(snapshot):
    snapshot["types"].append(dict(id=30, database_version_id=2, ref_uuid="other", name="Other"))
    snapshot["machines"][1]["id_equipment_group"] = 30
    plan = build(snapshot)
    row = next(r for r in plan.rows if r["key"] == "type:1")
    assert row["status"] == "ready"
    assert row["type_id"] == 20
    assert "Заменить тип" in row["reason"]
    assert "Other" in row["current_group"]
    assert machine_row(plan)["status"] == "ready"


def test_empty_binding_with_other_implicit_membership_requires_explicit_confirmation(snapshot):
    snapshot["groups"].append(group(3, 2, "other", 200))
    snapshot["sets"].append(dict(id=3, equipment_group_id=3, equipment_group_set_station_id=2))
    row = machine_row(build(snapshot))
    assert row["status"] == "conflict"
    assert "Вычисляется" in row["current_group"]
    assert "200" in row["current_group"]


def test_new_station_link_can_extend_implicit_membership(snapshot):
    snapshot["sets"].pop()
    plan = build(snapshot)
    assert machine_row(plan)["status"] == "ready"
    assert next(r for r in plan.rows if r["key"] == "link:1")["status"] == "ready"


def test_station_mismatch_is_blocked(snapshot):
    snapshot["machines"][1]["id_station"] = 900
    assert machine_row(build(snapshot))["status"] == "blocked"


@pytest.mark.parametrize("field", ["database_version_id", "machine_id"])
def test_inconsistent_param_does_not_get_relabelled_as_target_version(snapshot, field):
    if field == "database_version_id":
        snapshot["params"][1][field] = 99
    else:
        snapshot["params"].append(copy.deepcopy(snapshot["params"][1]))
    assert machine_row(build(snapshot))["status"] == "blocked"


def test_missing_group_is_only_created_when_enabled_and_safe(snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    assert machine_row(build(snapshot))["status"] == "blocked"
    plan = build(snapshot, True)
    assert machine_row(plan)["status"] == "conflict"
    assert plan.creations[1]["database_version_id"] == 2
    assert plan.creations[1]["external_code"] == "group"


def test_new_group_code_collision_is_not_merged(snapshot):
    snapshot["groups"][1]["external_code"] = "other"
    assert machine_row(build(snapshot, True))["status"] == "blocked"


def test_group_foreign_keys_are_remapped_by_reference_uuid(snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    snapshot["groups"][0]["energy_unit_id"] = 11
    snapshot["energy_unit_id"] = [dict(id=11, database_version_id=1, ref_uuid="unit"),
                                  dict(id=22, database_version_id=2, ref_uuid="unit")]
    plan = build(snapshot, True)
    assert plan.creations[1]["energy_unit_id"] == 22
    snapshot["energy_unit_id"].pop()
    assert machine_row(build(snapshot, True))["status"] == "blocked"


def test_composite_parent_is_a_creation_dependency(snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    snapshot["groups"][0]["main"] = 50
    parent = group(3, 1, "parent", 50)
    parent["comp"] = 1
    snapshot["groups"].append(parent)
    plan = build(snapshot, True)
    assert machine_row(plan)["status"] == "conflict"
    assert set(plan.creations) == {1, 3}
    assert plan.creations[1]["main"] == 50


def test_new_child_cannot_use_existing_non_composite_parent(snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["groups"][0]["main"] = 50
    source_parent = group(3, 1, "parent", 50)
    source_parent["comp"] = 1
    snapshot["groups"] += [source_parent, group(4, 2, "parent", 50)]
    plan = build(snapshot, True)
    row = machine_row(plan)
    assert row["status"] == "blocked"
    assert "Целевой родитель" in row["reason"]
    assert next(r for r in plan.rows if r["key"] == "type:1")["status"] == "same"


def test_cycle_is_reported_without_recursion_error(snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["groups"][0].update(main=100, comp=1)
    assert machine_row(build(snapshot, True))["status"] == "blocked"


def test_type_only_source_binding_is_already_matching_without_explicit_group(snapshot):
    snapshot["params"][0]["equipment_group_id"] = None
    plan = build(snapshot)
    row = next(row for row in plan.rows if row["key"] == "type:1")
    assert row["status"] == "same"
    assert row["source_group_id"] is None
    assert not any(row["kind"] == "machine" for row in plan.rows)


def test_fingerprint_changes_for_other_machines_and_metadata(snapshot):
    initial = service.snapshot_fingerprint(snapshot)
    snapshot["machines"][1]["machine_name"] = "Changed"
    assert service.snapshot_fingerprint(snapshot) != initial


@pytest.fixture
def storage(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.connect() as conn:
        for schema in ("gs_gen", "gs_fue", "gs_sys", "gs_logs"):
            conn.exec_driver_sql(f"ATTACH DATABASE ':memory:' AS {schema}")
        for table in [*service.TABLES.values(), *service._reference_tables().values(), service.Log.__table__]:
            table.create(conn)
        conn.commit()
    with Session(engine) as session:
        monkeypatch.setattr(service, "db", SimpleNamespace(session=session, engine=engine))
        yield session
    engine.dispose()


def seed(storage, snapshot):
    for name, table in service.TABLES.items():
        for row in snapshot[name]:
            values = {k: v for k, v in row.items() if k in table.c}
            if name == "machines":
                values["version"] = 1
            storage.execute(insert(table).values(**values))
    storage.commit()


def test_apply_changes_only_selected_target_binding_and_logs_before_values(storage, snapshot):
    seed(storage, snapshot)
    plan = build(snapshot)
    result = service.apply_transfer_plan(plan, ["machine:1"], "editor")
    assert result == {"machines": 1, "groups": 0, "links": 0, "station_links": 0}
    params = storage.execute(select(service.TABLES["params"]).order_by(service.TABLES["params"].c.id)).mappings().all()
    assert params[0]["equipment_group_id"] == 1
    assert params[1]["equipment_group_id"] == 2
    assert params[1]["numb1120"] == 100
    assert params[1]["note"] == "Keep"
    log = storage.execute(select(service.Log.__table__)).mappings().one()
    details = json.loads(log["details"])
    assert details["bindings"][0]["before_param"]["equipment_group_id"] is None
    assert log["database_version_id"] == 2


def test_apply_creates_only_selected_groups_not_other_planned_groups(storage, snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    snapshot["groups"].append(group(3, 1, "unused", 300))
    snapshot["sets"].append(dict(id=3, equipment_group_id=3, equipment_group_set_station_id=1))
    seed(storage, snapshot)
    result = service.apply_transfer_plan(build(snapshot, True), ["machine:1"], "editor")
    assert result["groups"] == 1
    targets = storage.execute(select(service.TABLES["groups"]).where(service.TABLES["groups"].c.database_version_id == 2)).mappings().all()
    assert [r["external_code"] for r in targets] == ["group"]


@pytest.mark.parametrize("keys", [[], ["machine:1", "machine:1"], ["made-up"], ["link:2"]])
def test_invalid_selection_writes_nothing(storage, snapshot, keys):
    seed(storage, snapshot)
    with pytest.raises(ValueError):
        service.apply_transfer_plan(build(snapshot), keys, "editor")
    assert storage.execute(select(service.Log.__table__)).all() == []


class TransferUser(SimpleNamespace):
    is_admin = User.is_admin
    has_admin = User.has_admin


@pytest.fixture
def transfer_client(monkeypatch, snapshot):
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[2] / "app/templates"))
    app.jinja_env.loader = ChoiceLoader([
        DictLoader({"base.html": "<title>{% block title %}{% endblock %}</title>{% block content %}{% endblock %}"}),
        app.jinja_env.loader,
    ])
    app.config.update(TESTING=True, SECRET_KEY="test")
    LoginManager(app)
    user = TransferUser(is_authenticated=True, roles=[SimpleNamespace(name="admin")],
                        username="Новикова Елена Юрьевна", get_id=lambda: "user-1")
    app.before_request(lambda: setattr(g, "_login_user", user))
    app.add_url_rule("/transfer", "fuel_bp.equipment_group_binding_transfer", routes.equipment_group_binding_transfer, methods=["GET", "POST"])
    app.add_url_rule("/transfer/page", "fuel_bp.equipment_group_binding_transfer_page", routes.equipment_group_binding_transfer_page)
    app.add_url_rule("/catalog", "fuel_bp.stations_equipment_groups", lambda: "")
    rows = [SimpleNamespace(id=1, version_number="Source"), SimpleNamespace(id=2, version_number="Target")]
    session = SimpleNamespace(execute=lambda *args: rows, rollback=Mock())
    monkeypatch.setattr(routes, "db", SimpleNamespace(session=session))
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 2)
    load = Mock(return_value=snapshot)
    apply = Mock(return_value={"machines": 1, "groups": 0, "links": 0})
    monkeypatch.setattr(routes, "load_transfer_snapshot", load)
    monkeypatch.setattr(routes, "apply_transfer_plan", apply)
    monkeypatch.setattr(routes, "clear_aggregation_cache", Mock())
    with app.test_client() as client:
        with client.session_transaction() as flask_session:
            flask_session["csrf_token"] = "csrf"
        yield client, user, load, apply


def post(client, data):
    if isinstance(data, dict) and data.get("action") == "preview":
        data = {"target_version_id": 2, **data}
    return client.post("/transfer", json=data, headers={"X-CSRF-Token": "csrf"})


def test_standalone_page_renders_without_loading_or_writing_bindings(transfer_client):
    client, _, load, apply = transfer_client
    response = client.get("/transfer/page")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    html = response.get_data(as_text=True)
    assert 'id="bindingTransferPage"' in html
    assert 'data-url="/transfer"' in html
    assert 'data-csrf-token="csrf"' in html
    assert 'data-catalog-url="/catalog"' in html
    assert 'id="bindingTransferBack" href="/catalog"' in html
    assert "equipment_group_binding_transfer.js?v=4" in html
    assert "bindingTransferModal" not in html
    assert "modal-dialog" not in html
    load.assert_not_called()
    apply.assert_not_called()


def test_standalone_page_requires_admin(transfer_client):
    client, user, load, apply = transfer_client
    user.roles = []
    assert client.get("/transfer/page").status_code == 403
    load.assert_not_called()
    apply.assert_not_called()


def test_standalone_page_requires_login(transfer_client):
    client, user, load, apply = transfer_client
    user.is_authenticated = False
    assert client.get("/transfer/page").status_code == 401
    load.assert_not_called()
    apply.assert_not_called()


def test_route_lists_versions_and_previews_without_write(transfer_client):
    client, _, load, apply = transfer_client
    data = client.get("/transfer").json
    assert data["target"]["id"] == 2
    assert [r["id"] for r in data["sources"]] == [1]
    result = post(client, dict(action="preview", source_version_id=1))
    assert result.status_code == 200
    assert result.json["token"]
    load.assert_called_once_with(1, 2)
    apply.assert_not_called()


@pytest.mark.parametrize("data", [[], None, {"action": "unknown"}, {"action": "preview", "source_version_id": 2},
                                      {"action": "preview", "source_version_id": True},
                                      {"action": "preview", "source_version_id": 1, "create_missing": "false"}])
def test_invalid_requests_do_not_load_or_write(transfer_client, data):
    client, _, load, apply = transfer_client
    response = post(client, data)
    assert response.status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


def test_csrf_and_permissions(transfer_client):
    client, user, load, apply = transfer_client
    assert client.post("/transfer", json=dict(action="preview", source_version_id=1)).status_code == 400
    user.roles = []
    assert client.get("/transfer").status_code == 403
    assert post(client, dict(action="preview", source_version_id=1)).status_code == 403
    load.assert_not_called()
    apply.assert_not_called()


@pytest.mark.parametrize("username", ["admin", "Новикова Елена Юрьевна"])
@pytest.mark.parametrize("role_name", ["fuel-admin", "generation-admin", "load-admin", "Admin", "admin2", "guest"])
def test_transfer_requires_exact_admin_role_not_username(transfer_client, username, role_name):
    client, user, load, apply = transfer_client
    user.username = username
    user.roles = [SimpleNamespace(name=role_name)]
    assert client.get("/transfer").status_code == 403
    for action in ("preview", "apply"):
        assert post(client, dict(action=action, source_version_id=1)).status_code == 403
    load.assert_not_called()
    apply.assert_not_called()


def test_removing_admin_role_revokes_access_to_previously_signed_plan(transfer_client):
    client, user, load, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    load.reset_mock()
    user.roles = [SimpleNamespace(name="fuel-admin")]
    response = post(client, dict(action="apply", token=token, keys=["machine:1"]))
    assert response.status_code == 403
    load.assert_not_called()
    apply.assert_not_called()


def test_preview_cannot_silently_change_destination_version(transfer_client):
    client, _, load, apply = transfer_client
    response = post(client, dict(action="preview", source_version_id=1, target_version_id=1))
    assert response.status_code == 409
    load.assert_not_called()
    apply.assert_not_called()


def test_signed_plan_is_applied_only_after_rechecking_snapshot(transfer_client):
    client, _, load, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    response = post(client, dict(action="apply", token=token, keys=["machine:1"]))
    assert response.status_code == 200
    load.assert_called_with(1, 2, lock=True)
    assert apply.call_args.args[1:] == (["machine:1"], "Новикова Елена Юрьевна")


@pytest.mark.parametrize("age_seconds", [901, 86400, 365 * 86400])
@pytest.mark.parametrize("data_changed", [False, True])
def test_old_plan_has_no_time_limit_but_still_checks_snapshot(transfer_client, snapshot, monkeypatch, age_seconds, data_changed):
    client, _, _, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    signer = routes._signer()
    payload = signer.loads(token)
    timestamp_signer = signer.make_signer()
    old_timestamp = timestamp_signer.get_timestamp() - age_seconds
    monkeypatch.setattr(timestamp_signer, "get_timestamp", lambda: old_timestamp)
    monkeypatch.setattr(signer, "make_signer", lambda salt=None: timestamp_signer)
    old_token = signer.dumps(payload)
    if data_changed:
        snapshot["params"][1]["note"] = "Changed after preview"
    response = post(client, dict(action="apply", token=old_token, keys=["machine:1"]))
    if data_changed:
        assert response.status_code == 409
        assert "данные изменились" in response.json["message"]
        apply.assert_not_called()
    else:
        assert response.status_code == 200
        apply.assert_called_once()


def test_stale_plan_is_rejected_without_apply(transfer_client, snapshot):
    client, _, _, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    snapshot["params"][1]["note"] = "Concurrent edit"
    response = post(client, dict(action="apply", token=token, keys=["machine:1"]))
    assert response.status_code == 409
    apply.assert_not_called()


def test_changed_current_version_is_rejected(transfer_client, monkeypatch):
    client, _, _, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 1)
    assert post(client, dict(action="apply", token=token, keys=["machine:1"])).status_code == 409
    apply.assert_not_called()


def test_cache_failure_does_not_claim_committed_transfer_was_cancelled(transfer_client, monkeypatch):
    client, _, _, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    monkeypatch.setattr(routes, "clear_aggregation_cache", Mock(side_effect=RuntimeError("Cache unavailable")))
    assert post(client, dict(action="apply", token=token, keys=["machine:1"])).json["success"] is True
    apply.assert_called_once()


def test_tampered_or_other_user_plan_is_rejected(transfer_client):
    client, user, _, apply = transfer_client
    token = post(client, dict(action="preview", source_version_id=1)).json["token"]
    assert post(client, dict(action="apply", token=token + "bad", keys=["machine:1"])).status_code == 409
    user.get_id = lambda: "another-user"
    assert post(client, dict(action="apply", token=token, keys=["machine:1"])).status_code == 409
    apply.assert_not_called()


def test_real_snapshot_after_apply_is_idempotent(storage, snapshot):
    seed(storage, snapshot)
    service.apply_transfer_plan(build(snapshot), ["machine:1"], "editor")
    actual = service.load_transfer_snapshot(1, 2)
    assert machine_row(build(actual))["status"] == "same"
    assert actual["params"][1]["note"] == "Keep"


def test_apply_creates_missing_param_and_remaps_type(storage, snapshot):
    snapshot["params"].pop()
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    service.apply_transfer_plan(build(snapshot), ["machine:1", "type:1"], "editor")
    actual = service.load_transfer_snapshot(1, 2)
    assert machine_row(build(actual))["status"] == "same"
    assert next(m for m in actual["machines"] if m["id"] == 2)["id_equipment_group"] == 20
    target = next(p for p in actual["params"] if p["machine_id"] == 2)
    assert target["database_version_id"] == 2


def test_audit_failure_rolls_back_bindings_and_created_groups(storage, snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    seed(storage, snapshot)

    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO gs_logs.logs"):
            raise IntegrityError(statement, parameters, Exception("Audit unavailable"))

    event.listen(storage.bind, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(IntegrityError):
            service.apply_transfer_plan(build(snapshot, True), ["machine:1"], "editor")
        storage.rollback()
    finally:
        event.remove(storage.bind, "before_cursor_execute", fail_audit)
    targets = storage.execute(select(service.TABLES["groups"]).where(service.TABLES["groups"].c.database_version_id == 2)).all()
    assert targets == []
    param = storage.execute(select(service.TABLES["params"]).where(service.TABLES["params"].c.machine_id == 2)).mappings().one()
    assert param["equipment_group_id"] == 99
    assert param["note"] == "Keep"


def test_multiple_selected_rows_share_one_created_group_and_relation(storage, snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][1]["equipment_group_id"] = 99
    snapshot["machines"] += [machine(3, 1, 1, 10, "second"), machine(4, 2, 2, 20, "second")]
    snapshot["params"] += [dict(id=3, machine_id=3, database_version_id=1, equipment_group_id=1, numb1120=100),
                           dict(id=4, machine_id=4, database_version_id=2, equipment_group_id=99, numb1120=None)]
    seed(storage, snapshot)
    result = service.apply_transfer_plan(build(snapshot, True), ["machine:1", "machine:3", "link:1"], "editor")
    assert result == {"machines": 2, "groups": 1, "links": 1, "station_links": 0}
    assert machine_row(build(service.load_transfer_snapshot(1, 2)))["status"] == "same"


def test_comparison_columns_show_identities_and_actual_station_links(snapshot):
    snapshot["params"][1]["equipment_group_id"] = 2
    row = machine_row(build(snapshot))
    assert row["current_group_external_code"] == "group (ID 2)"
    assert row["source_group_external_code"] == "group (ID 1)"
    assert row["current_type_ref_uuid"] == "type (ID 20)"
    assert row["source_type_ref_uuid"] == "type (ID 10)"
    assert "external_code: station; ID 2" in row["current_station_link"]
    assert "Группа ID 2 → станция/тип: есть (ID связи 2)" in row["current_station_link"]
    assert "Группа ID 1 → станция/тип: есть (ID связи 1)" in row["source_station_link"]


def test_same_display_number_and_type_name_do_not_hide_different_identities(snapshot):
    snapshot["groups"].append(group(3, 2, "other-group", 100))
    snapshot["params"][1]["equipment_group_id"] = 3
    snapshot["types"].append(dict(id=30, database_version_id=2, ref_uuid="other-type", name="Source type"))
    snapshot["machines"][1]["id_equipment_group"] = 30
    row = machine_row(build(snapshot))
    assert row["status"] == "conflict"
    assert row["current_group_external_code"] == "other-group (ID 3)"
    assert row["source_group_external_code"] == "group (ID 1)"
    assert row["current_type_ref_uuid"] == "other-type (ID 30)"
    assert "нет связи" in row["current_station_link"]


def test_comparison_shows_all_implicit_groups_and_missing_station_link(snapshot):
    snapshot["groups"].append(group(3, 2, "other-group", 200))
    snapshot["sets"].append(dict(id=3, equipment_group_id=3, equipment_group_set_station_id=2))
    row = machine_row(build(snapshot))
    assert row["current_group_external_code"] == "group (ID 2)\nother-group (ID 3)"
    snapshot["params"][1]["equipment_group_id"] = 2
    snapshot["sets"] = snapshot["sets"][:1]
    row = machine_row(build(snapshot))
    assert "нет связи" in row["current_station_link"]
    assert "есть" in row["source_station_link"]


def test_blocked_and_link_only_rows_have_comparison_columns(snapshot):
    snapshot["machines"][1]["id_station"] = 900
    plan = build(snapshot)
    row = machine_row(plan)
    assert row["status"] == "blocked"
    assert "ID 900" in row["current_station_link"]
    assert row["source_group_external_code"] == "group (ID 1)"
    link = next(r for r in plan.rows if r["kind"] == "link")
    assert link["current_group_external_code"] == "group (ID 2)"
    assert "ID связи 2" in link["current_station_link"]
    snapshot["params"][0]["equipment_group_id"] = None
    implicit = next(r for r in build(snapshot).rows if r["key"] == "type:1")
    assert implicit["source_group_external_code"] == "group (ID 1)"
    assert implicit["source_type_ref_uuid"] == "type (ID 10)"
    assert "ID связи 1" in implicit["source_station_link"]


def report_payload(snapshot, completed=False):
    return dict(source="Source", target="Target", rows=build(snapshot).public()["rows"],
                selected_keys=["machine:1"], completed=completed)


@pytest.mark.parametrize("completed", [False, True])
def test_excel_report_preserves_preview_and_selection_without_database_access(transfer_client, snapshot, completed):
    from io import BytesIO
    from openpyxl import load_workbook

    client, _, load, apply = transfer_client
    report = report_payload(snapshot, completed)
    # Export the analyzed snapshot, even if the database has changed since preview/apply.
    snapshot["groups"][0]["external_code"] = "changed-later"
    response = post(client, dict(action="report", report=report))
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "equipment_group_binding_transfer.xlsx" in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "no-store"
    sheet = load_workbook(BytesIO(response.data)).active
    assert sheet["B2"].value == "Source"
    assert sheet["B3"].value == "Target"
    assert sheet["B4"].value == ("Да" if completed else "Нет")
    assert sheet["A6"].value == "Да"
    assert sheet["A7"].value == "Нет"
    assert sheet["I6"].value == "group (ID 1)"
    assert sheet["J6"].value == "type (ID 20)"
    assert "ID связи 1" in sheet["M6"].value
    assert sheet.max_row == len(report["rows"]) + 5
    assert sheet.freeze_panes == "D6"
    assert sheet.auto_filter.ref == f"A5:N{sheet.max_row}"
    load.assert_not_called()
    apply.assert_not_called()


def test_excel_report_writes_formula_like_names_and_identifiers_as_text(transfer_client, snapshot):
    from io import BytesIO
    from openpyxl import load_workbook

    client, _, _, _ = transfer_client
    report = report_payload(snapshot)
    report["source"] = "=1+2"
    report["rows"][0]["station"] = '=HYPERLINK("https://example.test")'
    report["rows"][0]["source_group_external_code"] = "00001234567890123456789"
    response = post(client, dict(action="report", report=report))
    sheet = load_workbook(BytesIO(response.data)).active
    for address, value in (("B2", report["source"]), ("D6", report["rows"][0]["station"]),
                           ("I6", "00001234567890123456789")):
        assert sheet[address].value == value
        assert sheet[address].data_type == "s"


@pytest.mark.parametrize("bad_report", [None, {}, {"rows": [], "selected_keys": ["unknown"], "completed": False},
                                           {"rows": [None], "selected_keys": [], "completed": False}])
def test_invalid_excel_report_is_rejected_without_writes(transfer_client, bad_report):
    client, _, load, apply = transfer_client
    assert post(client, dict(action="report", report=bad_report)).status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


def test_excel_report_requires_admin_and_csrf(transfer_client, snapshot):
    client, user, load, apply = transfer_client
    data = dict(action="report", report=report_payload(snapshot))
    assert client.post("/transfer", json=data).status_code == 400
    user.roles = []
    assert post(client, data).status_code == 403
    load.assert_not_called()
    apply.assert_not_called()


@pytest.mark.parametrize("current_type", [None, 30])
@pytest.mark.parametrize("has_param", [False, True])
def test_type_transfer_is_independent_of_groups_links_and_fuel_params(storage, snapshot, current_type, has_param):
    snapshot["types"].append(dict(id=30, database_version_id=2, ref_uuid="other", name="Other"))
    snapshot["machines"][1]["id_equipment_group"] = current_type
    snapshot["groups"] = []
    snapshot["station_links"] = []
    snapshot["sets"] = []
    if has_param:
        for param in snapshot["params"]:
            param["equipment_group_id"] = None
    else:
        snapshot["params"] = []
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    row = next(r for r in build(before).rows if r["key"] == "type:1")
    assert row["status"] == "ready"
    result = service.apply_transfer_plan(build(before, True), ["type:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert next(m for m in after["machines"] if m["id"] == 2)["id_equipment_group"] == 20
    assert next(m for m in after["machines"] if m["id"] == 1) == before["machines"][0]
    assert after["params"] == before["params"]
    assert after["groups"] == after["station_links"] == after["sets"] == []
    assert result == {"machines": 1, "groups": 0, "links": 0, "station_links": 0}
    assert next(r for r in build(after).rows if r["key"] == "type:1")["status"] == "same"
    log = storage.execute(select(service.Log.__table__)).mappings().one()
    details = json.loads(log["details"])
    assert details["bindings"] == []
    assert details["type_changes"] == [{"machine_id": 2, "before_type_id": current_type, "after_type_id": 20}]
    version = storage.execute(select(service.TABLES["machines"].c.version).where(service.TABLES["machines"].c.id == 2)).scalar_one()
    assert version == 2


def test_missing_group_blocks_explicit_binding_but_not_type_transfer(storage, snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    plan = build(snapshot)
    assert machine_row(plan)["status"] == "blocked"
    assert next(r for r in plan.rows if r["key"] == "type:1")["status"] == "ready"
    service.apply_transfer_plan(plan, ["type:1"], "editor")
    actual = service.load_transfer_snapshot(1, 2)
    assert actual["params"][1]["equipment_group_id"] is None
    assert [g for g in actual["groups"] if g["database_version_id"] == 2] == []
    assert actual["machines"][1]["id_equipment_group"] == 20


@pytest.mark.parametrize("entity", ["machines", "types"])
@pytest.mark.parametrize("version", [1, 2])
def test_type_transfer_blocks_ambiguous_identity(snapshot, entity, version):
    duplicate = dict(next(r for r in snapshot[entity] if r["database_version_id"] == version), id=90)
    snapshot[entity].append(duplicate)
    assert next(r for r in build(snapshot).rows if r["key"] == "type:1")["status"] == "blocked"


@pytest.mark.parametrize("entity", ["machines", "types"])
def test_type_transfer_does_not_guess_missing_counterpart(snapshot, entity):
    snapshot[entity] = [r for r in snapshot[entity] if r["database_version_id"] != 2]
    assert next(r for r in build(snapshot).rows if r["key"] == "type:1")["status"] == "blocked"


def test_type_transfer_does_not_require_a_station_mapping(snapshot):
    snapshot["stations"] = []
    snapshot["machines"][0]["id_station"] = None
    snapshot["machines"][1].update(id_station=None, id_equipment_group=None)
    plan = build(snapshot)
    row = next(r for r in plan.rows if r["key"] == "type:1")
    assert row["status"] == "ready"
    assert machine_row(plan)["status"] == "blocked"


def test_empty_source_type_preserves_target_type_even_when_explicit_group_is_transferred(storage, snapshot):
    snapshot["machines"][0]["id_equipment_group"] = None
    seed(storage, snapshot)
    plan = build(snapshot)
    assert not any(r["kind"] == "type" for r in plan.rows)
    assert machine_row(plan)["status"] == "ready"
    service.apply_transfer_plan(plan, ["machine:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] == 20
    assert after["params"][1]["equipment_group_id"] == 2


def test_type_only_source_does_not_create_or_clear_explicit_binding(storage, snapshot):
    snapshot["params"][0]["equipment_group_id"] = None
    snapshot["groups"].append(group(3, 2, "existing", 300))
    snapshot["params"][1].update(equipment_group_id=3, numb1120=300)
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    plan = build(before)
    assert not any(r["kind"] == "machine" for r in plan.rows)
    service.apply_transfer_plan(plan, ["type:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["params"] == before["params"]
    assert after["sets"] == before["sets"]
    assert after["machines"][1]["id_equipment_group"] == 20


@pytest.mark.parametrize("null_type", [False, True])
def test_station_type_link_without_groups_or_machines_is_transferred(storage, snapshot, null_type):
    snapshot["machines"] = []
    snapshot["params"] = []
    snapshot["groups"] = []
    snapshot["sets"] = []
    snapshot["station_links"].pop()
    if null_type:
        snapshot["station_links"][0]["equipment_group_type_id"] = None
    seed(storage, snapshot)
    plan = build(snapshot)
    row = next(r for r in plan.rows if r["key"] == "station_link:1")
    assert row["status"] == "ready"
    result = service.apply_transfer_plan(plan, [row["key"]], "editor")
    actual = service.load_transfer_snapshot(1, 2)
    target = next(r for r in actual["station_links"] if r["database_version_id"] == 2)
    assert target["station_id"] == 2
    assert target["equipment_group_type_id"] == (None if null_type else 20)
    assert actual["sets"] == actual["groups"] == actual["machines"] == []
    assert result == {"machines": 0, "groups": 0, "links": 0, "station_links": 1}
    assert next(r for r in build(actual).rows if r["key"] == row["key"])["status"] == "same"


@pytest.mark.parametrize("version", [1, 2])
def test_duplicate_station_type_link_blocks_links_but_not_type_transfer(snapshot, version):
    link = next(r for r in snapshot["station_links"] if r["database_version_id"] == version)
    snapshot["station_links"].append(dict(link, id=90))
    plan = build(snapshot)
    assert next(r for r in plan.rows if r["key"] == "station_link:1")["status"] == "blocked"
    assert next(r for r in plan.rows if r["key"] == "link:1")["status"] == "blocked"
    assert next(r for r in plan.rows if r["key"] == "type:1")["status"] == "same"


def test_station_link_without_station_is_blocked(snapshot):
    snapshot["station_links"][0]["station_id"] = None
    plan = build(snapshot)
    assert next(r for r in plan.rows if r["key"] == "station_link:1")["status"] == "blocked"
    assert next(r for r in plan.rows if r["key"] == "link:1")["status"] == "blocked"


def test_additive_many_to_many_links_preserve_extra_relations_and_implicit_bindings(storage, snapshot):
    snapshot["params"] = []
    snapshot["groups"] += [group(3, 1, "second", 200), group(4, 2, "second", 200), group(5, 2, "extra", 300)]
    snapshot["sets"] = [dict(id=1, equipment_group_id=1, equipment_group_set_station_id=1),
                        dict(id=3, equipment_group_id=3, equipment_group_set_station_id=1),
                        dict(id=5, equipment_group_id=5, equipment_group_set_station_id=2)]
    snapshot["stations"] += [station(3, 1, "second-station"), station(4, 2, "second-station")]
    snapshot["station_links"].append(dict(id=3, station_id=3, equipment_group_type_id=10, database_version_id=1))
    snapshot["sets"].append(dict(id=6, equipment_group_id=1, equipment_group_set_station_id=3))
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    plan = build(before)
    keys = [r["key"] for r in plan.rows if r["status"] == "ready"]
    assert set(keys) == {"link:1", "link:3", "station_link:3", "link:6"}
    result = service.apply_transfer_plan(plan, list(reversed(keys)), "editor")
    after = service.load_transfer_snapshot(1, 2)
    relations = {(r["equipment_group_id"], r["equipment_group_set_station_id"]) for r in after["sets"]}
    assert {(r["equipment_group_id"], r["equipment_group_set_station_id"]) for r in before["sets"]} <= relations
    assert (2, 2) in relations and (4, 2) in relations and (5, 2) in relations
    new_link = next(r for r in after["station_links"] if r["station_id"] == 4)
    assert (2, new_link["id"]) in relations
    assert after["params"] == []
    assert after["machines"] == before["machines"]
    assert after["groups"] == before["groups"]
    assert result == {"machines": 0, "groups": 0, "links": 3, "station_links": 1}
    assert all(r["status"] == "same" for r in build(after).rows)


def test_existing_group_is_reused_without_overwriting_different_parameters(storage, snapshot):
    snapshot["groups"][0].update(main=999, comp=1, name="Source name")
    snapshot["groups"][1].update(numb=777, main=None, comp=0, name="Keep target name")
    snapshot["params"][1].update(note="Keep target note", yearin=2020, dem=2040, nt=123)
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    plan = build(before)
    assert machine_row(plan)["status"] == "ready"
    service.apply_transfer_plan(plan, ["machine:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["groups"] == before["groups"]
    target_param = next(p for p in after["params"] if p["machine_id"] == 2)
    for field in ("note", "yearin", "dem", "nt"):
        assert target_param[field] == before["params"][1][field]
    assert target_param["equipment_group_id"] == 2
    assert target_param["numb1120"] == 777


@pytest.mark.parametrize("keys", [["type:1", "machine:1"], ["machine:1", "type:1"]])
def test_type_and_explicit_binding_are_independent_and_count_machine_once(storage, snapshot, keys):
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    result = service.apply_transfer_plan(build(snapshot), keys, "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] == 20
    assert after["params"][1]["equipment_group_id"] == 2
    assert result["machines"] == 1
    assert all(r["status"] == "same" for r in build(after).rows)


def test_explicit_binding_selection_does_not_apply_unselected_type_change(storage, snapshot):
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    service.apply_transfer_plan(build(snapshot), ["machine:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] is None
    assert after["params"][1]["equipment_group_id"] == 2
    assert next(r for r in build(after).rows if r["key"] == "type:1")["status"] == "ready"


def test_creating_group_through_link_does_not_infer_explicit_machine_binding(storage, snapshot):
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["params"][0]["equipment_group_id"] = None
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    plan = build(before, True)
    assert not any(r["kind"] == "machine" for r in plan.rows)
    result = service.apply_transfer_plan(plan, ["type:1", "link:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["params"] == before["params"]
    target = next(g for g in after["groups"] if g["database_version_id"] == 2)
    assert target["external_code"] == "group"
    assert target["id"] != 1
    assert any(s["equipment_group_id"] == target["id"] and s["equipment_group_set_station_id"] == 2 for s in after["sets"])
    assert result == {"machines": 1, "groups": 1, "links": 1, "station_links": 0}
    assert all(r["status"] == "same" for r in build(after, True).rows)


def test_type_change_does_not_rewrite_an_already_matching_explicit_binding(storage, snapshot):
    snapshot["types"].append(dict(id=30, database_version_id=2, ref_uuid="old-type", name="Old"))
    snapshot["machines"][1]["id_equipment_group"] = 30
    snapshot["params"][1].update(equipment_group_id=2, numb1120=99)
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    plan = build(before)
    assert machine_row(plan)["status"] == "same"
    selected = [r["key"] for r in plan.rows if r["status"] == "ready"]
    assert selected == ["type:1"]
    service.apply_transfer_plan(plan, selected, "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] == 20
    assert after["params"] == before["params"]


def test_replacing_type_keeps_old_station_type_and_group_links(storage, snapshot):
    snapshot["types"].append(dict(id=30, database_version_id=2, ref_uuid="old-type", name="Old"))
    snapshot["machines"][1]["id_equipment_group"] = 30
    snapshot["station_links"].append(dict(id=3, station_id=2, equipment_group_type_id=30, database_version_id=2))
    snapshot["sets"].append(dict(id=3, equipment_group_id=2, equipment_group_set_station_id=3))
    seed(storage, snapshot)
    before = service.load_transfer_snapshot(1, 2)
    service.apply_transfer_plan(build(before), ["type:1"], "editor")
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] == 20
    assert after["station_links"] == before["station_links"]
    assert after["sets"] == before["sets"]
    assert after["params"] == before["params"]


def test_route_previews_and_applies_type_when_final_group_is_missing(transfer_client, storage, snapshot, monkeypatch):
    client, _, _, _ = transfer_client
    snapshot["groups"].pop()
    snapshot["sets"].pop()
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)
    # SQLite exercises real writes but does not support PostgreSQL table locks.
    monkeypatch.setattr(routes, "load_transfer_snapshot", lambda source, target, **kw: service.load_transfer_snapshot(source, target))
    monkeypatch.setattr(routes, "apply_transfer_plan", service.apply_transfer_plan)
    preview = post(client, dict(action="preview", source_version_id=1))
    assert preview.status_code == 200
    rows = {r["key"]: r for r in preview.json["plan"]["rows"]}
    assert rows["machine:1"]["status"] == "blocked"
    assert rows["type:1"]["status"] == "ready"
    response = post(client, dict(action="apply", token=preview.json["token"], keys=["type:1"]))
    assert response.status_code == 200
    assert response.json["result"]["machines"] == 1
    assert response.json["result"]["groups"] == 0
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] == 20
    assert after["params"][1]["equipment_group_id"] is None
    again = post(client, dict(action="preview", source_version_id=1))
    assert next(r for r in again.json["plan"]["rows"] if r["key"] == "type:1")["status"] == "same"


def test_audit_failure_rolls_back_independent_type_change(storage, snapshot):
    snapshot["machines"][1]["id_equipment_group"] = None
    seed(storage, snapshot)

    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO gs_logs.logs"):
            raise IntegrityError(statement, parameters, Exception("Audit unavailable"))

    event.listen(storage.bind, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(IntegrityError):
            service.apply_transfer_plan(build(snapshot), ["type:1"], "editor")
        storage.rollback()
    finally:
        event.remove(storage.bind, "before_cursor_execute", fail_audit)
    after = service.load_transfer_snapshot(1, 2)
    assert after["machines"][1]["id_equipment_group"] is None
    assert after["params"][1]["equipment_group_id"] is None


@pytest.mark.parametrize("group_id", [True, 0, -1, "1", 99])
def test_group_scope_rejects_invalid_or_missing_source_group(transfer_client, group_id):
    client, _, _, apply = transfer_client
    response = post(client, dict(action="preview", source_version_id=1, group_id=group_id))
    assert response.status_code == 400
    apply.assert_not_called()


def test_group_scope_excludes_other_groups_and_their_machine_types(snapshot):
    snapshot["groups"].append(group(3, 1, "other", 300))
    snapshot["machines"].append(machine(3, 1, 1, 10, "other-machine"))
    snapshot["params"].append(dict(id=3, machine_id=3, database_version_id=1, equipment_group_id=3, numb1120=300))
    snapshot["sets"].append(dict(id=3, equipment_group_id=3, equipment_group_set_station_id=1))
    plan = service.TransferPlan(snapshot, 1, 2, True, group_id=1).build()
    assert {row["key"] for row in plan.rows} == {"machine:1", "type:1", "station_link:1", "link:1"}
    assert not plan.creations


def test_group_scope_includes_implicit_machine_type_but_does_not_create_explicit_binding(snapshot):
    snapshot["params"][0]["equipment_group_id"] = None
    plan = service.TransferPlan(snapshot, 1, 2, True, group_id=1).build()
    assert {row["key"] for row in plan.rows} == {"type:1", "station_link:1", "link:1"}


def test_explicit_destination_is_signed_and_does_not_follow_current_version(transfer_client, monkeypatch):
    client, _, load, apply = transfer_client
    preview = post(client, dict(action="preview", source_version_id=2, destination_version_id=1, group_id=2))
    assert preview.status_code == 200
    load.assert_called_once_with(2, 1)
    token = preview.json["token"]
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 1)
    response = post(client, dict(action="apply", token=token, keys=["machine:2"], destination_version_id=2, group_id=1))
    assert response.status_code == 200
    plan = apply.call_args.args[0]
    assert (plan.source, plan.target, plan.group_id) == (2, 1, 2)
    load.assert_called_with(2, 1, lock=True)


@pytest.mark.parametrize("destination", [True, None, "1", 99, 1])
def test_invalid_or_identical_explicit_destination_cannot_write(transfer_client, destination):
    client, _, load, apply = transfer_client
    response = post(client, dict(action="preview", source_version_id=1, destination_version_id=destination))
    assert response.status_code == 400
    load.assert_not_called()
    apply.assert_not_called()


def test_scoped_apply_rejects_keys_outside_signed_group(transfer_client, snapshot, monkeypatch):
    client, _, _, apply = transfer_client
    snapshot["machines"].append(machine(3, 1, 1, None, "other"))
    preview = post(client, dict(action="preview", source_version_id=1, group_id=1))
    monkeypatch.setattr(routes, "apply_transfer_plan", service.apply_transfer_plan)
    response = post(client, dict(action="apply", token=preview.json["token"], keys=["type:3"]))
    assert response.status_code == 400
    assert "актуального предварительного плана" in response.json["message"]
    apply.assert_not_called()


def test_arkhangelsk_heat_group_can_be_created_in_every_named_version_without_machines(storage, snapshot, monkeypatch):
    snapshot["groups"] = [group(1, 1, "heat-code", 1958)]
    snapshot["groups"][0]["name"] = "Архангельская ТЭЦ(тепл)"
    snapshot["sets"] = snapshot["sets"][:1]
    snapshot["machines"] = []
    snapshot["params"] = []
    snapshot["stations"].append(station(3, 3))
    snapshot["types"].append(dict(id=30, database_version_id=3, ref_uuid="type", name="Type"))
    seed(storage, snapshot)
    for target in (2, 3):
        before = service.load_transfer_snapshot(1, target)
        plan = service.TransferPlan(before, 1, target, True, group_id=1).build()
        result = service.apply_transfer_plan(plan, [r["key"] for r in plan.rows if r["status"] == "ready"], "editor")
        assert result["groups"] == 1
        after = service.load_transfer_snapshot(1, target)
        target_group = next(g for g in after["groups"] if g["database_version_id"] == target)
        assert (target_group["external_code"], target_group["numb"], target_group["name"]) == (
            "heat-code", 1958, "Архангельская ТЭЦ(тепл)")
        target_links = {r["id"] for r in after["station_links"] if r["database_version_id"] == target}
        assert any(r["equipment_group_id"] == target_group["id"] and r["equipment_group_set_station_id"] in target_links
                   for r in after["sets"])
        again = service.TransferPlan(after, 1, target, True, group_id=1).build()
        assert all(r["status"] == "same" for r in again.rows)
    assert storage.execute(select(service.TABLES["groups"].c.database_version_id)).scalars().all() == [1, 2, 3]
    from app.generation.services.station_services import external_code_check_services as check
    from importlib import import_module

    for module in (
        "app.power_demand.models", "app.economics.models", "app.electrical_intensity.models",
        "app.energy_consumption.models", "app.energy_balance.models", "app.territories.models",
        "app.ecology.models", "app.rational_structure.models",
    ):
        import_module(module)

    monkeypatch.setattr(check, "db", SimpleNamespace(session=storage))
    view = SimpleNamespace(id=2, database_version_id=2, machines=[])
    check._attach_equipment_groups_for_check(
        view, [SimpleNamespace(id=i) for i in (1, 2, 3)], [None, 1, 2, 3], False, "",
    )
    assert len(view.external_code_equipment_groups) == 1
    node = view.external_code_equipment_groups[0]
    assert node.external_codes_by_version == {None: "", 1: "heat-code", 2: "heat-code", 3: "heat-code"}
    assert node.external_code_mismatch is False
    assert node.numb == 1958
