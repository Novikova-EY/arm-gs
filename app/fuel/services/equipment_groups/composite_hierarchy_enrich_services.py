# -*- coding: utf-8 -*-
"""
Общий enrich station_blocks для витрин модуля «Топливо».

Эталон UX (stations_equipment_group_fuel_params):
  - родитель сверху, имя «…, всего», жёлтый фон;
  - дети ниже обычными строками;
  - отдельная жёлтая «станция, всего» не рисуется;
  - значения родителя = сумма детей (station_summary).

Составность только при наличии детей (main>0). Одиночный comp=1 без детей —
обычная строка.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from app.fuel.services.equipment_groups.composite_display_cluster_services import (
    _sort_group_blocks,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    _as_int,
    classify_station_groups,
    fuel_param_row_participates,
    is_composite_child_group,
    is_composite_parent_group,
    resolve_params_detail_level_for_year,
    should_edit_fuel_param_row,
    should_show_station_summary_for_detail_level,
)


def _res_has_id(res) -> bool:
    return res is not None and getattr(res, "id", None) is not None


def _res_from_obl_or_district(eg):
    """
    РЭС по obl → TerritoriesEnergyExternalMapping или по субъекту группы.

    Как на stations_equipment_groups: у части standalone-групп (Калининградская
    ГРЭС-2, ТЭЦ-1 и др.) obl заполнен, а regional_energy_system_id пуст — без
    этого они уходят в «Не указано» отдельно от остальных станций области.
    """
    if eg is None:
        return None
    from app.fuel.services.stations.stations_equipment_groups_services import (
        _rd_res_from_obl_mapping,
    )

    mapped_rd, mapped_res = _rd_res_from_obl_mapping(eg)
    res = mapped_res if _res_has_id(mapped_res) else None
    rd = getattr(eg, "regional_district", None) or mapped_rd
    if rd and getattr(rd, "regional_energy_systems", None):
        rd_res_list = list(rd.regional_energy_systems)
        if not rd_res_list:
            return res
        rd_res_ids = {r.id for r in rd_res_list}
        if not res or getattr(res, "id", None) not in rd_res_ids:
            res = sorted(rd_res_list, key=lambda item: item.id or 0)[0]
    return res


def _res_for_equipment_group_territory(eg):
    """РЭС группы: FK, иначе obl/субъект."""
    res = getattr(eg, "regional_energy_system", None) if eg is not None else None
    if _res_has_id(res):
        return res
    return _res_from_obl_or_district(eg)


def territorial_ids_for_equipment_group(
    eg,
    parent_by_numb: dict[int, Any] | None = None,
) -> tuple[int, int, int]:
    """
    EST / UES / RES для витрины топлива.

    Приоритет:
    1) РЭС самой группы (FK);
    2) obl-маппинг / субъект группы (standalone без FK, Калининград и др.);
    3) у дочерней составной без своего РЭС — территория родителя (main),
       иначе кластер рвётся: родитель в настоящей РЭС, а вторая копия имени —
       в «Не указано». Свою РЭС ребёнка не подменяем.
    """
    res = _res_for_equipment_group_territory(eg)
    if not _res_has_id(res) and is_composite_child_group(eg):
        main = _as_int(getattr(eg, "main", None))
        parent = (parent_by_numb or {}).get(main) if main is not None else None
        if parent is not None:
            res = _res_for_equipment_group_territory(parent)
    ues = getattr(res, "union_energy_system", None) if res else None
    est_id = getattr(ues, "id_energy_system_type", None) if ues else None
    ues_id = getattr(ues, "id", None) if ues else None
    res_id = getattr(res, "id", None) if res else None
    return (
        est_id if est_id is not None else -1,
        ues_id if ues_id is not None else -1,
        res_id if res_id is not None else -1,
    )


def resolve_composite_parents_by_numb(
    rows,
    database_version_id=None,
) -> dict[int, Any]:
    """
    Для детей с MAIN>0 подтягивает EG-родителей (comp=1 / numb=MAIN) из БД,
    даже если их нет в rows (оболочка без параметров).
    """
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup

    mains: set[int] = set()
    for eg, _param in rows or []:
        if eg is not None and is_composite_child_group(eg):
            main = _as_int(getattr(eg, "main", None))
            if main is not None:
                mains.add(main)
    if not mains:
        return {}

    from sqlalchemy.orm import selectinload

    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    q = EquipmentGroup.query.filter(EquipmentGroup.numb.in_(list(mains)))
    if database_version_id is not None:
        q = q.filter(
            (EquipmentGroup.database_version_id == database_version_id)
            | (EquipmentGroup.database_version_id.is_(None))
        )
    q = q.options(
        selectinload(EquipmentGroup.regional_energy_system).selectinload(
            RegionalEnergySystem.union_energy_system
        ),
        selectinload(EquipmentGroup.territories_energy_external_mapping),
        selectinload(EquipmentGroup.regional_district).selectinload(
            RegionalDistrict.regional_energy_systems
        ),
    )
    parents: dict[int, Any] = {}
    for eg in q.all():
        numb = _as_int(eg.numb)
        if numb is None:
            continue
        if is_composite_parent_group(eg) or (
            _as_int(getattr(eg, "main", None)) in (None, 0)
            and _as_int(getattr(eg, "comp", None)) == 1
        ):
            prev = parents.get(numb)
            if prev is None:
                parents[numb] = eg
            elif (
                getattr(eg, "database_version_id", None) == database_version_id
                and getattr(prev, "database_version_id", None) != database_version_id
            ):
                parents[numb] = eg
    return parents


def _default_rows_for_summary(group_blocks: list[dict]) -> list:
    """Все строки блока (страницы без FuelParam.ved)."""
    rows: list = []
    for gb in group_blocks:
        rows.extend(gb.get("rows") or [])
    return rows


def _fuel_param_rows_for_summary(group_blocks: list[dict]) -> list:
    """
    Строки для суммы станции:
    - при заполненном ved — только ved>0;
    - если у всех ved пуст (legacy) — все строки.
    """
    all_rows = _default_rows_for_summary(group_blocks)
    has_any_ved = any(
        param is not None and getattr(param, "ved", None) is not None
        for _eg, param in all_rows
    )
    if not has_any_ved:
        return all_rows
    return [
        (eg, param)
        for eg, param in all_rows
        if fuel_param_row_participates(param)
    ]


def enrich_station_blocks_composite_display(
    station_blocks: list[dict],
    compute_summary: Callable[[list], dict],
    *,
    parent_by_numb: dict[int, Any] | None = None,
    allow_station_composite_fallback: bool = False,
    rows_for_summary: Callable[[list], list] | None = None,
    fuel_params_detail_mode: bool = False,
) -> list[dict]:
    """
    Проставляет флаги составности и кладёт итог на строку родителя.

    fuel_params_detail_mode=True — режим ved / by_groups / edit_allowed
    (как на stations_equipment_group_fuel_params).
    Иначе «всего» на родителе, если в кластере есть хотя бы один ребёнок.
    """
    parent_by_numb = parent_by_numb or {}
    rows_for_summary = rows_for_summary or (
        _fuel_param_rows_for_summary
        if fuel_params_detail_mode
        else _default_rows_for_summary
    )

    for sb in station_blocks:
        gbs = list(sb.get("group_blocks") or [])
        egs = [gb.get("equipment_group") for gb in gbs]
        parent_eg, child_egs = classify_station_groups(egs)
        child_ids = {getattr(eg, "id", None) for eg in child_egs if eg is not None}
        parent_id = sb.get("composite_parent_eg_id")
        if parent_id is None and parent_eg is not None:
            parent_id = getattr(parent_eg, "id", None)

        has_children = bool(child_egs) or any(
            is_composite_child_group(eg) for eg in egs if eg is not None
        )
        treat_as_composite = bool(sb.get("treat_as_composite")) and has_children
        if not treat_as_composite:
            treat_as_composite = bool(
                has_children
                or (
                    allow_station_composite_fallback
                    and len(gbs) > 1
                    and not any(is_composite_parent_group(eg) for eg in egs if eg)
                )
            )
        # Одиночный comp=1 без детей — не составная витрина.
        if not has_children and not (
            allow_station_composite_fallback and len(gbs) > 1
        ):
            treat_as_composite = False

        has_composite_structure = treat_as_composite
        multi_groups = len(gbs) > 1
        sb["treat_as_composite"] = treat_as_composite

        years_detail: dict[int, str] = {}
        year_to_params: dict[int, list] = defaultdict(list)
        if fuel_params_detail_mode:
            for gb in gbs:
                eg = gb.get("equipment_group")
                for _eg, param in gb.get("rows") or []:
                    if param is None or getattr(param, "year_number", None) is None:
                        continue
                    year_to_params[int(param.year_number)].append((eg, param))

            for ynum, eg_params in year_to_params.items():
                parent_param = None
                child_params: list = []
                for eg, param in eg_params:
                    if parent_id is not None and getattr(eg, "id", None) == parent_id:
                        parent_param = param
                    elif getattr(eg, "id", None) in child_ids:
                        child_params.append(param)
                    elif is_composite_parent_group(eg):
                        parent_param = param
                    elif is_composite_child_group(eg):
                        child_params.append(param)
                    elif has_composite_structure and allow_station_composite_fallback:
                        child_params.append(param)
                if (
                    allow_station_composite_fallback
                    and parent_id is None
                    and multi_groups
                    and not child_params
                ):
                    child_params = [p for _eg, p in eg_params]
                    parent_param = None
                years_detail[ynum] = resolve_params_detail_level_for_year(
                    parent_param=parent_param,
                    child_params=child_params,
                )

        show_summary = False
        if fuel_params_detail_mode:
            for ynum, level in years_detail.items():
                participating = 0
                for eg, param in year_to_params.get(ynum, []):
                    if fuel_param_row_participates(param):
                        participating += 1
                    elif param is not None and getattr(param, "ved", None) is None:
                        participating += 1
                if should_show_station_summary_for_detail_level(
                    level, participating_group_count=participating
                ):
                    show_summary = True
                    break
            if (
                allow_station_composite_fallback
                and not years_detail
                and multi_groups
                and has_composite_structure
            ):
                show_summary = True
            if (
                allow_station_composite_fallback
                and has_composite_structure
                and multi_groups
                and not any(lvl == "station_only" for lvl in years_detail.values())
                and not any(lvl == "by_groups" for lvl in years_detail.values())
            ):
                show_summary = True
        else:
            # Витрины без ved: «всего» при реальных детях в кластере.
            show_summary = has_composite_structure and has_children

        summary_rows = rows_for_summary(gbs)
        summary_rows = [
            (eg, param)
            for eg, param in summary_rows
            if not (
                parent_id is not None and getattr(eg, "id", None) == parent_id
            )
            and not is_composite_parent_group(eg)
        ]
        station_summary = compute_summary(summary_rows) if summary_rows else {}
        # По годам отдельно — иначе на edit_data (много лет) в каждой строке
        # родителя «…, всего» показывается сумма детей сразу за все годы.
        station_summary_by_year: dict[int, dict] = {}
        rows_by_year: dict[int, list] = defaultdict(list)
        for eg, param in summary_rows:
            y = getattr(param, "year_number", None) if param is not None else None
            if y is None:
                continue
            rows_by_year[int(y)].append((eg, param))
        for ynum, y_rows in rows_by_year.items():
            station_summary_by_year[ynum] = compute_summary(y_rows) if y_rows else {}
        sb["station_summary"] = station_summary
        sb["station_summary_by_year"] = station_summary_by_year
        sb["has_composite_structure"] = has_composite_structure
        sb["composite_parent_eg_id"] = parent_id
        if fuel_params_detail_mode:
            sb["params_detail_level_by_year"] = years_detail

        if has_composite_structure:
            sb["suppress_station_summary"] = True
            parent_obj = parent_eg
            if parent_obj is None and parent_id is not None:
                for _n, peg in parent_by_numb.items():
                    if getattr(peg, "id", None) == parent_id:
                        parent_obj = peg
                        break
            if parent_obj is None:
                for n, peg in parent_by_numb.items():
                    if any(
                        is_composite_child_group(eg)
                        and _as_int(getattr(eg, "main", None)) == n
                        for eg in egs
                        if eg is not None
                    ):
                        parent_obj = peg
                        parent_id = getattr(peg, "id", None)
                        sb["composite_parent_eg_id"] = parent_id
                        break

            has_parent_gb = any(
                getattr(gb.get("equipment_group"), "id", None) == parent_id
                for gb in gbs
                if parent_id is not None
            )
            if parent_obj is not None and not has_parent_gb:
                years_for_total = sorted(year_to_params.keys()) if year_to_params else []
                if not years_for_total:
                    # Страницы без year_number на param — одна синтетическая строка.
                    child_years = []
                    for gb in gbs:
                        for _eg, param in gb.get("rows") or []:
                            y = getattr(param, "year_number", None) if param else None
                            if y is not None:
                                child_years.append(int(y))
                    years_for_total = sorted(set(child_years)) or [None]
                total_rows = [
                    (parent_obj, type("P", (), {"year_number": y, "ved": 0})())
                    for y in years_for_total
                ]
                gbs.append({"equipment_group": parent_obj, "rows": total_rows})
                egs = [gb.get("equipment_group") for gb in gbs]
                parent_eg, child_egs = classify_station_groups(egs)
                child_ids = {
                    getattr(eg, "id", None) for eg in child_egs if eg is not None
                }

            gbs = _sort_group_blocks(list(gbs))
            sb["group_blocks"] = gbs
        elif not has_composite_structure and multi_groups:
            sb["suppress_station_summary"] = True
        elif show_summary is False:
            sb["suppress_station_summary"] = True

        # Полоска/└ как на stations_equipment_groups — только если в блоке есть и родитель, и ребёнок.
        show_composite_cluster = bool(has_composite_structure and has_children)
        for gb in gbs:
            eg = gb.get("equipment_group")
            is_parent = bool(
                parent_id is not None and getattr(eg, "id", None) == parent_id
            ) or is_composite_parent_group(eg)
            gb["is_composite_parent"] = is_parent
            gb["is_composite_child"] = bool(
                getattr(eg, "id", None) in child_ids
            ) or is_composite_child_group(eg)
            gb["show_composite_cluster"] = show_composite_cluster
            gb["is_composite_total_row"] = bool(
                has_composite_structure and is_parent and show_summary
            )
            if gb["is_composite_total_row"]:
                gb["use_station_summary"] = True
                if fuel_params_detail_mode and not any(
                    param is not None
                    and getattr(param, "year_number", None) is not None
                    for _eg, param in (gb.get("rows") or [])
                ):
                    years_for_total = sorted(year_to_params.keys()) or [None]
                    gb["rows"] = [
                        (eg, type("P", (), {"year_number": y, "ved": 0})())
                        for y in years_for_total
                    ]
            if fuel_params_detail_mode:
                gb["edit_allowed_by_year"] = {}
                param_by_year: dict[int, Any] = {}
                for _eg, param in gb.get("rows") or []:
                    y = getattr(param, "year_number", None) if param is not None else None
                    if y is not None:
                        param_by_year[int(y)] = param
                years_for_edit = set(years_detail) | set(param_by_year)
                for ynum in years_for_edit:
                    if is_parent:
                        gb["edit_allowed_by_year"][ynum] = True
                    else:
                        gb["edit_allowed_by_year"][ynum] = should_edit_fuel_param_row(
                            detail_level=years_detail.get(ynum, "unknown"),
                            equipment_group=eg,
                            has_composite_structure=has_composite_structure,
                        )

    return station_blocks
