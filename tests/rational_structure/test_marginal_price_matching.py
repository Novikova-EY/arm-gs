from copy import deepcopy

import pytest
from flask.templating import render_template
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database, price_bytes
from test_technical_characteristics import database, http_client
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.station.station_model import Station
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.routes import marginal_price_routes
from app.rational_structure.services.marginal_price_matching_services import match_marginal_price_tables
from app.rational_structure.services.marginal_price_services import (
    build_marginal_price_context, import_marginal_price_workbook, read_marginal_price_workbook,
)


@pytest.fixture
def matched_database(calculation_database):
    db.session.execute(EquipmentGroup.__table__.insert(), [
        {'id': 10, 'name_ext': ' Восток  СТАНЦИЯ\u00a0', 'name': 'Другое название', 'external_code': 'g10', 'database_version_id': 1},
        {'id': 11, 'name_ext': 'Восток станция', 'name': 'Другое название', 'external_code': 'g11', 'database_version_id': 2},
        {'id': 12, 'name_ext': 'Только внешнее название', 'name': 'Юг станция', 'external_code': 'g12', 'database_version_id': 1},
    ])
    db.session.execute(Station.__table__.insert(), {'id': 3, 'name': 'Чужая станция', 'external_code': 's3', 'database_version_id': 2})
    db.session.execute(EquipmentGroupSetStation.__table__.insert(), [
        {'id': 30, 'station_id': 1, 'database_version_id': 1},
        {'id': 31, 'station_id': 3, 'database_version_id': 2},
    ])
    db.session.execute(EquipmentGroupSet.__table__.insert(), [
        {'equipment_group_id': 10, 'equipment_group_set_station_id': 30},
        {'equipment_group_id': 10, 'equipment_group_set_station_id': 31},
        {'equipment_group_id': 11, 'equipment_group_set_station_id': 31},
    ])
    db.session.commit()
    return calculation_database


def test_import_saves_matching_and_version_scoped_station_links(matched_database):
    import_marginal_price_workbook(price_bytes(), 1, 'tester', 'price.xlsx')
    db.session.remove()
    book = db.session.scalar(db.select(CalculationWorkbook).filter_by(database_version_id=1, kind='marginal_price'))
    for row in book.data['east']['rows']:
        assert row['match_status'] == 'matched'
        assert row['equipment_group_id'] == 10
        assert row['stations'] == [{'id': 1, 'name': 'ТЭЦ Альфа'}]
        assert row['values']['D'] == 'Восток станция'
    assert all(row['equipment_group_id'] is None for row in book.data['south']['rows'])
    assert all(row['match_status'] == 'not_found' for row in book.data['south']['rows'])
    import_marginal_price_workbook(price_bytes(), 2, 'tester', 'other.xlsx')
    book = db.session.scalar(db.select(CalculationWorkbook).filter_by(database_version_id=2, kind='marginal_price'))
    assert book.data['east']['rows'][0]['equipment_group_id'] == 11
    assert book.data['east']['rows'][0]['stations'] == [{'id': 3, 'name': 'Чужая станция'}]


def test_duplicate_name_is_not_assigned_to_random_group(matched_database):
    db.session.execute(EquipmentGroup.__table__.insert(), {
        'id': 13, 'name_ext': 'Восток станция', 'external_code': 'g13', 'database_version_id': 1,
    })
    db.session.commit()
    import_marginal_price_workbook(price_bytes(), 1, 'tester', 'ambiguous.xlsx')
    book = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    row = book.data['east']['rows'][0]
    assert row['match_status'] == 'ambiguous'
    assert row['equipment_group_id'] is None
    assert row['stations'] == []


def test_parenthetical_group_details_are_significant(matched_database):
    db.session.execute(EquipmentGroup.__table__.insert(), [
        {'id': 14, 'name_ext': 'ТЭС(ПГУ)', 'external_code': 'g14', 'database_version_id': 1},
        {'id': 15, 'name_ext': 'ТЭС(конд)', 'external_code': 'g15', 'database_version_id': 1},
    ])
    db.session.commit()
    tables = read_marginal_price_workbook(price_bytes())
    for row, name in zip(tables['east']['rows'], ['ТЭС(ПГУ)', 'ТЭС(конд)', 'ТЭС']):
        row['values']['D'] = name
    matched = match_marginal_price_tables(tables, 1)
    assert [row['equipment_group_id'] for row in matched['east']['rows']] == [14, 15, None]
    assert 'equipment_group_id' not in tables['east']['rows'][0]


def test_old_workbook_gets_links_and_live_station_changes_without_mutating_source(matched_database):
    saved = db.session.scalar(db.select(CalculationWorkbook).filter_by(kind='marginal_price'))
    original = deepcopy(saved.data)
    context = build_marginal_price_context(MultiDict({'territory': 'east'}), 1)
    assert context['rows'][0]['equipment_group_id'] == 10
    assert saved.data == original
    assert [col['key'] for col in context['table']['columns']][2:4] == ['D', 'station']
    db.session.execute(EquipmentGroupSetStation.__table__.insert(), {'id': 32, 'station_id': 2, 'database_version_id': 1})
    db.session.execute(EquipmentGroupSet.__table__.insert(), {'equipment_group_id': 10, 'equipment_group_set_station_id': 32})
    db.session.commit()
    context = build_marginal_price_context(MultiDict({'territory': 'east'}), 1)
    assert context['rows'][0]['stations'] == [{'id': 1, 'name': 'ТЭЦ Альфа'}, {'id': 2, 'name': 'ТЭЦ Бета'}]
    db.session.execute(EquipmentGroup.__table__.delete().where(EquipmentGroup.id == 10))
    db.session.commit()
    assert build_marginal_price_context(MultiDict({'territory': 'east'}), 1)['rows'][0]['equipment_group_id'] is None


def test_table_links_and_headers_and_export_roundtrip(matched_database, http_client, monkeypatch):
    app = matched_database
    app.add_url_rule('/fuel/stations_equipment_groups/equipment_group/<int:equipment_group_id>',
                     endpoint='fuel_bp.equipment_group_edit', view_func=lambda equipment_group_id: '')
    monkeypatch.setattr(marginal_price_routes, 'render_template', render_template)
    client, _ = http_client
    response = client.get('/rational_structure/marginal_price?territory=east')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Название группы оборудования' in html
    assert html.index('data-column-key="D"') < html.index('data-column-key="station"') < html.index('data-column-key="P"')
    assert '<a href="/fuel/stations_equipment_groups/equipment_group/10">Восток станция</a>' in html
    assert '<a href="/stations/1">ТЭЦ Альфа</a>' in html
    assert 'Чужая станция' not in html
    assert '/equipment_group/11' not in html
    response = client.get('/rational_structure/marginal_price/export')
    exported = read_marginal_price_workbook(response.data)
    assert exported['east']['rows'][0]['values']['D'] == 'Восток станция'
    assert exported['east']['rows'][0]['values']['C'] == '1.23456789'
    html = client.get('/rational_structure/marginal_price?territory=south').get_data(as_text=True)
    assert 'Юг станция' in html
    assert '/equipment_group/12' not in html
