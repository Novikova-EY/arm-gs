# -*- coding: utf-8 -*-
"""
Данные для страницы «Редактировать данные» из модуля расчёта (/fuel/calculation/equipment_group_fuel_params_edit_data).

Те же источники, что и для stations_equipment_group_fuel_params: иерархия групп и основные топливные параметры
за интервал лет (start_year–end_year), по строке на год для каждой группы.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, or_

from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_db_version,
    filter_by_explicit_db_version,
    set_db_version_on_create,
)
from app.extensions import db
from app.common.services.help_services import (
    format_decimal_for_display,
    format_decimal_trim_for_display,
)
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_natural_fuel_model import EquipmentGroupNaturalFuel
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    TOPLS,
    UGLI,
    UGLI1,
    collect_fuel_names_from_formtxt,
)
from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_calc_services import (
    calc_bk_calc,
    calc_btp_calc,
    calc_sntp_calc,
    calc_y_calc,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS,
    FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS,
    build_equipment_group_fuel_params_hierarchy,
    build_name_maps_from_rows,
    get_equipment_group_ids_for_fuel_params_filters,
    get_equipment_groups_with_fuel_params_data,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    sanitize_equipment_group_fuel_param_foreign_keys,
)
from app.refdata.models.fuels.fuel_model import Fuel

# Столбцы таблицы «Редактирование данных» (метрики + виды топлива).
# Виды топлива упорядочиваются/группируются по Fuel.parent_id в build_fuel_param_columns_hierarchy.
FUEL_EDIT_DATA_PARAM_COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("numb1120", "Код группы оборудования", False),
    ("nust", EquipmentGroupFuelParam.NUST_COLUMN_LABEL, True),
    ("nr", EquipmentGroupFuelParam.NR_COLUMN_LABEL, True),
    ("h", EquipmentGroupFuelParam.H_COLUMN_LABEL, True),
    ("hfix", EquipmentGroupFuelParam.HFIX_COLUMN_LABEL, False),
    ("e", "Выработка ЭЭ, тыс.кВтч", True),
    ("ewtp", "Теплофикационная выработка ЭЭ, тыс.кВтч", True),
    ("eotp", EquipmentGroupFuelParam.EOTP_COLUMN_LABEL, True),
    ("eust", EquipmentGroupFuelParam.EUST_COLUMN_LABEL, True),
    ("eurt", EquipmentGroupFuelParam.EURT_COLUMN_LABEL, True),
    ("snk", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL, True),
    ("nt", EquipmentGroupFuelParam.NT_COLUMN_LABEL, True),
    ("nt_sum", EquipmentGroupFuelParam.NT_SUM_COLUMN_LABEL, True),
    ("q", EquipmentGroupFuelParam.Q_COLUMN_LABEL, True),
    ("qotr", "Тепловое потребление (отборов турбин), тыс.Гкал", True),
    ("turt", EquipmentGroupFuelParam.TURT_COLUMN_LABEL, True),
    ("tust", EquipmentGroupFuelParam.TUST_COLUMN_LABEL, True),
    ("sn_t", "СН, кВтч/⁠Гкал", True),
    ("b", "Всего", True),
    ("gaz", "Газ", True),
    ("isk_gaz", "Иск. газ", True),
    ("mazut", "Мазут", True),
    ("torf", "Торф", True),
    ("slan", "Сланцы", True),
    ("proch", "Прочее", True),
    ("ugol", "Уголь", True),
    ("don", "Дон", True),
    ("podm", "Подм", True),
    ("pech", "Печ", True),
    ("arkt", "Арктикуголь", True),
    ("kuzn", "Кузбасс", True),
    ("ural", "Урал", True),
    ("bashk", "Башкортостан", True),
    ("kazah", "Казахстан", True),
    ("kan", "Канск", True),
    ("tung", "Тунгусск", True),
    ("irkut", "Иркутск", True),
    ("hak", "Хакасия", True),
    ("tuv", "Тува", True),
    ("bur", "Бурятия", True),
    ("chit", "Чита", True),
    ("yakut", "Якутия", True),
    ("amur", "Амур", True),
    ("urg", "Юрга", True),
    ("ushum", "Ушумун", True),
    ("prim", "Приморье", True),
    ("mag", "Магадан", True),
    ("chukot", "Чукотка", True),
    ("kamch", "Камчатка", True),
    ("sah", "Сахалин", True),
)


FUEL_PARAM_RATIO_WARN_THRESHOLD = Decimal("8000")
FUEL_PARAM_RATIO_SCALE = Decimal("1000")
FUEL_PARAM_HOURS_WARN_TITLE = (
    "Число часов использования установленной тепловой мощности больше 8000 часов! "
    "Проверьте значение!"
)


def _nust_effective_for_compare(value) -> Decimal | None:
    """Как отображение «Руст» в таблице: пусто = None или 0 (см. render_numeric_or_dash)."""
    if value is None:
        return None
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    if d == 0:
        return None
    return d


def _nust_changed_vs_previous(prev_nust, curr_nust) -> bool:
    return _nust_effective_for_compare(prev_nust) != _nust_effective_for_compare(curr_nust)


def _to_decimal_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _numeric_values_equal_for_compare(prev_value, curr_value) -> bool:
    """Равенство как в ячейках: пусто и 0 считаются одинаковыми."""
    return _nust_effective_for_compare(prev_value) == _nust_effective_for_compare(curr_value)


def _ratio_ge_threshold(
    numerator,
    denominator,
    *,
    threshold: Decimal = FUEL_PARAM_RATIO_WARN_THRESHOLD,
    scale: Decimal = FUEL_PARAM_RATIO_SCALE,
) -> bool:
    """True, если (numerator / denominator) * scale >= threshold."""
    numer = _to_decimal_or_none(numerator)
    denom = _to_decimal_or_none(denominator)
    if numer is None or denom is None or denom == 0:
        return False
    return (numer / denom) * scale >= threshold


def _index_fuel_params_by_eg_year(rows: list) -> dict[int, dict[int, Any]]:
    by_eg_year: dict[int, dict[int, Any]] = defaultdict(dict)
    for eg, param in rows:
        if not eg or getattr(eg, "id", None) is None or param is None:
            continue
        yn = getattr(param, "year_number", None)
        if yn is None:
            continue
        by_eg_year[int(eg.id)][int(yn)] = param
    return by_eg_year


def _load_missing_prev_year_fuel_params_into_index(
    by_eg_year: dict[int, dict[int, Any]],
    display_pairs: list[tuple[int, int]],
) -> None:
    """Догружает параметры за (год−1), если их нет в текущей выборке строк страницы."""
    missing_by_version: dict[Any, set[tuple[int, int]]] = defaultdict(set)
    for eid, year in display_pairs:
        prev_y = year - 1
        if prev_y in by_eg_year.get(eid, {}):
            continue
        curr = by_eg_year.get(eid, {}).get(year)
        version_id = getattr(curr, "database_version_id", None) if curr is not None else None
        missing_by_version[version_id].add((eid, prev_y))

    for version_id, pairs in missing_by_version.items():
        if not pairs:
            continue
        eg_ids = sorted({eid for eid, _y in pairs})
        years = {y for _eid, y in pairs}
        loaded = _bulk_fuel_params_by_group_and_years(eg_ids, years, version_id)
        for (eid, y), param in loaded.items():
            by_eg_year[eid][y] = param


def build_fuel_param_row_warn_sets(rows: list) -> dict[str, frozenset[str]]:
    """
    Наборы ключей «{equipment_group_id}:{year_number}» для подсветки ячеек:

    - qotr_nt_ratio_warn_rows: (qotr/nt)*1000 >= 8000 (ячейка qotr)
    - q_nt_sum_ratio_warn_rows: (q/nt_sum)*1000 >= 8000 (ячейка q)
    - qotr_composition_warn_rows: nust изменился к предыдущему году, а qotr тот же (ячейка qotr)
    - nust_changed_from_prev_year_rows: nust изменился к предыдущему году (жёлтая строка)
    """
    empty = {
        "nust_changed_from_prev_year_rows": frozenset(),
        "qotr_nt_ratio_warn_rows": frozenset(),
        "q_nt_sum_ratio_warn_rows": frozenset(),
        "qotr_composition_warn_rows": frozenset(),
        "fuel_param_prev_compare": {},
    }
    if not rows:
        return empty

    by_eg_year = _index_fuel_params_by_eg_year(rows)
    display_pairs: list[tuple[int, int]] = []
    for eg, param in rows:
        if not eg or getattr(eg, "id", None) is None or param is None:
            continue
        y = getattr(param, "year_number", None)
        if y is None:
            continue
        display_pairs.append((int(eg.id), int(y)))

    _load_missing_prev_year_fuel_params_into_index(by_eg_year, display_pairs)

    nust_changed: set[str] = set()
    qotr_nt_warn: set[str] = set()
    q_nt_sum_warn: set[str] = set()
    composition_warn: set[str] = set()
    prev_compare: dict[str, dict[str, float | None]] = {}

    def _json_num(value) -> float | None:
        d = _to_decimal_or_none(value)
        if d is None:
            return None
        return float(d)

    for eid, year in display_pairs:
        param = by_eg_year.get(eid, {}).get(year)
        if param is None:
            continue
        key = f"{eid}:{year}"

        if _ratio_ge_threshold(getattr(param, "qotr", None), getattr(param, "nt", None)):
            qotr_nt_warn.add(key)
        if _ratio_ge_threshold(getattr(param, "q", None), getattr(param, "nt_sum", None)):
            q_nt_sum_warn.add(key)

        prev_param = by_eg_year.get(eid, {}).get(year - 1)
        if prev_param is None:
            continue
        prev_compare[key] = {
            "nust": _json_num(getattr(prev_param, "nust", None)),
            "qotr": _json_num(getattr(prev_param, "qotr", None)),
        }
        prev_nust = getattr(prev_param, "nust", None)
        curr_nust = getattr(param, "nust", None)
        if not _nust_changed_vs_previous(prev_nust, curr_nust):
            continue
        nust_changed.add(key)
        if _numeric_values_equal_for_compare(
            getattr(prev_param, "qotr", None),
            getattr(param, "qotr", None),
        ):
            composition_warn.add(key)

    return {
        "nust_changed_from_prev_year_rows": frozenset(nust_changed),
        "qotr_nt_ratio_warn_rows": frozenset(qotr_nt_warn),
        "q_nt_sum_ratio_warn_rows": frozenset(q_nt_sum_warn),
        "qotr_composition_warn_rows": frozenset(composition_warn),
        "fuel_param_prev_compare": prev_compare,
    }


def _build_nust_changed_from_prev_year_keys(
    rows: list,
    *,
    start_year: int | None = None,
) -> frozenset[str]:
    """Совместимость: ключи строк, где nust отличается от предыдущего календарного года."""
    del start_year  # сравнение идёт по календарному году−1 с догрузкой из БД при необходимости
    return build_fuel_param_row_warn_sets(rows)["nust_changed_from_prev_year_rows"]


_FUEL_PARAM_COPY_ATTRS: tuple[str, ...] = tuple(
    dict.fromkeys(
        ("name", "database_version_id")
        + tuple(EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS)
        + tuple(EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS)
        + tuple(EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS)
    )
)


def _year_uses_nust_nr_from_machine_powers(year_number: int, version_id: int | None) -> bool:
    """
    Руст/Ррасп из сумм p_ust/p_rasp по агрегатам: для годов с признаком «план» или «текущий (оценка)»
    (как в справочнике Year → YearFeature.name для данной версии БД).
    """
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict_for_version,
    )

    yf = get_year_feature_dict_for_version(version_id)
    raw = " ".join(str(yf.get(year_number) or "").split()).casefold()
    if raw in ("план", "текущий (оценка)"):
        return True
    if raw.replace(" ", "").startswith("текущий(") and "оценк" in raw:
        return True
    return False


def _apply_nust_nr_for_target_from_source_or_machines(
    target,
    source,
    *,
    target_year: int,
    equipment_group_id: int,
    version_id: int | None,
    cached_year_uses_nust_nr_from_machines: bool | None = None,
    cached_has_station_links: bool | None = None,
    cached_machine_ids: list[int] | None = None,
) -> None:
    """
    Руст/Ррасп: для «план» / «текущий (оценка)» — суммы p_ust/p_rasp (MachinePower) за целевой
    год, если у группы есть привязка к электростанции и есть агрегаты; иначе — как у базового года
    (source). Суммы 0 с MachinePower не подменяются с базового года: 0 допустим (агрегат не введён
    / выведен и т.д.).

    Тепловая мощность отборов, Гкал/ч (nt) при той же ветке: год строки = календарный год; из агрегатов группы
    берём те, у кого в этом году в MachinePower суммарно p_ust (Рust) ≠ 0; по MachineFuelParam.nt
    этих агрегатов сумма (по одному взносу на агрегат). Версия MFP: текущая или NULL. Иначе nt как у source.

    Поле nt_sum («Сумма тепловых мощностей, Гкал/ч») при расчёте nt по агрегатам выставляется равным этой же сумме — иначе после
    копирования года остаётся nt_sum с базового года (часто целое), а nt — дробное с машин.

    Кэш-параметры (все None — поведение как раньше, по одному SQL на вызов): ускоряют массовое
    «Добавить год/период» — по группе и году признак/привязка/список агрегатов считаются снаружи.
    """
    y_uses = (
        cached_year_uses_nust_nr_from_machines
        if cached_year_uses_nust_nr_from_machines is not None
        else _year_uses_nust_nr_from_machine_powers(target_year, version_id)
    )
    has_links = (
        cached_has_station_links
        if cached_has_station_links is not None
        else _fuel_equipment_group_has_station_links(equipment_group_id, version_id)
    )
    use_machines = y_uses and has_links
    if not use_machines:
        target.nust = getattr(source, "nust", None)
        target.nr = getattr(source, "nr", None)
        target.nt = getattr(source, "nt", None)
        return
    mids = (
        cached_machine_ids
        if cached_machine_ids is not None
        else _machine_ids_for_fuel_equipment_group(equipment_group_id, version_id)
    )
    if not mids:
        target.nust = getattr(source, "nust", None)
        target.nr = getattr(source, "nr", None)
        target.nt = getattr(source, "nt", None)
        return
    sum_ust, sum_rasp = _sum_p_ust_p_rasp_for_machines(mids, target_year, version_id)
    target.nust = sum_ust
    target.nr = sum_rasp
    target.nt = _sum_nt_for_machines_with_nonzero_p_ust_sum_in_year(
        mids, target_year, version_id
    )
    target.nt_sum = target.nt


def _fuel_equipment_group_has_station_links(
    equipment_group_id: int,
    version_id: int | None,
) -> bool:
    """Есть ли у группы реальная привязка к электростанции, а не standalone-link с `station_id = NULL`."""
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation

    q = (
        db.session.query(EquipmentGroupSet.id)
        .select_from(EquipmentGroupSet)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .filter(
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
            EquipmentGroupSetStation.station_id.isnot(None),
        )
    )
    if version_id is None:
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    return q.first() is not None


def _machine_ids_for_fuel_equipment_group(
    equipment_group_id: int,
    version_id: int | None,
) -> list[int]:
    """
    ID агрегатов (machines), входящих в итоговую группу оборудования:
    станция и тип группы из EquipmentGroupSet / EquipmentGroupSetStation.
    """
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    from app.generation.models.machine.machine_model import Machine

    q = (
        db.session.query(Machine.id)
        .select_from(EquipmentGroupSet)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .join(
            Machine,
            and_(
                Machine.id_station == EquipmentGroupSetStation.station_id,
                Machine.id_equipment_group == EquipmentGroupSetStation.equipment_group_type_id,
            ),
        )
        .outerjoin(MachineFuelParam, MachineFuelParam.machine_id == Machine.id)
        .filter(EquipmentGroupSet.equipment_group_id == equipment_group_id)
        .filter(
            or_(
                MachineFuelParam.equipment_group_id == equipment_group_id,
                MachineFuelParam.equipment_group_id.is_(None),
            )
        )
    )
    if version_id is None:
        q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
    else:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
    q = filter_by_explicit_db_version(q, Machine, version_id)
    rows = q.distinct().all()
    return [int(r[0]) for r in rows if r[0] is not None]


def _sum_p_ust_p_rasp_for_machines(
    machine_ids: list[int],
    year_number: int,
    version_id: int | None,
) -> tuple[Decimal, Decimal]:
    """Суммы p_ust и p_rasp в MachinePower за год (по всем переданным агрегатам)."""
    from app.generation.models.machine.machine_power_model import MachinePower

    if not machine_ids:
        return Decimal(0), Decimal(0)

    q = db.session.query(
        func.coalesce(func.sum(MachinePower.p_ust), 0),
        func.coalesce(func.sum(MachinePower.p_rasp), 0),
    ).filter(
        MachinePower.id_machine.in_(machine_ids),
        MachinePower.year_number == year_number,
    )
    q = filter_by_explicit_db_version(q, MachinePower, version_id)
    row = q.one()
    u, r = row[0], row[1]

    def _to_dec(x) -> Decimal:
        if x is None:
            return Decimal(0)
        if isinstance(x, Decimal):
            return x
        return Decimal(str(x))

    return _to_dec(u), _to_dec(r)


def _mfp_version_match_clause(version_id: int | None):
    """Как отбор MFP вместе с данными на странице «Турбины»: version_id или без версии."""
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam

    if version_id is None:
        return MachineFuelParam.database_version_id.is_(None)
    return or_(
        MachineFuelParam.database_version_id == version_id,
        MachineFuelParam.database_version_id.is_(None),
    )


def _sum_nt_for_machines_with_nonzero_p_ust_sum_in_year(
    machine_ids: list[int],
    year_number: int,
    version_id: int | None,
) -> Decimal:
    """
    nt для строки года: среди агрегатов группы (machine_ids) оставляем те, у которых в MachinePower
    за этот календарный год сумма p_ust (Рust) по всем строкам года не равна 0; для них один раз
    суммируем MachineFuelParam.nt (поле nt).
    """
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
    from app.generation.models.machine.machine_power_model import MachinePower

    if not machine_ids:
        return Decimal(0)

    mp_q = (
        db.session.query(MachinePower.id_machine, func.coalesce(func.sum(MachinePower.p_ust), 0))
        .filter(
            MachinePower.id_machine.in_(machine_ids),
            MachinePower.year_number == year_number,
        )
        .group_by(MachinePower.id_machine)
    )
    mp_q = filter_by_explicit_db_version(mp_q, MachinePower, version_id)

    def _to_dec(x) -> Decimal:
        if x is None:
            return Decimal(0)
        if isinstance(x, Decimal):
            return x
        return Decimal(str(x))

    eligible: set[int] = set()
    for mid, sum_ust in mp_q.all():
        if sum_ust is None:
            continue
        if _to_dec(sum_ust) == 0:
            continue
        if mid is not None:
            eligible.add(int(mid))

    if not eligible:
        return Decimal(0)

    mfp_q = (
        db.session.query(MachineFuelParam.nt)
        .filter(
            MachineFuelParam.machine_id.in_(eligible),
        )
        .filter(_mfp_version_match_clause(version_id))
    )

    tot = Decimal(0)
    for (nt_val,) in mfp_q.all():
        if nt_val is None:
            continue
        if isinstance(nt_val, Decimal):
            tot += nt_val
        else:
            tot += Decimal(str(nt_val))
    return tot


class _MissingYearFuelParam:
    """
    Год из интервала фильтра без строки в gs_fue_equipment_group_fuel_param.
    В шаблоне отображается год; поля параметров — как пустые. Для иерархии
    bool(param) == False, чтобы использовались данные EquipmentGroup (как у None).
    """

    __slots__ = ("year_number",)

    def __init__(self, year_number: int) -> None:
        self.year_number = int(year_number)

    def __bool__(self) -> bool:
        return False

    def __getattr__(self, name: str) -> None:
        return None


def _expand_fuel_param_rows_for_year_interval(
    rows: list,
    start_year: int,
    end_year: int,
) -> list:
    """
    Для каждой группы оборудования добавляет по строке на каждый год [start_year, end_year].
    Если записи параметров за год нет — пара (EquipmentGroup, _MissingYearFuelParam(year)).
    """
    years_range = range(start_year, end_year + 1)
    by_eg_order: list[int] = []
    by_eg_rows: dict[int, list] = defaultdict(list)

    for eg, param in rows or []:
        if not eg:
            continue
        eid = eg.id
        if eid not in by_eg_rows:
            by_eg_order.append(eid)
        by_eg_rows[eid].append((eg, param))

    out: list = []
    for eid in by_eg_order:
        eg_rows = by_eg_rows[eid]
        eg = eg_rows[0][0]
        year_to_param: dict[int, Any] = {}
        for _eg, param in eg_rows:
            if param is None:
                continue
            if isinstance(param, _MissingYearFuelParam):
                continue
            yn = getattr(param, "year_number", None)
            if yn is not None:
                year_to_param[int(yn)] = param
        for y in years_range:
            if y in year_to_param:
                out.append((eg, year_to_param[y]))
            else:
                out.append((eg, _MissingYearFuelParam(y)))
    return out


def assemble_fuel_edit_data_param_columns() -> tuple[
    list[tuple[str, str, bool]], frozenset[str]
]:
    """
    Базовые столбцы (метрики + TOPLS/UGLI) плюс детальные виды из ExtraFuelParam,
    которые есть в справочнике Fuel (для вложенной группировки: kazah→ekib и т.п.).
    """
    base: list[tuple[str, str, bool]] = list(FUEL_EDIT_DATA_PARAM_COLUMNS)
    seen = {a.casefold() for a, _, _ in base}
    fuel_nazvls = {
        (row.nazvl or "").casefold()
        for row in filter_by_db_version(Fuel.query, Fuel)
        .filter(Fuel.id > 0)
        .with_entities(Fuel.nazvl)
        if row.nazvl
    }
    extra_attrs: list[str] = []
    for name in sorted(_extra_fuel_param_value_column_names()):
        key = name.casefold()
        if key in seen or key not in fuel_nazvls:
            continue
        extra_attrs.append(name)
        base.append((name, name, True))
        seen.add(key)
    return base, frozenset(extra_attrs)


def enrich_fuel_hierarchy_summaries_with_extra(
    hierarchy: list | None,
    extra_by_gy: dict[str, Any] | None,
    extra_attrs: frozenset[str] | set[str] | None,
) -> None:
    """
    Дополняет station_summary / res_summary суммами по столбцам ExtraFuelParam
    (значения не лежат на основной записи FuelParam).
    """
    if not hierarchy or not extra_by_gy or not extra_attrs:
        return

    def _sum_extra(rows_to_sum: list) -> dict[str, Decimal]:
        summary: dict[str, Decimal] = {}
        for attr in extra_attrs:
            total = Decimal(0)
            for eg, param in rows_to_sum:
                if eg is None or getattr(eg, "id", None) is None or param is None:
                    continue
                ynum = getattr(param, "year_number", None)
                if ynum is None:
                    continue
                extra = extra_by_gy.get(f"{int(eg.id)}:{int(ynum)}")
                if extra is None:
                    continue
                val = getattr(extra, attr, None)
                if val is not None:
                    try:
                        total += Decimal(str(val))
                    except (TypeError, ValueError):
                        pass
            summary[attr] = total
        return summary

    for est_block in hierarchy:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                res_rows: list = []
                for gb in res_block.get("group_blocks") or []:
                    res_rows.extend(gb.get("rows") or [])
                if res_block.get("res_summary") is not None and res_rows:
                    res_block["res_summary"].update(_sum_extra(res_rows))
                for station_block in res_block.get("station_blocks") or []:
                    station_rows: list = []
                    for gb in station_block.get("group_blocks") or []:
                        station_rows.extend(gb.get("rows") or [])
                    if station_block.get("station_summary") is not None and station_rows:
                        station_block["station_summary"].update(_sum_extra(station_rows))


def _load_extra_fuel_param_by_group_year(
    equipment_group_ids: list[int],
    *,
    start_year: int,
    end_year: int,
) -> dict[str, Any]:
    """Ключ «{equipment_group_id}:{year_number}» → строка ExtraFuelParam (предпочтение текущей версии)."""
    ids = sorted({int(x) for x in (equipment_group_ids or []) if x is not None})
    if not ids:
        return {}
    version_id = get_current_db_version_id()
    q = EquipmentGroupExtraFuelParam.query.filter(
        EquipmentGroupExtraFuelParam.equipment_group_id.in_(ids),
        EquipmentGroupExtraFuelParam.year_number >= start_year,
        EquipmentGroupExtraFuelParam.year_number <= end_year,
    )
    if version_id is not None:
        q = q.filter(
            or_(
                EquipmentGroupExtraFuelParam.database_version_id == version_id,
                EquipmentGroupExtraFuelParam.database_version_id.is_(None),
            )
        )
    else:
        q = q.filter(EquipmentGroupExtraFuelParam.database_version_id.is_(None))

    by_gy: dict[tuple[int, int], list] = defaultdict(list)
    for row in q.all():
        if row.equipment_group_id is None or row.year_number is None:
            continue
        by_gy[(int(row.equipment_group_id), int(row.year_number))].append(row)

    out: dict[str, Any] = {}
    for (gid, y), items in by_gy.items():
        picked = _pick_specific_row_for_group_year(by_gy, gid, y, version_id)
        if picked is not None:
            out[f"{gid}:{y}"] = picked
    return out


def apply_extra_fuel_params_from_edit_data_form(
    request_form,
    *,
    equipment_group_ids: list[int],
    start_year: int,
    end_year: int,
    rounding_digits: int,
    extra_attrs: frozenset[str] | set[str],
) -> tuple[int, list[str], dict[int, list[tuple]]]:
    """
    Сохраняет детальные виды топлива (ExtraFuelParam) с массовой формы
    g{id}_fuel_param_{year}_{attr}.
    Возвращает (число затронутых групп, ошибки, change_details по id группы).
    """
    from app.fuel.services.equipment_groups.equipment_group_details_params_update_services import (
        TABLE_EXTRA,
        _convert_bulk_result_to_details,
    )
    from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_write_services import (
        save_equipment_group_extra_fuel_params_bulk,
    )

    if not extra_attrs:
        return 0, [], {}
    errs: list[str] = []
    changed_groups = 0
    details_by_group: dict[int, list[tuple]] = {}
    version_id = get_current_db_version_id()
    attrs = sorted(extra_attrs)
    for eg_id in equipment_group_ids:
        values_by_year: dict[int, dict] = {}
        for year in range(int(start_year), int(end_year) + 1):
            year_vals: dict[str, Any] = {}
            for attr in attrs:
                key = f"g{eg_id}_fuel_param_{year}_{attr}"
                if key not in request_form:
                    continue
                year_vals[attr] = request_form.get(key)
            if year_vals:
                values_by_year[year] = year_vals
        if not values_by_year:
            continue
        try:
            result = save_equipment_group_extra_fuel_params_bulk(
                equipment_group_id=int(eg_id),
                values_by_year=values_by_year,
                database_version_id=version_id,
                commit=False,
                rounding_digits=rounding_digits,
            )
            _count, details = _convert_bulk_result_to_details(result, TABLE_EXTRA)
            if details:
                changed_groups += 1
                details_by_group[int(eg_id)] = list(details)
        except Exception as exc:
            errs.append(f"Доп. топливо, группа id={eg_id}: {exc}")
    return changed_groups, errs, details_by_group


def build_fuel_nazvl_to_name_map() -> dict[str, str]:
    """Подписи столбцов топлива = Fuel.name из /refdata/fuel (ключ — nazvl без учёта регистра)."""
    fuel_query = filter_by_db_version(Fuel.query, Fuel)
    return {
        (row.nazvl or "").casefold(): (row.name or "").strip()
        for row in fuel_query.with_entities(Fuel.nazvl, Fuel.name)
        if row.nazvl and row.name
    }


def build_fuel_param_columns_hierarchy(
    fuel_param_columns: list[tuple[str, str, bool]],
) -> dict[str, Any]:
    """
    Упорядочивает столбцы видов топлива по иерархии Fuel.parent_id (как /refdata/fuel)
    и строит карту сворачивания: дочерние столбцы группируются под родительским «плюсиком»,
    с поддержкой нескольких уровней вложенности.

    Нетопливные столбцы (код, мощность и т.п.) сохраняют исходный порядок;
    блок видов топлива переставляется по DFS дерева справочника.
    """
    if not fuel_param_columns:
        return {
            "fuel_param_columns": [],
            "group_parents": [],
            "collapse_under": {},
            "children_by_parent": {},
        }

    col_by_attr = {attr: (attr, label, is_numeric) for attr, label, is_numeric in fuel_param_columns}
    attrs_in_order = [attr for attr, _, _ in fuel_param_columns]
    # Только поля видов топлива (не метрики вроде b/nt — иначе коллизия с Fuel.nazvl='B').
    # Детальные угли/газы из ExtraFuelParam — для вложенной группировки (kazah→ekib и т.п.).
    known_fuel_nazvl = {
        x.casefold()
        for x in (
            TOPLS
            | UGLI
            | UGLI1
            | _extra_fuel_param_value_column_names()
            | _natural_fuel_value_column_names()
        )
    }
    fuel_field_attrs = {a for a in attrs_in_order if a.casefold() in known_fuel_nazvl}
    attr_set = {a.casefold(): a for a in fuel_field_attrs}

    fuels = (
        filter_by_db_version(Fuel.query, Fuel)
        .filter(Fuel.id > 0)
        .with_entities(Fuel.id, Fuel.name, Fuel.nazvl, Fuel.parent_id)
        .all()
    )
    by_id: dict[int, Any] = {}
    children_ids: dict[int | None, list[int]] = defaultdict(list)
    for f in fuels:
        by_id[int(f.id)] = f
        children_ids[f.parent_id].append(int(f.id))

    def _sort_fuel_ids(ids: list[int]) -> list[int]:
        return sorted(
            ids,
            key=lambda fid: ((by_id[fid].name or "").casefold(), fid),
        )

    for pid in list(children_ids.keys()):
        children_ids[pid] = _sort_fuel_ids(children_ids[pid])

    nazvl_to_attr: dict[str, str] = {}
    attr_to_fuel_id: dict[str, int] = {}
    for f in fuels:
        if not f.nazvl:
            continue
        key = f.nazvl.casefold()
        attr = attr_set.get(key)
        if attr is not None:
            nazvl_to_attr[key] = attr
            attr_to_fuel_id[attr] = int(f.id)

    fuel_attrs_set = set(attr_to_fuel_id.keys())
    # Префикс до первого столбца-вида топлива; хвост — неизвестные справочнику attrs.
    first_fuel_idx = next(
        (i for i, a in enumerate(attrs_in_order) if a in fuel_attrs_set),
        len(attrs_in_order),
    )
    prefix_attrs = attrs_in_order[:first_fuel_idx]
    remaining_fuel_like = [a for a in attrs_in_order[first_fuel_idx:] if a not in fuel_attrs_set]

    ordered_fuel_attrs: list[str] = []
    seen_fuel: set[str] = set()

    def _walk(fuel_id: int) -> None:
        f = by_id.get(fuel_id)
        if f is None:
            return
        nazvl_key = (f.nazvl or "").casefold()
        attr = nazvl_to_attr.get(nazvl_key)
        if attr is not None and attr not in seen_fuel:
            seen_fuel.add(attr)
            ordered_fuel_attrs.append(attr)
        for child_id in children_ids.get(fuel_id, []):
            _walk(child_id)

    root_ids = _sort_fuel_ids([fid for fid in by_id if by_id[fid].parent_id is None])
    # Корни без parent_id, плюс «осиротевшие» (parent отсутствует в версии)
    orphan_ids = [
        fid
        for fid in by_id
        if by_id[fid].parent_id is not None and by_id[fid].parent_id not in by_id
    ]
    for fid in root_ids + _sort_fuel_ids(orphan_ids):
        _walk(fid)

    # Виды топлива из столбцов, не найденные в справочнике / не обойдённые — в исходном порядке
    for a in attrs_in_order:
        if a in fuel_attrs_set and a not in seen_fuel:
            ordered_fuel_attrs.append(a)
            seen_fuel.add(a)

    collapse_under: dict[str, str] = {}
    children_by_parent: dict[str, list[str]] = defaultdict(list)

    for attr, fuel_id in attr_to_fuel_id.items():
        cur = by_id.get(fuel_id)
        nearest: str | None = None
        seen_ids: set[int] = set()
        while cur is not None and cur.parent_id is not None and cur.parent_id not in seen_ids:
            seen_ids.add(int(cur.parent_id))
            parent = by_id.get(int(cur.parent_id))
            if parent is None:
                break
            parent_attr = nazvl_to_attr.get((parent.nazvl or "").casefold())
            if parent_attr is not None:
                nearest = parent_attr
                break
            cur = parent
        if nearest is not None:
            collapse_under[attr] = nearest
            children_by_parent[nearest].append(attr)

    # Сохраняем порядок детей как в упорядоченном списке столбцов
    for parent, kids in list(children_by_parent.items()):
        children_by_parent[parent] = [a for a in ordered_fuel_attrs if a in kids]

    group_parents = [p for p in ordered_fuel_attrs if p in children_by_parent]

    new_attrs = prefix_attrs + ordered_fuel_attrs + remaining_fuel_like
    # На случай дублей / пропусков — добить исходным порядком
    missing = [a for a in attrs_in_order if a not in new_attrs]
    new_attrs.extend(missing)

    # Подписи столбцов видов топлива — Fuel.name из /refdata/fuel
    ordered_columns: list[tuple[str, str, bool]] = []
    for a in new_attrs:
        if a not in col_by_attr:
            continue
        attr, label, is_numeric = col_by_attr[a]
        fuel_id = attr_to_fuel_id.get(attr)
        if fuel_id is not None:
            fuel_obj = by_id.get(fuel_id)
            fuel_name = (getattr(fuel_obj, "name", None) or "").strip()
            if fuel_name:
                label = fuel_name
        ordered_columns.append((attr, label, is_numeric))

    return {
        "fuel_param_columns": ordered_columns,
        "group_parents": group_parents,
        "collapse_under": dict(collapse_under),
        "children_by_parent": dict(children_by_parent),
    }


def split_fuel_param_columns_coal_vs_other(
    fuel_param_column_hierarchy: dict[str, Any] | None,
    *,
    metric_attrs: set[str] | frozenset[str] | None = None,
    coal_root: str = "ugol",
) -> tuple[list[tuple[str, str, bool]], list[tuple[str, str, bool]]]:
    """
    Делит столбцы видов топлива на «кроме Уголь, в т.ч.» и «Уголь, в т.ч.»
    (корень coal_root и все потомки по collapse_under). Метрики (мощность и т.п.)
    в обе таблицы не входят.
    """
    hier = fuel_param_column_hierarchy or {}
    columns = list(hier.get("fuel_param_columns") or [])
    collapse_under = dict(hier.get("collapse_under") or {})
    metrics = {a.casefold() for a in (metric_attrs or ())}

    def _is_coal_tree(attr: str) -> bool:
        if attr == coal_root:
            return True
        cur = attr
        seen: set[str] = set()
        while cur in collapse_under and cur not in seen:
            seen.add(cur)
            parent = collapse_under[cur]
            if parent == coal_root:
                return True
            cur = parent
        return False

    non_coal: list[tuple[str, str, bool]] = []
    coal: list[tuple[str, str, bool]] = []
    for attr, label, is_numeric in columns:
        if attr.casefold() in metrics:
            continue
        if _is_coal_tree(attr):
            coal.append((attr, label, is_numeric))
        else:
            non_coal.append((attr, label, is_numeric))
    return non_coal, coal


def _fuel_edit_detail_numeric_cell(value, *, rounding_digits: int) -> str:
    """Как render_numeric_or_dash в шаблоне основных параметров."""
    if value is None:
        return "—"
    try:
        if isinstance(value, Decimal):
            if value == 0:
                return "—"
        elif isinstance(value, (int, float)) and value == 0:
            return "—"
    except Exception:
        pass
    return format_decimal_trim_for_display(value, digits=rounding_digits)


def _fuel_edit_detail_int_cell(value) -> str:
    if value is None:
        return "—"
    return str(int(value))


def _fuel_edit_detail_db_tooltip_numeric(value) -> str:
    """
    Подсказка (title) с полным значением из БД, без округления UI.
    Пустая строка — не показывать title.
    """
    if value is None:
        return ""
    s = format_decimal_for_display(value, digits=0)
    return s if s and s != "—" else ""


def _fuel_edit_detail_db_tooltip_numb1120(value) -> str:
    if value is None:
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        s = str(value).strip()
        return s if s and s.lower() not in ("none", "") else ""


_EXTRA_FUEL_PARAM_SKIP_COLS = frozenset(
    {
        "id",
        "equipment_group_id",
        "year_number",
        "name",
        "numb1",
        "numb1120",
        "database_version_id",
        "created_at",
        "updated_at",
    }
)


def _extra_fuel_param_value_column_names() -> frozenset[str]:
    return frozenset(
        c.name
        for c in EquipmentGroupExtraFuelParam.__table__.columns
        if c.name not in _EXTRA_FUEL_PARAM_SKIP_COLS
    )


def _natural_fuel_value_column_names() -> frozenset[str]:
    return frozenset(
        c.name
        for c in EquipmentGroupNaturalFuel.__table__.columns
        if c.name not in _EXTRA_FUEL_PARAM_SKIP_COLS
    )


def _main_fuel_param_formula_value_column_names() -> frozenset[str]:
    """Поля EquipmentGroupFuelParam (TOPLS|UGLI), куда formtxt пишет доли, если имя не из UGLI1."""
    allowed = set(TOPLS) | set(UGLI)
    return frozenset(
        c.name
        for c in EquipmentGroupFuelParam.__table__.columns
        if c.name in allowed
    )


def _ordered_fuel_param_columns_from_formulas(
    formula_rows: list,
    extra_value_cols: frozenset[str],
    main_fuel_value_cols: frozenset[str],
) -> tuple[list[str], dict[str, str]]:
    """
    Уникальные виды топлива из formtxt в порядке первого вхождения; источник значения:
    'extra' — EquipmentGroupExtraFuelParam (детальные, UGLI1),
    'main' — EquipmentGroupFuelParam (суммовые TOPLS|UGLI), согласовано с _parse_formtxt.
    """
    ordered: list[str] = []
    sources: dict[str, str] = {}
    seen: set[str] = set()
    for fr in formula_rows:
        for nm in collect_fuel_names_from_formtxt((fr.formtxt or "").strip()):
            if nm in seen:
                continue
            if nm in UGLI1 and nm in extra_value_cols:
                seen.add(nm)
                sources[nm] = "extra"
                ordered.append(nm)
            elif nm not in UGLI1 and nm in main_fuel_value_cols:
                seen.add(nm)
                sources[nm] = "main"
                ordered.append(nm)
    return ordered, sources


def _formtxt_for_year_from_sorted_formula_rows(formula_rows: list, year: int) -> str:
    """Одна строка formtxt на год: при нескольких вариантах — с наименьшим variant_number."""
    cands = [fr for fr in formula_rows if int(fr.year_number) == int(year)]
    if not cands:
        return "—"
    cands = sorted(cands, key=lambda r: int(r.variant_number or 0))
    return (cands[0].formtxt or "").strip() or "—"


def _pick_specific_row_for_group_year(
    by_group_year: dict[tuple[int, int], list],
    equipment_group_id: int,
    year_number: int,
    prefer_version_id: int | None,
) -> Any:
    items = by_group_year.get((equipment_group_id, year_number)) or []
    if not items:
        return None
    if prefer_version_id is not None:
        for r in items:
            if getattr(r, "database_version_id", None) == prefer_version_id:
                return r
    for r in items:
        if getattr(r, "database_version_id", None) is None:
            return r
    return items[0]


def build_fuel_calculation_edit_detail_panels_data(
    equipment_group_ids: list[int],
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
) -> dict[str, dict[str, list]]:
    """
    Данные для нижней панели страницы equipment_group_fuel_params_edit_data:
    удельные показатели, формулы топлива и таблица «Параметры топлива» — сумма уникальных
    имён из formtxt на интервале лет (столбцы отсортированы по русскому названию топлива);
    значения из EquipmentGroupExtraFuelParam (UGLI1) и из EquipmentGroupFuelParam
    (TOPLS|UGLI), согласно разбору формулы.
    (ключ — str(equipment_group_id)).
    """
    ids = sorted({int(x) for x in (equipment_group_ids or []) if x is not None})
    if not ids:
        return {}

    version_id = get_current_db_version_id()
    years = list(range(int(start_year), int(end_year) + 1))

    spec_q = EquipmentGroupSpecificFuelConsumption.query.filter(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id.in_(ids),
        EquipmentGroupSpecificFuelConsumption.year_number >= start_year,
        EquipmentGroupSpecificFuelConsumption.year_number <= end_year,
    )
    if version_id is not None:
        spec_q = spec_q.filter(
            or_(
                EquipmentGroupSpecificFuelConsumption.database_version_id == version_id,
                EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
            )
        )
    else:
        spec_q = spec_q.filter(EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))

    by_gy: dict[tuple[int, int], list] = defaultdict(list)
    for row in spec_q.all():
        if row.equipment_group_id is None or row.year_number is None:
            continue
        by_gy[(int(row.equipment_group_id), int(row.year_number))].append(row)

    extra_q = EquipmentGroupExtraFuelParam.query.filter(
        EquipmentGroupExtraFuelParam.equipment_group_id.in_(ids),
        EquipmentGroupExtraFuelParam.year_number >= start_year,
        EquipmentGroupExtraFuelParam.year_number <= end_year,
    )
    if version_id is not None:
        extra_q = extra_q.filter(
            or_(
                EquipmentGroupExtraFuelParam.database_version_id == version_id,
                EquipmentGroupExtraFuelParam.database_version_id.is_(None),
            )
        )
    else:
        extra_q = extra_q.filter(EquipmentGroupExtraFuelParam.database_version_id.is_(None))

    by_gy_extra: dict[tuple[int, int], list] = defaultdict(list)
    for row in extra_q.all():
        if row.equipment_group_id is None or row.year_number is None:
            continue
        by_gy_extra[(int(row.equipment_group_id), int(row.year_number))].append(row)

    main_q = EquipmentGroupFuelParam.query.filter(
        EquipmentGroupFuelParam.equipment_group_id.in_(ids),
        EquipmentGroupFuelParam.year_number >= start_year,
        EquipmentGroupFuelParam.year_number <= end_year,
    )
    if version_id is not None:
        main_q = main_q.filter(
            or_(
                EquipmentGroupFuelParam.database_version_id == version_id,
                EquipmentGroupFuelParam.database_version_id.is_(None),
            )
        )
    else:
        main_q = main_q.filter(EquipmentGroupFuelParam.database_version_id.is_(None))

    by_gy_main: dict[tuple[int, int], list] = defaultdict(list)
    for row in main_q.all():
        if row.equipment_group_id is None or row.year_number is None:
            continue
        by_gy_main[(int(row.equipment_group_id), int(row.year_number))].append(row)

    extra_value_cols = _extra_fuel_param_value_column_names()
    main_fuel_value_cols = _main_fuel_param_formula_value_column_names()
    fuel_nazvl_labels = build_fuel_nazvl_to_name_map()

    # Как на /fuel/equipment_group_fuel_formulas: связка версии строки формулы с версией группы.
    # Годы формул ограничиваем интервалом [start_year, end_year], как у остальных таблиц
    # нижней панели.
    formula_version_match = or_(
        and_(
            EquipmentGroupFuelFormula.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelFormula.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    f_q = (
        db.session.query(EquipmentGroupFuelFormula)
        .join(
            EquipmentGroup,
            and_(
                EquipmentGroupFuelFormula.equipment_group_id == EquipmentGroup.id,
                formula_version_match,
            ),
        )
        .filter(EquipmentGroupFuelFormula.equipment_group_id.in_(ids))
        .filter(
            EquipmentGroupFuelFormula.year_number >= start_year,
            EquipmentGroupFuelFormula.year_number <= end_year,
        )
    )
    if version_id is not None:
        f_q = f_q.filter(EquipmentGroup.database_version_id == version_id)
    else:
        f_q = f_q.filter(EquipmentGroup.database_version_id.is_(None))

    by_formula_group: dict[int, list] = defaultdict(list)
    for row in f_q.all():
        by_formula_group[int(row.equipment_group_id)].append(row)

    def _sort_formulas(rows: list) -> list:
        return sorted(rows, key=lambda r: (int(r.year_number), int(r.variant_number or 0)))

    out: dict[str, dict[str, list]] = {}
    for gid in ids:
        spec_out: list[dict[str, str | int]] = []
        for y in years:
            r = _pick_specific_row_for_group_year(by_gy, gid, y, version_id)
            # Нижняя панель — только просмотр *_calc. Считаем по текущим топливным
            # параметрам (как recalc), чтобы не показывать прочерки при пустых
            # полях в gs_fue_equipment_group_specific_fuel_consumption.
            param = _pick_specific_row_for_group_year(by_gy_main, gid, y, version_id)
            if param is not None:
                coeff_k = (
                    r.k if (r is not None and getattr(r, "k", None) is not None) else None
                )
                v_y_calc = calc_y_calc(param)
                v_btp_calc = calc_btp_calc(param, coeff_k)
                v_sntp_calc = calc_sntp_calc(param)
                v_bk_calc = calc_bk_calc(param, v_btp_calc, v_sntp_calc)
                v_snk_calc = getattr(param, "snk", None)
            else:
                v_snk_calc = getattr(r, "snk_calc", None) if r else None
                v_btp_calc = getattr(r, "btp_calc", None) if r else None
                v_sntp_calc = getattr(r, "sntp_calc", None) if r else None
                v_bk_calc = getattr(r, "bk_calc", None) if r else None
                v_y_calc = getattr(r, "y_calc", None) if r else None
            spec_out.append(
                {
                    "year": y,
                    "snk_calc": _fuel_edit_detail_numeric_cell(
                        v_snk_calc,
                        rounding_digits=rounding_digits,
                    ),
                    "btp_calc": _fuel_edit_detail_numeric_cell(
                        v_btp_calc,
                        rounding_digits=rounding_digits,
                    ),
                    "sntp_calc": _fuel_edit_detail_numeric_cell(
                        v_sntp_calc,
                        rounding_digits=rounding_digits,
                    ),
                    "bk_calc": _fuel_edit_detail_numeric_cell(
                        v_bk_calc,
                        rounding_digits=rounding_digits,
                    ),
                    "y_calc": _fuel_edit_detail_numeric_cell(
                        v_y_calc,
                        rounding_digits=rounding_digits,
                    ),
                    "db_tooltips": {
                        "snk_calc": _fuel_edit_detail_db_tooltip_numeric(v_snk_calc),
                        "btp_calc": _fuel_edit_detail_db_tooltip_numeric(v_btp_calc),
                        "sntp_calc": _fuel_edit_detail_db_tooltip_numeric(v_sntp_calc),
                        "bk_calc": _fuel_edit_detail_db_tooltip_numeric(v_bk_calc),
                        "y_calc": _fuel_edit_detail_db_tooltip_numeric(v_y_calc),
                    },
                }
            )

        formulas_src = _sort_formulas(by_formula_group.get(gid, []))
        formulas_out = [
            {
                "year": y,
                "formtxt": _formtxt_for_year_from_sorted_formula_rows(formulas_src, y),
            }
            for y in years
        ]

        extra_columns, column_sources = _ordered_fuel_param_columns_from_formulas(
            formulas_src, extra_value_cols, main_fuel_value_cols
        )
        extra_column_labels = {
            c: fuel_nazvl_labels.get((c or "").casefold(), c) for c in extra_columns
        }
        # Столбцы «Параметры топлива» — по русскому названию (Fuel.name), затем по nazvl.
        extra_columns = sorted(
            extra_columns,
            key=lambda c: (
                (extra_column_labels.get(c) or c).casefold(),
                (c or "").casefold(),
            ),
        )
        extra_rows: list[dict[str, str | int]] = []
        for y in years:
            er = _pick_specific_row_for_group_year(by_gy_extra, gid, y, version_id)
            mr = _pick_specific_row_for_group_year(by_gy_main, gid, y, version_id)
            row_d: dict[str, str | int] = {"year": y}
            col_tips: dict[str, str] = {}
            for col in extra_columns:
                src = column_sources.get(col, "extra")
                src_row = er if src == "extra" else mr
                raw_c = getattr(src_row, col, None) if src_row else None
                row_d[col] = _fuel_edit_detail_numeric_cell(
                    raw_c,
                    rounding_digits=rounding_digits,
                )
                col_tips[col] = _fuel_edit_detail_db_tooltip_numeric(raw_c)
            row_d["db_tooltips"] = col_tips
            extra_rows.append(row_d)

        out[str(gid)] = {
            "specific": spec_out,
            "formulas": formulas_out,
            "extra_fuel": {
                "columns": extra_columns,
                "column_sources": column_sources,
                "column_labels": extra_column_labels,
                "rows": extra_rows,
            },
        }

    return out


def _group_fuel_param_rows_by_equipment_group(rows: list) -> list[list]:
    """
    Группирует подряд идущие строки одной группы оборудования (после сортировки по группе и году)
    для вертикального объединения ячеек в таблице.
    """
    if not rows:
        return []
    from itertools import groupby

    def _key(item: tuple) -> int:
        eg = item[0]
        return int(eg.id) if eg is not None and getattr(eg, "id", None) is not None else 0

    return [list(g) for _, g in groupby(rows, key=_key)]


_FUEL_PARAM_SHOW_ZERO_ATTRS = frozenset(
    {
        "nust",
        "nr",
        "h",
        "e",
        "ewtp",
        "eotp",
        "eurt",
        "eust",
        "snk",
        "nt",
        "nt_sum",
        "q",
        "qotr",
        "turt",
        "tust",
        "sn_t",
    }
)


def _dedupe_fuel_param_rows_one_per_group(rows: list) -> list:
    """По одной строке на группу — для построения иерархии и пагинации без разворота лет."""
    seen: set[int] = set()
    out: list = []
    for eg, param in rows or []:
        if eg is None or getattr(eg, "id", None) is None:
            continue
        eid = int(eg.id)
        if eid in seen:
            continue
        seen.add(eid)
        out.append((eg, param))
    return out


def _fuel_param_input_display_value(
    raw,
    *,
    attr: str,
    is_numeric: bool,
    rounding_digits: int,
) -> str:
    """Строка для value input — как в макросе fuel_param_edit_or_view."""
    if raw is None:
        return ""
    if is_numeric and raw == 0 and attr not in _FUEL_PARAM_SHOW_ZERO_ATTRS:
        return ""
    if is_numeric:
        if attr in ("nt", "nt_sum"):
            return format_decimal_for_display(raw, digits=0)
        return format_decimal_trim_for_display(raw, digits=rounding_digits)
    return str(raw)


def _build_deferred_fuel_columns_payload(
    *,
    full_columns: list[tuple[str, str, bool]],
    fuel_param_column_hierarchy: dict[str, Any],
    fuel_nazvl_to_name: dict[str, str],
    rows: list,
    extra_by_gy: dict[str, Any],
    extra_attrs: frozenset[str] | set[str],
    rounding_digits: int,
) -> dict[str, Any]:
    """
    Данные свёрнутых (collapse_under) столбцов для отложенной вставки в DOM.
    В начальном HTML их нет — это главный выигрыш по размеру страницы (~80% ячеек).
    """
    collapse_under = fuel_param_column_hierarchy.get("collapse_under") or {}
    children_by_parent = fuel_param_column_hierarchy.get("children_by_parent") or {}
    group_parents = set(fuel_param_column_hierarchy.get("group_parents") or [])
    hier_sum_attrs = set(group_parents)
    hier_sum_attrs.add("b")

    deferred_cols: list[dict[str, Any]] = []
    deferred_attrs: list[str] = []
    for attr, label, is_numeric in full_columns:
        under = collapse_under.get(attr)
        if not under:
            continue
        deferred_attrs.append(attr)
        display_label = label
        if attr not in _FUEL_PARAM_SHOW_ZERO_ATTRS and attr != "b":
            display_label = fuel_nazvl_to_name.get(attr, label)
        deferred_cols.append(
            {
                "a": attr,
                "l": display_label,
                "n": bool(is_numeric),
                "u": under,
                "hs": attr in hier_sum_attrs,
                "p": attr in group_parents,
            }
        )

    extra_attr_set = {a.casefold(): a for a in (extra_attrs or [])}
    values: dict[str, dict[str, str]] = {}
    for eg, param in rows or []:
        if eg is None or getattr(eg, "id", None) is None or param is None:
            continue
        ynum = getattr(param, "year_number", None)
        if ynum is None:
            continue
        row_key = f"{int(eg.id)}:{int(ynum)}"
        extra = extra_by_gy.get(row_key) if extra_by_gy else None
        row_vals: dict[str, str] = {}
        for attr, label, is_numeric in full_columns:
            if attr not in collapse_under:
                continue
            src = extra if attr.casefold() in extra_attr_set else param
            raw = getattr(src, attr, None) if src is not None else None
            disp = _fuel_param_input_display_value(
                raw,
                attr=attr,
                is_numeric=bool(is_numeric),
                rounding_digits=rounding_digits,
            )
            if disp:
                row_vals[attr] = disp
        if row_vals:
            values[row_key] = row_vals

    return {
        "columns": deferred_cols,
        "values": values,
        "children_by_parent": {
            k: list(v) for k, v in (children_by_parent or {}).items()
        },
        "order": deferred_attrs,
    }


def get_fuel_calculation_edit_data_view_model(
    filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
    page: int = 1,
    per_page: int | str = 25,
    show_all: bool = False,
) -> dict[str, Any]:
    """
    Контекст таблицы основных топливных параметров по фильтрам расчётного модуля.

    Пагинация по группам выполняется до разворота лет: на страницу попадают только
    параметры выбранных групп за весь интервал start_year–end_year.

    :param filters: результат extract_filters_from_args (без page или с ним — будет сброшен).
    """
    from app.fuel.services.equipment_groups.fuel_station_hierarchy_pagination import (
        paginate_fuel_eg_station_hierarchy,
    )

    f = {**filters}
    f.pop("page", None)

    fuel_data = get_equipment_groups_with_fuel_params_data(
        filters=f,
        per_page="all",
        page=1,
        start_year=start_year,
        end_year=end_year,
        show_all=True,
    )
    rows_raw = fuel_data.get("rows") or []

    def _group_sort_key(item: tuple) -> tuple:
        eg, _param = item
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid)

    rows_for_paging = sorted(
        _dedupe_fuel_param_rows_one_per_group(rows_raw),
        key=_group_sort_key,
    )
    hierarchy_for_paging = build_equipment_group_fuel_params_hierarchy(
        rows_for_paging, use_equipment_group_hierarchy_only=False
    )

    if show_all or (
        isinstance(per_page, str) and str(per_page).lower() == "all"
    ):
        page_hierarchy_skeleton = hierarchy_for_paging
        total_eg_count = sum(
            len(sb.get("group_blocks") or [])
            for est in hierarchy_for_paging or []
            for ues in est.get("ues_list") or []
            for res in ues.get("res_list") or []
            for sb in res.get("station_blocks") or []
        )
        total_pages = 1
        current_page = 1
    else:
        (
            page_hierarchy_skeleton,
            total_eg_count,
            total_pages,
            current_page,
        ) = paginate_fuel_eg_station_hierarchy(
            hierarchy_for_paging,
            page,
            per_page,
            FUEL_PARAMS_HIERARCHY_SUMMARY_NUMERIC_ATTRS,
        )

    page_group_ids: set[int] = set()
    for est_block in page_hierarchy_skeleton or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                for station_block in res_block.get("station_blocks") or []:
                    for gb in station_block.get("group_blocks") or []:
                        eg = gb.get("equipment_group")
                        if eg is not None and getattr(eg, "id", None) is not None:
                            page_group_ids.add(int(eg.id))

    rows_page_raw = [
        (eg, param)
        for eg, param in rows_raw
        if eg is not None
        and getattr(eg, "id", None) is not None
        and int(eg.id) in page_group_ids
    ]
    # Группы без строк параметров в интервале всё равно нужны на странице
    raw_ids = {
        int(eg.id)
        for eg, _ in rows_page_raw
        if eg is not None and getattr(eg, "id", None) is not None
    }
    for est_block in page_hierarchy_skeleton or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                for station_block in res_block.get("station_blocks") or []:
                    for gb in station_block.get("group_blocks") or []:
                        eg = gb.get("equipment_group")
                        if (
                            eg is not None
                            and getattr(eg, "id", None) is not None
                            and int(eg.id) not in raw_ids
                        ):
                            rows_page_raw.append((eg, None))
                            raw_ids.add(int(eg.id))

    rows = _expand_fuel_param_rows_for_year_interval(
        rows_page_raw, start_year, end_year
    )

    def _row_sort_key(item: tuple) -> tuple:
        eg, param = item
        y = getattr(param, "year_number", None) if param is not None else None
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid, y or 0)

    rows = sorted(rows, key=_row_sort_key)

    bulk_edit_equipment_group_ids = sorted(page_group_ids)

    row_groups = _group_fuel_param_rows_by_equipment_group(rows)

    name_maps = build_name_maps_from_rows(rows)
    hierarchy = build_equipment_group_fuel_params_hierarchy(
        rows, use_equipment_group_hierarchy_only=False
    )
    fuel_nazvl_to_name = build_fuel_nazvl_to_name_map()
    full_columns, fuel_extra_column_attrs = assemble_fuel_edit_data_param_columns()
    fuel_param_column_hierarchy = build_fuel_param_columns_hierarchy(full_columns)
    collapse_under = fuel_param_column_hierarchy.get("collapse_under") or {}
    fuel_param_columns_visible = [
        col for col in (fuel_param_column_hierarchy.get("fuel_param_columns") or full_columns)
        if col[0] not in collapse_under
    ]
    # В иерархии столбцов оставляем полный список (для JS), плюс явный visible-срез для шаблона
    fuel_param_column_hierarchy = {
        **fuel_param_column_hierarchy,
        "fuel_param_columns_visible": fuel_param_columns_visible,
    }
    extra_fuel_param_by_group_year = _load_extra_fuel_param_by_group_year(
        bulk_edit_equipment_group_ids,
        start_year=start_year,
        end_year=end_year,
    )

    warn_sets = build_fuel_param_row_warn_sets(rows)
    deferred_fuel_columns = _build_deferred_fuel_columns_payload(
        full_columns=fuel_param_column_hierarchy.get("fuel_param_columns") or full_columns,
        fuel_param_column_hierarchy=fuel_param_column_hierarchy,
        fuel_nazvl_to_name=fuel_nazvl_to_name,
        rows=rows,
        extra_by_gy=extra_fuel_param_by_group_year,
        extra_attrs=fuel_extra_column_attrs,
        rounding_digits=rounding_digits,
    )

    return {
        "equipment_group_fuel_param_rows": rows,
        "equipment_group_fuel_param_row_groups": row_groups,
        "equipment_group_fuel_params_hierarchy": hierarchy,
        **warn_sets,
        "total_count": total_eg_count,
        "total_pages": total_pages,
        "page": current_page,
        "per_page": per_page if not show_all else "all",
        "fuel_nazvl_to_name": fuel_nazvl_to_name,
        "fuel_param_column_hierarchy": fuel_param_column_hierarchy,
        "fuel_extra_column_attrs": fuel_extra_column_attrs,
        "extra_fuel_param_by_group_year": extra_fuel_param_by_group_year,
        "deferred_fuel_columns": deferred_fuel_columns,
        "obor_name_map": name_maps.get("obor_name_map", {}),
        "obl_name_map": name_maps.get("obl_name_map", {}),
        "dep_name_map": name_maps.get("dep_name_map", {}),
        "oes_name_map": name_maps.get("oes_name_map", {}),
        "er_name_map": name_maps.get("er_name_map", {}),
        "gk_name_map": name_maps.get("gk_name_map", {}),
        "be_name_map": name_maps.get("be_name_map", {}),
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "bulk_edit_equipment_group_ids": bulk_edit_equipment_group_ids,
    }


def _get_fuel_param_for_group_year(
    equipment_group_id: int,
    year_number: int,
    version_id: int | None,
) -> EquipmentGroupFuelParam | None:
    q = EquipmentGroupFuelParam.query.filter_by(
        equipment_group_id=equipment_group_id,
        year_number=year_number,
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupFuelParam.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroupFuelParam.database_version_id.is_(None))
    return q.first()


def _bulk_fuel_params_by_group_and_years(
    equipment_group_ids: list[int],
    year_numbers: set,
    version_id: int | None,
) -> dict[tuple[int, int], EquipmentGroupFuelParam]:
    """
    Одна выборка строк EquipmentGroupFuelParam по списку групп и набору календарных годов
    (ускоряет «Добавить год/период» вместо N·M запросов _get_fuel_param_for_group_year).
    """
    if not equipment_group_ids or not year_numbers:
        return {}
    year_list = [int(x) for x in year_numbers]
    q = db.session.query(EquipmentGroupFuelParam).filter(
        EquipmentGroupFuelParam.equipment_group_id.in_([int(x) for x in equipment_group_ids]),
        EquipmentGroupFuelParam.year_number.in_(year_list),
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupFuelParam.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroupFuelParam.database_version_id.is_(None))
    return {
        (int(r.equipment_group_id), int(r.year_number)): r
        for r in q.all()
    }


def copy_fuel_params_between_years_for_filters(
    filters: dict[str, Any],
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year: int,
    target_year: int,
) -> tuple[int, int, int]:
    """
    Копирует основные топливные параметры (EquipmentGroupFuelParam) с source_year на target_year
    для всех групп оборудования по тем же фильтрам, что на странице редактирования.

    Возвращает (число записей сохранено, пропущено — нет данных за год-источник, всего групп в выборке).
    """
    if source_year == target_year:
        return 0, 0, 0

    f = {**filters}
    f.pop("page", None)

    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f,
        start_year=filter_start_year,
        end_year=filter_end_year,
    )
    if not eg_ids:
        return 0, 0, 0

    version_id = get_current_db_version_id()
    year_uses_nust_nr = _year_uses_nust_nr_from_machine_powers(target_year, version_id)

    copied = 0
    skipped = 0

    for eg_id in eg_ids:
        eg_id = int(eg_id)
        source = _get_fuel_param_for_group_year(eg_id, source_year, version_id)
        if source is None:
            skipped += 1
            continue

        target = _get_fuel_param_for_group_year(eg_id, target_year, version_id)
        if target is None:
            target = EquipmentGroupFuelParam(
                equipment_group_id=eg_id,
                year_number=target_year,
                database_version_id=version_id,
            )
            set_db_version_on_create(target)
            db.session.add(target)

        for key in _FUEL_PARAM_COPY_ATTRS:
            setattr(target, key, getattr(source, key))

        target.year_number = target_year
        target.equipment_group_id = eg_id
        if version_id is not None and getattr(target, "database_version_id", None) is None:
            target.database_version_id = version_id

        if not year_uses_nust_nr:
            h_links, mid_list = False, []
        else:
            h_links = _fuel_equipment_group_has_station_links(eg_id, version_id)
            mid_list = _machine_ids_for_fuel_equipment_group(eg_id, version_id) if h_links else []

        _apply_nust_nr_for_target_from_source_or_machines(
            target,
            source,
            target_year=target_year,
            equipment_group_id=eg_id,
            version_id=version_id,
            cached_year_uses_nust_nr_from_machines=year_uses_nust_nr,
            cached_has_station_links=h_links,
            cached_machine_ids=mid_list,
        )

        sanitize_equipment_group_fuel_param_foreign_keys(target)
        copied += 1

    return copied, skipped, len(eg_ids)


# Показатели тепла с базового года (q — отдельно: приоритет «Тепло и тарифы из СТ»).
# nt задаётся в _apply_nust_nr_… (см. _sum_nt_for_machines_with_nonzero_p_ust_sum_in_year).
# hfix (+ h при фиксации): как в Access HFIX на каждом годе; иначе Распред пересчитает часы.
_HEAT_FUEL_PARAM_COPY_ATTRS: tuple[str, ...] = ("q", "qotr", "nt_sum", "turt", "hfix")


def _bulk_heat_and_tariffs_q_by_group_and_years(
    equipment_group_ids: list[int],
    year_numbers: set,
    version_id: int | None,
) -> dict[tuple[int, int], Any]:
    """
    Q из EquipmentGroupHeatAndTariffs (страница «Тепло и тарифы из СТ») по группе и году.

    При нескольких записях за один год сумма ненулевых q (как сводки на той странице).
    Ключ отсутствует, если записей нет или все q пустые — тогда q берут с базового года.
    """
    from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import (
        EquipmentGroupHeatAndTariffs,
    )

    if not equipment_group_ids or not year_numbers:
        return {}
    year_list = [int(x) for x in year_numbers]
    eg_list = [int(x) for x in equipment_group_ids]
    q = db.session.query(
        EquipmentGroupHeatAndTariffs.equipment_group_id,
        EquipmentGroupHeatAndTariffs.year_number,
        EquipmentGroupHeatAndTariffs.q,
    ).filter(
        EquipmentGroupHeatAndTariffs.equipment_group_id.in_(eg_list),
        EquipmentGroupHeatAndTariffs.year_number.in_(year_list),
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupHeatAndTariffs.database_version_id == version_id)
    else:
        q = q.filter(EquipmentGroupHeatAndTariffs.database_version_id.is_(None))

    sums: dict[tuple[int, int], Decimal] = {}
    has_value: dict[tuple[int, int], bool] = {}
    for eg_id, year_number, q_val in q.all():
        if eg_id is None or year_number is None or q_val is None:
            continue
        key = (int(eg_id), int(year_number))
        try:
            sums[key] = sums.get(key, Decimal(0)) + Decimal(str(q_val))
            has_value[key] = True
        except (TypeError, ValueError):
            continue
    return {k: sums[k] for k in has_value}


def copy_heat_fuel_param_columns_for_filters(
    filters: dict[str, Any],
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year_number: int,
    target_year_numbers: list[int],
) -> tuple[int, int, int]:
    """
    Заполняет тепловые показатели на заданные календарные годы для групп по фильтрам страницы.

    q: из EquipmentGroupHeatAndTariffs (Q на «Тепло и тарифы из СТ») за целевой год;
    если там нет данных — с source_year_number.
    qotr, nt_sum, turt: всегда с source_year_number.

    Существующая строка за целевой год обновляется только по перечисленным полям;
    при отсутствии строки создаётся новая.

    nust, nr, nt, nt_sum: см. _apply_nust_nr_for_target_from_source_or_machines (nt и nt_sum —
    сумма MachineFuelParam.nt по агрегатам группы с ненулевой суммой p_ust за целевой год; см.
    _sum_nt_for_machines_with_nonzero_p_ust_sum_in_year, в той же ветке, что и Руст).

    Возвращает (число операций group×год, пропущено групп без данных за год-источник, всего групп).
    """
    tyn_set = {int(x) for x in (target_year_numbers or []) if x is not None}
    tyn_set.discard(int(source_year_number))
    if not tyn_set:
        return 0, 0, 0
    tyn_sorted = sorted(tyn_set)

    f = {**filters}
    f.pop("page", None)
    eg_ids = get_equipment_group_ids_for_fuel_params_filters(
        f, start_year=filter_start_year, end_year=filter_end_year
    )
    if not eg_ids:
        return 0, 0, 0

    version_id = get_current_db_version_id()
    copied = 0
    skipped = 0

    years_to_load = {int(source_year_number), *tyn_set}
    eg_ids_int = [int(x) for x in eg_ids]
    params_by_eg_year = _bulk_fuel_params_by_group_and_years(
        eg_ids_int, years_to_load, version_id
    )
    q_from_heat_tariffs = _bulk_heat_and_tariffs_q_by_group_and_years(
        eg_ids_int, tyn_set, version_id
    )
    year_uses_machines: dict[int, bool] = {
        tyn: _year_uses_nust_nr_from_machine_powers(tyn, version_id) for tyn in tyn_sorted
    }
    any_year_needs_machines = any(year_uses_machines[tyn] for tyn in tyn_sorted)

    for eg_id in eg_ids:
        eg_id = int(eg_id)
        source = params_by_eg_year.get((eg_id, int(source_year_number)))
        if source is None:
            skipped += 1
            continue
        if not any_year_needs_machines:
            has_links = False
            mids: list[int] = []
        else:
            has_links = _fuel_equipment_group_has_station_links(eg_id, version_id)
            mids = _machine_ids_for_fuel_equipment_group(eg_id, version_id) if has_links else []
        for tyn in tyn_sorted:
            target = params_by_eg_year.get((eg_id, tyn))
            if target is None:
                target = EquipmentGroupFuelParam(
                    equipment_group_id=eg_id,
                    year_number=tyn,
                    database_version_id=version_id,
                )
                set_db_version_on_create(target)
                db.session.add(target)
            for key in _HEAT_FUEL_PARAM_COPY_ATTRS:
                if key == "q":
                    hat_q = q_from_heat_tariffs.get((eg_id, tyn))
                    setattr(
                        target,
                        "q",
                        hat_q if hat_q is not None else getattr(source, "q"),
                    )
                else:
                    setattr(target, key, getattr(source, key))

            # Access: при HFIX=1 часы H тоже зафиксированы — копируем с базы.
            try:
                src_hfix = int(getattr(source, "hfix", None) or 0)
            except (TypeError, ValueError):
                src_hfix = 0
            if src_hfix == 1 and getattr(source, "h", None) is not None:
                target.h = source.h

            _apply_nust_nr_for_target_from_source_or_machines(
                target,
                source,
                target_year=tyn,
                equipment_group_id=eg_id,
                version_id=version_id,
                cached_year_uses_nust_nr_from_machines=year_uses_machines[tyn],
                cached_has_station_links=has_links,
                cached_machine_ids=mids,
            )

            sanitize_equipment_group_fuel_param_foreign_keys(target)
            copied += 1

    return copied, skipped, len(eg_ids)


def _save_main_fuel_param_detail_panel_values(
    *,
    equipment_group_id: int,
    values_by_year: dict[int, dict],
    database_version_id: int | None,
    rounding_digits: int,
) -> None:
    """
    Обновление числовых полей EquipmentGroupFuelParam (доли TOPLS|UGLI) из нижней панели.
    values_by_year: {год: {attr: сырьё с формы}}.
    """
    from app.common.services.help_services import values_equal_by_display_precision
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
        NUMERIC_ATTRS,
        _parse_fuel_param_value,
    )

    for y, attrs in sorted(values_by_year.items()):
        if not attrs:
            continue
        y = int(y)
        param = _get_fuel_param_for_group_year(equipment_group_id, y, database_version_id)
        if param is None:
            has_any = any(
                _parse_fuel_param_value(a, raw) is not None
                for a, raw in attrs.items()
                if a in NUMERIC_ATTRS
            )
            if not has_any:
                continue
            param = EquipmentGroupFuelParam(
                equipment_group_id=equipment_group_id,
                year_number=y,
                database_version_id=database_version_id,
            )
            set_db_version_on_create(param)
            db.session.add(param)
            db.session.flush()

        if (
            hasattr(param, "database_version_id")
            and param.database_version_id is None
            and database_version_id is not None
        ):
            param.database_version_id = database_version_id

        for attr, raw in attrs.items():
            if attr not in NUMERIC_ATTRS:
                continue
            val = _parse_fuel_param_value(attr, raw)
            old_val = getattr(param, attr, None)
            if values_equal_by_display_precision(old_val, val, rounding_digits):
                continue
            setattr(param, attr, val)

        sanitize_equipment_group_fuel_param_foreign_keys(param)


def apply_fuel_calculation_detail_panels_save(
    equipment_group_id: int,
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
    specific_rows: list[dict] | None,
    formula_rows: list[dict] | None,
    extra_fuel: dict | None,
) -> list[str]:
    """
    Сохранение нижней панели (удельные показатели, формулы, доп. параметры) для одной группы.
    Возвращает список ошибок; пустой список — успех. Без commit.
    """
    from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_write_services import (
        save_equipment_group_extra_fuel_params_bulk,
    )
    from app.fuel.services.equipment_groups.equipment_group_fuel_formula_write_services import (
        save_equipment_group_fuel_formula_for_year,
    )
    from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_write_services import (
        CONSUMPTION_FORM_INPUT_ATTRS,
        save_specific_fuel_consumption_for_year,
    )

    errs: list[str] = []
    vid = get_current_db_version_id()
    eg_id = int(equipment_group_id)
    year_set = set(range(int(start_year), int(end_year) + 1))

    for row in specific_rows or []:
        try:
            y = int(row["year"])
        except (TypeError, KeyError, ValueError):
            continue
        if y not in year_set:
            continue
        values: dict = {}
        for attr in CONSUMPTION_FORM_INPUT_ATTRS:
            if attr in row:
                values[attr] = row[attr]
        if not values:
            continue
        try:
            save_specific_fuel_consumption_for_year(
                equipment_group_id=eg_id,
                year_number=y,
                values=values,
                database_version_id=vid,
                commit=False,
                rounding_digits=rounding_digits,
            )
        except Exception as exc:
            errs.append(f"Удельные, год {y}: {exc}")

    for row in formula_rows or []:
        try:
            y = int(row["year"])
        except (TypeError, KeyError, ValueError):
            continue
        if y not in year_set:
            continue
        if "formtxt" not in row:
            continue
        try:
            save_equipment_group_fuel_formula_for_year(
                equipment_group_id=eg_id,
                year_number=y,
                values={"formtxt": row.get("formtxt", "")},
                variant_number=0,
                database_version_id=vid,
                commit=False,
            )
        except Exception as exc:
            errs.append(f"Формула, год {y}: {exc}")

    ex = extra_fuel or {}
    cols = list(ex.get("columns") or [])
    col_src = ex.get("column_sources") or {}
    rows_ex = ex.get("rows") or []
    main_fuel_value_cols = _main_fuel_param_formula_value_column_names()
    extra_value_cols = _extra_fuel_param_value_column_names()

    values_by_year_extra: dict[int, dict] = {}
    values_by_year_main: dict[int, dict] = {}
    for row in rows_ex:
        try:
            y = int(row["year"])
        except (TypeError, KeyError, ValueError):
            continue
        if y not in year_set:
            continue
        d_extra: dict = {}
        d_main: dict = {}
        for c in cols:
            if c not in row:
                continue
            src = col_src.get(c, "extra")
            if src == "main" and c in main_fuel_value_cols:
                d_main[c] = row[c]
            elif src != "main" and c in extra_value_cols:
                d_extra[c] = row[c]
        if d_extra:
            values_by_year_extra[y] = d_extra
        if d_main:
            values_by_year_main[y] = d_main
    if values_by_year_extra:
        try:
            save_equipment_group_extra_fuel_params_bulk(
                equipment_group_id=eg_id,
                values_by_year=values_by_year_extra,
                database_version_id=vid,
                commit=False,
                rounding_digits=rounding_digits,
            )
        except Exception as exc:
            errs.append(f"Доп. параметры топлива: {exc}")
    if values_by_year_main:
        try:
            _save_main_fuel_param_detail_panel_values(
                equipment_group_id=eg_id,
                values_by_year=values_by_year_main,
                database_version_id=vid,
                rounding_digits=rounding_digits,
            )
        except Exception as exc:
            errs.append(f"Параметры топлива (основная запись): {exc}")

    return errs
