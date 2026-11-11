# -*- coding: utf-8 -*-
"""Юнит-тесты gentypes_info."""
from app.api.services import gentypes_info_exchange_services as svc


def test_select_gentypes_sheets_keeps_ees_sz_oes_drops_nt():
    sheets = [
        {"slug": "ees-rossii", "sheet_name": "ЕЭС России", "group": "ees"},
        {"slug": "1-sz-ees", "sheet_name": "1-я СЗ ЕЭС", "group": "sz"},
        {"slug": "2-sz-ees-vostok", "sheet_name": "2-я СЗ ЕЭС", "group": "sz"},
        {
            "slug": "severo-zapad",
            "sheet_name": "Северо-Запад",
            "group": "oes",
            "is_ees_member": True,
        },
        {
            "slug": "new-terr",
            "sheet_name": "Новые территории",
            "group": "oes",
            "is_ees_member": False,
        },
        {
            "slug": "tites-sibiri",
            "sheet_name": "ТИТЭС Сибири",
            "group": "oes",
            "is_ees_member": False,
        },
    ]
    selected = svc.select_gentypes_sheets(sheets)
    slugs = [s["slug"] for s in selected]
    assert "ees-rossii" in slugs
    assert "1-sz-ees" in slugs
    assert "severo-zapad" in slugs
    assert "tites-sibiri" in slugs
    assert "new-terr" not in slugs


def test_append_tites_res_sheets_inserts_after_parent(monkeypatch):
    sheets = [
        {
            "slug": "sibir",
            "sheet_name": "ОЭС Сибири",
            "group": "oes",
            "territory": {"kind": "ues", "id": 1, "name": "ОЭС Сибири"},
        },
        {
            "slug": "oes-318",
            "sheet_name": "ТИТЭС Сибири",
            "group": "oes",
            "territory": {"kind": "ues", "id": 318, "name": "ТИТЭС Сибири"},
        },
        {
            "slug": "oes-317",
            "sheet_name": "ТИТЭС Востока",
            "group": "oes",
            "territory": {"kind": "ues", "id": 317, "name": "ТИТЭС Востока"},
        },
        {
            "slug": "eu-254",
            "sheet_name": "Чаун-Билибинский энергорайон",
            "group": "eu",
            "territory": {"kind": "eu", "id": 254},
        },
    ]

    def fake_res(ues_id, parent_slug):
        if ues_id == 318:
            return [
                {
                    "slug": "res-2093",
                    "sheet_name": "ЭС г. Норильска Красноярского края",
                    "group": "res",
                    "parent_slug": parent_slug,
                    "territory": {"kind": "res", "id": 2093},
                }
            ]
        if ues_id == 317:
            return [
                {
                    "slug": "res-2048",
                    "sheet_name": "ЭС Камчатского края",
                    "group": "res",
                    "parent_slug": parent_slug,
                    "territory": {"kind": "res", "id": 2048},
                },
                {
                    "slug": "res-2106",
                    "sheet_name": "ЭС Чукотского АО",
                    "group": "res",
                    "parent_slug": parent_slug,
                    "territory": {"kind": "res", "id": 2106},
                },
            ]
        return []

    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services._res_sheets_for_ues",
        fake_res,
    )
    result = svc.append_tites_res_sheets(sheets)
    slugs = [s["slug"] for s in result]
    assert slugs == [
        "sibir",
        "oes-318",
        "res-2093",
        "oes-317",
        "res-2048",
        "res-2106",
        "eu-254",
    ]


def test_append_tites_res_sheets_skips_duplicate_slug(monkeypatch):
    sheets = [
        {
            "slug": "oes-318",
            "sheet_name": "ТИТЭС Сибири",
            "group": "oes",
            "territory": {"kind": "ues", "id": 318, "name": "ТИТЭС Сибири"},
        },
        {
            "slug": "res-2093",
            "sheet_name": "ЭС г. Норильска Красноярского края",
            "group": "res",
            "territory": {"kind": "res", "id": 2093},
        },
    ]
    monkeypatch.setattr(
        "app.energy_balance.services.power_balance_page_services._res_sheets_for_ues",
        lambda ues_id, parent_slug: [
            {
                "slug": "res-2093",
                "sheet_name": "ЭС г. Норильска Красноярского края",
                "group": "res",
                "parent_slug": parent_slug,
            }
        ],
    )
    result = svc.append_tites_res_sheets(sheets)
    assert [s["slug"] for s in result] == ["oes-318", "res-2093"]


def test_mock_keys_present_in_constants():
    assert svc.KEY_ZONE == "Название зоны"
    assert svc.KEY_INSTALLED == "Максимальная мощность, МВт"
    assert "млрд" in svc.KEY_CONSUMPTION
    assert svc.KEY_DEMAND_MAX.startswith("Максимум потребления")
    assert svc.KEY_OZP_MAX == "Максимум потребления мощности ОЗП, МВт"
    assert svc.KEY_ZONE_CODE == "external_code"


def test_build_gentypes_year_row_mock_key_order():
    row = svc.build_gentypes_year_row(
        year=2024,
        zone="1 синхронная зона",
        consumption=123,
        installed=300000,
        demand_max=2122,
        power_export=100,
        constraints=200,
        q4=100,
        flow=100,
        gaes=100,
        ee_export=200.32,
        chi=100.0,
        peak_dt="05.06 13:20",
        temp=-10,
        combined=100,
        ozp_max=120,
        ozp_peak_dt="11.12 15:23",
        external_code="00000000-0000-0000-0012-000000000001",
    )
    assert list(row.keys()) == [
        "Год",
        "Название зоны",
        "Потребление, млрд. кВт•ч",
        "Максимальная мощность, МВт",
        "Максимум потребления мощности, МВт",
        "Экспорт мощности, МВт",
        "Ограничения, МВт",
        "Вводы мощности после прохождения максимума, МВт",
        "Переток мощности в смежные энергосистемы (выдача (-), прием (+))",
        "Потребление электрической энергии на производственные нужды ГАЭС в насосном режиме, млн. кВт•ч",
        "Экспорт электрической энергии, млрд. кВт•ч",
        "Число часов использования максимума потребления мощности (без учета потребления электрической энергии на производственные нужды ГАЭС в насосном режиме), ч/год",
        "Дата и время прохождения максимума потребления мощности, дд.мм чч:мм",
        "Среднесуточная ТНВ, °С",
        "Потребление мощности на час прохождения максимума потребления мощности ЕЭС России, МВт",
        "Максимум потребления мощности ОЗП, МВт",
        "ОЗП. Дата и время прохождения максимума потребления мощности, дд.мм чч:мм",
        "твердые частицы (зола), млн т",
        "диоксид серы (SO2), млн т",
        "оксиды азота (NOx), млн т",
        "диоксид углерода (CO2), млн т",
        "external_code",
    ]
    assert "Прогнозируемые объемы капитальных вложений" not in "".join(row.keys())
    assert row[svc.KEY_ZONE_CODE] == "00000000-0000-0000-0012-000000000001"
    assert all(row[key] == 0.0 for key in svc._EMISSION_FIELDS)


def test_sheet_external_code_from_territory():
    codes = {("sa", 12): "uuid-sa-12", ("est", 1): "uuid-ees"}
    assert (
        svc._sheet_external_code(
            {"territory": {"kind": "sa", "id": 12}},
            codes,
        )
        == "uuid-sa-12"
    )
    assert (
        svc._sheet_external_code(
            {"territory": {"kind": "res", "id": 48}},
            {("res", 48): "uuid-res-48"},
        )
        == "uuid-res-48"
    )
    assert "res" in svc._KIND_DEMAND
    assert "eu" in svc._KIND_DEMAND
    assert svc._sheet_external_code({"territory": {}}, codes) == ""
    assert svc._chi(1000, 100, 200) == 4500.0
    assert svc._chi(1000, 0, 0) == 0.0
    assert svc._chi_as_on_oes_summary(1727.711524, 0, 317) == 5450
    assert svc._chi_as_on_oes_summary(1000, 100, 200) == 4500


def test_consumption_mlrd_divides_all_zones():
    assert svc._consumption_mlrd(125000) == 125
    assert svc._consumption_mlrd(0) == 0


def test_rounding_helpers():
    assert svc._as_int(253526.8015) == 253527
    assert svc._as_fixed(6980.636078, 1) == 6980.6
    assert svc._as_fixed(200.3249, 2) == 200.32


def test_format_ozp_peak_dt():
    assert svc._format_ozp_peak_dt(None) == 0
    assert svc._format_ozp_peak_dt("") == 0
    assert svc._format_ozp_peak_dt("11.12 15:23") == "11.12 15:23"
    assert svc._format_ozp_peak_dt("5.6 9:20") == "05.06 09:20"
    assert svc._format_ozp_peak_dt("26.11.2019 17:00") == "26.11.2019 17:00"
    from datetime import datetime, timezone

    assert svc._format_peak_dt(None) == 0
    assert svc._format_peak_dt("15.12 18:00") == "15.12 18:00"
    assert (
        svc._format_peak_dt(datetime(2026, 6, 5, 13, 20, tzinfo=timezone.utc))
        == "05.06 13:20"
    )


def test_sum_installed_uses_station_list_total_not_rasp(monkeypatch):
    from decimal import Decimal

    monkeypatch.setattr(svc, "installed_type_keys", lambda: ("installed_tes", "installed_aes"))
    cap = {
        "installed_total": {2025: Decimal("195.675")},
        "installed_tes": {2025: Decimal("195.675")},
        "available_tes": {2025: Decimal("186.325")},
        "constraints": {2025: Decimal("9")},
    }
    assert svc._sum_installed_for_year(cap, 2025) == Decimal("195.675")
    without_total = {
        "installed_tes": {2025: Decimal("195.675")},
        "available_tes": {2025: Decimal("186.325")},
    }
    assert svc._sum_installed_for_year(without_total, 2025) == Decimal("195.675")


def test_format_ozp_peak_dt():
    assert svc._format_ozp_peak_dt(None) == 0
    assert svc._format_ozp_peak_dt("") == 0
    assert svc._format_ozp_peak_dt("11.12 15:23") == "11.12 15:23"
    assert svc._format_ozp_peak_dt("5.6 9:20") == "05.06 09:20"
    assert svc._format_ozp_peak_dt("26.11.2019 17:00") == "26.11.2019 17:00"
    from datetime import datetime, timezone

    assert svc._format_peak_dt(None) == 0
    assert svc._format_peak_dt("15.12 18:00") == "15.12 18:00"
    assert (
        svc._format_peak_dt(datetime(2026, 6, 5, 13, 20, tzinfo=timezone.utc))
        == "05.06 13:20"
    )


def test_load_gentypes_years_uses_shared_exchange_range(monkeypatch):
    monkeypatch.setattr(
        svc,
        "load_exchange_years",
        lambda version_id: list(range(2020, 2032)),
    )
    years = svc.load_gentypes_years(37)
    assert years[0] == 2020
    assert years[-1] == 2031


def _stub_gentypes_loaders(
    monkeypatch, *, extras, demand_max, ozp_by_year, consumption=None, capacity=None
):
    monkeypatch.setattr(
        svc,
        "load_ee_balance_consumption_inputs",
        lambda years, sheets: consumption or {},
    )
    monkeypatch.setattr(
        svc, "load_power_balance_demand_max_inputs", lambda years, sheets: demand_max
    )
    monkeypatch.setattr(svc, "load_power_balance_export_inputs", lambda years, sheets: {})
    monkeypatch.setattr(svc, "load_ee_balance_export_inputs", lambda years, sheets: {})
    monkeypatch.setattr(
        svc,
        "load_power_balance_installed_capacity_inputs",
        lambda years, sheets: capacity or {},
    )
    monkeypatch.setattr(svc, "_load_demand_extras", lambda sheets, years: extras)
    monkeypatch.setattr(svc, "_custom_flow_net_by_slug", lambda sheets, years: {})
    monkeypatch.setattr(svc, "_load_gaes_by_sheet", lambda sheets, years, vid: {})
    monkeypatch.setattr(svc, "_load_ozp_rows_for_years", lambda vid, years: ozp_by_year)
    monkeypatch.setattr(svc, "_load_territory_external_codes", lambda vid: {})
    monkeypatch.setattr(svc, "get_power_balance_sheets", lambda: [])
    monkeypatch.setattr(
        svc, "_load_emissions_by_sheet",
        lambda sheets, years: {sheet["slug"]: {} for sheet in sheets},
    )


def test_ees_combined_uses_without_nt_max_power(monkeypatch):
    from types import SimpleNamespace

    sheets = [{"slug": "ees-rossii", "sheet_name": "ЕЭС России", "group": "ees"}]
    extras = {
        "ees-rossii": {
            "peak_datetime": {2024: "15.01 10:00"},
            "avg_daily_air_temp_c": {2024: -13},
            "combined_on_ees": {},
            "demand_max": {2024: 165434},
        }
    }
    _stub_gentypes_loaders(
        monkeypatch,
        extras=extras,
        demand_max={"ees-rossii": {"demand_max": {2024: 165434}}},
        ozp_by_year={
            2024: SimpleNamespace(max_power_mw=168741, peak_datetime="11.12.2023 12:00")
        },
    )
    rows = svc.build_gentypes_info_rows(years=[2024], sheets=sheets, version_id=37)
    assert rows[0][svc.KEY_COMBINED] == 165434
    assert rows[0][svc.KEY_DEMAND_MAX] == 165434
    assert rows[0][svc.KEY_TEMP] == -13
    assert rows[0][svc.KEY_PEAK_DT] == "15.01 10:00"
    assert rows[0][svc.KEY_OZP_MAX] == 168741
    assert rows[0][svc.KEY_OZP_PEAK_DT] == "11.12.2023 12:00"


def test_sz_combined_from_without_nt_and_ozp_only_on_ees(monkeypatch):
    from types import SimpleNamespace

    sheets = [
        {"slug": "ees-rossii", "sheet_name": "ЕЭС России", "group": "ees"},
        {"slug": "1-sz-ees", "sheet_name": "Первая синхронная зона", "group": "sz"},
    ]
    extras = {
        "1-sz-ees": {
            "peak_datetime": {2024: "15.01 10:00"},
            "avg_daily_air_temp_c": {2024: None},
            "combined_on_ees": {2024: 158241},
            "demand_max": {2024: 158241},
        }
    }
    _stub_gentypes_loaders(
        monkeypatch,
        extras=extras,
        demand_max={"1-sz-ees": {"demand_max": {2024: 158241}}},
        ozp_by_year={
            2024: SimpleNamespace(max_power_mw=168741, peak_datetime="11.12.2023 12:00")
        },
    )
    rows = svc.build_gentypes_info_rows(years=[2024], sheets=sheets, version_id=37)
    by_zone = {row[svc.KEY_ZONE]: row for row in rows}
    sz = by_zone["Первая синхронная зона"]
    ees = by_zone["ЕЭС России"]
    assert sz[svc.KEY_COMBINED] == 158241
    assert sz[svc.KEY_DEMAND_MAX] == 158241
    assert sz[svc.KEY_PEAK_DT] == "15.01 10:00"
    assert sz[svc.KEY_OZP_MAX] == 0
    assert sz[svc.KEY_OZP_PEAK_DT] == 0
    assert ees[svc.KEY_OZP_MAX] == 168741
    assert ees[svc.KEY_OZP_PEAK_DT] == "11.12.2023 12:00"


def test_tites_east_demand_max_sums_res_from_oes_summary(monkeypatch):
    sheets = [
        {
            "slug": "oes-317",
            "sheet_name": "ТИТЭС Востока",
            "group": "oes",
            "skip_table": True,
            "territory": {"kind": "ues", "id": 317, "name": "ТИТЭС Востока"},
        },
        {
            "slug": "res-2048",
            "sheet_name": "ЭС Камчатского края",
            "group": "res",
            "parent_slug": "oes-317",
            "territory": {"kind": "res", "id": 2048},
        },
        {
            "slug": "res-2059",
            "sheet_name": "ЭС Магаданской области",
            "group": "res",
            "parent_slug": "oes-317",
            "territory": {"kind": "res", "id": 2059},
        },
        {
            "slug": "res-2089",
            "sheet_name": "ЭС Сахалинской области",
            "group": "res",
            "parent_slug": "oes-317",
            "territory": {"kind": "res", "id": 2089},
        },
        {
            "slug": "eu-258",
            "sheet_name": "Центральный энергорайон Камчатского края",
            "group": "eu",
            "parent_slug": "oes-317",
            "territory": {"kind": "eu", "id": 258},
        },
        {
            "slug": "oes-318",
            "sheet_name": "ТИТЭС Сибири",
            "group": "oes",
            "territory": {"kind": "ues", "id": 318, "name": "ТИТЭС Сибири"},
        },
        {
            "slug": "res-2093",
            "sheet_name": "ЭС г. Норильска Красноярского края",
            "group": "res",
            "parent_slug": "oes-318",
            "territory": {"kind": "res", "id": 2093},
        },
    ]
    _stub_gentypes_loaders(
        monkeypatch,
        extras={
            "res-2048": {
                "peak_datetime": {2025: "15.01 19:00"},
                "avg_daily_air_temp_c": {2025: -11.5},
                "combined_on_ees": {2025: 100},
            },
            "res-2089": {
                "peak_datetime": {2025: "31.12 19:00"},
                "avg_daily_air_temp_c": {2025: -5.8},
                "combined_on_ees": {2025: 200},
            },
        },
        demand_max={
            "res-2048": {"demand_max": {2025: 317}},
            "res-2059": {"demand_max": {2025: 435}},
            "res-2089": {"demand_max": {2025: 496}},
            "eu-258": {"demand_max": {2025: 290}},
            "oes-318": {"demand_max": {2025: 1079}},
            "res-2093": {"demand_max": {2025: 1067}},
        },
        consumption={
            "res-2048": {"consumption": {2025: 1727.7}},
            "res-2059": {"consumption": {2025: 3191.9}},
            "res-2089": {"consumption": {2025: 2928.5}},
            "eu-258": {"consumption": {2025: 1727.7}},
            "oes-318": {"consumption": {2025: 16000}},
            "res-2093": {"consumption": {2025: 7678}},
        },
        ozp_by_year={},
        capacity={
            "oes-317": {"installed_total": {2025: 3106.434}},
            "res-2048": {
                "installed_total": {2025: 485.15},
                "installed_tes": {2025: 485.15},
                "available_tes": {2025: 448.85},
            },
            "res-2059": {"installed_total": {2025: 1790}},
            "res-2089": {"installed_total": {2025: 635.609}},
            "eu-258": {"installed_total": {2025: 485.15}},
            "oes-318": {"installed_total": {2025: 2288.64}},
            "res-2093": {
                "installed_total": {2025: 2288.64},
                "installed_tes": {2025: 2288.64},
                "available_tes": {2025: 1646.36},
            },
        },
    )
    rows = svc.build_gentypes_info_rows(years=[2025], sheets=sheets, version_id=37)
    by_zone = {row[svc.KEY_ZONE]: row for row in rows}
    assert by_zone["ТИТЭС Востока"][svc.KEY_DEMAND_MAX] == 1248
    assert by_zone["ЭС Камчатского края"][svc.KEY_DEMAND_MAX] == 317
    assert by_zone["ТИТЭС Сибири"][svc.KEY_DEMAND_MAX] == 1079
    assert by_zone["ТИТЭС Востока"][svc.KEY_CONSUMPTION] == 8
    assert by_zone["ЭС Камчатского края"][svc.KEY_CONSUMPTION] == 2
    assert by_zone["ТИТЭС Сибири"][svc.KEY_CONSUMPTION] == 16
    assert by_zone["ЭС Камчатского края"][svc.KEY_CHI] == 5450
    assert by_zone["ТИТЭС Востока"][svc.KEY_CHI] == 6289
    assert by_zone["ТИТЭС Сибири"][svc.KEY_CHI] == 14828.5
    assert by_zone["ТИТЭС Востока"][svc.KEY_PEAK_DT] == "31.12 19:00"
    assert by_zone["ТИТЭС Востока"][svc.KEY_TEMP] == -5.8
    assert by_zone["ТИТЭС Востока"][svc.KEY_COMBINED] == 300
    assert by_zone["ЭС Камчатского края"][svc.KEY_COMBINED] == 100
    assert by_zone["ТИТЭС Сибири"][svc.KEY_COMBINED] == 0
    assert by_zone["ТИТЭС Востока"][svc.KEY_INSTALLED] == 3106
    assert by_zone["ЭС Камчатского края"][svc.KEY_INSTALLED] == 485
    assert by_zone["Центральный энергорайон Камчатского края"][svc.KEY_INSTALLED] == 485
    assert by_zone["ТИТЭС Сибири"][svc.KEY_INSTALLED] == 2289
    assert by_zone["ЭС г. Норильска Красноярского края"][svc.KEY_INSTALLED] == 2289




def test_emissions_use_main_total_table_by_year_and_territory(monkeypatch):
    from decimal import Decimal

    sheets = [
        {"slug": svc.EES_RUSSIA_WITH_TITES_SLUG, "group": "ees", "sheet_name": "ЭЭС России"},
        {"slug": "ees-rossii", "group": "ees", "sheet_name": "ЕЭС России"},
        {"slug": "centr", "group": "oes", "sheet_name": "Центр"},
        {"slug": "2-sz-ees-vostok", "group": "sz", "sheet_name": "2-я СЗ ЕЭС (ОЭС Востока)"},
        {"slug": "1-sz-ees", "group": "sz", "source_slugs": ("centr", "sibir")},
        {"slug": "sibir", "group": "oes", "sheet_name": "Сибирь"},
        {"slug": "oes-317", "group": "oes", "sheet_name": "ТИТЭС Востока"},
        {"slug": "oes-318", "group": "oes", "sheet_name": "ТИТЭС Сибири"},
        {"slug": "res-1", "group": "res", "sheet_name": "ЭС Камчатского края"},
        {"slug": "eu-1", "group": "eu", "sheet_name": "Николаевский энергорайон"},
    ]
    calls = []

    def context(territory, tab, **filters):
        calls.append((territory, tab, filters))
        year = filters["view_year"]
        factor = Decimal(year - 2023)
        base = {
            "vsego": Decimal("99999.987654"), "centr": Decimal("1234.567891"),
            "sibir": Decimal("2000"), "vostok": Decimal("3000"),
            "norilsk": Decimal("4000"), "isolated-dv": Decimal("5000"),
            "minen": Decimal("80000"), "prompred": Decimal("90000"),
        }
        return {
            "view_year": year,
            "value_columns": [
                {"slug": f"{slug}:{year}", "territory_slug": slug, "year": year}
                for slug in base
            ],
            "rows": [
                {"key": metric, "col_values_raw": {
                    f"{slug}:{year}": str(value * factor * multiplier)
                    for slug, value in base.items()
                }}
                for multiplier, metric in enumerate(svc._EMISSION_FIELDS.values(), 1)
            ],
            "summary_volume_tables": [{"rows": []}],
        }

    monkeypatch.setattr(svc, "build_calculation_summary_context", context)
    result = svc._load_emissions_by_sheet(sheets, [2024, 2025])
    for multiplier, key in enumerate(svc._EMISSION_FIELDS, 1):
        assert result[svc.EES_RUSSIA_WITH_TITES_SLUG][2024][key] == float(Decimal("99.999987654") * multiplier)
        assert result["ees-rossii"][2024][key] == float(Decimal("6.234567891") * multiplier)
        assert result["1-sz-ees"][2024][key] == float(Decimal("3.234567891") * multiplier)
        assert result["2-sz-ees-vostok"][2024][key] == 3 * multiplier
        assert result["centr"][2024][key] == float(Decimal("1.234567891") * multiplier)
        assert result["oes-317"][2024][key] == 5 * multiplier
        assert result["oes-318"][2024][key] == 4 * multiplier
        assert result["centr"][2025][key] == float(Decimal("2.469135782") * multiplier)
        assert result["res-1"][2024][key] == 0.0
        assert result["eu-1"][2024][key] == 0.0
    assert calls == [
        ("vsego", "russia", {"start_year": year, "end_year": year, "view_year": year})
        for year in (2024, 2025)
    ]


def test_emissions_do_not_substitute_another_year(monkeypatch):
    monkeypatch.setattr(
        svc, "build_calculation_summary_context",
        lambda *args, **kwargs: {"view_year": 2024},
    )
    assert svc._load_emissions_by_sheet([{"slug": "ees-rossii"}], [2020]) == {"ees-rossii": {}}


def test_emissions_are_passed_to_dataset_rows(monkeypatch):
    _stub_gentypes_loaders(monkeypatch, extras={}, demand_max={}, ozp_by_year={})
    emissions = {key: 0.123456789 for key in svc._EMISSION_FIELDS}
    monkeypatch.setattr(
        svc, "_load_emissions_by_sheet", lambda sheets, years: {"centr": {2024: emissions}},
    )
    rows = svc.build_gentypes_info_rows(
        years=[2024, 2025], sheets=[{"slug": "centr", "sheet_name": "Центр"}], version_id=37,
    )
    for key in svc._EMISSION_FIELDS:
        assert rows[0][key] == emissions[key]
        assert rows[1][key] == 0.0



def test_ees_russia_uses_existing_balance_totals(monkeypatch):
    def table(values):
        return {"rows": [
            {"key": key, "year_values_raw": {2024: str(value)}}
            for key, value in values.items()
        ]}

    power = table({
        "installed_total": 500100.4, "demand_max": 220000, "export": 123.6,
        "constraints": 1200.2, "commissioning_after_max": 55.5, "flow_total": -700,
    })
    energy = table({"consumption": 1100000, "gaes_charge": 1000, "ee_export": 32.123})
    calls = []

    def load_power(slug, **filters):
        calls.append((slug, filters))
        return power

    monkeypatch.setattr(svc, "build_power_balance_table_context", load_power)
    monkeypatch.setattr(svc, "build_ee_balance_table_context", lambda *args, **kwargs: energy)
    emissions = {key: 0.123456789 for key in svc._EMISSION_FIELDS}
    rows = svc._build_ees_russia_rows(
        [2024], {2024: emissions},
        [
            {svc.KEY_YEAR: 2024, svc.KEY_ZONE: "ees", svc.KEY_COMBINED: 200000},
            {svc.KEY_YEAR: 2024, svc.KEY_ZONE: "tites", svc.KEY_COMBINED: 300},
            {svc.KEY_YEAR: 2024, svc.KEY_ZONE: "child", svc.KEY_COMBINED: 999},
        ],
        ("ees-rossii", "tites"),
        [{"slug": "ees-rossii", "sheet_name": "ees"}, {"slug": "tites", "sheet_name": "tites"}],
    )
    row = rows[0]
    assert row[svc.KEY_ZONE] == svc.EES_RUSSIA_WITH_TITES_NAME
    assert row[svc.KEY_INSTALLED] == 500100
    assert row[svc.KEY_DEMAND_MAX] == 220000
    assert row[svc.KEY_POWER_EXPORT] == 124
    assert row[svc.KEY_CONSTRAINTS] == 1200
    assert row[svc.KEY_Q4] == 56
    assert row[svc.KEY_FLOW] == -700
    assert row[svc.KEY_GAES] == 1000
    assert row[svc.KEY_EE_EXPORT] == 32.12
    assert row[svc.KEY_CONSUMPTION] == 1100
    assert row[svc.KEY_CHI] == svc._chi(1100000, 1000, 220000)
    assert row[svc.KEY_COMBINED] == 200300
    assert row[svc.KEY_PEAK_DT] == row[svc.KEY_TEMP] == row[svc.KEY_OZP_MAX] == row[svc.KEY_OZP_PEAK_DT] == 0
    assert row[svc.KEY_ZONE_CODE] == ""
    assert all(row[key] == emissions[key] for key in emissions)
    assert calls == [(svc.EES_RUSSIA_WITH_TITES_SLUG, {"start_year": 2024, "end_year": 2024})]


def test_dataset_adds_ees_before_ees_and_restores_version(app, monkeypatch):
    from flask import g

    base = [{"slug": "ees-rossii", "sheet_name": "ees", "group": "ees"}]
    aggregate = {"slug": svc.EES_RUSSIA_WITH_TITES_SLUG, "source_slugs": ("ees-rossii",)}
    monkeypatch.setattr(svc, "resolve_database_version", lambda version_id: (version_id, "test"))
    monkeypatch.setattr(svc, "load_gentypes_years", lambda version_id: [2024, 2025])
    monkeypatch.setattr(svc, "get_power_balance_sheets", lambda: base)
    monkeypatch.setattr(svc, "append_tites_res_sheets", lambda sheets: list(sheets))
    monkeypatch.setattr(svc, "_ees_russia_with_tites_sheet", lambda sheets: aggregate)

    def rows(**kwargs):
        assert g.current_db_version == 37
        assert kwargs["years"] == [2024]
        assert kwargs["sheets"] == [aggregate, *base]
        return [{svc.KEY_YEAR: 2024}]

    monkeypatch.setattr(svc, "build_gentypes_info_rows", rows)
    with app.app_context():
        g.current_db_version = 38
        payload = svc.load_gentypes_info_dataset(version_id=37, year=2024)
        assert g.current_db_version == 38
    assert payload["rows"] == [{svc.KEY_YEAR: 2024}]
    assert payload["database_version"] == 37
    assert payload["comment"] == ""
