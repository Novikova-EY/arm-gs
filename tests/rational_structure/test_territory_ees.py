from decimal import Decimal
from html import unescape
from io import BytesIO
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

from test_territory_data import (
    database, http_client, territory_database, territory_client, posted_table,
)
from app.extensions import db
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs,
)


def seed_values():
    for zone, value in ((1, '123.4567890123'), (2, '-23.4567890122'), (3, '9999')):
        context = build_territory_input_context(2 if zone == 3 else 1, zone, sheet='equipment')
        form = posted_table(context)
        form['value_164_2025'] = value
        form['value_164_2026'] = '0'
        form['note_164'] = 'Примечание отдельной зоны'
        save_territory_inputs(context, form, 'tester')


def test_ees_sums_exact_values_zero_and_missing_with_version_isolation(territory_database):
    seed_values()
    context = build_territory_input_context(1, 0, sheet='equipment')
    rows = {row['key']: row for row in context['rows']}
    assert context['is_ees'] and context['selected_zone'] is None
    assert rows['164']['cells'][:3] == ['100.0000000001', '0', '']
    assert rows['164']['note'] == ''
    assert all(row['readonly'] for row in rows.values())
    with pytest.raises(ValueError, match='Выберите энергозону'):
        save_territory_inputs(context, posted_table(context), 'tester')


@pytest.mark.parametrize('sheet', ['years', 'equipment'])
def test_ees_navigation_filters_export_and_write_protection(territory_client, sheet):
    seed_values()
    client, _ = territory_client
    query = dict(energy_zone_id=0, sheet=sheet, start_year=2025, end_year=2027, rounding_digits=2)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    nav = re.search(r'<nav[^>]*aria-label="Энергозоны".*?</nav>', html, re.S).group()
    assert re.findall(r'>([^<>]+)</a>', nav) == ['ЕЭС России', '1', '2']
    assert 'aria-current="page"' in nav.split('</a>')[0]
    assert '– ЕЭС России</h1>' in html
    assert 'name="note_' not in html
    value_names = re.findall(r'name="value_([^\"]+)"', html)
    assert all(name.startswith('24_') for name in value_names)
    assert bool(value_names) == (sheet == 'years')
    assert 'name="energy_zone_id" value="0"' in html
    for href in re.findall(r'href="([^"]+)"', html):
        url = urlsplit(unescape(href))
        if url.path.endswith('/territory_inputs') and 'energy_zone_id=0' in url.query:
            assert parse_qs(url.query)['energy_zone_id'] == ['0']
    page_nav = re.search(r'<nav[^>]*rs-page-nav.*?</nav>', html, re.S).group()
    assert page_nav.count('energy_zone_id=0') == 2
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200 and 'territory_inputs_ees_' in response.headers['Content-Disposition']
    book = load_workbook(BytesIO(response.data))
    try:
        assert book.active['A1'].value == 'ЕЭС России'
        assert [book.active.cell(2, col).value for col in (4, 5, 6)] == [2025, 2026, 2027]
        if sheet == 'equipment':
            hydro = [row for row in book.active.iter_rows(min_row=3, values_only=True)
                     if row[1] == 'ГЭС до 50 МВт'][1]
            assert hydro[3] == pytest.approx(100.0000000001)
            assert hydro[4] == 0
            assert hydro[5] is None
    finally:
        book.close()
    client.application.config['WTF_CSRF_ENABLED'] = False
    assert client.post('/rational_structure/territory_inputs', query_string=query).status_code == 403
    for field in ('value', 'note'):
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=0, sheet=sheet, row_key='164' if sheet == 'equipment' else '6',
            year=2025, field=field, value='10'))
        assert response.status_code == 400 and not response.json['ok']
    assert db.session.query(TerritoryInput).count() == 3


def test_ees_uses_national_summary_and_sums_only_other_rows(territory_client, monkeypatch):
    from app.rational_structure.services import territory_summary_services, territory_transfer_services

    def summary(version, zone, years):
        assert zone is None
        return dict(has_gaes=True, **{
            key: [Decimal(multiplier) if year == 2025 else None for year in years]
            for key, multiplier in [('consumption', 8760), ('consumption_with_gaes', 9000),
                                    ('max_power', 1200), ('combined', 500), ('hours', 4321)]})

    def transfers(version, zone, years):
        return {key: {'cells': [str(zone * sign) if year == 2025 else '' for year in years],
                      'details': [{'label': f'Связь зоны {zone}', 'cells': ['999'] * len(years)}]}
                for key, sign in [('7', -10), ('9', 20)]}

    monkeypatch.setattr(territory_summary_services, 'load_territory_summary_values', summary)
    monkeypatch.setattr(territory_transfer_services, 'load_territory_transfer_rows', transfers)
    context = prepare_territory_input_view(build_territory_input_context(1, 0), MultiDict(
        {'start_year': '2025', 'end_year': '2026'}))
    rows = {row['key']: row for row in context['rows']}
    assert list(rows)[:2] == ['0', '0_with_gaes']
    assert rows['0']['number'] == '1.1'
    for key, value in [('0', '8760'), ('0_with_gaes', '9000'), ('1', '1200'),
                       ('2', '500'), ('3', '4321'), ('4', '1000'), ('5', '0.5'),
                       ('7', '-30'), ('9', '60')]:
        assert Decimal(rows[key]['cells'][0]) == Decimal(value)
        assert rows[key]['cells'][1] == ''
    assert not any(row.get('parent_key') for row in rows.values())
    assert all(not row['collapsible'] for row in rows.values())


def test_ees_aligns_different_record_years(territory_client):
    seed_values()
    record = db.session.query(TerritoryInput).filter_by(energy_zone_id=2).one()
    record.years = [2026, 2027]
    record.rows = [dict(row, values=row['values'][:2]) for row in record.rows]
    db.session.commit()
    context = prepare_territory_input_view(build_territory_input_context(1, 0, sheet='equipment'),
                                          MultiDict({'start_year': '2025', 'end_year': '2027'}))
    row = next(row for row in context['rows'] if row['key'] == '164')
    assert row['cells'] == ['123.4567890123', '-23.4567890122', '0']


def test_ees_without_zones_is_empty(territory_database):
    context = prepare_territory_input_view(build_territory_input_context(None, 0), MultiDict())
    assert context['is_ees'] and context['rows'] == [] and context['zones'] == []
