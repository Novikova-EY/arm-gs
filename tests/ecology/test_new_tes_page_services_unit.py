# -*- coding: utf-8 -*-
"""Юнит-тесты расчёта по новым ТЭС (М = В × У)."""

from decimal import Decimal
from pathlib import Path

from app.ecology.services.new_tes_calc_services import (
    pg_mass_thousand_tonnes,
    zv_mass_thousand_tonnes,
    zv_mass_tonnes,
)
from app.ecology.services.new_tes_constants import (
    DEFAULT_NORMS,
    NEW_TES_CALC_SHEETS,
    default_norm,
    get_calc_sheet,
    parse_norm_field,
)
from app.ecology.services.new_tes_page_services import compute_new_tes_year_bundle
from app.ecology.services.operating_tes_fuel_input_services import (
    empty_fuel_bucket,
    equipment_group_operating_clause,
)


def test_ecology_hub_has_enabled_new_tes_calc_tile():
    text = Path("app/templates/ecology/ecology_start.html").read_text(encoding="utf-8")
    assert "ecology_bp.new_tes_table" in text
    assert "Расчет по новым ТЭС" in text
    assert "Расчет по действующим ТЭС" in text
    assert "hub_tile_disabled" not in text


def test_new_tes_sheets_follow_excel_outputs():
    slugs = [item["slug"] for item in NEW_TES_CALC_SHEETS]
    assert slugs == [
        "toplivo",
        "spravochnik",
        "zola",
        "sera",
        "azot",
        "co",
        "pg",
        "obemy",
        "udel-e",
        "udel-fuel",
        "udel-ee",
    ]
    assert get_calc_sheet("spravochnik")["sheet_name"] == "Нормативы"
    assert get_calc_sheet("obemy")["layout"] == "volumes"


def test_excel_mass_formulas():
    diesel_b = Decimal("48.33198")
    so2 = zv_mass_tonnes(diesel_b, Decimal("8.8"))
    assert so2 == Decimal("425.321424")
    assert zv_mass_thousand_tonnes(diesel_b, Decimal("8.8")) == so2 / Decimal("1000")
    gas_b = Decimal("670.206479938")
    nox_t = zv_mass_tonnes(gas_b, Decimal("1.26"))
    assert nox_t == Decimal("844.46016472188")
    pg = pg_mass_thousand_tonnes(gas_b, Decimal("1.59"))
    assert pg == Decimal("1065.62830310142")


def test_default_norms_from_excel_sheet():
    assert default_norm("gas_natural", "le100", "nox") == 1.26
    assert default_norm("gas_natural", "le100", "pg") == 1.59
    assert default_norm("mazut", "le100", "ash") == 1.76
    assert default_norm("mazut", "gt100", "ash") == 0.59
    assert default_norm("donetsk", "le100", "so2") == 17.6
    assert "gas_natural" in DEFAULT_NORMS
    parsed = parse_norm_field("ash_gt100")
    assert parsed == ("ash", "gt100")


def test_new_tes_operating_filter_excludes_d_eq_1():
    clause = equipment_group_operating_clause(operating=False)
    compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "IS NULL" in compiled.upper() or "is null" in compiled.lower()
    operating = str(
        equipment_group_operating_clause(operating=True).compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert " = 1" in operating or "=1" in operating.replace(" ", "")


def test_compute_new_tes_bundle_applies_le100_norms():
    le = empty_fuel_bucket()
    le["gaz_prir"] = Decimal("100")
    le["gaz"] = Decimal("100")
    le["b"] = Decimal("100")
    bundle = compute_new_tes_year_bundle(
        "vsego",
        2025,
        {"le100": le, "gt100": empty_fuel_bucket()},
        {},
    )
    gas = bundle["by_key"]["gas_natural"]
    assert gas["b"] == Decimal("100")
    assert gas["nox"] == Decimal("0.126")
    assert gas["pg"] == Decimal("159")
    assert bundle["volumes"]["nox"] == Decimal("0.126")
    assert bundle["volumes"]["co2"] == Decimal("159")


def test_new_tes_formula_labels_point_to_new_tes_urls():
    from app.ecology.services.operating_tes_formula_registry import (
        NEW_TES_PAGE_LABELS,
        get_formula_def,
    )

    item = get_formula_def("nt_zv_thous")
    assert item is not None
    labels = item.page_label_lines()
    assert any("/ecology/new_tes/" in line for line in labels)
    assert NEW_TES_PAGE_LABELS["obemy"].endswith("/ecology/new_tes/vsego/obemy/)")
    assert "М, тыс. т" in item.default_text
