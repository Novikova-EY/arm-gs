from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select
from werkzeug.datastructures import MultiDict

from test_territory_data import database
from test_calculation_pages import calculation_database
from test_territory_equipment import runtime_row, sources
from test_territory_equipment_perimeter import ees_reference
from test_equipment_runtime_modernization import set_current_year
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_data_export_services import export_territory_inputs
from app.rational_structure.services.territory_input_services import build_territory_input_context
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService


@pytest.fixture
def sipr_equipment(ees_reference):
    TerritoryInput.__table__.create(db.engine)
    TechnologyType.__table__.create(db.engine)
    set_current_year(2025)
    db.session.add_all([YearService(database_version_id=1, year_sipr_end=2030),
                        YearService(database_version_id=2, year_sipr_end=2034)])
    features = {}
    for name in ('факт', 'план'):
        item = YearFeature(name=name, database_version_id=1)
        db.session.add(item)
        db.session.flush()
        features[name] = item.id
    years = list(range(2024, 2043))
    for year in years:
        item = db.session.scalar(select(Year).where(Year.number == year, Year.database_version_id == 1))
        if item is None:
            item = Year(number=year, database_version_id=1)
            db.session.add(item)
        if year != 2025:
            item.id_year_feature = features['факт' if year in (2024, 2032) else 'план'] if year != 2033 else None
    kinds = ('ТЭС', 'АЭС', 'ГЭС', 'ВЭС', 'СЭС', 'ГАЭС', 'СНЭЭ')
    db.session.execute(StationType.__table__.insert(), [
        dict(id=index, name=name, database_version_id=1) for index, name in enumerate(kinds, 1) if index != 1])
    for type_id, name in enumerate(kinds, 1):
        station_id = type_id + 10
        db.session.execute(Station.__table__.insert(), dict(
            id=station_id, name=name, external_code=f'station-{station_id}', id_station_type=type_id,
            id_regional_district=1, database_version_id=1))
        for part in (0, 1):
            machine_id = station_id * 10 + part
            db.session.execute(Machine.__table__.insert(), dict(
                id=machine_id, id_station=station_id, machine_number=str(part), machine_name=f'{name} {part}',
                external_code=f'machine-{machine_id}', database_version_id=1))
            for index, year in enumerate(years, 1):
                power = type_id * index if part == 0 else (100 if year >= 2031 else 0)
                db.session.add(MachinePower(id_machine=machine_id, year_number=year,
                                           p_ust=power, database_version_id=1))
    db.session.commit()
    return years


@pytest.mark.parametrize('zone', [0, 1])
@pytest.mark.parametrize('selected', [None, 2031, 2042])
def test_initial_uses_annual_power_through_sipr_then_freezes_only_plan_years(sipr_equipment, zone, selected):
    args = MultiDict({'start_year': '2024', 'end_year': '2042'})
    if selected:
        args['view_year'] = str(selected)
    context = prepare_territory_input_view(build_territory_input_context(1, zone, sheet='equipment'), args)
    assert context['equipment_sipr_end_year'] == 2030
    source_years = {year: 2030 if year > 2030 and year not in (2032, 2033) else year
                    for year in context['years']}
    assert context['equipment_total_source_years'] == source_years
    for row in context['rows']:
        if row['equipment_block'] != 'equipment_block_0' or row['unit'] != 'МВт':
            continue
        if row.get('equipment_rollup') == 'type':
            factor = {'ТЭС (прочие)': 1, 'АЭС': 2, 'ГЭС': 3, 'ВИЭ': 9, 'ГАЭС': 6, 'СНЭЭ': 7}[row['label']]
            count = 2 if row['label'] == 'ВИЭ' else 1
            expected = [factor * (sipr_equipment.index(source_years[year]) + 1)
                        + (count * 100 if source_years[year] >= 2031 else 0) for year in context['years']]
            assert [Decimal(value or 0) for value in row['cells']] == expected
        if row.get('equipment_diagnostic') and row['cell_details']:
            for year, details in zip(context['years'], row['cell_details']):
                power = sum(aggregate['power'] for component in details for aggregate in component['aggregates'])
                assert power == Decimal(row['cells'][context['years'].index(year)] or 0)
    diagnostic_counts = next(row for row in context['rows']
                             if row['key'] == 'aes_counts_total_None_атом_None')
    assert [Decimal(value or 0) for value in diagnostic_counts['cells']] == [
        2 if source_years[year] >= 2031 else 1 for year in context['years']]
    initial = next(row for row in context['rows'] if row.get('equipment_rollup') == 'block')
    expected_total = [28 * (sipr_equipment.index(source_years[year]) + 1)
                      + (700 if source_years[year] >= 2031 else 0) for year in context['years']]
    assert [Decimal(value) for value in initial['cells']] == expected_total
    remaining = next(row for row in context['rows'] if row.get('equipment_rollup') == 'block'
                     and row['equipment_block'] == 'equipment_block_3')
    assert [Decimal(value) for value in remaining['cells']] == [
        28 * (sipr_equipment.index(year) + 1) + (700 if year >= 2031 else 0) for year in context['years']]
    book = load_workbook(export_territory_inputs(context))
    try:
        assert [book.active.cell(3, col).value for col in range(4, 4 + len(context['years']))] == expected_total
    finally:
        book.close()


def test_new_total_source_years_do_not_change_resources_or_remaining(sources):
    row = runtime_row(1, 1, first=2026, second=2030)
    powers = [(1, None, year, Decimal(value)) for year, value in ((2024, 10), (2026, 20), (2030, 30), (2042, 40))]
    years = [2024, 2026, 2030, 2042]
    original = services.equipment_series([row], sources[1], sources[2], powers, years, 2024, 1)[0]
    changed = services.equipment_series([row], sources[1], sources[2], powers, years, 2024, 1,
                                        total_years={2024: 2024, 2026: 2026, 2030: 2030, 2042: 2030})[0]
    assert changed['series']['total'] == [10, 20, 30, 30]
    for metric in ('series', 'counts'):
        for block in ('first', 'second', 'remaining'):
            assert changed[metric][block] == original[metric][block]
            assert changed['contributors'][metric][block] == original['contributors'][metric][block]


def test_missing_sipr_end_power_is_not_replaced_by_current_or_visible_year(sipr_equipment):
    db.session.execute(delete(MachinePower).where(
        MachinePower.database_version_id == 1, MachinePower.year_number == 2030))
    db.session.commit()
    context = prepare_territory_input_view(build_territory_input_context(1, 0, sheet='equipment'),
                                          MultiDict({'view_year': '2042'}))
    assert context['equipment_missing_years'] == [2030]
    initial = next(row for row in context['rows'] if row.get('equipment_rollup') == 'block')
    assert initial['cells'] == ['']
    assert all(row['cells'] == [''] for row in context['rows']
               if row['equipment_block'] == 'equipment_block_0' and row.get('equipment_diagnostic'))
    remaining = next(row for row in context['rows'] if row.get('equipment_rollup') == 'block'
                     and row['equipment_block'] == 'equipment_block_3')
    assert Decimal(remaining['cells'][0]) > 0


def test_frozen_pgu_parts_use_sipr_end_composition_without_parent_or_duplicate_codes(sources):
    parts = [runtime_row(1, None, part=10), runtime_row(1, None, part=11)]
    powers = [(1, None, 2030, Decimal(999)), (1, 10, 2030, Decimal(30)), (1, 11, 2030, Decimal(0)),
              (1, 10, 2042, Decimal(50)), (1, 11, 2042, Decimal(50))]
    item = services.equipment_series([*parts, parts[0]], sources[1], sources[2], powers, [2042], 2024, 1,
                                     total_years={2042: 2030})[0]
    assert item['series']['total'] == [30]
    assert item['counts']['total'] == [1]
    assert item['series']['remaining'] == [100]
    assert item['counts']['remaining'] == [2]
    assert [aggregate['number'] for aggregate in item['contributors']['series']['total'][0]] == ['10']
