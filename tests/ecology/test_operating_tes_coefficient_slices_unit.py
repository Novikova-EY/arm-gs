"""Просмотр и сохранение коэффициентов по территории, принадлежности и году."""
from decimal import Decimal
from types import SimpleNamespace

from flask import Flask
import pytest

from app.ecology.services import operating_tes_page_services as services
from app.ecology.services.operating_tes_constants import COEFFICIENT_TERRITORIES


def test_coefficient_slices_are_independent(operating_tes_db, monkeypatch):
    for index, territory in enumerate(COEFFICIENT_TERRITORIES, start=1):
        for offset, affiliation in enumerate(("all", "minen", "prompred")):
            services.upsert_coefficient(territory["slug"], 2026, "ash_eta", Decimal(index + offset) / 100, affiliation)
    services.upsert_coefficient("centr", 2027, "ash_eta", Decimal("0.91"), "minen")
    monkeypatch.setattr(services, "get_current_db_version_id", lambda: 2)
    services.upsert_coefficient("centr", 2026, "ash_eta", Decimal("0.92"), "minen")
    assert services.load_coefficient_overrides([2026], "minen")[("centr", 2026, "ash_eta")] == Decimal("0.92")
    monkeypatch.setattr(services, "get_current_db_version_id", lambda: 1)
    for offset, affiliation in enumerate(("all", "minen", "prompred")):
        overrides = services.load_coefficient_overrides([2026], affiliation)
        for index, territory in enumerate(COEFFICIENT_TERRITORIES, start=1):
            assert overrides[(territory["slug"], 2026, "ash_eta")] == Decimal(index + offset) / 100
    assert services.load_coefficient_overrides([2027], "minen")[("centr", 2027, "ash_eta")] == Decimal("0.91")


@pytest.mark.parametrize("column,territory,affiliation", [
    ("vsego", "vsego", "all"),
    ("minen", "vsego", "minen"),
    ("prompred", "vsego", "prompred"),
    ("centr", "centr", "all"),
    ("norilsk", "tites-sibir", "all"),
    ("isolated-dv", "tites-vostok", "all"),
    ("nikolaevsky", "decentralized-zone", "all"),
    ("severo-zapad", "severo-zapad", "all"),
    ("srednyaya-volga", "srednyaya-volga", "all"),
    ("yug", "yug", "all"),
    ("ural", "ural", "all"),
    ("sibir", "sibir", "all"),
    ("vostok", "vostok", "all"),
])
@pytest.mark.parametrize("eta", [Decimal("0"), Decimal("0.85"), Decimal("1")])
@pytest.mark.parametrize("kind,emitted,raw", [
    ("ash_eta", "ash", "ash_motkh"),
    ("sulfur_eta", "so2", "so2_motkh"),
    ("co_k", "co", "co_motkh"),
    ("nox_n", "nox", "nox_raw"),
    ("pg_k", "pg", "pg_motkh"),
    ("pg_k", "pg_tj", "pg_tj_motkh"),
])
def test_capture_reads_the_matching_coefficient_page_slice(
    operating_tes_db, column, territory, affiliation, eta, kind, emitted, raw,
):
    services.upsert_coefficient(territory, 2026, kind, eta, affiliation)
    if affiliation == "all":
        services.upsert_coefficient(territory, 2026, kind, Decimal("0.13"), "minen")
        services.upsert_coefficient(territory, 2026, kind, Decimal("0.67"), "prompred")
    services.upsert_coefficient(territory, 2027, kind, Decimal("0.42"), affiliation)
    overrides = services.load_coefficient_overrides([2026])
    assert services.resolve_coeff(column, 2026, kind, overrides) == eta
    chars = {("vsego", "gas_natural", 2026): {
        "qh_kcal": "3500", "qh_kj": "1013", "ash": "20", "ash_share": "0.5",
        "sulfur": "2.5", "sulfur_share": "0.1", "q_chem": "0.5", "r_chem": "0.8", "q_mech": "2", "bj": "5",
    }}
    bundle = services.compute_year_bundle(column, 2026, {"gaz_prir": Decimal("100")}, chars, overrides)
    assert bundle["coeffs"][kind] == eta
    assert bundle["by_key"]["gas_natural"][raw] > 0
    assert bundle["by_key"]["gas_natural"][emitted] == bundle["by_key"]["gas_natural"][raw] * (1 - eta)


def test_total_affiliation_remains_available_to_volume_calculations(operating_tes_db):
    services.upsert_coefficient("vsego", 2026, "pg_k", Decimal("0.25"), "minen")
    overrides = services.load_coefficient_overrides([2026])
    assert services.resolve_coeff("minen", 2026, "pg_k", overrides) == Decimal("0.25")
    assert services.resolve_coeff("vsego", 2026, "pg_k", overrides) == Decimal("0")
    assert services.load_coefficient_overrides([2026], "minen")[("vsego", 2026, "pg_k")] == Decimal("0.25")


def test_coefficient_page_reads_only_selected_slice(operating_tes_db, monkeypatch):
    services.upsert_coefficient("tites-sibir", 2026, "ash_eta", Decimal("0.77"), "prompred")
    services.upsert_coefficient("tites-sibir", 2026, "ash_eta", Decimal("0.22"))
    services.upsert_coefficient("tites-sibir", 2027, "ash_eta", Decimal("0.88"), "prompred")
    monkeypatch.setattr(services, "get_year_columns", lambda *args: [2026, 2027])
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2026, 2027])
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {})
    context = services.build_operating_tes_table_context(
        "tites-sibir", "koeff", view_year=2026, affiliation="prompred", rounding_digits=2,
    )
    row = next(row for row in context["rows"] if row["key"] == "ash_eta")
    assert row["col_values"] == {"tites-sibir:2026": "0,77", "tites-sibir:2027": "0,88"}
    assert context["years"] == [2026, 2027]
    assert [column["year"] for column in context["value_columns"]] == [2026, 2027]
    assert context["affiliation"] == "prompred"
    assert len(context["rows"]) == 5


@pytest.mark.parametrize("territory,affiliation,kind", [
    ("unknown", "all", "ash_eta"), ("centr", "unknown", "ash_eta"), ("centr", "all", "unknown"),
])
def test_invalid_coefficient_scope_is_rejected(territory, affiliation, kind):
    with pytest.raises(ValueError):
        services.upsert_coefficient(territory, 2026, kind, 1, affiliation)


@pytest.mark.parametrize("column,territory,affiliation", [
    ("vsego", "vsego", "all"),
    ("minen", "vsego", "minen"),
    ("prompred", "vsego", "prompred"),
    ("centr", "centr", "all"),
    ("norilsk", "tites-sibir", "all"),
    ("isolated-dv", "tites-vostok", "all"),
    ("nikolaevsky", "decentralized-zone", "all"),
])
@pytest.mark.parametrize("sheet,prefix,kind", [
    ("zola", "ash", "ash_eta"), ("sera", "so2", "sulfur_eta"),
    ("azot", "nox", "nox_n"), ("co", "co", "co_k"),
    ("pg", "pg", "pg_k"), ("pg-tj", "pg_tj", "pg_k"),
])
def test_emission_edit_is_shared_with_coefficient_page_and_survives_reload(
    operating_tes_db, monkeypatch, column, territory, affiliation, sheet, prefix, kind,
):
    from app.ecology.routes import operating_tes_routes as routes
    from app.ecology.services import fuel_exchange_services as exchange

    monkeypatch.setattr(services, "get_year_columns", lambda *args: [2026])
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2026])
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(services, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("vsego", "gas_natural", 2026): {
            "qh_kcal": Decimal("3500"), "qh_kj": Decimal("1013"),
            "ash": Decimal("20"), "ash_share": Decimal("0.5"),
            "sulfur": Decimal("2.5"), "sulfur_share": Decimal("0.1"),
            "q_chem": Decimal("0.5"), "r_chem": Decimal("0.8"),
            "q_mech": Decimal("2"), "bj": Decimal("5"),
        },
    })
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {
        2026: {column: {"gaz_prir": Decimal("100")}},
    })
    monkeypatch.setattr(routes, "can_edit_ecology", lambda user: True)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace())
    context = services.build_operating_tes_table_context("vsego", sheet, view_year=2026)
    coefficient_row = next(row for row in context["rows"] if row["key"] == kind)
    value_column = next(col for col in context["value_columns"] if col["territory_slug"] == column)
    target_territory = value_column["coefficient_territory_slug"]
    app = Flask(__name__)
    with app.test_request_context(json={
        "year": value_column["year"], "territory": target_territory, "affiliation": "all",
        "row_key": coefficient_row["key"], "field": coefficient_row["editable_field"], "value": "0,85",
    }, method="PATCH"):
        response = routes.operating_tes_update_value.__wrapped__(target_territory, "koeff")
        assert response.json == {"ok": True}

    saved_context = services.build_operating_tes_table_context(
        territory, "koeff", view_year=2026, affiliation=affiliation,
    )
    saved_row = next(row for row in saved_context["rows"] if row["key"] == kind)
    assert Decimal(saved_row["col_values_raw"][f"{territory}:2026"]) == Decimal("0.85")
    reloaded = services.build_operating_tes_table_context("vsego", sheet, view_year=2026)
    rows = {row["key"]: row for row in reloaded["rows"]}
    column_key = f"{column}:2026"
    total = Decimal(rows[f"{prefix}_motkh_total"]["col_values_raw"][column_key])
    assert total > 0
    assert Decimal(rows[kind]["col_values_raw"][column_key]) == Decimal("0.85")
    assert Decimal(rows[f"{prefix}_emitted"]["col_values_raw"][column_key]) == total * Decimal("0.15")


def test_patch_saves_selected_affiliation_and_rejects_invalid_number(operating_tes_db, monkeypatch):
    from app.ecology.routes import operating_tes_routes as routes

    app = Flask(__name__)
    monkeypatch.setattr(routes, "can_edit_ecology", lambda user: True)
    monkeypatch.setattr(routes, "current_user", SimpleNamespace())
    with app.test_request_context(json={
        "year": 2026, "territory": "decentralized-zone", "affiliation": "prompred",
        "row_key": "ash_eta", "value": "0,85",
    }, method="PATCH"):
        response = routes.operating_tes_update_value.__wrapped__("decentralized-zone", "koeff")
        assert response.json == {"ok": True}
    assert services.load_coefficient_overrides([2026], "prompred")[("decentralized-zone", 2026, "ash_eta")] == Decimal("0.85")
    with app.test_request_context(json={"year": 2026, "row_key": "ash_eta", "value": "not-a-number"}, method="PATCH"):
        response, status = routes.operating_tes_update_value.__wrapped__("centr", "koeff")
        assert status == 400
        assert response.json["ok"] is False
