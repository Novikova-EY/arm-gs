# -*- coding: utf-8 -*-
"""Маршрут итоговых сумм модуля «Экология»."""
from __future__ import annotations

from datetime import datetime

from flask import abort, current_app, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from werkzeug.exceptions import HTTPException

from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.ecology_logging_services import (
    context_lines,
    log_file_download,
    log_page_visit,
)
from app.ecology.services.ecology_totals_summary_services import (
    DEFAULT_ECOLOGY_TOTALS_SHEET,
    build_ecology_totals_summary_context,
)
from app.ecology.services.gis_tes_fuel_comparison_constants import ANALYSIS_SHEET_SLUGS
from app.fuel.services.totals_summary.fuel_totals_summary_services import (
    parse_aggregation_types,
)
from app.generation.services.station_services.generation_year_filter_services import (
    resolve_year_range_from_args_or_buffer,
)


def _with_query(url: str) -> str:
    qs = request.query_string.decode() if request.query_string else ""
    return f"{url}?{qs}" if qs else url


def _ecology_totals_page_context(sheet_slug: str):
    slug = (sheet_slug or "").strip()
    if slug not in ANALYSIS_SHEET_SLUGS:
        return None
    aggregation_types = parse_aggregation_types(request.args)
    start_year, end_year, filter_year_list = resolve_year_range_from_args_or_buffer(
        request.args
    )
    return build_ecology_totals_summary_context(
        sheet_slug=slug,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=request.args.get("rounding_digits"),
        aggregation_types=aggregation_types,
        filter_year_list=filter_year_list,
    )


@ecology_bp.route("/totals_summary")
@ecology_bp.route("/totals_summary/")
@login_required
def totals_summary_index():
    return redirect(
        _with_query(
            url_for("ecology_bp.totals_summary", sheet_slug=DEFAULT_ECOLOGY_TOTALS_SHEET)
        )
    )


@ecology_bp.route("/totals_summary/<sheet_slug>")
@ecology_bp.route("/totals_summary/<sheet_slug>/")
@login_required
def totals_summary(sheet_slug: str):
    context = _ecology_totals_page_context(sheet_slug)
    if context is None:
        abort(404)
    log_page_visit(
        "Итоговые суммы",
        tab=(context.get("sheet") or {}).get("page_title"),
        details=context_lines(
            ("лист", sheet_slug),
            ("период", f"{context.get('start_year')}–{context.get('end_year')}"),
            ("округление", context.get("rounding_digits")),
        ),
    )
    return render_template("ecology/totals_summary/ecology_totals_summary.html", **context)


@ecology_bp.route("/totals_summary_export")
@ecology_bp.route("/totals_summary_export/")
@login_required
def totals_summary_export_index():
    return redirect(
        _with_query(
            url_for(
                "ecology_bp.totals_summary_export",
                sheet_slug=DEFAULT_ECOLOGY_TOTALS_SHEET,
            )
        )
    )


@ecology_bp.route("/totals_summary/<sheet_slug>/export")
@ecology_bp.route("/totals_summary/<sheet_slug>/export/")
@login_required
def totals_summary_export(sheet_slug: str):
    from app.ecology.services.export_ecology_totals_summary_services import (
        export_ecology_totals_summary_to_excel,
    )

    try:
        context = _ecology_totals_page_context(sheet_slug)
        if context is None:
            abort(404)
        excel_file = export_ecology_totals_summary_to_excel(context)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ecology_totals_summary_{timestamp}.xlsx"
        log_file_download(
            context["page_title"],
            filename,
            details=[f"лист={sheet_slug}"],
        )
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.exception("Ошибка экспорта ecology totals_summary: %s", exc)
        return (
            "<p>Ошибка экспорта данных. Пожалуйста, попробуйте снова.</p>",
            500,
        )
