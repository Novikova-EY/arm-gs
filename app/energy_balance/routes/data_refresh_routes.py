"""Проверка актуальности таблиц и ручное обновление кеша энергобалансов."""

from flask import g, jsonify, request, url_for
from flask_login import login_required

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.data_refresh_history import capture_history, history_response, history_status
from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.energy_balance_cache import (
    clear_energy_balance_cache,
    get_energy_balance_data_revision,
)


_TABLE_ENDPOINTS = frozenset(
    f"energy_balance_bp.{name}" for name in (
        "ee_balance_table", "power_balance_table", "ee_balance_tes_forecast",
        "ee_balance_ves_ses", "ee_balance_aes", "ee_balance_ges", "ee_balance_gaes",
        "ee_balance_snee", "ee_generation", "ee_generation_totals_summary",
        "ee_transfers", "ee_import_export", "ee_receive_transfer_oes",
    )
)


def _revision():
    return f"{get_current_db_version_id()}:data:{get_energy_balance_data_revision()}"


@energy_balance_bp.before_request
def capture_table_revision():
    if request.endpoint in _TABLE_ENDPOINTS:
        # Читаем до построения таблицы: сохранение во время построения тоже даст уведомление.
        g.energy_balance_history = capture_history("balance")
        g.energy_balance_page_revision = _revision()


@energy_balance_bp.context_processor
def inject_data_refresh():
    if request.endpoint not in _TABLE_ENDPOINTS:
        return {}
    return {"energy_balance_refresh": {
        "revision": g.energy_balance_page_revision,
        "statusUrl": url_for("energy_balance_bp.data_revision"),
        "refreshUrl": url_for("energy_balance_bp.refresh_data"),
        "historyUrl": url_for("energy_balance_bp.data_changes"),
        **g.get("energy_balance_history", {}),
    }}


@energy_balance_bp.after_request
def prevent_stale_table_response(response):
    if request.endpoint == "energy_balance_bp.data_changes":
        response.headers["Cache-Control"] = "no-store, private"
    if request.endpoint in _TABLE_ENDPOINTS:
        response.headers["Cache-Control"] = "no-store, private"
    return response


@energy_balance_bp.route("/data-revision/", methods=["GET"])
@login_required
def data_revision():
    history = history_status("balance")
    response = jsonify(ok=True, revision=_revision(), **({"history": history} if history is not None else {}))
    response.headers["Cache-Control"] = "no-store, private"
    return response


@energy_balance_bp.route("/refresh-data/", methods=["POST"])
@login_required
def refresh_data():
    clear_energy_balance_cache()
    response = jsonify(ok=True, revision=_revision())
    response.headers["Cache-Control"] = "no-store, private"
    return response


@energy_balance_bp.route("/data-changes/", methods=["GET"])
@login_required
def data_changes():
    return history_response("balance")
