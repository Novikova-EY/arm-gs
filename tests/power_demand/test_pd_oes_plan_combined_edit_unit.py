"""Редактирование совмещённого потребления по ОЭС/ЕЭС в плановых годах."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from jinja2 import Environment

from app.power_demand.services import demand_parameter_services as dps


@pytest.mark.parametrize("model_name,parameter_key", [
    ("UnionEnergySystemDemandParameter", "combined_on_ees"),
    ("RegionalEnergySystemDemandParameter", "combined_on_oes"),
    ("RegionalEnergySystemDemandParameter", "combined_on_ees"),
    ("RegionalDistrictDemandParameter", "combined_on_oes"),
    ("RegionalDistrictDemandParameter", "combined_on_ees"),
])
def test_plan_year_accepts_oes_combined_values_for_existing_and_new_slices(
    monkeypatch, model_name, parameter_key
):
    monkeypatch.setattr(dps, "get_year_feature_dict", lambda: {2025: "План", 2042: "План"})
    for year in (2025, 2042):
        dps._assert_plan_year_only_max_power_editable(
            year, False, parameter_key, demand_model_name=model_name
        )


@pytest.mark.parametrize("model_name,parameter_key", [
    ("RegionalDistrictDemandParameter", "combined_on_es"),
    ("RegionalDistrictDemandParameter", "avg_temp"),
    ("UnionEnergySystemDemandParameter", "combined_on_oes"),
])
def test_plan_year_other_fields_remain_restricted(monkeypatch, model_name, parameter_key):
    monkeypatch.setattr(dps, "get_year_feature_dict", lambda: {2025: "План"})
    with pytest.raises(ValueError, match="Для годов с признаком"):
        dps._assert_plan_year_only_max_power_editable(
            2025, False, parameter_key, demand_model_name=model_name
        )


@pytest.mark.parametrize("parameter_key,row_exists", [
    ("combined_on_oes", False),
    ("combined_on_ees", True),
])
def test_subject_plan_combined_cell_save_creates_or_updates_row(
    monkeypatch, parameter_key, row_exists
):
    monkeypatch.setattr(dps, "get_year_feature_dict", lambda: {2025: "План"})
    monkeypatch.setattr(dps, "all_database_version_ids_for_refdata", lambda: [1])
    monkeypatch.setattr(dps, "get_current_version", lambda: 1)
    monkeypatch.setattr(dps, "_username", lambda: "editor")
    monkeypatch.setattr(dps, "_validate_summary_parent_binding", lambda *args: None)
    monkeypatch.setattr(dps, "_resolve_summary_parent_id_for_version", lambda *_: 42)
    row = SimpleNamespace(
        id=3, database_version_id=1, id_regional_district=42,
        is_historical_maximum=False, year_number=2025, perimeter_variant_code=None,
        combined_on_oes=None, combined_on_ees=None,
    )
    model = SimpleNamespace(id_regional_district=42, query=SimpleNamespace(get=lambda _: row))
    monkeypatch.setattr(dps, "_summary_demand_model_class", lambda _: model)
    monkeypatch.setattr(
        dps, "find_demand_row_for_summary_slice_resolving_pvc",
        lambda *args, **kwargs: row if row_exists else None,
    )
    create = MagicMock(return_value=row)
    monkeypatch.setattr(dps, "create_demand_row_for_summary_slice", create)
    session = MagicMock()
    monkeypatch.setattr(dps.db, "session", session)
    monkeypatch.setattr(dps, "_maybe_log_pd_summary_cell", lambda *args, **kwargs: None)

    result = dps.save_demand_summary_cell(
        "RegionalDistrictDemandParameter", parameter_key, "123,4",
        rounding_digits=1, row_id=3 if row_exists else None,
        slice_key="2025", parent_fk_column="id_regional_district", parent_id=42,
        summary_log_scope="oes",
    )

    assert result == "123,4"
    assert str(getattr(row, parameter_key)) == "123.4"
    assert create.call_count == (0 if row_exists else 1)
    session.commit.assert_called_once()


@pytest.mark.parametrize("model_name,parameter_key,scope,variant,hidden", [
    ("RegionalEnergySystemDemandParameter", "combined_on_oes", "oes", "max", False),
    ("RegionalDistrictDemandParameter", "combined_on_oes", "oes", "max", False),
    ("RegionalDistrictDemandParameter", "combined_on_ees", "oes", "max", False),
    ("UnionEnergySystemDemandParameter", "combined_on_ees", "oes", "max", False),
    ("RegionalDistrictDemandParameter", "combined_on_es", "oes", "max", True),
    ("RegionalDistrictDemandParameter", "combined_on_oes", "fo", "max", True),
    ("RegionalDistrictDemandParameter", "combined_on_oes", "oes", "coeff", True),
])
def test_plan_year_cells_are_visible_only_for_requested_summary_rows(
    model_name, parameter_key, scope, variant, hidden
):
    template_path = Path(__file__).resolve().parents[2] / "app/templates/perimeter_variants/power_demand_summary.html"
    source = template_path.read_text(encoding="utf-8")
    # Используем ту же логику видимости, что и таблица, без рендера всей страницы.
    visibility = source.split("{% set _plan_col = year_is_plan.get(_yr, false) %}", 1)[1].split(
        "{% set _yr_tt =", 1
    )[0]
    template = Environment().from_string(
        "{% set _plan_col = year_is_plan.get(_yr, false) %}" + visibility + "{{ _plan_hide }}"
    )
    result = template.render(
        _yr=2025,
        year_is_plan={2025: True},
        coeff_base_year=2024,
        row={"demand_model_name": model_name, "parameter_key": parameter_key},
        summary_route_variant=variant,
        active_summary=scope,
        _cz_fo_tot=False,
    )
    assert result.strip().endswith(str(hidden))
