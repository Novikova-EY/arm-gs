# -*- coding: utf-8 -*-
"""Соответствие имён переменных шаблона ключам справочника формул."""

from __future__ import annotations

from typing import Any

# Имена с префиксом «_pd_ec_» — сразу в контекст Jinja (без {% set %} в include).
EC_FORMULA_TEMPLATE_VAR_KEYS: dict[str, str] = {
    "_pd_ec_yoy_formula": "yoy_growth",
    "_pd_ec_sipr_yoy_formula": "sipr_yoy_growth",
    "_pd_ec_sipr_abs_formula": "sipr_abs_growth",
    "_pd_ec_verify_for_ues_tooltip": "verify_for_ues",
    "_pd_ec_verify_for_fo_tooltip": "verify_for_fo",
    "_pd_ec_verify_for_res_tooltip": "verify_for_res",
    "_pd_ec_verify_for_tites_res_eu_tooltip": "verify_for_tites_res_eu",
    "_pd_ec_verify_for_tites_aggregate_tooltip": "verify_for_tites_aggregate",
    "_pd_ec_verify_for_ez_tooltip": "ez_res_sum_verification",
    "_pd_ec_verify_ees_with_nt_tooltip": "verify_ees_with_nt",
    "_pd_ec_verify_ees_without_nt_tooltip": "verify_ees_without_nt",
    "_pd_ec_verify_south_with_nt_tooltip": "verify_south_with_nt",
    "_pd_ec_verify_south_without_nt_tooltip": "verify_south_without_nt",
    "_pd_ec_ez_mln_formula": "ez_mln",
    "_pd_ec_ez_sipr_formula": "ez_sipr",
    "_pd_ec_fo_mln_formula": "fo_mln",
    "_pd_ec_fo_sipr_formula": "fo_sipr",
    "_pd_ec_fo_gaes_adj_sum_res_formula": "fo_gaes_adj_sum_res",
    "_pd_ec_rd_gaes_adj_formula": "rd_gaes_adj",
    "_pd_ec_gaes_adj_fd_oes_formula": "gaes_adj_fd_oes",
    "_pd_ec_gaes_adj_ez_formula": "gaes_adj_ez",
    "_pd_ec_gaes_adj_ees_russia_ez_formula": "gaes_adj_ees_russia_ez",
    "_pd_ec_gaes_adj_ees_russia_with_nt_formula": "gaes_adj_ees_russia_with_nt",
    "_pd_ec_gaes_adj_ees_russia_without_nt_formula": "gaes_adj_ees_russia_without_nt",
    "_pd_ec_gaes_adj_sa_formula": "gaes_adj_sa",
    "_pd_ec_gaes_adj_generic_formula": "gaes_adj_generic",
    "_pd_ec_gaes_adj_first_sa_with_nt_without_gaes_formula": "gaes_adj_first_sa_with_nt_without_gaes",
    "_pd_ec_gaes_adj_first_sa_with_nt_without_kaliningrad_without_gaes_formula": (
        "gaes_adj_first_sa_with_nt_without_kaliningrad_without_gaes"
    ),
    "_pd_ec_gaes_adj_first_sa_without_nt_kaliningrad_without_gaes_formula": (
        "gaes_adj_first_sa_without_nt_kaliningrad_without_gaes"
    ),
    "_pd_ec_gaes_adj_first_sa_without_nt_without_kaliningrad_without_gaes_formula": (
        "gaes_adj_first_sa_without_nt_without_kaliningrad_without_gaes"
    ),
    "_pd_ec_first_sa_with_nt_with_gaes_formula": "first_sa_with_nt_with_gaes_with_kaliningrad_py",
    "_pd_ec_first_sa_without_nt_without_kaliningrad_with_gaes_formula": (
        "first_sa_without_nt_without_kaliningrad_with_gaes"
    ),
    "_pd_ec_ees_russia_ez_row_tooltip": "cz_russia_without_nt",
    "_pd_ec_ees_russia_ez_with_nt_tooltip": "ees_russia_ez_with_nt",
    "_pd_ec_oes_ees_russia_without_nt_mln_tooltip": "oes_ees_russia_without_nt_mln",
    "_pd_ec_oes_ees_russia_with_nt_mln_tooltip": "oes_ees_russia_with_nt_mln",
    "_pd_ec_oes_tites_mln_tooltip": "oes_tites_mln",
}


def inject_ec_formula_template_variables(
    context: dict[str, Any],
    formula_texts: dict[str, str],
) -> None:
    for var_name, registry_key in EC_FORMULA_TEMPLATE_VAR_KEYS.items():
        context[var_name] = formula_texts.get(registry_key, "")
