#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Read/query/display для страницы «Удельные показатели групп оборудования».

Запись в EquipmentGroupSpecificFuelConsumption — в
equipment_group_specific_fuel_consumption_write_services.py
(пересчёт *_calc — в equipment_group_specific_fuel_consumption_recalc_services.py).
"""

from collections import defaultdict
from decimal import Decimal
from sqlalchemy import or_, and_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.equipment_groups.composite_display_cluster_services import (
    apply_simple_station_summaries,
    build_station_blocks_from_group_items,
)
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    resolve_composite_parents_by_numb,
    territorial_ids_for_equipment_group,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    normalize_equipment_group_ids_filter,
    restrict_equipment_group_query_to_current_version,
)

# Пары загруженное / расчётное для временного фильтра расхождений
CALC_MISMATCH_FIELD_PAIRS = (
    ("y", "y_calc"),
    ("btp", "btp_calc"),
    ("sntp", "sntp_calc"),
    ("bk", "bk_calc"),
    ("snk", "snk_calc"),
)

# Игнорировать микроразницу в 6–7-м знаке после запятой (округление Excel vs расчёт)
CALC_MISMATCH_ABS_TOLERANCE = Decimal("0.00001")


def _normalize_consumption_value(value):
    """NULL и 0 на экране оба показываются как «—» — считаем эквивалентными."""
    if value is None:
        return None
    try:
        as_dec = Decimal(str(value))
    except Exception:
        return value
    if as_dec == 0:
        return None
    return as_dec


def _numeric_values_differ(left, right) -> bool:
    """True, если значения различаются заметно (после нормализации NULL/0, |Δ| >= 1e-5)."""
    left_n = _normalize_consumption_value(left)
    right_n = _normalize_consumption_value(right)
    if left_n is None and right_n is None:
        return False
    if left_n is None or right_n is None:
        return True
    try:
        return abs(left_n - right_n) >= CALC_MISMATCH_ABS_TOLERANCE
    except Exception:
        return left_n != right_n


def consumption_has_calc_mismatch(param) -> bool:
    """Есть ли хотя бы одна пара поле / поле_calc с расхождением."""
    if param is None:
        return False
    for loaded_attr, calc_attr in CALC_MISMATCH_FIELD_PAIRS:
        if _numeric_values_differ(
            getattr(param, loaded_attr, None),
            getattr(param, calc_attr, None),
        ):
            return True
    return False


def get_calc_mismatch_attrs(param) -> set:
    """Атрибуты (и loaded, и _calc), у которых пара расходится."""
    mismatched = set()
    if param is None:
        return mismatched
    for loaded_attr, calc_attr in CALC_MISMATCH_FIELD_PAIRS:
        if _numeric_values_differ(
            getattr(param, loaded_attr, None),
            getattr(param, calc_attr, None),
        ):
            mismatched.add(loaded_attr)
            mismatched.add(calc_attr)
    return mismatched


SPECIFIC_FUEL_CONSUMPTION_COLUMNS = [
    ("name", "Наименование", False),
    ("year_number", "Year", False),
    ("k", "K", True),
    ("y", EquipmentGroupSpecificFuelConsumption.Y_COLUMN_LABEL, True),
    ("btp", EquipmentGroupSpecificFuelConsumption.BTP_COLUMN_LABEL, True),
    ("sntp", EquipmentGroupSpecificFuelConsumption.SNTP_COLUMN_LABEL, True),
    ("bk", EquipmentGroupSpecificFuelConsumption.BK_COLUMN_LABEL, True),
    ("numb1120", "Код группы оборудования", False),
    ("snk", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL, True),
    ("snbas", "SNBAS", True),
    ("ksn", "KSN", True),
    ("bbas", "BBAS", True),
    ("kh", "KH", True),
    ("y_calc", EquipmentGroupSpecificFuelConsumption.Y_COLUMN_LABEL, True),
    ("btp_calc", EquipmentGroupSpecificFuelConsumption.BTP_COLUMN_LABEL, True),
    ("sntp_calc", EquipmentGroupSpecificFuelConsumption.SNTP_COLUMN_LABEL, True),
    ("bk_calc", EquipmentGroupSpecificFuelConsumption.BK_COLUMN_LABEL, True),
    ("snk_calc", EquipmentGroupSpecificFuelConsumption.SNK_COLUMN_LABEL, True),
]

# Суммы в иерархии: все числовые колонки, кроме k (не суммируем)
SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS = [
    attr for attr, _, is_num in SPECIFIC_FUEL_CONSUMPTION_COLUMNS
    if is_num and attr != "k"
]


def overlay_snk_calc_from_fuel_params(rows) -> None:
    """
    В таблице удельных snk_calc = SNK топливных параметров
    (формула sn_ee / e · 100 или сохранённый FuelParam.snk).

    Только для реальных строк удельников. Год без записи (плейсхолдер
    интервала) не заполняем — иначе Seek-годы 2027–2031 показывают чужой SNK.

    Подставляет значение в загруженные строки без пометки session dirty.
    """
    from sqlalchemy.orm.attributes import set_committed_value

    from app.fuel.models.fue_equipment_group_fuel_param_model import (
        EquipmentGroupFuelParam,
    )
    from app.fuel.services.equipment_groups.equipment_group_specific_fuel_consumption_calc_services import (
        calc_snk_calc,
    )

    pairs = []
    for eg, cons in rows or []:
        # Пустой год интервала (нет строки удельников) — не подставляем SNK из ТЭП,
        # иначе 2027–2031 выглядят заполненными при Seek-логике без копирования.
        if not cons:
            continue
        gid = cons.equipment_group_id or (getattr(eg, "id", None) if eg else None)
        year = getattr(cons, "year_number", None)
        if gid is None or year is None:
            continue
        pairs.append((cons, int(gid), int(year)))
    if not pairs:
        return

    gids = {gid for _, gid, _ in pairs}
    years = {year for _, _, year in pairs}
    params = EquipmentGroupFuelParam.query.filter(
        EquipmentGroupFuelParam.equipment_group_id.in_(gids),
        EquipmentGroupFuelParam.year_number.in_(years),
    ).all()
    by_key = {
        (int(p.equipment_group_id), int(p.year_number)): p
        for p in params
        if p.equipment_group_id is not None and p.year_number is not None
    }
    for cons, gid, year in pairs:
        value = calc_snk_calc(by_key.get((gid, year)))
        try:
            set_committed_value(cons, "snk_calc", value)
        except Exception:
            try:
                cons.snk_calc = value
            except Exception:
                object.__setattr__(cons, "snk_calc", value)


def get_equipment_groups_with_specific_fuel_consumption_data(
    filters=None,
    per_page=25,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает позиции из EquipmentGroup с присоединением удельных показателей
    EquipmentGroupSpecificFuelConsumption.
    Возвращает rows: list[(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)].
    """
    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from sqlalchemy.orm import selectinload

    _start = start_year if start_year is not None else get_filter_start_year()
    _end = end_year if end_year is not None else get_filter_end_year()
    current_version_id = get_current_db_version_id()

    version_match = or_(
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupSpecificFuelConsumption.year_number >= _start,
        EquipmentGroupSpecificFuelConsumption.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)
        .outerjoin(EquipmentGroupSpecificFuelConsumption, join_cond)
    )

    territorial_keys = (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
    )
    _filters = {
        k: v
        for k, v in (filters or {}).items()
        if k not in ("page", "start_year", "end_year")
    }
    equipment_group_name_filter = (_filters.get("equipment_group_name_filter") or "").strip() or None
    id_list = normalize_equipment_group_ids_filter(_filters.get("equipment_group_ids"))
    base_query = restrict_equipment_group_query_to_current_version(
        base_query,
        current_version_id,
        skip=bool(id_list),
    )
    if id_list:
        base_query = base_query.filter(EquipmentGroup.id.in_(id_list))
    elif any(_filters.get(k) for k in territorial_keys) or equipment_group_name_filter:
        from app.fuel.services.stations.stations_equipment_groups_services import (
            get_filtered_equipment_group_ids,
            get_filtered_standalone_equipment_group_ids,
        )

        filtered_ids = (
            get_filtered_equipment_group_ids(
                _filters, start_year=_start, end_year=_end
            )
            | get_filtered_standalone_equipment_group_ids(
                _filters,
                version_id=current_version_id,
                strict_version=True,
            )
        )
        if filtered_ids:
            base_query = base_query.filter(EquipmentGroup.id.in_(filtered_ids))
        else:
            base_query = base_query.filter(
                EquipmentGroup.id != EquipmentGroup.id
            )

    total_count = base_query.count()

    rows = (
        base_query
        .options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
        )
        .order_by(EquipmentGroup.name, EquipmentGroup.name_ext, EquipmentGroup.id)
        .all()
    )

    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        apply_numb1120_filter_to_eg_param_rows,
    )

    rows, numb1120_filter_choices = apply_numb1120_filter_to_eg_param_rows(
        rows, _filters
    )
    total_count = len(rows)
    overlay_snk_calc_from_fuel_params(rows)

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
        "numb1120_filter_choices": numb1120_filter_choices,
    }


def build_equipment_group_specific_fuel_consumption_hierarchy(rows):
    """
    Строит иерархию: energy_system_type → UES → РЭС → станция → группа оборудования.
    """
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_systems_name_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_display_order_map,
        get_union_energy_systems_map,
        union_energy_system_hierarchy_sort_key,
    )
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        _equipment_group_station_sort_key,
        _get_equipment_group_station_mapping_with_display_order,
        should_suppress_fuel_params_station_summary_row,
    )

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    equipment_group_ids = [eg.id for eg, _ in (rows or []) if eg]
    _vid = get_current_db_version_id()
    parent_by_numb = resolve_composite_parents_by_numb(rows, database_version_id=_vid)
    eg_station_metadata = _get_equipment_group_station_mapping_with_display_order(
        equipment_group_ids, all_versions=True
    )
    eg_to_stations = {
        eg_id: [(st_id, st_name) for st_id, st_name, _ in stations]
        for eg_id, stations in (eg_station_metadata or {}).items()
    }
    eg_primary_display_orders = {
        eg_id: (stations[0][2] if stations else None)
        for eg_id, stations in (eg_station_metadata or {}).items()
    }

    hierarchy = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    for eg, param in rows or []:
        if not eg:
            continue
        _est, _ues, _res = territorial_ids_for_equipment_group(
            eg, parent_by_numb=parent_by_numb
        )
        hierarchy[_est][_ues][_res][eg.id].append((eg, param))

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return union_energy_system_hierarchy_sort_key(uid, ues_names, ues_display_orders)

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _compute_summary(rows_to_sum):
        from decimal import Decimal

        summary = {}
        for attr in SPECIFIC_FUEL_CONSUMPTION_SUMMARY_NUMERIC_ATTRS:
            total = Decimal(0)
            for _eg, param in rows_to_sum:
                val = getattr(param, attr, None)
                if val is not None:
                    try:
                        total += Decimal(str(val))
                    except (TypeError, ValueError):
                        pass
            summary[attr] = total
        return summary

    def _get_primary_station(eg_id):
        stations = eg_to_stations.get(eg_id, [])
        if not stations:
            return None
        st_id, st_name = stations[0]
        return (st_id, st_name or "—")

    def _station_sort_key(station_tuple):
        st_id, st_name = station_tuple or (None, "—")
        return (1 if st_id is None else 0, (st_name or "").lower(), st_id or 0)

    hierarchy_flat = []
    for est_id in sorted(hierarchy.keys(), key=_sort_key_est):
        ues_list = []
        for ues_id in sorted(hierarchy[est_id].keys(), key=_sort_key_ues):
            res_list = []
            for res_id in sorted(hierarchy[est_id][ues_id].keys(), key=_sort_key_res):
                all_res_rows = []
                eg_items = sorted(
                    hierarchy[est_id][ues_id][res_id].items(),
                    key=lambda item: _equipment_group_station_sort_key(
                        item,
                        eg_primary_display_orders,
                    ),
                )

                for _eg_id, eg_rows in eg_items:
                    all_res_rows.extend(eg_rows)

                res_summary = _compute_summary(all_res_rows) if all_res_rows else {}

                station_blocks = build_station_blocks_from_group_items(
                    eg_items,
                    eg_to_stations,
                    allow_station_composite_fallback=False,
                    should_suppress_summary=should_suppress_fuel_params_station_summary_row,
                    parent_by_numb=parent_by_numb,
                )
                apply_simple_station_summaries(
                    station_blocks,
                    _compute_summary,
                    parent_by_numb=parent_by_numb,
                )

                res_list.append(
                    {
                        "res_id": res_id,
                        "res_name": res_names.get(res_id, "—"),
                        "group_blocks": [
                            gb for sb in station_blocks for gb in sb["group_blocks"]
                        ],
                        "station_blocks": station_blocks,
                        "res_summary": res_summary,
                    }
                )
            ues_list.append(
                {
                    "ues_id": ues_id,
                    "ues_name": ues_names.get(ues_id, "—"),
                    "res_list": res_list,
                }
            )
        hierarchy_flat.append(
            {
                "est_id": est_id,
                "est_name": est_names.get(est_id, "—"),
                "ues_list": ues_list,
            }
        )

    return hierarchy_flat


def map_latest_specific_y_by_equipment_group_id(
    group_ids: list[int],
    target_year: int,
    *,
    effective_db_version_id: int | None = None,
) -> dict[int, object | None]:
    """
    Для каждой группы — поле ``y`` из строки удельных расходов с максимальным
    ``year_number`` ≤ ``target_year``.

    Условие присоединения к группе — как на странице
    ``stations_equipment_group_specific_fuel_consumption`` (``version_match`` между
    строкой удельных расходов и ``EquipmentGroup``), а не фильтр только по
    ``database_version_id`` самой строки: иначе строки с версией, совпадающей с группой,
    но отличной от «текущей» глобальной версии, не находились.
    """
    if not group_ids:
        return {}

    uniq_ids = list(dict.fromkeys(group_ids))
    current_version_id = (
        effective_db_version_id
        if effective_db_version_id is not None
        else get_current_db_version_id()
    )

    # Как join в get_equipment_groups_with_specific_fuel_consumption_data
    version_match = or_(
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id
            == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupSpecificFuelConsumption.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
        version_match,
    )

    q = (
        db.session.query(EquipmentGroup, EquipmentGroupSpecificFuelConsumption)
        .join(EquipmentGroupSpecificFuelConsumption, join_cond)
        .filter(EquipmentGroup.id.in_(uniq_ids))
    )
    if current_version_id is not None:
        q = q.filter(EquipmentGroup.database_version_id == current_version_id)
    else:
        q = q.filter(EquipmentGroup.database_version_id.is_(None))

    best: dict[int, tuple[int, EquipmentGroupSpecificFuelConsumption]] = {}
    for _eg, spec in q.all():
        gid = spec.equipment_group_id
        if gid is None:
            continue
        yr = spec.year_number if spec.year_number is not None else -10**9
        prev = best.get(gid)
        if prev is None or yr > prev[0]:
            best[gid] = (yr, spec)

    return {g: (best[g][1].y if g in best else None) for g in uniq_ids}
