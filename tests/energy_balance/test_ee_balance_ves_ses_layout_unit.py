from decimal import Decimal

from app.energy_balance.services.ee_balance_ves_ses_page_services import (
    CHIIM_FORMULA_TOOLTIP,
    DATA_LABEL_CAPACITY,
    DATA_LABEL_CAPACITY_SES,
    DATA_LABEL_CAPACITY_VES,
    DATA_LABEL_CHIIM,
    DATA_LABEL_ENERGY,
    _capacity_data_label,
    _chiim_display_map,
    _chiim_hours,
    _finalize_total,
    _format_cell,
    _raw_title,
    _ves_ses_station_row_sort_key,
    _visible_owner_years,
    resolve_ves_ses_year_columns,
)


def test_capacity_labels_follow_station_type():
    assert _capacity_data_label("ves") == DATA_LABEL_CAPACITY_VES
    assert _capacity_data_label("ses") == DATA_LABEL_CAPACITY_SES
    assert _capacity_data_label("other") == DATA_LABEL_CAPACITY


def test_station_rows_sort_ves_then_ses_alphabetically():
    rows = [
        {"id": 4, "name": "Ясная СЭС", "type_key": "ses"},
        {"id": 1, "name": "Бурейская ВЭС", "type_key": "ves"},
        {"id": 3, "name": "Амурская СЭС", "type_key": "ses"},
        {"id": 2, "name": "Амурская ВЭС", "type_key": "ves"},
    ]
    ordered = sorted(rows, key=_ves_ses_station_row_sort_key)
    assert [row["name"] for row in ordered] == [
        "Амурская ВЭС",
        "Бурейская ВЭС",
        "Амурская СЭС",
        "Ясная СЭС",
    ]


def test_chiim_hours_from_generation_and_installed_capacity():
    assert _chiim_hours(Decimal("3.7"), Decimal("5.1")) == Decimal("3700") / Decimal("5.1")
    assert _chiim_hours(Decimal("3.7"), Decimal("0")) is None
    assert _chiim_hours(None, Decimal("5.1")) is None


def test_chiim_uses_raw_db_values_not_display_rounding():
    # 0,1578/0,6*1000 ≈ 263 по сырым из БД; при округлении отображения 0,2/0,6 дало бы 333.
    years = [2022]
    energy = {2022: Decimal("0.1578")}
    capacity = {2022: Decimal("0.6")}
    assert _chiim_display_map(energy, capacity, years)[2022] == "263"
    assert _format_cell(Decimal("0.1578"), 1) == "0,2"


def test_raw_title_shows_unrounded_db_value():
    assert _raw_title(Decimal("0.1578")) == "0,1578"
    assert _raw_title(None) == ""
    assert _raw_title(9.843585999999998) == "9,843586"


def test_finalize_total_has_three_metric_labels():
    years = [2024, 2025]
    total = {
        "capacity": {2024: Decimal("5.1"), 2025: Decimal("5.1")},
        "energy": {2024: Decimal("3.7"), 2025: Decimal("8.7")},
        "owner": {2024: None, 2025: None},
        "min_value": None,
    }
    row = _finalize_total(total, years, 1, "в т.ч. ВЭС", "type_total", type_key="ves")
    assert row["capacity_label"] == DATA_LABEL_CAPACITY_VES
    assert row["energy_label"] == DATA_LABEL_ENERGY
    assert row["chiim_label"] == DATA_LABEL_CHIIM
    assert row["chiim_display"][2024] == _chiim_display_map(
        total["energy"], total["capacity"], years
    )[2024]
    assert row["capacity_raw"][2024] == "5,1"
    assert row["type_name"] == "ВЭС"


def test_chiim_formula_tooltip_mentions_generation_and_installed_capacity():
    assert "× 1000" in CHIIM_FORMULA_TOOLTIP
    assert "Выработка электрической энергии" in CHIIM_FORMULA_TOOLTIP
    assert "Установленная мощность" in CHIIM_FORMULA_TOOLTIP


def test_visible_owner_years_include_current_and_plan_inside_range():
    years = [2023, 2024, 2025, 2026, 2027]
    features = {
        2023: "факт",
        2024: "факт",
        2025: "текущий",
        2026: "план",
        2027: "план",
        2028: "план",
    }
    assert _visible_owner_years(years, features) == [2025, 2026, 2027]


def test_default_year_columns_include_seven_fact_years(monkeypatch):
    monkeypatch.setattr(
        "app.energy_balance.services.ee_balance_ves_ses_page_services.get_ee_balance_filter_year_list",
        lambda: list(range(2010, 2040)),
    )
    years = resolve_ves_ses_year_columns(year_features={2025: "текущий"})
    assert years[0] == 2018
    assert years[-1] == 2031
    assert 2024 in years
    assert 2025 in years


def test_format_cell_shows_blank_for_zero():
    assert _format_cell(Decimal("0"), 1) == ""
    assert _format_cell(Decimal("0.0"), 1) == ""
    assert _format_cell(Decimal("0.04"), 1) == ""
    assert _format_cell(Decimal("0"), -1) == ""
    assert _format_cell(Decimal("1.2"), 1) == "1,2"


def test_format_cell_no_rounding_keeps_fraction():
    assert _format_cell(Decimal("0.1578"), 0) == "0,1578"
    assert _format_cell(Decimal("9.843586"), 0) == "9,843586"
    assert _format_cell(9.843585999999998, 0) == "9,843586"
