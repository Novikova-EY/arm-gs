# -*- coding: utf-8 -*-
from datetime import datetime

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp
from app.energy_balance.services.ee_balance_custom_flow_services import (
    add_custom_flow_row,
    delete_custom_flow_row,
    update_custom_flow_label,
    update_custom_flow_value,
)
from app.energy_balance.services.ee_balance_excel_services import export_ee_balance_to_excel
from app.energy_balance.services.balance_sheet_note_services import (
    BALANCE_KIND_EE,
    update_balance_sheet_note,
)
from app.energy_balance.services.ee_balance_manual_generation_services import (
    update_ee_balance_manual_generation_value,
)
from app.energy_balance.services.ee_balance_page_services import (
    build_ee_balance_table_context,
    first_row_active_slug,
    URAL_WITHOUT_TYUMEN_SLUG,
    SEVERO_ZAPAD_CENTER_SLUG,
    format_ee_balance_cell,
    get_ee_balance_sheet,
    get_ee_balance_sheets,
    group_ee_balance_sheets,
    is_persistable_ee_balance_slug,
    resolve_ee_balance_rounding_digits,
    tites_east_child_nav_sheets,
)
from app.energy_balance.services.ee_import_export_value_services import (
    update_ee_import_export_value,
)
from app.energy_balance.services.ee_receive_transfer_oes_value_services import (
    update_ee_receive_transfer_value,
)
from app.energy_balance.services.ee_balance_tes_forecast_services import (
    build_tes_forecast_context,
    is_tes_forecast_sheet,
    update_tes_forecast_value,
)
from app.energy_balance.services.ee_balance_hydro_own_needs_services import (
    save_hydro_own_needs_coefficient,
)
from app.energy_balance.services.ee_balance_ves_ses_page_services import (
    _format_cell,
    _can_edit_ves_ses_energy,
    build_aes_page_context,
    build_gaes_page_context,
    build_ges_page_context,
    build_snee_page_context,
    build_ves_ses_page_context,
)
from app.energy_balance.services.ee_balance_ves_ses_excel_services import (
    export_ves_ses_to_excel,
)
from app.common.services.help_services import format_decimal_trim_for_display
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_services import (
    save_station_energy_generation_service,
    save_station_owner_energy_generation_service,
)
from app.generation.services.station_services.station_type_flags import (
    is_aes_station,
    is_gaes_station,
    is_ges_station,
    is_snee_station,
    is_ves_or_ses_station,
)
from app.generation.services.station_services.ves_ses_plan_generation_services import (
    attach_ves_ses_plan_generation,
    save_station_exploitation_date_expected,
)
from app.common.services.database_version_filter import get_current_db_version_id
from app.energy_balance.services.power_balance_page_services import (
    tites_east_hub_redirect_slug,
)

DEFAULT_EE_BALANCE_SLUG = "ees-rossii"


@energy_balance_bp.route("/ee_balance/")
@login_required
def ee_balance_hub():
    """Промежуточный хаб убран: сразу открываем лист ЕЭС России."""
    return redirect(url_for("energy_balance_bp.ee_balance_table", slug=DEFAULT_EE_BALANCE_SLUG))


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
        return redirect(
            request.referrer
            or url_for("energy_balance_bp.ee_balance_table", slug=DEFAULT_EE_BALANCE_SLUG)
        )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Баланс_электрической_энергии_{timestamp}.xlsx",
    )


@energy_balance_bp.route("/ee_balance/ses-ves/")
@login_required
def ee_balance_ves_ses():
    """Выработка СЭС/ВЭС: станция и собственник, с иерархией как на списке станций."""
    from app.generation.services.station_services.filters_services import (
        extract_filters_from_args,
    )

    list_filters = extract_filters_from_args(request.args)
    context = build_ves_ses_page_context(
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        station_type_filter=request.args.getlist("station_type_filter"),
        page=request.args.get("page"),
        per_page=request.args.get("page_size", request.args.get("per_page")),
        list_filters=list_filters,
    )
    from app.generation.forms.station_forms import StationFilterForm

    context["form"] = StationFilterForm()
    context["station_filters_action"] = url_for("energy_balance_bp.ee_balance_ves_ses")
    context["station_filters_reset_url"] = url_for(
        "energy_balance_bp.ee_balance_ves_ses",
        start_year=context.get("start_year"),
        end_year=context.get("end_year"),
        rounding_digits=context.get("rounding_digits"),
    )
    return render_template("energy_balance/ee_balance/ee_balance_ves_ses.html", **context)


def _render_station_focus_page(context_builder, endpoint: str):
    from app.generation.services.station_services.filters_services import (
        extract_filters_from_args,
    )

    context = context_builder(
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        page=request.args.get("page"),
        per_page=request.args.get("page_size", request.args.get("per_page")),
        list_filters=extract_filters_from_args(request.args),
    )
    from app.generation.forms.station_forms import StationFilterForm

    context["form"] = StationFilterForm()
    context["station_filters_action"] = url_for(endpoint)
    context["station_filters_reset_url"] = url_for(
        endpoint,
        start_year=context.get("start_year"),
        end_year=context.get("end_year"),
        rounding_digits=context.get("rounding_digits"),
    )
    return render_template("energy_balance/ee_balance/ee_balance_ves_ses.html", **context)


@energy_balance_bp.route("/ee_balance/aes/")
@login_required
def ee_balance_aes():
    return _render_station_focus_page(
        build_aes_page_context, "energy_balance_bp.ee_balance_aes"
    )


@energy_balance_bp.route("/ee_balance/ges/")
@login_required
def ee_balance_ges():
    return _render_station_focus_page(
        build_ges_page_context, "energy_balance_bp.ee_balance_ges"
    )


@energy_balance_bp.route("/ee_balance/gaes/")
@login_required
def ee_balance_gaes():
    return _render_station_focus_page(
        build_gaes_page_context, "energy_balance_bp.ee_balance_gaes"
    )


@energy_balance_bp.route("/ee_balance/snee/")
@login_required
def ee_balance_snee():
    return _render_station_focus_page(
        build_snee_page_context, "energy_balance_bp.ee_balance_snee"
    )


@energy_balance_bp.route("/ee_balance/ses-ves/export/")
@login_required
def export_ee_balance_ves_ses():
    """Экспорт таблицы СЭС/ВЭС в Excel."""
    from app.generation.services.station_services.filters_services import (
        extract_filters_from_args,
    )

    list_filters = extract_filters_from_args(request.args)
    try:
        excel_file = export_ves_ses_to_excel(
            start_year=request.args.get("start_year"),
            end_year=request.args.get("end_year"),
            rounding_digits=request.args.get("rounding_digits"),
            station_type_filter=request.args.getlist("station_type_filter"),
            per_page="all",
            list_filters=list_filters,
        )
    except Exception as exc:
        current_app.logger.error("Ошибка экспорта СЭС/ВЭС: %s", exc, exc_info=True)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(ok=False, error=f"Ошибка экспорта данных: {exc}"), 500
        flash(f"Ошибка экспорта данных: {exc}", "danger")
        return redirect(
            request.referrer
            or url_for("energy_balance_bp.ee_balance_ves_ses")
        )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Выработка_СЭС_ВЭС_{timestamp}.xlsx",
    )


@energy_balance_bp.route("/ee_balance/ses-ves/value/", methods=["PATCH"])
@login_required
def ee_balance_ves_ses_value():
    """Перекрёстное сохранение выработки СЭС/ВЭС (те же таблицы, что на карточке станции)."""
    data = request.get_json(silent=True) or {}
    try:
        station_id = int(data.get("station_id"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверный запрос"), 400
    kind = str(data.get("kind") or "").strip()
    if kind not in {"energy", "owner", "exploitation_date", "coefficient"}:
        return jsonify(ok=False, error="Неверный тип значения"), 400

    station = Station.query.options(joinedload(Station.station_type)).get(station_id)
    if station is None:
        return jsonify(ok=False, error="Станция не найдена"), 404
    is_aes = is_aes_station(station)
    is_ges = is_ges_station(station)
    is_gaes = is_gaes_station(station)
    is_snee = is_snee_station(station)
    is_station_focus = is_aes or is_ges or is_gaes or is_snee
    if not (is_ves_or_ses_station(station) or is_station_focus):
        return jsonify(ok=False, error="Доступно только для СЭС, ВЭС, АЭС, ГЭС, ГАЭС и СНЭЭ"), 400
    if kind == "coefficient":
        if not (is_ges or is_gaes):
            return jsonify(ok=False, error="Коэффициент доступен только для ГЭС и ГАЭС"), 400
        if not _can_edit_ves_ses_energy():
            return jsonify(ok=False, error="Недостаточно прав"), 403
        try:
            coefficient = save_hydro_own_needs_coefficient(
                station.id,
                "ges" if is_ges else "gaes",
                data.get("value"),
                user=current_user,
                station_name=station.name,
            )
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception:
            current_app.logger.exception("Не удалось сохранить коэффициент СН ГЭС/ГАЭС")
            return jsonify(ok=False, error="Не удалось сохранить коэффициент"), 500
        coefficient_display = (
            format_decimal_trim_for_display(coefficient, digits=0)
            if coefficient is not None
            else ""
        )
        return jsonify(
            ok=True,
            kind=kind,
            display=coefficient_display,
            raw=coefficient_display,
            changed=True,
        )
    if is_station_focus and kind != "energy":
        return jsonify(ok=False, error="Для АЭС, ГЭС, ГАЭС и СНЭЭ доступно только редактирование выработки"), 400
    if not _can_edit_ves_ses_energy():
        return jsonify(ok=False, error="Недостаточно прав"), 403

    version_id = get_current_db_version_id()
    user = session.get("username", "Неизвестный пользователь")

    if kind == "exploitation_date":
        try:
            changes, display = save_station_exploitation_date_expected(
                user,
                station,
                data.get("value"),
                orig_value=data.get("orig"),
                version_id=version_id,
            )
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception:
            current_app.logger.exception(
                "Не удалось сохранить ожидаемую дату ввода СЭС/ВЭС"
            )
            return jsonify(ok=False, error="Не удалось сохранить значение"), 500

        digits = resolve_ee_balance_rounding_digits(
            data.get("rounding_digits", request.args.get("rounding_digits"))
        )
        try:
            page_start = int(data.get("start_year") or 0)
            page_end = int(data.get("end_year") or 0)
        except (TypeError, ValueError):
            page_start, page_end = 0, 0
        if page_start and page_end:
            attach_ves_ses_plan_generation(
                station,
                start_year=page_start,
                end_year=page_end,
                station_version_id=version_id,
            )
        plan_updates = {}
        plan_raw_updates = {}
        plan_rule_updates = {}
        stored = getattr(station, "station_energy_by_year", None) or {}
        calc = getattr(station, "station_energy_plan_calc_by_year", None) or {}
        rules = getattr(station, "station_energy_plan_rule_by_year", None) or {}
        for plan_year, calc_val in calc.items():
            if stored.get(int(plan_year)) is not None:
                continue
            plan_updates[str(plan_year)] = _format_cell(calc_val, digits)
            plan_raw_updates[str(plan_year)] = _format_cell(calc_val, 0)
            rule = rules.get(int(plan_year))
            if rule:
                plan_rule_updates[str(plan_year)] = rule
        return jsonify(
            ok=True,
            kind=kind,
            display=display,
            changed=bool(changes),
            plan_updates=plan_updates,
            plan_raw_updates=plan_raw_updates,
            plan_rule_updates=plan_rule_updates,
        )

    try:
        year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверный запрос"), 400

    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    prefix = "st_gen" if kind == "energy" else "st_owner_gen"
    orig = data.get("orig")
    if orig is None:
        orig = ""
    form_data = {
        f"{prefix}_{year}": data.get("value"),
        f"{prefix}_{year}_orig": orig,
    }
    try:
        if kind == "energy":
            changes = save_station_energy_generation_service(
                user, station, version_id, year, year, form_data
            )
        else:
            changes = save_station_owner_energy_generation_service(
                user, station, version_id, year, year, form_data
            )
    except Exception:
        current_app.logger.exception("Не удалось сохранить выработку СЭС/ВЭС")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500

    raw_value = data.get("value")
    display = _format_cell(raw_value, digits) if raw_value not in (None, "") else ""
    raw_display = _format_cell(raw_value, 0) if raw_value not in (None, "") else ""

    plan_updates = {}
    plan_raw_updates = {}
    plan_rule_updates = {}
    if kind == "owner":
        try:
            page_start = int(data.get("start_year") or year)
            page_end = int(data.get("end_year") or year)
        except (TypeError, ValueError):
            page_start, page_end = year, year
        attach_ves_ses_plan_generation(
            station,
            start_year=page_start,
            end_year=page_end,
            station_version_id=version_id,
        )
        stored = getattr(station, "station_energy_by_year", None) or {}
        calc = getattr(station, "station_energy_plan_calc_by_year", None) or {}
        rules = getattr(station, "station_energy_plan_rule_by_year", None) or {}
        for plan_year, calc_val in calc.items():
            if stored.get(int(plan_year)) is not None:
                continue
            plan_updates[str(plan_year)] = _format_cell(calc_val, digits)
            plan_raw_updates[str(plan_year)] = _format_cell(calc_val, 0)
            rule = rules.get(int(plan_year))
            if rule:
                plan_rule_updates[str(plan_year)] = rule
    return jsonify(
        ok=True,
        year=year,
        kind=kind,
        display=display,
        raw=raw_display,
        changed=bool(changes),
        plan_updates=plan_updates,
        plan_raw_updates=plan_raw_updates,
        plan_rule_updates=plan_rule_updates,
    )


@energy_balance_bp.route("/ee_balance/<slug>/")
@login_required
def ee_balance_table(slug: str):
    """Таблица баланса электрической энергии выбранного листа макета."""
    hub_sheet = get_ee_balance_sheet(slug)
    child_slug = tites_east_hub_redirect_slug(hub_sheet)
    if child_slug:
        target = url_for("energy_balance_bp.ee_balance_table", slug=child_slug)
        query = request.query_string.decode() if request.query_string else ""
        return redirect(f"{target}?{query}" if query else target)
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


@energy_balance_bp.route("/ee_balance/<slug>/tes_forecast/")
@login_required
def ee_balance_tes_forecast(slug: str):
    sheet = get_ee_balance_sheet(slug)
    if sheet is None or not is_tes_forecast_sheet(sheet):
        abort(404)
    context = build_tes_forecast_context(
        sheet,
        start_year=request.args.get("start_year"),
        end_year=request.args.get("end_year"),
        rounding_digits=request.args.get("rounding_digits"),
        view_year=request.args.get("view_year"),
    )
    if context is None:
        abort(404)
    sheets = get_ee_balance_sheets()
    context["sheet_groups"] = group_ee_balance_sheets(sheets)
    context["tites_east_child_sheets"] = tites_east_child_nav_sheets(sheets, sheet["slug"])
    context["first_row_active_slug"] = first_row_active_slug(sheet, sheet["slug"])
    context["can_edit"] = bool(_can_edit_ves_ses_energy() and context.get("is_plan_year"))
    return render_template(
        "energy_balance/ee_balance/ee_balance_tes_forecast.html",
        **context,
    )


@energy_balance_bp.route("/ee_balance/<slug>/tes_forecast/value/", methods=["PATCH"])
@login_required
def ee_balance_tes_forecast_value(slug: str):
    if not _can_edit_ves_ses_energy():
        return jsonify(ok=False, error="Недостаточно прав"), 403
    sheet = get_ee_balance_sheet(slug)
    if sheet is None or not is_tes_forecast_sheet(sheet):
        abort(404)
    data = request.get_json(silent=True) or {}
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    try:
        saved = update_tes_forecast_value(
            sheet,
            data.get("year"),
            data.get("row_key"),
            data.get("month"),
            data.get("value"),
            rounding_digits=digits,
            user=current_user,
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить помесячный расчёт выработки ТЭС")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    tes_total = saved.get("tes_total")
    tes_total_display = (
        "" if tes_total is None else format_ee_balance_cell(tes_total, digits=digits)
    )
    return jsonify(
        ok=True,
        year=saved["year"],
        row_key=saved.get("row_key"),
        month=saved.get("month"),
        cells=saved.get("cells") or {},
        formula_cells=saved.get("formula_cells") or {},
        tes_total_display=tes_total_display,
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
            user=current_user,
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
            deleted = delete_custom_flow_row(slug, row_id, user=current_user)
        except Exception:
            current_app.logger.exception("Не удалось удалить строку перетока баланса электрической энергии")
            return jsonify(ok=False, error="Не удалось удалить строку"), 500
        if not deleted:
            return jsonify(ok=False, error="Строка не найдена"), 404
        return jsonify(ok=True)

    data = request.get_json(silent=True) or {}
    if "label" in data and "year" not in data:
        try:
            row = update_custom_flow_label(slug, row_id, str(data.get("label") or ""), user=current_user)
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
        saved = update_custom_flow_value(
            slug, row_id, data.get("year"), data.get("value"), user=current_user
        )
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


@energy_balance_bp.route("/ee_balance/<slug>/generation_value/", methods=["PATCH"])
@login_required
def ee_balance_generation_value(slug: str):
    if not _can_edit_ves_ses_energy():
        return jsonify(ok=False, error="Недостаточно прав"), 403
    if slug == URAL_WITHOUT_TYUMEN_SLUG:
        sheet = get_ee_balance_sheet("ural")
        if sheet is None:
            abort(404)
    else:
        sheet = _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    if "year" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    try:
        saved = update_ee_balance_manual_generation_value(
            slug,
            data.get("row_key"),
            data.get("year"),
            data.get("value"),
            user=current_user,
            sheet_name=sheet.get("sheet_name"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception(
            "Не удалось сохранить выработку СНЭЭ/ТЭС баланса электрической энергии"
        )
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    display = (
        ""
        if saved.get("value") is None
        else format_ee_balance_cell(saved["value"], digits=digits)
    )
    return jsonify(
        ok=True, year=saved["year"], row_key=saved.get("row_key"), display=display
    )


@energy_balance_bp.route("/ee_balance/<slug>/note/", methods=["PATCH"])
@login_required
def ee_balance_note(slug: str):
    sheet = None
    if slug not in {URAL_WITHOUT_TYUMEN_SLUG, SEVERO_ZAPAD_CENTER_SLUG}:
        sheet = _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    try:
        saved = update_balance_sheet_note(
            BALANCE_KIND_EE,
            slug,
            data.get("row_key"),
            data.get("note"),
            user=current_user,
            sheet_name=(sheet or {}).get("sheet_name"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить примечание баланса электрической энергии")
        return jsonify(ok=False, error="Не удалось сохранить примечание"), 500
    return jsonify(ok=True, note=saved.get("note") or "", row_key=saved.get("row_key") or "")


@energy_balance_bp.route("/ee_balance/<slug>/import_export_value/", methods=["PATCH"])
@login_required
def ee_balance_import_export_value(slug: str):
    _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    if "year" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400
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
            direction=data.get("direction") or "import",
            raw_value=data.get("value"),
            user=current_user,
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить импорт/экспорт ЭЭ")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    display = (
        ""
        if saved.get("value") is None
        else format_ee_balance_cell(saved["value"], digits=digits)
    )
    return jsonify(ok=True, year=saved["year"], display=display)


@energy_balance_bp.route("/ee_balance/<slug>/receive_transfer_value/", methods=["PATCH"])
@login_required
def ee_balance_receive_transfer_value(slug: str):
    _require_sheet(slug)
    data = request.get_json(silent=True) or {}
    if "year" not in data:
        return jsonify(ok=False, error="Неверный запрос"), 400
    try:
        source_ues_id = int(data.get("source_ues_id"))
        target_ues_id = int(data.get("target_ues_id"))
        year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="Неверные данные ячейки"), 400
    try:
        saved = update_ee_receive_transfer_value(
            source_ues_id=source_ues_id,
            target_ues_id=target_ues_id,
            year=year,
            raw_value=data.get("value"),
            user=current_user,
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    except Exception:
        current_app.logger.exception("Не удалось сохранить прием/передачу ЭЭ")
        return jsonify(ok=False, error="Не удалось сохранить значение"), 500
    digits = resolve_ee_balance_rounding_digits(
        data.get("rounding_digits", request.args.get("rounding_digits"))
    )
    display = (
        ""
        if saved.get("value") is None
        else format_ee_balance_cell(saved["value"], digits=digits)
    )
    return jsonify(ok=True, year=saved["year"], display=display)

