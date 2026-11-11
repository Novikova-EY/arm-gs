from copy import deepcopy
from itertools import product

import pytest
from openpyxl import load_workbook

from app.common.perimeter_variant.constants import (
    CODE_WITH_NT, CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITH_GAES, CODE_WITHOUT_NT_WITHOUT_GAES,
)
from app.energy_consumption.pages import _summary_page_common as common
from app.energy_consumption.services import energy_consumption_summary_services as service
from app.energy_consumption.services.ec_summary_client_render_services import prepare_summary_rows_for_client
from app.energy_consumption.services.energy_consumption_summary_export_services import build_demand_summary_excel_stream


WITH_NT_MODELS = [
    ("EesRussiaEnergyConsumptionParameter", "ЭЭС России"),
    ("EnergySystemTypeEnergyConsumptionParameter", "ЕЭС России"),
    ("SynchronousAreaEnergyConsumptionParameter", "Первая синхронная зона"),
]
PARAMETERS = ["energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch",
              "energy_consumption_sipr_abs_growth_mln", "energy_consumption_yoy_growth_pct",
              "energy_consumption_sipr_yoy_growth_pct", "gaes_charge_consumption_mln_kvt_ch"]


def make_row(model, label, code, parameter="energy_consumption_mln_kvt_ch", unrestricted=True):
    return dict(demand_model_name=model, entity_label=label, parameter_key=parameter,
                parameter_label=parameter, perimeter_variant_code=code, entity_kind="group",
                year_values=["21,1", "22,2", "23,3", "24,4"],
                year_numeric_tooltips=["21,123", "22,234", "23,345", "24,456"],
                year_row_ids=[21, 22, 23, 24], pd_ec_skip_perimeter_variant_year_bounds=unrestricted)


@pytest.mark.parametrize("model,label", WITH_NT_MODELS)
@pytest.mark.parametrize("code", [CODE_WITH_NT, CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES])
@pytest.mark.parametrize("parameter", PARAMETERS)
@pytest.mark.parametrize("unrestricted", [False, True])
def test_with_nt_is_empty_before_2023_even_with_unrestricted_input(model, label, code, parameter, unrestricted):
    suffix = " с НТ без заряда ГАЭС" if code == CODE_WITH_NT_WITHOUT_GAES else " с НТ с зарядом ГАЭС"
    row = make_row(model, label + suffix, code, parameter, unrestricted)
    context = {"summary_rows": [row], "years": [2021, 2022, 2023, 2024]}
    service.mask_with_nt_summary_year_display(context)
    assert row["year_values"] == ["–", "–", "23,3", "24,4"]
    assert row["year_numeric_tooltips"] == ["", "", "23,345", "24,456"]
    assert row["year_row_ids"] == [None, None, 23, 24]
    assert row["perimeter_variant_from_year"] == 2023
    assert not row.get("pd_ec_skip_perimeter_variant_year_bounds")
    client_row = prepare_summary_rows_for_client([row])[0]
    assert client_row["perimeter_variant_from_year"] == 2023
    assert client_row["year_values"][:2] == ["–", "–"]
    assert client_row["year_numeric_tooltips"][:2] == ["", ""]


@pytest.mark.parametrize("model,label,code", [
    *((model, label, code) for (model, label), code in product(
        WITH_NT_MODELS, [CODE_WITHOUT_NT_WITH_GAES, CODE_WITHOUT_NT_WITHOUT_GAES])),
    ("UnionEnergySystemEnergyConsumptionParameter", "ОЭС Юга с НТ", CODE_WITH_NT_WITH_GAES),
    ("RussiaFederationEnergyConsumptionParameter", "Россия с НТ", CODE_WITH_NT),
    ("EnergySystemTypeEnergyConsumptionParameter", "ТИТЭС с НТ", CODE_WITH_NT),
    ("SynchronousAreaEnergyConsumptionParameter", "Вторая синхронная зона с НТ", CODE_WITH_NT),
    ("EesRussiaEnergyConsumptionParameter", "ЭЭС России", "o1_with_nt"),
])
def test_other_rows_are_unchanged(model, label, code):
    row = make_row(model, label, code)
    original = deepcopy(row)
    service.mask_with_nt_summary_year_display({"summary_rows": [row], "years": [2021, 2022, 2023, 2024]})
    assert row == original


def test_finalization_masks_after_growth_rounding_without_recomputing_values(monkeypatch):
    from app.energy_consumption.services import summary_formula_presentation, summary_row_note_services
    monkeypatch.setattr(common, "build_ec_formula_texts_map", lambda: {})
    monkeypatch.setattr(common, "inject_ec_formula_template_variables", lambda *args: None)
    monkeypatch.setattr(common, "apply_row_formula_text_overrides", lambda *args: None)
    monkeypatch.setattr(service, "ensure_first_sa_variant_formula_tooltips", lambda *args: None)
    monkeypatch.setattr(summary_formula_presentation, "attach_summary_formula_tooltips", lambda *args: None)
    monkeypatch.setattr(summary_row_note_services, "attach_summary_row_notes", lambda *args: None)
    row = make_row(*WITH_NT_MODELS[0], CODE_WITH_NT_WITH_GAES, "energy_consumption_yoy_growth_pct")
    result = common.finalize_ec_summary_page_context(
        {"summary_rows": [row], "years": [2021, 2022, 2023, 2024]}, growth_rounding_digits=3,
    )
    assert result["summary_rows"][0]["year_values"] == ["–", "–", "23,345", "24,456"]


@pytest.mark.parametrize("model,label", WITH_NT_MODELS)
@pytest.mark.parametrize("code", [CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES])
def test_excel_does_not_expose_hidden_values(model, label, code):
    row = make_row(model, label + " с НТ", code)
    context = {"summary_rows": [row], "years": [2021, 2022, 2023, 2024]}
    service.mask_with_nt_summary_year_display(context)
    workbook = load_workbook(build_demand_summary_excel_stream(**context, sheet_title="Summary"))
    assert [workbook.active.cell(2, column).value for column in range(3, 7)] == ["–", "–", 23.345, 24.456]


@pytest.mark.parametrize("code", [
    CODE_WITH_NT_WITH_GAES,
    CODE_WITH_NT_WITHOUT_GAES,
    *sorted(service._FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_CODES),
    *sorted(service._FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_CODES),
])
@pytest.mark.parametrize("unrestricted", [False, True])
def test_first_sync_area_display_bounds_do_not_change_formula_years(code, unrestricted):
    row = make_row(*WITH_NT_MODELS[2], code)
    service.mask_summary_rows_perimeter_variant_year_display(
        [row], [2021, 2022, 2023, 2024],
        unrestricted_perimeter_variant_input=unrestricted,
    )
    assert row["year_values"][:2] == ["\u2013", "\u2013"]
    assert row["year_numeric_tooltips"][:2] == ["", ""]
    assert row["year_row_ids"][:2] == [None, None]
    assert row["year_values"][2:] == ["23,3", "24,4"]
    assert row["perimeter_variant_from_year"] == 2023
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2022)
