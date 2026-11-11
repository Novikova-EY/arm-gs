from app.energy_consumption.services.energy_consumption_summary_formula_registry import get_formula_def


_PARAMETER_FORMULAS = {
    "energy_consumption_yoy_growth_pct": "yoy_growth",
    "energy_consumption_sipr_yoy_growth_pct": "sipr_yoy_growth",
    "energy_consumption_sipr_abs_growth_mln": "sipr_abs_growth",
}


def attach_summary_formula_tooltips(context):
    texts = context.get("ec_formula_texts") or {}
    for row in context.get("summary_rows") or []:
        parameter = row.get("parameter_key")
        key = _PARAMETER_FORMULAS.get(parameter) or row.get("pd_ec_formula_text_key")
        if parameter == "gaes_charge_consumption_mln_kvt_ch" and not row.get("gaes_station_id"):
            key = "gaes_charge_total"
        tip = ""
        if not key:
            tip = row.get("pd_ec_summary_row_formula_tooltip") or row.get("pd_ec_verification_formula_tooltip") or row.get("pd_parameter_formula_tooltip") or ""
        if not tip and not key:
            model = row.get("demand_model_name")
            if (model in ("FederalDistrictEnergyConsumptionParameter", "EnergyZoneEnergyConsumptionParameter")
                    and row.get("entity_kind") == "group"
                    and parameter in ("energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch")):
                prefix = "fo" if model == "FederalDistrictEnergyConsumptionParameter" else "ez"
                key = prefix + ("_sipr" if parameter == "energy_consumption_sipr_mln_kvt_ch" else "_mln")
            kind = row.get("gaes_without_charge_formula_kind")
            if kind:
                key = {"fo": "fo_gaes_adj_sum_res", "rd": "rd_gaes_adj", "oes": "gaes_adj_fd_oes"}.get(kind, "gaes_adj_" + str(kind))
                if get_formula_def(key) is None:
                    key = "gaes_adj_generic"
        if key:
            definition = get_formula_def(key)
            tip = texts.get(key) or (definition.default_text if definition else "")
        manual = row.get("pd_ec_cz_o1_with_nt_manual_row") or row.get("pd_ec_oes_ees_russia_manual_source_row")
        if manual and parameter not in _PARAMETER_FORMULAS and not row.get("pd_ec_formula_derived_row"):
            tip = ""
        if tip:
            row["pd_parameter_formula_tooltip"] = str(tip)
