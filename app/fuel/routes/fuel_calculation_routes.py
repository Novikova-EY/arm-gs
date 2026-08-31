# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import (
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import current_user, login_required
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.models.fue_distribution_parameter_model import (
    DISTRIBUTION_PARAMETER_FIELD_LABELS,
    DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS,
    DistributionParameter,
)
from app.fuel.models.fue_restriction_model import (
    FUEL_RESTRICTION_LIST_COLUMN_HEADINGS,
)
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_list_full,
)
from app.common.services.get_services.stations.tes_type_get_services import (
    get_tes_type_list_full,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_list_full,
)
from app.fuel.routes.coefficient_stage_routes import (
    coeff_tech_type_table,
    get_coeff_tech_aggregate_row,
)
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    FuelCoefficientCalculationService,
)
from app.fuel.services.distribution_parameters.distribution_parameters_list_services import (
    distribution_parameter_year_numbers_for_filter_dropdown,
    get_distribution_parameters_list,
)
from app.fuel.services.restrictions.fuel_restrictions_list_services import (
    build_restriction_obl_name_map,
    build_restriction_oes_name_map,
    get_fuel_restrictions_list,
    get_restriction_obl_choices,
    get_restriction_oes_choices,
)
from app.fuel.services.restrictions.fuel_restrictions_save_services import (
    apply_fuel_restrictions_save_from_form,
)
from app.fuel.services.restrictions.export_fuel_restrictions_services import (
    export_fuel_restrictions_to_excel,
)
from app.fuel.services.restrictions.import_fuel_restrictions_services import (
    import_fuel_restrictions_from_upload,
)
from app.fuel.services.distribution_parameters.distribution_parameters_bulk_copy_services import (
    build_distribution_parameters_bulk_copy_rows,
    build_distribution_parameters_bulk_copy_rows_for_period,
)
from app.fuel.services.distribution_parameters.distribution_parameters_save_services import (
    apply_distribution_parameters_bulk_apply_from_payload,
    apply_distribution_parameters_save_from_form,
)
from app.fuel.services.distribution_parameters.export_distribution_parameters_services import (
    export_distribution_parameters_to_excel,
)
from app.fuel.services.distribution_parameters.import_distribution_parameters_services import (
    import_distribution_parameters_from_upload,
)
from app.fuel.services.calculation.fuel.fuel_stage_services import FuelStageService
from app.fuel.services.equipment_groups.composite_calc_consistency_check_services import (
    equipment_group_ids_for_composite_energy_level_issues,
    find_composite_energy_level_issues,
)
from app.fuel.services.calculation.ensure_calculation_year_data_services import (
    ensure_calculation_year_data_from_base,
)
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    has_any_filters,
)
from app.extensions import db
from app.common.services.help_services import format_decimal_trim_for_display
from app.fuel.routes.fuel_calculation_common import (
    FUEL_COEFF_LAST_RUN_SESSION_KEY,
    FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY,
    FUEL_NR_HFIX_PENDING_SESSION_KEY,
    FUEL_STAGE_LAST_RUN_SESSION_KEY,
    fuel_calculation_form_query_string,
    fuel_calculation_tep_edit_query_string,
)
from . import fuel_bp
from app.fuel.services.formula_text.fuel_formula_text_services import (
    get_coeff_cell_tooltips,
    get_restriction_column_formulas,
)


def _d_decimal(val):
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _cptp_for_coeff_table(selected_row, coeff_calc_year_display):
    """
    Доля %тп по формуле Access: cptp = csumetp / E * 100.

    Знаменатель E — актуальное «Ераспред» из параметра (`selected_row.e`), числитель — `cetp` из сводки/превью,
    чтобы колонка совпадала с введённым E без обязательного повторного запуска «Коэфф» после правки параметра.
    Если E ≤ 0, показываем сохранённое cptp (уже посчитанное с запасным знаменателем ΣE в сервисе).
    """
    if coeff_calc_year_display is None:
        return None
    cetp = _d_decimal(getattr(coeff_calc_year_display, "cetp", None))
    if cetp is None:
        return None
    e_par = _d_decimal(getattr(selected_row, "e", None)) if selected_row else None
    if e_par is not None and e_par > 0:
        return cetp / e_par * Decimal("100")
    return _d_decimal(getattr(coeff_calc_year_display, "cptp", None))


def _coeff_ratio_row(
    selected_row,
    coeff_summary,
    coeff_base_preview,
    coeff_calc_year_display,
    coeff_calc_year_is_preview: bool,
):
    """
    Третья строка таблицы «Коэфф»: PE, PQ, Pотр, PH1 (как в Access после Кнопка5_Click).

    При наличии сводки — из БД (или восстановление из полей сводки, если коэффициенты не записаны).
    В режиме предпросмотра — из агрегатов базового года и расчёта по текущим данным.
    """
    if selected_row is None or coeff_calc_year_display is None:
        return None
    if coeff_summary is not None:
        e_tgt = _d_decimal(coeff_summary.e_target)
        be = _d_decimal(coeff_summary.be)
        betp = _d_decimal(coeff_summary.betp)
        cetp = _d_decimal(coeff_summary.cetp)
        bq = _d_decimal(coeff_summary.bq)
        bqotr = _d_decimal(coeff_summary.bqotr)
        bh = _d_decimal(coeff_summary.bh)
        cq = _d_decimal(coeff_summary.cq)
        cqotr = _d_decimal(coeff_summary.cqotr)
        ch = _d_decimal(coeff_summary.ch)
        pe = _d_decimal(coeff_summary.pe)
        pq = _d_decimal(coeff_summary.pq)
        potr = _d_decimal(coeff_summary.potr)
        ph1 = _d_decimal(coeff_summary.ph1)
        if pe is None and e_tgt is not None and be is not None and be > 0:
            pe = e_tgt / be
        petp = cetp / betp if cetp is not None and betp is not None and betp > 0 else None
        if pq is None and cq is not None and bq is not None and bq > 0:
            pq = cq / bq
        if potr is None and cqotr is not None and bqotr is not None and bqotr > 0:
            potr = cqotr / bqotr
        if ph1 is None and ch is not None and bh is not None and bh > 0:
            ph1 = ch / bh
        return {"pe": pe, "petp": petp, "pq": pq, "potr": potr, "ph1": ph1}
    if not coeff_calc_year_is_preview or coeff_base_preview is None:
        return None
    e_tgt = _d_decimal(getattr(coeff_calc_year_display, "e_target", None))
    cetp = _d_decimal(getattr(coeff_calc_year_display, "cetp", None))
    cq = _d_decimal(getattr(coeff_calc_year_display, "cq", None))
    cqotr = _d_decimal(getattr(coeff_calc_year_display, "cqotr", None))
    ch = _d_decimal(getattr(coeff_calc_year_display, "ch", None))
    be = _d_decimal(coeff_base_preview.get("be"))
    betp = _d_decimal(coeff_base_preview.get("betp"))
    bq = _d_decimal(coeff_base_preview.get("bq"))
    bqotr = _d_decimal(coeff_base_preview.get("bqotr"))
    bh = _d_decimal(coeff_base_preview.get("bh"))
    pe = e_tgt / be if e_tgt is not None and be is not None and be > 0 else None
    petp = cetp / betp if cetp is not None and betp is not None and betp > 0 else None
    pq = cq / bq if cq is not None and bq is not None and bq > 0 else None
    potr = cqotr / bqotr if cqotr is not None and bqotr is not None and bqotr > 0 else None
    ph1 = ch / bh if ch is not None and bh is not None and bh > 0 else None
    return {"pe": pe, "petp": petp, "pq": pq, "potr": potr, "ph1": ph1}


def _nr_hfix_pending_for_page(selected_row: DistributionParameter | None):
    """
    Пауза Распред: список станций NUST>0 / NR=0 / HFIX≠1 для текущего параметра.
    """
    if selected_row is None:
        return None
    raw = session.get(FUEL_NR_HFIX_PENDING_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        if int(raw.get("distribution_parameter_id")) != selected_row.id:
            return None
    except (TypeError, ValueError):
        return None
    candidates = raw.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None

    def _fmt(v):
        if v is None or v == "":
            return "—"
        try:
            # Как ячейки nust/nr/h на equipment_group_fuel_params_edit_data (view).
            return format_decimal_trim_for_display(Decimal(str(v)))
        except Exception:
            return str(v)

    formatted = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        item = dict(c)
        item["nust_display"] = _fmt(c.get("nust"))
        item["nr_display"] = _fmt(c.get("nr"))
        item["h_display"] = _fmt(c.get("h"))
        formatted.append(item)
    return {
        "distribution_parameter_id": selected_row.id,
        "distribution_name": (
            selected_row.union_energy_system.name
            if selected_row.union_energy_system is not None
            else None
        ),
        "year_number": raw.get("year_number"),
        "candidates": formatted,
    }


def _distribution_last_run_display_for_page(selected_row: DistributionParameter | None):
    """
    Результат последнего POST «Распред» для текущего параметра (таблица внизу страницы расчёта).
    """
    if selected_row is None:
        return None
    raw = session.get(FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        if int(raw.get("distribution_parameter_id")) != selected_row.id:
            return None
    except (TypeError, ValueError):
        return None

    def fmt_num(v, digits: int) -> str:
        if v is None or v == "":
            return "—"
        try:
            return format_decimal_trim_for_display(Decimal(str(v)), digits=digits)
        except Exception:
            return str(v)

    return {
        "distribution_name": raw.get("distribution_name") or "—",
        "year_number": raw.get("year_number"),
        "e_target": fmt_num(raw.get("e_target"), 0),
        "total_distributed_e": fmt_num(raw.get("total_distributed_e"), 1),
        "selected_group_count": raw.get("selected_group_count"),
        "processed_group_count": raw.get("processed_group_count"),
        "skipped_group_count": raw.get("skipped_group_count"),
        "updated_fuel_rows": raw.get("updated_fuel_rows"),
        "iterations": raw.get("iterations"),
        "restriction_outer_iterations": raw.get("restriction_outer_iterations"),
        "apply_restrictions": bool(raw.get("apply_restrictions")),
        "final_k": fmt_num(raw.get("final_k"), 0),
        "final_kn": fmt_num(raw.get("final_kn"), 0),
    }


def _fuel_stage_last_run_display_for_page(selected_row: DistributionParameter | None):
    """
    Результат последнего POST «Топливо» для текущего параметра (таблица внизу страницы расчёта).
    """
    if selected_row is None:
        return None
    raw = session.get(FUEL_STAGE_LAST_RUN_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        if int(raw.get("distribution_parameter_id")) != selected_row.id:
            return None
    except (TypeError, ValueError):
        return None

    def fmt_num(v, digits: int) -> str:
        if v is None or v == "":
            return "—"
        try:
            return format_decimal_trim_for_display(Decimal(str(v)), digits=digits)
        except Exception:
            return str(v)

    return {
        "distribution_name": raw.get("distribution_name") or "—",
        "year_number": raw.get("year_number"),
        "selected_group_count": raw.get("selected_group_count"),
        "success_count": raw.get("success_count"),
        "error_count": raw.get("error_count"),
        "calculated_count": raw.get("calculated_count"),
        "total_fuel_b": fmt_num(raw.get("total_fuel_b"), 1),
        "e_target": fmt_num(raw.get("e_target"), 0),
        "sum_e_cyear": fmt_num(raw.get("sum_e_cyear"), 1),
        "delta_e": fmt_num(raw.get("delta_e"), 1),
    }


def _coeff_last_run_display_for_page(selected_row: DistributionParameter | None):
    """
    Метаданные последнего POST «Коэфф» для текущего параметра.
    Числа агрегатов — в основных таблицах Коэфф (сводка БД), здесь — факт запуска.
    """
    if selected_row is None:
        return None
    raw = session.get(FUEL_COEFF_LAST_RUN_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    try:
        if int(raw.get("distribution_parameter_id")) != selected_row.id:
            return None
    except (TypeError, ValueError):
        return None

    def fmt_num(v, digits: int) -> str:
        if v is None or v == "":
            return "—"
        try:
            return format_decimal_trim_for_display(Decimal(str(v)), digits=digits)
        except Exception:
            return str(v)

    trigger = raw.get("trigger") or "run_coeff"
    trigger_label = {
        "run_coeff": "кнопка «Коэфф»",
        "update_tech_hn": "сохранение ЧЧИУМ (hn)",
        "run_distribution": "кнопка «Распред»",
    }.get(trigger, trigger)

    return {
        "distribution_name": raw.get("distribution_name") or "—",
        "year_number": raw.get("year_number"),
        "base_year_number": raw.get("base_year_number"),
        "total_groups": raw.get("total_groups"),
        "updated_fuel_rows": raw.get("updated_fuel_rows"),
        "summary_id": raw.get("summary_id"),
        "e_target": fmt_num(raw.get("e_target"), 0),
        "trigger_label": trigger_label,
    }


def _parse_rounding_digits_from_request() -> int:
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


def _get_coeff_summary_for_distribution_parameter(row: DistributionParameter):
    """
    Сводка этапа «Коэфф» для параметра распределения.

    Только строка с тем же database_version_id, что и при расчёте
    (поле параметра или текущая версия БД); при отсутствии версии — только NULL.
    """
    effective_version = row.database_version_id or get_current_db_version_id()
    if row.year is None:
        return None
    q = DistributionCoefficientSummary.query.filter_by(
        distribution_parameter_id=row.id,
        year_number=row.year.number,
    )
    if effective_version is not None:
        q = q.filter(DistributionCoefficientSummary.database_version_id == effective_version)
    else:
        q = q.filter(DistributionCoefficientSummary.database_version_id.is_(None))
    found = q.order_by(DistributionCoefficientSummary.id.desc()).first()
    if found is not None:
        return found
    # Сводка могла быть записана с другим database_version_id (смена активной версии и т.п.)
    return (
        DistributionCoefficientSummary.query.filter_by(
            distribution_parameter_id=row.id,
            year_number=row.year.number,
        )
        .order_by(DistributionCoefficientSummary.id.desc())
        .first()
    )


@fuel_bp.route("/calculation", methods=["GET"])
@login_required
def fuel_calculation_form():
    filters = extract_filters_from_args(request.args)
    raw_sy = request.args.get("start_year")
    if raw_sy is None or str(raw_sy).strip() == "":
        start_year = None
    else:
        try:
            start_year = int(raw_sy)
        except (TypeError, ValueError):
            start_year = None

    raw_by = request.args.get("base_year")
    base_year_from_query = False
    if raw_by is None or str(raw_by).strip() == "":
        base_year = None
    else:
        try:
            base_year = int(raw_by)
            base_year_from_query = True
        except (TypeError, ValueError):
            base_year = None

    # Расчёт — строго по одной ОЭС (без режима «Все ОЭС»).
    ues_ids_raw = filters.get("union_energy_system_filter") or []
    ues_ids = ues_ids_raw[:1] if ues_ids_raw else []

    matching_distribution_parameters: list = []
    selected_row = None
    # Без выбранной ОЭС параметры не подгружаем — иначе в таблице оказались бы все ОЭС.
    if start_year is not None and ues_ids:
        matching_distribution_parameters = get_distribution_parameters_list(
            year_numbers=[start_year],
            base_year_number=base_year if base_year_from_query else None,
            union_energy_system_ids=ues_ids,
        )
        requested_dp_id = None
        raw_dp_id = request.args.get("distribution_parameter_id")
        if raw_dp_id not in (None, ""):
            try:
                requested_dp_id = int(raw_dp_id)
            except (TypeError, ValueError):
                requested_dp_id = None
        if requested_dp_id is not None:
            for row in matching_distribution_parameters:
                if row.id == requested_dp_id:
                    selected_row = row
                    break
        if selected_row is None and matching_distribution_parameters:
            selected_row = matching_distribution_parameters[0]
        # Подпись в селекте: byear из параметра, если пользователь сам год не задал.
        if not base_year_from_query and selected_row is not None and selected_row.base_year is not None:
            base_year = selected_row.base_year.number

    # Нет строк ТЭП за расчётный год — посев с базового (без формул и удельных:
    # Access Seek year ≤ расчётный, копия 2024 перекрыла бы 2025/2026).
    if (
        start_year is not None
        and base_year is not None
        and start_year != base_year
        and ues_ids
    ):
        try:
            ensure_result = ensure_calculation_year_data_from_base(
                filters,
                base_year=base_year,
                calc_year=start_year,
            )
            if ensure_result.get("did_anything"):
                db.session.commit()
                parts: list[str] = []
                heat = ensure_result.get("heat") or (0, 0, 0)
                formulas = ensure_result.get("formulas") or (0, 0, 0)
                specific = ensure_result.get("specific") or (0, 0, 0)
                hat_q = int(ensure_result.get("hat_q") or 0)
                if heat[0]:
                    parts.append(f"ТЭП: {heat[0]}")
                if formulas[0]:
                    parts.append(f"формулы: {formulas[0]}")
                if specific[0]:
                    parts.append(f"удельные показатели: {specific[0]}")
                if hat_q:
                    parts.append(f"Q из схем теплоснабжения: {hat_q}")
                if parts:
                    flash(
                        f"Для расчётного {start_year} г. обновлены данные "
                        f"({'; '.join(parts)}).",
                        "success",
                    )
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception(
                "ensure_calculation_year_data_from_base failed"
            )
            flash(
                f"Не удалось автоматически добавить данные за {start_year} г.: {exc}",
                "warning",
            )

    apply_restrictions = str(request.args.get("apply_restrictions") or "").strip() in (
        "1",
        "true",
        "on",
        "yes",
    )

    restriction_rows: list = []
    restriction_oes_name_map: dict = {}
    restriction_obl_name_map: dict = {}
    if apply_restrictions and ues_ids and start_year is not None:
        restriction_rows = get_fuel_restrictions_list(
            year_numbers=[start_year],
            union_energy_system_ids=ues_ids,
        )
        restriction_oes_name_map = build_restriction_oes_name_map(restriction_rows)
        restriction_obl_name_map = build_restriction_obl_name_map(restriction_rows)

    coeff_summary = None
    coeff_base_preview = None
    coeff_calc_year_display = None
    coeff_calc_year_is_preview = False
    fuel_stage_readiness = None
    missing_specific_groups = None
    composite_energy_level_issues = None
    if selected_row:
        coeff_svc = FuelCoefficientCalculationService()
        coeff_summary = _get_coeff_summary_for_distribution_parameter(selected_row)
        coeff_base_preview = coeff_svc.compute_base_year_preview_for_distribution_parameter(
            selected_row.id
        )
        coeff_calc_year_display = coeff_summary
        if coeff_summary is None:
            prev = coeff_svc.compute_calc_year_preview_for_distribution_parameter(
                selected_row.id
            )
            if prev:
                coeff_calc_year_display = SimpleNamespace(**prev)
                coeff_calc_year_is_preview = True
        try:
            fuel_stage_readiness = FuelStageService().get_readiness(selected_row.id)
        except Exception:
            fuel_stage_readiness = None
        try:
            missing_specific_groups = (
                coeff_svc.list_groups_missing_specific_for_distribution_parameter(
                    selected_row.id
                )
            )
        except Exception:
            missing_specific_groups = None
        try:
            composite_year = (
                int(selected_row.year.number) if selected_row.year is not None else None
            )
            composite_group_ids = (
                list(fuel_stage_readiness.selected_group_ids)
                if fuel_stage_readiness is not None
                else []
            )
            if composite_year is not None and composite_group_ids:
                composite_energy_level_issues = find_composite_energy_level_issues(
                    db.session,
                    database_version_id=(
                        selected_row.database_version_id or get_current_db_version_id()
                    ),
                    year_number=composite_year,
                    selected_group_ids=composite_group_ids,
                )
        except Exception:
            composite_energy_level_issues = None

    missing_specific_edit_url = None
    missing_fuel_edit_url = None
    composite_energy_level_edit_url = None
    if missing_specific_groups:
        calc_y = missing_specific_groups.get("year_number") or start_year
        interval_start = base_year if base_year is not None else calc_y
        interval_end = calc_y if calc_y is not None else base_year
        if missing_specific_groups.get("missing_count"):
            missing_ids = [
                g["equipment_group_id"]
                for g in (missing_specific_groups.get("groups") or [])
                if g.get("equipment_group_id") is not None
            ]
            if missing_ids:
                # Как у кнопки «ТЭП»: Год начала = базовый, Год конца = расчётный.
                missing_specific_edit_url = url_for(
                    "fuel_bp.equipment_group_specific_fuel_consumption_edit_data",
                    equipment_group_ids=missing_ids,
                    start_year=interval_start,
                    end_year=interval_end,
                    union_energy_system_filter=ues_ids if ues_ids else None,
                    base_year=base_year if base_year is not None else None,
                    per_page="all",
                    show_empty_rows="1",
                )
        if missing_specific_groups.get("missing_fuel_count"):
            missing_fuel_ids = [
                g["equipment_group_id"]
                for g in (missing_specific_groups.get("missing_fuel_groups") or [])
                if g.get("equipment_group_id") is not None
            ]
            if missing_fuel_ids:
                missing_fuel_edit_url = url_for(
                    "fuel_bp.equipment_group_fuel_params_edit_data",
                    equipment_group_ids=missing_fuel_ids,
                    start_year=interval_start,
                    end_year=interval_end,
                    union_energy_system_filter=ues_ids if ues_ids else None,
                    base_year=base_year if base_year is not None else None,
                    per_page="all",
                    show_empty_rows="1",
                )

    if composite_energy_level_issues:
        composite_ids = equipment_group_ids_for_composite_energy_level_issues(
            composite_energy_level_issues
        )
        if composite_ids:
            composite_energy_level_edit_url = url_for(
                "fuel_bp.equipment_group_fuel_params_edit_data",
                equipment_group_ids=composite_ids,
                start_year=base_year if base_year is not None else start_year,
                end_year=start_year if start_year is not None else base_year,
                union_energy_system_filter=ues_ids if ues_ids else None,
                base_year=base_year if base_year is not None else None,
                per_page="all",
            )

    coeff_tech_rows = coeff_tech_type_table(coeff_calc_year_display)
    coeff_tech_aggregate_row = get_coeff_tech_aggregate_row(coeff_calc_year_display)

    coeff_ratio_row = _coeff_ratio_row(
        selected_row,
        coeff_summary,
        coeff_base_preview,
        coeff_calc_year_display,
        coeff_calc_year_is_preview,
    )
    coeff_cptp_display = _cptp_for_coeff_table(selected_row, coeff_calc_year_display)
    # PE выводится в строке «Отношение» (coeff_ratio_row); имя оставлено для совместимости со старыми шаблонами.
    coeff_base_row_pe = None

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [
        {"id": ues.id, "name": ues.name} for ues in union_energy_system_objects
    ]
    tes_type_names = [
        {"id": t.id, "name": t.name} for t in get_tes_type_list_full()
    ]

    return render_template(
        "fuel/calculation/fuel_calculation_form.html",
        selected_row=selected_row,
        matching_distribution_parameters=matching_distribution_parameters,
        distribution_parameter_field_labels=DISTRIBUTION_PARAMETER_FIELD_LABELS,
        distribution_param_headings=DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS,
        distribution_stage_last_result=_distribution_last_run_display_for_page(selected_row),
        nr_hfix_pending=_nr_hfix_pending_for_page(selected_row),
        fuel_stage_last_result=_fuel_stage_last_run_display_for_page(selected_row),
        coeff_stage_last_result=_coeff_last_run_display_for_page(selected_row),
        coeff_summary=coeff_summary,
        coeff_calc_year_display=coeff_calc_year_display,
        coeff_calc_year_is_preview=coeff_calc_year_is_preview,
        coeff_base_preview=coeff_base_preview,
        coeff_tech_rows=coeff_tech_rows,
        coeff_tech_aggregate_row=coeff_tech_aggregate_row,
        coeff_ratio_row=coeff_ratio_row,
        coeff_cptp_display=coeff_cptp_display,
        coeff_base_row_pe=coeff_base_row_pe,
        fuel_stage_readiness=fuel_stage_readiness,
        missing_specific_groups=missing_specific_groups,
        missing_specific_edit_url=missing_specific_edit_url,
        missing_fuel_edit_url=missing_fuel_edit_url,
        composite_energy_level_issues=composite_energy_level_issues,
        composite_energy_level_edit_url=composite_energy_level_edit_url,
        coeff_cell_tooltips=get_coeff_cell_tooltips(),
        filter_year_list=distribution_parameter_year_numbers_for_filter_dropdown(),
        start_year=start_year,
        base_year=base_year,
        apply_restrictions=apply_restrictions,
        restriction_rows=restriction_rows,
        restriction_headings=FUEL_RESTRICTION_LIST_COLUMN_HEADINGS,
        restriction_column_formulas=get_restriction_column_formulas(),
        restriction_oes_name_map=restriction_oes_name_map,
        restriction_obl_name_map=restriction_obl_name_map,
        rounding_digits=_parse_rounding_digits_from_request(),
        tes_type_filter=filters.get("tes_type_filter"),
        tes_type_names=tes_type_names,
        union_energy_system_list=union_energy_system_list,
        union_energy_system_filter=ues_ids,
        # Fallback, если tep-qs пуст (без годов/фильтров).
        calculation_edit_links_qs=fuel_calculation_form_query_string(request.args),
        # Сведения / ТЭП / формулы: Год начала = базовый, Год конца = расчётный.
        calculation_tep_edit_links_qs=fuel_calculation_tep_edit_query_string(
            base_year=base_year,
            calc_year=start_year,
            args=request.args,
        ),
    )


@fuel_bp.route("/distribution_parameters", methods=["GET"])
@login_required
def distribution_parameters_list():
    filters = extract_filters_from_args(request.args)
    # Расчитываемый год — несколько значений start_year=… как на station_list.
    start_year_filter: list[int] = []
    for raw in request.args.getlist("start_year"):
        if raw in (None, ""):
            continue
        try:
            start_year_filter.append(int(raw))
        except (TypeError, ValueError):
            pass
    start_year_filter = list(dict.fromkeys(start_year_filter))

    raw_by = request.args.get("base_year")
    base_year_filter: int | None = None
    if raw_by not in (None, ""):
        try:
            base_year_filter = int(raw_by)
        except (TypeError, ValueError):
            base_year_filter = None

    ues_ids = filters.get("union_energy_system_filter") or []
    prefill_union_energy_system_id = (
        int(ues_ids[0]) if len(ues_ids) == 1 else None
    )
    distribution_parameter_rows = get_distribution_parameters_list(
        year_numbers=start_year_filter if start_year_filter else None,
        base_year_number=base_year_filter,
        union_energy_system_ids=ues_ids if ues_ids else None,
    )
    rounding_digits = _parse_rounding_digits_from_request()

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [
        {"id": ues.id, "name": ues.name} for ues in union_energy_system_objects
    ]

    has_active_filters = has_any_filters(request.args) or (
        len(request.args.getlist("start_year")) > 0
        or request.args.get("base_year") not in (None, "")
    )

    return render_template(
        "fuel/distribution_parameters/distribution_parameters_list.html",
        distribution_parameter_rows=distribution_parameter_rows,
        distribution_param_headings=DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS,
        filter_year_list=distribution_parameter_year_numbers_for_filter_dropdown(),
        year_list_for_edit=get_year_list_full(),
        start_year_filter=start_year_filter,
        base_year_filter=base_year_filter,
        union_energy_system_list=union_energy_system_list,
        union_energy_system_filter=filters.get("union_energy_system_filter") or [],
        has_active_filters=has_active_filters,
        rounding_digits=rounding_digits,
        prefill_union_energy_system_id=prefill_union_energy_system_id,
    )


@fuel_bp.route("/distribution_parameters/bulk_row_data", methods=["GET"])
@login_required
def distribution_parameters_bulk_row_data():
    """JSON: поля для массового добавления строк (все ОЭС) по базовому году и году расчёта."""
    if not getattr(current_user, "has_admin", False):
        return jsonify({"ok": False, "errors": ["Недостаточно прав."]}), 403

    raw_base = request.args.get("id_base_year", "").strip()
    raw_target = request.args.get("id_year_target", "").strip()
    errors: list[str] = []
    try:
        id_base_year = int(raw_base)
    except ValueError:
        errors.append("Не задан или некорректен базовый год.")
        id_base_year = 0
    try:
        id_year_target = int(raw_target)
    except ValueError:
        errors.append("Не задан или некорректен расчитываемый год.")
        id_year_target = 0

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    rounding_digits = _parse_rounding_digits_from_request()
    rows, svc_errors, stats = build_distribution_parameters_bulk_copy_rows(
        id_base_year=id_base_year,
        id_year_target=id_year_target,
        rounding_digits=rounding_digits,
    )
    if svc_errors:
        return jsonify({"ok": False, "errors": svc_errors}), 400

    return jsonify({"ok": True, "rows": rows, "stats": stats})


@fuel_bp.route("/distribution_parameters/bulk_apply", methods=["POST"])
@login_required
def distribution_parameters_bulk_apply():
    """Сохранение строк, подготовленных «Добавить год» / «Добавить период», без отдельного «Сохранить»."""
    if not getattr(current_user, "has_admin", False):
        return jsonify({"ok": False, "errors": ["Недостаточно прав."]}), 403
    if not _csrf_ok():
        return jsonify({"ok": False, "errors": ["Ошибка проверки CSRF."]}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"ok": False, "errors": ["Ожидается JSON."]}), 400

    rows = data.get("rows")
    if not isinstance(rows, list):
        return jsonify({"ok": False, "errors": ["Поле rows должно быть массивом."]}), 400

    raw_rd = data.get("rounding_digits", 0)
    try:
        display_rd = int(raw_rd)
    except (TypeError, ValueError):
        display_rd = 0

    n, errs = apply_distribution_parameters_bulk_apply_from_payload(
        rows,
        user=current_user,
        display_rounding_digits=display_rd,
    )
    if errs:
        return jsonify({"ok": False, "errors": errs}), 400

    return jsonify({"ok": True, "saved": n})


@fuel_bp.route("/distribution_parameters/bulk_row_data_period", methods=["GET"])
@login_required
def distribution_parameters_bulk_row_data_period():
    """JSON: строки для массового добавления по диапазону расчитываемых лет (все ОЭС)."""
    if not getattr(current_user, "has_admin", False):
        return jsonify({"ok": False, "errors": ["Недостаточно прав."]}), 403

    raw_base = request.args.get("id_base_year", "").strip()
    raw_from = request.args.get("id_year_from", "").strip()
    raw_to = request.args.get("id_year_to", "").strip()
    errors: list[str] = []
    try:
        id_base_year = int(raw_base)
    except ValueError:
        errors.append("Не задан или некорректен базовый год.")
        id_base_year = 0
    try:
        id_year_from = int(raw_from)
    except ValueError:
        errors.append("Не задан или некорректен год начала периода.")
        id_year_from = 0
    try:
        id_year_to = int(raw_to)
    except ValueError:
        errors.append("Не задан или некорректен год конца периода.")
        id_year_to = 0

    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    rounding_digits = _parse_rounding_digits_from_request()
    rows, svc_errors, stats = build_distribution_parameters_bulk_copy_rows_for_period(
        id_base_year=id_base_year,
        id_year_from=id_year_from,
        id_year_to=id_year_to,
        rounding_digits=rounding_digits,
    )
    if svc_errors:
        return jsonify({"ok": False, "errors": svc_errors, "stats": stats}), 400

    return jsonify({"ok": True, "rows": rows, "stats": stats})


@fuel_bp.route("/restrictions", methods=["GET"])
@login_required
def fuel_restrictions_list():
    """Таблица «Ограничения» (Access); порядок строк — по obl (как Form_Open в Access)."""
    filters = extract_filters_from_args(request.args)
    # Год — несколько значений start_year=… как на distribution_parameters.
    start_year_filter: list[int] = []
    for raw in request.args.getlist("start_year"):
        if raw in (None, ""):
            continue
        try:
            start_year_filter.append(int(raw))
        except (TypeError, ValueError):
            continue
    start_year_filter = list(dict.fromkeys(start_year_filter))

    # Фильтры — id справочников UnionEnergySystem / RegionalEnergySystem.
    ues_filter = filters.get("union_energy_system_filter") or []
    res_filter = filters.get("regional_energy_system_filter") or []
    restriction_rows = get_fuel_restrictions_list(
        year_numbers=start_year_filter if start_year_filter else None,
        union_energy_system_ids=ues_filter if ues_filter else None,
        regional_energy_system_ids=res_filter if res_filter else None,
    )
    rounding_digits = _parse_rounding_digits_from_request()
    can_edit = bool(getattr(current_user, "has_admin", False))
    # Страница всегда в режиме редактирования для пользователей с правами.
    edit_mode = can_edit

    oes_choices = get_restriction_oes_choices()
    obl_choices = get_restriction_obl_choices()
    oes_name_map = build_restriction_oes_name_map(restriction_rows)
    obl_name_map = build_restriction_obl_name_map(restriction_rows)

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [
        {"id": ues.id, "name": ues.name} for ues in union_energy_system_objects
    ]
    regional_energy_system_objects = get_regional_energy_system_list_full()
    regional_energy_system_list = [
        {"id": res.id, "name": res.name} for res in regional_energy_system_objects
    ]

    has_active_filters = bool(
        ues_filter or res_filter or start_year_filter
    )

    # Query без edit — для возврата после save/import.
    qs_parts: list[str] = []
    for key, values in request.args.lists():
        if key == "edit":
            continue
        for v in values:
            qs_parts.append(f"{key}={v}")
    qs_no_edit = "&".join(qs_parts)

    return render_template(
        "fuel/restrictions/fuel_restrictions_list.html",
        restriction_rows=restriction_rows,
        restriction_headings=FUEL_RESTRICTION_LIST_COLUMN_HEADINGS,
        restriction_column_formulas=get_restriction_column_formulas(),
        filter_year_list=distribution_parameter_year_numbers_for_filter_dropdown(),
        start_year_filter=start_year_filter,
        start_year=start_year_filter[0] if len(start_year_filter) == 1 else None,
        oes_choices=oes_choices,
        obl_choices=obl_choices,
        oes_name_map=oes_name_map,
        obl_name_map=obl_name_map,
        union_energy_system_list=union_energy_system_list,
        regional_energy_system_list=regional_energy_system_list,
        union_energy_system_filter=ues_filter,
        regional_energy_system_filter=res_filter,
        has_active_filters=has_active_filters,
        rounding_digits=rounding_digits,
        edit_mode=edit_mode,
        can_edit=can_edit,
        qs_no_edit=qs_no_edit,
    )


def _redirect_fuel_restrictions_list_after_save():
    qs = (request.form.get("restrictions_save_return_qs") or "").strip()
    base = url_for("fuel_bp.fuel_restrictions_list")
    if qs:
        # После сохранения остаёмся в режиме правки.
        if "edit=" not in qs:
            qs = f"{qs}&edit=1" if qs else "edit=1"
        elif "edit=0" in qs or "edit=false" in qs:
            qs = qs.replace("edit=0", "edit=1").replace("edit=false", "edit=1")
        return redirect(f"{base}?{qs}")
    return redirect(f"{base}?edit=1")


@fuel_bp.route("/restrictions/save", methods=["POST"])
@login_required
def fuel_restrictions_save():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для редактирования ограничений.", "danger")
        return _redirect_fuel_restrictions_list_after_save()
    n, errs = apply_fuel_restrictions_save_from_form(request.form, user=current_user)
    if errs:
        for e in errs[:12]:
            flash(e, "danger")
        if len(errs) > 12:
            flash(f"…и ещё ошибок: {len(errs) - 12}", "danger")
        return _redirect_fuel_restrictions_list_after_save()
    flash(
        f"Ограничения сохранены во все версии БД "
        f"(изменено/добавлено/удалено логических строк: {n}).",
        "success",
    )
    return _redirect_fuel_restrictions_list_after_save()


def _redirect_fuel_restrictions_list_after_import():
    qs = (request.form.get("restrictions_import_return_qs") or "").strip()
    base = url_for("fuel_bp.fuel_restrictions_list")
    if qs:
        return redirect(f"{base}?{qs}")
    return redirect(base)


@fuel_bp.route("/restrictions/export", methods=["GET"])
@login_required
def fuel_restrictions_export():
    """Экспорт текущей выборки «Ограничения» в Excel (шапка Access)."""
    filters = extract_filters_from_args(request.args)
    start_year_filter: list[int] = []
    for raw in request.args.getlist("start_year"):
        if raw in (None, ""):
            continue
        try:
            start_year_filter.append(int(raw))
        except (TypeError, ValueError):
            continue
    start_year_filter = list(dict.fromkeys(start_year_filter))
    ues_ids = filters.get("union_energy_system_filter") or []
    res_ids = filters.get("regional_energy_system_filter") or []
    rows = get_fuel_restrictions_list(
        year_numbers=start_year_filter if start_year_filter else None,
        union_energy_system_ids=ues_ids if ues_ids else None,
        regional_energy_system_ids=res_ids if res_ids else None,
    )
    try:
        excel_file = export_fuel_restrictions_to_excel(rows)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Ограничения_{timestamp}.xlsx"
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception:
        current_app.logger.exception("fuel_restrictions export")
        flash("Ошибка экспорта в Excel.", "danger")
        return redirect(url_for("fuel_bp.fuel_restrictions_list"))


@fuel_bp.route("/restrictions/import", methods=["POST"])
@login_required
def fuel_restrictions_import():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для импорта ограничений.", "danger")
        return _redirect_fuel_restrictions_list_after_import()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_fuel_restrictions_list_after_import()

    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        flash("Файл не выбран.", "danger")
        return _redirect_fuel_restrictions_list_after_import()

    if not f.filename.lower().endswith((".xlsx", ".xlsm")):
        flash("Нужен файл Excel в формате .xlsx (таблица «Ограничения» из Access).", "danger")
        return _redirect_fuel_restrictions_list_after_import()

    try:
        added, updated, row_errors = import_fuel_restrictions_from_upload(f)
        if row_errors:
            preview = row_errors[:20]
            flash(
                "Импорт не выполнен. Ошибки: "
                + " ".join(preview)
                + (f" … (всего ошибок: {len(row_errors)})" if len(row_errors) > 20 else ""),
                "danger",
            )
        elif added == 0 and updated == 0:
            flash("Нет данных для импорта (пустые строки после шапки).", "warning")
        else:
            flash(
                f"Импорт ограничений во все версии БД: "
                f"добавлено копий {added}, обновлено {updated}.",
                "success",
            )
    except ValueError as e:
        flash(str(e), "danger")
    except Exception:
        current_app.logger.exception("fuel_restrictions import")
        flash("Ошибка импорта файла.", "danger")

    return _redirect_fuel_restrictions_list_after_import()


def _redirect_distribution_parameters_list():
    qs = request.query_string.decode("utf-8") if request.query_string else ""
    base = url_for("fuel_bp.distribution_parameters_list")
    return redirect(f"{base}?{qs}" if qs else base)


def _redirect_distribution_parameters_list_after_save():
    """После POST /save в URL нет query — восстанавливаем из скрытого поля формы."""
    qs = (request.form.get("distribution_save_return_qs") or "").strip()
    base = url_for("fuel_bp.distribution_parameters_list")
    return redirect(f"{base}?{qs}" if qs else base)


def _redirect_distribution_parameters_list_after_row_delete():
    """После POST удаления строки — query из поля return_qs."""
    qs = (request.form.get("return_qs") or "").strip()
    base = url_for("fuel_bp.distribution_parameters_list")
    return redirect(f"{base}?{qs}" if qs else base)


@fuel_bp.route("/distribution_parameters/row/<int:row_id>/delete", methods=["POST"])
@login_required
def distribution_parameter_row_delete(row_id: int):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.fuel.services.distribution_parameters.distribution_parameters_save_services import (
        _write_distribution_parameter_delete_logs,
    )

    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для удаления.", "danger")
        return _redirect_distribution_parameters_list_after_row_delete()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_distribution_parameters_list_after_row_delete()

    qs = (request.form.get("return_qs") or "").strip()
    base = url_for("fuel_bp.distribution_parameters_list")
    redirect_target = f"{base}?{qs}" if qs else base

    dp = db.session.get(DistributionParameter, row_id)
    if dp is None:
        flash("Запись не найдена или уже удалена.", "warning")
        return redirect(redirect_target)

    try:
        from app.fuel.services.distribution_parameters.distribution_parameters_all_versions_services import (
            delete_distribution_parameter_in_all_versions,
        )

        deleted_ids = delete_distribution_parameter_in_all_versions(row_id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            "Не удалось удалить запись: есть связанные данные (коэффициенты, расчёты). Сначала удалите зависимости.",
            "danger",
        )
        return redirect(redirect_target)
    except Exception as exc:
        db.session.rollback()
        flash(f"Ошибка удаления: {exc}", "danger")
        return redirect(redirect_target)

    flash(
        f"Параметр распределения удалён во всех версиях БД (записей: {len(deleted_ids)}).",
        "success",
    )
    _write_distribution_parameter_delete_logs(current_user, deleted_ids)
    return redirect(redirect_target)


@fuel_bp.route("/distribution_parameters/save", methods=["POST"])
@login_required
def distribution_parameters_save():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для сохранения.", "danger")
        return _redirect_distribution_parameters_list_after_save()
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_distribution_parameters_list_after_save()

    n, errs = apply_distribution_parameters_save_from_form(request.form, user=current_user)
    if errs:
        for msg in errs[:25]:
            flash(msg, "danger")
        if len(errs) > 25:
            flash(f"… и ещё ошибок: {len(errs) - 25}.", "danger")
    elif n == 0:
        flash("Изменений для сохранения не было (все значения совпадают с данными в БД).", "info")
    else:
        flash(f"Сохранено записей во всех версиях БД: {n}.", "success")

    return _redirect_distribution_parameters_list_after_save()


@fuel_bp.route("/distribution_parameters/export", methods=["GET"])
@login_required
def distribution_parameters_export():
    """Экспорт списка параметров распределения (с учётом фильтров в query)."""
    start_year_filter: list[int] = []
    for raw in request.args.getlist("start_year"):
        if raw in (None, ""):
            continue
        try:
            start_year_filter.append(int(raw))
        except (TypeError, ValueError):
            pass
    start_year_filter = list(dict.fromkeys(start_year_filter))

    raw_by = request.args.get("base_year")
    base_year_filter: int | None = None
    if raw_by not in (None, ""):
        try:
            base_year_filter = int(raw_by)
        except (TypeError, ValueError):
            base_year_filter = None

    filters = extract_filters_from_args(request.args)
    ues_ids = filters.get("union_energy_system_filter") or []

    rows = get_distribution_parameters_list(
        year_numbers=start_year_filter if start_year_filter else None,
        base_year_number=base_year_filter,
        union_energy_system_ids=ues_ids if ues_ids else None,
    )

    try:
        excel_file = export_distribution_parameters_to_excel(rows)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Параметры_распределения_{timestamp}.xlsx"
        excel_file.seek(0)
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except Exception:
        current_app.logger.exception("distribution_parameters export")
        flash("Ошибка экспорта в Excel.", "danger")
        return redirect(url_for("fuel_bp.distribution_parameters_list"))


@fuel_bp.route("/distribution_parameters/import", methods=["POST"])
@login_required
def distribution_parameters_import():
    if not _csrf_ok():
        flash("Ошибка проверки CSRF.", "danger")
        return _redirect_distribution_parameters_list()

    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        flash("Файл не выбран.", "danger")
        return _redirect_distribution_parameters_list()

    if not f.filename.lower().endswith((".xlsx", ".xlsm")):
        flash("Нужен файл Excel в формате .xlsx.", "danger")
        return _redirect_distribution_parameters_list()

    try:
        n_added, n_updated, row_errors = import_distribution_parameters_from_upload(f)
        # Ошибки валидации файла — полный откат; предупреждения по версиям — после успеха
        hard_errors = [e for e in row_errors if not str(e).startswith("Версия БД")]
        soft_warns = [e for e in row_errors if str(e).startswith("Версия БД")]
        if hard_errors:
            preview = hard_errors[:20]
            flash(
                "Импорт не выполнен. Ошибки: "
                + " ".join(preview)
                + (f" … (всего ошибок: {len(hard_errors)})" if len(hard_errors) > 20 else ""),
                "danger",
            )
        elif n_added == 0 and n_updated == 0:
            flash("Нет данных для импорта (пустые строки после шапки).", "warning")
        else:
            flash(
                f"Импорт во все версии БД: добавлено копий {n_added}, обновлено {n_updated}.",
                "success",
            )
            if soft_warns:
                flash(
                    "Часть версий пропущена: "
                    + " ".join(soft_warns[:10])
                    + (f" … (+{len(soft_warns) - 10})" if len(soft_warns) > 10 else ""),
                    "warning",
                )
    except ValueError as e:
        flash(str(e), "danger")
    except Exception:
        current_app.logger.exception("distribution_parameters import")
        flash("Ошибка импорта файла.", "danger")

    return _redirect_distribution_parameters_list()
