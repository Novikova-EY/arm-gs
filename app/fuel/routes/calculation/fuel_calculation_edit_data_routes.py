# -*- coding: utf-8 -*-
"""Страница «Редактировать данные» для блока «Коэфф» расчётного модуля."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.datastructures import MultiDict

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_year_list_full,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    apply_fuel_calculation_detail_panels_save,
    build_fuel_calculation_edit_detail_panels_data,
    copy_fuel_params_between_years_for_filters,
    copy_heat_fuel_param_columns_for_filters,
    get_fuel_calculation_edit_data_view_model,
)
from app.fuel.services.calculation.fuel_calculation_specific_consumption_edit_data_services import (
    copy_specific_fuel_consumption_between_years_for_filters,
    get_specific_fuel_consumption_calculation_edit_data_view_model,
)
from app.fuel.services.equipment_groups.equipment_group_details_specific_params_services import (
    CONSUMPTION_FORMULAS,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS,
    get_equipment_group_ids_for_fuel_params_filters,
)
from app.fuel.services.equipment_groups.fuel_station_hierarchy_pagination import (
    count_fuel_eg_groups_in_hierarchy,
    fuel_eg_station_hierarchy_nonempty,
    paginate_fuel_eg_station_hierarchy,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    apply_equipment_group_fuel_params_bulk_save_from_form,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_recalc_services import (
    recalculate_all_specific_fuel_consumption_calc,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
    apply_specific_fuel_consumption_bulk_save_from_form,
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
from .. import fuel_bp

# Поля массового сохранения: g{id}_fuel_param_{year}_{attr}
_BULK_FUEL_PARAM_FIELD_RE = re.compile(r"^g(\d+)_fuel_param_\d+_.+\Z")
# Удельные показатели: g{id}_specific_fc_{year}_{attr}
_BULK_SPECIFIC_FC_FIELD_RE = re.compile(r"^g(\d+)_specific_fc_\d+_.+\Z")


def _bulk_edit_group_ids_from_fuel_hierarchy(hierarchy) -> list[int]:
    """ID групп оборудования на текущей странице (для скрытого поля массового сохранения)."""
    ids: set[int] = set()
    for est_block in hierarchy or []:
        for ues_block in est_block.get("ues_list", []):
            for res_block in ues_block.get("res_list", []):
                for station_block in res_block.get("station_blocks", []):
                    for gb in station_block.get("group_blocks", []):
                        eg = gb.get("equipment_group")
                        if eg is not None and getattr(eg, "id", None) is not None:
                            ids.add(int(eg.id))
    return sorted(ids)


def _parse_rounding_digits() -> int:
    raw = request.args.get("rounding_digits")
    if raw is None or raw == "":
        return 1
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 1
    if v in (-1, 0, 1, 2, 3):
        return v
    return 1


def _resolve_year_interval() -> tuple[int, int]:
    sy = request.args.get("start_year", type=int)
    ey = request.args.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey if ey is not None else get_filter_start_year()
    elif ey is None:
        ey = sy
    if sy > ey:
        sy, ey = ey, sy
    return sy, ey


def _redirect_equipment_group_fuel_params_edit_data(md: MultiDict):
    """Редирект на equipment_group_fuel_params_edit_data с query string из MultiDict."""
    qs = urlencode(list(md.items(multi=True)))
    base = url_for("fuel_bp.equipment_group_fuel_params_edit_data")
    return redirect(base + ("?" + qs if qs else ""))


def _redirect_equipment_group_fuel_params_edit_data_after_bulk_save():
    qs = (request.form.get("save_return_qs") or "").strip()
    base = url_for("fuel_bp.equipment_group_fuel_params_edit_data")
    return redirect(f"{base}?{qs}" if qs else base)


def _year_number_from_ref_year_id(year_id) -> int | None:
    if year_id is None:
        return None
    try:
        yid = int(year_id)
    except (TypeError, ValueError):
        return None
    for y in get_year_list_full():
        if int(y.id) == yid and y.number is not None:
            return int(y.number)
    return None


def _md_from_heat_add_form() -> MultiDict:
    md = MultiDict()
    for k, v in request.form.items():
        if k.startswith("r_") and k not in ("r_csrf_token",):
            md.add(k[2:], v)
    return md


def _merge_interval_onto_md(
    md: MultiDict, *, y_min: int, y_max: int
) -> None:
    sy = md.get("start_year", type=int)
    ey = md.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey if ey is not None else get_filter_start_year()
    elif ey is None:
        ey = sy
    if sy is None or ey is None:
        return
    if sy > ey:
        sy, ey = ey, sy
    md["start_year"] = str(min(int(sy), int(y_min)))
    md["end_year"] = str(max(int(ey), int(y_max)))


@fuel_bp.route(
    "/calculation/equipment_group_fuel_params_edit_data/add_heat_year",
    methods=["POST"],
)
@login_required
def equipment_group_fuel_params_edit_data_add_heat_year():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав.", "danger")
        return redirect(
            request.referrer
            or url_for("fuel_bp.equipment_group_fuel_params_edit_data")
        )
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return redirect(
            request.referrer
            or url_for("fuel_bp.equipment_group_fuel_params_edit_data")
        )

    id_base = request.form.get("id_base_year", type=int)
    id_target = request.form.get("id_target_year", type=int)
    source_num = _year_number_from_ref_year_id(id_base)
    target_num = _year_number_from_ref_year_id(id_target)
    if source_num is None or id_base is None:
        flash("Выберите базовый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())
    if target_num is None or id_target is None:
        flash("Выберите расчитываемый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())

    if source_num == target_num:
        flash("Базовый и расчитываемый год должны различаться.", "warning")
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())

    md = _md_from_heat_add_form()
    filters = extract_filters_from_args(md)
    filters.pop("page", None)
    sy = md.get("start_year", type=int)
    ey = md.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey
    elif ey is None:
        ey = sy
    if sy > ey:
        sy, ey = ey, sy
    if sy is None or ey is None:
        sy, ey = get_filter_start_year(), get_filter_end_year()

    try:
        copied, skipped, total_groups = copy_heat_fuel_param_columns_for_filters(
            filters,
            filter_start_year=sy,
            filter_end_year=ey,
            source_year_number=source_num,
            target_year_numbers=[target_num],
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка: {exc}", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(md)

    _merge_interval_onto_md(md, y_min=target_num, y_max=target_num)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не обновлено ни одной записи: нет данных за {source_num} г. у выбранных групп "
            f"(в выборке: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопированы показатели тепла (q, qotr, nt_sum, turt) с {source_num} г. на {target_num} г.; "
            f"nust, nr, nt — по правилам целевого года. Операций: {copied} (в выборке групп: {total_groups}, "
            f"без данных за {source_num} г.: {skipped}).",
            "success",
        )
    return _redirect_equipment_group_fuel_params_edit_data(md)


@fuel_bp.route(
    "/calculation/equipment_group_fuel_params_edit_data/add_heat_period",
    methods=["POST"],
)
@login_required
def equipment_group_fuel_params_edit_data_add_heat_period():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав.", "danger")
        return redirect(
            request.referrer
            or url_for("fuel_bp.equipment_group_fuel_params_edit_data")
        )
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return redirect(
            request.referrer
            or url_for("fuel_bp.equipment_group_fuel_params_edit_data")
        )

    id_base = request.form.get("id_base_year", type=int)
    id_from = request.form.get("id_year_from", type=int)
    id_to = request.form.get("id_year_to", type=int)
    source_num = _year_number_from_ref_year_id(id_base)
    n_from = _year_number_from_ref_year_id(id_from)
    n_to = _year_number_from_ref_year_id(id_to)

    if source_num is None or id_base is None:
        flash("Выберите базовый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())
    if n_from is None or n_to is None:
        flash("Укажите границы периода (расчитываемые годы) в справочнике.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())

    n_lo, n_hi = (n_from, n_to) if n_from <= n_to else (n_to, n_from)
    for n in range(n_lo, n_hi + 1):
        if not any(
            y.number is not None and int(y.number) == n for y in get_year_list_full()
        ):
            flash(
                f"В справочнике текущей версии БД нет года с номером {n}.",
                "danger",
            )
            return _redirect_equipment_group_fuel_params_edit_data(
                _md_from_heat_add_form()
            )

    target_nums = [n for n in range(n_lo, n_hi + 1) if n != source_num]
    if not target_nums:
        flash(
            "Период не содержит расчитываемых годов, отличных от базового: нечего копировать.",
            "warning",
        )
        return _redirect_equipment_group_fuel_params_edit_data(_md_from_heat_add_form())

    md = _md_from_heat_add_form()
    filters = extract_filters_from_args(md)
    filters.pop("page", None)
    sy = md.get("start_year", type=int)
    ey = md.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey
    elif ey is None:
        ey = sy
    if sy is not None and ey is not None and sy > ey:
        sy, ey = ey, sy
    if sy is None or ey is None:
        sy, ey = get_filter_start_year(), get_filter_end_year()

    try:
        copied, skipped, total_groups = copy_heat_fuel_param_columns_for_filters(
            filters,
            filter_start_year=sy,
            filter_end_year=ey,
            source_year_number=source_num,
            target_year_numbers=target_nums,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка: {exc}", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(md)

    _merge_interval_onto_md(md, y_min=n_lo, y_max=n_hi)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не обновлено ни одной записи: нет данных за {source_num} г. "
            f"(в выборке: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопированы q, qotr, nt_sum, turt с {source_num} г. на годы {n_lo}—{n_hi}; "
            f"nust, nr, nt — по правилам целевого года (операций: {copied}; в выборке групп: {total_groups}).",
            "success",
        )
    return _redirect_equipment_group_fuel_params_edit_data(md)


@fuel_bp.route("/calculation/coeff_copy_fuel_params_year", methods=["POST"])
@login_required
def fuel_calculation_coeff_copy_fuel_params_year():
    md = MultiDict()
    for k, v in request.form.items():
        if k.startswith("r_") and k not in ("r_csrf_token",):
            md.add(k[2:], v)

    source_year = request.form.get("copy_source_year", type=int)
    target_year = request.form.get("copy_target_year", type=int)

    if source_year is None or target_year is None:
        flash("Укажите год исходных данных и год для копирования.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(md)

    if source_year == target_year:
        flash("Год исходных данных и год для копирования должны различаться.", "warning")
        return _redirect_equipment_group_fuel_params_edit_data(md)

    filters = extract_filters_from_args(md)
    filters.pop("page", None)

    sy = md.get("start_year", type=int)
    ey = md.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey
    elif ey is None:
        ey = sy
    if sy > ey:
        sy, ey = ey, sy

    try:
        copied, skipped, total_groups = copy_fuel_params_between_years_for_filters(
            filters,
            filter_start_year=sy,
            filter_end_year=ey,
            source_year=source_year,
            target_year=target_year,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка при копировании данных: {exc}", "danger")
        return _redirect_equipment_group_fuel_params_edit_data(md)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не скопировано ни одной записи: нет данных за {source_year} г. "
            f"для выбранных групп (в выборке групп: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопировано записей: {copied} (в выборке групп: {total_groups}). "
            f"Пропущено без данных за {source_year} г.: {skipped}.",
            "success",
        )
    return _redirect_equipment_group_fuel_params_edit_data(md)


@fuel_bp.route("/calculation/coeff_edit_data", methods=["GET", "POST"])
@login_required
def fuel_calculation_coeff_edit_data_legacy_redirect():
    """Редирект на новый URL (ранее страница открывалась по /calculation/coeff_edit_data)."""
    if request.method == "POST":
        return redirect(
            url_for(
                "fuel_bp.equipment_group_fuel_params_edit_data",
                **extract_filters_from_form(request.form),
            )
        )
    qs = request.query_string.decode("utf-8")
    base = url_for("fuel_bp.equipment_group_fuel_params_edit_data")
    return redirect(base + ("?" + qs if qs else ""), code=301)


@fuel_bp.route("/calculation/equipment_group_fuel_params_edit_data", methods=["GET", "POST"])
@login_required
def equipment_group_fuel_params_edit_data():
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(
            url_for(
                "fuel_bp.equipment_group_fuel_params_edit_data",
                **extract_filters_from_form(request.form),
            )
        )

    filters = extract_filters_from_args(request.args)
    page = request.args.get("page", 1, type=int)
    filters.pop("page", None)
    per_page_param = request.args.get("per_page", "10")
    show_all = str(per_page_param).lower() == "all"
    per_page = (
        "all"
        if show_all
        else int(per_page_param)
        if str(per_page_param).isdigit()
        else 10
    )

    start_year, end_year = _resolve_year_interval()
    rounding_digits = _parse_rounding_digits()

    vm = get_fuel_calculation_edit_data_view_model(
        filters,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
    )

    hierarchy_full = vm.get("equipment_group_fuel_params_hierarchy") or []
    total_eg_count = count_fuel_eg_groups_in_hierarchy(hierarchy_full)
    if show_all:
        equipment_group_fuel_params_hierarchy = hierarchy_full
        total_pages = 1
        current_page = 1
    else:
        (
            equipment_group_fuel_params_hierarchy,
            total_eg_count,
            total_pages,
            current_page,
        ) = paginate_fuel_eg_station_hierarchy(
            hierarchy_full,
            page,
            per_page,
            FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS,
        )

    if (
        not fuel_eg_station_hierarchy_nonempty(equipment_group_fuel_params_hierarchy)
        and total_eg_count > 0
        and page > 1
    ):
        target_page = max(1, current_page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(
            url_for("fuel_bp.equipment_group_fuel_params_edit_data", **redirect_args)
        )

    vm["equipment_group_fuel_params_hierarchy"] = equipment_group_fuel_params_hierarchy
    vm["bulk_edit_equipment_group_ids"] = _bulk_edit_group_ids_from_fuel_hierarchy(
        equipment_group_fuel_params_hierarchy
    )

    qs = request.query_string.decode("utf-8") if request.query_string else ""
    calculation_back_url = url_for("fuel_bp.fuel_calculation_form")
    if qs:
        calculation_back_url = calculation_back_url + "?" + qs

    data = {
        "stations": [],
        "stations_grouped": {},
        "station_ids": [],
        "total_count": total_eg_count,
        "total_pages": total_pages,
        "page": current_page,
        "per_page": per_page,
        "show_headers": {},
        "station_totals": {},
        "show_p_ogr": False,
        "show_p_rasp": False,
    }

    filter_ctx = {**filters, "start_year": start_year, "end_year": end_year}
    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        filter_ctx,
        show_all=show_all,
        hierarchy_data=None,
    )

    has_active_filters = has_any_filters(request.args)

    # context после vm: total_count / total_pages / current_page из data, не len(rows) из vm
    template_vars = {
        **vm,
        **context,
        "consumption_formulas": CONSUMPTION_FORMULAS,
        "consumption_column_labels": {
            **EquipmentGroupSpecificFuelConsumption.COLUMN_LABELS,
            "k": "Коэффициент экономии от теплофикации",
        },
    }

    return render_template(
        "fuel/calculation/equipment_group_fuel_params_edit_data.html",
        calculation_back_url=calculation_back_url,
        has_active_filters=has_active_filters,
        year_list_for_edit=get_year_list_full(),
        **template_vars,
    )


@fuel_bp.route(
    "/calculation/equipment_group_fuel_params_edit_data/detail_panels/<int:equipment_group_id>",
    methods=["GET"],
)
@login_required
def equipment_group_fuel_params_edit_detail_panels(equipment_group_id: int):
    """JSON: удельные показатели и формулы для одной группы (те же фильтры и интервал лет, что в query)."""
    filters = extract_filters_from_args(request.args)
    filters.pop("page", None)
    start_year, end_year = _resolve_year_interval()
    rounding_digits = _parse_rounding_digits()

    allowed = set(
        get_equipment_group_ids_for_fuel_params_filters(
            filters,
            start_year=start_year,
            end_year=end_year,
        )
    )
    if equipment_group_id not in allowed:
        return jsonify({"error": "Группа не найдена по текущим фильтрам."}), 404

    data = build_fuel_calculation_edit_detail_panels_data(
        [equipment_group_id],
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
    )
    pack = data.get(str(equipment_group_id)) or {
        "specific": [],
        "formulas": [],
        "extra_fuel": {
            "columns": [],
            "column_sources": {},
            "column_labels": {},
            "rows": [],
        },
    }
    return jsonify(pack)


@fuel_bp.route(
    "/calculation/equipment_group_fuel_params_edit_data/detail_panels/save",
    methods=["POST"],
)
@login_required
def equipment_group_fuel_params_edit_detail_panels_save():
    """JSON: сохранение удельных, формул и доп. параметров по одной группе (нижняя панель)."""
    if not getattr(current_user, "has_admin", False):
        return jsonify({"ok": False, "error": "Недостаточно прав для сохранения."}), 403
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Ошибка проверки CSRF."}), 400

    data = request.get_json(silent=True) or {}
    try:
        equipment_group_id = int(data.get("equipment_group_id", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Некорректный equipment_group_id."}), 400

    filters = extract_filters_from_args(request.args)
    filters.pop("page", None)
    start_year, end_year = _resolve_year_interval()
    rounding_digits = _parse_rounding_digits()

    allowed = set(
        get_equipment_group_ids_for_fuel_params_filters(
            filters,
            start_year=start_year,
            end_year=end_year,
        )
    )
    if equipment_group_id not in allowed:
        return jsonify({"ok": False, "error": "Группа не найдена по текущим фильтрам."}), 404

    specific_rows = data.get("specific")
    formula_rows = data.get("formulas")
    extra_fuel = data.get("extra_fuel")

    try:
        errs = apply_fuel_calculation_detail_panels_save(
            equipment_group_id,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            specific_rows=specific_rows if isinstance(specific_rows, list) else None,
            formula_rows=formula_rows if isinstance(formula_rows, list) else None,
            extra_fuel=extra_fuel if isinstance(extra_fuel, dict) else None,
        )
        if errs:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "; ".join(errs[:20]),
                        "errors": errs,
                    }
                ),
                400,
            )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "message": "Данные нижней панели сохранены."})


@fuel_bp.route(
    "/calculation/equipment_group_fuel_params_edit_data/save",
    methods=["POST"],
)
@login_required
def equipment_group_fuel_params_edit_data_save():
    """Массовое сохранение основных топливных параметров (как /fuel/distribution_parameters/save)."""
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для сохранения.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()

    md = MultiDict(parse_qsl((request.form.get("save_return_qs") or "").strip(), keep_blank_values=True))
    filters = extract_filters_from_args(md)
    filters.pop("page", None)

    start_year = request.form.get("start_year", type=int)
    end_year = request.form.get("end_year", type=int)
    if start_year is None or end_year is None:
        flash("Не указан интервал лет (start_year / end_year).", "danger")
        return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    rd = request.form.get("rounding_digits", type=int)
    if rd not in (-1, 0, 1, 2, 3):
        rd = 1

    gids_from_post: set[int] = set()
    for k in request.form:
        m = _BULK_FUEL_PARAM_FIELD_RE.match(k)
        if m:
            gids_from_post.add(int(m.group(1)))
    allowed = set(
        get_equipment_group_ids_for_fuel_params_filters(
            filters,
            start_year=start_year,
            end_year=end_year,
        )
    )
    ids = sorted(gids_from_post & allowed)
    if not gids_from_post:
        flash("Нет изменений для сохранения.", "info")
        return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()
    if not ids:
        flash(
            "Нет допустимых групп оборудования для сохранения (проверьте фильтры).",
            "warning",
        )
        return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()

    try:
        changed, errs = apply_equipment_group_fuel_params_bulk_save_from_form(
            request.form,
            equipment_group_ids=ids,
            start_year=start_year,
            end_year=end_year,
            rounding_digits_table1=rd,
            rounding_digits_table2=rd,
        )
        if errs:
            db.session.rollback()
            for msg in errs[:25]:
                flash(msg, "danger")
            if len(errs) > 25:
                flash(f"… и ещё ошибок: {len(errs) - 25}.", "danger")
        else:
            recalc_n = 0
            if changed > 0:
                db.session.flush()
                for gid in ids:
                    recalc_n += recalculate_all_specific_fuel_consumption_calc(
                        equipment_group_id=gid,
                        start_year=start_year,
                        end_year=end_year,
                        commit=False,
                    )
            db.session.commit()
            if changed > 0:
                from app.generation.services.station_services.station_services import (
                    clear_station_aggregation_cache,
                )

                clear_station_aggregation_cache(
                    "после сохранения топливных параметров (модуль расчёта), пересчёт удельных"
                )
            if changed == 0:
                flash(
                    "Изменений для сохранения не было (все значения совпадают с данными в БД).",
                    "info",
                )
            else:
                msg = f"Сохранены изменения по группам оборудования: {changed}."
                if recalc_n:
                    msg += f" Пересчитаны расчётные удельные показатели: {recalc_n}."
                flash(msg, "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка при сохранении: {exc}", "danger")

    return _redirect_equipment_group_fuel_params_edit_data_after_bulk_save()


def _redirect_equipment_group_specific_fuel_consumption_edit_data(md: MultiDict):
    qs = urlencode(list(md.items(multi=True)))
    base = url_for("fuel_bp.equipment_group_specific_fuel_consumption_edit_data")
    return redirect(base + ("?" + qs if qs else ""))


def _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save():
    qs = (request.form.get("save_return_qs") or "").strip()
    base = url_for("fuel_bp.equipment_group_specific_fuel_consumption_edit_data")
    return redirect(f"{base}?{qs}" if qs else base)


@fuel_bp.route("/calculation/coeff_copy_specific_consumption_year", methods=["POST"])
@login_required
def fuel_calculation_coeff_copy_specific_consumption_year():
    md = MultiDict()
    for k, v in request.form.items():
        if k.startswith("r_") and k not in ("r_csrf_token",):
            md.add(k[2:], v)

    source_year = request.form.get("copy_source_year", type=int)
    target_year = request.form.get("copy_target_year", type=int)

    if source_year is None or target_year is None:
        flash("Укажите год исходных данных и год для копирования.", "danger")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data(md)

    if source_year == target_year:
        flash("Год исходных данных и год для копирования должны различаться.", "warning")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data(md)

    filters = extract_filters_from_args(md)
    filters.pop("page", None)

    sy = md.get("start_year", type=int)
    ey = md.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey
    elif ey is None:
        ey = sy
    if sy > ey:
        sy, ey = ey, sy

    try:
        copied, skipped, total_groups = copy_specific_fuel_consumption_between_years_for_filters(
            filters,
            filter_start_year=sy,
            filter_end_year=ey,
            source_year=source_year,
            target_year=target_year,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка при копировании данных: {exc}", "danger")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data(md)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не скопировано ни одной записи: нет данных за {source_year} г. "
            f"для выбранных групп (в выборке групп: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопировано записей: {copied} (в выборке групп: {total_groups}). "
            f"Пропущено без данных за {source_year} г.: {skipped}.",
            "success",
        )
    return _redirect_equipment_group_specific_fuel_consumption_edit_data(md)


@fuel_bp.route(
    "/calculation/equipment_group_specific_fuel_consumption_edit_data",
    methods=["GET", "POST"],
)
@login_required
def equipment_group_specific_fuel_consumption_edit_data():
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(
            url_for(
                "fuel_bp.equipment_group_specific_fuel_consumption_edit_data",
                **extract_filters_from_form(request.form),
            )
        )

    filters = extract_filters_from_args(request.args)
    page = request.args.get("page", 1, type=int)
    filters.pop("page", None)
    per_page_param = request.args.get("per_page", "10")
    show_all = str(per_page_param).lower() == "all"
    per_page = (
        "all"
        if show_all
        else int(per_page_param)
        if str(per_page_param).isdigit()
        else 10
    )

    start_year, end_year = _resolve_year_interval()
    rounding_digits = _parse_rounding_digits()

    vm = get_specific_fuel_consumption_calculation_edit_data_view_model(
        filters,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
    )

    hierarchy_full = vm.get("equipment_group_specific_fuel_consumption_hierarchy") or []
    total_eg_count = count_fuel_eg_groups_in_hierarchy(hierarchy_full)
    if show_all:
        equipment_group_specific_fuel_consumption_hierarchy = hierarchy_full
        total_pages = 1
        current_page = 1
    else:
        (
            equipment_group_specific_fuel_consumption_hierarchy,
            total_eg_count,
            total_pages,
            current_page,
        ) = paginate_fuel_eg_station_hierarchy(
            hierarchy_full,
            page,
            per_page,
            SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS,
        )

    if (
        not fuel_eg_station_hierarchy_nonempty(
            equipment_group_specific_fuel_consumption_hierarchy
        )
        and total_eg_count > 0
        and page > 1
    ):
        target_page = max(1, current_page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = {}
        for key, values in args_multi.items():
            if not values:
                continue
            if len(values) == 1:
                redirect_args[key] = values[0]
            else:
                redirect_args[key] = values
        return redirect(
            url_for(
                "fuel_bp.equipment_group_specific_fuel_consumption_edit_data",
                **redirect_args,
            )
        )

    vm["equipment_group_specific_fuel_consumption_hierarchy"] = (
        equipment_group_specific_fuel_consumption_hierarchy
    )
    vm["bulk_edit_equipment_group_ids"] = _bulk_edit_group_ids_from_fuel_hierarchy(
        equipment_group_specific_fuel_consumption_hierarchy
    )

    qs = request.query_string.decode("utf-8") if request.query_string else ""
    calculation_back_url = url_for("fuel_bp.fuel_calculation_form")
    if qs:
        calculation_back_url = calculation_back_url + "?" + qs

    data = {
        "stations": [],
        "stations_grouped": {},
        "station_ids": [],
        "total_count": total_eg_count,
        "total_pages": total_pages,
        "page": current_page,
        "per_page": per_page,
        "show_headers": {},
        "station_totals": {},
        "show_p_ogr": False,
        "show_p_rasp": False,
    }

    filter_ctx = {**filters, "start_year": start_year, "end_year": end_year}
    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        filter_ctx,
        show_all=show_all,
        hierarchy_data=None,
    )

    has_active_filters = has_any_filters(request.args)

    template_vars = {
        **vm,
        **context,
        "consumption_formulas": CONSUMPTION_FORMULAS,
        "consumption_column_labels": {
            **EquipmentGroupSpecificFuelConsumption.COLUMN_LABELS,
            "k": "Коэффициент экономии от теплофикации",
        },
    }

    return render_template(
        "fuel/calculation/equipment_group_specific_fuel_consumption_edit_data.html",
        calculation_back_url=calculation_back_url,
        has_active_filters=has_active_filters,
        **template_vars,
    )


@fuel_bp.route(
    "/calculation/equipment_group_specific_fuel_consumption_edit_data/save",
    methods=["POST"],
)
@login_required
def equipment_group_specific_fuel_consumption_edit_data_save():
    """Массовое сохранение удельных показателей (k, y, btp, sntp, bk, snk)."""
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для сохранения.", "danger")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()

    md = MultiDict(
        parse_qsl((request.form.get("save_return_qs") or "").strip(), keep_blank_values=True)
    )
    filters = extract_filters_from_args(md)
    filters.pop("page", None)

    start_year = request.form.get("start_year", type=int)
    end_year = request.form.get("end_year", type=int)
    if start_year is None or end_year is None:
        flash("Не указан интервал лет (start_year / end_year).", "danger")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    rd = request.form.get("rounding_digits", type=int)
    if rd not in (-1, 0, 1, 2, 3):
        rd = 1

    gids_from_post: set[int] = set()
    for k in request.form:
        m = _BULK_SPECIFIC_FC_FIELD_RE.match(k)
        if m:
            gids_from_post.add(int(m.group(1)))
    allowed = set(
        get_equipment_group_ids_for_fuel_params_filters(
            filters,
            start_year=start_year,
            end_year=end_year,
        )
    )
    ids = sorted(gids_from_post & allowed)
    if not gids_from_post:
        flash("Нет изменений для сохранения.", "info")
        return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()
    if not ids:
        flash(
            "Нет допустимых групп оборудования для сохранения (проверьте фильтры).",
            "warning",
        )
        return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()

    try:
        changed, errs = apply_specific_fuel_consumption_bulk_save_from_form(
            request.form,
            equipment_group_ids=ids,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rd,
        )
        if errs:
            db.session.rollback()
            for msg in errs[:25]:
                flash(msg, "danger")
            if len(errs) > 25:
                flash(f"… и ещё ошибок: {len(errs) - 25}.", "danger")
        else:
            db.session.commit()
            if changed == 0:
                flash(
                    "Изменений для сохранения не было (все значения совпадают с данными в БД).",
                    "info",
                )
            else:
                flash(
                    f"Сохранены изменения по группам оборудования: {changed}.",
                    "success",
                )
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка при сохранении: {exc}", "danger")

    return _redirect_equipment_group_specific_fuel_consumption_edit_data_after_bulk_save()
