# -*- coding: utf-8 -*-
"""ЧЧИ (число часов использования максимального потребления мощности) на сводках /summary/."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITH_NT,
    CODE_WITH_NT_WITH_GAES,
    CODE_WITH_NT_WITHOUT_GAES,
    perimeter_variant_codes_prefer_without_gaes,
)
from app.common.perimeter_variant.registry import (
    is_o1_perimeter_variant_code,
    legacy_nt_group_for_perimeter_code,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
    EnergyUnitEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
)
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
    CentralizedZoneEnergyConsumptionParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
    EnergyZoneDemandParameter,
)
from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.power_demand.services.demand_summary_services import (
    _format_full_numeric_tooltip,
    _format_numeric,
    _parse_summary_cell_float,
)

PEAK_MAX_POWER_USAGE_HOURS_KEY = "peak_max_power_usage_hours"
PEAK_MAX_POWER_USAGE_HOURS_LABEL = (
    "Число часов использования максимального потребления мощности"
)

ENERGY_CONSUMPTION_MLN_KVT_CH_KEY = "energy_consumption_mln_kvt_ch"
ENERGY_CONSUMPTION_MLN_KVT_CH_LABEL = (
    "Потребление электрической энергии, млн кВтч"
)

COMBINED_ON_PARAMETER_KEYS_FOR_CHI: tuple[str, ...] = (
    "combined_on_ees",
    "combined_on_oes",
    "combined_on_es",
    "combined_on_ez",
    "combined_on_fo",
    "combined_on_cz",
)

def peak_combined_usage_hours_key(combined_on_key: str) -> str:
    return f"peak_{combined_on_key}_usage_hours"


def is_peak_combined_usage_hours_key(parameter_key: str) -> bool:
    pk = str(parameter_key or "").strip()
    return pk.startswith("peak_combined_on_") and pk.endswith("_usage_hours")


def combined_on_key_from_peak_combined_usage_hours(parameter_key: str) -> str | None:
    if not is_peak_combined_usage_hours_key(parameter_key):
        return None
    combined_key = str(parameter_key)[len("peak_") : -len("_usage_hours")]
    if combined_key in COMBINED_ON_PARAMETER_KEYS_FOR_CHI:
        return combined_key
    return None


def peak_combined_usage_hours_keys() -> frozenset[str]:
    return frozenset(
        peak_combined_usage_hours_key(k) for k in COMBINED_ON_PARAMETER_KEYS_FOR_CHI
    )

_AGGREGATE_EC_PARENT_ID = 0

_PD_TO_EC: dict[str, tuple[type, str | None]] = {
    RussiaFederationDemandParameter.__name__: (
        RussiaFederationEnergyConsumptionParameter,
        None,
    ),
    EesRussiaDemandParameter.__name__: (EesRussiaEnergyConsumptionParameter, None),
    EnergySystemTypeDemandParameter.__name__: (
        EnergySystemTypeEnergyConsumptionParameter,
        "id_energy_system_type",
    ),
    SynchronousAreaDemandParameter.__name__: (
        SynchronousAreaEnergyConsumptionParameter,
        "id_synchronous_area",
    ),
    UnionEnergySystemDemandParameter.__name__: (
        UnionEnergySystemEnergyConsumptionParameter,
        "id_union_energy_system",
    ),
    RegionalEnergySystemDemandParameter.__name__: (
        RegionalEnergySystemEnergyConsumptionParameter,
        "id_regional_energy_system",
    ),
    FederalDistrictDemandParameter.__name__: (
        FederalDistrictEnergyConsumptionParameter,
        "id_federal_district",
    ),
    RegionalDistrictDemandParameter.__name__: (
        RegionalDistrictEnergyConsumptionParameter,
        "id_regional_district",
    ),
    EnergyUnitDemandParameter.__name__: (
        EnergyUnitEnergyConsumptionParameter,
        "id_energy_unit",
    ),
    EnergyZoneDemandParameter.__name__: (
        EnergyZoneEnergyConsumptionParameter,
        "id_energy_zone",
    ),
    CentralizedZoneDemandParameter.__name__: (
        CentralizedZoneEnergyConsumptionParameter,
        None,
    ),
}

_OES_CHI_PD_MODELS = frozenset(_PD_TO_EC.keys())
# Потребление РФ в RussiaFederationEnergyConsumptionParameter хранится в млрд кВтч.
_RUSSIA_FEDERATION_EC_CHI_NUMERATOR_SCALE = 1000.0
# Итоговое ЧЧИ на сводках ОЭС / ФО / ЭЗ: (потребление, млн кВтч) / (мощность, МВт) × 1000.
_CHI_RESULT_DISPLAY_SCALE = 1000.0
# digits=-1 в format_decimal_for_display: округление до целого (0 = без округления).
_CHI_ROUNDING_DIGITS = -1

CzHubEcIndex = dict[tuple[str | None, Any], float]
# (ec_model_name, parent_id, pvc, slice) — ЭЭС России / синхронные зоны со сводной таблицы.
EesSaHubEcIndex = dict[tuple[str, int, str | None, Any], float]

def _load_oes_summary_table_hub_pipeline_rows(
    years: list[int],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    """Строки пайплайна summary_table (ЦЗ/ЭЭС/СЗ) для числителя ЧЧИ и строки потребления ЭЭ."""
    if not years:
        return []
    from app.energy_consumption.services.energy_consumption_summary_services import (
        build_summary_table_hub_oes_formula_pipeline_summary_rows,
    )

    return build_summary_table_hub_oes_formula_pipeline_summary_rows(
        rounding_digits,
        start_year=int(years[0]),
        end_year=int(years[-1]),
        filter_year_list=[],
    )


def _index_hub_ee_row_into_cz(
    index: CzHubEcIndex,
    row: dict[str, Any],
    years: list[int],
) -> None:
    from app.energy_consumption.services.energy_consumption_summary_services import (
        _raw_year_values_from_summary_row,
    )

    if row.get("demand_model_name") != CentralizedZoneEnergyConsumptionParameter.__name__:
        return
    if str(row.get("parameter_key") or "") != ENERGY_CONSUMPTION_MLN_KVT_CH_KEY:
        return
    pvc_raw = str(row.get("perimeter_variant_code") or "").strip()
    if pvc_raw and is_o1_perimeter_variant_code(pvc_raw):
        return
    pvc_key = pvc_raw if pvc_raw else None
    raw_by_year = _raw_year_values_from_summary_row(row, years)
    for year in years:
        raw = raw_by_year.get(int(year))
        if raw is not None:
            index[(pvc_key, int(year))] = float(raw)
    hist_raw = _parse_summary_cell_float(row.get("hist_value"))
    if hist_raw is not None:
        index[(pvc_key, "hist")] = float(hist_raw)


def _index_hub_ee_row_into_ees_sa(
    index: EesSaHubEcIndex,
    row: dict[str, Any],
    years: list[int],
) -> None:
    from app.energy_consumption.services.energy_consumption_summary_services import (
        _raw_year_values_from_summary_row,
    )

    ec_model_name = str(row.get("demand_model_name") or "")
    if ec_model_name not in (
        EesRussiaEnergyConsumptionParameter.__name__,
        SynchronousAreaEnergyConsumptionParameter.__name__,
    ):
        return
    if str(row.get("parameter_key") or "") != ENERGY_CONSUMPTION_MLN_KVT_CH_KEY:
        return
    pvc_raw = str(row.get("perimeter_variant_code") or "").strip()
    if pvc_raw and is_o1_perimeter_variant_code(pvc_raw):
        return
    pvc_key = pvc_raw if pvc_raw else None
    parent_raw = row.get("parent_id")
    if parent_raw is None:
        parent_id = _AGGREGATE_EC_PARENT_ID
    else:
        try:
            parent_id = int(parent_raw)
        except (TypeError, ValueError):
            parent_id = _AGGREGATE_EC_PARENT_ID
    raw_by_year = _raw_year_values_from_summary_row(row, years)
    for year in years:
        raw = raw_by_year.get(int(year))
        if raw is not None:
            index[(ec_model_name, parent_id, pvc_key, int(year))] = float(raw)
    hist_raw = _parse_summary_cell_float(row.get("hist_value"))
    if hist_raw is not None:
        index[(ec_model_name, parent_id, pvc_key, "hist")] = float(hist_raw)


def _build_oes_top_hub_ec_indexes(
    years: list[int],
    rounding_digits: int,
    *,
    need_cz: bool,
    need_ees_sa: bool,
    pipeline_rows: list[dict[str, Any]] | None = None,
) -> tuple[CzHubEcIndex | None, EesSaHubEcIndex | None]:
    """Индексы потребления ЦЗ / ЭЭС / СЗ как на EC «Сводная таблица» (+без ГАЭС)."""
    if not years or (not need_cz and not need_ees_sa):
        return None, None
    rows = (
        pipeline_rows
        if pipeline_rows is not None
        else _load_oes_summary_table_hub_pipeline_rows(years, rounding_digits)
    )
    cz_index: CzHubEcIndex | None = {} if need_cz else None
    ees_sa_index: EesSaHubEcIndex | None = {} if need_ees_sa else None
    for row in rows:
        if cz_index is not None:
            _index_hub_ee_row_into_cz(cz_index, row, years)
        if ees_sa_index is not None:
            _index_hub_ee_row_into_ees_sa(ees_sa_index, row, years)
    return cz_index, ees_sa_index


def _build_centralized_zone_hub_ec_chi_index(
    years: list[int],
    rounding_digits: int,
) -> CzHubEcIndex:
    """Потребление «ЦЗ России» как на /energy_consumption/summary_table/ (формулы с/без НТ)."""
    cz_index, _ = _build_oes_top_hub_ec_indexes(
        years,
        rounding_digits,
        need_cz=True,
        need_ees_sa=False,
    )
    return cz_index or {}


def _build_ees_sa_hub_ec_chi_index(
    years: list[int],
    rounding_digits: int,
) -> EesSaHubEcIndex:
    """Потребление ЭЭС России / СЗ как на EC summary/oes «Сводная таблица» (+без ГАЭС)."""
    _, ees_sa_index = _build_oes_top_hub_ec_indexes(
        years,
        rounding_digits,
        need_cz=False,
        need_ees_sa=True,
    )
    return ees_sa_index or {}


def _lookup_centralized_zone_hub_consumption(
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    cz_hub_index: CzHubEcIndex | None,
) -> float | None:
    if not cz_hub_index:
        return None
    for pvc in _ec_consumption_pvc_candidates_for_chi(anchor):
        pvc_key = str(pvc) if pvc not in (None, "") else None
        hit = cz_hub_index.get((pvc_key, slice_key))
        if hit is not None:
            return hit
    return None


def _lookup_ees_sa_hub_consumption(
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ees_sa_hub_index: EesSaHubEcIndex | None,
    ec_model_name: str,
    ec_parent_id: int,
) -> float | None:
    if not ees_sa_hub_index:
        return None
    for pvc in _ec_consumption_pvc_candidates_for_chi(anchor):
        pvc_key = str(pvc) if pvc not in (None, "") else None
        hit = ees_sa_hub_index.get(
            (ec_model_name, int(ec_parent_id), pvc_key, slice_key)
        )
        if hit is not None:
            return hit
    return None


def _chi_ec_consumption_scale_for_pd_model(pd_model_name: str) -> float:
    if pd_model_name == RussiaFederationDemandParameter.__name__:
        return _RUSSIA_FEDERATION_EC_CHI_NUMERATOR_SCALE
    return 1.0


def _legacy_nt_display_code_for_chi_anchor(anchor: dict[str, Any]) -> str | None:
    if anchor.get("pd_pd_nt_extra_row"):
        return CODE_WITH_NT
    label = str(anchor.get("entity_label") or "")
    if "с НТ" in label and "без НТ" not in label:
        return CODE_WITH_NT
    if "без НТ" in label:
        return CODE_WITHOUT_NT
    return None


def _pd_perimeter_variant_code_for_chi_anchor(anchor: dict[str, Any]) -> str | None:
    code = str(anchor.get("perimeter_variant_code") or "").strip()
    if code:
        return code
    return _legacy_nt_display_code_for_chi_anchor(anchor)


def _chi_ec_consumption_pvc_for_anchor(anchor: dict[str, Any]) -> str | None:
    """Код варианта потребления ЭЭ для числителя ЧЧИ (тот же, что у max_power в блоке)."""
    return _pd_perimeter_variant_code_for_chi_anchor(anchor)


def _ec_parent_id_for_chi(
    pd_model_name: str,
    parent_id: int | None,
) -> int | None:
    fk_column = _PD_TO_EC[pd_model_name][1]
    if fk_column is None:
        return _AGGREGATE_EC_PARENT_ID
    if parent_id is None:
        return None
    return int(parent_id)


def _resolve_ec_parent_id_for_chi_block(
    anchor: dict[str, Any],
    *,
    ec_model_name: str,
    anchor_parent_id: int | None,
    fk_column: str | None,
    years: list[int],
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> int | None:
    """FK для числителя ЧЧИ: из строки сводки или единственный id из индекса потребления ЭЭ."""
    base_parent_id = _ec_parent_id_for_chi(
        str(anchor.get("demand_model_name") or ""),
        anchor_parent_id,
    )
    if base_parent_id is None or fk_column is None:
        return base_parent_id

    pvc_candidates = _ec_consumption_pvc_candidates_for_chi(anchor)
    slice_keys: list[Any] = ["hist", *[int(y) for y in years]]
    for slice_key in slice_keys:
        for pvc in pvc_candidates:
            if (
                _lookup_ec_consumption_direct(
                    ec_model_name,
                    int(base_parent_id),
                    pvc,
                    slice_key,
                    ec_index=ec_index,
                )
                is not None
            ):
                return int(base_parent_id)

    pvc_keys = {str(pvc) if pvc not in (None, "") else None for pvc in pvc_candidates}
    slice_key_set = set(slice_keys)
    matching_parent_ids: set[int] = set()
    for model_name, parent_id, pvc_key, slice_key in ec_index:
        if model_name != ec_model_name:
            continue
        if pvc_key not in pvc_keys:
            continue
        if slice_key not in slice_key_set:
            continue
        matching_parent_ids.add(int(parent_id))
    if len(matching_parent_ids) == 1:
        return next(iter(matching_parent_ids))
    return int(base_parent_id)


def _ec_consumption_pvc_candidates_for_chi(anchor: dict[str, Any]) -> list[str | None]:
    """Потребление ЭЭ для ЧЧИ — вариант периметра строки (с тем же порядком поиска, что у max_power).

    Для группы «без НТ» в конце добавляется None: в БД старые годы часто лежат
    с perimeter_variant_code IS NULL до явной привязки варианта блока.
    """
    pvc = _chi_ec_consumption_pvc_for_anchor(anchor)
    if not pvc:
        return [None]
    candidates: list[str | None] = list(perimeter_variant_codes_prefer_without_gaes(pvc))
    if not candidates:
        candidates = [pvc]
    if legacy_nt_group_for_perimeter_code(pvc) == CODE_WITHOUT_NT and None not in candidates:
        candidates.append(None)
    return candidates


def _lookup_ec_consumption_direct(
    ec_model_name: str,
    parent_id: int,
    pvc: str | None,
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> float | None:
    pvc_key = str(pvc) if pvc not in (None, "") else None
    return ec_index.get((ec_model_name, parent_id, pvc_key, slice_key))


def _lookup_ec_consumption_for_chi(
    ec_model_name: str,
    parent_id: int,
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    parent_fk_column: str | None,
    years: list[int],
) -> float | None:
    for pvc in _ec_consumption_pvc_candidates_for_chi(anchor):
        hit = _lookup_ec_consumption_direct(
            ec_model_name, parent_id, pvc, slice_key, ec_index=ec_index
        )
        if hit is not None:
            return hit
    return None


def _sum_optional_ec_mln_parts(
    a: float | None,
    b: float | None,
) -> float | None:
    if a is None and b is None:
        return None
    return float(a or 0.0) + float(b or 0.0)


def _anchor_with_paired_without_nt_pvc(anchor: dict[str, Any]) -> dict[str, Any]:
    pvc = str(anchor.get("perimeter_variant_code") or "").strip()
    without = {
        CODE_WITH_NT: CODE_WITHOUT_NT,
        CODE_WITH_NT_WITHOUT_GAES: CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES: CODE_WITHOUT_NT_WITH_GAES,
    }.get(pvc)
    if without is None:
        without = CODE_WITHOUT_NT
    return {**anchor, "perimeter_variant_code": without}


@lru_cache(maxsize=1)
def _south_federal_district_id_for_chi() -> int | None:
    from app.power_demand.services.demand_summary_services import (
        _south_federal_district_for_nt_attachment,
    )

    south_fd, _ = _south_federal_district_for_nt_attachment()
    if south_fd is None:
        return None
    return int(south_fd.id)


def _is_south_federal_district_with_nt_chi_anchor(
    anchor: dict[str, Any],
    ec_parent_id: int,
) -> bool:
    if str(anchor.get("demand_model_name") or "") != FederalDistrictDemandParameter.__name__:
        return False
    south_fd_id = _south_federal_district_id_for_chi()
    if south_fd_id is None or int(ec_parent_id) != int(south_fd_id):
        return False
    pvc = _chi_ec_consumption_pvc_for_anchor(anchor)
    return legacy_nt_group_for_perimeter_code(pvc) == CODE_WITH_NT


def _sum_nt_subjects_ec_mln_for_chi(
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
) -> float | None:
    from app.power_demand.services.demand_summary_services import (
        _new_territories_regional_district_ids,
    )

    ec_model_name = RegionalDistrictEnergyConsumptionParameter.__name__
    total: float | None = None
    for rd_id in _new_territories_regional_district_ids():
        hit = _lookup_ec_consumption_direct(
            ec_model_name,
            int(rd_id),
            None,
            slice_key,
            ec_index=ec_index,
        )
        if hit is None:
            continue
        total = hit if total is None else total + hit
    return total


def _chi_ec_consumption_mln_for_south_fd_with_nt(
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    ec_model_name: str,
    ec_parent_id: int,
    fk_column: str | None,
    years: list[int],
) -> float | None:
    """Южный ФО с НТ: потребление без НТ + субъекты НТ (как на сводке потребления).

    Если сумма по субъектам НТ равна 0 или пуста — нет значения ЧЧИ.
    """
    without_anchor = _anchor_with_paired_without_nt_pvc(anchor)
    base_hit = _lookup_ec_consumption_for_chi(
        ec_model_name,
        ec_parent_id,
        without_anchor,
        slice_key,
        ec_index=ec_index,
        parent_fk_column=fk_column,
        years=years,
    )
    nt_hit = _sum_nt_subjects_ec_mln_for_chi(slice_key, ec_index=ec_index)
    if nt_hit is None or float(nt_hit) == 0.0:
        return None
    combined = _sum_optional_ec_mln_parts(base_hit, nt_hit)
    if combined is None:
        return None
    scale = _chi_ec_consumption_scale_for_pd_model(
        str(anchor.get("demand_model_name") or "")
    )
    return combined * scale


def _slice_key_from_ec_row(row: Any) -> Any:
    if getattr(row, "is_historical_maximum", False):
        return "hist"
    return getattr(row, "year_number", None)


def _build_ec_consumption_index(
    years: list[int],
) -> dict[tuple[str, int, str | None, Any], float]:
    """(ec_model_name, parent_id, pvc, slice) -> energy_consumption_mln_kvt_ch."""
    from app.power_demand.services.pd_ec_consumption_index_cache import (
        get_ec_consumption_index_for_years,
    )

    return get_ec_consumption_index_for_years(years)


def _chi_ec_consumption_mln_for_anchor(
    anchor: dict[str, Any],
    slice_key: Any,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    ec_model_name: str,
    ec_parent_id: int,
    fk_column: str | None,
    years: list[int],
    cz_hub_index: CzHubEcIndex | None = None,
    ees_sa_hub_index: EesSaHubEcIndex | None = None,
) -> float | None:
    if str(anchor.get("demand_model_name") or "") == CentralizedZoneDemandParameter.__name__:
        hub_hit = _lookup_centralized_zone_hub_consumption(
            anchor,
            slice_key,
            cz_hub_index=cz_hub_index,
        )
        if hub_hit is not None:
            return hub_hit
    if str(anchor.get("demand_model_name") or "") in (
        EesRussiaDemandParameter.__name__,
        SynchronousAreaDemandParameter.__name__,
    ):
        hub_hit = _lookup_ees_sa_hub_consumption(
            anchor,
            slice_key,
            ees_sa_hub_index=ees_sa_hub_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
        )
        if hub_hit is not None:
            return hub_hit
    if _is_south_federal_district_with_nt_chi_anchor(anchor, ec_parent_id):
        return _chi_ec_consumption_mln_for_south_fd_with_nt(
            anchor,
            slice_key,
            ec_index=ec_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
            fk_column=fk_column,
            years=years,
        )
    hit = _lookup_ec_consumption_for_chi(
        ec_model_name,
        ec_parent_id,
        anchor,
        slice_key,
        ec_index=ec_index,
        parent_fk_column=fk_column,
        years=years,
    )
    if hit is None:
        return None
    scale = _chi_ec_consumption_scale_for_pd_model(
        str(anchor.get("demand_model_name") or "")
    )
    return hit * scale


def _divide_hours(ec_mln: float | None, max_mw: float | None) -> float | None:
    if ec_mln is None or max_mw is None:
        return None
    if abs(max_mw) < 1e-12:
        return None
    return ec_mln / max_mw * _CHI_RESULT_DISPLAY_SCALE


def _divide_combined_peak_usage_hours(
    ec_mln_kvt_ch: float | None,
    combined_on_mw: float | None,
) -> float | None:
    """ЧЧИ совмещённого: (потребление, млн кВтч) / (совмещённое, МВт) × 1000."""
    return _divide_hours(ec_mln_kvt_ch, combined_on_mw)


def _find_row_by_parameter_key(
    block: list[dict[str, Any]],
    parameter_key: str,
) -> dict[str, Any] | None:
    for row in block:
        if str(row.get("parameter_key") or "") == parameter_key:
            return row
    return None


def _find_max_power_row(block: list[dict[str, Any]]) -> dict[str, Any] | None:
    return _find_row_by_parameter_key(block, "max_power")


def _combined_chi_label_from_combined_row(combined_row: dict[str, Any]) -> str:
    label = str(combined_row.get("parameter_label") or "").strip()
    if not label:
        return (
            "Число часов использования совмещенного потребления мощности "
            "на час прохождения максимума"
        )
    for suffix in (", МВт", ", Мвт"):
        if label.endswith(suffix):
            label = label[: -len(suffix)].strip()
            break
    for prefix in (
        "Совмещенное потребление мощности ",
        "Совмещенный максимум потребления мощности ",
        "Совмещенный ФО на ",
        "Совмещенный на ",
    ):
        if label.startswith(prefix):
            rest = label[len(prefix) :].strip()
            return (
                "Число часов использования совмещенного потребления мощности "
                + rest
            )
    return (
        "Число часов использования совмещенного потребления мощности "
        + label
    )


def _insert_after_parameter_key(
    summary_rows: list[dict[str, Any]],
    block_start: int,
    block_size: int,
    after_parameter_key: str,
) -> int:
    end = min(block_start + block_size, len(summary_rows))
    insert_at = block_start + block_size
    for i in range(block_start, end):
        if str(summary_rows[i].get("parameter_key") or "") == after_parameter_key:
            insert_at = i + 1
            break
    return insert_at


def _combined_chi_insert_after_key(
    combined_on_key: str,
    _keys_in_block: set[str],
) -> str:
    return combined_on_key


def _copy_chi_territory_fields_from_anchor(
    new_row: dict[str, Any],
    anchor: dict[str, Any],
) -> None:
    """Копирует id секций для пагинации сводки (ФО / энергозоны) и фильтров."""
    for field in ("id_federal_district", "id_energy_zone"):
        if anchor.get(field) is not None:
            new_row[field] = anchor.get(field)


def _hub_indexes_for_summary_blocks(
    blocks: list[tuple[int, int, list[dict[str, Any]]]],
    years: list[int],
    rounding_digits: int,
) -> tuple[CzHubEcIndex | None, EesSaHubEcIndex | None]:
    need_cz = False
    need_ees_sa = False
    for _start, _span, block in blocks:
        dm = str(block[0].get("demand_model_name") or "")
        if dm == CentralizedZoneDemandParameter.__name__:
            need_cz = True
        elif dm in (
            EesRussiaDemandParameter.__name__,
            SynchronousAreaDemandParameter.__name__,
        ):
            need_ees_sa = True
    return _build_oes_top_hub_ec_indexes(
        years,
        rounding_digits,
        need_cz=need_cz,
        need_ees_sa=need_ees_sa,
    )


def _insert_index_before_peak_datetime(
    summary_rows: list[dict[str, Any]],
    block_start: int,
    block_size: int,
) -> int:
    end = min(block_start + block_size, len(summary_rows))
    for i in range(block_start, end):
        if str(summary_rows[i].get("parameter_key") or "") == "peak_datetime":
            return i
    return block_start + 1


def _build_chi_row_for_block(
    block: list[dict[str, Any]],
    years: list[int],
    _rounding_digits: int,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    cz_hub_index: CzHubEcIndex | None = None,
    ees_sa_hub_index: EesSaHubEcIndex | None = None,
) -> dict[str, Any] | None:
    anchor = block[0]
    pd_model_name = str(anchor.get("demand_model_name") or "")
    if pd_model_name not in _OES_CHI_PD_MODELS:
        return None
    parent_id = anchor.get("parent_id")
    ec_model, fk_column = _PD_TO_EC[pd_model_name]
    ec_model_name = ec_model.__name__
    ec_index_local = ec_index
    ec_parent_id = _resolve_ec_parent_id_for_chi_block(
        anchor,
        ec_model_name=ec_model_name,
        anchor_parent_id=parent_id,
        fk_column=fk_column,
        years=years,
        ec_index=ec_index_local,
    )
    if ec_parent_id is None:
        return None
    max_power_row = _find_max_power_row(block)
    if max_power_row is None:
        return None

    year_values: list[str] = []
    year_tooltips: list[str] = []
    for ix, year in enumerate(years):
        ec_val = _chi_ec_consumption_mln_for_anchor(
            anchor,
            int(year),
            ec_index=ec_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
            fk_column=fk_column,
            years=years,
            cz_hub_index=cz_hub_index,
            ees_sa_hub_index=ees_sa_hub_index,
        )
        mw_val = _parse_summary_cell_float(
            (max_power_row.get("year_values") or [None] * len(years))[ix]
        )
        hours = _divide_hours(ec_val, mw_val)
        if hours is None:
            year_values.append("—")
            year_tooltips.append("")
        else:
            year_values.append(_format_numeric(hours, _CHI_ROUNDING_DIGITS))
            year_tooltips.append(_format_full_numeric_tooltip(hours))

    hist_ec = _chi_ec_consumption_mln_for_anchor(
        anchor,
        "hist",
        ec_index=ec_index,
        ec_model_name=ec_model_name,
        ec_parent_id=ec_parent_id,
        fk_column=fk_column,
        years=years,
        cz_hub_index=cz_hub_index,
        ees_sa_hub_index=ees_sa_hub_index,
    )
    hist_mw = _parse_summary_cell_float(max_power_row.get("hist_value"))
    hist_hours = _divide_hours(hist_ec, hist_mw)
    if hist_hours is None:
        hist_value = "—"
        hist_tooltip = ""
    else:
        hist_value = _format_numeric(hist_hours, _CHI_ROUNDING_DIGITS)
        hist_tooltip = _format_full_numeric_tooltip(hist_hours)

    new_row = {
        "entity_label": anchor.get("entity_label"),
        "entity_rowspan": int(anchor.get("entity_rowspan") or len(block)) + 1,
        "entity_depth": anchor.get("entity_depth", 0),
        "entity_kind": anchor.get("entity_kind"),
        "show_entity_cell": False,
        "parameter_key": PEAK_MAX_POWER_USAGE_HOURS_KEY,
        "parameter_label": PEAK_MAX_POWER_USAGE_HOURS_LABEL,
        "demand_model_name": anchor.get("demand_model_name"),
        "parent_fk_column": anchor.get("parent_fk_column"),
        "parent_id": anchor.get("parent_id"),
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": hist_value,
        "year_values": year_values,
        "hist_numeric_tooltip": hist_tooltip,
        "year_numeric_tooltips": year_tooltips,
        "id_union_energy_system": anchor.get("id_union_energy_system"),
        "id_regional_energy_system": anchor.get("id_regional_energy_system"),
        "id_regional_district": anchor.get("id_regional_district"),
        "id_energy_unit": anchor.get("id_energy_unit"),
        "perimeter_variant_code": _chi_ec_consumption_pvc_for_anchor(anchor)
        or anchor.get("perimeter_variant_code"),
        "year_coeff_k_stored": [],
        "entity_note_text": anchor.get("entity_note_text") or "",
        "entity_note_row_id": anchor.get("entity_note_row_id"),
        "show_entity_note_cell": False,
        "pd_pd_chi_row": True,
    }
    if anchor.get("pd_pd_decentralized_zone_mark"):
        new_row["pd_pd_decentralized_zone_mark"] = True
    if anchor.get("pd_pd_skip_empty_hide_row"):
        new_row["pd_pd_skip_empty_hide_row"] = True
    if anchor.get("id_synchronous_area") is not None:
        new_row["id_synchronous_area"] = anchor.get("id_synchronous_area")
    if anchor.get("pd_pd_nt_extra_row"):
        new_row["pd_pd_nt_extra_row"] = True
    if anchor.get("pd_pd_territory_detail_row"):
        new_row["pd_pd_territory_detail_row"] = True
        new_row["pd_pd_territory_compact_hide_row"] = True
    elif anchor.get("pd_pd_territory_compact_hide_row"):
        new_row["pd_pd_territory_compact_hide_row"] = True
    if anchor.get("pd_pd_summary_table_only_row"):
        new_row["pd_pd_summary_table_only_row"] = True
    _copy_chi_territory_fields_from_anchor(new_row, anchor)
    return new_row


def inject_peak_usage_hours_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Добавляет строки ЧЧИ перед «Дата и время» для поддерживаемых сущностей сводки."""
    if not summary_rows or not years:
        return

    blocks: list[tuple[int, int, list[dict[str, Any]]]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            span = int(row.get("entity_rowspan") or 1)
            block = summary_rows[i : i + span]
            dm = str(block[0].get("demand_model_name") or "")
            if dm in _OES_CHI_PD_MODELS and not any(
                str(r.get("parameter_key") or "") == PEAK_MAX_POWER_USAGE_HOURS_KEY
                for r in block
            ):
                blocks.append((i, span, block))
            i += span
        else:
            i += 1

    if not blocks:
        return

    ec_index = _build_ec_consumption_index(years)
    cz_hub_index, ees_sa_hub_index = _hub_indexes_for_summary_blocks(
        blocks, years, rounding_digits
    )
    insertions: list[tuple[int, dict[str, Any], int, int]] = []
    for start, span, block in blocks:
        new_row = _build_chi_row_for_block(
            block,
            years,
            rounding_digits,
            ec_index=ec_index,
            cz_hub_index=cz_hub_index,
            ees_sa_hub_index=ees_sa_hub_index,
        )
        if new_row is None:
            continue
        insert_at = _insert_index_before_peak_datetime(summary_rows, start, span)
        insertions.append((insert_at, new_row, start, span))

    for insert_at, new_row, start, span in reversed(insertions):
        summary_rows.insert(insert_at, new_row)
        new_span = span + 1
        for k in range(start, start + new_span):
            summary_rows[k]["entity_rowspan"] = new_span


def _build_combined_chi_row_for_block(
    block: list[dict[str, Any]],
    years: list[int],
    *,
    combined_on_key: str,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    cz_hub_index: CzHubEcIndex | None = None,
    ees_sa_hub_index: EesSaHubEcIndex | None = None,
) -> dict[str, Any] | None:
    anchor = block[0]
    pd_model_name = str(anchor.get("demand_model_name") or "")
    if pd_model_name not in _OES_CHI_PD_MODELS:
        return None
    combined_row = _find_row_by_parameter_key(block, combined_on_key)
    if combined_row is None:
        return None

    parent_id = anchor.get("parent_id")
    ec_model, fk_column = _PD_TO_EC[pd_model_name]
    ec_model_name = ec_model.__name__
    ec_parent_id = _resolve_ec_parent_id_for_chi_block(
        anchor,
        ec_model_name=ec_model_name,
        anchor_parent_id=parent_id,
        fk_column=fk_column,
        years=years,
        ec_index=ec_index,
    )
    if ec_parent_id is None:
        return None

    chi_key = peak_combined_usage_hours_key(combined_on_key)
    year_values: list[str] = []
    year_tooltips: list[str] = []
    for ix, year in enumerate(years):
        ec_val = _chi_ec_consumption_mln_for_anchor(
            anchor,
            int(year),
            ec_index=ec_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
            fk_column=fk_column,
            years=years,
            cz_hub_index=cz_hub_index,
            ees_sa_hub_index=ees_sa_hub_index,
        )
        combined_mw = _parse_summary_cell_float(
            (combined_row.get("year_values") or [None] * len(years))[ix]
        )
        hours = _divide_combined_peak_usage_hours(ec_val, combined_mw)
        if hours is None:
            year_values.append("—")
            year_tooltips.append("")
        else:
            year_values.append(_format_numeric(hours, _CHI_ROUNDING_DIGITS))
            year_tooltips.append(_format_full_numeric_tooltip(hours))

    hist_ec = _chi_ec_consumption_mln_for_anchor(
        anchor,
        "hist",
        ec_index=ec_index,
        ec_model_name=ec_model_name,
        ec_parent_id=ec_parent_id,
        fk_column=fk_column,
        years=years,
        cz_hub_index=cz_hub_index,
        ees_sa_hub_index=ees_sa_hub_index,
    )
    hist_combined = _parse_summary_cell_float(combined_row.get("hist_value"))
    hist_hours = _divide_combined_peak_usage_hours(hist_ec, hist_combined)
    if hist_hours is None:
        hist_value = "—"
        hist_tooltip = ""
    else:
        hist_value = _format_numeric(hist_hours, _CHI_ROUNDING_DIGITS)
        hist_tooltip = _format_full_numeric_tooltip(hist_hours)

    new_row = {
        "entity_label": anchor.get("entity_label"),
        "entity_rowspan": int(anchor.get("entity_rowspan") or len(block)) + 1,
        "entity_depth": anchor.get("entity_depth", 0),
        "entity_kind": anchor.get("entity_kind"),
        "show_entity_cell": False,
        "parameter_key": chi_key,
        "parameter_label": _combined_chi_label_from_combined_row(combined_row),
        "demand_model_name": anchor.get("demand_model_name"),
        "parent_fk_column": anchor.get("parent_fk_column"),
        "parent_id": anchor.get("parent_id"),
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": hist_value,
        "year_values": year_values,
        "hist_numeric_tooltip": hist_tooltip,
        "year_numeric_tooltips": year_tooltips,
        "id_union_energy_system": anchor.get("id_union_energy_system"),
        "id_regional_energy_system": anchor.get("id_regional_energy_system"),
        "id_regional_district": anchor.get("id_regional_district"),
        "id_energy_unit": anchor.get("id_energy_unit"),
        "perimeter_variant_code": anchor.get("perimeter_variant_code"),
        "year_coeff_k_stored": [],
        "entity_note_text": anchor.get("entity_note_text") or "",
        "entity_note_row_id": anchor.get("entity_note_row_id"),
        "show_entity_note_cell": False,
        "pd_pd_chi_row": True,
        "pd_pd_chi_combined_on_key": combined_on_key,
    }
    if anchor.get("pd_pd_decentralized_zone_mark"):
        new_row["pd_pd_decentralized_zone_mark"] = True
    if anchor.get("pd_pd_skip_empty_hide_row"):
        new_row["pd_pd_skip_empty_hide_row"] = True
    if anchor.get("id_synchronous_area") is not None:
        new_row["id_synchronous_area"] = anchor.get("id_synchronous_area")
    if anchor.get("pd_pd_nt_extra_row"):
        new_row["pd_pd_nt_extra_row"] = True
    if anchor.get("pd_pd_territory_detail_row"):
        new_row["pd_pd_territory_detail_row"] = True
        new_row["pd_pd_territory_compact_hide_row"] = True
    elif anchor.get("pd_pd_territory_compact_hide_row"):
        new_row["pd_pd_territory_compact_hide_row"] = True
    if anchor.get("pd_pd_summary_table_only_row"):
        new_row["pd_pd_summary_table_only_row"] = True
    _copy_chi_territory_fields_from_anchor(new_row, anchor)
    return new_row


def inject_combined_peak_usage_hours_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    _rounding_digits: int,
) -> None:
    """ЧЧИ совмещённого потребления: потребление ЭЭ (млн кВтч) / combined_on (МВт) × 1000."""
    if not summary_rows or not years:
        return

    blocks: list[tuple[int, int, list[dict[str, Any]]]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            span = int(row.get("entity_rowspan") or 1)
            block = summary_rows[i : i + span]
            dm = str(block[0].get("demand_model_name") or "")
            if dm in _OES_CHI_PD_MODELS:
                blocks.append((i, span, block))
            i += span
        else:
            i += 1

    if not blocks:
        return

    ec_index = _build_ec_consumption_index(years)
    cz_hub_index, ees_sa_hub_index = _hub_indexes_for_summary_blocks(
        blocks, years, _rounding_digits
    )

    insertions: list[tuple[int, dict[str, Any], int, int]] = []
    for start, span, block in blocks:
        keys_in_block = {
            str(r.get("parameter_key") or "")
            for r in block
            if str(r.get("parameter_key") or "")
        }
        existing_chi = {
            pk
            for pk in keys_in_block
            if is_peak_combined_usage_hours_key(pk)
        }
        for combined_on_key in COMBINED_ON_PARAMETER_KEYS_FOR_CHI:
            if combined_on_key not in keys_in_block:
                continue
            chi_key = peak_combined_usage_hours_key(combined_on_key)
            if chi_key in existing_chi:
                continue
            new_row = _build_combined_chi_row_for_block(
                block,
                years,
                combined_on_key=combined_on_key,
                ec_index=ec_index,
                cz_hub_index=cz_hub_index,
                ees_sa_hub_index=ees_sa_hub_index,
            )
            if new_row is None:
                continue
            after_key = _combined_chi_insert_after_key(combined_on_key, keys_in_block)
            insert_at = _insert_after_parameter_key(
                summary_rows,
                start,
                span,
                after_key,
            )
            insertions.append((insert_at, new_row, start, span))

    from collections import defaultdict

    grouped: dict[int, list[tuple[int, dict[str, Any], int]]] = defaultdict(list)
    for insert_at, new_row, start, span in insertions:
        grouped[start].append((insert_at, new_row, span))

    for start in sorted(grouped.keys(), reverse=True):
        items = grouped[start]
        span = items[0][2]
        for insert_at, new_row, _ in sorted(items, key=lambda item: -item[0]):
            summary_rows.insert(insert_at, new_row)
        new_span = span + len(items)
        for k in range(start, start + new_span):
            summary_rows[k]["entity_rowspan"] = new_span


def inject_oes_peak_usage_hours_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Сводка /summary/oes/: строки ЧЧИ (обратная совместимость)."""
    inject_peak_usage_hours_rows(summary_rows, years, rounding_digits)
    inject_combined_peak_usage_hours_rows(summary_rows, years, rounding_digits)


def _insert_index_before_max_power(
    summary_rows: list[dict[str, Any]],
    block_start: int,
    block_size: int,
) -> int:
    end = min(block_start + block_size, len(summary_rows))
    for i in range(block_start, end):
        if str(summary_rows[i].get("parameter_key") or "") == "max_power":
            return i
    return block_start


def _build_energy_consumption_row_for_block(
    block: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    ec_index: dict[tuple[str, int, str | None, Any], float],
    cz_hub_index: CzHubEcIndex | None = None,
    ees_sa_hub_index: EesSaHubEcIndex | None = None,
) -> dict[str, Any] | None:
    """Строка «Потребление электрической энергии, млн кВтч» (только чтение) для блока сводки."""
    anchor = block[0]
    pd_model_name = str(anchor.get("demand_model_name") or "")
    if pd_model_name not in _OES_CHI_PD_MODELS:
        return None
    if any(
        str(r.get("parameter_key") or "") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY
        for r in block
    ):
        return None
    parent_id = anchor.get("parent_id")
    ec_model, fk_column = _PD_TO_EC[pd_model_name]
    ec_model_name = ec_model.__name__
    ec_parent_id = _resolve_ec_parent_id_for_chi_block(
        anchor,
        ec_model_name=ec_model_name,
        anchor_parent_id=parent_id,
        fk_column=fk_column,
        years=years,
        ec_index=ec_index,
    )
    if ec_parent_id is None:
        return None

    year_values: list[str] = []
    year_tooltips: list[str] = []
    for year in years:
        ec_val = _chi_ec_consumption_mln_for_anchor(
            anchor,
            int(year),
            ec_index=ec_index,
            ec_model_name=ec_model_name,
            ec_parent_id=ec_parent_id,
            fk_column=fk_column,
            years=years,
            cz_hub_index=cz_hub_index,
            ees_sa_hub_index=ees_sa_hub_index,
        )
        if ec_val is None:
            year_values.append("—")
            year_tooltips.append("")
        else:
            year_values.append(_format_numeric(ec_val, rounding_digits))
            year_tooltips.append(_format_full_numeric_tooltip(ec_val))

    hist_ec = _chi_ec_consumption_mln_for_anchor(
        anchor,
        "hist",
        ec_index=ec_index,
        ec_model_name=ec_model_name,
        ec_parent_id=ec_parent_id,
        fk_column=fk_column,
        years=years,
        cz_hub_index=cz_hub_index,
        ees_sa_hub_index=ees_sa_hub_index,
    )
    if hist_ec is None:
        hist_value = "—"
        hist_tooltip = ""
    else:
        hist_value = _format_numeric(hist_ec, rounding_digits)
        hist_tooltip = _format_full_numeric_tooltip(hist_ec)

    new_row: dict[str, Any] = {
        "entity_label": anchor.get("entity_label"),
        "entity_rowspan": int(anchor.get("entity_rowspan") or len(block)) + 1,
        "entity_depth": anchor.get("entity_depth", 0),
        "entity_kind": anchor.get("entity_kind"),
        "show_entity_cell": False,
        "parameter_key": ENERGY_CONSUMPTION_MLN_KVT_CH_KEY,
        "parameter_label": ENERGY_CONSUMPTION_MLN_KVT_CH_LABEL,
        "demand_model_name": anchor.get("demand_model_name"),
        "parent_fk_column": anchor.get("parent_fk_column"),
        "parent_id": anchor.get("parent_id"),
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": hist_value,
        "year_values": year_values,
        "hist_numeric_tooltip": hist_tooltip,
        "year_numeric_tooltips": year_tooltips,
        "id_union_energy_system": anchor.get("id_union_energy_system"),
        "id_regional_energy_system": anchor.get("id_regional_energy_system"),
        "id_regional_district": anchor.get("id_regional_district"),
        "id_energy_unit": anchor.get("id_energy_unit"),
        "perimeter_variant_code": _chi_ec_consumption_pvc_for_anchor(anchor)
        or anchor.get("perimeter_variant_code"),
        "year_coeff_k_stored": [],
        "entity_note_text": anchor.get("entity_note_text") or "",
        "entity_note_row_id": anchor.get("entity_note_row_id"),
        "show_entity_note_cell": False,
        "pd_pd_ee_row": True,
    }
    if anchor.get("pd_pd_decentralized_zone_mark"):
        new_row["pd_pd_decentralized_zone_mark"] = True
    if anchor.get("pd_pd_skip_empty_hide_row"):
        new_row["pd_pd_skip_empty_hide_row"] = True
    if anchor.get("id_synchronous_area") is not None:
        new_row["id_synchronous_area"] = anchor.get("id_synchronous_area")
    if anchor.get("pd_pd_nt_extra_row"):
        new_row["pd_pd_nt_extra_row"] = True
    if anchor.get("pd_pd_territory_detail_row"):
        new_row["pd_pd_territory_detail_row"] = True
        new_row["pd_pd_territory_compact_hide_row"] = True
    elif anchor.get("pd_pd_territory_compact_hide_row"):
        new_row["pd_pd_territory_compact_hide_row"] = True
    if anchor.get("pd_pd_summary_table_only_row"):
        new_row["pd_pd_summary_table_only_row"] = True
    if anchor.get("perimeter_variant_from_year") is not None:
        new_row["perimeter_variant_from_year"] = anchor.get(
            "perimeter_variant_from_year"
        )
    if anchor.get("perimeter_variant_to_year") is not None:
        new_row["perimeter_variant_to_year"] = anchor.get("perimeter_variant_to_year")
    _copy_chi_territory_fields_from_anchor(new_row, anchor)
    return new_row


def inject_energy_consumption_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Добавляет строки потребления ЭЭ перед «Максимальное потребление мощности, МВт»."""
    if not summary_rows or not years:
        return

    blocks: list[tuple[int, int, list[dict[str, Any]]]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            span = int(row.get("entity_rowspan") or 1)
            block = summary_rows[i : i + span]
            dm = str(block[0].get("demand_model_name") or "")
            if dm in _OES_CHI_PD_MODELS and not any(
                str(r.get("parameter_key") or "") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY
                for r in block
            ):
                blocks.append((i, span, block))
            i += span
        else:
            i += 1

    if not blocks:
        return

    ec_index = _build_ec_consumption_index(years)
    cz_hub_index, ees_sa_hub_index = _hub_indexes_for_summary_blocks(
        blocks, years, rounding_digits
    )
    insertions: list[tuple[int, dict[str, Any], int, int]] = []
    for start, span, block in blocks:
        new_row = _build_energy_consumption_row_for_block(
            block,
            years,
            rounding_digits,
            ec_index=ec_index,
            cz_hub_index=cz_hub_index,
            ees_sa_hub_index=ees_sa_hub_index,
        )
        if new_row is None:
            continue
        insert_at = _insert_index_before_max_power(summary_rows, start, span)
        insertions.append((insert_at, new_row, start, span))

    for insert_at, new_row, start, span in reversed(insertions):
        if insert_at == start and summary_rows[start].get("show_entity_cell"):
            new_row["show_entity_cell"] = True
            if summary_rows[start].get("show_entity_note_cell"):
                new_row["show_entity_note_cell"] = True
                summary_rows[start]["show_entity_note_cell"] = False
            summary_rows[start]["show_entity_cell"] = False
        summary_rows.insert(insert_at, new_row)
        new_span = span + 1
        # После insert блок занимает [start, start+new_span) независимо от insert_at.
        for k in range(start, start + new_span):
            summary_rows[k]["entity_rowspan"] = new_span
