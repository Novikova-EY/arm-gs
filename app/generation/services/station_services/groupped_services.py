from app.extensions import db
from decimal import Decimal
from sqlalchemy import func
from collections import defaultdict
from sqlalchemy.orm import joinedload
from app.logs.models.logs_models import *
from app.refdata.models.energy_systems_models import *
from app.refdata.models.territories_models import *
from app.refdata.models.fuels_models import *
from app.refdata.models.gen_companies_models import *
from app.refdata.models.stations_refdata_models import *
from app.generation.models.stations_models import *
from app.generation.models.machines_models import *
from app.generation.models.pgu_machines_models import *
from app.generation.models.boilers_models import *

def get_station_hierarchy_aggregates(start_year, end_year):
    return (
        db.session.query(
            Station.id_energy_unit.label("energy_unit_id"),
            RegionalDistrict.id.label("regional_district_id"),
            RegionalEnergySystem.id.label("regional_energy_system_id"),
            UnionEnergySystem.id.label("union_energy_system_id"),
            EnergySystemType.id.label("energy_system_type_id"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Station.regional_district)
        .join(RegionalDistrict.regional_energy_systems)
        .join(RegionalEnergySystem.union_energy_system)
        .join(UnionEnergySystem.energy_system_type)
        .join(Machine, Machine.id_station == Station.id)
        .join(MachinePower, MachinePower.id_machine == Machine.id)
        .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
        .group_by(
            Station.id_energy_unit,
            RegionalDistrict.id,
            RegionalEnergySystem.id,
            UnionEnergySystem.id,
            EnergySystemType.id,
            MachinePower.year_number
        )
        .all()
    )


def build_hierarchy_structure(stations: list[Station], include_names=False):
    # Многоуровневая вложенность
    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    # Для имен
    est_names = {}
    ues_names = {}
    res_names = {}
    rd_names = {}
    eu_names = {}

    for station in stations:
        # Проверка наличия регионального округа и региональной энергосистемы
        if not station.regional_district or not station.regional_district.regional_energy_systems:
            continue

        for res in station.regional_district.regional_energy_systems:
            ues = res.union_energy_system
            if not ues:
                continue

            est_id = ues.id_energy_system_type
            ues_id = ues.id
            res_id = res.id
            rd_id = station.id_regional_district

            # Важно: проверяем наличие энергоузла
            if station.id_energy_unit is not None:
                eu_id = station.id_energy_unit
                eu_name = station.energy_unit.name if station.energy_unit else 100
            else:
                eu_id = 100
                eu_name = "без энергоузла"

            # Добавляем станцию в иерархию
            grouped_data[est_id][ues_id][res_id][rd_id][eu_id].append(station)

            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name
                res_names[res_id] = res.name
                rd_names[rd_id] = station.regional_district.name
                eu_names[eu_id] = eu_name

    result = {
        "grouped_stations": grouped_data,
        "stations": stations,
    }

    if include_names:
        result.update({
            "energy_system_type_name": est_names,
            "union_energy_system_name": ues_names,
            "regional_energy_system_name": res_names,
            "regional_district_name": rd_names,
            "energy_unit_name": eu_names,
        })

    return result


def fetch_machines_with_rowspans(station_ids: list[int], show_p_ogr=False, show_p_rasp=False):
    machines = Machine.query.options(
        joinedload(Machine.station_type),
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    ).filter(Machine.id_station.in_(station_ids)).all()

    machine_ids = [m.id for m in machines]
    pgu_machines = PGUMachine.query.filter(PGUMachine.id_parent_machine.in_(machine_ids)).all()

    pgu_machine_ids = [p.id for p in pgu_machines]
    pgu_powers = PGUMachinePower.query.filter(PGUMachinePower.id_pgu_machine.in_(pgu_machine_ids)).all()

    pgu_powers_map = defaultdict(dict)
    for power in pgu_powers:
        pgu_powers_map[power.id_pgu_machine][power.year_number] = power.p_ust or 0

    pgu_map = defaultdict(list)
    for pgu in pgu_machines:
        pgu.powers_by_year = pgu_powers_map.get(pgu.id, {})
        pgu_map[pgu.id_parent_machine].append(pgu)

    station_machine_map = defaultdict(list)
    station_totals = {}

    for m in machines:
        m.pgu_machines = pgu_map.get(m.id, [])
        station_machine_map[m.id_station].append(m)

    for station_id, machine_list in station_machine_map.items():
        machine_list.sort(key=lambda m: (
            (m.machine_group or '').lower(),
            (m.fuel_so or '').lower(),
            int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf')
        ))

        group_dict = defaultdict(list)
        for m in machine_list:
            group_key = (m.machine_group or '').strip()
            group_dict[group_key].append(m)

        for group in group_dict.values():
            group_rowspan = 0
            for m in group:
                num_pgu = len(m.pgu_machines)
                base_rows = 1 + num_pgu
                if show_p_ogr:
                    base_rows += 1
                if show_p_rasp:
                    base_rows += 1
                m.total_rows = base_rows
                group_rowspan += base_rows

            group[0].group_rowspan = group_rowspan
            for m in group[1:]:
                m.group_rowspan = 0

        fuel_dict = defaultdict(list)
        for m in machine_list:
            fuel_key = (m.fuel_so or '').strip()
            fuel_dict[fuel_key].append(m)

        for group in fuel_dict.values():
            fuel_rowspan = sum(m.total_rows for m in group)
            group[0].fuel_rowspan = fuel_rowspan
            for m in group[1:]:
                m.fuel_rowspan = 0

        # station total rows = sum total_rows of all machines + header row (1)
        station_total_rows = sum(m.total_rows for m in machine_list) + 1
        station_machine_count = len(machine_list)
        station_total_pgu_count = sum(len(m.pgu_machines) for m in machine_list)

        # Calculate summary row height: 1 (Руст) + optional p_ogr + optional p_rasp
        station_summary_rows = 1
        if show_p_ogr:
            station_summary_rows += 1
        if show_p_rasp:
            station_summary_rows += 1

        station_totals[station_id] = {
            'total_rows': station_total_rows,
            'machine_count': station_machine_count,
            'total_pgu_count': station_total_pgu_count,
            'summary_rows': station_summary_rows
        }

    all_machines = []
    for lst in station_machine_map.values():
        all_machines.extend(lst)

    for m in all_machines:
        if not hasattr(m, 'group_rowspan') or m.group_rowspan is None:
            m.group_rowspan = 1
        if not hasattr(m, 'fuel_rowspan') or m.fuel_rowspan is None:
            m.fuel_rowspan = 1

    return all_machines, station_totals
