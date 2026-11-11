import re
from decimal import Decimal
from html import unescape

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context, machine_sources
from test_equipment_runtime_modernization import set_current_year
from test_equipment_runtime_planned_events import planned_card
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_machine_services import _dismantling_transfers
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.refdata.models.years.year_service_model import YearService


@pytest.mark.parametrize('total,supply,scheduled,end,sipr,expected', [
    (2040, 2023, 0, 2042, 2032, (2038, 2038)),
    (2040, 2010, 0, 2042, 2032, (2025, 2033)),
    (2040, 2010, 2028, 2042, 2032, (2025, 2025)),
    (2040, 2017, 0, 2042, 2032, (2032, 2033)),
    (2040, 2018, 0, 2042, 2032, (2033, 2033)),
    (2040, 2027, None, 2042, 2032, (2042, 2042)),
    (2040, 2028, 0, 2042, 2032, (0, 0)),
    (2040, 2033, 0, 2048, 2038, (2048, 2048)),
    (2040, 2034, 0, 2048, 2038, (0, 0)),
    (2040, 2020, None, 2048, 2038, (2035, 2039)),
    (2040, 2020, 2030, 2048, 2038, (2035, 2035)),
    (0, 2030, 0, None, None, (0, 0)),
    (None, 2030, 0, 2048, 2038, (None, None)),
    (-1, 2030, 0, None, None, (-1, -1)),
    (2030, 0, 0, 2042, 2032, (2030, 2033)),
    (2030, None, None, 2042, 2032, (2030, 2033)),
    (2030, 0, 2030, None, None, (2030, 2030)),
    (2030, 2020, 2030, None, 2038, (None, None)),
    (2030, 0, 0, None, None, (2030, None)),
    (2040, None, 0, None, 2038, (2040, 2040)),
    (2040, 2034, 0, 2048, None, (0, 0)),
    (2040, 2020, 2030, 2048, None, (2035, 2035)),
    (2040, 2020, 0, 2048, None, (2035, None)),
    (2030, None, -1, None, None, (2030, 2030)),
    (Decimal('2031.75'), None, None, None, 2032, (Decimal('2031.75'), 2033)),
])
def test_transfers_follow_excel_branch_order_and_dynamic_periods(total, supply, scheduled, end, sipr, expected):
    result = _dismantling_transfers({'AY': total, 'AU': supply, 'AT': scheduled}, end, sipr)
    assert (result['AZ'], result['BA']) == expected


def test_transfers_replace_excel_and_feed_bc_filters_and_export_without_workbook(machine_sources):
    set_current_year(2030)
    db.session.add_all([
        YearService(database_version_id=1, year_sipr_end=2038),
        YearService(database_version_id=2, year_sipr_end=2099),
    ])
    characteristics = {row.report_year: row for row in db.session.scalars(select(EquipmentTechnicalCharacteristic))}
    characteristics[2024].commissioning_year = 1972
    characteristics[2025].commissioning_year = 2000
    characteristics[2025].standard_service_life = '20'
    machine = db.session.get(Machine, 1)
    machine.date_exploitation_expected = 2020
    machine.date_modernization_power_change_expected = 2035
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    keys = ('AZ', 'BA', 'BC')
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], **dict.fromkeys(keys, '#VALUE!')),
             formulas=dict(row['formulas'], **dict.fromkeys(keys, '=1/0')), errors=[*row['errors'], *keys])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    result = context(column_AZ='2035', column_BA='2039', column_BC='2042')
    assert result['total'] == 1
    row = result['rows'][0]
    assert row['values']['AY'] == 2042
    assert not set(keys) & set(row['errors'])
    assert not set(keys) & set(row['formulas'])
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert tuple(exported['calculation']['rows'][0]['values'][key] for key in keys) == (2035, 2039, 2042)
    machine.date_exploitation_expected = 2034
    db.session.commit()
    assert context(column_AZ='0', column_BA='0', column_BC='0')['total'] == 1
    machine.date_exploitation_expected = 2030
    db.session.commit()
    set_current_year(2024)
    assert context(column_AZ='0')['total'] == 1
    set_current_year(2030)
    assert context(column_AZ='2045', column_BA='2045', column_BC='2045')['total'] == 1
    service = db.session.scalar(select(YearService).where(YearService.database_version_id == 1))
    service.year_sipr_end = 2046
    db.session.commit()
    assert context(column_AZ='2045', column_BA='2047', column_BC='2047')['total'] == 1
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    machine.date_exploitation_expected = 0
    service.year_sipr_end = 2038
    db.session.commit()
    for year, expected in ((2024, '2042'), (2025, '2040')):
        result = context(year, column_AZ=expected, column_BA=expected)
        assert result['total'] == 1
        assert result['workbook'] is None
    assert context(version=2)['rows'] == []


@pytest.mark.parametrize('outcome,expected', [
    ('новый ввод', (2035, 2039)),
    ('окончательный вывод', (2030, 2030)),
])
def test_transfers_use_component_card_not_pgu_shell(machine_sources, planned_card, outcome, expected):
    parent, card = planned_card
    parent.relabing_outcome = outcome
    card.date_exploitation_expected = 2020
    card.date_decompressing_expected = 2030
    characteristic = db.session.scalar(select(EquipmentTechnicalCharacteristic).where(
        EquipmentTechnicalCharacteristic.equipment_code == '002', EquipmentTechnicalCharacteristic.report_year == 2024))
    characteristic.commissioning_year = 1972
    db.session.add(YearService(database_version_id=1, year_sipr_end=2038))
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    set_current_year(2030)
    row = next(row for row in context()['rows'] if row['machine_id'] == parent.id)
    assert (row['values']['AZ'], row['values']['BA']) == expected


def test_transfer_headers_explain_sources_and_missing_values_render_as_dash(machine_sources, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    set_current_year(2030)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2038))
    db.session.commit()
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?year=2024&column_C=002')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    headers = re.search(r'<thead.*?</thead>', html, re.S).group()
    for key, terms in (
            ('AZ', ('«Плановый год ввода оборудования» + 15', '«Базовый год демонтажа»', '2048')),
            ('BA', ('«Год демонтажа с учетом КОМ»', '«Плановый год окончательного вывода» = 0', '2039'))):
        label = dict(RUNTIME_COLUMNS)[key]
        button = re.search(r'<button\b[^>]*aria-label="Формула: ' + re.escape(label) + r'"[^>]*>', headers).group()
        assert 'data-bs-html="true"' in button
        assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
        text = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
        assert text.count('<p>') >= 2 and '<strong>' in text
        assert all(term in text for term in terms)
    body = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
    cells = re.findall(r'<td\b[^>]*>(.*?)</td>', body, re.S)
    columns = [key for key, _ in RUNTIME_COLUMNS]
    assert all(cells[columns.index(key)].strip() == '–' for key in ('AZ', 'BA'))
    assert 'BA пока берется из загруженной книги' not in html
