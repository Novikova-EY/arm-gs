# -*- coding: utf-8 -*-
"""Маршрут итоговых сумм модуля «Топливо»."""
from __future__ import annotations

from datetime import datetime

from flask import current_app, render_template, request, send_file
from flask_login import login_required

from . import fuel_bp


def _fuel_totals_page_context():
    from app.fuel.services.totals_summary.fuel_totals_summary_services import (
        build_fuel_totals_summary_context,
        parse_aggregation_types,
        resolve_rounding_digits,
    )
    from app.generation.services.station_services.generation_year_filter_services import (
        resolve_year_range_from_args_or_buffer,
    )

    start_year, end_year, filter_year_list = resolve_year_range_from_args_or_buffer(
        request.args
    )
    aggregation_types = parse_aggregation_types(request.args)
    rounding_digits = resolve_rounding_digits(
        request.args.get("rounding_digits"), default=1
    )
    return build_fuel_totals_summary_context(
        start_year=start_year,
        end_year=end_year,
        aggregation_types=aggregation_types,
        rounding_digits=rounding_digits,
        filter_year_list=filter_year_list,
    )


@fuel_bp.route("/totals_summary")
@login_required
def totals_summary():
    context = _fuel_totals_page_context()
    return render_template("fuel/totals_summary/fuel_totals_summary.html", **context)


@fuel_bp.route("/totals_summary_export")
@login_required
def totals_summary_export():
    from app.fuel.services.totals_summary.export_fuel_totals_summary_services import (
        export_fuel_totals_summary_to_excel,
    )

    try:
        context = _fuel_totals_page_context()
        excel_file = export_fuel_totals_summary_to_excel(context)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fuel_totals_summary_{timestamp}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as exc:
        current_app.logger.exception("Ошибка экспорта fuel totals_summary: %s", exc)
        return (
            "<p>Ошибка экспорта данных. Пожалуйста, попробуйте снова.</p>",
            500,
        )
