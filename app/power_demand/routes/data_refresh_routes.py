"""Проверка актуальности и ручное обновление всех HTML-страниц Нагрузок."""

from flask import g, jsonify, request, url_for
from flask_login import current_user, login_required

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.data_refresh_history import capture_history, history_response, history_status
from app.power_demand.routes.power_demand_bp import power_demand_bp
from app.power_demand.services.data_refresh_services import get_power_demand_data_revision
from app.power_demand.services.pd_summary_page_cache import invalidate_power_demand_display_caches


_PAGE_ENDPOINTS = frozenset(
    f"power_demand_bp.{name}" for name in (
        "power_demand_formulas",
        "power_demand_summary_formulas",
        "russia_demand",
        "russia_with_nt_demand",
        "ees_russia_demand",
        "ees_russia_with_nt_demand",
        "ees_demand",
        "ees_with_nt_demand",
        "regional_energy_system_list",
        "regional_energy_system_demand",
        "energy_area_list",
        "energy_area_demand",
        "federal_district_list",
        "federal_district_demand",
        "energy_unit_list",
        "energy_unit_demand",
        "energy_zone_list",
        "energy_zone_demand",
        "regional_district_list",
        "regional_district_demand",
        "synchronous_area_list",
        "synchronous_area_demand",
        "synchronous_area_with_nt_demand",
        "union_energy_system_list",
        "union_energy_system_demand",
        "energy_system_type_list",
        "energy_system_type_demand",
        "demand_summary_oes",
        "demand_summary_energy_zones",
        "demand_summary_federal_districts",
        "demand_summary_oes_coeff",
        "demand_summary_federal_districts_coeff",
        "demand_summary_energy_zones_coeff",
        "ozp_maxima",
    )
)


def _revision():
    return f"{get_current_db_version_id()}:data:{get_power_demand_data_revision()}"


@power_demand_bp.before_request
def capture_page_revision():
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if request.method == "POST" and (request.endpoint in (
            "power_demand_bp.demand_summary_save_cell",
            "power_demand_bp.demand_summary_save_perimeter_variant",
            "power_demand_bp.demand_summary_save_block_variant",
            "power_demand_bp.ozp_maxima_save",
            "power_demand_bp.power_demand_formulas_save",
            "power_demand_bp.power_demand_formulas_reset",
            "power_demand_bp.power_demand_summary_formulas_save",
            "power_demand_bp.power_demand_summary_formulas_reset",
        ) or request.endpoint in _PAGE_ENDPOINTS) and current_user.is_authenticated:
            g.power_demand_save_revision = _revision()
            g.power_demand_saved_revisions = []
        return
    if request.endpoint in _PAGE_ENDPOINTS and current_user.is_authenticated:
        # Сохранение во время построения страницы тоже должно дать уведомление.
        g.power_demand_history = capture_history("demand")
        g.power_demand_page_revision = _revision()


@power_demand_bp.context_processor
def inject_data_refresh():
    if request.endpoint not in _PAGE_ENDPOINTS or "power_demand_page_revision" not in g:
        return {}
    return {"power_demand_refresh": {
        "revision": g.power_demand_page_revision,
        "statusUrl": url_for("power_demand_bp.data_revision"),
        "refreshUrl": url_for("power_demand_bp.refresh_data"),
        "historyUrl": url_for("power_demand_bp.data_changes"),
        **g.get("power_demand_history", {}),
    }}


@power_demand_bp.after_request
def prevent_stale_page_response(response):
    if request.endpoint == "power_demand_bp.data_changes":
        response.headers["Cache-Control"] = "no-store, private"
    if request.endpoint in _PAGE_ENDPOINTS or request.endpoint in (
        "power_demand_bp.demand_summary_oes_data",
        "power_demand_bp.demand_summary_energy_zones_data",
        "power_demand_bp.demand_summary_federal_districts_data",
        "power_demand_bp.demand_summary_oes_coeff_data",
        "power_demand_bp.demand_summary_energy_zones_coeff_data",
        "power_demand_bp.demand_summary_federal_districts_coeff_data",
    ):
        response.headers["Cache-Control"] = "no-store, private"
    saved_revisions = g.get("power_demand_saved_revisions", [])
    if response.is_json and 200 <= response.status_code < 300 and saved_revisions:
        before = g.power_demand_save_revision
        version, revision = before.rsplit(":data:", 1)
        # Подтверждаем только собственные commit без чужих изменений между ними.
        expected = list(range(int(revision) + 1, int(revision) + len(saved_revisions) + 1))
        if saved_revisions == expected:
            response.headers["X-Power-Demand-Revision-Before"] = before
            response.headers["X-Power-Demand-Revision"] = f"{version}:data:{saved_revisions[-1]}"
    return response


@power_demand_bp.route("/data-revision/", methods=["GET"])
@login_required
def data_revision():
    history = history_status("demand")
    response = jsonify(ok=True, revision=_revision(), **({"history": history} if history is not None else {}))
    response.headers["Cache-Control"] = "no-store, private"
    return response


@power_demand_bp.route("/refresh-data/", methods=["POST"])
@login_required
def refresh_data():
    invalidate_power_demand_display_caches()
    response = jsonify(ok=True, revision=_revision())
    response.headers["Cache-Control"] = "no-store, private"
    return response


@power_demand_bp.route("/data-changes/", methods=["GET"])
@login_required
def data_changes():
    return history_response("demand")
