from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from test_territory_data import database, http_client, territory_client, territory_database, posted_table
from app.extensions import db
from app.rational_structure.models import TerritoryInput
from app.rational_structure.services import territory_summary_services as services
from app.rational_structure.services.territory_input_services import build_territory_input_context, save_territory_inputs


def source_row(model, zone, parameter, values, *, code=None, tooltips=None):
    return dict(demand_model_name=model, parent_id=zone, parameter_key=parameter,
                perimeter_variant_code=code, year_values=values, year_numeric_tooltips=tooltips or [])


@pytest.fixture
def summary_sources(monkeypatch):
    consumption = {"years": [2025, 2026], "summary_rows": [
        source_row(services.CONSUMPTION_MODEL, 2, "energy_consumption_mln_kvt_ch", ["999", "999"]),
        source_row(services.CONSUMPTION_MODEL, 1, "energy_consumption_mln_kvt_ch", ["9 000", "0"],
                   tooltips=["9 000,123456789", "0"]),
    ]}
    demand = {"years": [2025, 2026], "summary_rows": [
        source_row(services.DEMAND_MODEL, 1, "max_power", ["1 200", "–"]),
        source_row(services.DEMAND_MODEL, 1, "combined_on_ees", ["500", "0"]),
        source_row(services.DEMAND_MODEL, 1, "peak_max_power_usage_hours", ["4 321", "–"]),
        source_row(services.DEMAND_MODEL, 2, "max_power", ["999", "999"]),
    ]}
    monkeypatch.setattr(services, "get_current_version", lambda: 1)
    monkeypatch.setattr(services, "build_summary_ez_page_context", lambda *args, **kwargs: consumption)
    monkeypatch.setattr(services, "build_energy_zones_summary_context", lambda *args, **kwargs: demand)
    monkeypatch.setattr(services, "_gaes_charge_raw_station_values_for_entity", lambda *args: ())
    return consumption, demand


def test_sources_match_zone_year_and_preserve_full_precision(summary_sources):
    result = services.load_territory_summary_values(1, 1, [2026, 2025, 2027])
    assert not result["has_gaes"]
    assert result["consumption"] == [Decimal(0), Decimal("9000.123456789"), None]
    assert result["max_power"] == [None, Decimal(1200), None]
    assert result["combined"] == [Decimal(0), Decimal(500), None]
    assert result["hours"] == [None, Decimal(4321), None]
    with pytest.raises(ValueError, match="Версия"):
        services.load_territory_summary_values(2, 1, [2025])


def test_gaes_subtracts_charge_and_does_not_invent_missing_years(summary_sources, monkeypatch):
    monkeypatch.setattr(services, "_gaes_charge_raw_station_values_for_entity", lambda *args: (
        (10, "ГАЭС А", ((2025, Decimal("100.1")),)),
        (11, "ГАЭС Б", ((2025, Decimal("140.023456789")),)),
    ))
    result = services.load_territory_summary_values(1, 1, [2025, 2026])
    assert result["has_gaes"]
    assert result["consumption"] == [Decimal(8760), None]
    assert result["consumption_with_gaes"] == [Decimal("9000.123456789"), Decimal(0)]


def test_explicit_without_gaes_source_takes_precedence(summary_sources, monkeypatch):
    consumption, _ = summary_sources
    consumption["summary_rows"].append(source_row(
        services.CONSUMPTION_MODEL, 1, "energy_consumption_mln_kvt_ch", ["8 760", "0"],
        code="without_nt_without_gaes"))
    monkeypatch.setattr(services, "_gaes_charge_raw_station_values_for_entity", lambda *args: ((10, "ГАЭС", ()),))
    result = services.load_territory_summary_values(1, 1, [2025, 2026])
    assert result["consumption"] == [Decimal(8760), Decimal(0)]


def linked_values(version, zone, years):
    return dict(has_gaes=zone == 1,
                consumption=[Decimal(8760) if year == 2025 else Decimal(0) if year == 2026 else None for year in years],
                consumption_with_gaes=[Decimal(9000) if year == 2025 else None for year in years],
                max_power=[Decimal(1200)] * len(years), combined=[Decimal(500)] * len(years),
                hours=[Decimal(4321)] * len(years))


def test_http_linked_rows_formulas_export_and_missing_denominator(territory_client, monkeypatch):
    monkeypatch.setattr(services, "load_territory_summary_values", linked_values)
    client, _ = territory_client
    response = client.get('/rational_structure/territory_inputs?energy_zone_id=1&start_year=2025&end_year=2027')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Годовое потребление электрической энергии без ГАЭС' in html
    assert 'Годовое потребление электрической энергии с ГАЭС' in html
    assert 'Максимальное потребление мощности' in html
    assert 'Совмещенное потребление мощности на час прохождения максимума ЕЭС' in html
    assert 'aria-label="Формула: Среднегодовое потребление мощности"' in html
    assert '/ 8760 × 1000' in html
    assert 'name="value_0_2025"' not in html and 'name="value_4_2025"' not in html
    assert 'name="value_6_2025"' in html
    response = client.get('/rational_structure/territory_inputs/export?energy_zone_id=1&start_year=2025&end_year=2027')
    book = load_workbook(BytesIO(response.data))
    try:
        rows = {row[1]: row for row in book.active.iter_rows(min_row=3, values_only=True)}
        assert rows['Годовое потребление электрической энергии без ГАЭС'][0] == '1.1'
        assert rows['Годовое потребление электрической энергии с ГАЭС'][0] == '1.2'
        assert rows['Среднегодовое потребление мощности'][3:6] == (1000, 0, None)
        assert rows['Соотношение п.2а к Рсреднегодовой'][3:6] == (0.5, None, None)
        assert rows['ЧЧИМ'][3] == 4321
    finally:
        book.close()
    html = client.get('/rational_structure/territory_inputs?energy_zone_id=2').get_data(as_text=True)
    assert 'Годовое потребление электрической энергии без ГАЭС</th>' not in html
    assert 'Годовое потребление электрической энергии с ГАЭС' not in html
    assert db.session.scalar(select(TerritoryInput)) is None


def test_linked_values_cannot_be_overwritten_and_old_json_is_preserved(territory_client):
    client, _ = territory_client
    client.application.config['WTF_CSRF_ENABLED'] = False
    context = build_territory_input_context(1, 1)
    rows = deepcopy(context['all_rows'])
    stored_rows = [{key: row[key] for key in ('number', 'label', 'unit', 'note', 'section', 'values')} for row in rows]
    stored_rows[0]['values'][0] = '777.123456789'
    stored_rows[7]['values'][0] = '-123.456789'
    stored_rows[9]['values'][0] = '987.654321'
    record = TerritoryInput(database_version_id=1, energy_zone_id=1, years=context['years'],
                            rows=stored_rows, source_filename='existing.xlsx')
    db.session.add(record)
    db.session.commit()
    before = deepcopy(record.rows)
    for key in (*range(6), 7, 9):
        response = client.patch('/rational_structure/territory_inputs/cell', json=dict(
            database_version_id=1, energy_zone_id=1, sheet='years', row_key=str(key), year=2025,
            field='value', value='999'))
        assert response.status_code == 400
        assert 'автоматически' in response.json['error']
    context = build_territory_input_context(1, 1)
    form = posted_table(context)
    form['value_0_2025'] = '999'
    form['value_7_2025'] = '999'
    form['value_9_2025'] = '999'
    save_territory_inputs(context, form, 'tester')
    db.session.expire_all()
    assert db.session.get(TerritoryInput, record.id).rows == before
