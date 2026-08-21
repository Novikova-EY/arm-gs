# -*- coding: utf-8 -*-
from datetime import datetime

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.ee_balance_custom_flow_services import (
    add_custom_flow_row,
    delete_custom_flow_row,
    update_custom_flow_label,
    update_custom_flow_value,
)
from app.energy_balance.services.ee_balance_excel_services import export_ee_balance_to_excel
from app.energy_balance.services.ee_balance_export_services import (
    update_ee_balance_export_value,
)
from app.energy_balance.services.ee_balance_page_services import (
    build_ee_balance_table_context,
    format_ee_balance_cell,
    get_ee_balance_sheet,
    get_ee_balance_sheets,
    group_ee_balance_sheets,
    is_persistable_ee_balance_slug,
    resolve_ee_balance_rounding_digits,
)


@energy_balance_bp.route("/ee_balance/")
@login_required
def ee_balance_hub():
    """Хабы листов расчета балансов электрической энергии (по макету БЭ_ЕЭС)."""
    sheets = get_ee_balance_sheets()
    return render_template(
        "energy_balance/ee_balance/ee_balance_hub.html",
        sheets=sheets,
        sheet_groups=group_ee_balance_sheets(sheets),
    )


@energy_balance_bp.route("/ee_balance/export/")
@login_required
def export_ee_balance():
    """Выгрузка всех листов баланса электрической энергии в один Excel (вкладка = лист)."""
    try:
        excel_file = export_ee_balance_to_excel(
            start_year=request.args.get("start_year"),
            end_year=request.args.get("end_year"),
            rounding_digits=request.args.get("rounding_digits"),
            include_type_breakdown=request.args.get("include_type_breakdown") == "1",
            show_empty_rows=request.args.get("show_empty_rows", "1") != "0",
            show_flow_rows=request.args.get("show_flow_rows", "1") != "0",
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта баланса электрической энергии: %s", exc, exc_info=True)
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return redirect(request.referrer or url_for("energy_balance_bp.ee_balance_hub"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Баланс_электрической_энергии_{timestamp}.xlsx",
    )


@energy_balance_bp.route("/ee_balance/<slug>/")
@login_required
def ee_balance_table(slug: str):
    """Таблица баланса электрической энергии выбранного листа макета."""
    context = build_ee_balance_table_context(
        slug,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
    )
    if context is None:
        abort(404)
    return render_template(
        "energy_balance/ee_balance/ee_balance_table.html",
        **context,
    )


def _require_sheet(slug: str) -> dict:
    sheet = get_ee_balance_sheet(slug)
    if sheet is not None:
        return sheet
    wanted = str(slug or "").strip()
    if is_persistable_ee_balance_slug(wanted):
        return {"slug": wanted, "sheet_name": wanted}
    abort(404)


@energy_balance_bp.route("/ee_balance/<slug>/custom_flow/", methods=["POST"])
@login_required
def ee_balance_custom_flow_add(slug: str):
    _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    direction = str(data.get("direction") or "").strip()
    parent_key = str(data.get("parent_key") or direction).strip()
    try:
        row = add_custom_flow_row(
            slug,
            direction,
            label=str(data.get("label") or ""),
            parent_key=parent_key or None,
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось добавить строку перетока баланса электрической энергии")
        return jsonify(ok=False, error="Не удалось добавить строку"), 500
    return jsonify(ok=True, row=row)


@energy_balance_bp.route(
    "/ee_balance/<slug>/custom_flow/<int:row_id>/",
    methods=["PATCH", "DELETE"],
)
@login_required
def ee_balance_custom_flow_item(slug: str, row_id: int):
    _require_sheet(slug)
    if request.method == "DELETE":
        try:
            deleted = delete_custom_flow_row(slug, row_id)
        except Exception:
            current_app.logger.exception("Не удалось удалить строку перетока баланса электрической энергии")
            return jsonify(ok=False, error="Не удалось удалить строку"), 500
        if not deleted:
            return jsonify(ok=False, error="Строка не найдена"), 404
        return jsonify(ok=True)

    data = request.get_json(silent=True) or {}
    if "label" in data and "year" not in data:
        try:
            row = update_custom_flow_label(slug, row_id, str(data.get("label") or ""))
        except Exception:
            current_app.logger.exception("Не удалось сохранить наименование перетока баланса электрической энергии")
            return jsonify(ok=False, error="Не удалось сохранить наименование"), 500
        if row is None:
            return jsonify(ok=False, error="Строка не найдена"), 404
        return jsonify(ok=True, row=row)

    if "year" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    try:
        saved = update_custom_flow_value(slug, row_id, data.get("year"), data.get("value"))
    except KeyError:
        return jsonify(ok=False, error="Строка не найдена"), 404
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить значение перетока баланса электрической энергии")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    display = (
        ""
        if saved.get("value") is None
        else format_ee_balance_cell(saved["value"], digits=digits)
    )
    return jsonify(ok=True, year=saved["year"], display=display)


@energy_balance_bp.route("/ee_balance/<slug>/export_value/", methods=["PATCH"])
@login_required
def ee_balance_export_value(slug: str):
    _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    if "year" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    try:
        saved = update_ee_balance_export_value(slug, data.get("year"), data.get("value"))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить экспорт электрической энергии баланса")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    display = (
        ""
        if saved.get("value") is None
        else format_ee_balance_cell(saved["value"], digits=digits)
    )
    return jsonify(ok=True, year=saved["year"], display=display)
