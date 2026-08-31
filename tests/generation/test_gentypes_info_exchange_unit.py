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


def test_mock_keys_present_in_constants():
    assert svc.KEY_INSTALLED == "Максимальная мощность, МВт"
    assert "млрд" in svc.KEY_CONSUMPTION
    assert svc.KEY_DEMAND_MAX.startswith("Максимум потребления")


def test_chi_formula():
    assert svc._chi(1000, 100, 200) == 4500.0
    assert svc._chi(1000, 0, 0) == 0.0


def test_consumption_mlrd_divides_all_zones():
    assert svc._consumption_mlrd(125000, is_ees=True) == 125
    assert svc._consumption_mlrd(125000, is_ees=False) == 125
    assert svc._consumption_mlrd(0, is_ees=False) == 0


def test_rounding_helpers():
    assert svc._as_int(253526.8015) == 253527
    assert svc._as_fixed(6980.636078, 1) == 6980.6
    assert svc._as_fixed(200.3249, 2) == 200.32


def test_format_peak_dt():
    from datetime import datetime, timezone

    assert svc._format_peak_dt(None) == 0
    assert (
        svc._format_peak_dt(datetime(2026, 6, 5, 13, 20, tzinfo=timezone.utc))
        == "05.06 13:20"
    )


def test_load_gentypes_years_range(monkeypatch):
    monkeypatch.setattr(
        svc,
        "get_current_year_info",
        lambda version_id: {"current_year": 2025, "sipr_start": 2026, "sipr_end": 2031},
    )
    monkeypatch.setattr(
        svc,
        "_get_planning_period_years_for_version",
        lambda version_id: (2024, 2031),
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [(y,) for y in range(2020, 2032)]

    class _Session:
        def query(self, *a, **k):
            return _Q()

    monkeypatch.setattr(svc.db, "session", _Session())
    years = svc.load_gentypes_years(46)
    assert years[0] == 2020  # 2025-5
    assert years[-1] == 2031
