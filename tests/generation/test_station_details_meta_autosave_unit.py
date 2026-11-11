from types import SimpleNamespace

from flask import Flask


def _station():
    return SimpleNamespace(
        id=17,
        database_version_id=4,
        name="Старая станция",
        id_station_group=2,
        group=SimpleNamespace(id=2, name="Исходная группа"),
        regional_district=None,
        id_condition_type=3,
        id_station_type=5,
        station_sign=None,
        note="",
        external_code="station-17",
        kto="",
        id_regional_district=6,
        location="",
        id_regional_energy_system=7,
        id_energy_unit=8,
    )


def _request_endpoint(monkeypatch, payload, *, roles):
    import app.generation.routes.stations.station_details_routes as routes
    import app.rational_structure.models
    import app.electrical_intensity.models

    station = _station()
    user = SimpleNamespace(
        is_authenticated=True,
        role_names=set(roles),
        is_admin="admin" in roles,
    )
    monkeypatch.setattr(routes, "current_user", user)
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 4)
    monkeypatch.setattr(
        routes,
        "_load_station_with_version",
        lambda *_args, **_kwargs: (station, 4),
    )
    monkeypatch.setattr(
        routes,
        "can_fuel_user_edit_decentralized_station_details",
        lambda *_args: False,
    )
    monkeypatch.setattr(routes, "get_regional_district_list_full", lambda: [])
    monkeypatch.setattr(routes, "invalidate_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, "invalidate_cache_pattern", lambda *_args, **_kwargs: None)

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test-secret", WTF_CSRF_ENABLED=False)
    with app.test_request_context(
        "/generation/stations/station_details/17/meta_value",
        method="PATCH",
        json=payload,
    ):
        result = routes.station_details_meta_value.__wrapped__(17)

    if isinstance(result, tuple):
        response, status = result
    else:
        response, status = result, result.status_code
    return response.get_json(), status, station


def test_station_meta_autosave_persists_only_requested_field(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes

    saved = {}

    def save_field(_user, station, form, _districts, **kwargs):
        saved.update(kwargs)
        station.name = form.name.data
        return ["Название изменено"]

    monkeypatch.setattr(routes, "update_station_from_form_service", save_field)
    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "name", "value": "Новая станция"},
        roles={"generation-editor"},
    )

    assert status == 200
    assert body == {"ok": True, "changed": True, "value": "Новая станция"}
    assert station.name == "Новая станция"
    assert saved["only_fields"] == {"name"}


def test_station_meta_autosave_checks_field_permissions(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes

    monkeypatch.setattr(
        routes,
        "update_station_from_form_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not save")),
    )
    body, status, _station = _request_endpoint(
        monkeypatch,
        {"field": "name", "value": "Новая станция"},
        roles=set(),
    )

    assert status == 403
    assert body == {"ok": False, "error": "Недостаточно прав"}


def test_station_group_text_autosave_creates_group_in_station_version(monkeypatch):
    from unittest.mock import MagicMock

    import app.generation.services.station_services.station_services as services

    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr(services.db, "session", session)
    monkeypatch.setattr(services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(services, "clear_station_aggregation_cache", lambda *_args: None)
    monkeypatch.setattr(services, "log_to_db", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(services, "current_user", SimpleNamespace(is_authenticated=False))

    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "station_group_name", "value": "  Новая группа  "},
        roles={"generation-editor"},
    )

    assert status == 200
    assert body == {"ok": True, "changed": True, "value": "Новая группа"}
    assert station.group.name == "Новая группа"
    assert station.group.database_version_id == 4
    assert station.name == _station().name
    session.query.return_value.filter_by.assert_called_once_with(
        name="Новая группа", database_version_id=4
    )


def test_station_group_text_autosave_reuses_existing_group(monkeypatch):
    from unittest.mock import MagicMock

    import app.generation.services.station_services.station_services as services

    existing_group = SimpleNamespace(id=10, name="Другая группа", database_version_id=4)
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = existing_group
    monkeypatch.setattr(services.db, "session", session)
    monkeypatch.setattr(services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(services, "clear_station_aggregation_cache", lambda *_args: None)
    monkeypatch.setattr(services, "log_to_db", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(services, "current_user", SimpleNamespace(is_authenticated=False))

    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "station_group_name", "value": "Другая группа"},
        roles={"generation-editor"},
    )

    assert status == 200
    assert body["value"] == existing_group.name
    assert station.group is existing_group
    session.add.assert_not_called()


def test_station_group_text_autosave_clears_group(monkeypatch):
    import app.generation.services.station_services.station_services as services

    monkeypatch.setattr(services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(services, "clear_station_aggregation_cache", lambda *_args: None)
    monkeypatch.setattr(services, "log_to_db", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(services, "current_user", SimpleNamespace(is_authenticated=False))

    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "station_group_name", "value": "   "},
        roles={"generation-editor"},
    )

    assert status == 200
    assert body == {"ok": True, "changed": True, "value": ""}
    assert station.group is None


def test_station_group_text_autosave_rejects_long_names(monkeypatch):
    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "station_group_name", "value": "я" * 81},
        roles={"generation-editor"},
    )

    assert status == 400
    assert body["ok"] is False
    assert station.group.name == _station().group.name


def test_station_group_text_autosave_requires_edit_permission(monkeypatch):
    body, status, station = _request_endpoint(
        monkeypatch,
        {"field": "station_group_name", "value": "Новая группа"},
        roles=set(),
    )

    assert status == 403
    assert body["ok"] is False
    assert station.group.name == _station().group.name


def test_generation_only_switch_is_not_autosaved(monkeypatch):
    body, status, _ = _request_endpoint(
        monkeypatch, {"field": "is_generation_only", "value": "0"},
        roles={"generation-editor"},
    )
    assert status == 400
    assert not body["ok"]


def test_generation_only_switch_is_passed_only_by_explicit_page_save(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes
    from werkzeug.datastructures import MultiDict
    monkeypatch.setattr(routes, "current_user", SimpleNamespace(is_authenticated=False))
    received = []
    monkeypatch.setattr(routes, "update_station_from_form_service", lambda *a, **kw: received.append(kw))
    form = SimpleNamespace(process=lambda **kw: None, validate=lambda: True)
    app = Flask(__name__)
    app.secret_key = "test"
    for data, expected in [
        ({"station_details_unified_save": "1", "generation_only_toggle_present": "1"}, False),
        ({"station_details_unified_save": "1", "generation_only_toggle_present": "1", "is_generation_only": "1"}, True),
        ({"station_details_unified_save": "1"}, None),
        ({"generation_only_toggle_present": "1"}, None),
    ]:
        with app.test_request_context("/station", method="POST", data=MultiDict(data)):
            routes._save_station_meta_from_form(
                "test", _station(), form, [], can_edit=True, can_edit_fuel=False,
            )
        assert received[-1].get("is_generation_only") == expected
