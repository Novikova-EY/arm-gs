# -*- coding: utf-8 -*-
"""Сопоставление строк сводки нагрузок с ключами формул (иконка «i»)."""

from __future__ import annotations

from typing import Any

from app.common.perimeter_variant.constants import legacy_nt_group_for_perimeter_code
from app.common.perimeter_variant.registry import CODE_WITH_NT, CODE_WITHOUT_NT
from app.power_demand.services.pd_peak_usage_hours_services import (
    combined_on_key_from_peak_combined_usage_hours,
)
from app.power_demand.services.power_demand_summary_formula_registry import get_formula_def

_SECOND_SYNC_AREA_LABEL_CF = "вторая синхронная"
_NT_KEY_SUFFIXES = ("_without_nt", "_with_nt")


def _label_cf(row: dict[str, Any]) -> str:
    return str(row.get("entity_label") or "").strip().casefold()


def _is_second_synchronous_area(row: dict[str, Any]) -> bool:
    return _label_cf(row).startswith(_SECOND_SYNC_AREA_LABEL_CF)


def _is_first_synchronous_area(row: dict[str, Any]) -> bool:
    lbl = _label_cf(row)
    if not lbl or lbl.startswith(_SECOND_SYNC_AREA_LABEL_CF):
        return False
    return "калининград" not in lbl


def _is_kaliningrad_synchronous_area(row: dict[str, Any]) -> bool:
    return "калининград" in _label_cf(row)


def _is_far_east_federal_district(row: dict[str, Any]) -> bool:
    lbl = _label_cf(row).replace("ё", "е")
    for prefix in ("фо - ", "фо — "):
        if lbl.startswith(prefix):
            lbl = lbl[len(prefix) :].strip()
            break
    return "дальневосточн" in lbl


def strip_pd_formula_nt_suffix(formula_key: str | None) -> str:
    """Убрать хвостовой ``_with_nt`` / ``_without_nt`` у ключа формулы."""
    key = str(formula_key or "").strip()
    if not key:
        return ""
    for suffix in _NT_KEY_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


def nt_group_for_pd_formula_row(row: dict[str, Any]) -> str:
    """Группа НТ для выбора текста формулы: ``with_nt`` или ``without_nt``.

    Учитывает составные коды (``with_nt_without_gaes``, ``o1_with_nt`` и т.п.)
    и подпись строки («… с НТ» / «… без НТ»), если кода нет.
    """
    code = str(row.get("perimeter_variant_code") or "").strip()
    if code:
        group = legacy_nt_group_for_perimeter_code(code)
        if group in (CODE_WITH_NT, CODE_WITHOUT_NT):
            return group
        # o1_with_nt / o1_without_nt и прочие составные коды вне GAES-группы.
        # «without_nt» проверяем раньше: иначе «with_nt» ложно сработает на подстроке.
        normalized = code.casefold()
        if "without_nt" in normalized:
            return CODE_WITHOUT_NT
        if "with_nt" in normalized:
            return CODE_WITH_NT

    lbl = _label_cf(row)
    compact = str(row.get("pd_pd_entity_label_compact_nt") or "").strip().casefold()
    for candidate in (lbl, compact):
        if candidate.endswith(" без нт") or " без нт" in candidate:
            return CODE_WITHOUT_NT
        if candidate.endswith(" с нт") or " с нт" in candidate:
            return CODE_WITH_NT
    return CODE_WITHOUT_NT


def _nt_suffix(nt_group: Any) -> str:
    if nt_group == CODE_WITH_NT:
        return "_with_nt"
    return "_without_nt"


def _nt_formula_key(base_key: str, nt_group: Any) -> str | None:
    if not base_key:
        return None
    bare = strip_pd_formula_nt_suffix(base_key)
    candidate = f"{bare}{_nt_suffix(nt_group)}"
    if get_formula_def(candidate):
        return candidate
    if get_formula_def(bare):
        return bare
    if get_formula_def(base_key):
        return base_key
    return None


def resolve_pd_summary_parameter_formula_base_key(row: dict[str, Any]) -> str | None:
    """Базовый ключ формулы (без суффикса _with_nt/_without_nt) для строки показателя."""
    explicit = row.get("pd_formula_text_key")
    if explicit and get_formula_def(str(explicit)):
        return strip_pd_formula_nt_suffix(str(explicit)) or str(explicit)

    pk = str(row.get("parameter_key") or "")
    dm = str(row.get("demand_model_name") or "")
    ek = str(row.get("entity_kind") or "")

    if dm == "UnionEnergySystemDemandParameter":
        if pk == "calculated_max_power_mw":
            return "oes_ues_calc_max_oes_mw"
        if pk == "calculated_combined_on_ees_mw":
            return "oes_ues_calc_combined_ees_mw"
        if pk == "verify_for_calculated_max_power_mw":
            return "oes_verify_calc_max_mw"
        if pk == "verify_for_calculated_combined_on_ees_mw":
            return "oes_verify_combined_ees_mw"

    if dm == "FederalDistrictDemandParameter":
        if pk == "calculated_max_fo_mw":
            if _is_far_east_federal_district(row):
                return "fo_calc_max_mw_far_east"
            return "fo_calc_max_mw"
        if pk == "calculated_max_power_mw":
            if _is_far_east_federal_district(row):
                return "fo_calc_max_power_mw_far_east"
            return "fo_calc_max_power_mw"
        if pk == "calculated_combined_on_cz_mw":
            return "fo_calc_combined_on_cz_mw"
        if pk == "calculated_combined_on_ees_mw":
            return "fo_calc_combined_on_ees_mw"
        if pk == "verify_for_calculated_max_power_mw":
            return "fo_verify_calc_max_mw"
        if pk == "verify_for_calculated_combined_on_cz_mw":
            return "fo_verify_combined_on_cz_mw"
        if pk == "verify_for_calculated_combined_on_ees_mw":
            return "fo_verify_combined_ees_mw"
        if pk == "peak_max_power_usage_hours":
            return "fo_chi_federal_district"

    if dm == "CentralizedZoneDemandParameter" and pk == "peak_max_power_usage_hours":
        return "fo_chi_centralized_zone"

    if dm == "CentralizedZoneDemandParameter":
        if pk == "calculated_max_power_mw":
            return "cz_russia_calc_max_mw"
        if pk == "verify_for_calculated_max_power_mw":
            return "cz_russia_verify_calc_max_mw"

    if dm in ("EnergySystemTypeDemandParameter", "EesRussiaWithNtDemandParameter"):
        if pk == "calculated_max_ees_via_oes_mw":
            return "oes_ees_russia_calc_max_via_oes"
        if pk == "calculated_max_ees_russia_mw":
            return "oes_ees_russia_calc_max"
        if pk == "calculated_max_ees_via_es_mw":
            return "oes_ees_russia_calc_max_via_es"
        if pk == "calculated_max_ees_via_ez_mw":
            return "oes_ees_russia_calc_max_via_ez"

    if dm == "EesRussiaDemandParameter" and pk == "calculated_max_power_consumption_mw":
        return "oes_ees_calc_max_power_consumption"

    if pk == "verify_for_calculated_max_ees_russia_mw":
        return "ees_russia_verify_calc_max"

    if pk == "verify_for_calculated_max_ees_via_oes_mw":
        return "ees_russia_verify_calc_max_via_oes"

    if pk == "verify_for_calculated_max_ees_via_es_mw":
        return "ees_russia_verify_calc_max_via_es"

    if pk == "verify_for_calculated_max_ees_via_ez_mw":
        return "ees_russia_verify_calc_max_via_ez"

    if dm == "SynchronousAreaDemandParameter" and _is_second_synchronous_area(row):
        formula_key = {
            "max_power": "sa_second_max_power_from_ues_east",
            "peak_datetime": "sa_second_peak_datetime_from_ues_east",
            "avg_temp": "sa_second_avg_temp_from_ues_east",
            "combined_on_ees": "sa_second_combined_on_ees_from_ues_east",
            "calculated_max_power_mw": "sa_second_calc_max_power_mw",
            "calculated_max_sa_mw": "sa_second_calc_max_sa_mw",
            "peak_max_power_usage_hours": "sa_second_chi_from_ues_east",
            "peak_combined_on_ees_usage_hours": "sa_second_chi_combined_from_ues_east",
        }.get(pk)
        if formula_key:
            return formula_key

    if dm == "SynchronousAreaDemandParameter" and _is_kaliningrad_synchronous_area(row):
        formula_key = {
            "max_power": "sa_kaliningrad_max_power_from_es",
            "peak_datetime": "sa_kaliningrad_peak_datetime_from_es",
            "avg_temp": "sa_kaliningrad_avg_temp_from_es",
            "combined_on_ees": "sa_kaliningrad_combined_on_ees_from_es",
            "calculated_max_power_mw": "sa_kaliningrad_calc_max_power_mw",
            "calculated_max_sa_mw": "sa_kaliningrad_calc_max_sa_mw",
            "peak_max_power_usage_hours": "sa_kaliningrad_chi_from_es",
            "peak_combined_on_ees_usage_hours": "sa_kaliningrad_chi_combined_from_es",
        }.get(pk)
        if formula_key:
            return formula_key

    if dm == "SynchronousAreaDemandParameter" and _is_first_synchronous_area(row):
        if pk == "calculated_max_power_mw":
            return "sa_first_calc_max_power_mw"
        if pk == "calculated_max_sa_mw":
            return "sa_first_calc_max_sa_mw"

    if ek == "synchronous_area" and _is_second_synchronous_area(row):
        if pk == "verify_for_calculated_max_power_mw":
            return "sa_second_verify_max_power"
        if pk == "verify_for_calculated_max_sa_mw":
            return "sa_second_verify_combined_ees"

    if ek == "synchronous_area" and _is_kaliningrad_synchronous_area(row):
        if pk == "verify_for_calculated_max_power_mw":
            return "sa_kaliningrad_verify_max_power"
        if pk == "verify_for_calculated_max_sa_mw":
            return "sa_kaliningrad_verify_combined_ees"

    if ek == "synchronous_area" and _is_first_synchronous_area(row):
        if pk == "verify_for_calculated_max_power_mw":
            return "sa_first_verify_max_power"
        if pk == "verify_for_calculated_max_sa_mw":
            return "sa_first_verify_combined_ees"

    if pk == "verify_for_calculated_max_power_mw":
        if dm == "FederalDistrictDemandParameter":
            return "fo_verify_calc_max_mw"
        if dm == "CentralizedZoneDemandParameter":
            return "cz_russia_verify_calc_max_mw"
        return "oes_verify_calc_max_mw"

    if pk == "verify_for_calculated_combined_on_ees_mw":
        if dm == "FederalDistrictDemandParameter":
            return "fo_verify_combined_ees_mw"
        return "oes_verify_combined_ees_mw"

    if pk == "verify_for_calculated_combined_on_cz_mw":
        if dm == "FederalDistrictDemandParameter":
            return "fo_verify_combined_on_cz_mw"
        return None

    if pk == "verify_for_calculated_max_sa_mw":
        return "sa_first_verify_combined_ees"

    combined_on_key = combined_on_key_from_peak_combined_usage_hours(pk)
    if combined_on_key:
        return f"pd_peak_{combined_on_key}_usage_hours"

    if pk == "peak_max_power_usage_hours":
        if row.get("pd_pd_decentralized_zone_mark"):
            return "oes_chi_decentralized_zone"
        label = str(row.get("entity_label") or "").strip()
        ek = str(row.get("entity_kind") or "")
        if label == "Чукотский АО (в территориальных границах)" or ek == "chukotka_territorial_boundaries":
            return "oes_chi_chukotka_territorial"
        if label == "Чукотский АО" and ek != "chukotka_territorial_boundaries":
            return "oes_chi_chukotka_rd"
        dm = str(row.get("demand_model_name") or "")
        if dm == "RussiaFederationDemandParameter":
            return "oes_chi_russia"
        if dm == "EesRussiaDemandParameter":
            return "oes_chi_ees"
        if dm == "EnergySystemTypeDemandParameter":
            return "oes_chi_ues_russia"
        if dm == "SynchronousAreaDemandParameter" or ek == "synchronous_area":
            lbl = _label_cf(row)
            if lbl.startswith(_SECOND_SYNC_AREA_LABEL_CF):
                return "oes_chi_second_sa"
            if "калининград" in lbl:
                return "oes_chi_kaliningrad_sa"
            if _is_first_synchronous_area(row):
                return "oes_chi_first_sa"
        return "oes_peak_max_power_usage_hours"

    return None


def resolve_pd_summary_coeff_k_formula_base_key(row: dict[str, Any]) -> str | None:
    """Базовый ключ формулы для столбца k на сводках «коэффициенты»."""
    if row.get("pd_fo_coeff_cz_total"):
        return None
    pk = str(row.get("parameter_key") or "")
    dm = str(row.get("demand_model_name") or "")

    if pk == "combined_on_oes":
        return "coeff_res_oes_k"
    if pk == "combined_on_ees" and dm == "UnionEnergySystemDemandParameter":
        return "coeff_k_ues_combined_ees"
    if pk == "combined_on_ees":
        return "coeff_res_ees_k"
    if pk == "calculated_max_power_mw":
        return "coeff_k_ues_calc_max_oes"
    if pk == "calculated_combined_on_ees_mw":
        return "coeff_k_ues_calc_combined_ees"
    if pk == "calculated_max_ees_via_oes_mw":
        return "coeff_k_calculated_max_ees_via_oes"
    if pk == "calculated_max_ees_via_es_mw":
        return "coeff_k_calculated_max_ees_via_es"
    return None


def resolve_pd_summary_row_formula_key(row: dict[str, Any], *, base_key: str | None) -> str | None:
    if not base_key:
        return None
    return _nt_formula_key(base_key, nt_group_for_pd_formula_row(row))
