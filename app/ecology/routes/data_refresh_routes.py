"""Ручное обновление страниц модуля «Экология»."""

from datetime import datetime, timezone

from flask import g, jsonify, request, url_for
from flask_login import login_required

from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.gis_tes_fuel_comparison_services import clear_comparison_cache


_PAGE_ENDPOINTS = frozenset(
    f"ecology_bp.{name}"
    for name in (
        "hub",
        "operating_tes_formulas",
        "gis_tek_pg",
        "gis_tek_pollutants",
        "gis_tes_fuel_comparison",
        "operating_tes_table",
        "new_tes_table",
        "calculation_summary",
        "totals_summary",
        "operating_tes_fuel_review",
    )
)


@ecology_bp.before_request
def capture_page_load_time():
    if request.method == "GET" and request.endpoint in _PAGE_ENDPOINTS:
        g.ecology_page_loaded_at = datetime.now(timezone.utc).isoformat()


@ecology_bp.context_processor
def inject_data_refresh():
    if request.endpoint not in _PAGE_ENDPOINTS or request.endpoint == "ecology_bp.hub":
        return {}
    return {
        "ecology_refresh": {
            "loadedAt": getattr(g, "ecology_page_loaded_at", None),
            "refreshUrl": url_for("ecology_bp.refresh_data"),
        }
    }


@ecology_bp.after_request
def prevent_stale_page_response(response):
    if request.endpoint in _PAGE_ENDPOINTS or request.endpoint == "ecology_bp.refresh_data":
        response.headers["Cache-Control"] = "no-store, private"
    return response


@ecology_bp.route("/refresh-data/", methods=["POST"])
@login_required
def refresh_data():
    # Страницы расчетов строятся из отчетных данных и сохраненных данных анализа при каждом запросе.
    # Сброс разбора листов также гарантирует, что обновленные источники анализа будут перечитаны.
    clear_comparison_cache()
    response = jsonify(ok=True)
    response.headers["Cache-Control"] = "no-store, private"
    return response
