# -*- coding: utf-8 -*-
"""Соответствие имён переменных шаблона ключам справочника формул (сводки нагрузок)."""

from __future__ import annotations

from typing import Any

# Имена с префиксом «_pd_» — сразу в контекст Jinja (без {% set %} в include).
PD_FORMULA_TEMPLATE_VAR_KEYS: dict[str, str] = {
    "_pd_coeff_res_oes_k_formula": "coeff_res_oes_k",
    "_pd_coeff_res_ees_k_formula": "coeff_res_ees_k",
    "_pd_oes_ues_calc_max_oes_mw_formula": "oes_ues_calc_max_oes_mw_without_nt",
    "_pd_oes_ues_calc_combined_ees_mw_formula": "oes_ues_calc_combined_ees_mw_without_nt",
    "_pd_oes_ees_russia_calc_max_via_oes_formula": "oes_ees_russia_calc_max_via_oes_without_nt",
    "_pd_oes_ees_russia_calc_max_via_es_formula": "oes_ees_russia_calc_max_via_es_without_nt",
    "_pd_oes_ees_russia_calc_max_formula": "oes_ees_russia_calc_max_without_nt",
    "_pd_ees_russia_verify_calc_max_formula": "ees_russia_verify_calc_max_without_nt",
    "_pd_ees_russia_verify_calc_max_via_oes_formula": "ees_russia_verify_calc_max_via_oes_without_nt",
    "_pd_ees_russia_verify_calc_max_via_es_formula": "ees_russia_verify_calc_max_via_es_without_nt",
    "_pd_oes_ees_calc_max_power_consumption_formula": "oes_ees_calc_max_power_consumption_without_nt",
    "_pd_fo_calc_max_mw_formula": "fo_calc_max_mw",
    "_pd_fo_calc_combined_on_cz_mw_formula": "fo_calc_combined_on_cz_mw",
    "_pd_ez_calc_max_mw_formula": "ez_calc_max_mw",
    "_pd_sa_first_calc_max_power_mw_formula": "sa_first_calc_max_power_mw_without_nt",
    "_pd_sa_first_verify_max_power_formula": "sa_first_verify_max_power_without_nt",
    "_pd_sa_first_calc_max_sa_mw_formula": "sa_first_calc_max_sa_mw_without_nt",
    "_pd_sa_first_verify_combined_ees_formula": "sa_first_verify_combined_ees_without_nt",
    "_pd_sa_second_calc_max_power_mw_formula": "sa_second_calc_max_power_mw",
    "_pd_sa_second_verify_max_power_formula": "sa_second_verify_max_power",
    "_pd_sa_second_calc_max_sa_mw_formula": "sa_second_calc_max_sa_mw",
    "_pd_sa_second_verify_combined_ees_formula": "sa_second_verify_combined_ees",
    "_pd_sa_kaliningrad_calc_max_power_mw_formula": "sa_kaliningrad_calc_max_power_mw",
    "_pd_sa_kaliningrad_verify_max_power_formula": "sa_kaliningrad_verify_max_power",
    "_pd_sa_kaliningrad_calc_max_sa_mw_formula": "sa_kaliningrad_calc_max_sa_mw",
    "_pd_sa_kaliningrad_verify_combined_ees_formula": "sa_kaliningrad_verify_combined_ees",
    "_pd_oes_verify_calc_max_mw_formula": "oes_verify_calc_max_mw_without_nt",
    "_pd_oes_verify_combined_ees_mw_formula": "oes_verify_combined_ees_mw_without_nt",
    "_pd_chukotka_rd_calc_max_mw_formula": "chukotka_rd_calc_max_mw",
    "_pd_chukotka_rd_territorial_calc_max_mw_formula": "chukotka_rd_territorial_calc_max_mw",
    "_pd_oes_peak_max_power_usage_hours_formula": "oes_peak_max_power_usage_hours",
    "_pd_coeff_k_ues_calc_max_oes": "coeff_k_ues_calc_max_oes_without_nt",
    "_pd_coeff_k_ues_combined_ees": "coeff_k_ues_combined_ees_without_nt",
    "_pd_coeff_k_ues_calc_combined_ees": "coeff_k_ues_calc_combined_ees_without_nt",
    "_pd_coeff_k_calculated_max_ees_via_oes": "coeff_k_calculated_max_ees_via_oes_without_nt",
    "_pd_coeff_k_calculated_max_ees_via_es": "coeff_k_calculated_max_ees_via_es_without_nt",
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
