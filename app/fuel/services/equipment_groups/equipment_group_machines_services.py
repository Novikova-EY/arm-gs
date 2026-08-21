# -*- coding: utf-8 -*-
"""Сервис для получения агрегатов (machines) по группе оборудования."""

from collections import defaultdict
from decimal import Decimal
from typing import List, Tuple, Optional

from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_

from app.extensions import db
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.refdata.models.fuels.fuel_model import Fuel
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.services.station_services.station_services import _apply_machine_display_names
from app.generation.services.station_services.station_power_aggregation import (
    aggregate_powers_from_machine_power_rows,
)
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)


def resolve_equipment_group_ids_for_machines(
    equipment_group,
    member_equipment_groups: Optional[List[dict]] = None,
) -> List[int]:
    """
    Для составной станции (comp=1) агрегаты берутся из самой группы и из дочерних
    (MAIN=parent.NUMB): иначе агрегаты, ещё висящие на родителе, пропадают с карточки.
    """
    from app.fuel.services.equipment_groups.composite_station_semantics import (
        _as_int,
    )

    if equipment_group is None:
        return []
    ids = [int(equipment_group.id)]
    members = member_equipment_groups or []
    if _as_int(getattr(equipment_group, "comp", None)) == 1 and members:
        for item in members:
            child = item.get("equipment_group") if isinstance(item, dict) else None
            child_id = getattr(child, "id", None)
            if child_id is not None:
                ids.append(int(child_id))
    return list(dict.fromkeys(ids))


def get_equipment_group_machines_data(
    equipment_group_id: int | List[int],
    start_year: int,
    end_year: int,
    version_id: Optional[int] = None,
) -> List[Tuple["Station", List["Machine"]]]:
    """
    Возвращает список (station, machines) для агрегатов, входящих в группу оборудования.

    Связь: EquipmentGroupSet (equipment_group_id) -> EquipmentGroupSetStation (station_id, equipment_group_type_id).
    Machine.id_station = station_id, Machine.id_equipment_group = equipment_group_type_id.

    equipment_group_id — одна группа или список (для составной станции: дочерние
    группы с MAIN=parent.NUMB).

    Returns:
        Список кортежей (station, machines), где machines отсортированы по станционному номеру.
    """
    if version_id is None:
        version_id = get_current_db_version_id()

    if isinstance(equipment_group_id, (list, tuple, set)):
        eg_ids = [int(x) for x in equipment_group_id if x is not None]
    else:
        eg_ids = [int(equipment_group_id)] if equipment_group_id is not None else []
    # Сохраняем порядок, убираем дубли
    eg_ids = list(dict.fromkeys(eg_ids))
    if not eg_ids:
        return []

    # Получаем пары (station_id, equipment_group_type_id) из связей группы(групп)
    pairs = set()
    sets_q = EquipmentGroupSet.query.filter(
        EquipmentGroupSet.equipment_group_id.in_(eg_ids)
    ).all()
    for s in sets_q:
        link = EquipmentGroupSetStation.query.get(s.equipment_group_set_station_id)
        if link:
            pairs.add((link.station_id, link.equipment_group_type_id))

    if not pairs:
        return []

    # Собираем machine_ids по парам
    station_type_pairs = list(pairs)
    machines_q = (
        db.session.query(Machine)
        .options(
            joinedload(Machine.gen_company),
            joinedload(Machine.tes_machine_type),
            joinedload(Machine.equipment_group),
            joinedload(Machine.machine_fuel_param),
        )
        .filter(
            and_(
                Machine.id_station.isnot(None),
                Machine.id_equipment_group.isnot(None),
            )
        )
    )
    machines_q = filter_by_explicit_db_version(machines_q, Machine, version_id)

    # Фильтр по парам (station_id, equipment_group_type_id)
    or_conds = [
        and_(Machine.id_station == sid, Machine.id_equipment_group == tid)
        for sid, tid in station_type_pairs
    ]
    machines_q = (
        machines_q
        .outerjoin(MachineFuelParam, MachineFuelParam.machine_id == Machine.id)
        .filter(or_(*or_conds))
        .filter(
            or_(
                MachineFuelParam.equipment_group_id.in_(eg_ids),
                MachineFuelParam.equipment_group_id.is_(None),
            )
        )
    )
    all_machines = machines_q.all()

    # Группируем по station_id
    machines_by_station = defaultdict(list)
    for m in all_machines:
        if m.id_station:
            machines_by_station[m.id_station].append(m)

    # Загружаем электростанции
    station_ids = list(machines_by_station.keys())
    stations = (
        db.session.query(Station)
        .options(joinedload(Station.station_type))
        .filter(Station.id.in_(station_ids))
        .all()
    )
    station_map = {s.id: s for s in stations}

    # Загружаем мощности и топливо для всех машин
    machine_ids = [m.id for m in all_machines]
    powers_by_machine_year = {}
    fuels_by_machine_year = {}
    pgu_by_parent = defaultdict(list)

    if machine_ids:
        mp_query = (
            db.session.query(MachinePower)
            .filter(MachinePower.id_machine.in_(machine_ids))
            .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
        )
        mp_query = filter_by_explicit_db_version(mp_query, MachinePower, version_id)
        for mp in mp_query.all():
            powers_by_machine_year.setdefault(mp.id_machine, {})[mp.year_number] = mp

        mf_query = (
            db.session.query(MachineFuel)
            .options(joinedload(MachineFuel.fuel).joinedload(Fuel.fuel_type))
            .filter(MachineFuel.id_machine.in_(machine_ids))
            .filter(MachineFuel.year_number >= start_year, MachineFuel.year_number <= end_year)
        )
        mf_query = filter_by_explicit_db_version(mf_query, MachineFuel, version_id)
        for mf in mf_query.all():
            fuels_by_machine_year.setdefault(mf.id_machine, {})[mf.year_number] = mf

        # PGU
        pgu_query = (
            db.session.query(PGUMachine)
            .options(
                joinedload(PGUMachine.tes_machine_type),
                joinedload(PGUMachine.pgu_tes_machine_type),
            )
            .filter(PGUMachine.id_parent_machine.in_(machine_ids))
        )
        pgu_query = filter_by_explicit_db_version(pgu_query, PGUMachine, version_id)
        pgu_list = pgu_query.all()
        pgu_ids = [p.id for p in pgu_list]
        pgu_powers_by_year = {}
        if pgu_ids:
            pp_query = (
                db.session.query(PGUMachinePower)
                .filter(PGUMachinePower.id_pgu_machine.in_(pgu_ids))
                .filter(PGUMachinePower.year_number >= start_year, PGUMachinePower.year_number <= end_year)
            )
            pp_query = filter_by_explicit_db_version(pp_query, PGUMachinePower, version_id)
            for pp in pp_query.all():
                pgu_powers_by_year.setdefault(pp.id_pgu_machine, {})[pp.year_number] = pp
        for p in pgu_list:
            p.powers_by_year = pgu_powers_by_year.get(p.id, {})
            pgu_by_parent[p.id_parent_machine].append(p)

    # Сортируем машины по станционному номеру
    def _machine_sort_key(m):
        num_key = float("inf")
        try:
            if m.machine_number:
                s = str(m.machine_number).strip()
                if s.isdigit():
                    num_key = int(s)
        except Exception:
            pass
        return num_key

    result = []
    for station_id in sorted(machines_by_station.keys()):
        station = station_map.get(station_id)
        if not station:
            continue
        machines = machines_by_station[station_id]
        machines.sort(key=_machine_sort_key)

        _apply_machine_display_names(machines)

        # Прикрепляем данные к машинам и считаем итоги по электростанции
        station_nt_sum = Decimal(0)
        for m in machines:
            m.machine_powers = list((powers_by_machine_year.get(m.id, {}) or {}).values())
            m.machine_fuels = list((fuels_by_machine_year.get(m.id, {}) or {}).values())
            m.pgu_machines = pgu_by_parent.get(m.id, [])
            m.base_rows = 1 + len(m.pgu_machines)

            mfp = getattr(m, "machine_fuel_param", None)
            if mfp and mfp.nt is not None:
                station_nt_sum += Decimal(str(mfp.nt))

        all_machine_powers = []
        for m in machines:
            all_machine_powers.extend(m.machine_powers)
        station.powers_by_year = aggregate_powers_from_machine_power_rows(
            all_machine_powers,
            start_year=start_year,
            end_year=end_year,
        )
        station.machines_nt_sum = station_nt_sum
        station.machines = machines
        result.append((station, machines))

    return result
