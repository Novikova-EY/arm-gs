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
from app.fuel.models.fue_restriction_model import FUEL_RESTRICTION_LIST_COLUMN_HEADINGS
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
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
from app.fuel.services.distribution_parameters_list_services import (
    distribution_parameter_year_numbers_for_filter_dropdown,
    get_distribution_parameters_list,
)
from app.fuel.services.fuel_restrictions_list_services import get_fuel_restrictions_list
from app.fuel.services.distribution_parameters_bulk_copy_services import (
    build_distribution_parameters_bulk_copy_rows,
    build_distribution_parameters_bulk_copy_rows_for_period,
)
from app.fuel.services.distribution_parameters_save_services import (
    apply_distribution_parameters_bulk_apply_from_payload,
    apply_distribution_parameters_save_from_form,
)
from app.fuel.services.export_distribution_parameters_services import (
    export_distribution_parameters_to_excel,
)
from app.fuel.services.import_distribution_parameters_services import (
    import_distribution_parameters_from_upload,
)
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
)
from app.fuel.services.calculation.fuel.fuel_stage_services import FuelStageService
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
    has_any_filters,
)
from app.common.services.help_services import format_decimal_trim_for_display
from app.fuel.routes.fuel_calculation_common import FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY
from . import fuel_bp

# Подсказки у значений в таблицах «Коэфф» на /fuel/calculation (см. FuelCoefficientCalculationService).
# Префиксы b_/c_ — строка базового / расчётного года; tech_* — вторая таблица по типу строки.
FUEL_CALC_COEFF_CELL_TOOLTIPS = {
    "b_nust": (
        "Сумма установленной мощности N_уст (поле nust топливных параметров) по группам фильтра параметра "
        "распределения, для которых есть строка за базовый год."
    ),
    "c_nust": (
        "Сумма nust за расчётный год по группам, у которых есть строка топливных параметров за расчётный год."
    ),
    "b_e": (
        "Сумма E (выработка электроэнергии, поле e топливных параметров групп) за базовый год — столбец «E»."
    ),
    "c_e": (
        "В строке расчётного года столбец «E» (e) не заполняется; Ераспред см. в поле Е<sub>тек</sub> над таблицей."
    ),
    "b_etp": (
        "Сумма Этц (поле ewtp) за базовый год — столбец «Eтп»."
    ),
    "c_etp": (
        "Сумма Этц за расчётный год (cetp в Access после Кнопка5): Σ ewtp по строкам топлива после пересчёта ewtp = qotr·y/1000."
    ),
    "b_q": (
        "Сумма отпуска тепла Q (поле q топливых параметров) по группам фильтра за базовый год."
    ),
    "c_q": (
        "Сумма Q за расчётный год по группам со строкой топлива за расчётный год."
    ),
    "b_qotr": (
        "Сумма Q_отр (поле qotr) по группам фильтра за базовый год."
    ),
    "c_qotr": (
        "Сумма Q_отр за расчётный год по группам со строкой за расчётный год."
    ),
    "b_ptp": (
        "Доля тепла в электроэнергии, %: (сумма Этц)/(сумма E)·100 за базовый год."
    ),
    "c_ptp": (
        "Как в Access (Кнопка5_Click): cptp = csumetp / E · 100, где E — Ераспред (поле e параметра), "
        "csumetp — сумма пересчитанных Этц (ewtp) за расчётный год. Если E в параметре не задан, при расчёте "
        "в знаменателе используется ΣE по строкам топлива расчётного года."
    ),
    "b_h": (
        "Удельные часы Н (ч) за базовый год: ΣE / ΣN_уст·1000 (как в Access; то же значение, что bh в расчёте)."
    ),
    "c_h": (
        "Удельные часы Н (ч) за расчётный год: E_целевое / ΣN_уст·1000 по строкам топлива расчётного года (ch)."
    ),
    "tech_n": (
        "Сумма N_уст расчётного года по «новым» группам данного типа: в базовом году N_уст было 0; "
        "отнесение к ПСУ/ГТУ/ПГУ — по коду obor (ПСУ = всё новое минус ГТУ и ПГУ)."
    ),
    "tech_h_col_empty": (
        "В строках ПСУ/ГТУ/ПГУ коэффициенты hn (hnps, hngt, hnpg) вводятся в столбце «ЧЧИУМ»; "
        "столбец K_нов пересчитывается (kn = hn/ch) после сохранения."
    ),
    "tech_h_psu": ("Коэффициент hnps вводится в столбце «ЧЧИУМ»; здесь значение не дублируется."),
    "tech_h_gtu": ("Коэффициент hngt вводится в столбце «ЧЧИУМ»; здесь значение не дублируется."),
    "tech_h_pgu": ("Коэффициент hnpg вводится в столбце «ЧЧИУМ»; здесь значение не дублируется."),
    "tech_k_psu": ("K_нов для ПСУ: в Access knps = hnps / ch; при расчёте «Коэфф» подставляется то же правило."),
    "tech_k_gtu": ("K_нов для ГТУ: в Access kngt = hngt / ch."),
    "tech_k_pgu": ("K_нов для ПГУ: в Access knpg = hnpg / ch."),
    "tech_agg_n": (
        "Сумма мощностей новых агрегатов (cnustn): Σ N_уст по группам, где в базовом году N_уст было 0."
    ),
    "tech_agg_hd": (
        "Удельные часы на «старую» часть парка (hd): из Кнопка5_Click Access — после подстановки kn по строкам ПСУ/ГТУ/ПГУ."
    ),
    "tech_hd_col_ph": (
        "PH = hd / bh: отношение удельных часов на действующую часть парка (hd в строке выше) к базовым удельным часам bh "
        "(как в сводке этапа «Коэфф»). Выводится в строке ПСУ под тем же столбцом, что и hd."
    ),
    "tech_agg_kn": (
        "Средневзвешенный K_нов по новым мощностям (kn): (N_пс·knps + N_гт·kngt + N_пг·knpg) / cnustn."
    ),
    "tech_ch_psu": (
        "Ввод hnps (коэффициент H для ПСУ). После сохранения в параметр распределения выполняется пересчёт "
        "этапа «Коэфф»: knps = hnps/ch и обновление связанных полей."
    ),
    "tech_ch_gtu": (
        "Ввод hngt для ГТУ. После сохранения пересчитываются kngt = hngt/ch и этап «Коэфф»."
    ),
    "tech_ch_pgu": (
        "Ввод hnpg для ПГУ. После сохранения пересчитываются knpg = hnpg/ch и этап «Коэфф»."
    ),
    "r_nust": (
        "Для отношений текущего года к базовому по этому показателю отдельный коэффициент не выводится."
    ),
    "r_pe": (
        "PE = E_целевое / ΣE за базовый год (отношение суммарной выработки при заданном Ераспред к базе)."
    ),
    "r_etp": (
        "PETP = ΣЭтц расчётного года / ΣЭтц базового года (суммы поля ewtp по фильтру). "
        "Не путать с PQ — это отношение по столбцу Q (см. следующий столбец)."
    ),
    "r_pq": "PQ = ΣQ расчётного года / ΣQ базового года.",
    "r_potr": "Pотр = ΣQотр расчётного года / ΣQотр базового года.",
    "r_ptp": (
        "Для доли %тп отдельное отношение к базе в этой строке не показывается (см. столбцы E, Q, Qотр, Н)."
    ),
    "r_ph1": (
        "PH1 = ch / bh: отношение удельных часов (E/ΣNуст·1000) расчётного года к базовому."
    ),
    "extra_ph1": (
        "PH1 = ch / bh — отношение удельных часов расчётного года к базовому (как в сводке этапа «Коэфф»)."
    ),
    "extra_kplus": (
        "Коэффициент k+ из параметра распределения: копируется в сводку при выполнении «Коэфф»."
    ),
    "extra_kmin": (
        "Коэффициент k− из параметра распределения: копируется в сводку при выполнении «Коэфф»."
    ),
    "extra_lim": (
        "Параметр lim из параметра распределения: копируется в сводку при выполнении «Коэфф»."
    ),
    "extra_sum_e": (
        "ΣE — сумма выработки электроэнергии (поле e) по строкам топлива расчётного года под фильтром; "
        "используется как запасной знаменатель для доли %тп, если Ераспред в параметре не задан."
    ),
}


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


def _coeff_stage_extra_row(
    selected_row,
    coeff_summary,
    coeff_base_preview,
    coeff_calc_year_display,
):
    """
    Показатели, которые попадают в сводку этапа «Коэфф», но не вынесены в основные таблицы и поля K/doptim.

    PH1 (ph1); ΣE по расчётному году; k+, k−, lim (в фильтрах не дублируются).
    """
    if selected_row is None or coeff_calc_year_display is None:
        return None

    ph1 = None
    if coeff_summary is not None:
        ph1 = _d_decimal(coeff_summary.ph1)
        if ph1 is None:
            ch = _d_decimal(coeff_summary.ch)
            bh = _d_decimal(coeff_summary.bh)
            if ch is not None and bh is not None and bh > 0:
                ph1 = ch / bh
    else:
        ch = _d_decimal(getattr(coeff_calc_year_display, "ch", None))
        bh = _d_decimal(coeff_base_preview.get("bh")) if coeff_base_preview else None
        if ch is not None and bh is not None and bh > 0:
            ph1 = ch / bh

    if coeff_summary is not None:
        kplus = _d_decimal(coeff_summary.kplus)
        kmin = _d_decimal(coeff_summary.kmin)
        lim = _d_decimal(coeff_summary.lim)
    else:
        kplus = _d_decimal(getattr(selected_row, "kplus", None))
        kmin = _d_decimal(getattr(selected_row, "kmin", None))
        lim = _d_decimal(getattr(selected_row, "lim", None))

    sum_e_cyear = _d_decimal(getattr(coeff_calc_year_display, "sum_e_cyear", None))
    if sum_e_cyear is None and coeff_summary is not None and selected_row is not None:
        prev_full = FuelCoefficientCalculationService().compute_calc_year_preview_for_distribution_parameter(
            selected_row.id,
        )
        if prev_full:
            sum_e_cyear = _d_decimal(prev_full.get("sum_e_cyear"))

    return {
        "ph1": ph1,
        "sum_e_cyear": sum_e_cyear,
        "kplus": kplus,
        "kmin": kmin,
        "lim": lim,
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
        "final_k": fmt_num(raw.get("final_k"), 0),
        "final_kn": fmt_num(raw.get("final_kn"), 0),
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

    ues_ids = filters.get("union_energy_system_filter") or []

    if start_year is None:
        selected_row = None
    else:
        distribution_parameters = get_distribution_parameters_list(
            year_numbers=[start_year],
            union_energy_system_ids=ues_ids if ues_ids else None,
        )
        selected_row = distribution_parameters[0] if distribution_parameters else None

    coeff_summary = None
    coeff_base_preview = None
    coeff_calc_year_display = None
    coeff_calc_year_is_preview = False
    fuel_stage_readiness = None
    if selected_row:
        coeff_summary = _get_coeff_summary_for_distribution_parameter(selected_row)
        coeff_base_preview = FuelCoefficientCalculationService().compute_base_year_preview_for_distribution_parameter(
            selected_row.id
        )
        coeff_calc_year_display = coeff_summary
        if coeff_summary is None:
            prev = FuelCoefficientCalculationService().compute_calc_year_preview_for_distribution_parameter(
                selected_row.id
            )
            if prev:
                coeff_calc_year_display = SimpleNamespace(**prev)
                coeff_calc_year_is_preview = True
        try:
            fuel_stage_readiness = FuelStageService().get_readiness(selected_row.id)
        except Exception:
            fuel_stage_readiness = None

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

    coeff_stage_extra_row = _coeff_stage_extra_row(
        selected_row,
        coeff_summary,
        coeff_base_preview,
        coeff_calc_year_display,
    )

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [
        {"id": ues.id, "name": ues.name} for ues in union_energy_system_objects
    ]

    calc_equipment_group_ids: list[int] = []
    if selected_row is not None:
        try:
            calc_equipment_group_ids = DistributionStageService().list_equipment_group_ids_for_distribution_parameter(
                selected_row.id
            )
        except Exception:
            calc_equipment_group_ids = []

    return render_template(
        "fuel/calculation/fuel_calculation_form.html",
        selected_row=selected_row,
        distribution_parameter_field_labels=DISTRIBUTION_PARAMETER_FIELD_LABELS,
        distribution_stage_last_result=_distribution_last_run_display_for_page(selected_row),
        coeff_summary=coeff_summary,
        coeff_calc_year_display=coeff_calc_year_display,
        coeff_calc_year_is_preview=coeff_calc_year_is_preview,
        coeff_base_preview=coeff_base_preview,
        coeff_tech_rows=coeff_tech_rows,
        coeff_tech_aggregate_row=coeff_tech_aggregate_row,
        coeff_ratio_row=coeff_ratio_row,
        coeff_cptp_display=coeff_cptp_display,
        coeff_base_row_pe=coeff_base_row_pe,
        coeff_stage_extra_row=coeff_stage_extra_row,
        fuel_stage_readiness=fuel_stage_readiness,
        coeff_cell_tooltips=FUEL_CALC_COEFF_CELL_TOOLTIPS,
        filter_year_list=distribution_parameter_year_numbers_for_filter_dropdown(),
        start_year=filters["start_year"],
        tes_type_filter=filters.get("tes_type_filter"),
        tes_type_names=get_tes_type_list_full(),
        union_energy_system_list=union_energy_system_list,
        union_energy_system_filter=filters.get("union_energy_system_filter") or [],
        calc_equipment_group_ids=calc_equipment_group_ids,
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
    raw_sy = request.args.get("start_year")
    start_year: int | None = None
    if raw_sy not in (None, ""):
        try:
            start_year = int(raw_sy)
        except (TypeError, ValueError):
            start_year = None

    ues_ids = filters.get("union_energy_system_filter") or []
    restriction_rows = get_fuel_restrictions_list(
        year_number=start_year,
        union_energy_system_ids=ues_ids if ues_ids else None,
    )
    rounding_digits = _parse_rounding_digits_from_request()

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [
        {"id": ues.id, "name": ues.name} for ues in union_energy_system_objects
    ]

    has_active_filters = has_any_filters(request.args) or (
        request.args.get("start_year") not in (None, "")
    )

    return render_template(
        "fuel/restrictions/fuel_restrictions_list.html",
        restriction_rows=restriction_rows,
        restriction_headings=FUEL_RESTRICTION_LIST_COLUMN_HEADINGS,
        filter_year_list=distribution_parameter_year_numbers_for_filter_dropdown(),
        start_year=start_year,
        union_energy_system_list=union_energy_system_list,
        union_energy_system_filter=filters.get("union_energy_system_filter") or [],
        has_active_filters=has_active_filters,
        rounding_digits=rounding_digits,
    )


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
    from app.fuel.services.distribution_parameters_save_services import (
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
        db.session.delete(dp)
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

    flash("Параметр распределения удалён.", "success")
    _write_distribution_parameter_delete_logs(current_user, [row_id])
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
        flash(f"Сохранено записей: {n}.", "success")

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
        n, row_errors = import_distribution_parameters_from_upload(f)
        if row_errors:
            preview = row_errors[:20]
            flash(
                "Импорт не выполнен. Ошибки: "
                + " ".join(preview)
                + (f" … (всего ошибок: {len(row_errors)})" if len(row_errors) > 20 else ""),
                "danger",
            )
        elif n == 0:
            flash("Нет данных для импорта (пустые строки после шапки).", "warning")
        else:
            flash(f"Импортировано строк: {n}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception:
        current_app.logger.exception("distribution_parameters import")
        flash("Ошибка импорта файла.", "danger")

    return _redirect_distribution_parameters_list()
