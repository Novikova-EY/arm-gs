"""Territory, affiliation and year slices used by operating TES calculations."""
from collections import defaultdict
from decimal import Decimal

from app.ecology.services import operating_tes_page_services as page
from app.ecology.services.operating_tes_fuel_input_services import (
    _distribute,
    empty_fuel_bucket,
    fuel_bucket_for_level,
)


def test_characteristics_and_coefficients_are_resolved_for_one_matching_slice(
    operating_tes_db,
):
    page.upsert_characteristic("vsego", "gas_natural", 2026, "k_co2", "1.5")
    page.upsert_characteristic(
        "centr", "gas_natural", 2026, "k_co2", "2.1", affiliation="prompred"
    )
    page.upsert_coefficient("centr", 2026, "pg_k", "0.7", affiliation="prompred")
    page.upsert_coefficient("centr", 2026, "pg_k", "0.2", affiliation="all")

    char_overrides = page.load_characteristic_overrides([2026])
    coeff_overrides = page.load_coefficient_overrides([2026], "prompred")
    bundle = page.compute_year_bundle(
        "centr", 2026, {"gaz_prir": Decimal("10")}, char_overrides,
        coeff_overrides, affiliation="prompred",
    )

    assert abs(bundle["chars"]["gas_natural"]["k_co2"] - Decimal("2.1")) < Decimal("1e-12")
    assert abs(bundle["coeffs"]["pg_k"] - Decimal("0.7")) < Decimal("1e-12")
    assert abs(bundle["by_key"]["gas_natural"]["pg_motkh"] - Decimal("21.0")) < Decimal("1e-12")
    assert abs(bundle["by_key"]["gas_natural"]["pg"] - Decimal("6.30")) < Decimal("1e-12")
    assert page.resolve_chars(
        "gas_natural", 2026, char_overrides, "centr", "all"
    )["k_co2"] == Decimal("1.5")


def test_characteristic_defaults_are_seeded_for_each_territory_and_affiliation(
    operating_tes_db,
):
    page.ensure_default_persisted_rows([2026])
    rows = operating_tes_db.query(page.OperatingTesFuelCharacteristic).all()
    assert rows
    assert {row.affiliation for row in rows} == {"all", "minen", "prompred"}
    assert {row.territory_slug for row in rows} >= {
        "vsego", "centr", "severo-zapad", "tites-sibir", "tites-vostok",
    }
    assert len({
        (row.territory_slug, row.affiliation, row.fuel_key, row.year_number)
        for row in rows
    }) == len(rows)


def test_fuel_level_buckets_separate_ved_groups_and_keep_legacy_fallback():
    inputs = {2026: defaultdict(empty_fuel_bucket)}
    _distribute(
        inputs[2026], 1, {"centr"}, {"gaz_prir": Decimal("4")}
    )
    _distribute(
        inputs[2026], 3, {"centr"}, {"gaz_prir": Decimal("6")}
    )
    assert fuel_bucket_for_level(inputs, 2026, "centr", "all")["gaz_prir"] == 10
    assert fuel_bucket_for_level(inputs, 2026, "centr", "minen")["gaz_prir"] == 4
    assert fuel_bucket_for_level(inputs, 2026, "centr", "prompred")["gaz_prir"] == 6

    old_snapshot = {2026: {"centr": {"gaz_prir": Decimal("9")}}}
    assert fuel_bucket_for_level(old_snapshot, 2026, "centr", "minen")["gaz_prir"] == 9


def test_characteristic_edit_route_saves_the_selected_affiliation(operating_tes_db, monkeypatch):
    from types import SimpleNamespace
    from flask import Flask
    from app.ecology.routes import operating_tes_routes as routes

    monkeypatch.setattr(routes, "can_edit_ecology", lambda user: True)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace())
    app = Flask(__name__)
    with app.test_request_context(json={
        "year": 2026,
        "row_key": "gas_natural",
        "field": "k_co2",
        "affiliation": "prompred",
        "value": "2,4",
    }, method="PATCH"):
        response = routes.operating_tes_update_value.__wrapped__("centr", "khar-topl")
    assert response.json == {"ok": True}
    overrides = page.load_characteristic_overrides([2026])
    assert abs(overrides[("centr", "prompred", "gas_natural", 2026)]["k_co2"] - Decimal("2.4")) < Decimal("1e-12")


def test_new_fuel_snapshot_empty_affiliation_does_not_fall_back_to_total():
    total = empty_fuel_bucket()
    total["gaz_prir"] = Decimal("9")
    industry = empty_fuel_bucket()
    inputs = {2026: {
        "centr": total,
        "centr::all": total,
        "centr::minen": industry,
    }}
    assert fuel_bucket_for_level(inputs, 2026, "centr", "minen")["gaz_prir"] == 0


def test_fuel_page_shows_selected_year_and_affiliation_across_territories(
    monkeypatch,
):
    from app.ecology.services import fuel_exchange_services
    from app.ecology.services.operating_tes_constants import TERRITORIES

    monkeypatch.setattr(page, "get_year_columns", lambda *args: [2026, 2027])
    monkeypatch.setattr(page, "get_filter_year_list", lambda: [2026, 2027])
    monkeypatch.setattr(page, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(
        page, "get_territory_columns", lambda entries=TERRITORIES: [dict(item) for item in entries]
    )
    monkeypatch.setattr(page, "get_fuel_module_consumption_row_specs", lambda: [
        {"key": "b", "label": "Расход топлива", "unit": "тыс. т у.т.", "kind": "total", "indent": 0},
        {"key": "gaz_prir", "label": "Природный газ", "kind": "value", "indent": 1},
    ])
    monkeypatch.setattr(fuel_exchange_services, "load_accepted_fuel_inputs", lambda years: {
        2026: {
            "vsego::prompred": {"gaz_prir": Decimal("2")},
            "vsego::minen": {"gaz_prir": Decimal("30")},
            "centr::prompred": {"gaz_prir": Decimal("6")},
            "centr::minen": {"gaz_prir": Decimal("80")},
        },
        2027: {
            "vsego::prompred": {"gaz_prir": Decimal("4")},
            "vsego::minen": {"gaz_prir": Decimal("40")},
            "centr::prompred": {"gaz_prir": Decimal("8")},
            "centr::minen": {"gaz_prir": Decimal("90")},
        },
    })

    context = page.build_operating_tes_table_context(
        "centr", "toplivo", affiliation="prompred", view_year=2026,
    )
    row = next(row for row in context["rows"] if row["key"] == "gaz_prir")
    assert context["years"] == [2026]
    assert context["year_columns_mode"] is False
    territory_slugs = {item["slug"] for item in context["territory_columns"]}
    assert "centr" in territory_slugs
    assert "minen" not in territory_slugs
    assert "prompred" not in territory_slugs
    assert row["col_values"]["vsego:2026"] == "2"
    assert row["col_values"]["centr:2026"] == "6"
    assert "centr:2027" not in row["col_values"]


def test_characteristics_page_uses_selected_territory_affiliation_and_year(
    monkeypatch,
):
    from app.ecology.services.operating_tes_constants import TERRITORIES

    monkeypatch.setattr(page, "get_year_columns", lambda *args: [2026, 2027])
    monkeypatch.setattr(page, "get_filter_year_list", lambda: [2026, 2027])
    monkeypatch.setattr(page, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(
        page, "get_territory_columns", lambda entries=TERRITORIES: [dict(item) for item in entries]
    )
    monkeypatch.setattr(page, "get_fuel_module_consumption_row_specs", lambda: [
        {"key": "b", "label": "Расход топлива", "kind": "total", "indent": 0},
        {"key": "gaz_prir", "label": "Природный газ", "kind": "value", "indent": 1},
    ])
    monkeypatch.setattr(page, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(page, "load_characteristic_overrides", lambda years: {
        ("centr", "prompred", "gas_natural", 2026): {"k_co2": Decimal("2.1")},
        ("centr", "prompred", "gas_natural", 2027): {"k_co2": Decimal("2.2")},
    })

    context = page.build_operating_tes_table_context(
        "centr", "khar-topl", affiliation="prompred", view_year=2026,
    )
    row = next(row for row in context["rows"] if row["key"] == "gas_natural")
    assert context["year_columns_mode"] is False
    assert context["years"] == [2026]
    assert [item["slug"] for item in context["territory_columns"]] == ["centr"]
    assert row["char_values"][2026]["k_co2"] == "2,1"
    assert 2027 not in row["char_values"]


def test_emission_page_uses_matching_territory_affiliation_for_all_columns(monkeypatch):
    from app.ecology.services import fuel_exchange_services
    from app.ecology.services.operating_tes_constants import TERRITORIES

    monkeypatch.setattr(page, "get_year_columns", lambda *args: [2026])
    monkeypatch.setattr(page, "get_filter_year_list", lambda: [2026])
    monkeypatch.setattr(page, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(
        page, "get_territory_columns", lambda entries=TERRITORIES: [dict(item) for item in entries]
    )
    monkeypatch.setattr(page, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(page, "load_characteristic_overrides", lambda years: {
        ("centr", "prompred", "gas_natural", 2026): {"k_co2": Decimal("2")},
    })
    monkeypatch.setattr(page, "load_coefficient_overrides", lambda years, affiliation="all": {
        ("centr", 2026, "pg_k"): Decimal("0.75"),
    })
    monkeypatch.setattr(fuel_exchange_services, "load_accepted_fuel_inputs", lambda years: {
        2026: {"centr::prompred": {"gaz_prir": Decimal("10")}},
    })

    context = page.build_operating_tes_table_context(
        "vsego", "pg", affiliation="prompred", view_year=2026,
    )
    column = next(item for item in context["value_columns"] if item["territory_slug"] == "centr")
    fuel_row = next(row for row in context["rows"] if row["key"] == "gas_natural")
    emitted_row = next(row for row in context["rows"] if row["key"] == "pg_emitted")
    assert column["year"] == 2026
    assert fuel_row["col_values"][column["slug"]] == "20"
    assert emitted_row["col_values"][column["slug"]] == "5"
