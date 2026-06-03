# -*- coding: utf-8 -*-
"""Соответствие имён переменных шаблона ключам справочника формул (сводки нагрузок)."""

from __future__ import annotations

from typing import Any

# Имена с префиксом «_pd_» — сразу в контекст Jinja (без {% set %} в include).
PD_FORMULA_TEMPLATE_VAR_KEYS: dict[str, str] = {
    "_pd_coeff_res_oes_k_formula": "coeff_res_oes_k",
    "_pd_coeff_res_ees_k_formula": "coeff_res_ees_k",
    "_pd_oes_ues_calc_max_oes_mw_formula": "oes_ues_calc_max_oes_mw",
    "_pd_oes_ues_calc_combined_ees_mw_formula": "oes_ues_calc_combined_ees_mw",
    "_pd_oes_ees_russia_calc_max_via_oes_formula": "oes_ees_russia_calc_max_via_oes",
    "_pd_oes_ees_russia_calc_max_via_es_formula": "oes_ees_russia_calc_max_via_es",
    "_pd_oes_ees_russia_calc_max_formula": "oes_ees_russia_calc_max",
    "_pd_fo_calc_max_mw_formula": "fo_calc_max_mw",
    "_pd_fo_calc_combined_on_cz_mw_formula": "fo_calc_combined_on_cz_mw",
    "_pd_ez_calc_max_mw_formula": "ez_calc_max_mw",
    "_pd_sa_calc_max_mw_formula": "sa_calc_max_mw",
    "_pd_sa_verify_combined_ees_formula": "sa_verify_combined_ees",
    "_pd_coeff_k_ues_calc_max_oes": "coeff_k_ues_calc_max_oes",
    "_pd_coeff_k_ues_combined_ees": "coeff_k_ues_combined_ees",
    "_pd_coeff_k_ues_calc_combined_ees": "coeff_k_ues_calc_combined_ees",
    "_pd_coeff_k_calculated_max_ees_via_oes": "coeff_k_calculated_max_ees_via_oes",
    "_pd_coeff_k_calculated_max_ees_via_es": "coeff_k_calculated_max_ees_via_es",
    "_pd_coeff_k_formula_default_suffix": "coeff_k_formula_default_suffix",
    "_pd_coeff_f_gs10": "coeff_f_gs10",
    "_pd_coeff_f_gs10trim": "coeff_f_gs10trim",
    "_pd_coeff_f_gs5": "coeff_f_gs5",
    "_pd_coeff_f_sample": "coeff_f_sample",
}


def inject_pd_formula_template_variables(
    context: dict[str, Any],
    formula_texts: dict[str, str],
) -> None:
    for var_name, registry_key in PD_FORMULA_TEMPLATE_VAR_KEYS.items():
        context[var_name] = formula_texts.get(registry_key, "")
