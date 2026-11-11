from decimal import Decimal
import re

import pytest

from test_territory_data import database, http_client, territory_database, territory_client
from test_territory_equipment import sources
from app.rational_structure.services import territory_equipment_services as equipment


@pytest.mark.parametrize('part', [None, 70])
@pytest.mark.parametrize('group', [1, None])
def test_composition_links_to_station_and_correct_machine_card(territory_client, sources, monkeypatch, part, group):
    rows, groups, technologies, powers, base = sources
    rows[0].update(station_id=901, pgu_machine_id=part, equipment_group_type_id=group)
    powers = [(machine, part if machine == 1 else old_part, year, power)
              for machine, old_part, year, power in powers]
    monkeypatch.setattr(equipment, 'load_territory_equipment_sources',
                        lambda version: (rows, groups, technologies, powers, base))
    client, _ = territory_client
    response = client.get('/rational_structure/territory_inputs', query_string=dict(
        energy_zone_id=1, sheet='equipment', start_year=2025, end_year=2030))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    query = '?start_year=2025&amp;end_year=2030'
    station = f'/stations/901{query}'
    machine = f'/stations/901/machines/1/parts/70{query}' if part else f'/stations/901/machines/1{query}'
    items = [item for item in re.findall(r'<li>(.*?)</li>', html, re.S) if f'href="{station}"' in item]
    assert items
    for item in items:
        assert f'href="{station}" target="_blank" rel="noopener">Станция 1</a>' in item
        assert f'href="{machine}" target="_blank" rel="noopener">1 – Агрегат 1</a>' in item


@pytest.mark.parametrize('power,display', [
    ('150.0000', '150'), ('150.1200', '150,12'),
    ('0.0000000012300', '0,00000000123'), ('123456789.123456789000', '123 456 789,123456789'),
])
def test_hover_and_popup_trim_only_fraction_zeros_without_losing_database_precision(
    territory_client, sources, monkeypatch, power, display,
):
    rows, groups, technologies, powers, base = sources
    power = Decimal(power)
    rows = rows[:1]
    powers = [(machine, part, year, power) for machine, part, year, _ in powers if machine == 1]
    monkeypatch.setattr(equipment, 'load_territory_equipment_sources',
                        lambda version: (rows, groups, technologies, powers, base))
    client, _ = territory_client
    response = client.get('/rational_structure/territory_inputs', query_string=dict(
        energy_zone_id=1, sheet='equipment', start_year=2025, end_year=2026, rounding_digits=1))
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'<td data-raw-value="{power}" title="{display}">' in html
    assert f'Руст <span title="{display}">{display}</span> МВт' in html
