# -*- coding: utf-8 -*-
"""Маршруты расчёта по действующим ТЭС."""

from __future__ import annotations

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.ecology.routes.ecology_bp import ecology_bp
from app.ecology.services.ecology_logging_services import (
    affiliation_label,
    context_lines,
    log_changes,
    log_event,
    log_page_visit,
    value_change,
)
from app.ecology.services.gis_tek_page_services import can_edit_ecology
from app.ecology.services.operating_tes_constants import (
    DEFAULT_SHEET_SLUG,
    DEFAULT_TERRITORY_SLUG,
    get_calc_sheet,
    get_coefficient_territory,
    get_territory,
)
from app.ecology.services.operating_tes_page_services import (
    build_operating_tes_table_context,
    upsert_characteristic,
    upsert_coefficient,
)
from app.common.services.help_services import parse_decimal_from_display


@ecology_bp.route("/operating_tes/")
@login_required
def operating_tes_hub():
    return redirect(
        url_for(
            "ecology_bp.operating_tes_table",
            territory_slug=DEFAULT_TERRITORY_SLUG,
            sheet_slug=DEFAULT_SHEET_SLUG,
        )
    )


@ecology_bp.route("/operating_tes/<territory_slug>/")
@login_required
def operating_tes_territory(territory_slug: str):
    if get_territory(territory_slug) is None:
        abort(404)
    return redirect(
        url_for(
            "ecology_bp.operating_tes_table",
            territory_slug=territory_slug,
            sheet_slug=DEFAULT_SHEET_SLUG,
            **request.args,
        )
    )


@ecology_bp.route("/operating_tes/<territory_slug>/<sheet_slug>/")
@login_required
def operating_tes_table(territory_slug: str, sheet_slug: str):
    context = build_operating_tes_table_context(
        territory_slug,
        sheet_slug,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        coefficient_rounding_digits=request.args.get("coefficient_rounding_digits"),
        view_year=request.args.get("view_year"),
        affiliation=request.args.get("affiliation", "all"),
    )
    if context is None:
        abort(404)
    sheet = context.get("sheet") or {}
    visit_details = context_lines(
        ("территория", (context.get("territory") or {}).get("sheet_name")),
        ("период", f"{context.get('start_year')}–{context.get('end_year')}"),
        ("год", context.get("view_year")),
    )
    if sheet.get("layout") == "coeff":
        visit_details.append(
            f"принадлежность={affiliation_label(context.get('affiliation'))}"
        )
    log_page_visit(
        "Действующие ТЭС",
        tab=str(sheet.get("sheet_name") or sheet_slug),
        details=visit_details,
    )
    context["can_edit"] = bool(
        can_edit_ecology(current_user) and sheet.get("layout") != "fuel"
    )
    if sheet.get("layout") == "fuel":
        from app.ecology.services.fuel_exchange_services import pending_submissions

        pending = pending_submissions(context["range_years"])
        context["fuel_pending_by_year"] = {item.year_number: item for item in pending}
        context["fuel_pending"] = context["fuel_pending_by_year"].get(context["view_year"])
    return render_template(
        "ecology/operating_tes/operating_tes_table.html",
        document_title="Расчет по действующим ТЭС",
        **context,
    )


@ecology_bp.route("/operating_tes/fuel_submissions/<int:submission_id>/", methods=["GET", "POST"])
@login_required
def operating_tes_fuel_review(submission_id):
    from app.ecology.services.fuel_exchange_services import (
        get_submission, review_fuel_submission, submission_differences,
    )
    from app.ecology.services.operating_tes_page_services import format_cell

    submission = get_submission(submission_id)
    if submission is None:
        abort(404)
    from app.ecology.services.fuel_summary_constants import FUEL_SUMMARY_LABELS

    from app.ecology.services.fuel_summary_constants import NEW_TES_SCOPE_CAPACITY

    scope_label = FUEL_SUMMARY_LABELS[submission.scope]
    capacity_class = NEW_TES_SCOPE_CAPACITY.get(submission.scope)
    return_endpoint = "ecology_bp.operating_tes_table" if submission.scope == "operating" else "ecology_bp.new_tes_table"
    can_review = can_edit_ecology(current_user)
    if request.method == "POST":
        if not can_review:
            abort(403)
        decision = request.form.get("decision")
        if decision not in {"accept", "reject"}:
            abort(400)
        # До акцепта: после него эталонный снимок уже совпадает с пакетом.
        differences = submission_differences(submission) if decision == "accept" else []
        try:
            review_fuel_submission(submission_id, accept=decision == "accept")
        except ValueError as exc:
            return str(exc), 409
        review_details = context_lines(
            ("пакет", submission_id),
            ("год", submission.year_number),
            ("категория", scope_label),
        )
        action_title = f"Данные из модуля «Топливо» за {submission.year_number} год – {scope_label}"
        changes = [
            value_change(
                f"{item['label']} ({item['territory']})", item["before"], item["after"]
            )
            for item in differences
        ]
        if decision == "reject":
            log_event(f"Отклонены {action_title}", review_details)
        elif changes:
            log_changes(f"Акцепт: {action_title}", changes, context=review_details)
        else:
            log_event(f"Акцепт: {action_title} (изменений нет)", review_details)
        flash("Данные акцептованы." if decision == "accept" else "Данные отклонены. Принятые показатели не изменены.", "success")
        return redirect(url_for(return_endpoint, territory_slug="vsego", sheet_slug="toplivo", start_year=request.args.get("start_year", submission.year_number), end_year=request.args.get("end_year", submission.year_number), view_year=submission.year_number, rounding_digits=request.args.get("rounding_digits", 1), capacity_class=capacity_class))
    log_page_visit(
        "Акцепт данных из модуля «Топливо»",
        tab=f"{submission.year_number} год",
        details=context_lines(("пакет", submission_id)),
    )
    return render_template(
        "ecology/operating_tes/fuel_review.html", submission=submission,
        differences=submission_differences(submission), can_review=can_review, format_cell=format_cell,
        scope_label=scope_label, return_endpoint=return_endpoint, capacity_class=capacity_class,
    )


@ecology_bp.route(
    "/operating_tes/<territory_slug>/<sheet_slug>/value/",
    methods=["PATCH"],
)
@login_required
def operating_tes_update_value(territory_slug: str, sheet_slug: str):
    if not can_edit_ecology(current_user):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    territory = get_territory(territory_slug)
    if sheet_slug == "koeff":
        territory = territory or get_coefficient_territory(territory_slug)
    if territory is None or get_calc_sheet(sheet_slug) is None:
        abort(404)
    data = request.get_json(silent=True) or {}
    year = data.get("year")
    field = str(data.get("field") or "").strip()
    row_key = str(data.get("row_key") or "").strip()
    coeff_territory = str(data.get("territory") or territory_slug).strip()
    try:
        year_int = int(year)
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Некорректный год"), 400
    raw = data.get("value")
    try:
        amount = parse_decimal_from_display(raw) if raw not in (None, "") else None
    except Exception:
        return jsonify(ok=False, error="Некорректное число"), 400
    try:
        if sheet_slug == "koeff":
            upsert_coefficient(
                coeff_territory, year_int, row_key or field, amount,
                affiliation=str(data.get("affiliation") or "all"),
            )
        elif sheet_slug == "khar-topl":
            upsert_characteristic(territory_slug, row_key, year_int, field, amount)
        else:
            return jsonify(ok=False, error="Лист только для просмотра"), 400
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить значение расчёта ТЭС")
        return jsonify(ok=False, error="Не удалось сохранить"), 500
    return jsonify(ok=True)
