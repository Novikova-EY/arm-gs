# -*- coding: utf-8 -*-
"""Страница «Формулы для расчета топлива по группам оборудования» и импорт из Excel."""

from urllib.parse import urlencode

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app.fuel.services.equipment_groups.equipment_group_fuel_formula_services import (
    annotate_formula_rows_numb1120_merge,
    apply_numb1120_merge_to_formula_hierarchy,
    get_equipment_groups_with_fuel_formula_data,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    build_equipment_group_specific_fuel_consumption_hierarchy,
)
from app.fuel.services.fuel_imports.import_equipment_group_fuel_formula_services import (
    import_equipment_group_fuel_formula_from_excel,
)
from app.generation.forms.station_forms import StationFilterForm
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    extract_filters_from_form,
    has_any_filters,
)
from app.generation.services.station_services.station_services import (
    get_station_list_template_context,
)
from app.logs.services.logging_service import log_to_db
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_year_list_full,
)

from . import fuel_bp


_YEAR_QUERY_KEYS = frozenset({"year", "start_year", "end_year"})


@fuel_bp.route("/equipment_group_fuel_formulas", methods=["GET", "POST"])
@login_required
def equipment_group_fuel_formulas_page():
    form = StationFilterForm()

    if request.method == "GET" and any(k in request.args for k in _YEAR_QUERY_KEYS):
        pairs = [
            (k, v)
            for k in request.args
            for v in request.args.getlist(k)
            if k not in _YEAR_QUERY_KEYS
        ]
        target = url_for("fuel_bp.equipment_group_fuel_formulas_page")
        if pairs:
            target = target + "?" + urlencode(pairs, doseq=True)
        return redirect(target)

    if request.method == "POST":
        return redirect(
            url_for(
                "fuel_bp.equipment_group_fuel_formulas_page",
                **extract_filters_from_form(request.form),
            )
        )

    filters = extract_filters_from_args(request.args)
    filters.pop("page", None)
    filters.pop("year", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)

    start_year = get_filter_start_year()
    end_year = get_filter_end_year()
    filter_year_list = [y.number for y in get_year_list_full()]
    per_page = "all"
    show_all = True

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1

    formula_data = get_equipment_groups_with_fuel_formula_data(
        filters=filters,
        per_page=per_page,
        page=1,
        start_year=start_year,
        end_year=end_year,
        show_all=show_all,
    )

    rows = formula_data.get("rows") or []
    total_count = formula_data.get("total_count", 0)

    equipment_group_fuel_formula_hierarchy = (
        apply_numb1120_merge_to_formula_hierarchy(
            build_equipment_group_specific_fuel_consumption_hierarchy(rows)
        )
    )
    equipment_group_fuel_formula_rows = annotate_formula_rows_numb1120_merge(
        rows, include_eg_in_key=True
    )

    data = {
        "stations": [],
        "stations_grouped": {},
        "station_ids": [],
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": formula_data.get("per_page", per_page),
        "show_headers": {},
        "station_totals": {},
        "show_p_ogr": False,
        "show_p_rasp": False,
    }

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
        hierarchy_data=None,
    )
    context["filter_year_list"] = filter_year_list
    context["selected_year"] = None

    has_active_filters = has_any_filters(request.args)

    formula_columns_merge = [
        ("numb1120", "numb1120", False),
    ]
    formula_columns_rest = [
        ("year_number", "year", False),
        ("formtxt", "formtxt", False),
    ]

    return render_template(
        "fuel/fuel_formula/stations_equipment_group_fuel_formula.html",
        has_active_filters=has_active_filters,
        equipment_group_fuel_formula_hierarchy=equipment_group_fuel_formula_hierarchy,
        equipment_group_fuel_formula_rows=equipment_group_fuel_formula_rows,
        formula_columns_merge=formula_columns_merge,
        formula_columns_rest=formula_columns_rest,
        **context,
    )


@fuel_bp.route("/equipment_group_fuel_formulas/import", methods=["POST"])
@login_required
def import_equipment_group_fuel_formula():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для загрузки файла.", "danger")
        return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page"))

    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Начата загрузка формул топлива из Excel")
    current_app.logger.info(
        "[IMPORT_FUEL_FORMULA] start user=%s filename=%s",
        user,
        getattr(request.files.get("file"), "filename", None),
    )

    redirect_args = {
        k: v for k, v in request.form.items() if k not in ("file", "csrf_token")
    }

    if "file" not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args))

    file = request.files["file"]
    if file.mimetype not in [
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args))

    try:
        result = import_equipment_group_fuel_formula_from_excel(file, user)
        flash(result["message"], "success")
    except ValueError as e:
        current_app.logger.warning(
            "[IMPORT_FUEL_FORMULA] validation error: %s",
            e,
            exc_info=True,
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception("[IMPORT_FUEL_FORMULA] import failed")
        flash(f"Ошибка загрузки данных: {str(e)}", "danger")

    return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args))
