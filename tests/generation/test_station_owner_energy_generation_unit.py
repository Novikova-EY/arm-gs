# -*- coding: utf-8 -*-
"""Проверки таблицы выработки от собственника (ВЭС/СЭС) на карточке станции."""
from types import SimpleNamespace

from flask import Flask

from app.generation.services.station_services.station_type_flags import (
    is_gaes_station,
    is_ges_station,
    is_ves_or_ses_station,
)


def _station(type_name):
    return SimpleNamespace(station_type=SimpleNamespace(name=type_name))


def test_ves_and_ses_are_detected():
    assert is_ves_or_ses_station(_station("ВЭС")) is True
    assert is_ves_or_ses_station(_station("СЭС")) is True
    assert is_ves_or_ses_station(_station("вэс")) is True
    assert is_ves_or_ses_station(_station("ВЭС (Р)")) is True
    assert is_ves_or_ses_station(_station("СЭС (Р)")) is True


def test_other_station_types_are_not_ves_ses():
    assert is_ves_or_ses_station(_station("ТЭС")) is False
    assert is_ves_or_ses_station(_station("ГАЭС")) is False
    assert is_ves_or_ses_station(_station("ГЭС")) is False
    assert is_ves_or_ses_station(_station(None)) is False
    assert is_ves_or_ses_station(SimpleNamespace(station_type=None)) is False


def test_gaes_detection_unchanged():
    assert is_gaes_station(_station("ГАЭС")) is True
    assert is_gaes_station(_station("ВЭС")) is False


def test_ges_detection():
    assert is_ges_station(_station("ГЭС")) is True
    assert is_ges_station(_station("гэс")) is True
    assert is_ges_station(_station("ГАЭС")) is False
    assert is_ges_station(_station("ТЭС")) is False


def test_clearing_zero_energy_is_detected_as_change():
    from app.generation.services.station_services.station_services import (
        _station_numeric_field_changed,
    )

    assert _station_numeric_field_changed("", "0,0") is True
    assert _station_numeric_field_changed("", "0.0") is True
    assert _station_numeric_field_changed("0", "") is True
    assert _station_numeric_field_changed("0,0", "0.0") is False
    assert _station_numeric_field_changed("", "") is False


def _ves_station():
    return SimpleNamespace(id=6719, station_type=SimpleNamespace(name="СЭС"))


def _request_owner_generation_patch(monkeypatch, payload, *, roles, station=None):
    import app.generation.routes.stations.station_details_routes as routes

    station = station or _ves_station()
    user = SimpleNamespace(is_authenticated=True, role_names=set(roles))
    monkeypatch.setattr(routes, "current_user", user)
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 4)
    monkeypatch.setattr(
        routes, "_load_station_with_version", lambda *_args, **_kwargs: (station, 4)
    )
    monkeypatch.setattr(
        routes, "can_fuel_user_edit_decentralized_station_details", lambda *_args: False
    )
    monkeypatch.setattr(routes, "invalidate_cache", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(routes, "invalidate_cache_pattern", lambda *_args, **_kwargs: None)

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test-secret", WTF_CSRF_ENABLED=False)
    with app.test_request_context(
        "/generation/stations/station_details/6719/energy_value",
        method="PATCH",
        json=payload,
        query_string={"start_year": "2024", "end_year": "2031"},
    ):
        result = routes.station_details_energy_value.__wrapped__(6719)

    if isinstance(result, tuple):
        response, status = result
    else:
        response, status = result, result.status_code
    return response.get_json(), status


def test_owner_generation_patch_saves_cell_and_returns_plan_sync(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes

    saved_forms = []
    sync_calls = []

    def save_owner(_user, _station, _version_id, start_year, end_year, form_data):
        saved_forms.append((start_year, end_year, dict(form_data)))
        return ["2028 г.: 100 → 112,74"]

    def sync(_user, _station, **kwargs):
        sync_calls.append(kwargs)
        return {"year": 2028, "value": "112,74", "rule": "Расчёт: выработка от собственника"}

    monkeypatch.setattr(routes, "save_station_owner_energy_generation_service", save_owner)
    monkeypatch.setattr(routes, "_sync_owner_generation_to_plan_cell", sync)

    body, status = _request_owner_generation_patch(
        monkeypatch,
        {
            "kind": "owner_generation",
            "year": "2028",
            "value": "112,74",
            "orig": "100",
            "rounding": "2",
        },
        roles={"generation-editor"},
    )

    assert status == 200
    assert body["ok"] is True
    assert body["changed"] is True
    assert body["gen"] == {
        "year": 2028,
        "value": "112,74",
        "rule": "Расчёт: выработка от собственника",
    }
    assert saved_forms == [
        (2028, 2028, {"st_owner_gen_2028": "112,74", "st_owner_gen_2028_orig": "100"})
    ]
    assert sync_calls == [
        {
            "year": 2028,
            "previous_owner_value": "100",
            "plan_start_year": 2024,
            "plan_end_year": 2031,
            "station_version_id": 4,
            "rounding_digits": 2,
        }
    ]


def test_owner_generation_patch_is_rejected_outside_ves_ses(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes

    monkeypatch.setattr(
        routes,
        "save_station_owner_energy_generation_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not save")),
    )

    body, status = _request_owner_generation_patch(
        monkeypatch,
        {"kind": "owner_generation", "year": "2028", "value": "112,74", "orig": ""},
        roles={"generation-editor"},
        station=SimpleNamespace(id=6719, station_type=SimpleNamespace(name="ТЭС")),
    )

    assert status == 400
    assert body == {
        "ok": False,
        "error": "Поле доступно только для электростанций СЭС и ВЭС",
    }


def test_owner_generation_patch_requires_edit_role(monkeypatch):
    import app.generation.routes.stations.station_details_routes as routes

    monkeypatch.setattr(
        routes,
        "save_station_owner_energy_generation_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not save")),
    )

    body, status = _request_owner_generation_patch(
        monkeypatch,
        {"kind": "owner_generation", "year": "2028", "value": "112,74", "orig": ""},
        roles=set(),
    )

    assert status == 403
    assert body == {"ok": False, "error": "Недостаточно прав"}


def test_energy_patch_rounding_keeps_zero_meaning_no_rounding():
    import app.generation.routes.stations.station_details_routes as routes

    app = Flask(__name__)
    with app.test_request_context("/?rounding_digits_gen=2"):
        assert routes._rounding_from_energy_payload({"rounding": "0"}) == 0
        assert routes._rounding_from_energy_payload({"rounding": "2"}) == 2
        assert routes._rounding_from_energy_payload({}) == 2
        assert routes._rounding_from_energy_payload({"rounding": "7"}) == 2
