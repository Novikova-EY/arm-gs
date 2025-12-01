import types
from unittest.mock import patch


def test_gen_company_list_get_ok(client):
    with patch("app.refdata.routes.gen_companies.gen_company_routes.get_gen_company_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        resp = client.get("/refdata/gen_company")
        assert resp.status_code == 200


def test_gen_company_post_delete_redirects(client):
    with patch("app.refdata.routes.gen_companies.gen_company_routes.delete_gen_company_service") as m_delete, \
         patch("app.refdata.routes.gen_companies.gen_company_routes.get_gen_company_list") as m_get_list:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        form = {
            "gen_company_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/gen_company", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_gen_company_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.gen_companies.gen_company_routes.export_gen_company_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_gen_company")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )














