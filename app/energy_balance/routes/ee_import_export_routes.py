# -*- coding: utf-8 -*-
from datetime import datetime

from flask import current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.ee_import_export_export_services import (
    export_ee_import_export_to_excel,
)
from app.energy_balance.services.ee_import_export_page_services import (
    get_ee_import_export_page_data,
)
from app.energy_balance.services.ee_transfers_import_services import (
    import_ee_transfers_from_excel,
)
from app.energy_balance.services.ee_import_export_value_services import (
    update_ee_import_export_value,
)
from app.energy_balance.services.ee_transfers_page_services import format_transfer_cell
from app.energy_balance.services.ee_balance_page_services import (
    get_ee_balance_filter_year_list,
)
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
            "energy_balance_bp.ee_import_export",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=_rounding_digits(),
        )
    )


@energy_balance_bp.route("/ee_import_export/")
@login_required
def ee_import_export():
    start_year, end_year = _year_filters()
    rounding_digits = _rounding_digits()
    direction_filter = request.args.getlist("direction_filter")
    country_filter = request.args.getlist("country_filter", type=int)
    page_data = get_ee_import_export_page_data(
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        direction_filter=direction_filter,
        country_filter=country_filter,
    )
    page_data["can_edit"] = True
    filter_year_list = sorted(set(get_ee_balance_filter_year_list()) | {start_year, end_year})
    return render_template(
        "energy_balance/ee_import_export/ee_import_export.html",
        **page_data,
        filter_year_list=filter_year_list,
        rounding_digits=rounding_digits,
    )


@energy_balance_bp.route("/ee_import_export/value/", methods=["PATCH"])
@login_required
def ee_import_export_value():
    data = request.get_json(silent=True) or {}
    try:
        ues_id = int(data.get("ues_id"))
        country_id = int(data.get("country_id"))
        year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверные данные ячейки"), 400

    try:
        saved = update_ee_import_export_value(
            ues_id=ues_id,
            country_id=country_id,
            year=year,
            direction=data.get("direction"),
            raw_value=data.get("value"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить плановый импорт/экспорт ЭЭ")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500

    value = saved["value"]
    if value is None or value == 0:
        direction = None
    else:
        direction = "import" if value > 0 else "export"
    digits = data.get("rounding_digits", request.args.get("rounding_digits", 1))
    try:
        digits = int(digits)
    except (TypeError, ValueError):
        digits = 1
    if digits < -1:
        digits = 1
    return jsonify(
        ok=True,
        year=year,
        raw="" if value is None else str(value),
        display="" if value is None else format_transfer_cell(value, digits),
        direction=direction,
    )


@energy_balance_bp.route("/ee_import_export/export/")
@login_required
def export_ee_import_export():
    start_year, end_year = _year_filters()
    try:
        excel_file = export_ee_import_export_to_excel(
            start_year=start_year,
            end_year=end_year,
            rounding_digits=_rounding_digits(),
            direction_filter=request.args.getlist("direction_filter"),
            country_filter=request.args.getlist("country_filter", type=int),
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта импорта/экспорта ЭЭ: %s", exc, exc_info=True)
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return _page_redirect()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Импорт_Экспорт_ЭЭ_{timestamp}.xlsx",
    )


@energy_balance_bp.route("/ee_import_export/import/", methods=["POST"])
@login_required
def import_ee_import_export():
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Файл не выбран.", "danger")
        return _page_redirect()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("Неверный формат файла. Ожидается .xlsx или .xls.", "danger")
        return _page_redirect()

    try:
        result = import_ee_transfers_from_excel(
            file,
            session.get("username", "Неизвестный пользователь"),
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return _page_redirect()
    except Exception as exc:
        current_app.logger.error("Ошибка импорта данных ЭЭ: %s", exc, exc_info=True)
        flash("Ошибка импорта данных. Пожалуйста, попробуйте снова.", "danger")
        return _page_redirect()

    flash(result["message"], "warning" if result.get("errors_count") else "success")
    for error in (result.get("errors") or [])[:8]:
        flash(error, "warning")
    return _page_redirect(imported_year=result.get("year_number"))
