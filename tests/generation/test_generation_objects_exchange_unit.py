# -*- coding: utf-8 -*-
"""Юнит-тесты JSON-наборов generation_objects / generation_machines."""
from types import SimpleNamespace

from app.api.services import generation_objects_exchange_services as svc


def test_json_number_int_and_float():
    assert svc.json_number("100") == 100
    assert svc.json_number("100.5") == 100.5
    assert svc.json_number(None) is None


def test_generation_mwh_converts_and_rounds():
    assert svc.generation_mwh(10.3234) == 10.323
    assert svc.generation_mwh("0.000323") == 0.0
    assert svc.generation_mwh("0.000523") == 0.001
    assert svc.generation_mwh(None) == 0.0


def test_energy_zone_number_parses_int():
    assert svc.energy_zone_number("10") == 10
    assert svc.energy_zone_number("зона-10") is None


def test_station_is_planned_by_condition_name():
    assert svc.station_is_planned("планируемый") is True
    assert svc.station_is_planned("Планируемая") is True
    assert svc.station_is_planned("действующий") is False
    assert svc.station_is_planned(None) is False


def test_station_is_planned_by_machines_rules():
    ok = SimpleNamespace(
        date_exploitation_expected=2026,
        date_commission_fact=None,
        is_archived=False,
    )
    early = SimpleNamespace(
        date_exploitation_expected=2020,
        date_commission_fact=None,
        is_archived=False,
    )
    with_fact = SimpleNamespace(
        date_exploitation_expected=2030,
        date_commission_fact="01.01.2024",
        is_archived=False,
    )
    archived_bad = SimpleNamespace(
        date_exploitation_expected=2020,
        date_commission_fact="01.01.2020",
        is_archived=True,
    )
    assert svc.station_is_planned_by_machines([ok], current_year=2025) is True
    assert svc.station_is_planned_by_machines([ok, archived_bad], current_year=2025) is True
    assert svc.station_is_planned_by_machines([ok, early], current_year=2025) is False
    assert svc.station_is_planned_by_machines([with_fact], current_year=2025) is False
    assert svc.station_is_planned_by_machines([], current_year=2025) is False


def test_year_from_fact_date_shifts_january_first():
    assert svc.year_from_fact_date("01.01.2050") == 2049
    assert svc.year_from_fact_date("15.06.2050") == 2050
    assert svc.year_from_fact_date("2050-01-01") == 2049


def test_commission_and_decommission_years():
    assert svc.commission_year(2010, 2012) == 2010
    assert svc.commission_year(None, 2012) == 2012
    assert svc.decommission_year(2050, None) == 2050
    assert svc.decommission_year(2050, "01.01.2040") == 2039


def test_select_exchange_years_keeps_last_five_fact_current_and_plan():
    rows = [
        (2018, "факт"),
        (2019, "факт"),
        (2020, "факт"),
        (2021, "факт"),
        (2022, "факт"),
        (2023, "факт"),
        (2024, "текущий (оценка)"),
        (2025, "план"),
        (2030, "план"),
    ]
    assert svc.select_exchange_years(rows) == [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2030]


def test_select_exchange_years_without_features_returns_all():
    assert svc.select_exchange_years([(2032, None), (2033, "")]) == [2032, 2033]


def test_clip_years_single_and_range():
    years = [2024, 2025, 2030]
    assert svc.clip_years(years, year=2025) == [2025]
    assert svc.clip_years(years, start_year=2025, end_year=2030) == [2025, 2030]


def test_build_station_year_row_keys():
    row = svc.build_station_year_row(
        external_code="st-1",
        name="ТЭС 1",
        station_type="ТЭС",
        year=2032,
        subject="Регион",
        zone="1-я синхронная зона",
        energy_zone="10",
        capacity=100,
        generation="12.5",
        planned=True,
    )
    assert row[svc.KEY_STATION_CODE] == "st-1"
    assert row[svc.KEY_ENERGY_ZONE] == 10
    assert row[svc.KEY_GENERATION] == 12.5
    assert row[svc.KEY_PLANNED] is True
    assert row[svc.KEY_CAPACITY] == 100


def test_build_machine_year_row_join_key():
    row = svc.build_machine_year_row(
        station_external_code="st-1",
        external_code="m-1",
        year=2032,
        machine_number="1",
        machine_name="Блок 1",
        block_type="Угольный блок тип 1",
        capacity=50,
        fuel="уголь",
        equipment_group_type="КЭС",
        equipment_group_name="КЭС-1",
        equipment_group_external_code="eg-1",
        commission=2010,
        decommission=2050,
        archived=False,
    )
    assert row[svc.KEY_STATION_CODE_ON_MACHINE] == "st-1"
    assert row[svc.KEY_MACHINE_CODE] == "m-1"
    assert row[svc.KEY_FUEL] == "уголь"
    assert row[svc.KEY_EQUIPMENT_GROUP_TYPE] == "КЭС"
    assert row[svc.KEY_EQUIPMENT_GROUP_NAME] == "КЭС-1"
    assert row[svc.KEY_EQUIPMENT_GROUP_CODE] == "eg-1"
    assert row[svc.KEY_ARCHIVED] is False


def test_build_generation_objects_rows_station_times_year():
    station = SimpleNamespace(
        id=1,
        external_code="st-1",
        name="ТЭС 1",
        station_type=SimpleNamespace(name="ТЭС"),
        condition_type=SimpleNamespace(name="планируемый"),
        regional_district=SimpleNamespace(
            name="Регион",
            synchronous_area=SimpleNamespace(name="1-я синхронная зона"),
            energy_zone=SimpleNamespace(number="10"),
        ),
    )
    rows = svc.build_generation_objects_rows(
        [station],
        [2032, 2033, 2034],
        {(1, 2032): 100, (1, 2033): 80},
        {(1, 2032): 12},
        planned_by_station={1: True},
    )
    assert len(rows) == 2
    assert rows[0][svc.KEY_YEAR] == 2032
    assert rows[0][svc.KEY_CAPACITY] == 100
    assert rows[1][svc.KEY_CAPACITY] == 80
    assert rows[0][svc.KEY_GENERATION] == 12.0
    assert rows[1][svc.KEY_GENERATION] == 0.0
    assert rows[0][svc.KEY_PLANNED] is True


def test_build_generation_machines_rows_station_code_and_archive():
    machine = SimpleNamespace(
        id=9,
        external_code="m-1",
        machine_number="2",
        machine_name="Блок 2",
        date_exploitation=2015,
        date_exploitation_expected=None,
        date_decompressing_expected=2050,
        date_decompressing_fact=None,
        is_archived=True,
        tes_machine_type=SimpleNamespace(name="Угольный блок тип 1"),
        machine_type=SimpleNamespace(name="турбина"),
        machine_station=SimpleNamespace(external_code="st-1"),
        equipment_group=SimpleNamespace(name="КЭС"),
        machine_fuel_param=SimpleNamespace(
            equipment_group=SimpleNamespace(name="КЭС-1", external_code="eg-1")
        ),
    )
    rows = svc.build_generation_machines_rows(
        [machine],
        [2032, 2033],
        {(9, 2032): 40},
        {(9, 2032): "уголь"},
    )
    assert len(rows) == 1
    assert rows[0][svc.KEY_STATION_CODE_ON_MACHINE] == "st-1"
    assert rows[0][svc.KEY_BLOCK_TYPE] == "Угольный блок тип 1"
    assert rows[0][svc.KEY_COMMISSION] == 2015
    assert rows[0][svc.KEY_DECOMMISSION] == 2050
    assert rows[0][svc.KEY_ARCHIVED] is True
    assert rows[0][svc.KEY_EQUIPMENT_GROUP_TYPE] == "КЭС"
    assert rows[0][svc.KEY_EQUIPMENT_GROUP_NAME] == "КЭС-1"
    assert rows[0][svc.KEY_EQUIPMENT_GROUP_CODE] == "eg-1"


def test_dataset_envelope_shape():
    payload = svc.dataset_envelope(
        "generation_objects",
        database_version=7,
        version_number="ГС-2026",
        rows=[{"Год": 2032}],
    )
    assert list(payload.keys()) == [
        "dataset",
        "database_version",
        "version_number",
        "version",
        "comment",
        "rows",
    ]
    assert payload["dataset"] == "generation_objects"
    assert payload["database_version"] == 7
    assert payload["version_number"] == "ГС-2026"
    assert payload["version"] == 7
    assert payload["rows"] == [{"Год": 2032}]
