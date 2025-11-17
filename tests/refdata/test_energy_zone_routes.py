import types
from unittest.mock import patch


def test_energy_zone_list_get_ok(client):
    with patch("app.refdata.routes.energy_systems.energy_zone_routes.get_energy_zone_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/energy_zone")
        assert resp.status_code == 200


def test_energy_zone_post_delete_redirects(client):
    with patch("app.refdata.routes.energy_systems.energy_zone_routes.delete_energy_zone_service") as m_delete, \
         patch("app.refdata.routes.energy_systems.energy_zone_routes.get_energy_zone_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "energy_zone_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/energy_zone", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_energy_zone_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.energy_systems.energy_zone_routes.export_energy_zone_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_energy_zone")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )












