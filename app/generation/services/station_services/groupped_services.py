from app.extensions import db
from decimal import Decimal
from sqlalchemy import func, or_, and_
from collections import defaultdict
from sqlalchemy.orm import joinedload, selectinload
import re
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.refdata.models.fuels.fuel_model import Fuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.years.year_model import Year
from app.common.services.database_version_filter import filter_by_db_version, get_current_db_version_id
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.services.station_services.filters_services import (
    build_machine_note_search_condition,
)


def is_current_version(entity) -> bool:
    """Checks if entity matches current DB version or is common (NULL)."""
    current_version_id = get_current_db_version_id()
    if entity is None:
        return False
    if not hasattr(entity, 'database_version_id'):
        return True
    return (entity.database_version_id is None) or (entity.database_version_id == current_version_id)


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
    
    # Проверка на дубликаты станций
    station_ids_seen = {}
    duplicates = []
    for station in stations:
        if station.id in station_ids_seen:
            duplicates.append(f"Station ID {station.id} ({station.name}) - duplicate")
        station_ids_seen[station.id] = station
    
    if duplicates:
        print(f"[WARNING] Обнаружены дубликаты станций в списке:")
        for dup in duplicates:
            print(f"  - {dup}")
    
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
    
    # Используем set для отслеживания уже добавленных станций
    added_stations = set()
    processed_count = 0
    skipped_count = 0
    skipped_no_rd_or_res = 0
    skipped_no_ues = 0
    skipped_duplicates = 0

    for station in stations:
        processed_count += 1
        
        # Проверка наличия регионального округа
        if not station.regional_district:
            print(f"[DEBUG] Станция {station.id} ({station.name}): нет regional_district")
            skipped_count += 1
            skipped_no_rd_or_res += 1
            continue

        # ----- Определяем РЭС и ОЭС -----
        res = None

        # 1) Приоритет: прямая связь станции с РЭС (Station.id_regional_energy_system)
        if getattr(station, "id_regional_energy_system", None):
            direct_res = getattr(station, "regional_energy_system_obj", None)
            if direct_res and is_current_version(direct_res):
                res = direct_res

        # 2) Fallback: через субъект РФ (старое поведение)
        if res is None:
            rd_res_list = [
                r for r in (station.regional_district.regional_energy_systems or [])
                if is_current_version(r)
            ]
            if not rd_res_list:
                print(
                    f"[DEBUG] Станция {station.id} ({station.name}): "
                    f"нет regional_energy_systems в regional_district {station.regional_district.id}"
                )
                skipped_count += 1
                skipped_no_rd_or_res += 1
                continue

            # Берем первую РЭС текущей версии, у которой есть ОЭС текущей версии; иначе первую подходящую
            for r in rd_res_list:
                u = getattr(r, "union_energy_system", None)
                if u and is_current_version(u):
                    res = r
                    break
            if res is None:
                # нет РЭС с валидной ОЭС — берем первую по версии, даже если у нее нет ОЭС (будет пропуск)
                res = rd_res_list[0]

        ues = getattr(res, 'union_energy_system', None)
        if not ues:
            print(f"[DEBUG] Станция {station.id} ({station.name}): нет union_energy_system в РЭС {res.id}")
            skipped_count += 1
            skipped_no_ues += 1
            continue
        
        if not is_current_version(ues):
            print(f"[DEBUG] Станция {station.id} ({station.name}): union_energy_system {ues.id} не текущей версии (версия БД: {ues.database_version_id})")
            skipped_count += 1
            skipped_no_ues += 1
            continue

        est_id = ues.id_energy_system_type
        ues_id = ues.id
        res_id = res.id
        rd_id = station.id_regional_district

        # Важно: проверяем наличие энергоузла
        if station.id_energy_unit is not None:
            eu_id = station.id_energy_unit
            eu_name = station.energy_unit.name if station.energy_unit else 0
        else:
            eu_id = 0
            eu_name = "без энергоузла"

        # Создаем уникальный ключ для отслеживания добавленных станций
        station_key = (station.id, est_id, ues_id, res_id, rd_id, eu_id)
        
        # Проверяем, не была ли эта станция уже добавлена в эту группу
        if station_key in added_stations:
            print(f"[WARNING] Станция {station.id} ({station.name}) уже добавлена в группу {station_key}, пропускаем")
            skipped_count += 1
            skipped_duplicates += 1
            continue
        
        added_stations.add(station_key)

        # Добавляем станцию в иерархию
        grouped_data[est_id][ues_id][res_id][rd_id][eu_id].append(station)

        if include_names:
            est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
            ues_names[ues_id] = ues.name
            res_names[res_id] = res.name
            rd_names[rd_id] = station.regional_district.name
            eu_names[eu_id] = eu_name

    # Подсчитываем общее количество станций в группировке
    total_stations_in_groups = 0
    for est_id, est_group in grouped_data.items():
        for ues_id, ues_group in est_group.items():
            for res_id, res_group in ues_group.items():
                for rd_id, rd_group in res_group.items():
                    for eu_id, eu_group in rd_group.items():
                        total_stations_in_groups += len(eu_group)

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

    # Итоговая сводка для отладки
    try:
        print(
            f"[DEBUG][build_hierarchy_structure] processed={processed_count}, "
            f"skipped={skipped_count}, grouped_count={total_stations_in_groups}"
        )
        print(
            f"[DEBUG][build_hierarchy_structure] skipped_no_rd_or_res={skipped_no_rd_or_res}, "
            f"skipped_no_ues={skipped_no_ues}, skipped_duplicates={skipped_duplicates}"
        )
    except Exception:
        pass

    return result


def fetch_machines_with_rowspans(
    station_ids: list[int],
    show_p_ogr: bool = False,
    show_p_rasp: bool = False,
    filters: dict | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
):
    # Локальный помощник для фильтрации по текущей версии (чтобы избежать проблем области видимости)
    def _is_current_version(entity) -> bool:
        current_version_id = get_current_db_version_id()
        if entity is None:
            return False
        if not hasattr(entity, 'database_version_id'):
            return True
        return (entity.database_version_id is None) or (entity.database_version_id == current_version_id)
    # Базовые агрегаты с фильтром по версии
    machine_query = Machine.query
    machine_query = filter_by_db_version(machine_query, Machine)
    machine_query = machine_query.options(
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station).joinedload(Station.station_type),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_fuels)
            .selectinload(MachineFuel.fuel)
            .selectinload(Fuel.fuel_type),
        joinedload(Machine.machine_fuel_param),
        joinedload(Machine.equipment_group),
    ).filter(Machine.id_station.in_(station_ids))

    # При фильтрах по датам: показывать Machine, если он сам или его PGUMachine-потомки совпадают
    date_filters_present = (
        (filters or {}).get("date_commission_filter")
        or (filters or {}).get("date_exploitation_filter")
        or (filters or {}).get("date_decompressing_expected_filter")
        or (filters or {}).get("date_modernization_expected_filter")
        or (filters or {}).get("date_modernization_no_power_expected_filter")
    )
    if date_filters_present:
        from app.generation.services.station_services.filters_services import (
            build_date_commission_filter,
            build_date_exploitation_filter,
            build_date_decompressing_filter,
            build_date_modernization_filter,
            build_date_modernization_no_power_filter,
            get_pgu_date_cond_for_filter,
        )
        filter_pairs = [
            (build_date_commission_filter, "date_commission_filter"),
            (build_date_exploitation_filter, "date_exploitation_filter"),
            (build_date_decompressing_filter, "date_decompressing_expected_filter"),
            (build_date_modernization_filter, "date_modernization_expected_filter"),
            (build_date_modernization_no_power_filter, "date_modernization_no_power_expected_filter"),
        ]
        and_parts = []
        for build_fn, key in filter_pairs:
            if not (filters or {}).get(key):
                continue
            machine_cond = build_fn(Machine, filters or {})
            pgu_cond = get_pgu_date_cond_for_filter(PGUMachine, filters or {}, key)
            if machine_cond is not None and pgu_cond is not None:
                and_parts.append(or_(machine_cond, Machine.pgu_submachines.any(pgu_cond)))
            elif machine_cond is not None:
                and_parts.append(machine_cond)
            elif pgu_cond is not None:
                and_parts.append(Machine.pgu_submachines.any(pgu_cond))
        if and_parts:
            machine_query = machine_query.filter(and_(*and_parts))

    from app.generation.services.station_services.filters_services import build_relabing_outcome_filter

    rel_cond = build_relabing_outcome_filter(Machine, filters or {})
    if rel_cond is not None:
        machine_query = machine_query.filter(rel_cond)

    # Фильтр: только агрегаты без группы оборудования
    if (filters or {}).get("machines_without_equipment_group"):
        machine_query = machine_query.filter(Machine.id_equipment_group.is_(None))

    note_machine_cond = build_machine_note_search_condition(
        Machine, PGUMachine, (filters or {}).get("note_filter")
    )
    if note_machine_cond is not None:
        machine_query = machine_query.filter(note_machine_cond)

    machines = machine_query.all()

    # Сначала фильтруем внутренние коллекции по версии БД (важно для primary_fuel_type)
    for m in machines:
        if hasattr(m, 'machine_powers') and m.machine_powers:
            m.machine_powers = [mp for mp in m.machine_powers if _is_current_version(mp)]
        if hasattr(m, 'machine_fuels') and m.machine_fuels:
            m.machine_fuels = [mf for mf in m.machine_fuels if _is_current_version(mf)]

    # Проверка топлива: оставляем только "проблемные" агрегаты:
    # - fuel_so (по СО ЕЭС) пустое, но есть топливо по годам, ИЛИ
    # - fuel_so заполнено, но не совпадает с топливами по годам в диапазоне лет.
    if (filters or {}).get("fuel_check"):
        from app.common.services.get_services.years.years_get_services import (
            get_filter_start_year,
            get_filter_end_year,
        )
        from config import Config

        def _fuel_so_missing(value) -> bool:
            if value is None:
                return True
            text = str(value).strip()
            return (text == "") or (text.lower() == "не указано")

        def _normalize_fuel_token(text: str) -> str:
            # Нормализация для сравнения (без попыток "умного" маппинга синонимов)
            return " ".join(str(text).strip().lower().split())

        def _split_fuel_so(text: str) -> set[str]:
            # fuel_so часто вводится как "уголь, газ" / "уголь;газ" / "уголь/газ" / "уголь и газ"
            s = _normalize_fuel_token(text)
            for sep in [";", "/", "+", "|"]:
                s = s.replace(sep, ",")
            s = s.replace(" и ", ",")
            parts = [p.strip() for p in s.split(",") if p.strip()]
            return set(parts)

        sy = int(start_year if start_year is not None else get_filter_start_year())
        ey = int(end_year if end_year is not None else get_filter_end_year())

        def _is_problem_machine(m: Machine) -> bool:
            fuels_by_year = m.fuel_type_by_year or {}
            year_fuels = {
                _normalize_fuel_token(name)
                for y, name in fuels_by_year.items()
                if y is not None and sy <= int(y) <= ey and name and _normalize_fuel_token(name) != "не указано"
            }
            if not year_fuels:
                return False

            if _fuel_so_missing(m.fuel_so):
                return True

            so_tokens = _split_fuel_so(m.fuel_so)
            if not so_tokens:
                return True

            # Совпадение, если хотя бы один токен из fuel_so встречается в топливах по годам
            return year_fuels.isdisjoint(so_tokens)

        machines = [m for m in machines if _is_problem_machine(m)]

    # Загружаем годы и устанавливаем их вручную
    year_numbers = set()
    for machine in machines:
        for mp in machine.machine_powers:
            if mp.year_number:
                year_numbers.add(mp.year_number)
        for mf in machine.machine_fuels:
            if mf.year_number:
                year_numbers.add(mf.year_number)
        for mt in machine.machine_tes_types:
            if mt.year_number:
                year_numbers.add(mt.year_number)
    
    if year_numbers:
        years = Year.query.filter(Year.number.in_(year_numbers)).all()
        year_dict = {y.number: y for y in years}
        
        # Устанавливаем year вручную
        for machine in machines:
            for mp in machine.machine_powers:
                if mp.year_number and mp.year_number in year_dict:
                    mp.year = year_dict[mp.year_number]
            for mf in machine.machine_fuels:
                if mf.year_number and mf.year_number in year_dict:
                    mf.year = year_dict[mf.year_number]
            for mt in machine.machine_tes_types:
                if mt.year_number and mt.year_number in year_dict:
                    mt.year = year_dict[mt.year_number]

    machine_ids = [m.id for m in machines]
    pgu_query = PGUMachine.query
    pgu_query = filter_by_db_version(pgu_query, PGUMachine)
    pgu_machines = pgu_query.filter(PGUMachine.id_parent_machine.in_(machine_ids)).all()

    pgu_machine_ids = [p.id for p in pgu_machines]
    pgu_power_query = PGUMachinePower.query
    pgu_power_query = filter_by_db_version(pgu_power_query, PGUMachinePower)
    pgu_powers = pgu_power_query.filter(PGUMachinePower.id_pgu_machine.in_(pgu_machine_ids)).all()

    pgu_powers_map = defaultdict(dict)
    for power in pgu_powers:
        pgu_powers_map[power.id_pgu_machine][power.year_number] = power.p_ust or 0

    pgu_map = defaultdict(list)
    # Фильтрация по версии после загрузки на всякий случай
    for pgu in pgu_machines:
        pgu.powers_by_year = pgu_powers_map.get(pgu.id, {})
        pgu_map[pgu.id_parent_machine].append(pgu)

    station_machine_map = defaultdict(list)
    station_totals = {}

    note_filter_sub = ((filters or {}).get("note_filter") or "").strip()

    for m in machines:
        m.pgu_machines = [p for p in pgu_map.get(m.id, []) if _is_current_version(p)]
        if note_filter_sub:
            mach_note = (getattr(m, "note", None) or "")
            if note_filter_sub.casefold() not in mach_note.casefold():
                nf = note_filter_sub.casefold()
                m.pgu_machines = [
                    p
                    for p in m.pgu_machines
                    if (getattr(p, "note", None) or "")
                    and nf in (p.note or "").casefold()
                ]
        station_machine_map[m.id_station].append(m)

    for station_id, machine_list in station_machine_map.items():
        def machine_number_key(value):
            s = str(value).strip() if value is not None else ''
            match = re.match(r"(\d+)", s)
            if match:
                num = int(match.group(1))
                suffix = s[match.end():].lower()
                return (0, num, suffix)
            return (1, float('inf'), s.lower())

        def machine_group_key(value):
            raw = str(value).strip() if value is not None else ''
            if not raw or raw.lower() == 'не указано':
                return (1, float('inf'), '')
            match = re.match(r"(\d+)", raw)
            if match:
                num = int(match.group(1))
                suffix = raw[match.end():].lower()
                return (0, num, suffix)
            return (0, float('inf'), raw.lower())

        def fuel_sort_key(m):
            """Ключ для сортировки: топливо по СО ЕЭС (пустое/не указано — в конец)."""
            raw = (getattr(m, 'fuel_so', None) or '').strip()
            if not raw or raw.lower() == 'не указано':
                return (1, raw.lower())  # в конец
            return (0, raw.lower())

        # Порядок блоков внутри станции определяем по минимальному станционному номеру.
        # Сначала держим агрегаты одной группы оборудования вместе, а внутри группы
        # оставляем прежнюю группировку по топливу и номеру агрегата.
        def group_min_number_key(machines):
            return min(machine_number_key(getattr(m, 'machine_number', None)) for m in machines)

        equipment_group_blocks_dict = defaultdict(list)
        for m in machine_list:
            group_value = (getattr(m, 'machine_group', None) or '').strip()
            if not group_value or group_value.lower() == 'не указано':
                block_key = ("__machine__", m.id)
            else:
                block_key = ("group", group_value)
            equipment_group_blocks_dict[block_key].append(m)

        ordered_group_blocks = []
        ordered_fuel_blocks = []
        for _, equipment_group_block in sorted(
            equipment_group_blocks_dict.items(),
            key=lambda item: (
                group_min_number_key(item[1]),
                machine_group_key(item[1][0].machine_group),
            ),
        ):
            fuel_groups_dict = defaultdict(list)
            for m in equipment_group_block:
                fkey = fuel_sort_key(m)
                if fkey[0] == 1:
                    fkey = (1, m.id)  # уникальный ключ для пустого/не указано
                fuel_groups_dict[fkey].append(m)

            for group in fuel_groups_dict.values():
                group.sort(key=lambda m: (
                    machine_number_key(getattr(m, 'machine_number', None)),
                    (getattr(m, 'machine_name', None) or '').strip().lower(),
                    getattr(m, 'id', 0) or 0,
                ))

            sorted_fuel_groups = sorted(fuel_groups_dict.values(), key=group_min_number_key)
            ordered_group_blocks.append([m for group in sorted_fuel_groups for m in group])
            ordered_fuel_blocks.extend(sorted_fuel_groups)

        machine_list[:] = [m for group in ordered_group_blocks for m in group]

        # Сначала задаем total_rows каждой машине (нужно для fuel_rowspan)
        for m in machine_list:
            num_pgu = len(m.pgu_machines)
            base_rows = 1 + num_pgu
            total_rows = base_rows
            if show_p_ogr:
                total_rows += 1
            if show_p_rasp:
                total_rows += 1
            m.total_rows = total_rows
            m.base_rows = base_rows

        # Группа "гр." — одна ячейка на весь блок группы оборудования внутри станции.
        for group in ordered_group_blocks:
            group_rowspan = sum(m.total_rows for m in group)
            group_base_rows = sum((1 + len(m.pgu_machines)) for m in group)
            group[0].group_rowspan = group_rowspan
            group[0].group_base_rows = group_base_rows
            group[0].group_machine_count = len(group)
            for m in group[1:]:
                m.group_rowspan = 0
                m.group_base_rows = 0
                m.group_machine_count = 0

        # Топливо (по СО ЕЭС) объединяем только внутри блока группы оборудования.
        for group in ordered_fuel_blocks:
            fuel_rowspan = sum(m.total_rows for m in group)
            fuel_base_rows = sum((1 + len(m.pgu_machines)) for m in group)
            group[0].fuel_rowspan = fuel_rowspan
            group[0].fuel_base_rows = fuel_base_rows
            group[0].fuel_machine_count = len(group)
            for m in group[1:]:
                m.fuel_rowspan = 0
                m.fuel_base_rows = 0
                m.fuel_machine_count = 0

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
