# -*- coding: utf-8 -*-
"""
UI и API для пакетного пересчета топлива по фильтрам станций.
Эндпоинты по параметрам распределения (DistributionParameter) оставлены для вызова из кода/API.
"""
from __future__ import annotations

from typing import Any

from config import SCHEMA_FUEL
from flask import current_app, jsonify, render_template, request, session
from flask_login import login_required

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.distribution_parameter_calculation_services import (
    DistributionParameterCalculationService,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_batch_calculation_services import (
    BatchCalculationResult,
    EquipmentGroupFuelBatchCalculationService,
)
from app.fuel.services.equipment_groups.fuel_param_batch_preview_columns import (
    resolve_fuel_param_preview_columns,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_services import (
    map_latest_specific_y_by_equipment_group_id,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_sipr_end_year,
    get_sipr_start_year,
    get_year_list_full,
)
from app.generation.services.station_services.filters_services import (
    get_territorial_filter_reference_data,
)
from app.fuel.services.stations.stations_equipment_groups_services import (
    get_filtered_equipment_group_ids,
)
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_write_reference import (
    get_fuel_calculation_write_reference,
)
from . import fuel_bp

TERRITORIAL_FILTER_KEYS = (
    "energy_system_type_filter",
    "union_energy_system_filter",
    "regional_energy_system_filter",
    "federal_district_filter",
    "regional_district_filter",
)


def _parse_bool_json(value: object, default: bool = False) -> bool:
    """Безопасное булево из JSON (в т.ч. строки «false»/«0» не дают True)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _station_filters_from_batch_body(data: dict) -> dict:
    """Фильтры из JSON тела запроса (те же ключи, что у station_list)."""
    out: dict = {}
    for key in TERRITORIAL_FILTER_KEYS:
        raw = data.get(key)
        if not isinstance(raw, list):
            continue
        vals: list[int] = []
        for x in raw:
            try:
                if x is None or x == "":
                    continue
                vals.append(int(x))
            except (TypeError, ValueError):
                continue
        if vals:
            out[key] = vals
    name = (data.get("equipment_group_name_filter") or "").strip()
    if name:
        out["equipment_group_name_filter"] = name
    return out


def _has_territorial_or_name_filter(station_filters: dict) -> bool:
    if (station_filters.get("equipment_group_name_filter") or "").strip():
        return True
    return any(station_filters.get(k) for k in TERRITORIAL_FILTER_KEYS)


def _parse_year_from_json(value: object, *, field: str = "year_number") -> tuple[int | None, str | None]:
    """Разбор года из JSON (в т.ч. после null из JS при NaN)."""
    if value is None or value == "":
        return None, "Укажите год расчета (целое число)."
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f"Поле «{field}» должно быть целым числом."


def _resolve_equipment_group_ids_from_station_filters(
    *,
    station_filters: dict,
    filter_start_year: int | None,
    filter_end_year: int | None,
) -> list[int]:
    fs = filter_start_year if filter_start_year is not None else get_filter_start_year()
    fe = filter_end_year if filter_end_year is not None else get_filter_end_year()
    ids_set = get_filtered_equipment_group_ids(
        station_filters,
        start_year=fs,
        end_year=fe,
    )
    return sorted(ids_set)


def _batch_to_dict(batch: BatchCalculationResult) -> dict[str, Any]:
    return {
        "total": batch.total,
        "success_count": batch.success_count,
        "error_count": batch.error_count,
        "ok_ids": batch.ok_ids,
        "failed_ids": batch.failed_ids,
        "items": [
            {
                "equipment_group_id": it.equipment_group_id,
                "success": it.success,
                "error": it.error,
                "calculated": it.calculated,
            }
            for it in batch.items
        ],
    }


def _parse_equipment_group_ids_from_json(data: dict) -> tuple[list[int] | None, str | None]:
    raw = data.get("equipment_group_ids")
    if not isinstance(raw, list) or not raw:
        return None, "Укажите непустой список equipment_group_ids."
    ids: list[int] = []
    for x in raw:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            return None, "equipment_group_ids: ожидаются целые числа."
    return sorted(set(ids)), None


def _parse_year_numbers_for_preview(data: dict) -> tuple[list[int] | None, str | None]:
    raw = data.get("year_numbers")
    if isinstance(raw, list) and len(raw) > 0:
        years: list[int] = []
        for x in raw:
            try:
                years.append(int(x))
            except (TypeError, ValueError):
                return None, "year_numbers: ожидаются целые числа."
        return sorted(set(years)), None
    yn = data.get("year_number")
    if yn is None or yn == "":
        return None, "Укажите year_number или непустой year_numbers."
    y, err = _parse_year_from_json(yn)
    if err:
        return None, err
    return [y], None


def _csrf_ok() -> bool:
    expected = session.get("csrf_token") or ""
    if not str(expected).strip():
        return True
    token = request.headers.get("X-CSRF-Token") or (
        request.get_json(silent=True) or {}
    ).get("csrf_token") or request.form.get("csrf_token")
    return bool(token) and token == expected


@fuel_bp.route("/fuel_batch_recalc_hub", methods=["GET"])
@login_required
def fuel_batch_recalc_hub():
    """Промежуточное меню: формулы топлива и пакетный пересчет."""
    return render_template("fuel/batch_recalc/fuel_batch_recalc_hub.html")


@fuel_bp.route("/equipment_group_fuel_batch_calculation", methods=["GET"])
@login_required
def equipment_group_fuel_batch_calculation_page():
    years = [y.number for y in get_year_list_full()]
    # Как get_station_list_template_context / fuel station_filters_third_row: диапазон лет из YearService текущей версии БД
    filter_year_list = list(range(get_filter_start_year(), get_filter_end_year() + 1))
    # Границы СиПР из номера/настроек версии БД (как «СиПР 2026–2031» → начало 2026, конец 2031)
    sipr_start = get_sipr_start_year()
    sipr_end = get_sipr_end_year()
    if filter_year_list:
        fy_min = filter_year_list[0]
        fy_max = filter_year_list[-1]
        default_batch_filter_start_year = max(fy_min, min(sipr_start, fy_max))
        default_batch_filter_end_year = max(fy_min, min(sipr_end, fy_max))
        if default_batch_filter_start_year > default_batch_filter_end_year:
            default_batch_filter_start_year, default_batch_filter_end_year = fy_min, fy_max
    else:
        default_batch_filter_start_year = sipr_start
        default_batch_filter_end_year = sipr_end
    # Год расчёта по умолчанию = год конца (отбора / СиПР) + 1, но только из списка лет справочника
    preferred_calc_year = default_batch_filter_end_year + 1
    if years:
        if preferred_calc_year in years:
            default_year = preferred_calc_year
        elif preferred_calc_year < years[0]:
            default_year = years[0]
        elif preferred_calc_year > years[-1]:
            default_year = years[-1]
        else:
            default_year = next((y for y in years if y >= preferred_calc_year), years[-1])
    else:
        default_year = preferred_calc_year
    territorial_filters_data = get_territorial_filter_reference_data()

    return render_template(
        "fuel/batch_recalc/equipment_group_fuel_batch_calculation.html",
        years=years,
        default_year=default_year,
        filter_year_list=filter_year_list,
        default_batch_filter_start_year=default_batch_filter_start_year,
        default_batch_filter_end_year=default_batch_filter_end_year,
        territorial_filters_data=territorial_filters_data,
        calculation_write_reference=get_fuel_calculation_write_reference(),
    )


@fuel_bp.route("/equipment_group_fuel_batch_calculation/resolve_group_ids", methods=["POST"])
@login_required
def equipment_group_fuel_batch_calculation_resolve_group_ids():
    """Предпросмотр: список id групп по тем же фильтрам, что и station_list (без пересчета)."""
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Недействительный CSRF-токен"}), 403

    data = request.get_json(silent=True) or {}
    try:
        year_number = int(data.get("year_number") or data.get("year") or 0)
    except (TypeError, ValueError):
        year_number = None

    station_filters = _station_filters_from_batch_body(data)
    if not _has_territorial_or_name_filter(station_filters):
        return jsonify(
            {
                "ok": False,
                "error": "Укажите фильтры территории или часть названия группы.",
            },
        ), 400

    try:
        fs = data.get("filter_start_year")
        fe = data.get("filter_end_year")
        filter_start_year = int(fs) if fs not in (None, "") else None
        filter_end_year = int(fe) if fe not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Неверные filter_start_year / filter_end_year"}), 400

    if year_number and filter_start_year is None and filter_end_year is None:
        filter_start_year = filter_end_year = year_number
    elif filter_start_year is None and filter_end_year is None:
        filter_start_year = get_filter_start_year()
        filter_end_year = get_filter_end_year()
    elif filter_start_year is None:
        filter_start_year = filter_end_year
    elif filter_end_year is None:
        filter_end_year = filter_start_year

    ids = _resolve_equipment_group_ids_from_station_filters(
        station_filters=station_filters,
        filter_start_year=filter_start_year,
        filter_end_year=filter_end_year,
    )
    return jsonify(
        {
            "ok": True,
            "count": len(ids),
            "equipment_group_ids": ids,
            "filter_start_year": filter_start_year,
            "filter_end_year": filter_end_year,
            "station_filters": station_filters,
            "note": "Пересчёт не выполнялся; calculation_write_reference — куда пишутся данные при запуске пакета.",
            "calculation_write_reference": get_fuel_calculation_write_reference(),
        }
    )


@fuel_bp.route("/equipment_group_fuel_batch_calculation/batch", methods=["POST"])
@login_required
def equipment_group_fuel_batch_calculation_batch_api():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Недействительный CSRF-токен"}), 403

    data = request.get_json(silent=True) or {}
    year_number, year_err = _parse_year_from_json(data.get("year_number"))
    if year_err:
        current_app.logger.info("equipment_group_fuel_batch_calculation/batch: %s", year_err)
        return jsonify({"ok": False, "error": year_err}), 400

    station_filters = _station_filters_from_batch_body(data)
    if not _has_territorial_or_name_filter(station_filters):
        msg = (
            "Укажите тип ЭС, ОЭС, РЭС, ФО и/или субъект РФ и/или часть названия группы "
            "(хотя бы одно условие)."
        )
        current_app.logger.info("equipment_group_fuel_batch_calculation/batch: no filters")
        return jsonify({"ok": False, "error": msg}), 400
    try:
        fs = data.get("filter_start_year")
        fe = data.get("filter_end_year")
        filter_start_year = int(fs) if fs not in (None, "") else None
        filter_end_year = int(fe) if fe not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Неверные filter_start_year / filter_end_year"}), 400
    if filter_start_year is None and filter_end_year is None:
        filter_start_year = filter_end_year = year_number
    elif filter_start_year is None:
        filter_start_year = filter_end_year
    elif filter_end_year is None:
        filter_end_year = filter_start_year

    equipment_group_ids = _resolve_equipment_group_ids_from_station_filters(
        station_filters=station_filters,
        filter_start_year=filter_start_year,
        filter_end_year=filter_end_year,
    )
    if not equipment_group_ids:
        current_app.logger.info(
            "equipment_group_fuel_batch_calculation/batch: zero groups for filters %s",
            station_filters,
        )
        return jsonify(
            {
                "ok": False,
                "error": "По выбранным фильтрам не найдено ни одной группы оборудования (привязка к станциям).",
                "station_filters": station_filters,
            },
        ), 400

    db_vid = data.get("database_version_id")
    if db_vid not in (None, ""):
        try:
            database_version_id = int(db_vid)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Неверный database_version_id"}), 400
    else:
        database_version_id = get_current_db_version_id()

    variant_number = int(data.get("variant_number") or 0)

    # Для UI режим по умолчанию: каждая группа считается отдельно
    commit_each = _parse_bool_json(data.get("commit_each"), default=True)
    final_commit = _parse_bool_json(data.get("final_commit"), default=True)
    stop_on_error = _parse_bool_json(data.get("stop_on_error"), default=False)
    strict_formula_validation = _parse_bool_json(
        data.get("strict_formula_validation"),
        default=False,
    )
    chunk_size = int(data.get("chunk_size") or 200)

    svc = EquipmentGroupFuelBatchCalculationService()
    try:
        batch = svc.calculate_for_many_groups(
            equipment_group_ids=equipment_group_ids,
            year_number=year_number,
            database_version_id=database_version_id,
            variant_number=variant_number,
            strict_formula_validation=strict_formula_validation,
            commit_each=commit_each,
            final_commit=final_commit,
            stop_on_error=stop_on_error,
            chunk_size=chunk_size,
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(
        {
            "ok": True,
            "batch": _batch_to_dict(batch),
            "equipment_group_ids": equipment_group_ids,
            "station_filters": station_filters,
            "calculation_run": {
                "year_number": year_number,
                "database_version_id": database_version_id,
                "variant_number": variant_number,
                "groups_total": len(equipment_group_ids),
                "note": (
                    "Для каждой успешной группы calculate_group_year записывает значения в строки "
                    f"{SCHEMA_FUEL}.gs_fue_equipment_group_fuel_param и "
                    f"{SCHEMA_FUEL}.gs_fue_equipment_group_extra_fuel_param "
                    "с тем же year_number и обновлённым database_version_id."
                ),
            },
            "calculation_write_reference": get_fuel_calculation_write_reference(),
        }
    )


@fuel_bp.route("/equipment_group_fuel_batch_calculation/fuel_params_tables", methods=["POST"])
@login_required
def equipment_group_fuel_batch_fuel_params_tables_api():
    """
    HTML-фрагменты таблиц как на stations_equipment_group_fuel_params и
    stations_equipment_group_extra_fuel_params для списка групп и года(лет).

    JSON-тело может содержать ``fuel_param_column_set``: ``full`` (по умолчанию) —
    все колонки как на полной выгрузке; ``calculation`` — только баланс энергии и
    расчётные показатели по строке (страница «Расчёт»).
    """
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Недействительный CSRF-токен"}), 403

    data = request.get_json(silent=True) or {}
    ids, ids_err = _parse_equipment_group_ids_from_json(data)
    if ids_err:
        return jsonify({"ok": False, "error": ids_err}), 400

    years_list, err_years = _parse_year_numbers_for_preview(data)
    if err_years or not years_list:
        return jsonify({"ok": False, "error": err_years or "Укажите год(ы)."}), 400

    try:
        rounding_digits = int(data.get("rounding_digits", 1))
    except (TypeError, ValueError):
        rounding_digits = 1
    if rounding_digits < 0:
        rounding_digits = 1

    fuel_param_columns, collapsible_ugol_attrs = resolve_fuel_param_preview_columns(
        data.get("fuel_param_column_set")
    )

    from app.common.services.database_version_filter import filter_by_db_version
    from app.refdata.models.fuels.fuel_model import Fuel
    from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_services import (
        build_equipment_group_extra_fuel_params_hierarchy,
        get_equipment_groups_with_extra_fuel_params_data,
    )
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        build_equipment_group_fuel_params_hierarchy,
        build_name_maps_from_rows,
        get_equipment_groups_with_fuel_params_data,
    )

    fuel_query = filter_by_db_version(Fuel.query, Fuel)
    fuel_nazvl_to_name_main = {
        row.nazvl: (row.name[0].lower() + row.name[1:])
        if row.name and len(row.name) > 0
        else (row.name or "")
        for row in fuel_query.with_entities(Fuel.nazvl, Fuel.name)
        if row.nazvl and row.name
    }
    fuel_nazvl_to_name_extra = dict(fuel_nazvl_to_name_main)
    fuel_nazvl_to_name_extra["gtt"] = "газотурбинное топливо"

    filters = {"equipment_group_ids": ids}
    sections: list[dict[str, Any]] = []

    for y in years_list:
        fuel_data = get_equipment_groups_with_fuel_params_data(
            filters=filters,
            per_page="all",
            page=1,
            start_year=y,
            end_year=y,
            show_all=True,
        )
        rows = fuel_data.get("rows") or []
        name_maps = build_name_maps_from_rows(rows)
        hierarchy = build_equipment_group_fuel_params_hierarchy(
            rows, use_equipment_group_hierarchy_only=False
        )

        extra_data = get_equipment_groups_with_extra_fuel_params_data(
            filters=filters,
            per_page="all",
            page=1,
            start_year=y,
            end_year=y,
            show_all=True,
        )
        extra_rows = extra_data.get("rows") or []
        extra_hierarchy = build_equipment_group_extra_fuel_params_hierarchy(extra_rows)

        tid_main = f"batchFuelParams_{y}"
        tid_extra = f"batchExtraFuelParams_{y}"

        column_set_key = (data.get("fuel_param_column_set") or "").strip().lower()
        is_calculation_preview = column_set_key == "calculation"
        disable_auto_export_excel = bool(data.get("disable_auto_export_excel"))
        specific_y_by_group_id: dict[int, object | None] = {}
        if is_calculation_preview:
            specific_y_by_group_id = map_latest_specific_y_by_equipment_group_id(
                ids,
                y,
                effective_db_version_id=get_current_db_version_id(),
            )

        html_main = render_template(
            "fuel/batch_recalc/_batch_preview_fuel_params_table.html",
            disable_auto_export_excel=disable_auto_export_excel,
            table_element_id=tid_main,
            selected_year=y,
            equipment_group_fuel_params_hierarchy=hierarchy,
            equipment_group_fuel_param_rows=rows,
            fuel_param_columns=fuel_param_columns,
            collapsible_ugol_attrs=collapsible_ugol_attrs,
            specific_y_by_group_id=specific_y_by_group_id,
            show_ewtp_formula_hint=is_calculation_preview,
            fuel_nazvl_to_name=fuel_nazvl_to_name_main,
            obor_name_map=name_maps.get("obor_name_map", {}),
            obl_name_map=name_maps.get("obl_name_map", {}),
            dep_name_map=name_maps.get("dep_name_map", {}),
            oes_name_map=name_maps.get("oes_name_map", {}),
            er_name_map=name_maps.get("er_name_map", {}),
            gk_name_map=name_maps.get("gk_name_map", {}),
            be_name_map=name_maps.get("be_name_map", {}),
            rounding_digits=rounding_digits,
        )
        html_extra = render_template(
            "fuel/batch_recalc/_batch_preview_extra_fuel_params_table.html",
            disable_auto_export_excel=disable_auto_export_excel,
            table_element_id=tid_extra,
            selected_year=y,
            equipment_group_extra_fuel_params_hierarchy=extra_hierarchy,
            equipment_group_extra_fuel_param_rows=extra_rows,
            fuel_nazvl_to_name=fuel_nazvl_to_name_extra,
            rounding_digits=rounding_digits,
        )
        sections.append(
            {
                "year": y,
                "html_fuel_params": html_main,
                "html_extra_fuel_params": html_extra,
            }
        )

    return jsonify({"ok": True, "years": years_list, "sections": sections})


@fuel_bp.route("/equipment_group_fuel_batch_calculation/distribution", methods=["POST"])
@login_required
def equipment_group_fuel_batch_calculation_distribution_api():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Недействительный CSRF-токен"}), 403

    data = request.get_json(silent=True) or {}
    try:
        distribution_param_id = int(data["distribution_param_id"])
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"ok": False, "error": f"Неверный distribution_param_id: {e}"}), 400

    db_vid = data.get("database_version_id")
    if db_vid not in (None, ""):
        try:
            database_version_id = int(db_vid)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Неверный database_version_id"}), 400
    else:
        database_version_id = get_current_db_version_id()

    variant_number = int(data.get("variant_number") or 0)
    commit_each = _parse_bool_json(data.get("commit_each"), default=True)
    final_commit = _parse_bool_json(data.get("final_commit"), default=True)
    stop_on_error = _parse_bool_json(data.get("stop_on_error"), default=False)
    strict_formula_validation = _parse_bool_json(
        data.get("strict_formula_validation"),
        default=False,
    )

    svc = DistributionParameterCalculationService()
    try:
        run = svc.calculate_from_distribution_param(
            distribution_param_id=distribution_param_id,
            database_version_id=database_version_id,
            variant_number=variant_number,
            strict_formula_validation=strict_formula_validation,
            commit_each=commit_each,
            final_commit=final_commit,
            stop_on_error=stop_on_error,
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500

    br = run.batch_result
    return jsonify(
        {
            "ok": True,
            "run": {
                "distribution_parameter_id": run.distribution_parameter_id,
                "distribution_name": run.distribution_name,
                "year_number": run.year_number,
                "selected_group_ids": run.selected_group_ids,
                "selected_count": len(run.selected_group_ids),
                "batch": _batch_to_dict(br) if br else None,
            },
        }
    )


@fuel_bp.route("/equipment_group_fuel_batch_calculation/distribution_multi", methods=["POST"])
@login_required
def equipment_group_fuel_batch_calculation_distribution_multi_api():
    if not _csrf_ok():
        return jsonify({"ok": False, "error": "Недействительный CSRF-токен"}), 403

    data = request.get_json(silent=True) or {}
    ids = data.get("distribution_param_ids")
    if isinstance(ids, list) and ids:
        distribution_param_ids = [int(x) for x in ids]
    else:
        distribution_param_ids = None

    name = (data.get("name") or "").strip() or None
    try:
        year_number = int(data["year_number"]) if data.get("year_number") not in (None, "") else None
    except (TypeError, ValueError):
        year_number = None

    db_vid = data.get("database_version_id")
    if db_vid not in (None, ""):
        try:
            database_version_id = int(db_vid)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Неверный database_version_id"}), 400
    else:
        database_version_id = get_current_db_version_id()

    variant_number = int(data.get("variant_number") or 0)
    commit_each = _parse_bool_json(data.get("commit_each"), default=True)
    final_commit = _parse_bool_json(data.get("final_commit"), default=True)
    stop_on_error = _parse_bool_json(data.get("stop_on_error"), default=False)
    strict_formula_validation = _parse_bool_json(
        data.get("strict_formula_validation"),
        default=False,
    )

    if not distribution_param_ids and not name and year_number is None:
        return jsonify(
            {
                "ok": False,
                "error": (
                    "Задайте наименование ОЭС (name, как в справочнике UnionEnergySystem), "
                    "год и/или список id — иначе будут выбраны все строки параметров."
                ),
            },
        ), 400

    svc = DistributionParameterCalculationService()
    try:
        runs = svc.calculate_from_distribution_params(
            distribution_param_ids=distribution_param_ids,
            name=name,
            year_number=year_number,
            database_version_id=database_version_id,
            variant_number=variant_number,
            strict_formula_validation=strict_formula_validation,
            commit_each=commit_each,
            final_commit=final_commit,
            stop_on_error=stop_on_error,
        )
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500

    out_runs = []
    for run in runs:
        br = run.batch_result
        out_runs.append(
            {
                "distribution_parameter_id": run.distribution_parameter_id,
                "distribution_name": run.distribution_name,
                "year_number": run.year_number,
                "selected_count": len(run.selected_group_ids),
                "batch": _batch_to_dict(br) if br else None,
            }
        )

    return jsonify({"ok": True, "runs": out_runs, "runs_count": len(out_runs)})
