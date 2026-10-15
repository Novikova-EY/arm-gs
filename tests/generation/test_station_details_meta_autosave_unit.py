from types import SimpleNamespace

from flask import Flask


def _station():
    return SimpleNamespace(
        id=17,
        database_version_id=4,
        name="Старая станция",
        id_station_group=2,
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
