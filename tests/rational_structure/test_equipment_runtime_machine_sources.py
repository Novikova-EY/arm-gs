from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, insert, select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_technical_characteristics import database
from app.extensions import db
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.services.calculation.fuel_calculation_edit_data_services import build_fuel_nazvl_to_name_map
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic, TechnicalInspectionCode
from app.rational_structure.services.equipment_runtime_machine_services import MAIN_FUEL_FIELDS, main_fuel
from app.rational_structure.services.equipment_runtime_services import build_equipment_runtime_context, read_equipment_runtime_workbook
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType


def context(year=2024, version=1, **filters):
    return build_equipment_runtime_context(MultiDict(dict(year=str(year), per_page='all', **filters)), version)


@pytest.fixture
def machine_sources(calculation_database):
    db.session.execute(insert(Fuel), [
        {'name': 'Уголь', 'nazvl': 'UGOL', 'database_version_id': 1},
        {'name': 'Газ природный', 'nazvl': 'gaz', 'database_version_id': 1},
        {'name': 'Уголь другой версии', 'nazvl': 'UGOL', 'database_version_id': 2},
    ])
    db.session.execute(insert(GenCompany), {'id': 1, 'name': 'Собственник агрегата', 'database_version_id': 1})
    db.session.get(Machine, 1).id_gen_company = 1
    db.session.execute(insert(EquipmentGroupType), {'id': 1, 'name': 'Тип группы из карточки', 'database_version_id': 1})
    db.session.get(Machine, 1).id_equipment_group = 1
    db.session.execute(insert(EquipmentGroup), {
        'id': 1, 'name': 'Название группы, НЕ тип', 'external_code': 'group-1', 'database_version_id': 1})
    db.session.execute(insert(EquipmentGroupSetStation), {
        'id': 1, 'station_id': 1, 'equipment_group_type_id': 1, 'database_version_id': 1})
    db.session.execute(insert(EquipmentGroupSet), {'equipment_group_id': 1, 'equipment_group_set_station_id': 1})
    db.session.add(MachineFuelParam(machine_id=1, equipment_group_id=1, database_version_id=1))
    db.session.add_all([
        EquipmentGroupFuelParam(equipment_group_id=1, year_number=2024, database_version_id=1,
                                b=100, gaz=20, mazut=10, ugol=70, kan=70),
        EquipmentGroupFuelParam(equipment_group_id=1, year_number=2025, database_version_id=1,
                                b=100, gaz=80, mazut=20),
        MachinePower(id_machine=1, year_number=2025, p_ust=Decimal('123.45'), database_version_id=1),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='steam', report_year=2024,
                                         equipment_kind='Паровая турбина', database_version_id=1,
                                         station_name='Устаревшая станция', subject_name='Устаревший собственник',
                                         installed_electric_power=999, equipment_brand='Устаревшая марка'),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='gas', report_year=2025,
                                         equipment_kind='Газовая турбина', database_version_id=1),
    ])
    db.session.commit()
    return calculation_database


def test_card_fields_override_workbook_and_characteristics(machine_sources):
    row = next(row for row in context()['rows'] if row['machine_id'] == 1)
    expected = {'A': '1', 'B': 'Регион Альфа', 'C': '002', 'E': 'Паровая турбина',
                'F': 'Собственник агрегата', 'G': 'ТЭЦ Альфа', 'H': '1',
                'K': 'Тип группы из карточки', 'L': 'Турбина Альфа', 'N': Decimal('0'), 'AM': 'Уголь'}
    for key, value in expected.items():
        assert row['values'][key] == value
    assert row['values']['AN'] == 0
    assert 'BK' not in row['values']
    assert row['errors'] == []
    assert context(equipment_type='Паровая турбина')['total'] == 1
    assert context(subject='Собственник')['total'] == 1


@pytest.mark.parametrize('equipment_type', ['steam', 'gas'])
def test_average_runtime_uses_selected_three_year_window_and_code(calculation_database, equipment_type):
    db.session.add_all([
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type=equipment_type,
                                         report_year=year, operating_hours_year=hours, database_version_id=1)
        for year, hours in ((2021, 100), (2022, 7938), (2023, 7905), (2024, 7677), (2025, 6000))
    ])
    db.session.add_all([
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type=equipment_type,
                                         report_year=2024, operating_hours_year=10, database_version_id=2),
        EquipmentTechnicalCharacteristic(equipment_code='003', equipment_type=equipment_type,
                                         report_year=2024, operating_hours_year=123, database_version_id=1),
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='boiler_energy',
                                         report_year=2024, operating_hours_year=20, database_version_id=1),
    ])
    db.session.commit()
    first = context()
    row = next(row for row in first['rows'] if row['values']['C'] == '002')
    assert row['values']['AN'] == 7840
    assert next(row for row in first['rows'] if row['values']['C'] == '003')['values']['AN'] == 123
    assert next(row for row in context(2025)['rows'] if row['values']['C'] == '002')['values']['AN'] == 7194
    assert all(row['values']['AN'] == 0 for row in context(2030)['rows'])
    filtered = context(column_AN='7840')
    assert filtered['total'] == 1
    exported = read_equipment_runtime_workbook(export_equipment_runtime(filtered).getvalue())
    assert exported['calculation']['rows'][0]['values']['AN'] == 7840
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    assert next(row for row in context()['rows'] if row['values']['C'] == '002')['values']['AN'] == 7840


@pytest.mark.parametrize('hours,expected', [
    ((7938, 0, 7677), Decimal('7807.5')),
    ((None, 7905, None), Decimal('7905')),
    ((None, 0, None), 0),
    ((0, 0, 0), 0),
    ((Decimal('10.25'), Decimal('20.5'), None), Decimal('15.375')),
    ((-10, 20, 0), Decimal('5')),
])
def test_average_runtime_ignores_only_null_and_zero_values(calculation_database, hours, expected):
    db.session.add_all([
        EquipmentTechnicalCharacteristic(equipment_code='002', equipment_type='steam',
                                         report_year=year, operating_hours_year=value, database_version_id=1)
        for year, value in zip((2022, 2023, 2024), hours)
    ])
    db.session.commit()
    row = next(row for row in context()['rows'] if row['values']['C'] == '002')
    assert row['values']['AN'] == expected


def test_calculated_average_replaces_saved_value_formula_and_error(calculation_database):
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    rows = workbook.data['calculation']['rows']
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], AN='#DIV/0!'),
             formulas=dict(row['formulas'], AN='=1/0'), errors=[*row['errors'], 'AN'])
        for row in rows
    ]))
    db.session.commit()
    result = context()
    assert result['table']['error_count'] == 0  # скрытые ошибки BK не учитываются в таблице
    for row in result['rows']:
        assert row['values']['AN'] == 0
        assert 'AN' not in row['formulas']
        assert 'AN' not in row['errors']


@pytest.mark.parametrize('field', MAIN_FUEL_FIELDS)
def test_reference_fuel_names_are_used_in_rows_filters_and_export(machine_sources, field):
    label = f'Название из справочника: {field}'
    db.session.execute(delete(Fuel).where(Fuel.database_version_id == 1))
    db.session.execute(insert(Fuel), {'name': label, 'nazvl': field.upper(), 'database_version_id': 1})
    params = db.session.scalar(select(EquipmentGroupFuelParam).where(
        EquipmentGroupFuelParam.equipment_group_id == 1, EquipmentGroupFuelParam.year_number == 2024))
    for key in MAIN_FUEL_FIELDS:
        setattr(params, key, 100 if key == field else 0)
    db.session.commit()
    result = context(column_AM=label)
    assert result['total'] == 1
    assert result['rows'][0]['values']['AM'] == label
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert exported['calculation']['rows'][0]['values']['AM'] == label


def test_fuel_name_map_preserves_current_version_default_and_supports_explicit_version(machine_sources, monkeypatch):
    monkeypatch.setattr('app.common.services.database_version_filter.get_current_db_version_id', lambda: 1)
    assert build_fuel_nazvl_to_name_map() == {'ugol': 'Уголь', 'gaz': 'Газ природный'}
    assert build_fuel_nazvl_to_name_map(2) == {'ugol': 'Уголь другой версии'}


def test_missing_fuel_name_does_not_use_another_version_or_raw_code(machine_sources):
    db.session.execute(delete(Fuel).where(Fuel.database_version_id == 1))
    db.session.commit()
    row = next(row for row in context()['rows'] if row['machine_id'] == 1)
    assert row['values']['AM'] is None


def test_selected_year_changes_values_not_aggregate_inventory(machine_sources):
    first, second = context(), context(2025)
    assert {(row['machine_id'], row['pgu_machine_id']) for row in first['rows']} == {
        (row['machine_id'], row['pgu_machine_id']) for row in second['rows']}
    row = next(row for row in second['rows'] if row['machine_id'] == 1)
    assert row['values']['N'] == pytest.approx(Decimal('123.45'))
    assert row['values']['AM'] == 'Газ природный'
    assert row['values']['E'] == 'Газовая турбина'
    assert row['values']['AN'] == 0
    assert row['errors'] == []
    missing = next(row for row in context(2030)['rows'] if row['machine_id'] == 1)
    assert missing['values']['N'] is None and missing['values']['AM'] is None
    assert missing['values']['E'] == 'Газовая турбина'  # вид доступен по коду даже без отчета за выбранный год


def test_uncoded_archived_and_pgu_aggregates_survive_without_workbook(machine_sources):
    db.session.execute(insert(Machine), {
        'id': 3, 'id_station': 1, 'machine_number': '3', 'machine_name': 'Без кода',
        'external_code': 'machine-3', 'is_archived': True, 'database_version_id': 1})
    db.session.execute(insert(PGUMachine), {
        'id': 1, 'id_parent_machine': 3, 'machine_number': '3ГТ', 'machine_name': 'Компонент ПГУ',
        'database_version_id': 1})
    db.session.add(PGUMachinePower(id_pgu_machine=1, year_number=2024, p_ust=45, database_version_id=1))
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    result = context()
    assert result['workbook'] is None
    assert result['total'] == 3
    uncoded = [row for row in result['rows'] if row['machine_id'] == 3]
    assert len(uncoded) == 1
    assert all(row['values']['C'] is None for row in uncoded)
    assert next(row for row in uncoded if row['pgu_machine_id'])['values']['N'] == 45
    assert context(column_C='__empty__')['total'] == 1
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert len(exported['calculation']['rows']) == 3
    assert sum(not row['values']['C'] for row in exported['calculation']['rows']) == 1


def test_only_tes_and_current_version_including_when_year_data_missing(machine_sources):
    db.session.execute(insert(StationType), {'id': 2, 'name': 'ГЭС', 'database_version_id': 1})
    for station_id, kind, version in ((3, 2, 1), (4, 1, 2)):
        db.session.execute(insert(Station), {'id': station_id, 'name': f'Иная станция {station_id}',
                                           'id_station_type': kind, 'database_version_id': version,
                                           'external_code': f'station-{station_id}'})
        db.session.execute(insert(Machine), {'id': station_id, 'id_station': station_id, 'machine_number': '1',
                                           'machine_name': 'Иной агрегат', 'database_version_id': version,
                                           'external_code': f'machine-{station_id}'})
    db.session.commit()
    assert context()['total'] == 2
    assert context(version=2)['total'] == 1
    assert context(version=2)['rows'][0]['machine_id'] == 4
    assert context(version=None)['total'] == 0


def test_group_inferred_only_for_unique_station_type_link(machine_sources):
    binding = db.session.scalar(select(MachineFuelParam).where(MachineFuelParam.machine_id == 1))
    binding.equipment_group_id = None
    db.session.commit()
    assert context()['rows'][0]['values']['AM'] == 'Уголь'
    db.session.execute(insert(EquipmentGroup), {'id': 2, 'external_code': 'group-2', 'database_version_id': 1})
    db.session.execute(insert(EquipmentGroupSet), {'equipment_group_id': 2, 'equipment_group_set_station_id': 1})
    db.session.commit()
    assert context()['rows'][0]['values']['AM'] is None
    binding.equipment_group_id = 1
    db.session.commit()
    assert context()['rows'][0]['values']['AM'] == 'Уголь'


def test_characteristics_and_saved_rows_do_not_add_or_replace_aggregates_from_other_versions(machine_sources):
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='gas', equipment_kind='Чужая версия', report_year=2024,
        database_version_id=2))
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        *workbook.data['calculation']['rows'],
        {'source_row': 999, 'values': {'C': 'orphan', 'D': 2024, 'G': 'Только в Excel'},
         'formulas': {}, 'errors': []},
    ]))
    db.session.commit()
    result = context()
    assert result['total'] == 2
    assert result['rows'][0]['values']['E'] == 'Паровая турбина'
    assert all(row['values']['C'] != 'orphan' for row in result['rows'])


def test_pgu_component_replaces_shell_and_does_not_inherit_shell_code(machine_sources):
    db.session.execute(insert(PGUMachine), {'id': 1, 'id_parent_machine': 1, 'machine_number': '1ГТ',
                                          'machine_name': 'Газовая часть', 'database_version_id': 1})
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='0007', equipment_type='gas', equipment_kind='Газовая турбина', report_year=2024,
        machine_id=1, pgu_machine_id=1, match_status='matched', database_version_id=1,
        operating_hours_year=321, standard_service_life='1000', operating_hours_total=500))
    db.session.commit()
    rows = [row for row in context()['rows'] if row['machine_id'] == 1]
    assert len(rows) == 1
    assert all(row['pgu_machine_id'] is not None for row in rows)
    part = next(row for row in rows if row['pgu_machine_id'] == 1)
    assert part['values']['C'] == '0007'
    assert part['values']['E'] == 'Газовая турбина'
    assert part['values']['AN'] == 321
    assert part['values']['AO'] == 1500
    assert part['values']['AP'] == 2029
    assert part['values']['AQ'] == 2026


@pytest.mark.parametrize('values,expected', [({}, None), ({'gaz': 0, 'mazut': -1}, None),
                                          ({'gaz': 20, 'mazut': 70, 'proch': 10}, 'MAZUT'),
                                          ({'gaz': 20, 'proch': 80}, 'PROCH')])
def test_main_fuel_uses_largest_positive_consumption(values, expected):
    params = SimpleNamespace(**dict.fromkeys(MAIN_FUEL_FIELDS))
    for key, value in values.items():
        setattr(params, key, value)
    assert main_fuel(params) == expected
    assert main_fuel(None) is None
