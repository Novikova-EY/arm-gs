from app.ecology.services import operating_tes_page_services as page


def test_characteristic_notes_are_independent_by_territory_and_affiliation(operating_tes_db):
    page.upsert_characteristic("vsego", "gas_natural", 2026, "note", "Общее примечание")
    page.upsert_characteristic("centr", "gas_natural", 2026, "note", "Примечание Центра")
    page.upsert_characteristic(
        "centr", "gas_natural", 2026, "note", "Примечание Минэнерго", affiliation="minen"
    )

    overrides = page.load_characteristic_overrides([2026])

    assert page.resolve_chars("gas_natural", 2026, overrides, "vsego", "all")["note"] == "Общее примечание"
    assert page.resolve_chars("gas_natural", 2026, overrides, "centr", "all")["note"] == "Примечание Центра"
    assert page.resolve_chars("gas_natural", 2026, overrides, "centr", "minen")["note"] == "Примечание Минэнерго"


def test_characteristic_note_update_route_accepts_text(operating_tes_db, monkeypatch):
    from types import SimpleNamespace
    from flask import Flask
    from app.ecology.routes import operating_tes_routes as routes

    monkeypatch.setattr(routes, "can_edit_ecology", lambda user: True)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace())
    app = Flask(__name__)
    with app.test_request_context(json={
        "year": 2026,
        "row_key": "gas_natural",
        "field": "note",
        "affiliation": "prompred",
        "value": "Комментарий к характеристике топлива",
    }, method="PATCH"):
        response = routes.operating_tes_update_value.__wrapped__("centr", "khar-topl")

    assert response.json == {"ok": True}
    overrides = page.load_characteristic_overrides([2026])
    assert overrides[("centr", "prompred", "gas_natural", 2026)]["note"] == "Комментарий к характеристике топлива"
