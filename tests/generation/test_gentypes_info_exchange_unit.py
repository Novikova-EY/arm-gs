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
        "external_code",
    ]
    assert "Прогнозируемые объемы капитальных вложений" not in "".join(row.keys())
    assert row[svc.KEY_ZONE_CODE] == "00000000-0000-0000-0012-000000000001"


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

