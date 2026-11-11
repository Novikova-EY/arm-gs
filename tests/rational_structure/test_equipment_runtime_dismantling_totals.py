import re
from html import unescape
from types import SimpleNamespace

import pytest
from flask.templating import render_template
from sqlalchemy import delete, select

from test_calculation_pages import calculation_database
from test_equipment_runtime_machine_sources import context, machine_sources
from test_equipment_runtime_modernization import set_current_year
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.rational_structure.models import CalculationWorkbook, EquipmentTechnicalCharacteristic
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_COLUMNS
from app.rational_structure.services.equipment_runtime_excel_services import export_equipment_runtime
from app.rational_structure.services.equipment_runtime_machine_services import _dismantling_years
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.years.year_service_model import YearService


@pytest.mark.parametrize('coal,commissioning,scheduled,resource,year,end,sipr,expected', [
    (True, 1983, 2025, 2046, 2024, 2042, 2032, (2025, 0, 2025)),
    (True, 1983, 0, 2046, 2024, 2042, 2032, (0, 0, 0)),
    (False, 1980, 0, 2042, 2024, 2042, 2032, (0, 2042, 2042)),
    (False, 1980, 0, 2037, 2024, 2042, 2032, (0, 2037, 2037)),
    (True, 1972, None, 2090, 2024, 2042, 2032, (2042, 0, 2042)),
    (True, 1973, None, 2030, 2024, 2042, 2032, (0, 0, 0)),
    (True, 1978, None, 2090, 2025, 2048, 2036, (2048, 0, 2048)),
    (False, 1970, None, 2048, 2025, 2048, 2036, (0, 2048, 2048)),
    (False, 1970, None, 2049, 2025, 2048, 2036, (0, 0, 0)),
    (True, 1954, None, 2040, 2024, 2042, 2038, (2024, 0, 2039)),
    (True, 1955, None, 2040, 2024, 2042, 2038, (2025, 0, 2025)),
    (False, 1980, None, 2025, 2025, 2042, 2038, (0, 2025, 2039)),
    (False, 1980, None, 2026, 2025, 2042, 2038, (0, 2026, 2026)),
    (False, 1980, 2020, 2030, 2025, 2042, 2038, (0, 2020, 2020)),
    (True, None, 2099, 0, 2025, None, None, (2099, 0, 2099)),
    (False, None, 2099, 0, 2025, None, None, (0, 2099, 2099)),
    (True, None, None, 0, 2025, 2042, 2032, (None, 0, None)),
    (True, 1970, None, 0, 2025, None, 2032, (None, 0, None)),
    (False, None, None, 2030, 2025, None, 2032, (0, None, None)),
    (False, None, None, 0, 2025, None, None, (0, 0, 0)),
    (False, None, None, -1, 2025, 2042, 2032, (0, 0, 0)),
    (False, None, None, 2024, 2025, 2042, None, (0, 2024, None)),
    (None, 1980, None, 2030, 2025, 2042, 2032, (None, None, None)),
    (None, 1980, 2031, 2030, 2025, 2042, 2032, (None, None, 2031)),
])
def test_dismantling_branch_order_and_dynamic_limits(
        coal, commissioning, scheduled, resource, year, end, sipr, expected):
    characteristic = SimpleNamespace(commissioning_year=commissioning) if commissioning is not None else None
    result = _dismantling_years(characteristic, {'AT': scheduled, 'AP': resource}, coal, year, end, sipr)
    assert tuple(result[key] for key in ('AW', 'AX', 'AY')) == expected


def test_live_fuel_resource_plan_and_reference_periods_replace_excel(machine_sources):
    set_current_year(2030)
    db.session.add_all([
        YearService(database_version_id=1, year_sipr_end=2038),
        YearService(database_version_id=2, year_sipr_end=2099),
    ])
    characteristics = {row.report_year: row for row in db.session.scalars(select(EquipmentTechnicalCharacteristic))}
    characteristics[2024].commissioning_year = 1978
    characteristics[2024].standard_service_life = '35'
    characteristics[2025].commissioning_year = 1980
    characteristics[2025].standard_service_life = '20'
    coal_name = db.session.scalar(select(Fuel).where(Fuel.database_version_id == 1, Fuel.nazvl == 'UGOL'))
    coal_name.name = 'Каменный уголь (название из справочника)'
    workbook = db.session.scalar(select(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    keys = ('AW', 'AX', 'AY')
    workbook.data = dict(workbook.data, calculation=dict(workbook.data['calculation'], rows=[
        dict(row, values=dict(row['values'], **dict.fromkeys(keys, '#VALUE!')),
             formulas=dict(row['formulas'], **dict.fromkeys(keys, '=1/0')), errors=[*row['errors'], *keys])
        for row in workbook.data['calculation']['rows']
    ]))
    db.session.commit()
    result = context(column_AW='2048', column_AY='2048')
    assert result['total'] == 1
    assert result['sipr_end_year'] == 2038
    assert result['general_scheme_end_year'] == 2048
    row = result['rows'][0]
    assert row['values']['AM'] == coal_name.name
    assert row['values']['AX'] == 0
    assert not set(keys) & set(row['errors'])
    assert not set(keys) & set(row['formulas'])
    exported = read_equipment_runtime_workbook(export_equipment_runtime(result).getvalue())
    assert exported['calculation']['rows'][0]['values']['AY'] == 2048
    result = context(2025, column_AX='2020', column_AY='2039')
    assert result['total'] == 1
    assert result['rows'][0]['values']['AW'] == 0
    service = db.session.scalar(select(YearService).where(YearService.database_version_id == 1))
    service.year_sipr_end = 2039
    db.session.commit()
    assert context(2025, column_AY='2040')['total'] == 1
    machine = db.session.get(Machine, 1)
    machine.relabing_outcome = 'окончательный вывод'
    machine.date_decompressing_expected = 2090
    db.session.execute(delete(CalculationWorkbook).where(CalculationWorkbook.kind == 'equipment_runtime'))
    db.session.commit()
    for year in (2024, 2025):
        result = context(year, column_AY='2090')
        assert result['total'] == 1
        assert result['rows'][0]['values']['AY'] == 2090
        assert result['rows'][0]['values']['AW' if year == 2024 else 'AX'] == 2090


def test_dismantling_headers_have_formatted_explanations(machine_sources, http_client, monkeypatch):
    from app.rational_structure.routes import equipment_runtime_routes as routes
    monkeypatch.setattr(routes, 'render_template', render_template)
    set_current_year(2030)
    db.session.add(YearService(database_version_id=1, year_sipr_end=2038))
    db.session.commit()
    client, _ = http_client
    response = client.get('/rational_structure/equipment_runtime?year=2025')
    assert response.status_code == 200
    headers = re.search(r'<thead.*?</thead>', response.get_data(as_text=True), re.S).group()
    for key, term in (('AW', '«Год ввода оборудования в эксплуатацию» + 70'),
                      ('AX', '«Расчетный год демонтажа по ресурсу» ≤'),
                      ('AY', '«Год демонтажа угольного оборудования» + «Год демонтажа неугольного оборудования»')):
        label = dict(RUNTIME_COLUMNS)[key]
        button = re.search(r'<button\b[^>]*aria-label="Формула: ' + re.escape(label) + r'"[^>]*>', headers).group()
        assert 'data-bs-html="true"' in button
        assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in button
        help_text = unescape(re.search(r'\btitle="([^"]*)"', button).group(1))
        assert help_text.count('<p>') >= 4 and '<strong>' in help_text
        assert term in help_text
        if key == 'AY':
            assert '2026' in help_text and '2039' in help_text
        else:
            assert '2048' in help_text
