# -*- coding: utf-8 -*-
"""Страница «Формулы для расчета топлива по группам оборудования» и импорт из Excel."""

import re
from itertools import groupby
from urllib.parse import parse_qsl, urlencode

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
from werkzeug.datastructures import MultiDict

from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_year_list_full,
)
from app.extensions import db
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import (
    fuel_calculation_form_url_from_tep_edit_args,
)
from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
    build_fuel_param_row_warn_sets,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_formula_services import (
    expand_formula_rows_for_year_interval,
    get_equipment_groups_with_fuel_formula_data,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_formula_write_services import (
    apply_fuel_formula_bulk_save_from_form,
    copy_fuel_formulas_between_years_for_filters,
    formtxt_editable_year_numbers_for_version,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    get_equipment_group_ids_for_fuel_params_filters,
    get_equipment_groups_with_fuel_params_data,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    build_equipment_group_specific_fuel_consumption_hierarchy,
)
from app.fuel.services.equipment_groups.fuel_station_hierarchy_pagination import (
    count_fuel_eg_groups_in_hierarchy,
    fuel_eg_station_hierarchy_nonempty,
    paginate_fuel_eg_station_hierarchy,
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

from . import fuel_bp

_BULK_FUEL_FORMULA_FIELD_RE = re.compile(r"^g(\d+)_fuel_formula_\d+_v\d+_formtxt$")


def _resolve_year_interval():
    """Как на ТЭП edit_data: start_year / end_year из query (базовый / расчётный с формы расчёта)."""
    sy = request.args.get("start_year", type=int)
    ey = request.args.get("end_year", type=int)
    if sy is None and ey is None:
        sy = get_filter_start_year()
        ey = get_filter_end_year()
    elif sy is None:
        sy = ey if ey is not None else get_filter_start_year()
    elif ey is None:
        ey = sy
    if sy is not None and ey is not None and sy > ey:
        sy, ey = ey, sy
    return sy, ey


def _redirect_equipment_group_fuel_formulas(md: MultiDict | None = None):
    base = url_for("fuel_bp.equipment_group_fuel_formulas_page")
    if md is None:
        return redirect(base)
    qs = urlencode(list(md.items(multi=True)))
    return redirect(base + ("?" + qs if qs else ""))


def _redirect_equipment_group_fuel_formulas_after_bulk_save():
    qs = (request.form.get("save_return_qs") or "").strip()
    base = url_for("fuel_bp.equipment_group_fuel_formulas_page")
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


def _md_from_formula_add_form() -> MultiDict:
    md = MultiDict()
    for k, v in request.form.items():
        if k.startswith("r_") and k not in ("r_csrf_token",):
            md.add(k[2:], v)
    return md


def _merge_interval_onto_md(md: MultiDict, *, y_min: int, y_max: int) -> None:
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


def _resolve_filter_year_interval_from_md(md: MultiDict) -> tuple[int, int]:
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
    return sy, ey


@fuel_bp.route("/equipment_group_fuel_formulas", methods=["GET", "POST"])
@login_required
def equipment_group_fuel_formulas_page():
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(
            url_for(
                "fuel_bp.equipment_group_fuel_formulas_page",
                **extract_filters_from_form(request.form),
            )
        )

    filters = extract_filters_from_args(request.args)
    page = request.args.get("page", 1, type=int)
    filters.pop("page", None)
    per_page_param = request.args.get("per_page", "25")
    show_all = str(per_page_param).lower() == "all"
    per_page = (
        "all"
        if show_all
        else int(per_page_param)
        if str(per_page_param).isdigit()
        else 25
    )

    start_year, end_year = _resolve_year_interval()
    filter_year_list = [y.number for y in get_year_list_full()]
    year_list_for_edit = get_year_list_full()

    try:
        rounding_digits = int(request.args.get("rounding_digits"))
    except (ValueError, TypeError):
        rounding_digits = 1

    formula_data = get_equipment_groups_with_fuel_formula_data(
        filters=filters,
        per_page=per_page,
        page=page,
        start_year=start_year,
        end_year=end_year,
        show_all=show_all,
    )

    rows = formula_data.get("rows") or []
    rows = expand_formula_rows_for_year_interval(rows, start_year, end_year)

    def _row_sort_key(item):
        eg, param = item
        y = getattr(param, "year_number", None) if param is not None else None
        v = getattr(param, "variant_number", None) if param is not None else None
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid, y or 0, v or 0)

    rows = sorted(rows, key=_row_sort_key)

    # Как на ТЭП / удельных: иерархия EST→UES→RES, пагинация по группам ОБ.
    hierarchy_full = build_equipment_group_specific_fuel_consumption_hierarchy(rows)
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_suppress_aggregate_rows_to_hierarchy,
        should_suppress_aggregate_rows_for_filters,
    )
    if should_suppress_aggregate_rows_for_filters(filters):
        apply_suppress_aggregate_rows_to_hierarchy(hierarchy_full)
    total_eg_count = count_fuel_eg_groups_in_hierarchy(hierarchy_full)
    if show_all:
        equipment_group_fuel_formula_hierarchy = hierarchy_full
        total_pages = 1
        current_page = 1
    else:
        (
            equipment_group_fuel_formula_hierarchy,
            total_eg_count,
            total_pages,
            current_page,
        ) = paginate_fuel_eg_station_hierarchy(
            hierarchy_full,
            page,
            per_page,
            [],
        )

    if (
        not fuel_eg_station_hierarchy_nonempty(equipment_group_fuel_formula_hierarchy)
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
            url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args)
        )

    # Строки текущей страницы (для fallback без иерархии и bulk_edit_group_ids).
    page_rows: list = []
    for est_block in equipment_group_fuel_formula_hierarchy or []:
        for ues_block in est_block.get("ues_list", []):
            for res_block in ues_block.get("res_list", []):
                for station_block in res_block.get("station_blocks", []):
                    for gb in station_block.get("group_blocks") or []:
                        page_rows.extend(gb.get("rows") or [])

    def _eg_group_key(row):
        eg = row[0] if row else None
        return getattr(eg, "id", None) if eg is not None else None

    equipment_group_fuel_formula_row_groups = [
        list(g) for _, g in groupby(page_rows, key=_eg_group_key)
    ]

    bulk_edit_equipment_group_ids = sorted(
        {
            int(eg.id)
            for eg, _ in page_rows
            if eg is not None and getattr(eg, "id", None) is not None
        }
    )

    formtxt_editable_years = formtxt_editable_year_numbers_for_version()

    # Жёлтая подсветка при изменении Nуст к предыдущему году — как на ТЭП
    fuel_params_data = get_equipment_groups_with_fuel_params_data(
        filters=filters,
        per_page="all",
        page=1,
        start_year=start_year,
        end_year=end_year,
        show_all=True,
    )
    fuel_param_warn_sets = build_fuel_param_row_warn_sets(
        fuel_params_data.get("rows") or []
    )
    nust_changed_from_prev_year_rows = fuel_param_warn_sets[
        "nust_changed_from_prev_year_rows"
    ]

    # Интервал как у ТЭП: start=базовый, end=расчётный → «Назад к расчёту»
    calculation_back_url = fuel_calculation_form_url_from_tep_edit_args(request.args)

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

    return render_template(
        "fuel/fuel_formula/stations_equipment_group_fuel_formula.html",
        has_active_filters=has_active_filters,
        equipment_group_fuel_formula_hierarchy=equipment_group_fuel_formula_hierarchy,
        equipment_group_fuel_formula_row_groups=equipment_group_fuel_formula_row_groups,
        nust_changed_from_prev_year_rows=nust_changed_from_prev_year_rows,
        formtxt_editable_years=formtxt_editable_years,
        bulk_edit_equipment_group_ids=bulk_edit_equipment_group_ids,
        calculation_back_url=calculation_back_url,
        year_list_for_edit=year_list_for_edit,
        numb1120_filter_choices=formula_data.get("numb1120_filter_choices") or [],
        **context,
    )


@fuel_bp.route("/equipment_group_fuel_formulas/add_year", methods=["POST"])
@login_required
def equipment_group_fuel_formulas_add_year():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав.", "danger")
        return redirect(
            request.referrer or url_for("fuel_bp.equipment_group_fuel_formulas_page")
        )
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return redirect(
            request.referrer or url_for("fuel_bp.equipment_group_fuel_formulas_page")
        )

    id_base = request.form.get("id_base_year", type=int)
    id_target = request.form.get("id_target_year", type=int)
    source_num = _year_number_from_ref_year_id(id_base)
    target_num = _year_number_from_ref_year_id(id_target)
    if source_num is None or id_base is None:
        flash("Выберите базовый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())
    if target_num is None or id_target is None:
        flash("Выберите расчитываемый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())
    if source_num == target_num:
        flash("Базовый и расчитываемый год должны различаться.", "warning")
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())

    md = _md_from_formula_add_form()
    filters = extract_filters_from_args(md)
    filters.pop("page", None)
    sy, ey = _resolve_filter_year_interval_from_md(md)

    try:
        copied, skipped, total_groups = copy_fuel_formulas_between_years_for_filters(
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
        return _redirect_equipment_group_fuel_formulas(md)

    _merge_interval_onto_md(md, y_min=target_num, y_max=target_num)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не скопировано ни одной формулы: нет данных за {source_num} г. "
            f"у выбранных групп (в выборке: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопированы формулы с {source_num} г. на {target_num} г.: "
            f"операций {copied} (в выборке групп: {total_groups}, "
            f"без данных за {source_num} г.: {skipped}).",
            "success",
        )
    return _redirect_equipment_group_fuel_formulas(md)


@fuel_bp.route("/equipment_group_fuel_formulas/add_period", methods=["POST"])
@login_required
def equipment_group_fuel_formulas_add_period():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав.", "danger")
        return redirect(
            request.referrer or url_for("fuel_bp.equipment_group_fuel_formulas_page")
        )
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return redirect(
            request.referrer or url_for("fuel_bp.equipment_group_fuel_formulas_page")
        )

    id_base = request.form.get("id_base_year", type=int)
    id_from = request.form.get("id_year_from", type=int)
    id_to = request.form.get("id_year_to", type=int)
    source_num = _year_number_from_ref_year_id(id_base)
    n_from = _year_number_from_ref_year_id(id_from)
    n_to = _year_number_from_ref_year_id(id_to)

    if source_num is None or id_base is None:
        flash("Выберите базовый год в справочнике.", "danger")
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())
    if n_from is None or n_to is None:
        flash("Укажите границы периода (расчитываемые годы) в справочнике.", "danger")
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())

    n_lo, n_hi = (n_from, n_to) if n_from <= n_to else (n_to, n_from)
    for n in range(n_lo, n_hi + 1):
        if not any(
            y.number is not None and int(y.number) == n for y in get_year_list_full()
        ):
            flash(
                f"В справочнике текущей версии БД нет года с номером {n}.",
                "danger",
            )
            return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())

    target_nums = [n for n in range(n_lo, n_hi + 1) if n != source_num]
    if not target_nums:
        flash(
            "Период не содержит расчитываемых годов, отличных от базового: нечего копировать.",
            "warning",
        )
        return _redirect_equipment_group_fuel_formulas(_md_from_formula_add_form())

    md = _md_from_formula_add_form()
    filters = extract_filters_from_args(md)
    filters.pop("page", None)
    sy, ey = _resolve_filter_year_interval_from_md(md)

    try:
        copied, skipped, total_groups = copy_fuel_formulas_between_years_for_filters(
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
        return _redirect_equipment_group_fuel_formulas(md)

    _merge_interval_onto_md(md, y_min=n_lo, y_max=n_hi)

    if total_groups == 0:
        flash("По текущим фильтрам не найдено групп оборудования.", "warning")
    elif copied == 0:
        flash(
            f"Не скопировано ни одной формулы: нет данных за {source_num} г. "
            f"(в выборке: {total_groups}, пропущено: {skipped}).",
            "warning",
        )
    else:
        flash(
            f"Скопированы формулы с {source_num} г. на годы {n_lo}—{n_hi}: "
            f"операций {copied} (в выборке групп: {total_groups}).",
            "success",
        )
    return _redirect_equipment_group_fuel_formulas(md)


@fuel_bp.route("/equipment_group_fuel_formulas/save", methods=["POST"])
@login_required
def equipment_group_fuel_formulas_save():
    """Массовое сохранение formtxt; numb1120 ← numb группы; только годы «текущий»/«план»."""
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для сохранения.", "danger")
        return _redirect_equipment_group_fuel_formulas_after_bulk_save()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_equipment_group_fuel_formulas_after_bulk_save()

    md = MultiDict(
        parse_qsl((request.form.get("save_return_qs") or "").strip(), keep_blank_values=True)
    )
    filters = extract_filters_from_args(md)
    filters.pop("page", None)

    start_year = request.form.get("start_year", type=int)
    end_year = request.form.get("end_year", type=int)
    if start_year is None or end_year is None:
        flash("Не указан интервал лет (start_year / end_year).", "danger")
        return _redirect_equipment_group_fuel_formulas_after_bulk_save()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    gids_from_post: set[int] = set()
    for k in request.form:
        m = _BULK_FUEL_FORMULA_FIELD_RE.match(k)
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
        return _redirect_equipment_group_fuel_formulas_after_bulk_save()
    if not ids:
        flash(
            "Нет допустимых групп оборудования для сохранения (проверьте фильтры).",
            "warning",
        )
        return _redirect_equipment_group_fuel_formulas_after_bulk_save()

    try:
        changed, errs = apply_fuel_formula_bulk_save_from_form(
            request.form,
            equipment_group_ids=ids,
            start_year=start_year,
            end_year=end_year,
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
        current_app.logger.exception("[FUEL_FORMULA_BULK_SAVE] failed")
        flash(f"Ошибка сохранения: {exc}", "danger")

    return _redirect_equipment_group_fuel_formulas_after_bulk_save()


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
            "[IMPORT_FUEL_FORMULA] ValueError: %s", e, exc_info=True
        )
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.exception("[IMPORT_FUEL_FORMULA] failed")
        flash(f"Ошибка импорта: {e}", "danger")

    return redirect(url_for("fuel_bp.equipment_group_fuel_formulas_page", **redirect_args))
