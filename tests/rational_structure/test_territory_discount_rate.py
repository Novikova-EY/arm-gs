from copy import deepcopy
from io import BytesIO
import re

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import MultiDict

from test_territory_data import (
    database, http_client, territory_database, territory_client, posted_table,
)
from app.extensions import db
from app.rational_structure.models import TerritoryDiscountRate, TerritoryInput
from app.rational_structure.services.territory_cell_services import save_territory_cell
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view
from app.rational_structure.services.territory_input_services import (
    build_territory_input_context, save_territory_inputs,
)


ENDPOINT = '/rational_structure/territory_inputs/cell'


def payload(**changes):
    return dict(dict(database_version_id=1, energy_zone_id=0, sheet='years', row_key='24',
                     year=2026, field='value', value='5,123456789'), **changes)


def rate_context(zone=0, version=1, **args):
    context = prepare_territory_input_view(build_territory_input_context(version, zone), MultiDict(args))
    row = next(row for row in context['rows'] if row['key'] == '24')
    return context, row


def test_rate_renders_editable_only_in_ees_with_csrf_and_admin_access(territory_client):
    client, user = territory_client
    query = dict(energy_zone_id=0, start_year=2024, end_year=2042)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'data-zone-id="0"' in html
    assert 'name="value_24_2024"' in html and 'name="value_24_2042"' in html
    assert all(name.startswith('24_') for name in re.findall(r'name="value_([^"]+)"', html))
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    assert client.patch(ENDPOINT, json=payload()).status_code == 400
    response = client.patch(ENDPOINT, json=payload(), headers={'X-CSRFToken': token})
    assert response.status_code == 200
    assert response.json['year_values']['2042'] == '5.123456789'
    zone_html = client.get('/rational_structure/territory_inputs?energy_zone_id=1').get_data(as_text=True)
    assert 'name="value_24_' not in zone_html and 'name="note_24"' not in zone_html
    assert 'data-raw-value="5.123456789"' in zone_html
    assert 'name="value_6_' in zone_html
    user.has_admin = False
    html = client.get('/rational_structure/territory_inputs', query_string=query).get_data(as_text=True)
    assert 'name="value_24_' not in html
    assert client.patch(ENDPOINT, json=payload(), headers={'X-CSRFToken': token}).status_code == 403


def test_rate_prolongs_to_real_end_not_visible_range_and_preserves_previous_years(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    assert client.patch(ENDPOINT, json=payload(year=2024, value='4')).status_code == 200
    response = client.patch(ENDPOINT, json=payload())
    assert response.status_code == 200
    assert response.json['year_values'] == {str(year): '5.123456789' for year in range(2026, 2043)}
    for zone in (0, 1, 2):
        context, row = rate_context(zone, start_year='2024', end_year='2027')
        assert row['cells'] == ['4', '4', '5.123456789', '5.123456789']
        assert row['readonly'] == (zone != 0)
        assert row['note_readonly']
        assert context['years'] == [2024, 2025, 2026, 2027]
    context, row = rate_context(0, start_year='2025', end_year='2028', view_year='2027')
    assert context['years'] == [2027] and row['cells'] == ['5.123456789']
    assert db.session.get(TerritoryDiscountRate, 1).year_values['2042'] == '5.123456789'
    assert db.session.scalar(select(TerritoryInput)) is None


def test_rate_clear_prolongs_and_isolated_by_version(territory_client):
    save_territory_cell('inputs', payload(year=2025, value='0'), 1, 'tester')
    save_territory_cell('inputs', payload(database_version_id=2, year=2025, value='9'), 2, 'tester')
    result = save_territory_cell('inputs', payload(year=2027, value=''), 1, 'tester')
    assert result['year_values']['2042'] == ''
    assert rate_context(1, start_year='2025', end_year='2028')[1]['cells'] == ['0', '0', '', '']
    assert rate_context(3, version=2, start_year='2025', end_year='2028')[1]['cells'] == ['9'] * 4


@pytest.mark.parametrize('change', [
    {'energy_zone_id': 1}, {'energy_zone_id': 2}, {'energy_zone_id': False},
    {'database_version_id': 2}, {'row_key': '6'}, {'row_key': '0'},
    {'sheet': 'equipment'}, {'field': 'note'}, {'year': 2099}, {'year': True},
    {'value': 'NaN'}, {'value': 'Infinity'}, {'value': '=1+1'}, {'value': '1e16'},
])
def test_rate_rejects_wrong_scope_fields_and_values(territory_client, change):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    response = client.patch(ENDPOINT, json=payload(**change))
    assert response.status_code in (400, 404)
    assert not response.json['ok']
    assert db.session.get(TerritoryDiscountRate, 1) is None
    assert db.session.scalar(select(TerritoryInput)) is None


@pytest.mark.parametrize('existing', [False, True])
def test_rate_save_failure_is_atomic_and_retry_succeeds(territory_client, monkeypatch, existing):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    if existing:
        assert client.patch(ENDPOINT, json=payload(value='4')).status_code == 200
    before = deepcopy(db.session.get(TerritoryDiscountRate, 1).year_values) if existing else None
    commit = db.session.commit

    def fail():
        raise SQLAlchemyError('storage unavailable')

    monkeypatch.setattr(db.session, 'commit', fail)
    response = client.patch(ENDPOINT, json=payload())
    assert response.status_code == 500 and not response.json['ok']
    record = db.session.get(TerritoryDiscountRate, 1)
    assert (record.year_values if record else None) == before
    monkeypatch.setattr(db.session, 'commit', commit)
    assert client.patch(ENDPOINT, json=payload()).status_code == 200
    assert db.session.get(TerritoryDiscountRate, 1).year_values['2042'] == '5.123456789'


def test_legacy_zone_rates_are_ignored_and_bulk_save_cannot_change_shared_rate(territory_client):
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form['value_24_2025'] = '999'
    form['note_24'] = 'Не должно сохраняться'
    save_territory_inputs(context, form, 'tester')
    assert db.session.scalar(select(TerritoryInput)).rows[24]['values'][0] is None
    assert db.session.scalar(select(TerritoryInput)).rows[24]['note'] == ''
    record = db.session.scalar(select(TerritoryInput))
    legacy = deepcopy(record.rows)
    legacy[24]['values'][0] = '888'
    record.rows = legacy
    db.session.commit()
    assert rate_context(1)[1]['cells'][0] == ''
    save_territory_cell('inputs', payload(year=2025, value='5'), 1, 'tester')
    assert rate_context(1)[1]['cells'][0] == '5'
    assert rate_context(0)[1]['cells'][0] == '5'
    assert db.session.get(TerritoryInput, record.id).rows[24]['values'][0] == '888'


def test_rate_export_matches_ees_in_all_zones(territory_client):
    save_territory_cell('inputs', payload(year=2024, value='7.25'), 1, 'tester')
    client, _ = territory_client
    for zone in (0, 1, 2):
        response = client.get('/rational_structure/territory_inputs/export', query_string=dict(
            energy_zone_id=zone, start_year=2024, end_year=2026))
        assert response.status_code == 200
        book = load_workbook(BytesIO(response.data))
        try:
            row = next(row for row in book.active.iter_rows(values_only=True) if row[1] == 'Ставка дисконтирования')
            assert row[0] == '16' and row[3:6] == (7.25, 7.25, 7.25)
        finally:
            book.close()
