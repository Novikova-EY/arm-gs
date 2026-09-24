# -*- coding: utf-8 -*-
"""Маршруты итоговых сумм выработки ЭЭ."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, render_template, request, send_file, url_for
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp


def _totals_page_context():
    from app.energy_balance.services.ee_generation_totals_summary_services import (
        DEFAULT_AGGREGATION_TYPES,
        build_ee_generation_totals_summary_context,
        parse_show_res,
        parse_show_verification,
        resolve_rounding_digits,
    )
    from app.energy_balance.services.energy_balance_year_filter_services import (
        resolve_ee_year_filters_for_request,
    )

    start_year, end_year, year_redirect = resolve_ee_year_filters_for_request()
    if year_redirect:
        return None, year_redirect
    rounding_digits = resolve_rounding_digits(
        request.args.get("rounding_digits"), default=1
    )
    context = build_ee_generation_totals_summary_context(
        start_year=start_year,
        end_year=end_year,
        aggregation_types=list(DEFAULT_AGGREGATION_TYPES),
        rounding_digits=rounding_digits,
        show_res=parse_show_res(request.args),
    )
    context["ee_control_save_url"] = url_for(
        "energy_balance_bp.ee_generation_control_value"
    )
    context["show_verification"] = parse_show_verification(request.args)
    return context, None


@energy_balance_bp.route("/ee_generation/totals_summary")
@energy_balance_bp.route("/ee_generation/totals_summary/")
@login_required
def ee_generation_totals_summary():
    context, year_redirect = _totals_page_context()
    if year_redirect:
        return year_redirect
    return render_template(
        "energy_balance/ee_generation/totals_summary/ee_generation_totals_summary.html",
        **context,
    )


@energy_balance_bp.route("/ee_generation/totals_summary_export")
@energy_balance_bp.route("/ee_generation/totals_summary_export/")
@login_required
def ee_generation_totals_summary_export():
    from app.energy_balance.services.export_ee_generation_totals_summary_services import (
        export_ee_generation_totals_summary_to_excel,
    )

    try:
        context, year_redirect = _totals_page_context()
        if year_redirect:
            return year_redirect
        excel_file = export_ee_generation_totals_summary_to_excel(context)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Выработка_ЭЭ_итоговые_{timestamp}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.exception(
            "Ошибка экспорта итоговых значений выработки ЭЭ: %s", exc
        )
        return (
            "<p>Ошибка экспорта данных. Пожалуйста, попробуйте снова.</p>",
            500,
        )
