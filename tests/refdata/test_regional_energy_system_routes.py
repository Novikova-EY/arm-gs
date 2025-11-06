import types
from unittest.mock import patch


def test_regional_energy_system_list_get_ok(client):
    with patch("app.refdata.routes.energy_systems.regional_energy_system_routes.get_regional_energy_system_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/regional_energy_system")
        assert resp.status_code == 200


def test_regional_energy_system_post_delete_redirects(client):
    with patch("app.refdata.routes.energy_systems.regional_energy_system_routes.delete_regional_energy_system_service") as m_delete, \
         patch("app.refdata.routes.energy_systems.regional_energy_system_routes.get_regional_energy_system_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "regional_energy_system_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/regional_energy_system", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_regional_energy_system_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.energy_systems.regional_energy_system_routes.export_regional_energy_system_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_regional_energy_system")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )









