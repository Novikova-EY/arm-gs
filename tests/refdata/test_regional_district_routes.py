import types
from unittest.mock import patch


def test_regional_district_list_get_ok(client):
    with patch("app.refdata.routes.territories.regional_district_routes.get_regional_district_list") as m_get_list, \
         patch("app.refdata.routes.territories.regional_district_routes.get_energy_zone_list_full") as m_ez, \
         patch("app.refdata.routes.territories.regional_district_routes.get_synchronous_area_list_full") as m_sa, \
         patch("app.refdata.routes.territories.regional_district_routes.choices_cache.get_choices") as m_choices:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_ez.return_value = []
        m_sa.return_value = []
        m_choices.return_value = []
        resp = client.get("/refdata/regional_district")
        assert resp.status_code == 200


def test_regional_district_post_delete_redirects(client):
    with patch("app.refdata.routes.territories.regional_district_routes.delete_regional_district_service") as m_delete, \
         patch("app.refdata.routes.territories.regional_district_routes.get_regional_district_list") as m_get_list, \
         patch("app.refdata.routes.territories.regional_district_routes.get_energy_zone_list_full") as m_ez, \
         patch("app.refdata.routes.territories.regional_district_routes.get_synchronous_area_list_full") as m_sa, \
         patch("app.refdata.routes.territories.regional_district_routes.choices_cache.get_choices") as m_choices:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_ez.return_value = []
        m_sa.return_value = []
        m_choices.return_value = []
        form = {
            "regional_district_delete[]": ["1"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/regional_district", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_export_regional_district_ok(client):
    from io import BytesIO
    with patch("app.refdata.routes.territories.regional_district_routes.export_regional_district_service") as m_export:
        m_export.return_value = BytesIO(b"PK\x03\x04dummy-xlsx")
        resp = client.get("/refdata/export_regional_district")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )









