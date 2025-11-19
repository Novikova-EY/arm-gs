import types
from unittest.mock import patch


def test_fuel_type_list_get_ok(client):
    with patch("app.refdata.routes.fuels.fuel_type_routes.get_fuel_type_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/fuel_type")
        assert resp.status_code == 200


def test_fuel_type_post_delete_redirects(client):
    with patch("app.refdata.routes.fuels.fuel_type_routes.delete_fuel_type_service") as m_delete, \
         patch("app.refdata.routes.fuels.fuel_type_routes.get_fuel_type_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "fuel_type_delete[]": ["1", "2"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/fuel_type", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_fuel_type_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.fuels.fuel_type_routes.export_fuel_type_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_fuel_type")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )













