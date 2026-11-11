from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from werkzeug.datastructures import MultiDict

from test_territory_data import database, http_client, territory_database, territory_client
from test_territory_summary import source_row
from app.extensions import db
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.rational_structure.services import territory_summary_services as services
from app.rational_structure.services.territory_summary_services import load_territory_summary_values
from app.rational_structure.services.territory_input_services import build_territory_input_context
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view


@pytest.fixture
def ees_sources(territory_client, monkeypatch):
    EnergySystemType.__table__.create(db.engine)
    db.session.execute(EnergySystemType.__table__.insert(), [
        dict(id=7, database_version_id=1, name='ЕЭС России', ref_uuid='ees'),
        dict(id=8, database_version_id=1, name='ТИТЭС', ref_uuid='tites'),
    ])
    db.session.commit()
    consumption = {'years': [2025, 2026], 'summary_rows': [
        source_row('EnergySystemTypeEnergyConsumptionParameter', 7, 'energy_consumption_mln_kvt_ch',
                   ['9 000', '10'], code='without_nt_with_gaes', tooltips=['9 000,123456789', '10']),
        source_row('EnergySystemTypeEnergyConsumptionParameter', 7, 'energy_consumption_mln_kvt_ch',
                   ['8 760', '0'], code='without_nt_without_gaes'),
        source_row('EnergySystemTypeEnergyConsumptionParameter', 7, 'energy_consumption_mln_kvt_ch',
                   ['999', '999'], code='with_nt_without_gaes'),
        source_row('EnergySystemTypeEnergyConsumptionParameter', 7, 'energy_consumption_mln_kvt_ch',
                   ['999', '999'], code='with_nt_with_gaes'),
        source_row('EnergySystemTypeEnergyConsumptionParameter', 8, 'energy_consumption_mln_kvt_ch',
                   ['999', '999'], code='without_nt_without_gaes'),
        source_row('EesRussiaEnergyConsumptionParameter', 7, 'energy_consumption_mln_kvt_ch', ['999', '999']),
        source_row(services.CONSUMPTION_MODEL, 1, 'energy_consumption_mln_kvt_ch', ['999', '999']),
    ]}
    demand = {'years': [2025, 2026], 'summary_rows': []}
    for key, values in [('max_power', ['1200', '500']), ('combined_on_ees', ['500', '10']),
                        ('peak_max_power_usage_hours', ['4321.123456789', '0'])]:
        demand['summary_rows'].extend([
            source_row('EnergySystemTypeDemandParameter', 7, key, ['999', '999'], code='with_nt'),
            source_row('EnergySystemTypeDemandParameter', 8, key, ['999', '999'], code='without_nt'),
            source_row(services.DEMAND_MODEL, 1, key, ['999', '999']),
            source_row('EnergySystemTypeDemandParameter', 7, key, values, code='without_nt'),
        ])
    calls = []

    def build(context, *args, **kwargs):
        calls.append(kwargs)
        assert kwargs['ez_territory_ordered'] == ([], [])
        return context

    monkeypatch.setattr(services, 'get_current_version', lambda: 1)
    monkeypatch.setattr(services, 'load_territory_summary_values', load_territory_summary_values)
    monkeypatch.setattr(services, 'build_summary_ez_page_context', lambda *a, **kw: build(consumption, *a, **kw))
    monkeypatch.setattr(services, 'build_energy_zones_summary_context', lambda *a, **kw: build(demand, *a, **kw))
    monkeypatch.setattr(services, '_gaes_charge_raw_station_values_for_entity',
                        lambda *a: pytest.fail('Для ЕЭС используются строки сводки, не сумма станций'))
    return consumption, demand, calls


def test_national_sources_match_type_perimeter_years_and_precision(ees_sources):
    data = load_territory_summary_values(1, None, [2026, 2025, 2027])
    assert data['has_gaes']
    assert data['consumption'] == [Decimal(0), Decimal(8760), None]
    assert data['consumption_with_gaes'] == [Decimal(10), Decimal('9000.123456789'), None]
    assert data['max_power'] == [Decimal(500), Decimal(1200), None]
    assert data['combined'] == [Decimal(10), Decimal(500), None]
    assert data['hours'] == [Decimal(0), Decimal('4321.123456789'), None]
    calls = ees_sources[2]
    assert len(calls) == 2
    assert all(call['filter_year_list'] == [2026, 2025, 2027] for call in calls)
    assert calls[1]['data_segments'] == frozenset({'core', 'chi'})
    with pytest.raises(ValueError, match='Версия'):
        load_territory_summary_values(2, None, [2025])


def test_national_formulas_render_and_export(territory_client, ees_sources):
    context = prepare_territory_input_view(build_territory_input_context(1, 0),
                                          MultiDict({'start_year': '2025', 'end_year': '2027'}))
    rows = {row['key']: row for row in context['rows']}
    assert len(rows) == len(context['rows'])
    assert rows['0']['cells'] == ['8760', '0', '']
    assert rows['0_with_gaes']['cells'] == ['9000.123456789', '10', '']
    assert rows['4']['cells'] == ['1000', '0', '']
    assert rows['5']['cells'] == ['0.5', '', '']
    assert '/ 8760 × 1000' in rows['4']['formula']
    assert 'При нулевом знаменателе' in rows['5']['formula']
    client, _ = territory_client
    query = dict(energy_zone_id=0, start_year=2025, end_year=2027)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-raw-value="9000.123456789"' in html
    assert 'data-raw-value="4321.123456789"' in html
    assert '/ 8760 × 1000' in html
    response = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    try:
        rows = {row[1]: row for row in book.active.iter_rows(min_row=3, values_only=True)}
        assert rows['Годовое потребление электрической энергии без ГАЭС'][3:6] == (8760, 0, None)
        assert rows['Годовое потребление электрической энергии с ГАЭС'][3] == pytest.approx(9000.123456789)
        assert rows['Среднегодовое потребление мощности'][3:6] == (1000, 0, None)
        assert rows['Соотношение п.2а к Рсреднегодовой'][3:6] == (0.5, None, None)
    finally:
        book.close()


def test_national_missing_source_is_not_replaced_with_zone_sum(ees_sources):
    consumption, demand, _ = ees_sources
    consumption['summary_rows'] = [row for row in consumption['summary_rows']
                                   if row.get('perimeter_variant_code') != 'without_nt_without_gaes']
    demand['summary_rows'] = [row for row in demand['summary_rows']
                              if row.get('perimeter_variant_code') != 'without_nt']
    data = load_territory_summary_values(1, None, [2025])
    assert data['consumption'] == [None]
    # Не подменяем отсутствующие значения данными периметра «с НТ».
    assert data['max_power'] == [None]
    assert data['combined'] == [None]
    assert data['hours'] == [None]


def test_national_type_is_version_scoped(ees_sources):
    db.session.execute(EnergySystemType.__table__.update().where(EnergySystemType.id == 7)
                       .values(database_version_id=2))
    db.session.commit()
    data = load_territory_summary_values(1, None, [2025])
    assert data['has_gaes']
    assert all(data[key] == [None] for key in ('consumption', 'consumption_with_gaes',
                                              'max_power', 'combined', 'hours'))
    assert ees_sources[2] == []
