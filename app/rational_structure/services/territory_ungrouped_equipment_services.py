"""Диагностика незаполненного типа группы оборудования без изменения итогов."""


def ungrouped_equipment_series(runtime, groups, powers, years, base_year, zone_id,
                               *, total_years=None):
    from app.rational_structure.services.territory_equipment_services import equipment_series

    group_ids = {group.id for group in groups if group.id > 0 and group.name.strip().casefold() not in (
        '', 'не указано', 'без группы оборудования')}
    rows = [dict(row, technology_type_id='ТЭС') for row in runtime
            if row['equipment_group_type_id'] not in group_ids]
    data = equipment_series(rows, [], [], powers, years, base_year, zone_id,
                            total_years=total_years)
    result = {}
    for item in data:
        technology, fuel, _ = item['key']
        generation_type = 'АЭС' if fuel == 'атом' else technology or 'ТЭС'
        result[generation_type, fuel if generation_type == 'ТЭС' else ''] = item
    return result


def ungrouped_equipment_rows(item, generation_type, fuel, block, years):
    for metric, unit in (('counts', 'шт'), ('series', 'МВт')):
        cells = item[metric][block] if item else [0] * len(years)
        aggregates = item['contributors'][metric][block] if item else [[] for _ in years]
        yield dict(key=f'ungrouped_{block}_{generation_type}_{fuel}_{metric}',
                   label='Без группы оборудования', number='', unit=unit,
                   note='В том числе: тип группы оборудования в карточке не задан. Повторно в итог не включается.',
                   section=False, readonly=True, virtual=True, equipment_diagnostic=True,
                   cells=[str(value) if value else '' for value in cells],
                   cell_details=[[dict(label='', sign=1, aggregates=items)] if items else [] for items in aggregates],
                   formula='',
                   equipment_identity=('ungrouped', generation_type, fuel, metric))
