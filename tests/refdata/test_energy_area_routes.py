import types
from unittest.mock import patch


def test_energy_area_list_get_ok(client):
    with (
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_energy_area_list") as m_get_list,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_regional_district_list_full") as m_rd,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_regional_energy_system_list_full") as m_res,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_union_energy_system_list_full") as m_ues,
    ):
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_rd.return_value = [(1, "РД 1"), (2, "РД 2")]
        m_res.return_value = [types.SimpleNamespace(id=1, name="РЭС 1")]
        m_ues.return_value = [types.SimpleNamespace(id=1, name="ОЭС 1")]

        resp = client.get("/refdata/energy_areas")
        assert resp.status_code == 200


def test_energy_area_post_delete_redirects(client):
    with (
        patch("app.refdata.routes.energy_systems.energy_area_routes.delete_energy_area_service") as m_delete,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_energy_area_list") as m_get_list,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_regional_district_list_full") as m_rd,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_regional_energy_system_list_full") as m_res,
        patch("app.refdata.routes.energy_systems.energy_area_routes.get_union_energy_system_list_full") as m_ues,
    ):
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_rd.return_value = []
        m_res.return_value = []
        m_ues.return_value = []
        form = {
            "energy_area_delete[]": ["1", "2"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/energy_areas", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_energy_area_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.energy_systems.energy_area_routes.export_energy_area_service") as m_export:
        buf = BytesIO(b"PK\x03\x04dummy-xlsx")
        m_export.return_value = buf
        resp = client.get("/refdata/export_energy_area_to_excel")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


