# -*- coding: utf-8 -*-
from datetime import datetime

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.access_services import can_edit_energy_balance
from app.energy_balance.services.ee_receive_transfer_oes_export_services import (
    export_ee_receive_transfer_oes_to_excel,
)
from app.energy_balance.services.ee_receive_transfer_oes_page_services import (
    get_ee_receive_transfer_oes_page_data,
)
from app.energy_balance.services.ee_receive_transfer_oes_value_services import (
    update_ee_receive_transfer_oes_value,
)
from app.energy_balance.services.ee_transfers_page_services import format_transfer_cell
from app.energy_balance.services.ee_balance_page_services import get_ee_balance_filter_year_list
from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
    resolve_ee_transfers_year_range,
)


def _year_filters() -> tuple[int, int]:
    if request.method == "GET":
        return resolve_ee_transfers_year_range()
    default_start = get_ee_default_start_year()
    default_end = get_ee_default_end_year()
    try:
        start_year = int(request.values.get("start_year", default_start))
    except (TypeError, ValueError):
        start_year = default_start
    try:
        end_year = int(request.values.get("end_year", default_end))
    except (TypeError, ValueError):
        end_year = default_end
    return (end_year, start_year) if start_year > end_year else (start_year, end_year)


def _rounding_digits() -> int:
    try:
        digits = int(request.values.get("rounding_digits", "1"))
    except (TypeError, ValueError):
        return 1
    return digits if digits >= -1 else 1


def _page_redirect(*, imported_year: int | None = None):
    start_year, end_year = _year_filters()
    if imported_year is not None:
        start_year = min(start_year, imported_year)
        end_year = max(end_year, imported_year)
    return redirect(
        url_for(
            "energy_balance_bp.ee_receive_transfer_oes",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=_rounding_digits(),
        )
    )


@energy_balance_bp.route("/ee_receive_transfer_oes/")
@login_required
def ee_receive_transfer_oes():
    start_year, end_year = _year_filters()
    rounding_digits = _rounding_digits()
    direction_filter = request.args.getlist("direction_filter")
    oes_filter = request.args.getlist("country_filter", type=int)
    source_ues_filter = request.args.getlist("union_energy_system_filter", type=int)
    page_data = get_ee_receive_transfer_oes_page_data(
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        direction_filter=direction_filter,
        oes_filter=oes_filter,
        filters={"union_energy_system_filter": source_ues_filter},
    )
    page_data["can_edit"] = can_edit_energy_balance(current_user)
    filter_year_list = sorted(set(get_ee_balance_filter_year_list()) | {start_year, end_year})
    return render_template(
        "energy_balance/ee_import_export/ee_import_export.html",
        **page_data,
        filter_year_list=filter_year_list,
        rounding_digits=rounding_digits,
        page_variant=True,
        page_title="Прием/Передача электрической энергии между ОЭС",
        page_endpoint="energy_balance_bp.ee_receive_transfer_oes",
        save_endpoint="energy_balance_bp.ee_receive_transfer_oes_value",
        export_endpoint="energy_balance_bp.export_ee_receive_transfer_oes",
    )


@energy_balance_bp.route("/ee_receive_transfer_oes/value/", methods=["PATCH"])
@login_required
def ee_receive_transfer_oes_value():
    data = request.get_json(silent=True) or {}
    try:
        source_ues_id = int(data.get("ues_id"))
        target_ues_id = int(data.get("country_id"))
        year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверные данные ячейки"), 400

    try:
        saved = update_ee_receive_transfer_oes_value(
            source_ues_id=source_ues_id,
            target_ues_id=target_ues_id,
            year=year,
            raw_value=data.get("value"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить плановый прием/передачу ЭЭ по ОЭС")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500

    value = saved["value"]
    direction = None if value is None else ("receive" if value >= 0 else "transfer")
    return jsonify(
        ok=True,
        raw="" if value is None else str(value),
        display="" if value is None else format_transfer_cell(value, _rounding_digits()),
        direction=direction,
    )


@energy_balance_bp.route("/ee_receive_transfer_oes/export/")
@login_required
def export_ee_receive_transfer_oes():
    start_year, end_year = _year_filters()
    try:
        excel_file = export_ee_receive_transfer_oes_to_excel(
            start_year=start_year,
            end_year=end_year,
            rounding_digits=_rounding_digits(),
            direction_filter=request.args.getlist("direction_filter"),
            oes_filter=request.args.getlist("country_filter", type=int),
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта приема/передачи ЭЭ по ОЭС: %s", exc, exc_info=True)
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return _page_redirect()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Прием_Передача_ЭЭ_по_ОЭС_{timestamp}.xlsx",
    )
