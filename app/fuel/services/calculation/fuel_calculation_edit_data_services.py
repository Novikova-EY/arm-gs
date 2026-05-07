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
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    TOPLS,
    UGLI,
    UGLI1,
    collect_fuel_names_from_formtxt,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    EQUIPMENT_GROUP_DETAILS_MAIN_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE1_ATTRS,
    EQUIPMENT_GROUP_DETAILS_TABLE2_ATTRS,
    build_equipment_group_fuel_params_hierarchy,
    build_name_maps_from_rows,
    get_equipment_group_ids_for_fuel_params_filters,
    get_equipment_groups_with_fuel_params_data,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_write_services import (
    sanitize_equipment_group_fuel_param_foreign_keys,
)
from app.refdata.models.fuels.fuel_model import Fuel


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


def _build_nust_changed_from_prev_year_keys(
    rows: list,
    *,
    start_year: int,
) -> frozenset[str]:
    """
    Ключи «{equipment_group_id}:{year_number}», где Руст (nust) в одной группе оборудования отличается
    от значения за предыдущий календарный год в пределах той же выборки (текущая версия БД в данных страницы).

    Пусто/0 и ненулевое значение — как в ячейках таблицы (см. render_numeric_or_dash).

    Строка за start_year не проверяется (нет года для сравнения в интервале фильтра).
    """
    if not rows:
        return frozenset()

    nust_by_eg_year: dict[int, dict[int, Any]] = defaultdict(dict)
    for eg, param in rows:
        if not eg or getattr(eg, "id", None) is None:
            continue
        yn = getattr(param, "year_number", None)
        if yn is None:
            continue
        eid = int(eg.id)
        nust_by_eg_year[eid][int(yn)] = getattr(param, "nust", None)

    changed: set[str] = set()
    for eg, param in rows:
        if not eg or getattr(eg, "id", None) is None:
            continue
        y = getattr(param, "year_number", None)
        if y is None:
            continue
        y = int(y)
        if y <= start_year:
            continue
        prev_y = y - 1
        eid = int(eg.id)
        prev_nust = nust_by_eg_year.get(eid, {}).get(prev_y)
        curr_nust = getattr(param, "nust", None)
        if _nust_changed_vs_previous(prev_nust, curr_nust):
            changed.add(f"{eid}:{y}")

    return frozenset(changed)


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

    Тепл. мощн. отборов (nt) при той же ветке: год строки = календарный год; из агрегатов группы
    берём те, у кого в этом году в MachinePower суммарно p_ust (Рust) ≠ 0; по MachineFuelParam.nt
    этих агрегатов сумма (по одному взносу на агрегат). Версия MFP: текущая или NULL. Иначе nt как у source.

    Поле nt_sum («Сумма NT») при расчёте nt по агрегатам выставляется равным этой же сумме — иначе после
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


def build_fuel_nazvl_to_name_map() -> dict[str, str]:
    """Подписи столбцов топлива по полю nazvl (как на странице основных параметров)."""
    fuel_query = filter_by_db_version(Fuel.query, Fuel)
    return {
        row.nazvl: (row.name[0].lower() + row.name[1:])
        if row.name and len(row.name) > 0
        else (row.name or "")
        for row in fuel_query.with_entities(Fuel.nazvl, Fuel.name)
        if row.nazvl and row.name
    }


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
    имён из formtxt на интервале лет; значения из EquipmentGroupExtraFuelParam (UGLI1) и
    из EquipmentGroupFuelParam (TOPLS|UGLI), согласно разбору формулы.
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
        extra_column_labels = {c: fuel_nazvl_labels.get(c, c) for c in extra_columns}
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


def get_fuel_calculation_edit_data_view_model(
    filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    rounding_digits: int,
) -> dict[str, Any]:
    """
    Контекст таблицы основных топливных параметров по фильтрам расчётного модуля.

    :param filters: результат extract_filters_from_args (без page или с ним — будет сброшен).
    """
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
    rows = fuel_data.get("rows") or []
    rows = _expand_fuel_param_rows_for_year_interval(rows, start_year, end_year)

    def _row_sort_key(item: tuple) -> tuple:
        eg, param = item
        y = getattr(param, "year_number", None) if param is not None else None
        name = (eg.name or "") if eg else ""
        name_ext = (eg.name_ext or "") if eg else ""
        eid = eg.id if eg else 0
        return ((name or "").lower(), (name_ext or "").lower(), eid, y or 0)

    rows = sorted(rows, key=_row_sort_key)

    bulk_edit_equipment_group_ids = sorted(
        {int(eg.id) for eg, _ in rows if eg is not None and getattr(eg, "id", None) is not None}
    )

    row_groups = _group_fuel_param_rows_by_equipment_group(rows)

    name_maps = build_name_maps_from_rows(rows)
    hierarchy = build_equipment_group_fuel_params_hierarchy(
        rows, use_equipment_group_hierarchy_only=False
    )
    fuel_nazvl_to_name = build_fuel_nazvl_to_name_map()

    return {
        "equipment_group_fuel_param_rows": rows,
        "equipment_group_fuel_param_row_groups": row_groups,
        "equipment_group_fuel_params_hierarchy": hierarchy,
        "nust_changed_from_prev_year_rows": _build_nust_changed_from_prev_year_keys(
            rows, start_year=start_year
        ),
        "total_count": len(rows),
        "fuel_nazvl_to_name": fuel_nazvl_to_name,
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


# Только показатели тепла, копируемые с базового года; nt задаётся в _apply_nust_nr_…
# (см. _sum_nt_for_machines_with_nonzero_p_ust_sum_in_year).
_HEAT_FUEL_PARAM_COPY_ATTRS: tuple[str, ...] = ("q", "qotr", "nt_sum", "turt")


def copy_heat_fuel_param_columns_for_filters(
    filters: dict[str, Any],
    *,
    filter_start_year: int,
    filter_end_year: int,
    source_year_number: int,
    target_year_numbers: list[int],
) -> tuple[int, int, int]:
    """
    Копирует q, qotr, nt_sum, turt с source_year_number на заданные календарные годы
    для всех групп оборудования по тем же фильтрам, что на странице.

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
    params_by_eg_year = _bulk_fuel_params_by_group_and_years(
        [int(x) for x in eg_ids], years_to_load, version_id
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
                setattr(target, key, getattr(source, key))

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
