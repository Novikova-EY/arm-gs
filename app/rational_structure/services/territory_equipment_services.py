import re
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import literal, select
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.refdata.services.year_management_services import get_current_year_info
from app.common.perimeter_variant.constants import EES_UNIFIED_REF_NAME
from app.generation.services.station_services.station_services import _station_res_placement_sql_filter
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.rational_structure.services.territory_equipment_hierarchy_services import (
    build_equipment_hierarchy, build_equipment_verification_rows,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_power_aggregation import (
    load_stations_powers_by_year, machine_not_archived_clause,
)
from app.rational_structure.services.equipment_runtime_services import build_equipment_runtime_context
from app.rational_structure.services.territory_ungrouped_equipment_services import ungrouped_equipment_series
from app.rational_structure.services.territory_input_services import (
    TERRITORY_STATION_POWER_LABELS, territory_nuclear_row_keys, territory_station_power_row_keys,
    territory_thermal_row_keys,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


BLOCKS = (
    ('total', 'Всего до проведения мероприятий'),
    ('first', 'Первый ресурс'),
    ('second', 'Второй ресурс'),
    ('remaining', 'Всего за вычетом первого и второго ресурса'),
)


def _ees_station_clause(version_id):
    # Итог ЕЭС ограничен составом энергозон выбранной версии; прямая РЭС приоритетнее субъекта РФ.
    return _station_res_placement_sql_filter(RegionalEnergySystem.union_energy_system.has(
        UnionEnergySystem.energy_system_type.has(EnergySystemType.name == EES_UNIFIED_REF_NAME))) & (
            Station.regional_district.has(
                (RegionalDistrict.database_version_id == version_id) & RegionalDistrict.energy_zone.has(
                    (EnergyZone.database_version_id == version_id) & (EnergyZone.id > 0))))


def _territory_machine_ids(version_id, *, ees_only=False):
    query = select(Machine.id).join(Station, Station.id == Machine.id_station).where(
        Machine.database_version_id == version_id, Station.database_version_id == version_id,
        machine_not_archived_clause())
    if ees_only:
        query = query.where(_ees_station_clause(version_id))
    return set(db.session.scalars(query))


def load_territory_equipment_sources(version_id):
    runtime = build_equipment_runtime_context(MultiDict({'per_page': 'all'}), version_id)
    # Топливо и мероприятия совпадают с расчетом наработки; базовый год Руст определяется отдельно.
    base_year = runtime['current_year'] or runtime['selected_year']
    groups = list(db.session.scalars(select(EquipmentGroupType).where(
        EquipmentGroupType.database_version_id == version_id).order_by(
            EquipmentGroupType.display_order.asc().nullslast(), EquipmentGroupType.id)))
    technologies = list(db.session.scalars(select(TechnologyType).where(
        (TechnologyType.database_version_id == version_id) |
        TechnologyType.id.in_({group.id_technology_type for group in groups})).order_by(
            TechnologyType.display_order.asc().nullslast(), TechnologyType.id)))
    rows = runtime['calculation_rows'] + load_territory_nuclear_rows(version_id)
    machine_ids = _territory_machine_ids(version_id)
    rows = [row for row in rows if row['machine_id'] in machine_ids]
    machine_ids = {row['machine_id'] for row in rows}
    powers = list(db.session.execute(select(
        MachinePower.id_machine, literal(None), MachinePower.year_number, MachinePower.p_ust,
    ).where(MachinePower.database_version_id == version_id, MachinePower.id_machine.in_(machine_ids))))
    powers.extend(db.session.execute(select(
        PGUMachine.id_parent_machine, PGUMachinePower.id_pgu_machine,
        PGUMachinePower.year_number, PGUMachinePower.p_ust,
    ).join(PGUMachine, PGUMachine.id == PGUMachinePower.id_pgu_machine).where(
        PGUMachinePower.database_version_id == version_id, PGUMachine.database_version_id == version_id,
        PGUMachine.id_parent_machine.in_(machine_ids))))
    return rows, groups, technologies, powers, base_year


def load_territory_nuclear_rows(version_id):
    machines = db.session.scalars(select(Machine).join(Station, Station.id == Machine.id_station).join(
        StationType, StationType.id == Station.id_station_type).where(
            Machine.database_version_id == version_id, Station.database_version_id == version_id,
            StationType.name == 'АЭС').options(
                joinedload(Machine.machine_station).joinedload(Station.regional_district)).order_by(
                    Station.name, Machine.machine_number, Machine.id))
    rows = []
    for machine in machines:
        station = machine.machine_station
        region = station.regional_district
        rows.append(dict(station_id=station.id, machine_id=machine.id, pgu_machine_id=None,
                         energy_zone_id=region.id_energy_zone if region else None,
                         technology_type_id=machine.id_technology_type,
                         equipment_group_type_id=machine.id_equipment_group, fuel_code='NUCLEAR',
                         values=dict(G=station.name, H=machine.machine_number, L=machine.machine_name,
                                     AS=None, BC=machine.date_decompressing_expected)))
    return rows


def load_territory_station_types(version_id):
    query = filter_by_explicit_db_version(select(StationType), StationType, version_id).where(StationType.id > 0)
    return [item.name for item in db.session.scalars(query.order_by(
        StationType.display_order.asc().nullslast(), StationType.id))]


def load_territory_station_power_totals(version_id, zone_id, years):
    query = select(Station.id, StationType.name).join(StationType, StationType.id == Station.id_station_type).where(
        Station.database_version_id == version_id, StationType.name.in_(TERRITORY_STATION_POWER_LABELS))
    if zone_id is None:
        query = query.where(_ees_station_clause(version_id))
    else:
        query = query.join(RegionalDistrict, RegionalDistrict.id == Station.id_regional_district).where(
            RegionalDistrict.id_energy_zone == zone_id, RegionalDistrict.database_version_id == version_id)
    stations = db.session.execute(query).all()
    powers = load_stations_powers_by_year([station_id for station_id, _ in stations], years, version_id)
    totals = {label: [Decimal(0)] * len(years)
              for group in TERRITORY_STATION_POWER_LABELS.values() for label in group}
    for station_id, station_type in stations:
        labels = TERRITORY_STATION_POWER_LABELS[station_type]
        for index, year in enumerate(years):
            power = powers.get(station_id, {}).get(year, {}).get('p_ust', Decimal(0))
            label = labels[1] if station_type == 'ГЭС' and power >= 50 else labels[0]
            totals[label][index] += power
    return totals


def _aggregate_detail(row, year, power):
    values = row['values']
    return dict(year=year, station=values['G'] or '–', number=values['H'] or '–',
                name=values['L'] or '–', power=power, station_id=row['station_id'],
                machine_id=row['machine_id'], pgu_machine_id=row['pgu_machine_id'])


def equipment_series(runtime_rows, groups, technologies, powers, years, base_year, zone_id, *, total_years=None):
    group_by_id = {group.id: group for group in groups}
    technology_by_id = {technology.id: technology for technology in technologies}
    nuclear_technology_ids = {technology.id for technology in technologies if technology.name == 'АЭС'}
    nuclear_groups = [group for group in groups if group.id_technology_type in nuclear_technology_ids
                      and group.id > 0 and group.name.strip().casefold() not in (
                          '', 'не указано', 'без группы оборудования')]
    annual_powers = {(machine_id, part_id, year): power for machine_id, part_id, year, power in powers}
    thermal_technology_id = next((technology.id for technology in technologies if technology.name == 'ТЭС'), None)
    canonical = {group.name.strip(): group for group in groups}
    group_labels = {group.id: re.sub(r'^(Блоки \d+)Т \(рек\)$', r'\1К',
                                   re.sub(r'\s*\([Рр]\)\s*$', '', group.name).strip()) for group in groups}
    for group in groups:
        canonical.setdefault(group_labels[group.id], group)
    events = {}
    for row in runtime_rows:
        if zone_id is not None and row['energy_zone_id'] != zone_id:
            continue
        group = group_by_id.get(row['equipment_group_type_id'])
        nuclear = row['fuel_code'] == 'NUCLEAR'
        if group is not None and (group.id <= 0 or group.name.strip().casefold() in (
                '', 'не указано', 'без группы оборудования')):
            group = None
        if group is not None and not nuclear:
            group = canonical.get(group_labels[group.id], group)
        fuel = {'GAZ': 'газ', 'ISK_GAZ': 'газ', 'UGOL': 'уголь', 'NUCLEAR': 'атом'}.get(row['fuel_code'], 'прочие')
        if nuclear:
            technology_id = None
        elif group is None:
            technology_id = thermal_technology_id
        else:
            technology_id = group.id_technology_type or row['technology_type_id']
        key = (technology_id, fuel, group.id if group else None) if fuel != 'прочие' else (None, fuel, None)
        # Несколько кодов ТО одного агрегата не должны повторно учитывать его мощность и количество.
        identity = row['machine_id'], row['pgu_machine_id']
        events.setdefault(identity, (key, row))
    keys = {key for key, row in events.values()} | {(None, 'атом', group.id) for group in nuclear_groups}
    metrics = {metric: {key: {block: [Decimal(0)] * len(years) for block, _ in BLOCKS}
                        for key in keys}
               for metric in ('series', 'counts')}
    values, counts = metrics['series'], metrics['counts']
    contributors = {metric: {key: {block: [[] for _ in years] for block, _ in BLOCKS}
                             for key in keys}
                    for metric in metrics}
    for identity, (key, row) in events.items():
        scheduled = [(row['values'][column], block) for block, column in (('first', 'AS'), ('second', 'BC'))
                     if row['values'][column] is not None and row['values'][column] > base_year]
        # После первого мероприятия агрегат уже выбыл из базового состава: повторно его не вычитаем.
        withdrawal = min(scheduled) if scheduled else None
        for index, year in enumerate(years):
            remaining_power = annual_powers.get((*identity, year))
            if remaining_power is not None and remaining_power > 0:
                values[key]['remaining'][index] += remaining_power
                counts[key]['remaining'][index] += 1
                aggregate = _aggregate_detail(row, None, remaining_power)
                for metric in contributors:
                    contributors[metric][key]['remaining'][index].append(aggregate)
            source_year = total_years[year] if total_years is not None else min(year, base_year)
            power = annual_powers.get((*identity, source_year))
            if power is not None and power > 0:
                aggregate = _aggregate_detail(row, None, power)
                values[key]['total'][index] += power
                counts[key]['total'][index] += 1
                contributors['series'][key]['total'][index].append(aggregate)
                contributors['counts'][key]['total'][index].append(aggregate)
            power = annual_powers.get((*identity, min(year, base_year)))
            if power is not None and power > 0 and withdrawal is not None and withdrawal[0] <= year:
                block = withdrawal[1]
                values[key][block][index] += power
                counts[key][block][index] += 1
                resource_aggregate = _aggregate_detail(row, withdrawal[0], power)
                contributors['series'][key][block][index].append(resource_aggregate)
                contributors['counts'][key][block][index].append(resource_aggregate)
    fuels = defaultdict(set)
    for technology_id, fuel, _ in values:
        if fuel not in ('прочие', 'атом'):
            fuels[technology_id].add(fuel)
    group_order = {group.id: index for index, group in enumerate(groups)}
    technology_order = {technology.id: index for index, technology in enumerate(technologies)}
    ordered = sorted(values, key=lambda key: (
        key[1] == 'прочие', technology_order.get(key[0], len(technologies)),
        key[1] != 'газ', group_order.get(key[2], len(groups))))
    result = []
    for key in ordered:
        technology_id, fuel, group_id = key
        technology = technology_by_id.get(technology_id)
        label = 'АЭС' if fuel == 'атом' else (technology.name if technology else 'Без типа технологии')
        if fuel != 'атом' and len(fuels[technology_id]) > 1:
            label += f' ({fuel})'
        group = group_by_id.get(group_id)
        group_label = (group.name if fuel == 'атом' else group_labels[group.id]) if group else 'Без группы оборудования'
        result.append(dict(key=key, technology=label, group=group_label,
                           series=values[key], counts=counts[key],
                           contributors={metric: sources[key] for metric, sources in contributors.items()}))
    return result


def _calculated_row(key, label, cells, formula='', section=False, unit='МВт'):
    return dict(key=key, label=label, number='', unit='' if section else unit, note='',
                section=section, readonly=True, virtual=True, cells=cells, formula=formula)


def _equipment_rows(data, block, formula, *, metric='series', unit='МВт'):
    previous = None
    for item in data:
        technology_id, fuel, group_id = item['key']
        parent = technology_id, fuel
        family = 'aes' if fuel == 'атом' else 'tes'
        prefix = f'{family}_{"counts_" if metric == "counts" else ""}{block}_{technology_id}_{fuel}'
        if fuel != 'прочие' and parent != previous:
            yield dict(_calculated_row(prefix, item['technology'], [], section=True), subsection=True)
        previous = parent
        label = 'Прочие' if fuel == 'прочие' else item['group']
        cells = [str(value) if value else '' for value in item[metric][block]]
        cell_details = [[dict(label='', sign=1, aggregates=aggregates)] if aggregates else []
                        for aggregates in item['contributors'][metric][block]]
        result = dict(_calculated_row(f'{prefix}_{group_id}', label, cells, formula, unit=unit),
                      cell_details=cell_details, generation_type='АЭС' if family == 'aes' else 'ТЭС',
                      generation_fuel=fuel, equipment_identity=(family, technology_id, fuel, group_id, metric))
        if group_id is None and fuel != 'прочие':
            result.update(equipment_diagnostic=True, formula='', note='Тип группы оборудования в карточке не задан.')
        yield result


def _paired_equipment_rows(data, block, power_formula, count_formula):
    power_rows = _equipment_rows(data, block, power_formula)
    count_rows = _equipment_rows(data, block, count_formula, metric='counts', unit='шт')
    for power_row, count_row in zip(power_rows, count_rows):
        if not count_row['section']:
            yield count_row
        yield power_row


def populate_territory_equipment_rows(context):
    if (context['sheet'] != 'equipment' or context['version_id'] is None or not context['years']
            or (context['selected_zone'] is None and not context.get('is_ees'))):
        return
    runtime, groups, technologies, powers, base_year = load_territory_equipment_sources(context['version_id'])
    zone_id = None if context.get('is_ees') else context['selected_zone'].id
    if context.get('is_ees'):
        machine_ids = _territory_machine_ids(context['version_id'], ees_only=True)
        runtime = [row for row in runtime if row['machine_id'] in machine_ids]
    sipr_end = get_current_year_info(context['version_id'])['sipr_end'] or None
    total_years = {year: sipr_end if (sipr_end is not None and year > sipr_end
                                    and context.get('year_features', {}).get(year) == 'план') else year
                   for year in context['years']}
    context['equipment_sipr_end_year'] = sipr_end
    context['equipment_total_source_years'] = total_years
    data = equipment_series(runtime, groups, technologies, powers, context['years'], base_year, zone_id,
                            total_years=total_years)
    ungrouped = ungrouped_equipment_series(runtime, groups, powers, context['years'], base_year, zone_id,
                                          total_years=total_years)
    nuclear_data = [item for item in data if item['key'][1] == 'атом']
    thermal_data = [item for item in data if item['key'][1] != 'атом']
    identities = {(row['machine_id'], row['pgu_machine_id']) for row in runtime
                  if zone_id is None or row['energy_zone_id'] == zone_id}
    available_years = {year for machine_id, part_id, year, power in powers
                       if (machine_id, part_id) in identities and power is not None}
    source_years = set(total_years.values())
    context['equipment_missing_years'] = (sorted(source_years - available_years) if identities else [])
    context['equipment_base_year'] = base_year
    old_blocks = []
    for row in context['rows']:
        if str(row['number']).strip() == '18':
            old_blocks.append([])
        if old_blocks:
            old_blocks[-1].append(row)
    if len(old_blocks) != 4:
        raise ValueError('В составе оборудования ожидаются четыре блока данных.')
    thermal_keys = territory_thermal_row_keys()
    nuclear_keys = territory_nuclear_row_keys()
    station_power_keys = territory_station_power_row_keys()
    station_years = sorted(set(context['years']) | set(total_years.values()))
    station_sources = load_territory_station_power_totals(context['version_id'], zone_id, station_years)
    station_power_totals = {}
    initial_station_totals = {}
    for label, values in station_sources.items():
        by_year = dict(zip(station_years, values))
        station_power_totals[label] = [by_year[year] for year in context['years']]
        initial_station_totals[label] = [by_year[total_years[year]] for year in context['years']]
    generation_sections = {
        'ГЭС до 50 МВт': ('hydro', 'ГЭС'),
        'СЭС': ('renewable', 'ВИЭ'),
    }
    result = []
    total_rule = (f'Для лет с признаком «план» начиная с {sipr_end + 1} года повторяются данные '
                  f'года окончания СиПР ({sipr_end}); для остальных лет используются данные года столбца.'
                  if sipr_end is not None else
                  'Год окончания СиПР не задан; используются данные года столбца.')
    context['equipment_total_rule'] = total_rule
    formulas = {
        'total': f'Сумма Руст > 0 из карточек агрегатов. {total_rule}',
        'first': f'Руст базового {base_year} года агрегатов, выбывающих по столбцу «Расчетный год модернизации с учетом СиПР» (AS) после {base_year} и не позднее года столбца. «Плановый год модернизации» не используется. Нарастающий итог; учитывается только первое мероприятие агрегата.',
        'second': f'Руст базового {base_year} года агрегатов, выбывающих по демонтажу (BC) после {base_year} и не позднее года столбца. Нарастающий итог; учитывается только первое мероприятие агрегата.',
        'remaining': 'Сумма Руст > 0 из карточек агрегатов за год столбца, включая плановые годы. Независимый расчет после проведения мероприятий.',
    }
    count_formulas = {
        'total': f'1 шт = агрегат с Руст > 0 в карточке. {total_rule} Части ПГУ учитываются без родительского агрегата и без повторения кодов ТО.',
        'first': f'Количество агрегатов базового {base_year} года с Руст > 0, выбывающих по столбцу «Расчетный год модернизации с учетом СиПР» (AS). «Плановый год модернизации» не используется. Нарастающий итог; учитывается только первое мероприятие агрегата.',
        'second': f'Количество агрегатов базового {base_year} года с Руст > 0, выбывающих по демонтажу (BC). Нарастающий итог; учитывается только первое мероприятие агрегата.',
        'remaining': 'Количество агрегатов с Руст > 0 в карточке за год столбца, включая плановые годы. Части ПГУ учитываются без родительского агрегата и повторения кодов ТО.',
    }
    # В исходном шаблоне остаток стоит первым, исходный состав – вторым.
    for (block, title), originals in zip(BLOCKS, (old_blocks[1], old_blocks[2], old_blocks[3], old_blocks[0])):
        inserted = False
        nuclear_inserted = False
        for index, original in enumerate(originals):
            if index == 0:
                result.append(dict(original, label=title))
                continue
            if original['key'] in nuclear_keys:
                if not nuclear_inserted:
                    nuclear_inserted = True
                    if nuclear_data:
                        result.extend(_paired_equipment_rows(nuclear_data, block, '', ''))
                    else:
                        result.append(dict(_calculated_row(f'aes_{block}', 'АЭС', [], section=True), subsection=True))
                continue
            if original['key'] not in thermal_keys:
                group = generation_sections.get(original['label'])
                if group is not None:
                    code, label = group
                    result.append(dict(_calculated_row(f'{code}_{block}', label, [], section=True), subsection=True))
                if original['key'] in station_power_keys:
                    totals = initial_station_totals if block == 'total' else station_power_totals
                    cells = [str(value) if value else '' for value in totals[original['label']]]
                    result.append(dict(original, cells=cells, readonly=True, formula=''))
                else:
                    result.append(original)
                continue
            if inserted:
                continue
            inserted = True
            result.extend(_paired_equipment_rows(thermal_data, block, formulas[block], count_formulas[block]))
    context['rows'] = build_equipment_hierarchy(
        result, load_territory_station_types(context['version_id']), station_power_totals, context['years'],
        initial_station_totals, ungrouped=ungrouped)
    context['equipment_verification_rows'] = build_equipment_verification_rows(context['rows'], context['years'])
