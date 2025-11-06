import types
from unittest.mock import patch


def test_synchronous_area_list_get_ok(client):
    with patch("app.refdata.routes.energy_systems.synchronous_area_routes.get_synchronous_area_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/synchronous_area")
        assert resp.status_code == 200


def test_synchronous_area_post_delete_redirects(client):
    with patch("app.refdata.routes.energy_systems.synchronous_area_routes.delete_synchronous_area_service") as m_delete, \
         patch("app.refdata.routes.energy_systems.synchronous_area_routes.get_synchronous_area_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "synchronous_area_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/synchronous_area", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_synchronous_area_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.energy_systems.synchronous_area_routes.export_synchronous_area_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_synchronous_area")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )









