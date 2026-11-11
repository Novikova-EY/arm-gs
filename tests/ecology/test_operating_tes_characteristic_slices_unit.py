"""Общие характеристики топлива при независимых годах и версиях БД."""
from decimal import Decimal

import pytest

from app.ecology.services import operating_tes_page_services as services
from app.ecology.services.operating_tes_constants import (
    COEFFICIENT_TERRITORIES,
    DEFAULT_CHARACTERISTICS,
    TERRITORIES,
)


@pytest.fixture
def fuel_row_specs(monkeypatch):
    specs = [
        {"key": "b", "label": "Расход топлива", "kind": "total", "indent": 0},
        {"key": "ugol", "label": "Уголь из справочника", "kind": "total", "indent": 0},
        {"key": "arkt", "label": "Арктический", "kind": "value", "indent": 1},
        {"key": "gaz", "label": "Газ из справочника", "kind": "total", "indent": 0},
        {"key": "gaz_prir", "label": "Природный газ из справочника", "kind": "value", "indent": 1},
        {"key": "slan", "label": "Сланцы", "kind": "value", "indent": 0},
    ]
    monkeypatch.setattr(services, "get_fuel_module_consumption_row_specs", lambda: specs)
    return specs


def test_saved_characteristics_are_independent_by_level_year_and_version(operating_tes_db, monkeypatch):
    level_territories = [
        item for item in TERRITORIES if item["slug"] not in {"minen", "prompred"}
    ]
    for index, territory in enumerate(level_territories, start=1):
        services.upsert_characteristic(territory["slug"], "gas_natural", 2031, "k_co2", index)
        assert operating_tes_db.query(services.OperatingTesFuelCharacteristic).count() == index
    services.upsert_characteristic("vsego", "gas_natural", 2030, "k_co2", 20)
    monkeypatch.setattr(services, "get_current_db_version_id", lambda: 2)
    services.upsert_characteristic("prompred", "gas_natural", 2031, "k_co2", 30)
    assert services.load_characteristic_overrides([2031])[("prompred", "all", "gas_natural", 2031)]["k_co2"] == 30
    monkeypatch.setattr(services, "get_current_db_version_id", lambda: 1)
    overrides = services.load_characteristic_overrides([2030, 2031])
    assert len(overrides) == len(level_territories) + 1
    for index, territory in enumerate(level_territories, start=1):
        bundle = services.compute_year_bundle(
            territory["slug"], 2031, {"gaz_prir": Decimal("10")}, overrides, {},
        )
        assert bundle["volumes"]["co2"] == Decimal(10 * index)
    assert services.resolve_chars("gas_natural", 2030, overrides)["k_co2"] == 20
    assert services.resolve_chars("gas_natural", 2029, overrides)["k_co2"] == DEFAULT_CHARACTERISTICS["gas_natural"]["k_co2"]


def test_updating_and_clearing_characteristics_is_scoped_to_territory(operating_tes_db):
    services.upsert_characteristic("vsego", "gas_natural", 2031, "tut_per_t", 2)
    services.upsert_characteristic("centr", "gas_natural", 2031, "tut_per_t", 5)
    overrides = services.load_characteristic_overrides([2031])
    assert services.resolve_chars("gas_natural", 2031, overrides, "centr")["tut_per_t"] == 5
    assert services.resolve_chars("gas_natural", 2031, overrides, "vsego")["tut_per_t"] == 2
    services.upsert_characteristic("centr", "gas_natural", 2031, "tut_per_t", None)
    overrides = services.load_characteristic_overrides([2031])
    assert services.resolve_chars("gas_natural", 2031, overrides, "centr")["tut_per_t"] == 2
    assert services.resolve_chars("gas_natural", 2031, overrides, "vsego")["tut_per_t"] == 2
    assert operating_tes_db.query(services.OperatingTesFuelCharacteristic).count() == 2


@pytest.mark.parametrize("slug,fuel", [("unknown", "gas_natural"), ("centr", "unknown")])
def test_invalid_slice_or_fuel_is_rejected(fuel_row_specs, slug, fuel):
    with pytest.raises(ValueError):
        services.upsert_characteristic(slug, fuel, 2031, "tut_per_t", 1)


def test_territory_characteristic_rows_are_loaded_and_used(operating_tes_db):
    services.upsert_characteristic("vsego", "gas_natural", 2031, "k_co2", 2)
    operating_tes_db.add(services.OperatingTesFuelCharacteristic(
        territory_slug="centr", fuel_key="gas_natural", year_number=2031,
        database_version_id=1, k_co2=5,
    ))
    operating_tes_db.commit()
    overrides = services.load_characteristic_overrides([2031])
    assert set(overrides) == {
        ("vsego", "all", "gas_natural", 2031),
        ("centr", "all", "gas_natural", 2031),
    }
    assert services.resolve_chars("gas_natural", 2031, overrides, "centr")["k_co2"] == 5
    assert operating_tes_db.query(services.OperatingTesFuelCharacteristic).count() == 2


def test_basin_fallback_uses_shared_characteristics():
    overrides = {
        ("centr", "kuzn_gd", 2031): {"k_co2": Decimal("5")},
        ("vsego", "kuzn_gd", 2031): {"k_co2": Decimal("2")},
    }
    for territory in TERRITORIES:
        bundle = services.compute_year_bundle(territory["slug"], 2031, {"kuzn": Decimal("10")}, overrides, {})
        assert bundle["volumes"]["co2"] == 20


def test_default_characteristics_seed_each_level_only_once(operating_tes_db):
    services.ensure_default_persisted_rows([2030, 2031])
    services.ensure_default_persisted_rows([2030, 2031])
    rows = operating_tes_db.query(services.OperatingTesFuelCharacteristic).all()
    expected_rows = 2 * len(DEFAULT_CHARACTERISTICS) * len(COEFFICIENT_TERRITORIES) * 3
    assert len(rows) == expected_rows
    assert {row.territory_slug for row in rows} == {
        territory["slug"] for territory in COEFFICIENT_TERRITORIES
    }
    assert {row.affiliation for row in rows} == {"all", "minen", "prompred"}
    coefficients = operating_tes_db.query(services.OperatingTesCoefficient).all()
    assert {row.territory_slug for row in coefficients} == {territory["slug"] for territory in TERRITORIES}


def test_characteristic_table_shows_selected_level_and_year(monkeypatch, fuel_row_specs):
    monkeypatch.setattr(services, "get_year_columns", lambda *args: [2030, 2031])
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2030, 2031])
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(services, "ensure_default_persisted_rows", lambda years: None)
    monkeypatch.setattr(services, "load_characteristic_overrides", lambda years: {
        ("centr", "all", "gas_natural", 2031): {"k_co2": Decimal("5")},
        ("vsego", "all", "gas_natural", 2030): {"k_co2": Decimal("3")},
        ("vsego", "all", "gas_natural", 2031): {"k_co2": Decimal("2")},
    })
    for territory in TERRITORIES:
        context = services.build_operating_tes_table_context(
            territory["slug"], "khar-topl", view_year=2031,
        )
        row = next(row for row in context["rows"] if row["key"] == "gas_natural")
        expected_2031 = "5" if territory["slug"] == "centr" else "2"
        assert set(row["char_values"]) == {2031}
        assert row["char_values"][2031]["k_co2"] == expected_2031
        assert "k_natural" not in row["char_values"][2031]
        assert "k_natural" not in {column["key"] for column in context["char_columns"]}
        assert context["years"] == [2031]
        assert context["range_years"] == [2030, 2031]
        assert context["year_columns_mode"] is False
        assert len([row for row in context["rows"] if row["key"] == "gas_natural"]) == 1


def test_characteristic_rows_follow_fuel_page_and_keep_saved_values(
    operating_tes_db, monkeypatch, fuel_row_specs,
):
    from app.ecology.services import fuel_exchange_services as exchange
    from app.ecology.services.operating_tes_constants import FUEL_PARAM_FIELDS, TOP_INPUT_ROWS

    monkeypatch.setattr(services, "get_year_columns", lambda *args: [2026, 2027])
    monkeypatch.setattr(services, "get_filter_year_list", lambda: [2026, 2027])
    monkeypatch.setattr(services, "get_year_feature_dict", lambda: {})
    monkeypatch.setattr(exchange, "load_accepted_fuel_inputs", lambda years: {})
    services.upsert_characteristic("centr", "gas_natural", 2026, "k_co2", "2.3")
    services.upsert_characteristic("centr", "slan", 2026, "ash", "15.2")
    services.upsert_characteristic("centr", "arkt", 2026, "ash", "8.4")

    def check_rows():
        fuel = services.build_operating_tes_table_context("vsego", "toplivo", view_year=2026)
        chars = services.build_operating_tes_table_context("centr", "khar-topl", view_year=2026)
        fuel_rows = fuel["rows"][len(TOP_INPUT_ROWS) + 1:]
        assert [(row["label"], row["indent"], row["kind"]) for row in chars["rows"]] == [
            (row["label"], row["indent"], row["kind"]) for row in fuel_rows
        ]
        assert [FUEL_PARAM_FIELDS.get(row["key"], row["key"]) for row in chars["rows"]] == [
            row["key"] for row in fuel_rows
        ]
        assert "b" not in {row["key"] for row in chars["rows"]}
        rows = {row["key"]: row for row in chars["rows"]}
        assert rows["gas_natural"]["char_values"][2026]["k_co2"] == "2,3"
        assert rows["slan"]["char_values"][2026]["ash"] == "15,2"
        assert rows["arkt"]["char_values"][2026]["ash"] == "8,4"
        assert rows["slan"]["editable_values"] is True
        assert rows["coal"]["editable_values"] is False
        assert rows["coal"]["is_empty"] is False
        assert rows["coal"]["css_class"] == "table-info fw-bold"

    check_rows()
    # Изменение подписи, порядка и родителя справочника отражается на обеих вкладках.
    fuel_row_specs[2]["label"] = "Арктический (новое название)"
    fuel_row_specs[2]["indent"] = 2
    fuel_row_specs[2], fuel_row_specs[4] = fuel_row_specs[4], fuel_row_specs[2]
    check_rows()


@pytest.mark.parametrize("field", ["k_natural", ""])
def test_removed_or_missing_characteristic_field_is_rejected(operating_tes_db, field):
    with pytest.raises(ValueError, match="Неизвестное поле характеристики"):
        services.upsert_characteristic("vsego", "gas_natural", 2026, field, 1)
    assert operating_tes_db.query(services.OperatingTesFuelCharacteristic).count() == 0


@pytest.mark.parametrize("fuel", ["b", "e", "unknown"])
def test_non_fuel_characteristic_keys_are_rejected(fuel_row_specs, fuel):
    with pytest.raises(ValueError, match="Неизвестный вид топлива"):
        services.upsert_characteristic("vsego", fuel, 2026, "ash", 1)
