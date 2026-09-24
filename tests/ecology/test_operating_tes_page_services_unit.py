# -*- coding: utf-8 -*-
"""Юнит-тесты каталога вкладок расчёта по действующим ТЭС."""

from app.ecology.services.operating_tes_constants import (
    CALC_SHEETS,
    DEFAULT_SHEET_SLUG,
    DEFAULT_TERRITORY_SLUG,
    FUEL_ROWS,
    default_coefficient,
    get_calc_sheet,
    get_territory,
)
from decimal import Decimal

from app.ecology.services.operating_tes_page_services import (
    compute_year_bundle,
    group_territories,
    resolve_selected_year,
    resolve_view_year,
)


def test_default_slugs_exist():
    assert get_territory(DEFAULT_TERRITORY_SLUG) is not None
    assert get_calc_sheet(DEFAULT_SHEET_SLUG) is not None
    assert get_calc_sheet("toplivo")["sheet_name"] == "Данные по модулю Топливо"
    assert get_calc_sheet("toplivo")["page_title"] == "Топливные показатели (модуль Топливо)"
    assert get_calc_sheet("toplivo")["layout"] == "fuel"
    assert get_calc_sheet("zola")["layout"] == "emission"
    assert get_calc_sheet("khar-topl")["layout"] == "chars"
    assert get_calc_sheet("khar-topl")["sheet_name"] == "Характеристики"
    assert get_calc_sheet("khar-topl")["page_title"].startswith("Характеристика топлив")
    assert get_calc_sheet("spravochnik")["layout"] == "spravochnik"
    assert get_calc_sheet("spravochnik")["sheet_name"] == "Справочник"
    assert get_calc_sheet("koeff")["sheet_name"] == "Коэффициенты"


def test_excel_sheets_are_tabs():
    slugs = [item["slug"] for item in CALC_SHEETS]
    assert slugs == [
        "toplivo",
        "spravochnik",
        "khar-topl",
        "koeff",
        "zola",
        "sera",
        "azot",
        "co",
        "pg",
        "pg-tj",
        "obemy",
        "udel-e",
        "udel-fuel",
        "udel-ee",
    ]


def test_territory_tabs_follow_excel_column_order():
    from app.ecology.services.operating_tes_constants import TERRITORIES

    sheets = group_territories()[0]["sheets"]
    slugs = [item["slug"] for item in sheets]
    assert slugs == [item["slug"] for item in TERRITORIES]
    assert slugs[0:3] == ["vsego", "minen", "prompred"]
    assert slugs[-1] == "norilsk"


def test_fuel_tree_has_coal_children():
    coal = next(item for item in FUEL_ROWS if item["key"] == "coal")
    assert "kuznetsk" in coal["children"]
    kuz = next(item for item in FUEL_ROWS if item["key"] == "kuznetsk")
    assert kuz["is_header"] is True
    assert "kuzn_gd" in kuz["children"]


def test_default_coefficient_falls_back_to_2024():
    assert default_coefficient(2030, "vsego", "ash_eta") == default_coefficient(
        2024, "vsego", "ash_eta"
    )
    assert default_coefficient(2021, "vsego", "co_k") == 0.0
    assert default_coefficient(2021, "centr", "co_k") == 1.0


def test_top_input_amounts_convert_fuel_module_units():
    from app.ecology.services.operating_tes_constants import TOP_INPUT_ROWS
    from app.ecology.services.operating_tes_fuel_input_services import (
        bucket_top_input_amount,
    )

    bucket = {"e": Decimal("1234000"), "q": Decimal("5600"), "b": Decimal("89000")}
    assert bucket_top_input_amount(bucket, "ee_generation") == Decimal("1234")
    assert bucket_top_input_amount(bucket, "heat_output") == Decimal("5600")
    labels = [item["label"] for item in TOP_INPUT_ROWS]
    units = [item["unit"] for item in TOP_INPUT_ROWS]
    assert labels == ["Выработка электроэнергии", "Отпуск тепла"]
    assert units == ["млрд.кВтч", "тыс.Гкал"]


def test_char_columns_follow_excel_khar_topl():
    from app.ecology.services.operating_tes_constants import CHAR_COLUMNS

    assert [key for key, _label in CHAR_COLUMNS] == [
        "ash",
        "ash_share",
        "q_mech",
        "sulfur",
        "sulfur_share",
        "qh_kj",
        "qh_kcal",
        "bj",
        "k_co2",
        "r_chem",
        "q_chem",
        "tut_per_t",
        "tj_per_kt",
        "t_co2_per_tj",
        "k_natural",
    ]
    assert dict(CHAR_COLUMNS)["k_co2"] == "КСО2"


def test_char_header_groups_merge_excel_cells():
    from app.ecology.services.operating_tes_constants import CHAR_HEADER_GROUPS

    by_title = {item["title"]: item["keys"] for item in CHAR_HEADER_GROUPS}
    assert by_title["Низшая теплота сгорания"] == ("qh_kj", "qh_kcal")
    assert by_title["Коэффициенты для расчета как в НД о Кадастре ПГ"] == (
        "tut_per_t",
        "tj_per_kt",
        "t_co2_per_tj",
    )
    k_group = next(item for item in CHAR_HEADER_GROUPS if item["keys"] == ("k_natural",))
    assert k_group.get("rowspan") == 2


def test_spravochnik_columns_and_sources_follow_excel():
    from app.ecology.services.operating_tes_constants import (
        CHAR_SOURCE_COLORS,
        CHAR_SOURCE_OPTIONS,
        DEFAULT_CHAR_SOURCES,
        SPR_COLUMNS,
        SPR_HEADER_GROUPS,
        fuel_label_bg,
    )

    assert [key for key, _label in SPR_COLUMNS] == [
        "ash",
        "ash_share",
        "q_mech",
        "sulfur",
        "sulfur_share",
        "qh_kj",
        "qh_kcal",
        "bj",
        "k_co2",
        "r_chem",
        "q_chem",
    ]
    spr_keys = tuple(key for group in SPR_HEADER_GROUPS for key in group["keys"])
    assert spr_keys == tuple(key for key, _label in SPR_COLUMNS)
    keys = [item["key"] for item in CHAR_SOURCE_OPTIONS]
    assert keys == ["thermal", "method", "industry", "table21", "rosstat"]
    assert CHAR_SOURCE_COLORS["thermal"] == "#b7e8e8"
    assert CHAR_SOURCE_COLORS["method"] == "#d58d53"
    assert CHAR_SOURCE_COLORS["rosstat"] == "#44d89b"
    assert DEFAULT_CHAR_SOURCES["kuzn_t"] == "thermal"
    assert DEFAULT_CHAR_SOURCES["kuzn_other"] == "method"
    assert DEFAULT_CHAR_SOURCES["zyryan"] == "industry"
    assert DEFAULT_CHAR_SOURCES["other_solid"] == "rosstat"
    assert DEFAULT_CHAR_SOURCES["gas_natural"] == "rosstat"
    assert fuel_label_bg("kuzn_t", "thermal") == "#b7e8e8"
    assert fuel_label_bg("kuzn_other", "method") == "#d58d53"
    assert fuel_label_bg("donetsk", None) == "#bfbfbf"


def test_resolve_chars_fills_spravochnik_note_and_source():
    from app.ecology.services.operating_tes_page_services import resolve_chars

    chars = resolve_chars("kuzn_t", 2024, {})
    assert chars["source_key"] == "thermal"
    assert chars["note"] == "Стр. 129 из котельного справочника"

    chars = resolve_chars(
        "kuzn_t",
        2024,
        {("kuzn_t", 2024): {"source_key": "method", "note": ""}},
    )
    assert chars["source_key"] == "method"
    assert chars["note"] == ""


def test_collapse_indent_counts_parents():
    from app.ecology.services.operating_tes_fuel_input_services import _collapse_indent

    collapse = {"gaz_prir": "gaz", "kuzngd": "kuzn", "kuzn": "ugol"}
    assert _collapse_indent("gaz", collapse) == 0
    assert _collapse_indent("gaz_prir", collapse) == 1
    assert _collapse_indent("kuzngd", collapse) == 2


def test_fuel_param_fields_match_refdata_nazvl():
    from app.ecology.services.operating_tes_constants import FUEL_PARAM_FIELDS

    assert FUEL_PARAM_FIELDS["gas_natural"] == "gaz_prir"
    assert FUEL_PARAM_FIELDS["gas_associated"] == "gazpp"
    assert FUEL_PARAM_FIELDS["blast_furnace_gas"] == "domen_g"
    assert FUEL_PARAM_FIELDS["coke_oven_gas"] == "koks_g"
    assert FUEL_PARAM_FIELDS["npz_gas"] == "prochgaz"
    assert FUEL_PARAM_FIELDS["mazut"] == "maztop"
    assert FUEL_PARAM_FIELDS["diesel"] == "disel"
    assert FUEL_PARAM_FIELDS["kuzn_gd"] == "kuzngd"
    assert FUEL_PARAM_FIELDS["inta"] == "intin"


def test_gas_subtypes_sum_to_header():
    bundle = compute_year_bundle(
        "vsego",
        2024,
        {"gaz_prir": Decimal("10"), "gazpp": Decimal("2"), "gaz": Decimal("99")},
        {},
        {},
    )
    assert bundle["by_key"]["gas_natural"]["b"] == Decimal("10")
    assert bundle["by_key"]["gas_associated"]["b"] == Decimal("2")
    assert bundle["by_key"]["gas"]["b"] == Decimal("12")


def test_basin_header_without_subtypes_enters_volumes():
    bundle = compute_year_bundle(
        "vsego",
        2024,
        {"kuzn": Decimal("100"), "don": Decimal("50")},
        {},
        {},
    )
    assert bundle["by_key"]["kuznetsk"]["b"] == Decimal("100")
    assert bundle["by_key"]["donetsk"]["b"] == Decimal("50")
    assert bundle["by_key"]["coal"]["b"] == Decimal("150")
    assert bundle["volumes"]["ash"] is not None
    assert bundle["volumes"]["ash"] > 0
    assert bundle["volumes"]["co2"] is not None


def test_resolve_view_year_only_inside_range():
    years = [2021, 2022, 2023]
    assert resolve_view_year(2022, years) == 2022
    assert resolve_view_year("2023", years) == 2023
    assert resolve_view_year(2020, years) is None
    assert resolve_view_year("", years) is None
    assert resolve_view_year(None, years) is None
    assert resolve_view_year("abc", years) is None


def test_resolve_selected_year_defaults_to_first():
    years = [2021, 2022, 2023]
    assert resolve_selected_year(2023, years) == 2023
    assert resolve_selected_year(None, years) == 2021
    assert resolve_selected_year(1999, years) == 2021
    assert resolve_selected_year(None, []) is None


def test_emission_sheet_view_follows_excel():
    from app.ecology.services.operating_tes_constants import EMISSION_SHEET_VIEW

    assert EMISSION_SHEET_VIEW["zola"]["kind"] == "pair"
    assert EMISSION_SHEET_VIEW["zola"]["left_metric"] == "bn"
    assert EMISSION_SHEET_VIEW["zola"]["right_metric"] == "ash_motkh"
    assert EMISSION_SHEET_VIEW["sera"]["right_metric"] == "so2_motkh"
    assert EMISSION_SHEET_VIEW["co"]["right_metric"] == "co_motkh"
    assert EMISSION_SHEET_VIEW["azot"]["kind"] == "single"
    assert EMISSION_SHEET_VIEW["azot"]["metric"] == "nox_raw"
    assert EMISSION_SHEET_VIEW["pg"]["metric"] == "pg_motkh"
    assert EMISSION_SHEET_VIEW["pg-tj"]["left_metric"] == "energy_tj"
    assert EMISSION_SHEET_VIEW["pg-tj"]["right_metric"] == "pg_tj_motkh"
    assert get_calc_sheet("pg")["page_title"].startswith("Выбросы ПАРНИКОВЫХ ГАЗОВ")


def test_motkh_kept_before_capture():
    bundle = compute_year_bundle(
        "vsego",
        2024,
        {"kuzn": Decimal("100")},
        {},
        {},
    )
    row = bundle["by_key"]["kuznetsk"]
    eta = Decimal(str(default_coefficient(2024, "vsego", "ash_eta")))
    nox_n = Decimal(str(default_coefficient(2024, "vsego", "nox_n")))
    assert row["ash_motkh"] is not None
    assert row["ash"] is not None
    assert eta > 0
    assert abs(row["ash"] - row["ash_motkh"] * (Decimal("1") - eta)) < Decimal("1e-8")
    assert row["nox_raw"] is not None
    assert row["nox"] == row["nox_raw"] * (Decimal("1") - nox_n)
    assert bundle["volumes"]["ash"] == row["ash"]


def test_operating_tes_formula_registry_covers_excel_sheets():
    from app.ecology.services.operating_tes_formula_registry import (
        SHEET_FORMULA_KEYS,
        get_formula_def,
    )
    from app.ecology.services.formula_text.operating_tes_formula_text_services import (
        formula_text_for_sheet,
    )

    for slug in ("zola", "sera", "azot", "co", "pg", "pg-tj", "obemy"):
        key = SHEET_FORMULA_KEYS[slug]
        assert get_formula_def(key) is not None
        text = formula_text_for_sheet(slug)
        assert text
    assert "Мотх=0,01*ВН" in formula_text_for_sheet("zola")
    assert formula_text_for_sheet("toplivo") == ""


def test_pg_difference_formulas_are_on_analysis_pages():
    from app.ecology.services.operating_tes_formula_registry import (
        PAGE_ANALYSIS_PG_BEZ_KOT,
        PAGE_ANALYSIS_PG_VSE,
        PAGE_LABELS,
        get_formula_def,
    )

    expected = {
        "d_mazut": ("MAZUT_6tp", "MAZUT_ek"),
        "d_gaz": ("GAZ_ESTEST", "GAZ_ek"),
        "d_tv": ("TvTopl_6tp", "TvTopl_ek"),
        "K_gaz_ek": ("CO2_gaz", "GAZ_ek"),
        "K_mazut_ek": ("CO2_mazut", "MAZUT_ek"),
        "K_ugol_ek": ("CO2_ugol", "TvTopl_ek"),
        "CO2": ("CO2_gaz", "CO2_mazut", "CO2_ugol"),
        "UD_CO2_ek": ("CO2", "GAZ_ek", "MAZUT_ek", "TvTopl_ek"),
        "UD_CO2_ener": ("CO2", "W_en", "Teplo", "859,8"),
    }
    pages = frozenset({PAGE_ANALYSIS_PG_BEZ_KOT, PAGE_ANALYSIS_PG_VSE})
    for key, parts in expected.items():
        item = get_formula_def(key)
        assert item is not None
        assert item.pages == pages
        for part in parts:
            assert part in item.default_text
        labels = item.page_label_lines()
        assert PAGE_LABELS[PAGE_ANALYSIS_PG_BEZ_KOT] in labels
        assert PAGE_LABELS[PAGE_ANALYSIS_PG_VSE] in labels
    assert "Выброшено ПГ всего" in get_formula_def("CO2").default_text
    assert "/ecology/analysis/pg-bez-kot/" in PAGE_LABELS[PAGE_ANALYSIS_PG_BEZ_KOT]
    assert "/ecology/analysis/pg-vse/" in PAGE_LABELS[PAGE_ANALYSIS_PG_VSE]


def test_gaseous_and_liquid_formula_is_on_gis_tek_pollutants_page():
    from app.ecology.services.operating_tes_formula_registry import (
        PAGE_ANALYSIS_ZV_BEZ_KOT,
        PAGE_ANALYSIS_ZV_VSE,
        PAGE_GIS_TEK_ZV,
        PAGE_LABELS,
        get_formula_def,
    )

    item = get_formula_def("gaseous_and_liquid")
    assert item is not None
    assert PAGE_GIS_TEK_ZV in item.pages
    assert PAGE_ANALYSIS_ZV_VSE in item.pages
    assert PAGE_ANALYSIS_ZV_BEZ_KOT in item.pages
    assert item.cell_name == "Газообразные и жидкие вещества, всего"
    for part in (
        "диоксид серы",
        "оксид углерода [CO]",
        "оксиды азота [в пересчете на NO2]",
        "углеводороды [без летучих органических соединений]",
        "летучие органические соединения [ЛОС]",
        "прочие газообразные и жидкие",
    ):
        assert part in item.default_text
    assert "/ecology/gis_tek/pollutants/" in PAGE_LABELS[PAGE_GIS_TEK_ZV]
    assert PAGE_LABELS[PAGE_GIS_TEK_ZV] in item.page_label_lines()
    assert "/ecology/analysis/zv-vse/" in PAGE_LABELS[PAGE_ANALYSIS_ZV_VSE]
    assert PAGE_LABELS[PAGE_ANALYSIS_ZV_VSE] in item.page_label_lines()

    total_item = get_formula_def("zv_total")
    assert total_item is not None
    assert PAGE_GIS_TEK_ZV in total_item.pages
    assert PAGE_ANALYSIS_ZV_VSE in total_item.pages
    assert PAGE_ANALYSIS_ZV_BEZ_KOT in total_item.pages
    assert total_item.cell_name == "всего"
    assert "Твердые вещества" in total_item.default_text
    assert "Газообразные и жидкие вещества (всего)" in total_item.default_text

    energy_item = get_formula_def("zv_brought_energy")
    assert energy_item is not None
    assert PAGE_ANALYSIS_ZV_VSE in energy_item.pages
    assert "859,8" in energy_item.default_text
    ee_item = get_formula_def("zv_normir_na_ee")
    assert ee_item is not None
    assert "W_en" in ee_item.default_text
    fuel_item = get_formula_def("zv_udel_nox")
    assert "GAZ_6tp" in fuel_item.default_text
    assert "MAZUT_6tp" in fuel_item.default_text

