import types
from unittest.mock import patch


def test_pgu_tes_machine_type_list_get_ok(client):
    with patch("app.refdata.routes.refdata_for_stations.machines.pgu_tes_machine_type_routes.get_pgu_tes_machine_type_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/pgu_tes_machine_type")
        assert resp.status_code == 200


def test_pgu_tes_machine_type_post_delete_redirects(client):
    with patch("app.refdata.routes.refdata_for_stations.machines.pgu_tes_machine_type_routes.delete_pgu_tes_machine_type_service") as m_delete, \
         patch("app.refdata.routes.refdata_for_stations.machines.pgu_tes_machine_type_routes.get_pgu_tes_machine_type_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "pgu_tes_machine_type_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/pgu_tes_machine_type", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_pgu_tes_machine_type_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.refdata_for_stations.machines.pgu_tes_machine_type_routes.export_pgu_tes_machine_type_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_pgu_tes_machine_type")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )














