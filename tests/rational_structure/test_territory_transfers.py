from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from test_territory_data import database, http_client, territory_database, territory_client
from app.extensions import db
from app.rational_structure.services import territory_transfer_services as services
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system as membership,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict


@pytest.fixture
def transfers(territory_database, monkeypatch):
    for model in (RegionalDistrict, RegionalEnergySystem, EnergyUnit):
        model.__table__.create(db.engine)
    membership.create(db.engine)
    for identifier, version, zone in ((10, 1, 1), (11, 1, 1), (12, 1, 2), (13, 2, 1)):
        db.session.execute(RegionalDistrict.__table__.insert().values(
            id=identifier, database_version_id=version, id_energy_zone=zone,
            name=f"Субъект {identifier}", name_full=f"Субъект {identifier}", name_rp="", name_dp="",
            ref_uuid=f"district-{identifier}",
        ))
    for identifier, version in ((20, 1), (21, 1), (22, 1), (23, 2)):
        db.session.execute(RegionalEnergySystem.__table__.insert().values(
            id=identifier, database_version_id=version, name=f"РЭС {identifier}",
            name_full=f"РЭС {identifier}", name_rp="",
            ref_uuid=f"res-{identifier}",
        ))
    db.session.execute(membership.insert(), [
        {"regional_district_id": district, "regional_energy_system_id": res}
        for district, res in ((10, 20), (11, 20), (11, 21), (12, 22), (13, 23))
    ])
    db.session.execute(EnergyUnit.__table__.insert().values(
        id=30, database_version_id=1, name="Энергорайон", name_rp="", name_dp="",
        id_regional_district=10, id_regional_energy_system=20, ref_uuid="unit-30",
    ))
    db.session.commit()
    monkeypatch.setattr(services, "get_current_version", lambda: 1)
    rows = []
    monkeypatch.setattr(services, "get_ee_transfers_page_data", lambda **kwargs: {"all_rows": rows})
    return rows


def transfer(*, source=20, target=22, values=None, **fields):
    return dict(from_name=f"РЭС {source}", to_name=f"Контрагент {target}", from_res_id=source,
                to_res_id=target, periods=values or {}, **fields)


def test_sums_by_zone_exclude_internal_and_mirrored_rows_preserve_sign_and_precision(transfers):
    transfers.extend([
        transfer(target=None, to_country_id=50, values={2025: Decimal("-10.1234567890123456"), 2026: Decimal("5.25")}),
        transfer(source=21, target=None, to_country_id=51, values={2025: Decimal("-20.5")}),
        transfer(source=22, target=20, values={2025: Decimal("10.1234567890123456")}),
        transfer(target=21, values={2025: Decimal("-900")}),
        transfer(target=None, to_rd_id=10, values={2025: Decimal("-800")}),
        transfer(target=None, to_eu_id=30, values={2025: Decimal("-700")}),
        transfer(source=23, target=None, to_country_id=50, values={2025: Decimal("-600")}),
        transfer(source=None, from_rd_id=10, to_country_id=50, values={2025: Decimal("-500")}),
        transfer(values={2025: Decimal("-400")}),
        transfer(source=21, target=None, to_country_id=52, values={2025: Decimal("2.5")}),
        transfer(target=None, to_country_id=53, values={2025: Decimal("-3.1")}),
        transfer(source=22, target=None, to_country_id=50, values={2025: Decimal("-6")}),
    ])
    result = services.load_territory_transfer_rows(1, 1, [2026, 2025, 2027])
    assert list(map(Decimal, result["7"]["cells"][:2])) == [Decimal(0), Decimal("-33.7234567890123456")]
    assert list(map(Decimal, result["9"]["cells"][:2])) == [Decimal("5.25"), Decimal("2.5")]
    assert result["7"]["cells"][2] == result["9"]["cells"][2] == ""
    for group in result.values():
        for index in (0, 1):
            assert sum((Decimal(row["cells"][index]) for row in group["details"] if row["cells"][index]),
                       Decimal(0)) == Decimal(group["cells"][index])
    assert len(result["7"]["details"]) == len(result["9"]["details"]) == 4
    # Две связи одного РЭС с субъектами не удваивают суммы; другая энергозона независима.
    other = services.load_territory_transfer_rows(1, 2, [2025])
    assert Decimal(other["7"]["cells"][0]) == Decimal("-6")
    assert Decimal(other["9"]["cells"][0]) == Decimal(0)
    with pytest.raises(ValueError, match="Версия"):
        services.load_territory_transfer_rows(2, 1, [2025])


def test_missing_values_are_blank_and_explicit_zero_is_not_lost(transfers):
    empty = services.load_territory_transfer_rows(1, 1, [2025, 2026])
    assert all(group == {"cells": ["", ""], "details": []} for group in empty.values())
    transfers.append(transfer(target=None, to_country_id=50, values={2025: Decimal(0)}))
    result = services.load_territory_transfer_rows(1, 1, [2025, 2026])
    for group in result.values():
        assert group["cells"] == ["0", ""]
        assert group["details"][0]["cells"] == ["0", ""]


def test_http_totals_collapsed_details_readonly_export_and_year_filter(territory_client, monkeypatch):
    client, _ = territory_client
    detail_label = '=РЭС А – РЭС Б'

    def linked(version, zone, years):
        return {key: {"cells": [str(amount) if year == 2025 else "" for year in years],
                      "details": [{"label": detail_label, "cells": [str(amount) if year == 2025 else "" for year in years]}]}
                for key, amount in (("7", -25), ("9", 10))}

    monkeypatch.setattr(services, "load_territory_transfer_rows", linked)
    html = client.get('/rational_structure/territory_inputs?energy_zone_id=1&start_year=2025&end_year=2026').get_data(as_text=True)
    assert html.count('data-transfer-toggle=') == 2
    assert html.count('aria-expanded="false"') == 2
    assert 'Всего</div>' in html
    assert 'class="territory-transfer-child territory-transfer-hidden" data-transfer-parent="7"' in html
    assert 'class="territory-transfer-child territory-transfer-hidden" data-transfer-parent="9"' in html
    for key in ("7", "9"):
        assert f'name="value_{key}_2025"' not in html
        assert f'name="value_{key}_transfer_0_2025"' not in html
    assert 'name="value_8_2025"' in html and 'name="value_10_2025"' in html
    response = client.get('/rational_structure/territory_inputs/export?energy_zone_id=1&start_year=2025&end_year=2026')
    book = load_workbook(BytesIO(response.data))
    try:
        rows = list(book.active.iter_rows(min_row=3, values_only=True))
        export = next(index for index, row in enumerate(rows) if row[1] == 'Экспорт электрической энергии')
        assert rows[export][3:5] == (-25, None)
        assert rows[export + 1][1:5] == (detail_label, 'млн кВт·ч', -25, None)
        assert book.active.cell(export + 4, 2).data_type == 's'
        assert next(row for row in rows if row[1] == 'Импорт электрической энергии')[3] == 10
    finally:
        book.close()
    html = client.get('/rational_structure/territory_inputs?energy_zone_id=1&start_year=2026&end_year=2026').get_data(as_text=True)
    assert 'data-raw-value="-25"' not in html
    html = client.get('/rational_structure/territory_inputs?energy_zone_id=1&sheet=equipment').get_data(as_text=True)
    assert html.count('data-transfer-toggle=') == 5
    assert 'data-transfer-toggle="equipment_check"' in html
    assert 'data-transfer-toggle="7"' not in html and 'data-transfer-toggle="9"' not in html


def test_fact_year_outside_imported_excel_is_displayed_without_becoming_editable(territory_client, monkeypatch):
    from app.rational_structure.models import TerritoryInput
    from app.refdata.models.years.year_feature_model import YearFeature
    from app.refdata.models.years.year_model import Year
    from sqlalchemy import select
    import re

    client, _ = territory_client
    fact = YearFeature(name="факт", database_version_id=1)
    db.session.add(fact)
    db.session.flush()
    year = db.session.scalar(select(Year).where(Year.number == 2024, Year.database_version_id == 1))
    year.id_year_feature = fact.id
    db.session.commit()

    def linked(version, zone, years):
        return {key: {"cells": [amount if year == 2024 else "" for year in years],
                      "details": [{"label": "РЭС – Норвегия",
                                   "cells": [amount if year == 2024 else "" for year in years]}]}
                for key, amount in (("7", "-123.456"), ("9", "0"))}

    monkeypatch.setattr(services, "load_territory_transfer_rows", linked)
    endpoint = '/rational_structure/territory_inputs'
    html = client.get(endpoint + '?energy_zone_id=1').get_data(as_text=True)
    assert 'data-year="2024"' in html
    assert 'data-year="2042"' in html
    assert 'data-raw-value="-123.456"' in html
    assert 'РЭС – Норвегия' in html
    assert 'name="value_6_2024"' not in html
    assert 'name="value_6_2025"' in html
    assert db.session.scalar(select(TerritoryInput)) is None

    response = client.get(endpoint + '?energy_zone_id=1&start_year=2024&end_year=2024')
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'data-year="2024"' in html and 'data-year="2025"' not in html
    assert 'data-raw-value="-123.456"' in html
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html).group(1)
    response = client.patch(endpoint + '/cell', headers={'X-CSRFToken': token}, json=dict(
        database_version_id=1, energy_zone_id=1, sheet='years', row_key='6',
        field='value', year=2024, value='999',
    ))
    assert response.status_code == 400
    assert db.session.scalar(select(TerritoryInput)) is None

    response = client.get(endpoint + '/export?energy_zone_id=1&start_year=2024&end_year=2024')
    book = load_workbook(BytesIO(response.data))
    try:
        assert book.active['D2'].value == 2024
        rows = list(book.active.iter_rows(min_row=3, values_only=True))
        assert next(row for row in rows if row[1] == 'Экспорт электрической энергии')[3] == -123.456
    finally:
        book.close()
