"""Проверка актуальности и ручное обновление всех HTML-страниц Спроса."""

from flask import g, jsonify, request, url_for
from flask_login import current_user, login_required

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.data_refresh_history import capture_history, history_response, history_status
from app.energy_consumption.routes.energy_consumption_bp import energy_consumption_bp
from app.energy_consumption.services.data_refresh_services import get_energy_consumption_data_revision
from app.energy_consumption.services.ec_display_cache import invalidate_energy_consumption_display_caches


_PAGE_ENDPOINTS = frozenset(
    f"energy_consumption_bp.{name}" for name in (
        "energy_consumption_formulas", "energy_consumption_summary_formulas",
        "russia_demand", "russia_with_nt_demand", "ees_russia_demand",
        "ees_russia_with_nt_demand", "ees_demand",
        "regional_energy_system_list", "regional_energy_system_demand",
        "energy_area_list", "energy_area_demand",
        "federal_district_list", "federal_district_demand",
        "energy_unit_list", "energy_unit_demand",
        "energy_zone_list", "energy_zone_demand",
        "regional_district_list", "regional_district_demand",
        "synchronous_area_list", "synchronous_area_demand",
        "union_energy_system_list", "union_energy_system_demand",
        "energy_system_type_list", "energy_system_type_demand",
        "summary_table_start", "summary_table_hub",
        "demand_summary_oes", "demand_summary_energy_zones", "demand_summary_federal_districts",
        "demand_summary_oes_gaes_charge", "demand_summary_federal_districts_gaes_charge",
        "demand_summary_energy_zones_gaes_charge", "demand_summary_table_oes",
        "demand_summary_table_oes_gaes_charge", "demand_summary_table_federal_districts",
        "demand_summary_table_federal_districts_gaes_charge",
        "demand_summary_table_energy_zones_gaes_charge", "demand_summary_table_energy_zones",
    )
)


def _revision():
    return f"{get_current_db_version_id()}:data:{get_energy_consumption_data_revision()}"


@energy_consumption_bp.before_request
def capture_page_revision():
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        if request.method == "POST" and request.endpoint in (
            "energy_consumption_bp.demand_summary_save_cell",
            "energy_consumption_bp.demand_summary_save_perimeter_variant",
            "energy_consumption_bp.demand_summary_save_block_variant",
            "energy_consumption_bp.demand_summary_persist_computed_rows",
        ) and current_user.is_authenticated:
            g.energy_consumption_save_revision = _revision()
            g.energy_consumption_saved_revisions = []
        return
    if request.endpoint in _PAGE_ENDPOINTS and current_user.is_authenticated:
        # Сохранение во время построения страницы тоже должно дать уведомление.
        g.energy_consumption_history = capture_history("consumption")
        g.energy_consumption_page_revision = _revision()


@energy_consumption_bp.context_processor
def inject_data_refresh():
    if request.endpoint not in _PAGE_ENDPOINTS or "energy_consumption_page_revision" not in g:
        return {}
    return {"energy_consumption_refresh": {
        "revision": g.energy_consumption_page_revision,
        "statusUrl": url_for("energy_consumption_bp.data_revision"),
        "refreshUrl": url_for("energy_consumption_bp.refresh_data"),
        "historyUrl": url_for("energy_consumption_bp.data_changes"),
        **g.get("energy_consumption_history", {}),
    }}


@energy_consumption_bp.after_request
def prevent_stale_page_response(response):
    if request.endpoint == "energy_consumption_bp.data_changes":
        response.headers["Cache-Control"] = "no-store, private"
    if request.endpoint in _PAGE_ENDPOINTS or request.endpoint in (
        "energy_consumption_bp.demand_summary_oes_data",
        "energy_consumption_bp.demand_summary_energy_zones_data",
        "energy_consumption_bp.demand_summary_federal_districts_data",
    ):
        response.headers["Cache-Control"] = "no-store, private"
    saved_revisions = g.get("energy_consumption_saved_revisions", [])
    if response.is_json and 200 <= response.status_code < 300 and saved_revisions:
        before = g.energy_consumption_save_revision
        version, revision = before.rsplit(":data:", 1)
        # Подтверждаем только собственные commit без чужих изменений между ними.
        expected = list(range(int(revision) + 1, int(revision) + len(saved_revisions) + 1))
        if saved_revisions == expected:
            response.headers["X-Consumption-Revision-Before"] = before
            response.headers["X-Consumption-Revision"] = f"{version}:data:{saved_revisions[-1]}"
    return response


@energy_consumption_bp.route("/data-revision/", methods=["GET"])
@login_required
def data_revision():
    history = history_status("consumption")
    response = jsonify(ok=True, revision=_revision(), **({"history": history} if history is not None else {}))
    response.headers["Cache-Control"] = "no-store, private"
    return response


@energy_consumption_bp.route("/refresh-data/", methods=["POST"])
@login_required
def refresh_data():
    invalidate_energy_consumption_display_caches(version_id=get_current_db_version_id())
    response = jsonify(ok=True, revision=_revision())
    response.headers["Cache-Control"] = "no-store, private"
    return response


@energy_consumption_bp.route("/data-changes/", methods=["GET"])
@login_required
def data_changes():
    return history_response("consumption")
