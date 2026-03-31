#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сервисы для страницы «Цена для групп оборудования»."""

from collections import defaultdict
from sqlalchemy import or_, and_

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.services.equipment_group_specific_fuel_price_calc_services import (
    calc_specific_fuel_price_fields,
)


# Базовые колонки (без _calc) — из них строим пары: (xxx_c, xxx_c_calc)
_SPECIFIC_FUEL_PRICE_BASE = [
    ("name", "NAME", False),
    ("year_number", "Year", False),
    ("obl", "OBL", False),
    ("gaz_c", "ГАЗ, всего", True),
    ("gazpp_c", "gazpp_c", True),
    ("gaz_prir_c", "gaz_prir_c", True),
    ("mazut_c", "МАЗУТ, всего", True),
    ("disel_c", "disel_c", True),
    ("maztop_c", "maztop_c", True),
    ("gtt_c", "Газотурбинное топливо", True),
    ("nft_proch_c", "nft_proch_c", True),
    ("torf_c", "TORF_c", True),
    ("isk_gaz_c", "ISK_GAZ_c", True),
    ("domen_g_c", "domen_g_c", True),
    ("koks_g_c", "koks_g_c", True),
    ("prochgaz_c", "prochgaz_c", True),
    ("proch_c", "ПРОЧЕЕ, всего", True),
    ("tvproch_c", "tvproch_c", True),
    ("szh_gaz_c", "szh_gaz_c", True),
    ("inoe_c", "inoe_c", True),
    ("don_c", "DON_c", True),
    ("podm_c", "PODM_c", True),
    ("pech_c", "PECH_c", True),
    ("vork_c", "vork_c", True),
    ("intin_c", "intin_c", True),
    ("kuzn_c", "KUZN_c", True),
    ("kuzngd_c", "kuzngd_c", True),
    ("kuznt_c", "kuznt_c", True),
    ("kuznss_c", "kuznss_c", True),
    ("kuznun_c", "kuznun_c", True),
    ("ural_c", "URAL_c", True),
    ("sver_c", "sver_c", True),
    ("chel_c", "chel_c", True),
    ("kizel_c", "kizel_c", True),
    ("bashk_c", "BASHK_c", True),
    ("kazah_c", "KAZAH_c", True),
    ("ekib_c", "ekib_c", True),
    ("maikub_c", "maikub_c", True),
    ("karag_c", "karag_c", True),
    ("karajyra_c", "karajyra_c", True),
    ("teniz_c", "teniz_c", True),
    ("kan_c", "KAN_c", True),
    ("nazar_c", "nazar_c", True),
    ("ibor_c", "ibor_c", True),
    ("berez_c", "berez_c", True),
    ("per_c", "per_c", True),
    ("irbei_c", "irbei_c", True),
    ("kansk_c", "kansk_c", True),
    ("irkut_c", "IRKUT_c", True),
    ("azey_c", "azey_c", True),
    ("mug_c", "mug_c", True),
    ("cher_c", "cher_c", True),
    ("tung_c", "TUNG_c", True),
    ("jer_c", "jer_c", True),
    ("karab_c", "karab_c", True),
    ("hak_c", "HAK_c", True),
    ("tuv_c", "TUV_c", True),
    ("bur_c", "BUR_c", True),
    ("gusin_c", "gusin_c", True),
    ("tugn_c", "tugn_c", True),
    ("okino_c", "okino_c", True),
    ("chit_c", "CHIT_c", True),
    ("har_c", "har_c", True),
    ("urt_c", "urt_c", True),
    ("tataur_c", "tataur_c", True),
    ("tarbag_c", "tarbag_c", True),
    ("zab_kam_c", "zab_kam_c", True),
    ("amur_c", "AMUR_c", True),
    ("rai_c", "rai_c", True),
    ("erk_c", "erk_c", True),
    ("ogodj_c", "ogodj_c", True),
    ("svo_c", "svo_c", True),
    ("urg_c", "URG_c", True),
    ("ushum_c", "USHUM_c", True),
    ("prim_c", "PRIM_c", True),
    ("bikin_c", "bikin_c", True),
    ("razdol_c", "razdol_c", True),
    ("hankai_c", "hankai_c", True),
    ("yakut_c", "YAKUT_c", True),
    ("neru_c", "neru_c", True),
    ("zyryan_c", "zyryan_c", True),
    ("pyak_c", "pyak_c", True),
    ("mag_c", "MAG_c", True),
    ("chukot_c", "CHUKOT_c", True),
    ("anad_c", "anad_c", True),
    ("bering_c", "bering_c", True),
    ("kamch_c", "KAMCH_c", True),
    ("sah_c", "SAH_c", True),
    ("numb1120", "Код станции", False),
    ("sost", "sost", False),
    ("group", "group", False),
]

# Колонки с парами: xxx_c (из БД/Excel) и xxx_c_calc (расчётные)
SPECIFIC_FUEL_PRICE_COLUMNS = []
for attr, label, is_numeric in _SPECIFIC_FUEL_PRICE_BASE:
    SPECIFIC_FUEL_PRICE_COLUMNS.append((attr, label, is_numeric))
    if is_numeric and attr.endswith("_c"):
        SPECIFIC_FUEL_PRICE_COLUMNS.append((f"{attr}_calc", f"{label} (расчёт)", True))

# Формулы для _calc столбцов (tooltip).
# get_price_formulas(fuel_nazvl_to_name) — подставляет имена из Fuel.name
def get_price_formulas(fuel_nazvl_to_name=None):
    """Возвращает формулы с подстановкой имён топлива из Fuel.name (nazvl -> name)."""
    nazvl_to_name = fuel_nazvl_to_name or {}
    result = {}
    for attr, label, is_numeric in _SPECIFIC_FUEL_PRICE_BASE:
        if is_numeric and attr.endswith("_c"):
            base = attr[:-2]  # gaz_c -> gaz
            fuel_name = nazvl_to_name.get(base, base)
            result[f"{attr}_calc"] = f"{attr} = стоимость.{fuel_name} / объём топлива"
    return result


# Дефолтные формулы (без Fuel) — для обратной совместимости
PRICE_FORMULAS = get_price_formulas()


def _apply_calculated_specific_fuel_prices(rows):
    """
    Вычисляет xxx_c по формулам и сохраняет в param._price_calc.
    Исходные значения из БД/Excel не перезаписываются.
    """
    from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
        EquipmentGroupExtraFuelParam,
    )
    from app.fuel.models.fue_equipment_group_fuel_param_model import (
        EquipmentGroupFuelParam,
    )
    from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
        EquipmentGroupSpecificFuelCost,
    )

    pairs = [
        (eg.id, param.year_number)
        for eg, param in (rows or [])
        if eg and param and param.year_number is not None
    ]
    if not pairs:
        return

    eg_ids = {p[0] for p in pairs}
    years = {p[1] for p in pairs}

    fuel_params = {
        (r.equipment_group_id, r.year_number): r
        for r in EquipmentGroupFuelParam.query.filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(eg_ids),
            EquipmentGroupFuelParam.year_number.in_(years),
        ).all()
    }
    extra_params = {
        (r.equipment_group_id, r.year_number): r
        for r in EquipmentGroupExtraFuelParam.query.filter(
            EquipmentGroupExtraFuelParam.equipment_group_id.in_(eg_ids),
            EquipmentGroupExtraFuelParam.year_number.in_(years),
        ).all()
    }
    costs = {
        (r.equipment_group_id, r.year_number): r
        for r in EquipmentGroupSpecificFuelCost.query.filter(
            EquipmentGroupSpecificFuelCost.equipment_group_id.in_(eg_ids),
            EquipmentGroupSpecificFuelCost.year_number.in_(years),
        ).all()
    }

    for eg, param in rows or []:
        if not eg or not param or param.year_number is None:
            continue
        key = (eg.id, param.year_number)
        fuel_param = fuel_params.get(key)
        extra_param = extra_params.get(key)
        cost = costs.get(key)
        param._price_calc = calc_specific_fuel_price_fields(
            fuel_param, extra_param, cost
        )


def get_equipment_groups_with_specific_fuel_price_data(
    filters=None,
    per_page=10,
    page=1,
    start_year=None,
    end_year=None,
    show_all=False,
):
    """
    Выбирает позиции из EquipmentGroup с присоединением цены
    EquipmentGroupSpecificFuelPrice.
    Возвращает rows: list[(EquipmentGroup, EquipmentGroupSpecificFuelPrice)].
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
            EquipmentGroupSpecificFuelPrice.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupSpecificFuelPrice.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupSpecificFuelPrice.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupSpecificFuelPrice.year_number >= _start,
        EquipmentGroupSpecificFuelPrice.year_number <= _end,
        version_match,
    )

    base_query = (
        db.session.query(EquipmentGroup, EquipmentGroupSpecificFuelPrice)
        .outerjoin(EquipmentGroupSpecificFuelPrice, join_cond)
    )

    if hasattr(EquipmentGroup, "database_version_id"):
        if current_version_id is not None:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id == current_version_id
            )
        else:
            base_query = base_query.filter(
                EquipmentGroup.database_version_id.is_(None)
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
    if any(_filters.get(k) for k in territorial_keys) or equipment_group_name_filter:
        from app.fuel.services.stations_equipment_groups_services import (
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

    _apply_calculated_specific_fuel_prices(rows)

    return {
        "rows": rows,
        "total_count": total_count,
        "total_pages": 1,
        "page": 1,
        "per_page": total_count or 1,
    }


def build_equipment_group_specific_fuel_price_hierarchy(rows):
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
        get_union_energy_systems_map,
    )
    from app.fuel.services.equipment_group_fuel_params_services import (
        _get_equipment_group_station_mapping,
    )

    est_names = dict(get_energy_system_type_map())
    ues_names = dict(get_union_energy_systems_map())
    res_names = dict(get_regional_energy_systems_name_map())
    est_names[-1] = "Не указано"
    ues_names[-1] = "Не указано"
    res_names[-1] = "Не указано"

    equipment_group_ids = [eg.id for eg, _ in (rows or []) if eg]
    eg_to_stations = _get_equipment_group_station_mapping(
        equipment_group_ids, all_versions=True
    )

    hierarchy = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    for eg, param in rows or []:
        if not eg:
            continue
        res = getattr(eg, "regional_energy_system", None)
        ues = getattr(res, "union_energy_system", None) if res else None
        est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        ues_id = ues.id if ues else None
        res_id = res.id if res else None

        _est = est_id if est_id is not None else -1
        _ues = ues_id if ues_id is not None else -1
        _res = res_id if res_id is not None else -1

        hierarchy[_est][_ues][_res][eg.id].append((eg, param))

    def _sort_key_est(eid):
        return (1 if eid == -1 else 0, est_names.get(eid, ""))

    def _sort_key_ues(uid):
        return (1 if uid == -1 else 0, ues_names.get(uid, ""))

    def _sort_key_res(rid):
        return (1 if rid == -1 else 0, res_names.get(rid, ""))

    def _eg_sort_key(item):
        eg_id, eg_rows = item
        eg = eg_rows[0][0] if eg_rows else None
        name = (eg.name or eg.name_ext or "") if eg else ""
        return (0, (name or "").lower(), eg_id or 0)

    NUMERIC_ATTRS = [attr for attr, _label, is_num in SPECIFIC_FUEL_PRICE_COLUMNS if is_num]

    def _compute_summary(rows_to_sum):
        from decimal import Decimal

        summary = {}
        for attr in NUMERIC_ATTRS:
            total = Decimal(0)
            for _eg, param in rows_to_sum:
                if param is None:
                    continue
                if attr.endswith("_calc"):
                    price_calc = getattr(param, "_price_calc", None) or {}
                    base_attr = attr[:-5]  # gaz_c_calc -> gaz_c
                    val = price_calc.get(base_attr)
                else:
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
                    hierarchy[est_id][ues_id][res_id].items(), key=_eg_sort_key
                )

                by_station = defaultdict(list)
                for eg_id, eg_rows in eg_items:
                    all_res_rows.extend(eg_rows)
                    eg = eg_rows[0][0] if eg_rows else None
                    station_key = _get_primary_station(eg_id)
                    by_station[station_key].append(
                        {"equipment_group": eg, "rows": eg_rows}
                    )

                res_summary = _compute_summary(all_res_rows) if all_res_rows else {}

                station_blocks = []
                for station_key in sorted(by_station.keys(), key=_station_sort_key):
                    group_blocks = by_station[station_key]
                    station_rows = []
                    for gb in group_blocks:
                        station_rows.extend(gb["rows"])
                    station_summary = (
                        _compute_summary(station_rows) if station_rows else {}
                    )
                    st_id, st_name = station_key if station_key else (None, "—")
                    station_blocks.append(
                        {
                            "station_id": st_id,
                            "station_name": st_name,
                            "group_blocks": group_blocks,
                            "station_summary": station_summary,
                            "is_virtual": False,
                        }
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
