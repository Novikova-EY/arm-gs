from unittest.mock import Mock

import pytest

from app.electrical_intensity.routes import electrical_intensity_fo_routes as routes
from app.electrical_intensity.routes.electrical_intensity_root_bp import (
    electrical_intensity_root_bp,
)


@pytest.fixture
def electrical_intensity_client(app):
    app.register_blueprint(electrical_intensity_root_bp)
    return app.test_client()


def test_save_cell_rejects_non_numeric_value_before_writing(
    electrical_intensity_client, monkeypatch
):
    monkeypatch.setattr(routes, "current_user", type("User", (), {"has_admin": True})())
    monkeypatch.setattr(routes, "csrf_ok", lambda: True)
    save = Mock()
    monkeypatch.setattr(routes, "save_electrical_intensity_from_post", save)

    response = electrical_intensity_client.post(
        "/electrical_intensity_fo/save_cell",
        data={
            "territory_kind[]": "rf",
            "territory_id[]": "",
            "cell_ved_id[]": "",
            "row_kind[]": "intensity",
            "cell_year[]": "2028",
            "cell_value[]": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert response.json == {"ok": False, "error": "Введите числовое значение."}
    save.assert_not_called()


@pytest.mark.parametrize(
    "data",
    [
        {
            "territory_kind[]": "rf",
            "territory_id[]": "",
            "cell_ved_id[]": "",
            "row_kind[]": "intensity",
            "cell_year[]": "2028",
            "cell_value[]": "12,5",
        },
        {
            "coef_territory_kind[]": "rf",
            "coef_territory_id[]": "",
            "coef_ved_id[]": "",
            "coef_a[]": "0.85",
        },
        {
            "fd_total_k_territory_kind[]": "fd",
            "fd_total_k_territory_id[]": "10",
            "fd_total_k_row_kind[]": "fd_network_losses",
            "fd_total_k_value[]": "",
        },
    ],
)
def test_save_cell_commits_one_supported_electrical_intensity_field(
    electrical_intensity_client, monkeypatch, data
):
    monkeypatch.setattr(routes, "current_user", type("User", (), {"has_admin": True})())
    monkeypatch.setattr(routes, "csrf_ok", lambda: True)
    save = Mock(return_value=(1, 0))
    commit = Mock()
    invalidate = Mock()
    monkeypatch.setattr(routes, "save_electrical_intensity_from_post", save)
    monkeypatch.setattr(routes.db.session, "commit", commit)
    monkeypatch.setattr(routes, "get_current_version", lambda: 7)
    monkeypatch.setattr(routes, "invalidate_economics_fd_data_cache", invalidate)

    response = electrical_intensity_client.post(
        "/electrical_intensity_fo/save_cell", data=data
    )

    assert response.status_code == 200
    assert response.json == {"ok": True, "updated": 1}
    save.assert_called_once()
    commit.assert_called_once()
    invalidate.assert_called_once_with(7, *routes._EI_CACHE_DATASETS)


def test_live_save_accepts_clearing_an_already_empty_cell(
    electrical_intensity_client, monkeypatch
):
    monkeypatch.setattr(routes, "current_user", type("User", (), {"has_admin": True})())
    monkeypatch.setattr(routes, "csrf_ok", lambda: True)
    monkeypatch.setattr(routes, "save_electrical_intensity_from_post", Mock(return_value=(0, 0)))
    monkeypatch.setattr(routes.db.session, "commit", Mock())

    response = electrical_intensity_client.post(
        "/electrical_intensity_fo/save_cell",
        data={
            "territory_kind[]": "rf",
            "territory_id[]": "",
            "cell_ved_id[]": "",
            "row_kind[]": "intensity",
            "cell_year[]": "2028",
            "cell_value[]": "",
        },
    )

    assert response.status_code == 200
    assert response.json == {"ok": True, "updated": 0}


def test_electrical_intensity_templates_enable_cell_feedback_and_live_save(app):
    app.jinja_env.get_template("electrical_intensity/electrical_intensity.html")
    app.jinja_env.get_template("electrical_intensity/electrical_intensity_formulas.html")
    page, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity.html"
    )
    formulas, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity_formulas.html"
    )

    assert "electrical_intensity_save_cell" in page
    assert "electrical_intensity/live_save.js" in page
    assert ".is-save-success" in page
    assert ".is-save-error" in page
    assert 'data-live-save="electrical-intensity"' in formulas
