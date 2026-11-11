from collections import defaultdict
from decimal import Decimal

from app.rational_structure.services.territory_ungrouped_equipment_services import ungrouped_equipment_rows


def _summary_row(key, label, rows, years, unit='МВт'):
    cells = []
    for index in range(len(years)):
        value = sum((Decimal(row['cells'][index] or '0') for row in rows if row['unit'] == unit), Decimal(0))
        cells.append(str(value) if value else '')
    return dict(key=key, label=label, number='', unit=unit, note='', section=False,
                readonly=True, virtual=True, formula='', cells=cells)


def build_equipment_hierarchy(rows, station_types, station_totals, years, initial_station_totals, *, ungrouped=None):
    type_by_label = {'ГЭС до 50 МВт': 'ГЭС', 'ГЭС более 50 МВт': 'ГЭС', 'ВЭС': 'ВИЭ', 'СЭС': 'ВИЭ'}
    technology_order = {name: index for index, name in enumerate(station_types)}
    type_order = []
    for name in [*station_types, 'АЭС', 'ГЭС', 'ТЭС', 'ВИЭ', 'ГАЭС', 'СНЭЭ']:
        name = 'ВИЭ' if name in ('ВЭС', 'СЭС') else name
        if name in ('АЭС', 'ГЭС', 'ТЭС', 'ВИЭ', 'ГАЭС', 'СНЭЭ') and name not in type_order:
            type_order.append(name)
    blocks = []
    for row in rows:
        if str(row['number']).strip() == '18':
            blocks.append([row, []])
        elif blocks:
            blocks[-1][1].append(row)
    result = []
    for block_index, (original, children) in enumerate(blocks):
        block_key = f'equipment_block_{block_index}'
        groups = defaultdict(list)
        for row in children:
            if row['section']:
                continue
            generation_type = row.get('generation_type') or type_by_label.get(row['label'])
            if generation_type is not None:
                fuel = row.get('generation_fuel', '') if generation_type == 'ТЭС' else ''
                groups[generation_type, fuel].append(row)
        group_rows = []
        body = []
        for generation_type in type_order:
            fuels = [fuel for kind, fuel in groups if kind == generation_type] or ['']
            if generation_type == 'ТЭС' and any(fuels):
                fuels.sort(key=lambda fuel: (fuel != 'газ', fuel != 'уголь', fuel))
                thermal_leaves = [row for fuel in fuels for row in groups[generation_type, fuel]]
                thermal_key = f'{block_key}_tes'
                units = ['шт', 'МВт'] if any(row['unit'] == 'шт' for row in thermal_leaves) else ['МВт']
                for unit in units:
                    summary = _summary_row(f'{thermal_key}_{unit}', 'ТЭС', thermal_leaves, years, unit=unit)
                    summary.update(subsection=True, equipment_rollup='thermal', equipment_group=thermal_key,
                                   equipment_block=block_key, equipment_parent=block_key,
                                   equipment_identity=('thermal', unit))
                    body.append(summary)
            for fuel in fuels:
                label = f'ТЭС ({fuel})' if fuel else generation_type
                group_key = f'{block_key}_type_{len(group_rows)}'
                leaves = groups[generation_type, fuel]
                if generation_type == 'ВИЭ':
                    leaves.sort(key=lambda row: technology_order.get(row['label'], len(station_types)))
                summary = _summary_row(group_key, label, leaves, years)
                summary.update(subsection=True, equipment_rollup='type', equipment_group=group_key,
                               equipment_block=block_key, equipment_parent=block_key,
                               equipment_identity=('type', generation_type, fuel, 'МВт'))
                if generation_type in ('ГАЭС', 'СНЭЭ') and block_index in (0, 3):
                    totals = initial_station_totals if block_index == 0 else station_totals
                    summary['cells'] = [str(value) if value else ''
                                        for value in totals[generation_type]]
                group_rows.append(summary)
                count_leaves = [row for row in leaves if row['unit'] == 'шт']
                if count_leaves:
                    count_summary = _summary_row(f'{group_key}_counts', label, count_leaves, years, unit='шт')
                    count_summary.update(subsection=True, equipment_rollup='type', equipment_group=group_key,
                                         equipment_block=block_key, equipment_parent=block_key,
                                         equipment_identity=('type', generation_type, fuel, 'шт'))
                    body.append(count_summary)
                body.append(summary)
                for row in leaves:
                    body.append(dict(row, equipment_parent=block_key, equipment_group=group_key,
                                     equipment_block=block_key, equipment_identity=row.get(
                                         'equipment_identity', ('leaf', generation_type, row['label'], row['unit']))))
                has_ungrouped_leaf = any(row['label'] == 'Без группы оборудования' for row in leaves)
                if ungrouped is not None and generation_type in ('ТЭС', 'АЭС') and not has_ungrouped_leaf:
                    item = ungrouped.get((generation_type, fuel))
                    for row in ungrouped_equipment_rows(item, generation_type, fuel,
                                                        ('total', 'first', 'second', 'remaining')[block_index], years):
                        # Диагностический срез уже входит в leaves; отсутствие equipment_group исключает повторный счет в JS.
                        body.append(dict(row, equipment_parent=block_key, equipment_block=block_key))
        total = _summary_row(original['key'], original['label'], group_rows, years)
        total.update(number='18', note=original['note'], equipment_rollup='block', equipment_block=block_key,
                     equipment_identity=('block',))
        result.extend([total, *body])
    return result


def build_equipment_verification_rows(rows, years):
    blocks = defaultdict(dict)
    for row in rows:
        blocks[row['equipment_block']][row['equipment_identity']] = row
    formula = ('Всего до проведения мероприятий − Первый ресурс − Второй ресурс '
               '− Всего за вычетом первого и второго ресурса.')
    result = []
    for identity, original in blocks['equipment_block_0'].items():
        sources = [blocks[f'equipment_block_{index}'][identity] for index in range(4)]
        cells = [str(Decimal(sources[0]['cells'][index] or '0') - sum(
            (Decimal(source['cells'][index] or '0') for source in sources[1:]), Decimal(0)))
                 for index in range(len(years))]
        key = f'equipment_check_{len(result)}'
        row = dict(original, key=key, number='', cells=cells, note='', readonly=True, virtual=True,
                   formula=formula, cell_details=[], equipment_verification=True,
                   verification_sources=[source['key'] for source in sources],
                   verification_errors=[Decimal(value) != 0 for value in cells],
                   equipment_block='equipment_check')
        if original.get('equipment_rollup') == 'block':
            row.update(label='Проверка', equipment_parent=None, equipment_rollup='verification')
        else:
            row.update(equipment_parent='equipment_check', equipment_rollup='verification_type'
                       if original.get('equipment_rollup') else None)
        row.pop('equipment_group', None)
        result.append(row)
    return result
