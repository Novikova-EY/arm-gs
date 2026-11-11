from decimal import Decimal
from io import BytesIO
import re
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from test_territory_data import database, http_client, territory_database, territory_client
from test_territory_equipment import runtime_row, sources
from app.rational_structure.services import territory_equipment_services as equipment
from app.rational_structure.services.territory_ungrouped_equipment_services import (
    ungrouped_equipment_series,
)


def test_ungrouped_uses_explicit_card_type_and_preserves_other_fuels():
    groups = [SimpleNamespace(id=1, name='ВВЭР-1000', id_technology_type=2),
              SimpleNamespace(id=2, name='Не указано', id_technology_type=None)]
    rows = [runtime_row(1, None, fuel='NUCLEAR'), runtime_row(2, 1, fuel='NUCLEAR'),
            runtime_row(3, None, fuel='MAZUT'), runtime_row(4, 2, fuel='GAZ'),
            runtime_row(5, 0, fuel='UGOL'), runtime_row(6, 999, fuel='GAZ', zone=2),
            runtime_row(7, None, part=70), runtime_row(7, None, part=71)]
    rows[0]['values']['L'] = 'ВВЭР-1000'
    rows.append(rows[-1])
    powers = [(row['machine_id'], row['pgu_machine_id'], year, Decimal(10))
              for row in rows for year in (2024, 2026)]
    data = ungrouped_equipment_series(rows, groups, powers, [2024, 2026], 2024, 1)
    assert set(data) == {('АЭС', ''), ('ТЭС', 'прочие'), ('ТЭС', 'газ'), ('ТЭС', 'уголь')}
    assert data['АЭС', '']['series']['total'] == [10, 10]
    assert data['ТЭС', 'газ']['series']['total'] == [30, 30]
    assert data['ТЭС', 'газ']['counts']['total'] == [3, 3]
    assert data['ТЭС', 'газ']['series']['first'] == [0, 30]
    assert {item['number'] for item in data['ТЭС', 'газ']['contributors']['series']['total'][0]} == {'4', '70', '71'}
    assert data['ТЭС', 'прочие']['series']['total'] == [10, 10]


@pytest.mark.parametrize('zone', [0, 1])
def test_diagnostic_rows_in_all_blocks_visible_readonly_detailed_and_exported(territory_client, sources, monkeypatch, zone):
    rows, groups, technologies, powers, base = sources
    rows[0]['equipment_group_type_id'] = None
    monkeypatch.setattr(equipment, 'load_territory_equipment_sources',
                        lambda version: (rows, groups, technologies, powers, base))
    client, _ = territory_client
    query = dict(energy_zone_id=zone, sheet='equipment', start_year=2025, end_year=2026)
    response = client.get('/rational_structure/territory_inputs', query_string=query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    diagnostics = [(attrs, body) for attrs, body in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
                   if 'data-equipment-diagnostic' in attrs and 'data-equipment-verification' not in attrs]
    assert len(diagnostics) == 4 * 4 * 2
    assert 'Всего до проведения мероприятий: Для лет' not in html
    assert not re.search(r'ungrouped_(?:total|first|second|remaining)_(?:ВИЭ|ГЭС|ГАЭС|СНЭЭ)_', html)
    for attrs, body in diagnostics:
        assert '>Без группы оборудования</th>' in body
        assert 'data-value-row' not in attrs and 'name="value_' not in body
        if 'data-equipment-group=' in attrs:
            assert 'Тип группы оборудования в карточке не задан.' in body
        else:
            assert 'Повторно в итог не включается' in body
    assert 'data-equipment-row-key="tes_total_1_газ_None"' in html
    assert 'aria-controls="equipment-tes_total_1_газ_None-2025"' in html
    assert 'ungrouped_total_ТЭС_газ_series' not in html
    ungrouped = [body for attrs, body in re.findall(r'<tr([^>]*)>(.*?)</tr>', html, re.S)
                 if '>Без группы оборудования</th>' in body and 'data-equipment-verification' not in attrs]
    assert len(ungrouped) == len(diagnostics)
    assert 'Станция 1, 1 – Агрегат 1' in re.sub(r'<[^>]+>', '', html)
    result = client.get('/rational_structure/territory_inputs/export', query_string=query)
    assert result.status_code == 200
    book = load_workbook(BytesIO(result.data))
    try:
        diagnostic = [row for row in book.active.values if row[1] == 'Без группы оборудования'
                      and row[-1]]
        assert len(diagnostic) == len(diagnostics)
        assert any(row[2] == 'МВт' and row[3] == 150 for row in diagnostic)
    finally:
        book.close()

