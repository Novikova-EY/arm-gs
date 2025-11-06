import io
import types
from unittest.mock import patch


def test_fuel_list_get_ok(client, dummy_pagination):
    with patch("app.refdata.routes.fuels.fuel_routes.get_fuel_list") as m_get_list, \
         patch("app.refdata.routes.fuels.fuel_routes.choices_cache.get_choices") as m_choices:
        m_get_list.return_value = dummy_pagination(items=[], page=1, per_page=20, total=0)
        m_choices.return_value = [(1, "Тип 1"), (2, "Тип 2")]

        resp = client.get("/refdata/fuel")
        assert resp.status_code == 200


def test_fuel_list_post_delete_redirects(client):
    with patch("app.refdata.routes.fuels.fuel_routes.delete_fuel_service") as m_delete, \
         patch("app.refdata.routes.fuels.fuel_routes.get_fuel_list") as m_get_list, \
         patch("app.refdata.routes.fuels.fuel_routes.choices_cache.get_choices") as m_choices:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_choices.return_value = []
        form = {
            "fuel_delete[]": ["1", "2"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/fuel", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert m_delete.called


def test_fuel_list_post_update_validation_error(client):
    with patch("app.refdata.routes.fuels.fuel_routes.update_fuel_service") as m_update, \
         patch("app.refdata.routes.fuels.fuel_routes.get_fuel_list") as m_get_list, \
         patch("app.refdata.routes.fuels.fuel_routes.choices_cache.get_choices") as m_choices:
        m_get_list.return_value = types.SimpleNamespace(items=[], page=1, per_page=20, total=0)
        m_choices.return_value = []
        m_update.side_effect = ValueError("bad data")

        form = {
            "fuel_ids[]": ["1"],
            "fuel_names[]": ["Газ"],
            "fuel_types[]": ["2"],
            "page": "1",
            "per_page": "20",
        }
        resp = client.post("/refdata/fuel", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)


def test_export_fuel_ok(client, dummy_excel_bytes):
    with patch("app.refdata.routes.fuels.fuel_routes.export_fuel_service") as m_export:
        m_export.return_value = dummy_excel_bytes()
        resp = client.get("/refdata/export_fuel")
        assert resp.status_code == 200
        assert resp.headers.get("Content-Type").startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


def test_add_fuel_post_ok(client):
    with patch("app.refdata.routes.fuels.fuel_routes.add_fuel_service") as m_add, \
         patch("app.refdata.routes.fuels.fuel_routes.fuel_query") as m_query, \
         patch("app.refdata.routes.fuels.fuel_routes.choices_cache.get_choices") as m_choices:
        m_choices.return_value = []
        m_add.return_value = None
        m_query.return_value = types.SimpleNamespace(count=lambda: 21)

        form = {
            "name": "Новое топливо",
            "fuel_type": "1",
        }
        resp = client.post("/refdata/add_fuel?page=1&per_page=20", data=form, follow_redirects=False)
        assert resp.status_code in (302, 303)









