from werkzeug.datastructures import ImmutableMultiDict

from app.electrical_intensity.services import electrical_intensity_services as eis
from app.electrical_intensity.services.electrical_intensity_services import (
    save_electrical_intensity_from_post,
)


def test_clearing_an_already_empty_cell_is_an_idempotent_success(app, monkeypatch):
    monkeypatch.setattr(eis, "get_current_version", lambda: 20)
    monkeypatch.setattr(eis, "_ei_current_year_number", lambda: 2025)
    monkeypatch.setattr(eis, "_username", lambda: "tester")
    monkeypatch.setattr(eis, "_refdata_ved_ids", lambda version_id: frozenset())
    monkeypatch.setattr(eis, "_refdata_ved_types_for_version", lambda version_id: [])
    monkeypatch.setattr(eis, "_preload_rf_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_fd_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_year_row_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_rf_coef_row", lambda version_id: None)
    monkeypatch.setattr(eis, "_preload_fd_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_population_coef_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "_preload_fd_total_k_cache", lambda version_id: {})
    monkeypatch.setattr(eis, "queue_electrical_intensity_cell_change", lambda *a, **k: None)

    form = ImmutableMultiDict([
        ("territory_kind[]", "rf"),
        ("territory_id[]", ""),
        ("cell_ved_id[]", ""),
        ("row_kind[]", "intensity"),
        ("cell_year[]", "2026"),
        ("cell_value[]", ""),
    ])

    with app.app_context(), app.test_request_context():
        updated, skipped = save_electrical_intensity_from_post(form)

    assert (updated, skipped) == (0, 0)
