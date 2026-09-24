# -*- coding: utf-8 -*-
"""Юнит-тесты JSON-наборов generation_stations / generation_machines."""
from types import SimpleNamespace

from app.api.services import generation_objects_exchange_services as svc


def test_json_number_int_and_float():
    assert svc.json_number("100") == 100
    assert svc.json_number("100.5") == 100.5
    assert svc.json_number(None) is None


def test_capacity_mw_two_decimals():
    assert svc.capacity_mw("450") == 450.0
    assert svc.capacity_mw("60.006") == 60.01
    assert svc.capacity_mw("60.004") == 60.0
    assert svc.capacity_mw(None) == 0.0


def test_generation_mwh_converts_and_rounds():
    assert svc.generation_mwh(10.3234) == 10.323
    assert svc.generation_mwh("0.000323") == 0.0
    assert svc.generation_mwh("0.000523") == 0.001
    assert svc.generation_mwh(None) == 0.0


def test_energy_zone_number_parses_int():
    assert svc.energy_zone_number("10") == 10
    assert svc.energy_zone_number("2") == 2
    assert svc.energy_zone_number("не указано") is None
    assert svc.energy_zone_number("зона-10") is None


def test_station_is_planned_by_condition_name():
    assert svc.station_is_planned("планируемый") is True
    assert svc.station_is_planned("Планируемая") is True
    assert svc.station_is_planned("действующий") is False
    assert svc.station_is_planned(None) is False


def test_station_is_planned_for_year_zero_now_positive_later():
    caps = {2020: 0, 2021: 0, 2026: 11}
    assert svc.station_is_planned_for_year(caps, 2020) is True
    assert svc.station_is_planned_for_year(caps, 2021) is True
    assert svc.station_is_planned_for_year(caps, 2026) is False


def test_station_is_planned_for_year_positive_or_never():
    assert svc.station_is_planned_for_year({2020: 10, 2026: 20}, 2020) is False
    assert svc.station_is_planned_for_year({2020: 0, 2021: 0}, 2020) is False


def test_station_page_name_falls_back_to_combined():
    empty = SimpleNamespace(name="", name_combined="ТЭС 1", name_so="so")
    assert svc.station_page_name(empty) == "ТЭС 1"
    named = SimpleNamespace(name="  Карточка  ", name_combined="x", name_so="y")
    assert svc.station_page_name(named) == "Карточка"


def test_station_page_zone_uses_subject_synchronous_area_full_name():
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            synchronous_area=SimpleNamespace(
                name="1 СЗ",
                name_full="1-я синхронная зона ЕЭС России",
            )
        ),
        energy_unit=None,
        energy_system_type="ЕЭС России",
    )
    assert svc.station_page_zone(station) == "1-я синхронная зона ЕЭС России"
    no_full = SimpleNamespace(
        regional_district=SimpleNamespace(
            synchronous_area=SimpleNamespace(name="1 СЗ", name_full=""),
        ),
        energy_unit=None,
    )
    assert svc.station_page_zone(no_full) == "1 СЗ"


def test_station_page_energy_zone_uses_subject_energy_zone_number():
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            energy_zone=SimpleNamespace(number="2"),
        ),
        energy_unit=None,
    )
    assert svc.station_page_energy_zone(station) == "2"
    assert svc.energy_zone_number(svc.station_page_energy_zone(station)) == 2


def test_year_from_fact_date_shifts_january_first():
    assert svc.year_from_fact_date("01.01.2050") == 2049
    assert svc.year_from_fact_date("15.06.2050") == 2050
    assert svc.year_from_fact_date("2050-01-01") == 2049


def test_decommission_years():
    assert svc.decommission_year(2050, None) == 2050
    assert svc.decommission_year(2050, "01.01.2040") == 2039


def test_exchange_years_from_current_minus_six_to_period_end(monkeypatch):
    version = SimpleNamespace(id=37, version_number="СиПР 2026-2031 (РАБОЧАЯ)")

    class _Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [(y,) for y in range(2018, 2033)]

    class _Session:
        def get(self, model, pk):
            return version if int(pk) == 37 else None

        def query(self, *a, **k):
            return _Q()

    monkeypatch.setattr(svc.db, "session", _Session())
    monkeypatch.setattr(
        "app.api.services.general_info_exchange_services.planning_meta_for_version",
        lambda version_id, version_number: {
            "planning_scheme": "sipr",
            "current_year": 2025,
            "period_start": 2026,
            "period_end": 2031,
        },
    )
    assert svc.exchange_years_bounds(37) == (2019, 2031)
    assert svc.load_exchange_years(37) == list(range(2019, 2032))
    assert svc.load_exchange_years(None) == []


def test_clip_years_single_and_range():
    years = [2024, 2025, 2030]
    assert svc.clip_years(years, year=2025) == [2025]
    assert svc.clip_years(years, start_year=2025, end_year=2030) == [2025, 2030]


def test_station_page_oes_uses_union_energy_system():
    station = SimpleNamespace(
        union_energy_system="ТИТЭС Сибири",
        regional_energy_system_obj=None,
        regional_district=None,
    )
    assert svc.station_page_oes(station) == "ТИТЭС Сибири"
    via_res = SimpleNamespace(
        regional_energy_system_obj=SimpleNamespace(
            union_energy_system=SimpleNamespace(name="ОЭС Урала")
        ),
        regional_district=None,
    )
    assert svc.station_page_oes(via_res) == "ОЭС Урала"


def test_build_station_year_row_keys():
    row = svc.build_station_year_row(
        external_code="st-1",
        name="ТЭС 1",
        station_type="ТЭС",
        year=2032,
        subject="Регион",
        zone="1-я синхронная зона",
        oes="ТИТЭС Сибири",
        energy_zone="10",
        capacity=100,
        generation="12.5",
        planned=True,
    )
    assert list(row.keys()) == [
        "Год",
        "Зона станции",
        "ОЭС",
        "external_code",
        "Субъект станции",
        "Тип станции",
        "Название станции",
        "Установленная мощность, МВт",
        "Станция является планируемой",
        "Номер энергозоны (код для оптимизации)",
        "Производство электроэнергии в году, МВт*ч",
    ]
    assert row[svc.KEY_STATION_CODE] == "st-1"
    assert row["Название станции"] == "ТЭС 1"
    assert row["Субъект станции"] == "Регион"
    assert row["Зона станции"] == "1-я синхронная зона"
    assert row[svc.KEY_OES] == "ТИТЭС Сибири"
    assert row[svc.KEY_ENERGY_ZONE] == 10
    assert row[svc.KEY_GENERATION] == 12.5
    assert row[svc.KEY_PLANNED] is True
    assert row[svc.KEY_CAPACITY] == 100


def test_json_date_or_dash_and_year_as_date():
    assert svc.json_date_or_dash(None) == "-"
    assert svc.json_date_or_dash("  ") == "-"
    assert svc.json_date_or_dash("01.01.2020") == "01.01.2020"
    assert svc.json_year_as_date(2030) == "01.01.2030"
    assert svc.json_year_as_date("2030") == "01.01.2030"
    assert svc.json_year_as_date(None) == "-"


def test_build_machine_year_row_mock_keys_and_placeholders():
    row = svc.build_machine_year_row(
        name="Агрегат 1. ТЭС 1",
        station_type="ТЭС",
        capacity=100,
        fuel="уголь",
        year=2026,
        subject="Санкт-Петербург",
        zone="1 синхронная зона",
        machine_type="Угольный блок тип 1",
        planned=True,
        decommission=2050,
        energy_zone=10,
        commission_fact_date="01.01.2020",
        decommission_date="01.01.2025",
        modernization_date="01.01.2030",
        external_code="00000000-0000-0000-0000-000000000011",
        station_external_code="st-1",
    )
    assert list(row.keys()) == [
        "Название агрегата",
        "Тип станции агрегата",
        "Установленная мощность агрегата, МВт",
        "Тип топлива",
        "Год",
        "Субъект агрегата",
        "Зона агрегата",
        "Производство агрегатом электроэнергии в году, МВт*ч",
        "Тип агрегата",
        "Блок является планируемым",
        "твердые частицы (зола), млн т",
        "диоксид серы (SO2), млн т",
        "оксиды азота (NOx), млн т",
        "диоксид углерода (CO2), млн т",
        "Год вывода из эксплуатации",
        "Номер энергозоны (код для оптимизации)",
        "Дата ввода блока (фактическая)",
        "Дата вывода блока",
        "Дата модернизации блока",
        "Модернизация целесообразна",
        "external_code",
        "station_external_code",
    ]
    assert row[svc.KEY_MACHINE_CAPACITY] == 100.0
    assert row[svc.KEY_MACHINE_GENERATION] == 0.0
    assert row[svc.KEY_ASH] == 0.0
    assert row[svc.KEY_SO2] == 0.0
    assert row[svc.KEY_NOX] == 0.0
    assert row[svc.KEY_CO2] == 0.0
    assert row[svc.KEY_MODERNIZATION_ADVISABLE] is False
    assert row[svc.KEY_COMMISSION_FACT_DATE] == "01.01.2020"
    assert row[svc.KEY_MACHINE_PLANNED] is True
    assert row[svc.KEY_MACHINE_CODE] == "00000000-0000-0000-0000-000000000011"
    assert row[svc.KEY_STATION_CODE_ON_MACHINE] == "st-1"


def test_build_generation_objects_rows_station_times_year():
    station = SimpleNamespace(
        id=1,
        external_code="st-1",
        name="ТЭС 1",
        station_type=SimpleNamespace(name="ТЭС"),
        condition_type=SimpleNamespace(name="планируемый"),
        union_energy_system="ОЭС Урала",
        regional_district=SimpleNamespace(
            name="Регион",
            synchronous_area=SimpleNamespace(
                name="1 СЗ",
                name_full="1-я синхронная зона ЕЭС России",
            ),
            energy_zone=SimpleNamespace(number="10"),
        ),
    )
    rows = svc.build_generation_objects_rows(
        [station],
        [2032, 2033, 2034],
        {(1, 2032): 100, (1, 2033): 80},
        {(1, 2032): 12},
    )
    assert len(rows) == 2
    assert rows[0][svc.KEY_YEAR] == 2032
    assert rows[0][svc.KEY_CAPACITY] == 100
    assert rows[1][svc.KEY_CAPACITY] == 80
    assert rows[0][svc.KEY_GENERATION] == 12
    assert rows[1][svc.KEY_GENERATION] == 0
    assert rows[0][svc.KEY_PLANNED] is False
    assert rows[1][svc.KEY_PLANNED] is False
    assert rows[0]["Название станции"] == "ТЭС 1"
    assert rows[0]["Субъект станции"] == "Регион"
    assert rows[0]["Зона станции"] == "1-я синхронная зона ЕЭС России"
    assert rows[0][svc.KEY_OES] == "ОЭС Урала"


def test_build_generation_objects_rows_skips_station_without_card_name():
    station = SimpleNamespace(
        id=1,
        external_code="ae2dd8bc-7c23-50da-ac37-d28b043104c4",
        name="",
        name_combined=None,
        name_so=None,
        station_type=None,
        regional_district=None,
        energy_unit=None,
    )
    rows = svc.build_generation_objects_rows(
        [station],
        [2024],
        {},
        {(1, 2024): 63.265},
    )
    assert rows == []


def test_build_generation_objects_rows_planned_when_capacity_appears_later():
    station = SimpleNamespace(
        id=1,
        external_code="st-1",
        name="",
        name_combined="Станция 1",
        name_so=None,
        station_type=SimpleNamespace(name="ТЭС"),
        regional_district=SimpleNamespace(
            name="Ленинградская обл.",
            synchronous_area=SimpleNamespace(
                name="1 СЗ",
                name_full="1-я синхронная зона ЕЭС России",
            ),
            energy_zone=SimpleNamespace(number=None),
        ),
        energy_unit=None,
    )
    rows = svc.build_generation_objects_rows(
        [station],
        [2020, 2021, 2026],
        {(1, 2026): 11},
        {(1, 2020): 69.206},
    )
    assert [r[svc.KEY_YEAR] for r in rows] == [2020, 2021, 2026]
    assert rows[0][svc.KEY_CAPACITY] == 0
    assert rows[0][svc.KEY_PLANNED] is True
    assert rows[0][svc.KEY_GENERATION] == 69.206
    assert rows[1][svc.KEY_PLANNED] is True
    assert rows[2][svc.KEY_CAPACITY] == 11
    assert rows[2][svc.KEY_PLANNED] is False
    assert rows[0]["Название станции"] == "Станция 1"
    assert rows[0]["Зона станции"] == "1-я синхронная зона ЕЭС России"
    assert rows[0]["Субъект станции"] == "Ленинградская обл."
    assert rows[0][svc.KEY_ENERGY_ZONE] is None


def _machine(*, archived=False, **overrides):
    station = SimpleNamespace(
        external_code="st-1",
        name="ТЭС 1",
        station_type=SimpleNamespace(name="ТЭС"),
        regional_district=SimpleNamespace(
            name="Санкт-Петербург",
            synchronous_area=SimpleNamespace(
                name="1 СЗ",
                name_full="1-я синхронная зона ЕЭС России",
            ),
            energy_zone=SimpleNamespace(number="10"),
        ),
        energy_unit=None,
    )
    data = dict(
        id=9,
        external_code="m-1",
        machine_number="1",
        machine_name="Агрегат 1. ТЭС 1",
        is_archived=archived,
        tes_machine_type=SimpleNamespace(name="Угольный блок тип 1"),
        machine_type=SimpleNamespace(name="турбина"),
        machine_station=station,
        date_decompressing_expected=2050,
        date_decompressing_fact="01.01.2025",
        date_commission_fact="01.01.2020",
        date_modernization_power_change_expected=2030,
        date_modernization_no_power_change_expected=None,
        year_modern=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_build_generation_machines_rows_skips_archived():
    rows = svc.build_generation_machines_rows(
        [_machine(archived=True)],
        [2032],
        {(9, 2032): 40},
        {(9, 2032): "уголь"},
    )
    assert rows == []


def test_build_generation_machines_rows_fields_and_planned():
    rows = svc.build_generation_machines_rows(
        [_machine()],
        [2020, 2021, 2026],
        {(9, 2026): 100},
        {(9, 2026): "уголь"},
    )
    assert [r[svc.KEY_YEAR] for r in rows] == [2020, 2021, 2026]
    assert rows[0][svc.KEY_MACHINE_CAPACITY] == 0.0
    assert rows[0][svc.KEY_MACHINE_PLANNED] is True
    assert rows[2][svc.KEY_MACHINE_CAPACITY] == 100.0
    assert rows[2][svc.KEY_MACHINE_PLANNED] is False
    assert rows[2][svc.KEY_MACHINE_NAME] == "Агрегат 1. ТЭС 1"
    assert rows[2][svc.KEY_MACHINE_STATION_TYPE] == "ТЭС"
    assert rows[2][svc.KEY_MACHINE_SUBJECT] == "Санкт-Петербург"
    assert rows[2][svc.KEY_MACHINE_ZONE] == "1-я синхронная зона ЕЭС России"
    assert rows[2][svc.KEY_MACHINE_TYPE] == "Угольный блок тип 1"
    assert rows[2][svc.KEY_FUEL] == "уголь"
    assert rows[2][svc.KEY_ENERGY_ZONE] == 10
    assert rows[2][svc.KEY_DECOMMISSION] == 2024
    assert rows[2][svc.KEY_COMMISSION_FACT_DATE] == "01.01.2020"
    assert rows[2][svc.KEY_DECOMMISSION_DATE] == "01.01.2025"
    assert rows[2][svc.KEY_MODERNIZATION_DATE] == "01.01.2030"
    assert rows[2][svc.KEY_MACHINE_GENERATION] == 0.0
    assert rows[2][svc.KEY_ASH] == 0.0
    assert rows[2][svc.KEY_MODERNIZATION_ADVISABLE] is False
    assert rows[2][svc.KEY_MACHINE_CODE] == "m-1"
    assert rows[2][svc.KEY_STATION_CODE_ON_MACHINE] == "st-1"


def test_dataset_envelope_shape():
    payload = svc.dataset_envelope(
        "generation_stations",
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
    assert payload["dataset"] == "generation_stations"
    assert payload["database_version"] == 7
    assert payload["version_number"] == "ГС-2026"
    assert payload["version"] == 7
    assert payload["comment"] == ""
    assert payload["rows"] == [{"Год": 2032}]


def test_generation_machines_comment_lists_missing_sources():
    text = svc.GENERATION_MACHINES_COMMENT
    assert "твердые частицы (зола), млн т" in text
    assert "Производство агрегатом электроэнергии в году, МВт*ч" in text
    assert "Модернизация целесообразна" in text
    assert "Ожидаемый год модернизации с изменением мощности" in text
    assert "Ожидаемый год модернизации без изменения мощности" in text
    assert "station_external_code" in text
    assert "связи со станцией" in text
    assert text.count("\n\n") == 3
    payload = svc.dataset_envelope(
        "generation_machines",
        database_version=7,
        version_number="ГС-2026",
        comment=text,
        rows=[],
    )
    assert payload["comment"] == text
