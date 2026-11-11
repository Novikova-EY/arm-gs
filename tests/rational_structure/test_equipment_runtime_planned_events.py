import re
from html import unescape

import pytest
from flask.templating import render_template
from sqlalchemy import delete, insert, select

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context
from test_equipment_runtime_modernization import set_current_year
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.station.station_model import Station
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic, TechnicalInspectionCode
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook


@pytest.fixture(params=[False, True], ids=['machine', 'pgu_component'])
def planned_card(calculation_database, request):
    parent = db.session.get(Machine, 1)
    card = parent
    if request.param:
        card = PGUMachine(id_parent_machine=parent.id, machine_number='1ГТ',
                          machine_name='Компонент ПГУ', database_version_id=1)
        db.session.add(card)
        db.session.flush()
        code = db.session.scalar(select(TechnicalInspectionCode).where(
            TechnicalInspectionCode.database_version_id == 1, TechnicalInspectionCode.equipment_code == '002'))
        code.pgu_machine_id = card.id
        parent.date_modernization_power_change_expected = 2090
        parent.date_exploitation_expected = 2091
        parent.date_decompressing_expected = 2092
    workbook = db.session.scalar(select(CalculationWorkbook).where(
        CalculationWorkbook.kind == 'equipment_runtime'))
    keys = ('planned_modernization_year', 'AT', 'AU', 'AV')
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], **dict.fromkeys(keys, '#VALUE!')),
             formulas=dict(row['formulas'], **dict.fromkeys(keys, '=1/0')), errors=[*row['errors'], *keys])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    return parent, card


@pytest.mark.parametrize('power,no_power,expected', [
    (None, None, None), (2032, None, 2032), (None, 2031, 2031),
    (2035, 2030, 2030), (2029, 2033, 2029), (2030, 2030, 2030), (0, 2030, 0),
])
def test_sipr_uses_earliest_filled_expected_year(planned_card, power, no_power, expected):
    _, card = planned_card
    card.date_modernization_power_change_expected = power
    card.date_modernization_no_power_change_expected = no_power
    card.date_relabing_fact = '01.02.2040'
    db.session.commit()
    row = next(row for row in context()['rows'] if row['machine_id'] == 1)
    assert row['values']['planned_modernization_year'] == expected
    for key in ('planned_modernization_year', 'AT', 'AU', 'AV'):
        assert key not in row['formulas']
        assert key not in row['errors']


@pytest.mark.parametrize('outcome,expected', [
    (None, (None, 2031, None)), ('', (None, 2031, None)),
    ('не указано', (None, 2031, None)), ('новый ввод', (None, 2031, None)),
    ('окончательный вывод', (2037, None, None)), ('замена', (None, None, 2037)),
    ('другое', (None, None, None)),
])
def test_expected_years_use_state_change_not_fact_dates(planned_card, outcome, expected):
    parent, card = planned_card
    parent.relabing_outcome = outcome
    card.date_exploitation_expected = 2031
    card.date_decompressing_expected = 2037
    card.date_exploitation = 1980
    card.date_decompressing_fact = '01.02.2040'
    db.session.commit()
    for year in (2024, 2025):
        row = next(row for row in context(year)['rows'] if row['machine_id'] == 1)
        assert tuple(row['values'][key] for key in ('AT', 'AU', 'AV')) == expected
        assert row['pgu_machine_id'] == (card.id if isinstance(card, PGUMachine) else None)


@pytest.mark.parametrize('outcome,key', [('новый ввод', 'AU'), ('окончательный вывод', 'AT'), ('замена', 'AV')])
@pytest.mark.parametrize('year', [None, 0])
def test_missing_year_is_dash_and_zero_is_preserved(planned_card, outcome, key, year):
    parent, card = planned_card
    parent.relabing_outcome = outcome
    card.date_exploitation_expected = year
    card.date_decompressing_expected = year
    db.session.commit()
    row = next(row for row in context()['rows'] if row['machine_id'] == 1)
    assert row['values'][key] == year


def test_card_values_filter_export_and_work_without_excel(planned_card):
    parent, card = planned_card
    parent.relabing_outcome = 'замена'
    card.date_decompressing_expected = 2033
    card.date_modernization_no_power_change_expected = 2030
    db.session.commit()
    for remove_workbook in (False, True):
        if remove_workbook:
            db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
            db.session.commit()
        result = context(column_planned_modernization_year='2030', column_AV='2033')
        assert result['total'] == 1
        exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
        values = exported['calculation']['rows'][0]['values']
        assert values['planned_modernization_year'] == 2030
        assert values['AV'] == 2033
        assert values['AT'] is None and values['AU'] is None


def test_supply_from_card_feeds_modernization_not_excel(planned_card):
    parent, card = planned_card
    parent.relabing_outcome = 'новый ввод'
    card.date_exploitation_expected = 2035
    set_current_year(2024)
    db.session.add(EquipmentTechnicalCharacteristic(
        equipment_code='002', equipment_type='steam', report_year=2024, database_version_id=1,
        commissioning_year=1980, expected_service_life_year=2040))
    db.session.commit()
    row = next(row for row in context()['rows'] if row['machine_id'] == 1)
    assert row['values']['AU'] == 2035
    assert row['values']['AR'] == 2035


def test_planned_events_use_selected_database_version(calculation_database):
    db.session.execute(insert(Station), dict(id=3, name='Другая версия', id_station_type=1,
                                            external_code='station-v2', database_version_id=2))
    db.session.execute(insert(Machine), dict(id=3, id_station=3, machine_number='1', machine_name='Другой агрегат',
                                            external_code='machine-v2', database_version_id=2,
                                            date_exploitation_expected=2090,
                                            date_modernization_power_change_expected=2089))
    db.session.commit()
    assert all(row['values']['AU'] is None for row in context()['rows'])
    other = context(version=2)
    assert other['total'] == 1
    assert other['rows'][0]['values']['planned_modernization_year'] == 2089
    assert other['rows'][0]['values']['AU'] == 2090


def test_planned_event_help_and_pgu_inventory_render(planned_card, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    parent, card = planned_card
    parent.relabing_outcome = 'окончательный вывод'
    card.date_decompressing_expected = 2037
    db.session.commit()
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?year=2024&column_AT=2037')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    for key, term in (('planned_modernization_year', 'более ранний'), ('AT', 'окончательный вывод'),
                      ('AU', 'новый ввод'), ('AV', 'замена')):
        label = dict(RUNTIME_COLUMNS)[key]
        button = re.search(r'<button\b[^>]*aria-label="Формула: ' + re.escape(label) + r'"[^>]*>', headers).group()
        assert 'data-bs-html="true"' in button
        assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
        help_text = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
        assert '<strong>' in help_text and help_text.count('<p>') >= 2
        assert term in help_text
        assert 'выбранной версии базы' not in help_text
    if isinstance(card, PGUMachine):
        body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
        assert 'Компонент ПГУ' in body
        assert 'Турбина Альфа' not in body
