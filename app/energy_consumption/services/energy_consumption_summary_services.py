from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.common.perimeter_variant.constants import (
    CENTRALIZED_ZONE_AGGREGATE_NAME,
    legacy_nt_group_for_perimeter_code,
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITH_NT_WITH_GAES,
    EES_RUSSIA_AGGREGATE_NAME,
    EES_UNIFIED_REF_NAME,
    ENTITY_KIND_CENTRALIZED_ZONE,
    ENTITY_KIND_EES_RUSSIA,
    ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    ENTITY_KIND_RUSSIA_FEDERATION,
    RUSSIA_FEDERATION_AGGREGATE_NAME,
)
from app.common.perimeter_variant.registry import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    entity_perimeter_bindings,
    is_o1_perimeter_variant_code,
    model_supports_perimeter_variant,
    ordered_tree_variants_for_display,
    perimeter_variant_applies_to_year,
    perimeter_variant_definitions,
    perimeter_variant_year_bounds_for_code,
    perimeter_entity_context_for_model,
    perimeter_variant_display_label_for_entity,
    perimeter_variant_options_for_entity,
    perimeter_variant_options_for_ees_unified_summary_nt_group,
    is_ees_unified_energy_system_type_entity,
    resolve_entity_perimeter_binding,
    resolve_entity_perimeter_variants,
    resolve_catalog_o1_perimeter_variant_code,
)
from app.common.perimeter_variant.registry_types import EntityPerimeterBinding, PerimeterVariantDefinition
from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.help_services import (
    apply_thousand_grouping_to_display,
    format_decimal_for_display,
    format_decimal_trim_for_display,
)
from app.extensions import db
from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
    EesEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
    CentralizedZoneEnergyConsumptionParameter,
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
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
    SynchronousAreaEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
    RussiaFederationEnergyConsumptionParameter,
)
from app.energy_consumption.services.perimeter_variant_tree_rules import (
    SOUTH_FD_NAME_CF,
    SOUTH_CRIMEA_SEV_RES_BASE_LABEL_CF,
    MIDDLE_VOLGA_UES_NAME_CF,
    SOUTH_UES_NAME_CF,
    URAL_UES_NAME_CF,
    SOUTH_UES_VERIFICATION_EXCLUDE_CRIMEA_SEV_THROUGH_YEAR,
    TITES_EAST_UES_NAME_CF,
    TITES_SIBERIA_UES_NAME_CF,
    TITES_EAST_VERIFICATION_FROM_YEAR,
    south_ues_base_tree_includes_new_territories,
)
from app.energy_consumption.services import energy_consumption_parameter_services as dps
from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
)
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType


PLACEHOLDER_NAMES = {"не указано", "не указано2"}
_VERSION_CONTEXT_UNSET = object()

# Не показывать в сводке по ФО (экран и Excel).
_FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF = frozenset({"новые территории"})
_NEW_TERRITORIES_SUBJECTS_AGGREGATE_LABEL = "Новые территории"
_NT_UNDER_SOUTH_FORMULA_TOOLTIP = (
    "Потребление «Новые территории», млн кВт·ч = "
    "сумма потребления ЭЭ всех субъектов РФ, входящих в блок «Новые территории»"
)
_NEW_TERRITORIES_UES_NAME_TOKEN_CF = "новые территории"
_NEW_TERRITORIES_FD_NAME_CF = "новые территории"
_FIRST_SYNC_AREA_BASE_LABEL_CF = "первая синхронная зона"
_SECOND_SYNC_AREA_BASE_LABEL_CF = "вторая синхронная зона"
_KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF = "калининград"
_TITES_TYPE_LABEL_CF = "титэс"
_SAKHA_YAKUTIA_RES_NAME_MARKERS_CF = ("саха", "якутия")
_TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_CF = frozenset(
    {
        "западный энергорайон",
        "центральный энергорайон",
    }
)
_TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR = 2019
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_FORMULA_TOOLTIP = (
    "Потребление ЭЭС России без НТ с зарядом ГАЭС, млн кВт·ч = "
    "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) + "
    "Вторая синхронная зона + "
    "ТИТЭС"
)
_EES_RUSSIA_WITH_NT_WITH_GAES_FORMULA_TOOLTIP = (
    "Потребление ЭЭС России с НТ с зарядом ГАЭС, млн кВт·ч = "
    "Первая синхронная зона с НТ с зарядом ГАЭС + "
    "Вторая синхронная зона + "
    "Синхронная зона Калининградской области + "
    "ТИТЭС + "
    "потребление ЭЭ Новыми территориями"
)
_FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT = "with_nt_with_gaes_with_kaliningrad_es"
_FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT = (
    "with_nt_without_gaes_without_kaliningrad_es"
)
_FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_FORMULA_TOOLTIP = (
    "Потребление Первая синхронная зона с НТ с зарядом ГАЭС (с ЭС Калининградской области), "
    "млн кВт·ч = сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области) + "
    "заряд ГАЭС + "
    "потребление ЭЭ Новыми территориями"
)
_FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP = (
    "Потребление Первая синхронная зона с НТ без заряда ГАЭС (без ЭС Калининградской области), "
    "млн кВт·ч = "
    "Первая синхронная зона с НТ с зарядом ГАЭС (с ЭС Калининградской области) − "
    "заряд ГАЭС"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT = (
    "without_nt_with_gaes_without_kaliningrad_es"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP = (
    "Потребление Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области), "
    "млн кВт·ч = "
    "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области, ОЭС Юга и ОЭС Центра с зарядом ГАЭС), "
    "без ОЭС Востока и ОЭС «Новые территории» − "
    "потребление ЭС Калининградской области"
)
_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT = (
    "without_nt_without_gaes_with_kaliningrad_es"
)
_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_FORMULA_TOOLTIP = (
    "Потребление Первая синхронная зона без НТ без заряда ГАЭС (с ЭС Калининградской области), "
    "млн кВт·ч = "
    "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) − "
    "заряд ГАЭС"
)
_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT = (
    "without_nt_without_gaes_without_kaliningrad_es"
)
# Порядок строк «Первая синхронная зона» на сводной таблице при «+НТ» и «+заряд ГАЭС».
_FIRST_SA_VARIANT_DISPLAY_ORDER: dict[str, int] = {
    _FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT: 0,
    _FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT: 1,
    CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES: 2,
    _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT: 3,
    _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT: 4,
    _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT: 5,
}
_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP = (
    "Потребление Первая синхронная зона без НТ без заряда ГАЭС (без ЭС Калининградской области), "
    "млн кВт·ч = "
    "Первая синхронная зона без НТ с зарядом ГАЭС (без ЭС Калининградской области) − "
    "заряд ГАЭС"
)
_UES_EAST_NAME_CF = "оэс востока"
_KALININGRAD_ES_NAME_CF = "эс калининградской области"
_SECOND_SA_FROM_UES_EAST_FORMULA_TOOLTIP = (
    "Потребление Вторая синхронная зона, млн кВт·ч = ОЭС Востока"
)
_KALININGRAD_SA_FROM_ES_FORMULA_TOOLTIP = (
    "Потребление Синхронная зона Калининградской области, млн кВт·ч = "
    "ЭС Калининградской области"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL = (
    "Проверка первой синхронной зоны без НТ с зарядом ГАЭС "
    "(без ЭС Калининградской области)"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_TOOLTIP = (
    "Проверка = Первая синхронная зона без НТ с зарядом ГАЭС "
    "(без ЭС Калининградской области) − "
    "(сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области и ОЭС Юга с зарядом ГАЭС), "
    "без ОЭС Востока − потребление ЭС Калининградской области)"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL = (
    "Проверка первой синхронной зоны без НТ с зарядом ГАЭС "
    "(с ЭС Калининградской области)"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_TOOLTIP = (
    "Проверка = Первая синхронная зона без НТ с зарядом ГАЭС "
    "(с ЭС Калининградской области) − "
    "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области), без ОЭС Востока "
)
_EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL = (
    "Проверка ЕЭС России с НТ с зарядом ГАЭС"
)
_EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP = (
    "Проверка = ЕЭС России с НТ с зарядом ГАЭС − "
    "(Первая синхронная зона с НТ с зарядом ГАЭС + "
    "Вторая синхронная зона) − "
    "Синхронная зона Калининградской области"
)
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL = (
    "Проверка ЕЭС России без НТ с зарядом ГАЭС"
)
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP = (
    "Проверка = ЕЭС России без НТ с зарядом ГАЭС − "
    "Первая синхронная зона без НТ с зарядом ГАЭС (с ЭС Калининградской области) − "
    "Вторая синхронная зона − "
    "ТИТЭС"
)
# В режиме «СиПР» для этих строк «Проверка …» не показываем абсолютный прирост (СиПР).
_EC_SUMMARY_VERIFICATION_OMIT_SIPR_ABS_ENTITY_LABELS = frozenset(
    {
        _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        _FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        _EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
    }
)

_EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
    }
)


def _federal_district_excluded_from_summary(fd: FederalDistrict) -> bool:
    name = (getattr(fd, "name", None) or "").strip()
    cf = name.casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(prefix) :].strip()
            break
    return cf in _FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF

# Округление из URL влияет только на эти показатели; полная точность — в title/data-db-full.
_NUMERIC_ROUNDING_TOOLTIP_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_yoy_growth_pct",
        "energy_consumption_sipr_abs_growth_mln",
        "energy_consumption_sipr_yoy_growth_pct",
    }
)

ENERGY_CONSUMPTION_YOY_PARAMETER_KEY = "energy_consumption_yoy_growth_pct"
ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY = "energy_consumption_sipr_abs_growth_mln"
ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY = "energy_consumption_sipr_yoy_growth_pct"

# Годовой темп прироста, % — всегда с точностью до 5 знаков после запятой (независимо от rounding_digits в URL).
_ENERGY_CONSUMPTION_YOY_DISPLAY_DECIMALS = 2

GAES_CHARGE_PARAMETER_KEY = "gaes_charge_consumption_mln_kvt_ch"
GAES_CHARGE_PARAMETER_LABEL = "Потребление электрической энергии ГАЭС на заряд, млн кВт·ч"
_SUMMARY_ALWAYS_VISIBLE_PARAMETER_KEYS = frozenset({GAES_CHARGE_PARAMETER_KEY})
_SIPR_INTEGER_DISPLAY_PARAMETER_KEYS = frozenset(
    {
        "energy_consumption_sipr_mln_kvt_ch",
        ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        GAES_CHARGE_PARAMETER_KEY,
    }
)

_KALININGRAD_ES_LABEL_SUFFIX_WITH = " с ЭС Калининградской области"
_KALININGRAD_ES_LABEL_SUFFIX_WITHOUT = " без ЭС Калининградской области"
_KALININGRAD_ES_LABEL_SUFFIXES = (
    _KALININGRAD_ES_LABEL_SUFFIX_WITH,
    _KALININGRAD_ES_LABEL_SUFFIX_WITHOUT,
)
_NT_LABEL_SUFFIX_WITHOUT = " без НТ"
_NT_LABEL_SUFFIX_WITH = " с НТ"
_GAES_LABEL_SUFFIX_WITHOUT = " без заряда ГАЭС"
_GAES_LABEL_SUFFIX_WITH = " с зарядом ГАЭС"
_GAES_CHARGE_LABEL_SUFFIX = " (заряд ГАЭС)"
_GAES_PERIMETER_VARIANT_LABEL_WITH = _GAES_LABEL_SUFFIX_WITH.strip()
_GAES_PERIMETER_VARIANT_LABEL_WITHOUT = _GAES_LABEL_SUFFIX_WITHOUT.strip()
_SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL = "Заряд ГАЭС"
_SUMMARY_TABLE_VARIANT_LABEL_STRIP_SUFFIXES = (
    _GAES_CHARGE_LABEL_SUFFIX,
    _GAES_LABEL_SUFFIX_WITH,
    _GAES_LABEL_SUFFIX_WITHOUT,
    _NT_LABEL_SUFFIX_WITH,
    _NT_LABEL_SUFFIX_WITHOUT,
)

PARAMETERS_ENERGY_CONSUMPTION: tuple[tuple[str, str], ...] = (
    ("energy_consumption_mln_kvt_ch", "Потребление электрической энергии, млн кВт·ч"),
    ("energy_consumption_sipr_mln_kvt_ch", "Потребление электрической энергии (СиПР), млн кВт·ч"),
    (ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY, "Абсолютный прирост потребления электрической энергии (СиПР), млн кВт·ч"),
    (ENERGY_CONSUMPTION_YOY_PARAMETER_KEY, "Годовой темп прироста, %"),
    (ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY, "Годовой темп прироста (СиПР), %"),
)

_EC_SUMMARY_VERIFICATION_PARAMETERS: tuple[tuple[str, str], ...] = tuple(
    item
    for item in PARAMETERS_ENERGY_CONSUMPTION
    if "Годовой темп прироста" not in item[1]
)
_EC_SUMMARY_VERIFY_FOR_DISPLAY_DECIMALS = 6
# Строки «Проверка …» — 6 знаков (см. _format_verification_*); потребление млн кВт·ч — rounding_digits из URL;
# в режиме «СиПР» (кнопка) целые значения задаёт syncPdEcSummaryTableSiprIntegerDisplay в шаблоне.


def _display_digits_for_summary_parameter(parameter_key: str, rounding_digits: int) -> int:
    return rounding_digits


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "—":
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _effective_energy_consumption_sipr_raw(sipr: Any, ec: Any) -> Any:
    """Значение для строки «Потребление (СиПР)»: СиПР, иначе потребление, млн кВт·ч."""
    return sipr if sipr is not None else ec


def _effective_sipr_values_by_year(
    raw_ec: dict[int, Any],
    raw_sipr: dict[int, Any],
) -> dict[int, Any]:
    """Ряд СиПР по годам с подстановкой потребления, млн кВт·ч, где СиПР не задан."""
    out: dict[int, Any] = {}
    for sk in set(raw_ec.keys()) | set(raw_sipr.keys()):
        out[sk] = _effective_energy_consumption_sipr_raw(raw_sipr.get(sk), raw_ec.get(sk))
    return out


def _yoy_growth_pct_value(curr: Any, prev: Any) -> Any:
    """Текущий / прошлый × 100 − 100; иначе None."""
    c = _decimal_or_none(curr)
    p = _decimal_or_none(prev)
    if c is None or p is None or p == 0:
        return None
    return (c / p) * Decimal(100) - Decimal(100)


def _abs_diff_value(curr: Any, prev: Any) -> Any:
    """Текущий год минус прошлый; иначе None."""
    c = _decimal_or_none(curr)
    p = _decimal_or_none(prev)
    if c is None or p is None:
        return None
    return c - p


@dataclass(slots=True)
class _AggregatedYearDemandSlice:
    year_number: int
    energy_consumption_mln_kvt_ch: Any = None
    energy_consumption_sipr_mln_kvt_ch: Any = None


@dataclass(slots=True)
class SummaryEntity:
    label: str
    depth: int
    parameters: tuple[tuple[str, str], ...]
    demand_rows: list[Any]
    entity_kind: str = "default"
    children: list["SummaryEntity"] = field(default_factory=list)
    # Имя класса модели SQLAlchemy (whitelist в save_demand_summary_cell).
    demand_model_name: str | None = None
    # Для создания строки без существующего среза: колонка FK и id родителя (как в get_demand_rows).
    parent_fk_column: str | None = None
    parent_id: int | None = None
    # Справочные id для фильтров сводки (ветка ЕЭС / ФО / энергозоны).
    id_union_energy_system: int | None = None
    id_regional_energy_system: int | None = None
    id_regional_district: int | None = None
    id_energy_unit: int | None = None
    id_federal_district: int | None = None
    id_energy_zone: int | None = None
    id_synchronous_area: int | None = None
    perimeter_variant_code: str | None = None
    # Энергорайон децентрализованной зоны (РЭС «не указано» в справочнике).
    is_decentralized_zone_energy_unit: bool = False
    summary_ec_mln_display_divisor: int = 1


_EES_RUSSIA_DEMAND_MODEL_NAME = EesRussiaEnergyConsumptionParameter.__name__


def _is_ees_russia_without_nt_tree_root(e: SummaryEntity) -> bool:
    """Корень дерева ОЭС: агрегат «ЕЭС России … без НТ» (ветка ОЭС/СЗ/РЭС под ним)."""
    if int(e.depth or 0) != 0:
        return False
    if e.entity_kind not in (ENTITY_KIND_EES_RUSSIA, "group-root"):
        return False
    if not e.children:
        return False
    if e.demand_model_name == _EES_RUSSIA_DEMAND_MODEL_NAME:
        return e.perimeter_variant_code in (None, CODE_WITHOUT_NT)
    if e.demand_model_name == EnergySystemTypeEnergyConsumptionParameter.__name__:
        label_cf = (e.label or "").strip().casefold()
        return (
            label_cf == EES_UNIFIED_REF_NAME.casefold()
            and e.perimeter_variant_code in (None, CODE_WITHOUT_NT)
        )
    return False


def _synchronous_area_display_label(sa: SynchronousArea) -> str:
    return (getattr(sa, "name", None) or "").strip()


def _shift_summary_entity_depth(e: SummaryEntity, delta: int) -> SummaryEntity:
    d = int(e.depth) if e.depth is not None else 0
    new_d = max(0, d + delta)
    new_children = [_shift_summary_entity_depth(c, delta) for c in e.children]
    return replace(e, depth=new_d, children=new_children)


def _oes_promote_subjects_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по субъекту — под «ЕЭС России (без НТ)» только субъекты (без уровней ОЭС и РЭС)."""
    if not f_rd:
        return entities
    ues_dn = UnionEnergySystemEnergyConsumptionParameter.__name__
    rd_dn = RegionalDistrictEnergyConsumptionParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if not _is_ees_russia_without_nt_tree_root(e):
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            if child.demand_model_name != ues_dn:
                promoted.append(child)
                continue
            for res in child.children:
                for sub in res.children:
                    if sub.demand_model_name != rd_dn:
                        continue
                    rid = sub.id_regional_district
                    if rid is None or rid not in f_rd:
                        continue
                    promoted.append(_shift_summary_entity_depth(sub, -2))
        out.append(replace(e, children=promoted))
    return out


def _oes_promote_energy_units_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_eu: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по энергоузлу — под «ЕЭС России (без НТ)» только энергоузлы (без ОЭС, РЭС, субъекта)."""
    if not f_eu:
        return entities
    eu_dn = EnergyUnitEnergyConsumptionParameter.__name__

    def walk_collect(node: SummaryEntity, promoted: list[SummaryEntity]) -> None:
        if node.demand_model_name == eu_dn:
            euid = node.id_energy_unit
            if euid is not None and euid in f_eu:
                d = int(node.depth) if node.depth is not None else 0
                delta = -(d - 1) if d > 1 else 0
                promoted.append(_shift_summary_entity_depth(node, delta))
                return
        for c in node.children:
            walk_collect(c, promoted)

    out: list[SummaryEntity] = []
    for e in entities:
        if not _is_ees_russia_without_nt_tree_root(e):
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            walk_collect(child, promoted)
        out.append(replace(e, children=promoted))
    return out


def _oes_promote_res_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по РЭС — только строки РЭС (без ОЭС, субъектов и энергоузлов)."""
    if not f_res:
        return entities
    ues_dn = UnionEnergySystemEnergyConsumptionParameter.__name__
    res_dn = RegionalEnergySystemEnergyConsumptionParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if not _is_ees_russia_without_nt_tree_root(e):
            out.append(e)
            continue
        promoted: list[SummaryEntity] = []
        for child in e.children:
            if child.entity_kind == "synchronous_area":
                continue
            if child.demand_model_name != ues_dn:
                continue
            for res in child.children:
                if res.demand_model_name != res_dn:
                    continue
                rid = res.id_regional_energy_system
                if rid is None or rid not in f_res:
                    continue
                d = int(res.depth) if res.depth is not None else 0
                delta = -(d - 1) if d > 1 else 0
                promoted.append(replace(_shift_summary_entity_depth(res, delta), children=[]))
        out.append(replace(e, children=promoted))
    return out


def _build_perimeter_aggregate_entities(
    *,
    entity_kind: str,
    entity_name: str,
    demand_model: Any,
    russia_country_summary_ec_divisor: int = 1,
    entity_kind_attr: str | None = None,
    display_label: str | None = None,
    all_bound_variants: bool = False,
    perimeter_variant_codes: tuple[str, ...] | None = None,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Строки агрегата (Россия / ЕЭС России) по привязкам вариантов периметра в БД."""
    binding = resolve_entity_perimeter_variants(entity_kind, entity_name)
    divisor = int(russia_country_summary_ec_divisor or 1)
    row_entity_kind = entity_kind_attr or entity_kind
    label = display_label or entity_name

    def _top_entity(vcode: str) -> SummaryEntity:
        return replace(
            _standalone_entity(
                label,
                demand_model,
                PARAMETERS_ENERGY_CONSUMPTION,
                entity_kind=row_entity_kind,
                perimeter_variant_code=vcode,
            ),
            summary_ec_mln_display_divisor=divisor,
        )

    if binding is None or not binding.variants:
        return []
    out = [
        _top_entity(vdef.code)
        for vdef in _perimeter_variants_for_entity_binding(
            binding,
            tree_years,
            all_bound_variants=all_bound_variants,
        )
    ]
    if perimeter_variant_codes is not None:
        allowed_order = {
            str(code): idx for idx, code in enumerate(perimeter_variant_codes)
        }
        out = [
            entity
            for entity in out
            if str(entity.perimeter_variant_code or "") in allowed_order
        ]
        out.sort(
            key=lambda entity: allowed_order[str(entity.perimeter_variant_code or "")]
        )
    if out:
        return _order_variants_with_gaes_charge_rows(
            out,
            _gaes_charge_marker_entity(out[0]),
        )
    return []


_DEMAND_MODEL_CLASS_BY_NAME: dict[str, type] = {
    UnionEnergySystemEnergyConsumptionParameter.__name__: UnionEnergySystemEnergyConsumptionParameter,
    RegionalEnergySystemEnergyConsumptionParameter.__name__: RegionalEnergySystemEnergyConsumptionParameter,
    SynchronousAreaEnergyConsumptionParameter.__name__: SynchronousAreaEnergyConsumptionParameter,
    FederalDistrictEnergyConsumptionParameter.__name__: FederalDistrictEnergyConsumptionParameter,
    CentralizedZoneEnergyConsumptionParameter.__name__: CentralizedZoneEnergyConsumptionParameter,
    RussiaFederationEnergyConsumptionParameter.__name__: RussiaFederationEnergyConsumptionParameter,
    EesRussiaEnergyConsumptionParameter.__name__: EesRussiaEnergyConsumptionParameter,
    EnergySystemTypeEnergyConsumptionParameter.__name__: EnergySystemTypeEnergyConsumptionParameter,
    RegionalDistrictEnergyConsumptionParameter.__name__: RegionalDistrictEnergyConsumptionParameter,
    EnergyUnitEnergyConsumptionParameter.__name__: EnergyUnitEnergyConsumptionParameter,
    EnergyZoneEnergyConsumptionParameter.__name__: EnergyZoneEnergyConsumptionParameter,
}


def _perimeter_variants_for_entity_binding(
    binding: EntityPerimeterBinding,
    tree_years: list[int] | None,
    *,
    all_bound_variants: bool = False,
) -> tuple[PerimeterVariantDefinition, ...]:
    """Варианты для строк сводной таблицы: все привязки сущности (``all_bound_variants``),
    иначе только варианты дерева (без блоков «с/без заряда ГАЭС»)."""
    variants = binding.variants if all_bound_variants else ordered_tree_variants_for_display(binding)
    if not tree_years:
        return variants
    return tuple(
        v
        for v in variants
        if any(perimeter_variant_applies_to_year(v, int(y)) for y in tree_years)
    )


def _split_variants_around_gaes_charge_rows(
    entities: list[SummaryEntity],
) -> tuple[list[SummaryEntity], list[SummaryEntity]]:
    """Варианты «с зарядом ГАЭС» идут до строк заряда, «без заряда ГАЭС» — после."""
    before: list[SummaryEntity] = []
    after: list[SummaryEntity] = []
    for entity in entities:
        code = str(entity.perimeter_variant_code or "")
        if "without_gaes" in code:
            after.append(entity)
        else:
            before.append(entity)
    return before, after


def _normalize_perimeter_variant_code(code: object) -> str:
    return str(code or "").strip().casefold().replace("о1", "o1")


def _nt_group_for_variant_code(code: str) -> str:
    normalized = _normalize_perimeter_variant_code(code)
    # Исторически коды вариантов были вида with_nt / without_nt (и o1_*),
    # но в справочнике могут встречаться префиксные/составные коды вроде
    # "<entity>_with_nt" / "<entity>_without_nt". Для UI-переключателя «+ НТ»
    # важно корректно определить группу НТ независимо от позиции токена.
    if "without_nt" in normalized or "o1_without_nt" in normalized:
        return "without_nt"
    if "with_nt" in normalized or "o1_with_nt" in normalized:
        return "with_nt"
    return "other"


def _kaliningrad_group_for_variant_code(code: str) -> str:
    if "with_kaliningrad_es" in code:
        return "with_kaliningrad_es"
    if "without_kaliningrad_es" in code:
        return "without_kaliningrad_es"
    return "other"


def _has_gaes_variant_codes(entities: list[SummaryEntity]) -> bool:
    return any("with_gaes" in str(e.perimeter_variant_code or "") or "without_gaes" in str(e.perimeter_variant_code or "") for e in entities)


def _has_kaliningrad_variant_entities(entities: list[SummaryEntity]) -> bool:
    return any(
        _kaliningrad_group_for_variant_code(str(e.perimeter_variant_code or ""))
        != "other"
        for e in entities
    )


def _order_first_sa_kaliningrad_variant_entities(
    variant_entities: list[SummaryEntity],
    charge_marker: SummaryEntity | None,
) -> list[SummaryEntity]:
    """Первая СЗ: сначала варианты с НТ, затем без НТ; внутри без НТ — с зарядом ГАЭС, потом без."""
    sorted_entities = sorted(
        variant_entities,
        key=lambda entity: _FIRST_SA_VARIANT_DISPLAY_ORDER.get(
            str(entity.perimeter_variant_code or ""), 999
        ),
    )
    if charge_marker is None:
        return sorted_entities

    result: list[SummaryEntity] = []
    saw_with_gaes_for: set[tuple[str, str]] = set()
    inserted_charge_for: set[tuple[str, str]] = set()
    for entity in sorted_entities:
        code = str(entity.perimeter_variant_code or "")
        group_key = (
            _nt_group_for_variant_code(code),
            _kaliningrad_group_for_variant_code(code),
        )
        if "with_gaes" in code and "without_gaes" not in code:
            saw_with_gaes_for.add(group_key)
        elif (
            "without_gaes" in code
            and group_key in saw_with_gaes_for
            and group_key not in inserted_charge_for
        ):
            result.append(charge_marker)
            inserted_charge_for.add(group_key)
        result.append(entity)
    return result


def _is_ees_unified_energy_system_type(
    binding_entity_kind: str,
    binding_entity_name: str | None,
    entity: SummaryEntity,
) -> bool:
    if binding_entity_kind != ENTITY_KIND_ENERGY_SYSTEM_TYPE:
        return False
    name = (binding_entity_name or entity.label or "").strip()
    return name.casefold() == EES_UNIFIED_REF_NAME.casefold()


def _filter_ees_unified_summary_variants(
    variants: tuple[PerimeterVariantDefinition, ...],
) -> tuple[PerimeterVariantDefinition, ...]:
    """У «ЭЭС России» с вариантами ГАЭС plain with_nt/without_nt заменяются строками EesRussia*."""
    if not any(
        "with_gaes" in v.code or "without_gaes" in v.code for v in variants
    ):
        return variants
    return tuple(v for v in variants if v.code not in {CODE_WITH_NT, CODE_WITHOUT_NT})


def _ees_unified_gaes_variant_uses_ees_russia_aggregate(variant_code: str) -> bool:
    """Варианты ГАЭС для «ЕЭС России» хранятся в ``EnergySystemType*``, не в ``EesRussia*``."""
    del variant_code
    return False


def _binding_has_gaes_perimeter_variants(
    binding: EntityPerimeterBinding | None,
) -> bool:
    if binding is None or not binding.variants:
        return False
    return any(
        "with_gaes" in v.code or "without_gaes" in v.code for v in binding.variants
    )


def _resolve_ees_unified_summary_perimeter_binding(
    *,
    energy_system_type_binding: EntityPerimeterBinding | None,
    ees_russia_binding: EntityPerimeterBinding | None,
    use_ees_russia_gaes_variants: bool,
) -> EntityPerimeterBinding | None:
    """Привязки вариантов для строки «ЕЭС России» (тип энергосистемы) в сводке."""
    if use_ees_russia_gaes_variants:
        if _binding_has_gaes_perimeter_variants(energy_system_type_binding):
            return energy_system_type_binding
        if _binding_has_gaes_perimeter_variants(ees_russia_binding):
            return ees_russia_binding
        return energy_system_type_binding
    if energy_system_type_binding is not None:
        return energy_system_type_binding
    return ees_russia_binding


def _gaes_charge_marker_entity(entity: SummaryEntity) -> SummaryEntity:
    return replace(
        entity,
        parameters=tuple(),
        demand_rows=[],
        children=[],
        perimeter_variant_code=None,
    )


def _variant_o1_after_base_sort_key(entity: SummaryEntity) -> int:
    """Базовый вариант (with_nt / without_nt) перед парным О-1 (o1_with_nt / o1_without_nt)."""
    return 1 if is_o1_perimeter_variant_code(entity.perimeter_variant_code) else 0


def _order_variants_by_nt_groups_with_o1_after_base(
    variant_entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    """with_nt, o1_with_nt, without_nt, o1_without_nt — для агрегатов без вариантов ГАЭС (ЦЗ России)."""
    result: list[SummaryEntity] = []
    for nt_group in ("with_nt", "without_nt", "other"):
        grouped = [
            e
            for e in variant_entities
            if _nt_group_for_variant_code(str(e.perimeter_variant_code or "")) == nt_group
        ]
        if not grouped:
            continue
        grouped.sort(key=_variant_o1_after_base_sort_key)
        result.extend(grouped)
    return result


def _children_marker_entity(entity: SummaryEntity) -> SummaryEntity:
    return replace(
        entity,
        parameters=tuple(),
        demand_rows=[],
        children=list(entity.children),
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        perimeter_variant_code=None,
    )


def _order_variants_with_gaes_charge_rows(
    variant_entities: list[SummaryEntity],
    charge_marker: SummaryEntity | None,
) -> list[SummaryEntity]:
    if not variant_entities:
        return [charge_marker] if charge_marker is not None else []
    if charge_marker is None:
        return list(variant_entities)
    if not _has_gaes_variant_codes(variant_entities):
        ordered = _order_variants_by_nt_groups_with_o1_after_base(variant_entities)
        result: list[SummaryEntity] = []
        charge_inserted = False
        for nt_group in ("with_nt", "without_nt", "other"):
            grouped = [
                e
                for e in ordered
                if _nt_group_for_variant_code(str(e.perimeter_variant_code or "")) == nt_group
            ]
            if not grouped:
                continue
            result.extend(grouped)
            if (
                charge_marker is not None
                and nt_group == "with_nt"
                and not charge_inserted
            ):
                result.append(charge_marker)
                charge_inserted = True
        if charge_marker is not None and not charge_inserted:
            result.append(charge_marker)
        return result

    if _has_kaliningrad_variant_entities(variant_entities):
        return _order_first_sa_kaliningrad_variant_entities(
            variant_entities,
            charge_marker,
        )

    result: list[SummaryEntity] = []
    for nt_group in ("with_nt", "without_nt", "other"):
        nt_grouped = [
            e
            for e in variant_entities
            if _nt_group_for_variant_code(str(e.perimeter_variant_code or "")) == nt_group
        ]
        if not nt_grouped:
            continue
        for kaliningrad_group in (
            "with_kaliningrad_es",
            "without_kaliningrad_es",
            "other",
        ):
            grouped = [
                e
                for e in nt_grouped
                if _kaliningrad_group_for_variant_code(str(e.perimeter_variant_code or ""))
                == kaliningrad_group
            ]
            if not grouped:
                continue
            with_gaes_variants = [
                e
                for e in grouped
                if "with_gaes" in str(e.perimeter_variant_code or "")
                and "without_gaes" not in str(e.perimeter_variant_code or "")
            ]
            plain_variants = [
                e
                for e in grouped
                if "without_gaes" not in str(e.perimeter_variant_code or "")
                and "with_gaes" not in str(e.perimeter_variant_code or "")
            ]
            without_gaes_variants = [
                e
                for e in grouped
                if "without_gaes" in str(e.perimeter_variant_code or "")
            ]
            with_gaes_variants.sort(key=_variant_o1_after_base_sort_key)
            plain_variants.sort(key=_variant_o1_after_base_sort_key)
            without_gaes_variants.sort(key=_variant_o1_after_base_sort_key)
            result.extend(with_gaes_variants)
            if with_gaes_variants and charge_marker is not None:
                result.append(charge_marker)
            elif without_gaes_variants and charge_marker is not None:
                result.append(charge_marker)
            result.extend(without_gaes_variants)
            result.extend(plain_variants)
    return result


_SOUTH_UES_SUMMARY_EXPAND_GAES_VARIANT_CODES: tuple[str, ...] = (
    CODE_WITH_NT_WITH_GAES,
    CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
)

_SOUTH_UES_GAES_VARIANT_LABEL_SUFFIX: dict[str, str] = {
    CODE_WITH_NT_WITH_GAES: "с НТ с зарядом ГАЭС",
    CODE_WITH_NT_WITHOUT_GAES: "с НТ без заряда ГАЭС",
    CODE_WITHOUT_NT_WITH_GAES: "без НТ с зарядом ГАЭС",
    CODE_WITHOUT_NT_WITHOUT_GAES: "без НТ без заряда ГАЭС",
}


def _is_south_union_energy_system_perimeter_binding(
    binding_entity_kind: str,
    binding_entity_name: str | None,
) -> bool:
    return (
        str(binding_entity_kind or "") == "union_energy_system"
        and (binding_entity_name or "").strip().casefold() == SOUTH_UES_NAME_CF
    )


def _south_ues_summary_expand_perimeter_variants(
    tree_years: list[int] | None,
) -> tuple[PerimeterVariantDefinition, ...]:
    """Варианты «с/без заряда ГАЭС» для /summary_table/ и /summary/oes/ (не в дереве БД)."""
    catalog = perimeter_variant_definitions()
    out: list[PerimeterVariantDefinition] = []
    for code in _SOUTH_UES_SUMMARY_EXPAND_GAES_VARIANT_CODES:
        vdef = catalog.get(code)
        if vdef is None:
            suffix = _SOUTH_UES_GAES_VARIANT_LABEL_SUFFIX.get(code, code)
            vdef = PerimeterVariantDefinition(code, suffix)
        if tree_years and not any(
            perimeter_variant_applies_to_year(vdef, int(y)) for y in tree_years
        ):
            continue
        out.append(vdef)
    return tuple(out)


_O1_SUBJECT_EXPAND_DEMAND_MODELS = frozenset(
    {
        RegionalEnergySystemEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
    }
)


def _binding_has_o1_perimeter_variant(binding: EntityPerimeterBinding | None) -> bool:
    if binding is None:
        return False
    return any(
        is_o1_perimeter_variant_code(getattr(v, "code", None))
        for v in getattr(binding, "variants", ())
    )


def _o1_perimeter_variant_code_from_binding(binding: EntityPerimeterBinding) -> str:
    for vdef in getattr(binding, "variants", ()):
        code = getattr(vdef, "code", None)
        if is_o1_perimeter_variant_code(code):
            return str(code)
    return resolve_catalog_o1_perimeter_variant_code()


def _expand_summary_entity_o1_subject_perimeter_variants(
    entity: SummaryEntity,
) -> list[SummaryEntity]:
    """РЭС/субъект с O-1 на /perimeter_variants/: строка O-1 сразу перед базовой (без O-1)."""
    expanded_children: list[SummaryEntity] = []
    for child in entity.children:
        expanded_children.extend(
            _expand_summary_entity_o1_subject_perimeter_variants(child)
        )
    base_entity = replace(entity, children=expanded_children)

    if base_entity.perimeter_variant_code is not None:
        return [base_entity]
    if base_entity.demand_model_name not in _O1_SUBJECT_EXPAND_DEMAND_MODELS:
        return [base_entity]
    if base_entity.parent_fk_column is None or base_entity.parent_id is None:
        return [base_entity]

    ctx = perimeter_entity_context_for_model(
        str(base_entity.demand_model_name),
        parent_fk_column=base_entity.parent_fk_column,
        parent_id=base_entity.parent_id,
    )
    if ctx is None:
        return [base_entity]
    pe_kind, pe_name = ctx
    binding = resolve_entity_perimeter_binding(pe_kind, pe_name)
    if not _binding_has_o1_perimeter_variant(binding):
        return [base_entity]

    o1_code = _o1_perimeter_variant_code_from_binding(binding)  # type: ignore[arg-type]
    model_cls = _DEMAND_MODEL_CLASS_BY_NAME.get(base_entity.demand_model_name or "")
    if model_cls is None:
        return [base_entity]

    o1_entity = replace(
        base_entity,
        perimeter_variant_code=o1_code,
        demand_rows=dps.get_demand_rows(
            model_cls,
            base_entity.parent_fk_column,
            base_entity.parent_id,
            perimeter_variant_code=o1_code,
        ),
        children=[],
    )
    return [o1_entity, base_entity]


def _expand_summary_entities_o1_subject_perimeter_variants(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for entity in entities:
        out.extend(_expand_summary_entity_o1_subject_perimeter_variants(entity))
    return out


def _expand_summary_entity_perimeter_variants(
    entity: SummaryEntity,
    *,
    binding_entity_kind: str,
    expand: bool,
    tree_years: list[int] | None = None,
    binding_entity_name: str | None = None,
    use_ees_russia_gaes_variants: bool = False,
) -> list[SummaryEntity]:
    """Дублирует только строку сущности по вариантам периметра, не её дочернюю ветку."""
    if not expand:
        return [entity]
    binding = resolve_entity_perimeter_binding(
        binding_entity_kind,
        binding_entity_name or entity.label,
    )
    ees_russia_binding = None
    ees_unified_type = _is_ees_unified_energy_system_type(
        binding_entity_kind,
        binding_entity_name,
        entity,
    )
    if ees_unified_type:
        ees_russia_binding = resolve_entity_perimeter_binding(
            ENTITY_KIND_EES_RUSSIA,
            EES_RUSSIA_AGGREGATE_NAME,
        )
        binding = _resolve_ees_unified_summary_perimeter_binding(
            energy_system_type_binding=binding,
            ees_russia_binding=ees_russia_binding,
            use_ees_russia_gaes_variants=use_ees_russia_gaes_variants,
        )
    if binding is None:
        return [entity]
    variants = _perimeter_variants_for_entity_binding(
        binding,
        tree_years,
        all_bound_variants=expand,
    )
    if _is_south_union_energy_system_perimeter_binding(
        binding_entity_kind,
        binding_entity_name,
    ):
        variants = _south_ues_summary_expand_perimeter_variants(tree_years)
    if _is_ees_unified_energy_system_type(
        binding_entity_kind,
        binding_entity_name,
        entity,
    ):
        variants = _filter_ees_unified_summary_variants(variants)
    if not variants:
        return [entity]
    model_cls = _DEMAND_MODEL_CLASS_BY_NAME.get(entity.demand_model_name or "")
    if model_cls is None:
        return [entity]
    if entity.parent_fk_column is None or entity.parent_id is None:
        return [entity]

    ees_unified_type = _is_ees_unified_energy_system_type(
        binding_entity_kind,
        binding_entity_name,
        entity,
    )
    out: list[SummaryEntity] = []
    for vdef in variants:
        if ees_unified_type and _ees_unified_gaes_variant_uses_ees_russia_aggregate(vdef.code):
            demand_model = EesRussiaEnergyConsumptionParameter
            demand_fk_column: str | None = None
            demand_parent_id: int | None = None
        else:
            demand_model = model_cls
            demand_fk_column = entity.parent_fk_column
            demand_parent_id = entity.parent_id
        demand_rows = dps.get_demand_rows(
            demand_model,
            demand_fk_column,
            demand_parent_id,
            perimeter_variant_code=vdef.code,
        )
        out.append(
            replace(
                entity,
                label=entity.label,
                perimeter_variant_code=vdef.code,
                demand_rows=demand_rows,
                children=[],
                entity_kind="perimeter_variant" if len(variants) > 1 else entity.entity_kind,
                demand_model_name=demand_model.__name__,
                parent_fk_column=demand_fk_column,
                parent_id=demand_parent_id,
            )
        )
    result = _order_variants_with_gaes_charge_rows(out, _gaes_charge_marker_entity(entity))
    if entity.children:
        result.append(_children_marker_entity(entity))
    return result


def _build_oes_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
    include_russia_top_row: bool = True,
    include_ees_russia_rows: bool = True,
    include_synchronous_area_rows: bool = True,
    ees_top_from_db: bool = False,
    russia_country_summary_ec_divisor: int = 1,
    expand_south_ues_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Полное дерево сводки по ОЭС без территориальных фильтров (для объединения выборов и «без фильтра»)."""
    entities: list[SummaryEntity] = []

    if include_russia_top_row:
        if ees_top_from_db:
            entities.extend(
                _build_perimeter_aggregate_entities(
                    entity_kind=ENTITY_KIND_RUSSIA_FEDERATION,
                    entity_name=RUSSIA_FEDERATION_AGGREGATE_NAME,
                    demand_model=RussiaFederationEnergyConsumptionParameter,
                    russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
                    display_label=RUSSIA_FEDERATION_AGGREGATE_NAME,
                )
            )
        else:
            entities.extend(
                [
                    _standalone_entity(
                        "Россия (с НТ)",
                        RussiaFederationEnergyConsumptionParameter,
                        PARAMETERS_ENERGY_CONSUMPTION,
                        entity_kind="oes_top_aggregate",
                        perimeter_variant_code=CODE_WITH_NT,
                    ),
                    _standalone_entity(
                        "Россия (без НТ)",
                        RussiaFederationEnergyConsumptionParameter,
                        PARAMETERS_ENERGY_CONSUMPTION,
                        entity_kind="oes_top_aggregate",
                        perimeter_variant_code=CODE_WITHOUT_NT,
                    ),
                ]
            )

    if not ees_top_from_db:
        entities.append(
            _standalone_entity(
                "ЭЭС",
                EesEnergyConsumptionParameter,
                PARAMETERS_ENERGY_CONSUMPTION,
                entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
            )
        )

    if not include_ees_russia_rows:
        if include_synchronous_area_rows:
            entities.extend(
                _build_synchronous_area_entities(
                    depth=0,
                    expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
                    tree_years=tree_years,
                )
            )
        entities.extend(
            _build_energy_system_type_entities(
                EES_UNIFIED_REF_NAME,
                _is_ees_branch,
                depth=0,
                always_show_subject_row_under_res=always_show_subject_row_under_res,
                expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
                tree_years=tree_years,
            )
        )
        entities.extend(
            _build_energy_system_type_entities(
                "ТИТЭС",
                _is_tites_branch,
                depth=0,
                always_show_subject_row_under_res=always_show_subject_row_under_res,
                expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
                tree_years=tree_years,
            )
        )
        return entities

    ees_russia_perimeter = (
        _build_perimeter_aggregate_entities(
            entity_kind=ENTITY_KIND_EES_RUSSIA,
            entity_name=EES_RUSSIA_AGGREGATE_NAME,
            demand_model=EesRussiaEnergyConsumptionParameter,
            russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
            display_label="ЭЭС",
        )
        if ees_top_from_db
        else []
    )
    ees_without_nt: SummaryEntity | None = None
    if ees_top_from_db:
        for ent in ees_russia_perimeter:
            if ent.perimeter_variant_code == CODE_WITH_NT:
                entities.append(ent)
            elif ent.perimeter_variant_code == CODE_WITHOUT_NT:
                ees_without_nt = replace(ent, entity_kind=ENTITY_KIND_EES_RUSSIA, depth=0)
    else:
        entities.append(
            _standalone_entity(
                "ЭЭС",
                EesRussiaEnergyConsumptionParameter,
                PARAMETERS_ENERGY_CONSUMPTION,
                entity_kind=ENTITY_KIND_EES_RUSSIA,
                perimeter_variant_code=CODE_WITH_NT,
            )
        )
        ees_without_nt = _standalone_entity(
            "ЭЭС",
            EesRussiaEnergyConsumptionParameter,
            PARAMETERS_ENERGY_CONSUMPTION,
            entity_kind=ENTITY_KIND_EES_RUSSIA,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )

    if ees_without_nt is None:
        ees_without_nt = SummaryEntity(
            label="ЭЭС",
            depth=0,
            parameters=tuple(),
            demand_rows=[],
            entity_kind=ENTITY_KIND_EES_RUSSIA,
            demand_model_name=None,
            parent_fk_column=None,
            parent_id=None,
        )

    sa_children = (
        _build_synchronous_area_entities(
            depth=1,
            expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
            tree_years=tree_years,
        )
        if include_synchronous_area_rows
        else []
    )
    type_children = _build_energy_system_type_entities(
        EES_UNIFIED_REF_NAME,
        _is_ees_branch,
        depth=1,
        always_show_subject_row_under_res=always_show_subject_row_under_res,
        expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
        tree_years=tree_years,
    ) + _build_energy_system_type_entities(
        "ТИТЭС",
        _is_tites_branch,
        depth=1,
        always_show_subject_row_under_res=always_show_subject_row_under_res,
        expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
        tree_years=tree_years,
    )

    ees_without_nt.children = sa_children + type_children
    entities.append(ees_without_nt)
    return entities


def _build_oes_summary_table_union_energy_system_entities(
    *,
    always_show_subject_row_under_res: bool = False,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """ОЭС ветки ЕЭС на глубине 0 (как на /power_demand/summary/oes/), с зарядом ГАЭС между вариантами."""
    return [
        _shift_summary_entity_depth(entity, -1)
        for entity in _build_ues_entities_filtered(
            _is_ees_branch,
            always_show_subject_row_under_res=always_show_subject_row_under_res,
            expand_entity_perimeter_variants=expand_entity_perimeter_variants,
            tree_years=tree_years,
        )
    ]


def _build_summary_table_top_aggregate_entities(
    *,
    always_show_subject_row_under_res: bool = False,
    include_russia_top_row: bool = True,
    include_ees_russia_rows: bool = True,
    include_synchronous_area_rows: bool = True,
    russia_federation_first: bool = True,
    russia_country_summary_ec_divisor: int = 1,
    expand_south_ues_perimeter_variants: bool = False,
    ees_unified_use_ees_russia_gaes_variants: bool = True,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Общий верх сводной таблицы: Россия → ЦЗ → ЭЭС → ЕЭС → синхронные зоны.

    Без блоков ОЭС/ТИТЭС и без уровней ФО/энергозон — используется на /summary/oes/,
    /summary/federal_districts/ и /summary/energy_zones/ в режиме «Сводная таблица».
    """
    entities: list[SummaryEntity] = []
    aggregate_kwargs = dict(
        russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
        all_bound_variants=True,
        tree_years=tree_years,
    )
    russia_entities: list[SummaryEntity] = []
    if include_russia_top_row:
        russia_entities = _build_perimeter_aggregate_entities(
            entity_kind=ENTITY_KIND_RUSSIA_FEDERATION,
            entity_name=RUSSIA_FEDERATION_AGGREGATE_NAME,
            demand_model=RussiaFederationEnergyConsumptionParameter,
            display_label=RUSSIA_FEDERATION_AGGREGATE_NAME,
            perimeter_variant_codes=(CODE_WITH_NT,),
            **aggregate_kwargs,
        )
    if russia_federation_first and russia_entities:
        entities.extend(russia_entities)

    entities.extend(
        _build_perimeter_aggregate_entities(
            entity_kind=ENTITY_KIND_CENTRALIZED_ZONE,
            entity_name=CENTRALIZED_ZONE_AGGREGATE_NAME,
            demand_model=CentralizedZoneEnergyConsumptionParameter,
            display_label=CENTRALIZED_ZONE_AGGREGATE_NAME,
            **aggregate_kwargs,
        )
    )
    if include_russia_top_row and not russia_federation_first:
        entities.extend(russia_entities)
    if include_ees_russia_rows:
        entities.extend(
            _build_perimeter_aggregate_entities(
                entity_kind=ENTITY_KIND_EES_RUSSIA,
                entity_name=EES_RUSSIA_AGGREGATE_NAME,
                demand_model=EesRussiaEnergyConsumptionParameter,
                display_label=EES_RUSSIA_AGGREGATE_NAME,
                **aggregate_kwargs,
            )
        )

    # ЕЭС России — только варианты периметра (+ заряд ГАЭС), без дочерних ОЭС.
    entities.extend(
        _build_energy_system_type_entities(
            EES_UNIFIED_REF_NAME,
            lambda _ues: False,
            depth=0,
            always_show_subject_row_under_res=always_show_subject_row_under_res,
            expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
            ees_unified_use_ees_russia_gaes_variants=ees_unified_use_ees_russia_gaes_variants,
            tree_years=tree_years,
        )
    )

    if include_synchronous_area_rows:
        entities.extend(
            _build_synchronous_area_entities(
                depth=0,
                expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
                tree_years=tree_years,
            )
        )
    return entities


def _build_oes_summary_table_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
    include_russia_top_row: bool = True,
    include_ees_russia_rows: bool = True,
    include_synchronous_area_rows: bool = True,
    russia_federation_first: bool = False,
    russia_country_summary_ec_divisor: int = 1,
    expand_south_ues_perimeter_variants: bool = False,
    ees_unified_use_ees_russia_gaes_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Плоский верхний порядок как на /power_demand/summary/oes/.

    По умолчанию: ЦЗ России → (опц. Россия) → ЭЭС → ЕЭС (без вложенных ОЭС) →
    синхронные зоны → ОЭС → ТИТЭС.
    При ``russia_federation_first``: Россия → ЦЗ → …
    """
    entities = _build_summary_table_top_aggregate_entities(
        always_show_subject_row_under_res=always_show_subject_row_under_res,
        include_russia_top_row=include_russia_top_row,
        include_ees_russia_rows=include_ees_russia_rows,
        include_synchronous_area_rows=include_synchronous_area_rows,
        russia_federation_first=russia_federation_first,
        russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
        expand_south_ues_perimeter_variants=expand_south_ues_perimeter_variants,
        ees_unified_use_ees_russia_gaes_variants=ees_unified_use_ees_russia_gaes_variants,
        tree_years=tree_years,
    )
    entities.extend(
        _build_oes_summary_table_union_energy_system_entities(
            always_show_subject_row_under_res=always_show_subject_row_under_res,
            expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
            tree_years=tree_years,
        )
    )
    tites_entities = _build_energy_system_type_entities(
        "ТИТЭС",
        _is_tites_branch,
        depth=0,
        always_show_subject_row_under_res=always_show_subject_row_under_res,
        expand_entity_perimeter_variants=expand_south_ues_perimeter_variants,
        tree_years=tree_years,
    )
    entities.extend(
        replace(
            entity,
            children=_unwrap_hidden_tites_ues_entities(entity.children),
        )
        for entity in tites_entities
    )
    return entities


def _strip_oes_ees_russia_nt_parent_aggregate(entities: list[SummaryEntity]) -> list[SummaryEntity]:
    """Убирает строки-показатели у агрегата «ЕЭС России (без НТ)» при территориальном фильтре."""
    out: list[SummaryEntity] = []
    for e in entities:
        if _is_ees_russia_without_nt_tree_root(e):
            out.append(
                replace(
                    e,
                    parameters=tuple(),
                    demand_rows=[],
                    demand_model_name=None,
                    parent_fk_column=None,
                    parent_id=None,
                )
            )
        else:
            out.append(e)
    return out


def _effective_data_year_bounds(
    start_year: int,
    end_year: int,
    data_start_year: int | None,
    data_end_year: int | None,
) -> tuple[int, int]:
    if data_start_year is not None and data_end_year is not None:
        return data_start_year, data_end_year
    return start_year, end_year


def build_oes_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
    include_ees_russia_rows: bool = True,
    include_synchronous_area_rows: bool = True,
    include_russia_top_row: bool = True,
    ees_top_from_db: bool = False,
    russia_country_summary_ec_divisor: int = 1,
    include_oes_summary_table_sync_sa_ees_verification: bool = False,
    expand_south_ues_perimeter_variants: bool = False,
    summary_table_top_order: bool = False,
    ees_unified_use_ees_russia_gaes_variants: bool = False,
    russia_federation_first: bool = False,
) -> dict[str, Any]:
    """Сводка по ОЭС (GET ds_ues, ds_res, ds_rd, ds_eu).

    Набор строк показателей по каждой сущности не урезается территориальными фильтрами; скрытие
    отдельных параметров — только через модальное окно «Наименование параметров» (и ``visible_rows`` при выгрузке).

    При сочетании фильтров нижний уровень сужается **отдельно в каждой ветке родителя** (как на
    сводках по ФО и энергозонам): например, выбранные субъекты РФ относятся только к одной ОЭС —
    под остальными выбранными ОЭС показываются все РЭС/субъекты/энергорайоны этой ветки; то же
    для РЭС ↔ субъектов и субъектов ↔ энергорайонов.

    Ровно один id: для одной РЭС, одного субъекта или одного энергорайона — прежнее поднятие
    строки под «ЕЭС России (без НТ)»; для одной ОЭС — полное поддерево (РЭС и ниже).
    """
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    years = list(range(dsy, dey + 1))
    oes_raw_kwargs = dict(
        include_russia_top_row=include_russia_top_row,
        include_ees_russia_rows=include_ees_russia_rows,
        include_synchronous_area_rows=include_synchronous_area_rows,
        ees_top_from_db=ees_top_from_db,
        russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
        expand_south_ues_perimeter_variants=expand_south_ues_perimeter_variants,
        tree_years=years,
    )
    _ = include_oes_summary_table_sync_sa_ees_verification
    ues_l, res_l, rd_l, eu_l = ([], [], [], [])
    if oes_territory_ordered is not None:
        ues_l, res_l, rd_l, eu_l = oes_territory_ordered

    has_territory_selection = bool(ues_l or res_l or rd_l or eu_l)

    if has_territory_selection:
        base_entities = copy.deepcopy(
            _build_oes_raw_entities(
                always_show_subject_row_under_res=bool(rd_l),
                **oes_raw_kwargs,
            )
        )
        base_entities = _strip_oes_ees_russia_nt_parent_aggregate(base_entities)
        f_ues = frozenset(ues_l)
        f_res = frozenset(res_l)
        f_rd = frozenset(rd_l)
        f_eu = frozenset(eu_l)
        ent = prune_summary_entities_oes(base_entities, f_ues, f_res, f_rd, f_eu, frozenset())
        total_ids = len(ues_l) + len(res_l) + len(rd_l) + len(eu_l)
        # Только ОЭС в URL — полное поддерево (РЭС → субъект → энергорайон), без «поднятия» одной строки ОЭС.
        if total_ids == 1:
            if eu_l:
                ent = _oes_promote_energy_units_only_under_ees_russia(ent, f_eu)
            elif rd_l:
                ent = _oes_promote_subjects_only_under_ees_russia(ent, f_rd)
            elif res_l:
                ent = _oes_promote_res_only_under_ees_russia(ent, f_res)
        ent = _expand_summary_entities_o1_subject_perimeter_variants(ent)
        summary_rows = _flatten_entities(
            ent, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        )
        ctx = _build_summary_context(
            entities=[],
            page_title="Потребление электрической энергии по энергосистемам",
            active_summary="oes",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        tag_energy_consumption_summary_rows_perimeter_variant_labels(summary_rows)
        apply_chukotka_chersky_reference_summary_rows(
            summary_rows, years, rounding_digits
        )
        ctx["summary_rows"] = summary_rows
        return ctx

    if summary_table_top_order:
        entities = _build_oes_summary_table_raw_entities(
            always_show_subject_row_under_res=False,
            include_russia_top_row=include_russia_top_row,
            include_ees_russia_rows=include_ees_russia_rows,
            include_synchronous_area_rows=include_synchronous_area_rows,
            russia_federation_first=russia_federation_first,
            russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
            expand_south_ues_perimeter_variants=expand_south_ues_perimeter_variants,
            ees_unified_use_ees_russia_gaes_variants=ees_unified_use_ees_russia_gaes_variants,
            tree_years=years,
        )
    else:
        entities = _build_oes_raw_entities(
            always_show_subject_row_under_res=False,
            **oes_raw_kwargs,
        )
    entities = _expand_summary_entities_o1_subject_perimeter_variants(entities)
    ctx = _build_summary_context(
        entities=entities,
        page_title="Потребление электрической энергии по энергосистемам",
        active_summary="oes",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        hidden_demand_model_names=frozenset(),
    )
    apply_chukotka_chersky_reference_summary_rows(
        ctx["summary_rows"],
        years=list(ctx.get("years") or years),
        rounding_digits=rounding_digits,
    )
    return ctx


def build_federal_district_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    fo_filter_sets: tuple[frozenset[int], frozenset[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
    expand_entity_perimeter_variants: bool = False,
) -> dict[str, Any]:
    """Сводка по ФО и РЭС (GET ds_fd, ds_res).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — ЦЗ и полное дерево по всем ФО со всеми РЭС, входящими в округ.

    Только ``ds_fd`` — каждая выбранная строка ФО и **все** РЭС этих округов.

    ``ds_fd`` + ``ds_res`` — строка по каждому выбранному ФО; РЭС сужаются **отдельно по
    каждому округу**: если в ``ds_res`` есть РЭС этого ФО — показываются только они, если
    все отмеченные РЭС из других ФО — под данным ФО выводятся **все** его РЭС.

    Только ``ds_res`` (без ``ds_fd``) — плоский список строк по РЭС без уровня ФО (как в Excel).
    """
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    tree_years = list(range(dsy, dey + 1))
    if expand_entity_perimeter_variants:
        # Как на /summary/oes/: Россия → ЦЗ → ЭЭС → ЕЭС → СЗ, затем ФО.
        entities = _build_summary_table_top_aggregate_entities(
            russia_federation_first=True,
            include_russia_top_row=True,
            include_ees_russia_rows=True,
            include_synchronous_area_rows=True,
            expand_south_ues_perimeter_variants=True,
            ees_unified_use_ees_russia_gaes_variants=True,
            tree_years=tree_years,
        )
    else:
        entities = [
            _standalone_entity(
                "Централизованная зона",
                CentralizedZoneEnergyConsumptionParameter,
                PARAMETERS_ENERGY_CONSUMPTION,
                entity_kind="centralized_zone",
            ),
        ]
    entities.extend(
        _build_federal_district_entities(
            expand_entity_perimeter_variants=expand_entity_perimeter_variants,
            tree_years=tree_years,
        )
    )

    if fo_filter_sets is not None:
        f_fd, f_res = fo_filter_sets
        if f_fd or f_res:
            entities = prune_summary_entities_fo(entities, f_fd, f_res)

    entities = _expand_summary_entities_o1_subject_perimeter_variants(entities)
    ctx = _build_summary_context(
        entities=entities,
        page_title="Потребление электрической энергии по ФО",
        active_summary="fo",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    apply_chukotka_chersky_reference_summary_rows(
        ctx["summary_rows"],
        years=list(ctx.get("years") or tree_years),
        rounding_digits=rounding_digits,
    )
    return ctx


def _build_ez_raw_entities(
    *,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    if expand_entity_perimeter_variants:
        # Как на /summary/oes/: Россия → ЦЗ → ЭЭС → ЕЭС → СЗ, затем энергозоны.
        entities = _build_summary_table_top_aggregate_entities(
            russia_federation_first=True,
            include_russia_top_row=True,
            include_ees_russia_rows=True,
            include_synchronous_area_rows=True,
            expand_south_ues_perimeter_variants=True,
            ees_unified_use_ees_russia_gaes_variants=True,
            tree_years=tree_years,
        )
    else:
        entities = [
            _standalone_entity(
                "Централизованная зона",
                CentralizedZoneEnergyConsumptionParameter,
                PARAMETERS_ENERGY_CONSUMPTION,
                entity_kind="centralized_zone",
            ),
        ]
    entities.extend(_build_energy_zone_entities())
    return entities


def build_energy_zones_summary_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    ez_territory_ordered: tuple[list[int], list[int]] | None = None,
    avg_temp_uses_global_rounding: bool = False,
    expand_entity_perimeter_variants: bool = False,
) -> dict[str, Any]:
    """Сводка по энергозонам (GET ds_ez, ds_res).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — ЦЗ и полное дерево энергозона → РЭС → …

    Только ``ds_ez`` — выбранные зоны со всеми РЭС внутри.

    ``ds_ez`` + ``ds_res`` — каждая выбранная зона; РЭС сужаются **по зоне**: если в ``ds_res``
    есть РЭС из этой зоны — только они, иначе все РЭС зоны (как на сводке по ФО).

    Только ``ds_res`` (без ``ds_ez``) — плоский список по выбранным РЭС без строки энергозоны.
    """
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    years = list(range(dsy, dey + 1))
    ez_l: list[int] = []
    res_l: list[int] = []
    if ez_territory_ordered is not None:
        ez_l, res_l = ez_territory_ordered

    ez_raw_kwargs = dict(
        expand_entity_perimeter_variants=expand_entity_perimeter_variants,
        tree_years=years,
    )
    if ez_l or res_l:
        base_entities = copy.deepcopy(_build_ez_raw_entities(**ez_raw_kwargs))
        f_ez = frozenset(ez_l)
        f_res = frozenset(res_l)
        ent = prune_summary_entities_ez(base_entities, f_ez, f_res)
        if _ez_res_only_flat_mode(f_ez, f_res):
            ent = _flatten_energy_zone_parents_when_res_filtered(ent)
        summary_rows = _flatten_entities(
            ent, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        )
        inject_siberia_energy_zone_summary_rows(summary_rows, years, rounding_digits)
        inject_east_energy_zone_summary_rows(
            summary_rows,
            years,
            rounding_digits,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        apply_chukotka_chersky_reference_summary_rows(
            summary_rows, years, rounding_digits
        )
        ctx = _build_summary_context(
            entities=[],
            page_title="Потребление электрической энергии по энергозонам",
            active_summary="ez",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        tag_energy_consumption_summary_rows_perimeter_variant_labels(summary_rows)
        ctx["summary_rows"] = summary_rows
        return ctx

    entities = _build_ez_raw_entities(**ez_raw_kwargs)
    ctx = _build_summary_context(
        entities=entities,
        page_title="Потребление электрической энергии по энергозонам",
        active_summary="ez",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    inject_siberia_energy_zone_summary_rows(
        ctx["summary_rows"],
        years=list(ctx.get("years") or years),
        rounding_digits=rounding_digits,
    )
    inject_east_energy_zone_summary_rows(
        ctx["summary_rows"],
        years=list(ctx.get("years") or years),
        rounding_digits=rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    apply_chukotka_chersky_reference_summary_rows(
        ctx["summary_rows"],
        years=list(ctx.get("years") or years),
        rounding_digits=rounding_digits,
    )
    return ctx


_EAST_ENERGY_ZONE_LABEL = "Энергозона Востока"
_EAST_ENERGY_ZONE_FORMULA_TOOLTIP = (
    "Энергозона Востока = ЭС Амурской области + ЭС Приморского края + "
    "ЭС Хабаровского края и Еврейской АО + ЭС Республики Саха (Якутия) + "
    "Западный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
    "Центральный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
    "ЭС Камчатского края (О-1) + ЭС Чукотского АО (О-1) + "
    "ЭС Сахалинской области (О-1) + ЭС Магаданской области (О-1) + "
    "Изолированый энергорайон Республики Саха (Якутия) (О-1) + "
    "Николаевский энергорайон Хабаровского края (О-1)"
)
_EAST_ENERGY_ZONE_FORMULA_SOURCE_BASE_LABELS: tuple[str, ...] = (
    "ЭС Амурской области",
    "ЭС Приморского края",
    "ЭС Хабаровского края и Еврейской АО",
    "ЭС Республики Саха (Якутия)",
    "Западный энергорайон ЭС Республики Саха (Якутия)",
    "Центральный энергорайон ЭС Республики Саха (Якутия)",
    "ЭС Камчатского края",
    "ЭС Чукотского АО",
    "ЭС Сахалинской области",
    "ЭС Магаданской области",
    "Изолированый энергорайон Республики Саха (Якутия)",
    "Николаевский энергорайон Хабаровского края",
)
_EAST_ENERGY_ZONE_FORMULA_O1_SOURCE_BASE_LABELS_CF = frozenset(
    label.casefold()
    for label in _EAST_ENERGY_ZONE_FORMULA_SOURCE_BASE_LABELS[6:]
)
_EAST_ENERGY_ZONE_SAKHA_ENERGY_DISTRICTS_FORMULA_THROUGH_YEAR = 2018
_EAST_ENERGY_ZONE_SAKHA_ENERGY_DISTRICTS_FORMULA_LABELS_CF = frozenset(
    label.casefold()
    for label in (
        "Западный энергорайон ЭС Республики Саха (Якутия)",
        "Центральный энергорайон ЭС Республики Саха (Якутия)",
    )
)
_EAST_ENERGY_ZONE_FORMULA_LABEL_ALIASES_CF: dict[str, frozenset[str]] = {
    "западный энергорайон эс республики саха (якутия)": frozenset(
        {
            "западный энергорайон эс республики саха (якутия)",
            "западный энергорайон",
        }
    ),
    "центральный энергорайон эс республики саха (якутия)": frozenset(
        {
            "центральный энергорайон эс республики саха (якутия)",
            "центральный энергорайон",
        }
    ),
}
# В конце блока «Энергозона Востока» (после РЭС ТИТЭС Востока), только вариант О-1.
_EAST_ENERGY_ZONE_EXTRA_ENERGY_UNIT_NAME_MARKER_GROUPS_CF: tuple[frozenset[str], ...] = (
    frozenset({"изолирован", "саха", "якутия"}),
    frozenset({"николаевск", "хабаровск"}),
)
_EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_LABEL = f"Проверка для {_EAST_ENERGY_ZONE_LABEL}"
_EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_TOOLTIP = (
    "Энергозона Востока = Энергозона Востока − ЭС Камчатского края О-1 − "
    "ЭС Магаданской области О-1 − ЭС Сахалинской области О-1 − "
    "ЭС Чукотского АО О-1 − "
    "Изолированый энергорайон Республики Саха (Якутия) О-1 − "
    "Николаевский энергорайон Хабаровского края О-1 + "
    "ЭС Амурской области + ЭС Приморского края + "
    "ЭС Хабаровского края и Еврейской АО + ЭС Республики Саха (Якутия) + "
    "Западный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно) + "
    "Центральный энергорайон ЭС Республики Саха (Якутия) (до 2018 года включительно)"
)


def _summary_rows_block_end_index(
    summary_rows: list[dict[str, Any]],
    entity_label: str,
) -> int | None:
    for index, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if str(row.get("entity_label") or "").strip() != entity_label:
            continue
        return index + max(int(row.get("entity_rowspan") or 1), 1)
    return None


def _east_energy_zone_o1_perimeter_variant_code() -> str:
    return resolve_catalog_o1_perimeter_variant_code()


def _east_energy_zone_summary_block_slice(
    summary_rows: list[dict[str, Any]],
) -> slice | None:
    """Индексы строк блока «Энергозона Востока» (включая дочерние ЭС и энергорайоны)."""
    start: int | None = None
    for index, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        label = str(row.get("entity_label") or "").strip()
        if label == _EAST_ENERGY_ZONE_LABEL:
            start = index
            continue
        if start is not None and row.get("entity_depth", 0) == 0:
            return slice(start, index)
    if start is not None:
        return slice(start, len(summary_rows))
    return None


def _apply_east_energy_zone_parent_formula_tooltip(row: dict[str, Any]) -> None:
    if row.get("parameter_key") in (
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
    ):
        row["pd_ec_summary_row_formula_tooltip"] = _EAST_ENERGY_ZONE_FORMULA_TOOLTIP
    if row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch":
        row["pd_ec_sipr_integer_display_row"] = True


def _mark_energy_zone_footer_parent_o1_visibility(row: dict[str, Any]) -> None:
    """«Энергозона Сибири/Востока»: бейдж О-1; видимость — «Сводная таблица» + «Форма О-1»."""
    row["pd_ec_o1_form_row"] = True
    if row.get("show_entity_cell"):
        row["pd_ec_show_o1_badge"] = True
    else:
        row.pop("pd_ec_show_o1_badge", None)


def _finalize_east_energy_zone_summary_block_rows(
    block_rows: list[dict[str, Any]],
) -> None:
    """Строка-итог «Энергозона Востока» — О-1 (Сводная + Форма О-1); дочерние — только О-1."""
    o1_code = _east_energy_zone_o1_perimeter_variant_code()
    for row in block_rows:
        row["pd_ec_skip_empty_hide_row"] = True
        label = str(row.get("entity_label") or "").strip()
        if label == _EAST_ENERGY_ZONE_LABEL:
            _apply_east_energy_zone_parent_formula_tooltip(row)
        elif row.get("parameter_key") in (
            "energy_consumption_mln_kvt_ch",
            "energy_consumption_sipr_mln_kvt_ch",
        ):
            row.pop("pd_ec_summary_row_formula_tooltip", None)
        if label != _EAST_ENERGY_ZONE_LABEL:
            continue
        if row.get("entity_kind") == "formula":
            row["perimeter_variant_code"] = None
            _mark_energy_zone_footer_parent_o1_visibility(row)
        else:
            row["perimeter_variant_code"] = o1_code
            if row.get("show_entity_cell"):
                row["pd_ec_o1_form_row"] = True


def _filter_east_energy_zone_summary_rows_to_o1(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Оставляет в блоке «Энергозона Востока» только строки варианта О-1."""
    block = _east_energy_zone_summary_block_slice(summary_rows)
    if block is None:
        return
    block_rows = summary_rows[block]
    kept: list[dict[str, Any]] = []
    for row in block_rows:
        code = row.get("perimeter_variant_code")
        if code is not None and not is_o1_perimeter_variant_code(code):
            continue
        kept.append(row)
    _finalize_east_energy_zone_summary_block_rows(kept)
    summary_rows[block] = kept
    tag_energy_consumption_summary_rows_perimeter_variant_labels(kept)
    _finalize_east_energy_zone_summary_block_rows(kept)


def _is_tites_east_union_energy_system(ues: UnionEnergySystem) -> bool:
    name_cf = (getattr(ues, "name", None) or "").strip().casefold().replace(" ", "")
    return name_cf == TITES_EAST_UES_NAME_CF.replace(" ", "")


def _load_east_energy_zone_extra_energy_units() -> list[EnergyUnit]:
    """Энергорайоны в конце блока «Энергозона Востока» (вне дерева РЭС ТИТЭС Востока)."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    matched: dict[frozenset[str], EnergyUnit] = {}
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        name_cf = str(getattr(energy_unit, "name", None) or "").strip().casefold()
        if not name_cf:
            continue
        for markers in _EAST_ENERGY_ZONE_EXTRA_ENERGY_UNIT_NAME_MARKER_GROUPS_CF:
            if markers in matched:
                continue
            if all(marker in name_cf for marker in markers):
                matched[markers] = energy_unit
                break
    return [
        matched[markers]
        for markers in _EAST_ENERGY_ZONE_EXTRA_ENERGY_UNIT_NAME_MARKER_GROUPS_CF
        if markers in matched
    ]


def _build_east_energy_zone_extra_energy_unit_entities() -> list[SummaryEntity]:
    o1_code = _east_energy_zone_o1_perimeter_variant_code()
    return _build_energy_unit_entities(
        _load_east_energy_zone_extra_energy_units(),
        depth=1,
        perimeter_variant_code=o1_code,
    )


def _build_tites_regional_energy_system_entities_for_east_energy_zone() -> list[SummaryEntity]:
    """РЭС ветки «ТИТЭС Востока» с энергорайонами под «Энергозона Востока» (без строк ОЭС ТИТЭС)."""
    o1_code = _east_energy_zone_o1_perimeter_variant_code()
    query = UnionEnergySystem.query.options(
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.regional_districts
        ).selectinload(
            RegionalDistrict.energy_units
        ),
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.energy_units
        ),
    )
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    query = query.order_by(
        UnionEnergySystem.display_order.asc().nullslast(),
        UnionEnergySystem.name.asc(),
        UnionEnergySystem.id.asc(),
    )

    children: list[SummaryEntity] = []
    for ues in query.all():
        if not _is_valid_named_item(ues) or not _is_tites_east_union_energy_system(ues):
            continue
        for res in sorted(ues.regional_energy_systems, key=_sort_by_name):
            if not _is_valid_named_item(res):
                continue
            res_entity = _build_regional_energy_system_entity(
                res,
                ues_id=int(ues.id),
                always_show_subject_row_under_res=False,
                perimeter_variant_code=o1_code,
            )
            children.append(_shift_summary_entity_depth(res_entity, -1))
    _extend_east_energy_zone_block_children_with_extra_energy_units(children)
    return children


def _iter_summary_entity_energy_unit_descendants(
    entity: SummaryEntity,
) -> list[SummaryEntity]:
    if entity.demand_model_name == EnergyUnitEnergyConsumptionParameter.__name__:
        return [entity]
    out: list[SummaryEntity] = []
    for child in entity.children:
        out.extend(_iter_summary_entity_energy_unit_descendants(child))
    return out


def _east_energy_zone_formula_row_label_aliases_cf(base_label: str) -> frozenset[str]:
    base_cf = base_label.casefold()
    return _EAST_ENERGY_ZONE_FORMULA_LABEL_ALIASES_CF.get(base_cf, frozenset({base_cf}))


def _pick_east_energy_zone_formula_component_row(
    summary_rows: list[dict[str, Any]],
    base_label: str,
    parameter_key: str,
    *,
    require_o1: bool = False,
) -> dict[str, Any] | None:
    label_aliases_cf = _east_energy_zone_formula_row_label_aliases_cf(base_label)
    best: dict[str, Any] | None = None
    o1_row: dict[str, Any] | None = None
    for row in summary_rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL:
            continue
        if _summary_row_base_label_cf(row) not in label_aliases_cf:
            continue
        code = row.get("perimeter_variant_code")
        if require_o1:
            if is_o1_perimeter_variant_code(code):
                return row
            continue
        if is_o1_perimeter_variant_code(code):
            o1_row = row
            continue
        if code in (None, ""):
            return row
        best = best or row
    if require_o1:
        return o1_row
    return best or o1_row


def _east_energy_zone_formula_component_year_values(
    component_row: dict[str, Any],
    years: list[int],
    base_label: str,
) -> dict[int, Decimal | None]:
    values = _raw_year_values_from_summary_row(component_row, years)
    if base_label.casefold() not in _EAST_ENERGY_ZONE_SAKHA_ENERGY_DISTRICTS_FORMULA_LABELS_CF:
        return values
    through_year = _EAST_ENERGY_ZONE_SAKHA_ENERGY_DISTRICTS_FORMULA_THROUGH_YEAR
    return {
        int(year): values.get(int(year)) if int(year) <= through_year else None
        for year in years
    }


def _sum_east_energy_zone_formula_from_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    """Сумма по слагаемым формулы «Энергозона Востока» по всей сводке (не только блоку О-1)."""
    parts: list[dict[int, Decimal | None]] = []
    for base_label in _EAST_ENERGY_ZONE_FORMULA_SOURCE_BASE_LABELS:
        require_o1 = base_label.casefold() in _EAST_ENERGY_ZONE_FORMULA_O1_SOURCE_BASE_LABELS_CF
        component_row = _pick_east_energy_zone_formula_component_row(
            summary_rows,
            base_label,
            parameter_key,
            require_o1=require_o1,
        )
        if component_row is not None:
            parts.append(
                _east_energy_zone_formula_component_year_values(
                    component_row,
                    years,
                    base_label,
                )
            )
    return _sum_year_value_dicts(years, *parts)


def _extend_east_energy_zone_block_children_with_extra_energy_units(
    children: list[SummaryEntity],
) -> None:
    seen_eu_ids = {
        eu_entity.id_energy_unit
        for res_child in children
        for eu_entity in _iter_summary_entity_energy_unit_descendants(res_child)
        if eu_entity.id_energy_unit is not None
    }
    for extra_entity in _build_east_energy_zone_extra_energy_unit_entities():
        euid = extra_entity.id_energy_unit
        if euid is not None and euid in seen_eu_ids:
            continue
        children.append(extra_entity)
        if euid is not None:
            seen_eu_ids.add(euid)


def inject_east_energy_zone_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> None:
    """Добавляет «Энергозона Востока» после «Энергозона Сибири» с ЭС ТИТЭС и энергорайонами."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL
        for row in summary_rows
    ):
        return

    tites_children = _build_tites_regional_energy_system_entities_for_east_energy_zone()
    if not tites_children:
        return

    o1_code = _east_energy_zone_o1_perimeter_variant_code()

    parent_entity = SummaryEntity(
        label=_EAST_ENERGY_ZONE_LABEL,
        depth=0,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="formula",
        children=tites_children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        perimeter_variant_code=None,
    )
    new_rows = _flatten_entity(
        parent_entity,
        years,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    tag_energy_consumption_summary_rows_perimeter_variant_labels(new_rows)

    insert_at = _summary_rows_block_end_index(summary_rows, "Энергозона Сибири")
    if insert_at is None:
        insert_at = len(summary_rows)
    summary_rows[insert_at:insert_at] = new_rows

    series_ec = _sum_east_energy_zone_formula_from_summary_rows(
        summary_rows,
        years,
        "energy_consumption_mln_kvt_ch",
    )
    if _year_values_have_any_numeric(series_ec):
        target_ec = next(
            row
            for row in summary_rows
            if row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
            and str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL
        )
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            series_ec,
            parameter_key="energy_consumption_mln_kvt_ch",
            rounding_digits=rounding_digits,
        )

    series_sipr = _sum_east_energy_zone_formula_from_summary_rows(
        summary_rows,
        years,
        "energy_consumption_sipr_mln_kvt_ch",
    )
    if _year_values_have_any_numeric(series_sipr):
        target_sipr = next(
            row
            for row in summary_rows
            if row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
            and str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL
        )
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            series_sipr,
            parameter_key="energy_consumption_sipr_mln_kvt_ch",
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _filter_east_energy_zone_summary_rows_to_o1(summary_rows)
    east_block = _east_energy_zone_summary_block_slice(summary_rows)
    if east_block is not None:
        for row in summary_rows[east_block]:
            if str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL:
                _apply_east_energy_zone_parent_formula_tooltip(row)


def _pick_energy_zone_formula_source_row(
    summary_rows: list[dict[str, Any]],
    label: str,
    parameter_key: str,
    *,
    prefer_o1: bool = False,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    o1_row: dict[str, Any] | None = None
    for row in summary_rows:
        if row.get("parameter_key") != parameter_key:
            continue
        ent = str(row.get("entity_label") or "")
        if label not in ent:
            continue
        code = row.get("perimeter_variant_code")
        if prefer_o1 and is_o1_perimeter_variant_code(code):
            o1_row = row
            continue
        if code in (None, ""):
            if not prefer_o1:
                return row
            best = best or row
            continue
        best = best or row
    if prefer_o1 and o1_row is not None:
        return o1_row
    return best


def _year_values_from_union_energy_system(
    ues_id: int | None,
    years: list[int],
    attr: str,
    *,
    perimeter_variant_code: str | None = None,
) -> dict[int, Decimal | None]:
    if ues_id is None:
        return {int(year): None for year in years}
    demand_rows = dps.get_demand_rows(
        UnionEnergySystemEnergyConsumptionParameter,
        "id_union_energy_system",
        int(ues_id),
        perimeter_variant_code=perimeter_variant_code,
    )
    out: dict[int, Decimal | None] = {int(year): None for year in years}
    for demand_row in demand_rows:
        year_number = getattr(demand_row, "year_number", None)
        if year_number is None:
            continue
        year_key = int(year_number)
        if year_key not in out:
            continue
        out[year_key] = _decimal_or_none(getattr(demand_row, attr, None))
    return out


def _sum_energy_zone_year_value_series(
    years: list[int],
    first: dict[int, Decimal | None],
    second: dict[int, Decimal | None],
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for year in years:
        first_value = first.get(int(year))
        second_value = second.get(int(year))
        if first_value is None and second_value is None:
            out[int(year)] = None
        else:
            out[int(year)] = (first_value or Decimal(0)) + (second_value or Decimal(0))
    return out


def inject_siberia_energy_zone_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Добавляет расчётную строку «Энергозона Сибири» = «ОЭС Сибири» + «ТИТЭС Сибири» в конец списка.

    Расчёт выполняется по данным, которые уже попали на страницу (с учётом фильтров).
    """
    if not summary_rows or not years:
        return

    # Не дублировать при повторных применениях (напр. в summary_table пайплайне).
    if any(str(r.get("entity_label") or "").strip() == "Энергозона Сибири" for r in summary_rows):
        return

    oes_row_ec = _pick_energy_zone_formula_source_row(
        summary_rows, "ОЭС Сибири", "energy_consumption_mln_kvt_ch"
    )
    tites_row_ec = _pick_energy_zone_formula_source_row(
        summary_rows, "ТИТЭС Сибири", "energy_consumption_mln_kvt_ch"
    )
    oes_row_sipr = _pick_energy_zone_formula_source_row(
        summary_rows, "ОЭС Сибири", "energy_consumption_sipr_mln_kvt_ch"
    )
    tites_row_sipr = _pick_energy_zone_formula_source_row(
        summary_rows, "ТИТЭС Сибири", "energy_consumption_sipr_mln_kvt_ch"
    )

    # На странице сводки по энергозонам строк «ОЭС Сибири»/«ТИТЭС Сибири» может не быть,
    # поэтому подстрахуемся загрузкой данных напрямую из БД по именам ОЭС.
    oes_id = _resolve_union_energy_system_id_by_name_cf("оэс сибири")
    tites_id = _resolve_union_energy_system_id_by_name_cf("титэс сибири")

    oes_direct_ec = _year_values_from_union_energy_system(
        oes_id, years, "energy_consumption_mln_kvt_ch"
    )
    tites_direct_ec = _year_values_from_union_energy_system(
        tites_id, years, "energy_consumption_mln_kvt_ch"
    )
    oes_direct_sipr = _year_values_from_union_energy_system(
        oes_id, years, "energy_consumption_sipr_mln_kvt_ch"
    )
    tites_direct_sipr = _year_values_from_union_energy_system(
        tites_id, years, "energy_consumption_sipr_mln_kvt_ch"
    )

    has_any_source = (
        (oes_row_ec and tites_row_ec)
        or (oes_row_sipr and tites_row_sipr)
        or _year_values_have_any_numeric(oes_direct_ec)
        or _year_values_have_any_numeric(tites_direct_ec)
        or _year_values_have_any_numeric(oes_direct_sipr)
        or _year_values_have_any_numeric(tites_direct_sipr)
    )
    if not has_any_source:
        return

    template_row = (
        oes_row_ec
        or tites_row_ec
        or oes_row_sipr
        or tites_row_sipr
        or (summary_rows[0] if summary_rows else None)
    )
    if template_row is None:
        return

    entity_label = "Энергозона Сибири"
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    formula_tooltip = "Энергозона Сибири = ОЭС Сибири + ТИТЭС Сибири"

    new_block: list[dict[str, Any]] = []
    for idx, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        r = dict(template_row)
        r.update(
            {
                "entity_label": entity_label,
                "entity_rowspan": entity_rowspan,
                "entity_depth": 0,
                "entity_kind": "formula",
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "year_row_ids": [None for _ in years],
                "hist_row_id": None,
                "hist_value": "—",
                "year_values": ["—" for _ in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": ["" for _ in years],
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": idx == 0,
                "perimeter_variant_code": None,
            }
        )
        if parameter_key in ("energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch"):
            r["pd_ec_summary_row_formula_tooltip"] = formula_tooltip
        new_block.append(r)

    if oes_row_ec and tites_row_ec:
        oes_ec = _raw_year_values_from_summary_row(oes_row_ec, years)
        tites_ec = _raw_year_values_from_summary_row(tites_row_ec, years)
    else:
        oes_ec = oes_direct_ec
        tites_ec = tites_direct_ec
    series_ec = _sum_energy_zone_year_value_series(years, oes_ec, tites_ec)
    if _year_values_have_any_numeric(series_ec):
        target_ec = next(r for r in new_block if r.get("parameter_key") == "energy_consumption_mln_kvt_ch")
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            series_ec,
            parameter_key="energy_consumption_mln_kvt_ch",
            rounding_digits=rounding_digits,
        )

    if oes_row_sipr and tites_row_sipr:
        oes_sipr = _raw_year_values_from_summary_row(oes_row_sipr, years)
        tites_sipr = _raw_year_values_from_summary_row(tites_row_sipr, years)
    else:
        oes_sipr = oes_direct_sipr
        tites_sipr = tites_direct_sipr
    series_sipr = _sum_energy_zone_year_value_series(years, oes_sipr, tites_sipr)
    if _year_values_have_any_numeric(series_sipr):
        target_sipr = next(
            r for r in new_block if r.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
        )
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            series_sipr,
            parameter_key="energy_consumption_sipr_mln_kvt_ch",
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )

    summary_rows.extend(new_block)


_SUMMARY_TABLE_HUB_ENERGY_ZONE_FOOTER_LABELS: tuple[str, ...] = (
    "Энергозона Сибири",
    _EAST_ENERGY_ZONE_LABEL,
)


def _summary_table_hub_missing_energy_zone_footer_labels(
    summary_rows: list[dict[str, Any]],
) -> list[str]:
    present: set[str] = set()
    for row in summary_rows:
        if int(row.get("entity_depth") or 0) != 0:
            continue
        label = str(row.get("entity_label") or "").strip()
        if label in _SUMMARY_TABLE_HUB_ENERGY_ZONE_FOOTER_LABELS:
            present.add(label)
    return [
        label
        for label in _SUMMARY_TABLE_HUB_ENERGY_ZONE_FOOTER_LABELS
        if label not in present
    ]


def _extract_flat_energy_zone_footer_blocks(
    summary_rows: list[dict[str, Any]],
    entity_labels: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Строки энергозон без дочерних территорий (только entity_depth=0)."""
    want = {label.casefold() for label in entity_labels}
    return [
        dict(row)
        for row in summary_rows
        if str(row.get("entity_label") or "").strip().casefold() in want
        and int(row.get("entity_depth") or 0) == 0
    ]


def append_summary_table_hub_energy_zone_footer_rows(
    summary_rows: list[dict[str, Any]],
    *,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    data_start_year: int,
    data_end_year: int,
    filter_year_list: list[int],
) -> None:
    """Добавляет в конец /summary_table/ строки энергозон Сибири и Востока без дерева.

    Расчёт и подписи — как на /summary/energy_zones/ (без строк заряда ГАЭС).
    """
    missing_labels = _summary_table_hub_missing_energy_zone_footer_labels(summary_rows)
    if not missing_labels:
        return

    ez_ctx = build_energy_zones_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        expand_entity_perimeter_variants=True,
    )
    from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
        exclude_gaes_charge_summary_rows,
    )

    ez_rows = exclude_gaes_charge_summary_rows(list(ez_ctx.get("summary_rows") or []))
    footer = _extract_flat_energy_zone_footer_blocks(ez_rows, tuple(missing_labels))
    if footer:
        summary_rows.extend(footer)


_CHUKOTKA_RES_LABEL = "ЭС Чукотского АО"
_CHAUN_BILIBINO_EU_LABEL = "Чаун-Билибинский энергорайон"
_CHAUN_BILIBINO_CHERSKY_TRANSFER_NOTE = (
    "с перетоком в пос. Черский (Республика Саха (Якутия))"
)
_CHUKOTKA_REFERENCE_ROW_ENTITY_DEPTH = 2
_CHERSKY_REFERENCE_TRANSFER_LABEL = (
    "СПРАВОЧНО. Переток в пос. Черский (Республика Саха (Якутия))"
)
_CHERSKY_REFERENCE_TRANSFER_FORMULA_TOOLTIP = (
    "Переток в пос. Черский = ЭС Чукотского АО (О-1) − сумма входящих энергорайонов "
    "ЭС Чукотского АО (О-1)"
)
_CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL = (
    "СПРАВОЧНО. Чаун-Билибинский энергорайон без перетока в пос. Черский "
    "(Республика Саха (Якутия))"
)
_CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_FORMULA_TOOLTIP = (
    f"{_CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL} = "
    f"{_CHAUN_BILIBINO_EU_LABEL} + {_CHERSKY_REFERENCE_TRANSFER_LABEL}"
)


def _summary_entity_subtree_slice(
    summary_rows: list[dict[str, Any]],
    entity_label: str,
) -> slice | None:
    slices = _summary_entity_subtree_slices(summary_rows, entity_label)
    return slices[0] if slices else None


def _summary_entity_subtree_slices(
    summary_rows: list[dict[str, Any]],
    entity_label: str,
) -> list[slice]:
    """Все поддеревья с данным ``entity_label`` (на ОЭС/ФО Чукотка бывает дважды: О-1 и база)."""
    slices: list[slice] = []
    index = 0
    n = len(summary_rows)
    while index < n:
        row = summary_rows[index]
        if not (
            row.get("show_entity_cell")
            and str(row.get("entity_label") or "").strip() == entity_label
        ):
            index += 1
            continue
        entity_depth = int(row.get("entity_depth") or 0)
        end_index = n
        for scan in range(index + 1, n):
            child = summary_rows[scan]
            if not child.get("show_entity_cell"):
                continue
            if int(child.get("entity_depth") or 0) <= entity_depth:
                end_index = scan
                break
        slices.append(slice(index, end_index))
        index = end_index
    return slices


def _energy_unit_block_start_indices_in_slice(
    summary_rows: list[dict[str, Any]],
    block: slice,
    *,
    o1_only: bool,
) -> list[int]:
    starts: list[int] = []
    eu_model = EnergyUnitEnergyConsumptionParameter.__name__
    for index in range(block.start, block.stop):
        row = summary_rows[index]
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != eu_model:
            continue
        if o1_only and not (
            row.get("pd_ec_o1_form_row")
            or is_o1_perimeter_variant_code(row.get("perimeter_variant_code"))
        ):
            continue
        starts.append(index)
    return starts


def _o1_energy_unit_block_start_indices_in_slice(
    summary_rows: list[dict[str, Any]],
    block: slice,
) -> list[int]:
    return _energy_unit_block_start_indices_in_slice(
        summary_rows, block, o1_only=True
    )


def _chukotka_incoming_energy_unit_block_start_indices(
    summary_rows: list[dict[str, Any]],
) -> list[int]:
    """Энергорайоны Чукотки для формулы перетока в Черский.

    На энергозонах все ЭУ помечены О-1 и лежат под одной строкой РЭС.
    На ОЭС/ФО: «ЭС Чукотского АО» О-1 без детей, а энергорайоны — под базовой
    строкой РЭС (часть без метки О-1). Берём все ЭУ под любым блоком Чукотки.
    """
    slices = _summary_entity_subtree_slices(summary_rows, _CHUKOTKA_RES_LABEL)
    if not slices:
        return []
    starts: list[int] = []
    for block in slices:
        starts.extend(
            _energy_unit_block_start_indices_in_slice(
                summary_rows, block, o1_only=False
            )
        )
    return starts


def apply_chaun_bilibino_chersky_transfer_note(summary_rows: list[dict[str, Any]]) -> None:
    """Подпись о перетоке в Черский у блока «Чаун-Билибинский энергорайон» (перед меткой О-1)."""
    for row in summary_rows:
        if str(row.get("entity_label") or "").strip() != _CHAUN_BILIBINO_EU_LABEL:
            continue
        row["pd_ec_chukotka_reference_align"] = True
        if row.get("show_entity_cell"):
            row["pd_ec_chersky_transfer_note"] = _CHAUN_BILIBINO_CHERSKY_TRANSFER_NOTE


def apply_chukotka_chersky_reference_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Справочные строки перетока в Черский (после «Чаун-Билибинский энергорайон»).

    Нужны на сводках по энергозонам, ОЭС и ФО, когда в таблице есть Чукотка и Чаун-Билибинский.
    """
    inject_chukotka_chersky_reference_transfer_row(
        summary_rows, years, rounding_digits
    )
    inject_chaun_bilibino_without_chersky_transfer_row(
        summary_rows, years, rounding_digits
    )
    apply_chaun_bilibino_chersky_transfer_note(summary_rows)


def _chukotka_reference_row_template(
    summary_rows: list[dict[str, Any]],
    *,
    parameter_key: str,
    fallback_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Шаблон справочной строки: как у «Чаун-Билибинский энергорайон» (глубина, отступ)."""
    chaun_row = _pick_energy_zone_formula_source_row(
        summary_rows, _CHAUN_BILIBINO_EU_LABEL, parameter_key
    )
    if chaun_row is not None:
        return chaun_row
    for row in fallback_rows:
        if row is not None:
            return row
    return None


def _finalize_chukotka_reference_block_o1_visibility(
    new_block: list[dict[str, Any]],
) -> None:
    """Справочные строки Черский/Чаун: бейдж О-1 и показ только при кнопке «Форма О-1».

    При «Сводная таблица» + «Форма О-1» скрываются (см. ``pd_ec_hide_when_summary_table_and_o1``).
    """
    for row in new_block:
        row.pop("pd_ec_chukotka_ref_skip_o1_hide", None)
        row["pd_ec_o1_form_row"] = True
        row["pd_ec_hide_when_summary_table_and_o1"] = True
        if row.get("show_entity_cell"):
            row["pd_ec_show_o1_badge"] = True


def inject_chukotka_chersky_reference_transfer_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Справочная строка после «Чаун-Билибинский энергорайон»: ЭС Чукотского АО (О-1) − энергорайоны (О-1)."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_label") or "").strip() == _CHERSKY_REFERENCE_TRANSFER_LABEL
        for row in summary_rows
    ):
        return
    if _summary_rows_block_end_index(summary_rows, _CHAUN_BILIBINO_EU_LABEL) is None:
        return

    eu_block_starts = _chukotka_incoming_energy_unit_block_start_indices(summary_rows)
    if not eu_block_starts:
        return

    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    res_row_ec = _pick_energy_zone_formula_source_row(
        summary_rows,
        _CHUKOTKA_RES_LABEL,
        ec_key,
        prefer_o1=True,
    )
    res_row_sipr = _pick_energy_zone_formula_source_row(
        summary_rows,
        _CHUKOTKA_RES_LABEL,
        sipr_key,
        prefer_o1=True,
    )
    if res_row_ec is None and res_row_sipr is None:
        return

    sum_ec = _sum_summary_entity_blocks_parameter_by_year(
        summary_rows,
        eu_block_starts,
        years=years,
        parameter_key=ec_key,
        demand_model_name=EnergyUnitEnergyConsumptionParameter.__name__,
    )
    sum_sipr = _sum_summary_entity_blocks_parameter_by_year(
        summary_rows,
        eu_block_starts,
        years=years,
        parameter_key=sipr_key,
        demand_model_name=EnergyUnitEnergyConsumptionParameter.__name__,
    )

    if res_row_ec is not None:
        base_ec = _raw_year_values_from_summary_row(res_row_ec, years)
        series_ec = _subtract_year_value_dicts(years, base_ec, sum_ec)
    else:
        series_ec = {}

    if res_row_sipr is not None:
        base_sipr = _raw_year_values_from_summary_row(res_row_sipr, years)
        series_sipr = _subtract_year_value_dicts(years, base_sipr, sum_sipr)
    else:
        series_sipr = {}

    has_any = _year_values_have_any_numeric(series_ec) or _year_values_have_any_numeric(
        series_sipr
    )
    if not has_any:
        return

    template_row = _chukotka_reference_row_template(
        summary_rows,
        parameter_key=ec_key,
        fallback_rows=[
            res_row_ec,
            res_row_sipr,
            summary_rows[eu_block_starts[0]],
        ],
    )
    if template_row is None:
        return
    o1_code = resolve_catalog_o1_perimeter_variant_code()
    # Глубина как у «Чаун-Билибинский» (на ОЭС/ФО дерево глубже, чем на энергозонах).
    entity_depth = int(
        template_row.get("entity_depth") or _CHUKOTKA_REFERENCE_ROW_ENTITY_DEPTH
    )
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    new_block: list[dict[str, Any]] = []
    for idx, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        row = dict(template_row)
        row.pop("pd_ec_perimeter_entity_kind", None)
        row.pop("pd_ec_perimeter_entity_name", None)
        row.pop("pd_ec_chersky_transfer_note", None)
        row.update(
            {
                "entity_label": _CHERSKY_REFERENCE_TRANSFER_LABEL,
                "entity_rowspan": entity_rowspan,
                "entity_depth": entity_depth,
                "entity_kind": "chukotka_chersky_reference",
                "pd_ec_chukotka_reference_align": True,
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "year_row_ids": [None for _ in years],
                "hist_row_id": None,
                "hist_value": "—",
                "year_values": ["—" for _ in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": ["" for _ in years],
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": idx == 0,
                "perimeter_variant_code": o1_code,
                "perimeter_variant_label": "",
                "perimeter_variant_options": [],
                "pd_ec_formula_derived_row": True,
                "pd_ec_skip_empty_hide_row": True,
            }
        )
        if idx == 0:
            row["pd_ec_show_o1_badge"] = True
            row.pop("pd_ec_o1_form_row", None)
        if parameter_key in (ec_key, sipr_key):
            row["pd_ec_summary_row_formula_tooltip"] = (
                _CHERSKY_REFERENCE_TRANSFER_FORMULA_TOOLTIP
            )
        new_block.append(row)

    if _year_values_have_any_numeric(series_ec):
        target_ec = next(row for row in new_block if row.get("parameter_key") == ec_key)
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            series_ec,
            parameter_key=ec_key,
            rounding_digits=rounding_digits,
        )
    if _year_values_have_any_numeric(series_sipr):
        target_sipr = next(row for row in new_block if row.get("parameter_key") == sipr_key)
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            series_sipr,
            parameter_key=sipr_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=ec_key,
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=sipr_key,
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )

    tag_energy_consumption_summary_rows_perimeter_variant_labels(new_block)
    _finalize_chukotka_reference_block_o1_visibility(new_block)
    insert_at = _summary_rows_block_end_index(summary_rows, _CHAUN_BILIBINO_EU_LABEL)
    if insert_at is None:
        return
    summary_rows[insert_at:insert_at] = new_block


def inject_chaun_bilibino_without_chersky_transfer_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Справочная строка после перетока в Черский: Чаун-Билибинский энергорайон + переток."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_label") or "").strip()
        == _CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        for row in summary_rows
    ):
        return
    if _summary_rows_block_end_index(summary_rows, _CHERSKY_REFERENCE_TRANSFER_LABEL) is None:
        return
    if _summary_rows_block_end_index(summary_rows, _CHAUN_BILIBINO_EU_LABEL) is None:
        return

    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"

    chaun_row_ec = _pick_energy_zone_formula_source_row(
        summary_rows, _CHAUN_BILIBINO_EU_LABEL, ec_key
    )
    chaun_row_sipr = _pick_energy_zone_formula_source_row(
        summary_rows, _CHAUN_BILIBINO_EU_LABEL, sipr_key
    )
    chersky_row_ec = _pick_energy_zone_formula_source_row(
        summary_rows, _CHERSKY_REFERENCE_TRANSFER_LABEL, ec_key
    )
    chersky_row_sipr = _pick_energy_zone_formula_source_row(
        summary_rows, _CHERSKY_REFERENCE_TRANSFER_LABEL, sipr_key
    )
    if (chaun_row_ec is None and chaun_row_sipr is None) or (
        chersky_row_ec is None and chersky_row_sipr is None
    ):
        return

    if chaun_row_ec is not None and chersky_row_ec is not None:
        chaun_ec = _raw_year_values_from_summary_row(chaun_row_ec, years)
        chersky_ec = _raw_year_values_from_summary_row(chersky_row_ec, years)
        series_ec = _sum_energy_zone_year_value_series(years, chaun_ec, chersky_ec)
    else:
        series_ec = {}

    if chaun_row_sipr is not None and chersky_row_sipr is not None:
        chaun_sipr = _raw_year_values_from_summary_row(chaun_row_sipr, years)
        chersky_sipr = _raw_year_values_from_summary_row(chersky_row_sipr, years)
        series_sipr = _sum_energy_zone_year_value_series(years, chaun_sipr, chersky_sipr)
    else:
        series_sipr = {}

    has_any = _year_values_have_any_numeric(series_ec) or _year_values_have_any_numeric(
        series_sipr
    )
    if not has_any:
        return

    template_row = _chukotka_reference_row_template(
        summary_rows,
        parameter_key=ec_key,
        fallback_rows=[chaun_row_ec, chaun_row_sipr, chersky_row_ec, chersky_row_sipr],
    )
    if template_row is None:
        return
    o1_code = resolve_catalog_o1_perimeter_variant_code()
    entity_depth = int(
        template_row.get("entity_depth") or _CHUKOTKA_REFERENCE_ROW_ENTITY_DEPTH
    )
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    new_block: list[dict[str, Any]] = []
    for idx, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        row = dict(template_row)
        row.pop("pd_ec_perimeter_entity_kind", None)
        row.pop("pd_ec_perimeter_entity_name", None)
        row.pop("pd_ec_chersky_transfer_note", None)
        row.update(
            {
                "entity_label": _CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL,
                "entity_rowspan": entity_rowspan,
                "entity_depth": entity_depth,
                "entity_kind": "chaun_bilibino_without_chersky_reference",
                "pd_ec_chukotka_reference_align": True,
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "year_row_ids": [None for _ in years],
                "hist_row_id": None,
                "hist_value": "—",
                "year_values": ["—" for _ in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": ["" for _ in years],
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": idx == 0,
                "perimeter_variant_code": o1_code,
                "perimeter_variant_label": "",
                "perimeter_variant_options": [],
                "pd_ec_formula_derived_row": True,
                "pd_ec_skip_empty_hide_row": True,
            }
        )
        if idx == 0:
            row["pd_ec_show_o1_badge"] = True
            row.pop("pd_ec_o1_form_row", None)
        if parameter_key in (ec_key, sipr_key):
            row["pd_ec_summary_row_formula_tooltip"] = (
                _CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_FORMULA_TOOLTIP
            )
        new_block.append(row)

    if _year_values_have_any_numeric(series_ec):
        target_ec = next(row for row in new_block if row.get("parameter_key") == ec_key)
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            series_ec,
            parameter_key=ec_key,
            rounding_digits=rounding_digits,
        )
    if _year_values_have_any_numeric(series_sipr):
        target_sipr = next(row for row in new_block if row.get("parameter_key") == sipr_key)
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            series_sipr,
            parameter_key=sipr_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=ec_key,
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=sipr_key,
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )

    tag_energy_consumption_summary_rows_perimeter_variant_labels(new_block)
    _finalize_chukotka_reference_block_o1_visibility(new_block)
    insert_at = _summary_rows_block_end_index(
        summary_rows, _CHERSKY_REFERENCE_TRANSFER_LABEL
    )
    if insert_at is None:
        return
    summary_rows[insert_at:insert_at] = new_block


def _build_summary_context(
    *,
    entities: list[SummaryEntity],
    page_title: str,
    active_summary: str,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    avg_temp_uses_global_rounding: bool = False,
    hidden_demand_model_names: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    years = list(range(dsy, dey + 1))
    _yf = get_year_feature_dict() or {}
    year_is_plan: dict[int, bool] = {}
    for y in years:
        nm = _yf.get(y)
        year_is_plan[y] = (
            str(nm).strip().lower().replace(" ", "") == "план" if nm is not None else False
        )
    summary_rows = _flatten_entities(
        entities,
        years,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        hidden_demand_model_names=hidden_demand_model_names,
    )
    reorder_centralized_zone_russia_variant_blocks_in_summary_rows(summary_rows)
    tag_energy_consumption_summary_rows_perimeter_variant_labels(summary_rows)
    return {
        "page_title": page_title,
        "summary_rows": summary_rows,
        "years": years,
        "year_features": _yf,
        "year_is_plan": year_is_plan,
        "rounding_digits": rounding_digits,
        "active_summary": active_summary,
        "start_year": start_year,
        "end_year": end_year,
        "filter_year_list": filter_year_list,
    }


OES_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
    }
)
FO_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
    }
)
EZ_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
    }
)


def slice_energy_consumption_summary_context_for_export_years(
    context: dict[str, Any],
    export_years: list[int],
) -> dict[str, Any]:
    """Ограничить годовые столбцы списком лет с экрана (видимые колонки после переключателей периодов)."""
    full_years = list(context.get("years") or [])
    if not export_years or not full_years:
        return context
    if export_years == full_years:
        return context
    idx_map = [full_years.index(y) for y in export_years if y in full_years]
    if len(idx_map) != len(export_years):
        return context
    new_context = dict(context)
    yf_all = context.get("year_features") or {}
    yip_all = context.get("year_is_plan") or {}
    new_context["years"] = list(export_years)
    new_context["year_features"] = {y: yf_all.get(y) for y in export_years}
    new_context["year_is_plan"] = {y: yip_all.get(y, False) for y in export_years}
    new_rows: list[dict[str, Any]] = []
    list_keys = ("year_values", "year_row_ids", "year_numeric_tooltips")
    for row in context.get("summary_rows") or []:
        rc = dict(row)
        for lk in list_keys:
            old = row.get(lk)
            if isinstance(old, list):
                rc[lk] = [old[i] for i in idx_map if i < len(old)]
            else:
                rc[lk] = old
        new_rows.append(rc)
    new_context["summary_rows"] = new_rows
    return new_context


def filter_summary_rows_for_parameter_keys(
    summary_rows: list[dict[str, Any]],
    visible_keys: frozenset[str],
) -> list[dict[str, Any]]:
    """Усечение по выбору пользователя (GET ``visible_rows`` при экспорте Excel), не по территории."""
    if not visible_keys:
        return list(summary_rows)
    keys = visible_keys
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        filtered_block = [r for r in block if (r.get("parameter_key") or "") in keys]
        for j, r in enumerate(filtered_block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(filtered_block)
            out.append(rc)
        i += block_size
    return out


_PD_EC_EXPORT_NORMAL_PARAM_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
    }
)
_PD_EC_EXPORT_SIPR_PARAM_KEYS = frozenset(
    {
        "energy_consumption_sipr_mln_kvt_ch",
        ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
    }
)


@dataclass(frozen=True)
class EnergyConsumptionExportUiOptions:
    """Состояние кнопок сводки при выгрузке Excel (как на экране)."""

    sipr_on: bool = False
    gaes_detail_on: bool = True
    nt_detail_on: bool = False
    verification_on: bool = False
    territory_compact_on: bool = False
    isolated_energy_units_on: bool = False
    summary_table_page: bool = False


def _parse_export_ui_bool_arg(arg_name: str, default: bool) -> bool:
    from flask import request

    raw = request.args.get(arg_name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def parse_energy_consumption_export_ui_options(
    *,
    summary_table_page: bool = False,
) -> EnergyConsumptionExportUiOptions:
    defaults = EnergyConsumptionExportUiOptions(
        territory_compact_on=summary_table_page,
    )
    return EnergyConsumptionExportUiOptions(
        sipr_on=_parse_export_ui_bool_arg("export_sipr", defaults.sipr_on),
        gaes_detail_on=_parse_export_ui_bool_arg("export_gaes_detail", defaults.gaes_detail_on),
        nt_detail_on=_parse_export_ui_bool_arg("export_nt_detail", defaults.nt_detail_on),
        verification_on=_parse_export_ui_bool_arg(
            "export_verification", defaults.verification_on
        ),
        territory_compact_on=_parse_export_ui_bool_arg(
            "export_territory_compact", defaults.territory_compact_on
        ),
        isolated_energy_units_on=_parse_export_ui_bool_arg(
            "export_isolated_eu", defaults.isolated_energy_units_on
        ),
        summary_table_page=summary_table_page,
    )


def _is_ec_summary_verification_row(row: dict[str, Any]) -> bool:
    label = str(row.get("entity_label") or "")
    if label.startswith("Проверка "):
        return True
    ek = str(row.get("entity_kind") or "")
    return ek in (
        "oes_ees_model_verification",
        "oes_ees_sync_table_verification",
        "oes_south_oes_model_verification",
        "ues_res_sum_check",
        "res_subject_sum_check",
        "tites_res_energy_unit_sum_check",
        "east_ez_o1_res_energy_unit_sum_check",
        "east_ez_o1_parent_sum_check",
        "oes_tites_aggregate_check",
        "fo_res_sum_check",
        "ez_res_sum_check",
    ) or label.startswith("Проверка ОЭС ")


def _summary_row_visible_for_export_ui(
    row: dict[str, Any],
    *,
    opts: EnergyConsumptionExportUiOptions,
    parameter_visible: Callable[[str], bool],
) -> bool:
    pk = str(row.get("parameter_key") or "")
    is_ver = _is_ec_summary_verification_row(row)
    user_show = parameter_visible(pk)

    if is_ver and opts.verification_on:
        if row.get("pd_ec_verification_require_isolated_eu") and not opts.isolated_energy_units_on:
            return False
        return True

    mode_hide = (opts.sipr_on and pk in _PD_EC_EXPORT_NORMAL_PARAM_KEYS) or (
        not opts.sipr_on and pk in _PD_EC_EXPORT_SIPR_PARAM_KEYS
    )
    if not (user_show and not mode_hide):
        return False

    if (
        not is_ver
        and row.get("pd_ec_hide_when_isolated_eu_on")
        and opts.isolated_energy_units_on
    ):
        return False
    if (
        not is_ver
        and row.get("pd_ec_hide_when_summary_table_and_o1")
        and opts.territory_compact_on
        and opts.isolated_energy_units_on
    ):
        return False
    if not is_ver and row.get("pd_ec_o1_form_row") and not opts.isolated_energy_units_on:
        return False
    collapsed_nt_gaes = not opts.gaes_detail_on and not opts.nt_detail_on
    expanded_nt_gaes = opts.gaes_detail_on and opts.nt_detail_on
    nt_on_gaes_off = opts.nt_detail_on and not opts.gaes_detail_on
    if (
        not is_ver
        and collapsed_nt_gaes
        and row.get("pd_ec_collapsed_nt_gaes_redundant_row")
    ):
        return False
    if not is_ver and expanded_nt_gaes and row.get("pd_ec_expanded_nt_gaes_redundant_row"):
        return False
    if (
        not is_ver
        and nt_on_gaes_off
        and row.get("pd_ec_nt_on_gaes_off_redundant_row")
    ):
        return False
    if not is_ver and row.get("pd_ec_gaes_extra_row") and not opts.gaes_detail_on:
        if not (
            (collapsed_nt_gaes and row.get("pd_ec_collapsed_nt_gaes_visible_row"))
            or (nt_on_gaes_off and row.get("pd_ec_nt_on_gaes_off_visible_row"))
        ):
            return False
    if (
        not is_ver
        and row.get("pd_ec_gaes_without_row")
        and not opts.gaes_detail_on
    ):
        if not (
            (collapsed_nt_gaes and row.get("pd_ec_collapsed_nt_gaes_visible_row"))
            or (nt_on_gaes_off and row.get("pd_ec_nt_on_gaes_off_visible_row"))
        ):
            return False
    if not is_ver and row.get("pd_ec_nt_extra_row") and not opts.nt_detail_on:
        return False
    if (
        not is_ver
        and opts.territory_compact_on
        and row.get("pd_ec_territory_detail_row")
        and not (
            opts.nt_detail_on
            and (
                row.get("pd_ec_nt_extra_row")
                or row.get("pd_ec_territory_detail_relaxed_compact_nt_gaes")
            )
        )
    ):
        return False
    if (
        not is_ver
        and not opts.territory_compact_on
        and row.get("pd_ec_summary_table_only_row")
    ):
        return False
    if not is_ver and opts.territory_compact_on and row.get("pd_ec_territory_compact_hide_row"):
        if not opts.summary_table_page:
            return False
    if (
        not is_ver
        and opts.territory_compact_on
        and str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY
    ):
        return False
    if (
        not is_ver
        and row.get("pd_ec_first_sa_gaes_compact_variant") == "detail"
        and opts.territory_compact_on
    ):
        return False
    if is_ver and not opts.verification_on:
        return False
    if not is_ver and row.get("pd_ec_verification_nt_split_only") and not opts.nt_detail_on:
        return False

    sync_nt_vis = str(row.get("pd_ec_sync_verify_nt_visibility") or "")
    if sync_nt_vis == "summary" and opts.nt_detail_on and not opts.verification_on:
        return False
    if sync_nt_vis == "detail" and not opts.nt_detail_on and not opts.verification_on:
        return False
    return True


def export_entity_label_for_summary_row(
    row: dict[str, Any],
    opts: EnergyConsumptionExportUiOptions,
) -> str:
    full_l = str(row.get("entity_label") or "").strip()

    if row.get("pd_ec_sync_verify_label_matrix"):
        key = (opts.nt_detail_on, opts.gaes_detail_on)
        variants = {
            (True, True): row.get("pd_ec_sync_verify_l_nt1_gaes1"),
            (True, False): row.get("pd_ec_sync_verify_l_nt1_gaes0"),
            (False, True): row.get("pd_ec_sync_verify_l_nt0_gaes1"),
            (False, False): row.get("pd_ec_sync_verify_l_nt0_gaes0"),
        }
        chosen = variants.get(key)
        return str(chosen or full_l).strip()

    collapsed = row.get("pd_ec_ees_verification_nt_collapsed_label")
    if collapsed is not None:
        return full_l if opts.nt_detail_on else str(collapsed).strip()

    cg = row.get("pd_ec_entity_label_compact")
    cn = row.get("pd_ec_entity_label_compact_nt")
    c_both = row.get("pd_ec_entity_label_compact_nt_gaes")
    if opts.gaes_detail_on and opts.nt_detail_on:
        return full_l
    if not opts.gaes_detail_on and not opts.nt_detail_on:
        return str(c_both if c_both is not None else full_l).strip()
    if not opts.gaes_detail_on and opts.nt_detail_on:
        return str(cg if cg is not None else full_l).strip()
    return str(cn if cn is not None else full_l).strip()


def finalize_summary_rows_for_excel_export(
    summary_rows: list[dict[str, Any]],
    *,
    visible_parameter_keys: frozenset[str] | None,
    ui_opts: EnergyConsumptionExportUiOptions,
) -> list[dict[str, Any]]:
    def parameter_visible(pk: str) -> bool:
        if not visible_parameter_keys:
            return True
        return pk in visible_parameter_keys or pk in _SUMMARY_ALWAYS_VISIBLE_PARAMETER_KEYS

    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        kept: list[dict[str, Any]] = []
        for r in block:
            pk = str(r.get("parameter_key") or "")
            if not _summary_row_visible_for_export_ui(
                r, opts=ui_opts, parameter_visible=parameter_visible
            ):
                continue
            rc = dict(r)
            rc["entity_label"] = export_entity_label_for_summary_row(r, ui_opts)
            kept.append(rc)
        for j, r in enumerate(kept):
            r["show_entity_cell"] = j == 0
            r["entity_rowspan"] = len(kept)
            r["show_entity_note_cell"] = j == 0
            out.append(r)
        i += block_size
    return out


_TERRITORY_DETAIL_DEMAND_MODELS = frozenset(
    {
        RegionalEnergySystemEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
        EnergyUnitEnergyConsumptionParameter.__name__,
    }
)

_SUMMARY_TABLE_HIDDEN_OES_DETAIL_DEMAND_MODELS = frozenset(
    {
        RegionalEnergySystemEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
    }
)


def _is_centralized_zone_russia_summary_row(row: dict[str, Any]) -> bool:
    if row.get("entity_kind") == ENTITY_KIND_CENTRALIZED_ZONE:
        return True
    if row.get("demand_model_name") != CentralizedZoneEnergyConsumptionParameter.__name__:
        return False
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    return label_cf in (
        CENTRALIZED_ZONE_AGGREGATE_NAME.casefold(),
        "централизованная зона",
    )


def _is_centralized_zone_russia_o1_summary_row(row: dict[str, Any]) -> bool:
    """«ЦЗ России с/без НТ», вариант периметра О-1 (o1_with_nt / o1_without_nt)."""
    if not _is_centralized_zone_russia_summary_row(row):
        return False
    code = row.get("perimeter_variant_code")
    return bool(code) and is_o1_perimeter_variant_code(code)


def _centralized_zone_russia_variant_block_sort_key(
    block: list[dict[str, Any]],
) -> tuple[int, int]:
    code = str((block[0] if block else {}).get("perimeter_variant_code") or "")
    nt_group = _nt_group_for_variant_code(code)
    nt_order = {"with_nt": 0, "without_nt": 1}.get(nt_group, 2)
    return (nt_order, 1 if is_o1_perimeter_variant_code(code) else 0)


def reorder_centralized_zone_russia_variant_blocks_in_summary_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    """С НТ → с НТ О-1 → без НТ → без НТ О-1 для подряд идущих блоков «ЦЗ России» (depth=0)."""
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_centralized_zone_russia_summary_row(row):
            i += 1
            continue
        if int(row.get("entity_depth") or 0) != 0:
            i += 1
            continue
        start = i
        segment_end = start
        while segment_end < n:
            segment_row = summary_rows[segment_end]
            if not _is_centralized_zone_russia_summary_row(segment_row):
                break
            if int(segment_row.get("entity_depth") or 0) != 0:
                break
            segment_end += 1
        blocks: list[list[dict[str, Any]]] = []
        j = start
        while j < segment_end:
            block_row = summary_rows[j]
            if block_row.get("show_entity_cell"):
                block_size = max(int(block_row.get("entity_rowspan") or 1), 1)
                blocks.append(summary_rows[j : j + block_size])
                j += block_size
            else:
                j += 1
        if len(blocks) >= 2:
            blocks.sort(key=_centralized_zone_russia_variant_block_sort_key)
            reordered: list[dict[str, Any]] = []
            for block in blocks:
                reordered.extend(block)
            summary_rows[start:segment_end] = reordered
        i = segment_end


def exclude_centralized_zone_russia_o1_summary_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Убирает строки «ЦЗ России … О-1»; пересчитывает ``entity_rowspan`` (страница /summary/energy_zones/)."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            out.append(dict(row))
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        if any(_is_centralized_zone_russia_o1_summary_row(r) for r in block):
            i += block_size
            continue
        for j, r in enumerate(block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(block)
            if j == 0:
                rc["show_entity_note_cell"] = True
            out.append(rc)
        i += block_size
    return out


def tag_energy_consumption_summary_rows_for_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Метки строк, скрываемых в режиме «Сводная таблица».

    В т.ч. строки «Заряд ГАЭС» и «… (заряд ГАЭС)» (parameter ``gaes_charge_…``).
    """
    for row in summary_rows:
        row.pop("pd_ec_territory_detail_row", None)
        row.pop("pd_ec_territory_detail_relaxed_compact_nt_gaes", None)

        if _is_centralized_zone_russia_summary_row(row):
            row["pd_ec_territory_compact_hide_row"] = True
        else:
            row.pop("pd_ec_territory_compact_hide_row", None)

        dm = row.get("demand_model_name") or ""
        if dm in _TERRITORY_DETAIL_DEMAND_MODELS and int(row.get("entity_depth") or 0) > 0:
            row["pd_ec_territory_detail_row"] = True

        if _is_gaes_charge_summary_compact_hide_row(row):
            row["pd_ec_territory_compact_hide_row"] = True

    _apply_tites_subtree_territory_compact_rules(summary_rows)


def tag_energy_consumption_summary_rows_before_oes_blocks(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Строки до блоков ОЭС — только при нажатой «Сводная таблица»."""
    tag_energy_consumption_summary_rows_before_section_blocks(summary_rows, "oes")


def _is_federal_district_summary_top_block_start(row: dict[str, Any]) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if int(row.get("entity_depth") or 0) != 0:
        return False
    if row.get("demand_model_name") != FederalDistrictEnergyConsumptionParameter.__name__:
        return False
    if row.get("parent_fk_column") != "id_federal_district":
        return False
    return str(row.get("entity_kind") or "") in ("group", "perimeter_variant")


def _is_energy_zone_summary_top_block_start(row: dict[str, Any]) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if int(row.get("entity_depth") or 0) != 0:
        return False
    if row.get("demand_model_name") != EnergyZoneEnergyConsumptionParameter.__name__:
        return False
    if row.get("parent_fk_column") != "id_energy_zone":
        return False
    return str(row.get("entity_kind") or "") in ("group", "perimeter_variant")


def tag_energy_consumption_summary_rows_before_section_blocks(
    summary_rows: list[dict[str, Any]],
    scope: str,
) -> None:
    """Строки до блоков ОЭС/ФО/энергозон — только при нажатой «Сводная таблица»."""
    if not summary_rows:
        return
    for row in summary_rows:
        row.pop("pd_ec_summary_table_only_row", None)
    if scope == "oes":
        is_start = _is_union_energy_system_oes_summary_top_block_start
    elif scope == "fo":
        is_start = _is_federal_district_summary_top_block_start
    elif scope == "ez":
        is_start = _is_energy_zone_summary_top_block_start
    else:
        return
    first_idx: int | None = None
    for i, row in enumerate(summary_rows):
        if is_start(row):
            first_idx = i
            break
    if first_idx is None:
        return
    for i in range(first_idx):
        summary_rows[i]["pd_ec_summary_table_only_row"] = True


def tag_energy_consumption_summary_rows_before_federal_district_blocks(
    summary_rows: list[dict[str, Any]],
) -> None:
    tag_energy_consumption_summary_rows_before_section_blocks(summary_rows, "fo")


def tag_energy_consumption_summary_rows_before_energy_zone_blocks(
    summary_rows: list[dict[str, Any]],
) -> None:
    tag_energy_consumption_summary_rows_before_section_blocks(summary_rows, "ez")


_SUMMARY_TABLE_ENERGY_ZONE_FOOTER_LABELS: frozenset[str] = frozenset(
    {
        "Энергозона Сибири",
        _EAST_ENERGY_ZONE_LABEL,
    }
)


def tag_summary_table_energy_zone_footer_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Блоки «Энергозона Сибири» / «Энергозона Востока» — только при «Сводная таблица».

    У самих строк энергозон — значок О-1; видимы при «Сводная таблица» + «Форма О-1».
    Включая дочерние ЭС/энергорайоны в блоке Востока. Вызывать после
    ``tag_energy_consumption_summary_rows_before_*_blocks`` (там метка сбрасывается).
    """
    if not summary_rows:
        return
    labels = _SUMMARY_TABLE_ENERGY_ZONE_FOOTER_LABELS
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        label = str(row.get("entity_label") or "").strip()
        if (
            row.get("show_entity_cell")
            and int(row.get("entity_depth") or 0) == 0
            and label in labels
        ):
            j = i + 1
            while j < n:
                nxt = summary_rows[j]
                if (
                    nxt.get("show_entity_cell")
                    and int(nxt.get("entity_depth") or 0) == 0
                ):
                    break
                j += 1
            for k in range(i, j):
                summary_rows[k]["pd_ec_summary_table_only_row"] = True
                if str(summary_rows[k].get("entity_label") or "").strip() in labels:
                    _mark_energy_zone_footer_parent_o1_visibility(summary_rows[k])
            i = j
            continue
        if label in labels:
            # Параметрные строки без show_entity_cell (плоско, как на /summary/oes/).
            row["pd_ec_summary_table_only_row"] = True
            _mark_energy_zone_footer_parent_o1_visibility(row)
        i += 1


def _is_tites_branch_regional_energy_system_row(row: dict[str, Any]) -> bool:
    if (
        str(row.get("demand_model_name") or "").strip()
        != RegionalEnergySystemEnergyConsumptionParameter.__name__
    ):
        return False
    if row.get("pd_ec_decentralized_zone_mark"):
        return False
    ues_id = row.get("id_union_energy_system")
    if ues_id is None:
        return False
    return int(ues_id) in _tites_union_energy_system_ids()


def _apply_tites_subtree_territory_compact_rules(
    summary_rows: list[dict[str, Any]],
) -> None:
    """В «Сводной таблице»: блок ТИТЭС — только РЭС ветки (без ОЭС, субъектов, энергорайонов)."""
    ues_mn = UnionEnergySystemEnergyConsumptionParameter.__name__
    res_mn = RegionalEnergySystemEnergyConsumptionParameter.__name__
    rd_mn = RegionalDistrictEnergyConsumptionParameter.__name__
    eu_mn = EnergyUnitEnergyConsumptionParameter.__name__

    i = 0
    n = len(summary_rows)
    while i < n:
        if not _is_oes_tites_root_summary_block_anchor_row(summary_rows[i]):
            i += 1
            continue

        header = summary_rows[i]
        base_depth = int(header.get("entity_depth", 0) or 0)

        subtree_end = i + 1
        while subtree_end < n:
            child = summary_rows[subtree_end]
            if child.get("show_entity_cell"):
                child_depth = int(child.get("entity_depth", 0) or 0)
                if child_depth <= base_depth:
                    break
            subtree_end += 1

        tites_res_ids: set[int] = set()
        for k in range(i + 1, subtree_end):
            row = summary_rows[k]
            if not _is_tites_branch_regional_energy_system_row(row):
                continue
            if not row.get("show_entity_cell"):
                continue
            res_id = row.get("id_regional_energy_system")
            if res_id is not None:
                tites_res_ids.add(int(res_id))

        for k in range(i + 1, subtree_end):
            row = summary_rows[k]
            dm = str(row.get("demand_model_name") or "").strip()
            res_id = row.get("id_regional_energy_system")
            in_tites_res_block = res_id is not None and int(res_id) in tites_res_ids

            if in_tites_res_block and dm == res_mn:
                row.pop("pd_ec_territory_detail_row", None)
                row.pop("pd_ec_territory_compact_hide_row", None)
            elif row.get("pd_ec_decentralized_zone_mark") or dm == ues_mn:
                row["pd_ec_territory_compact_hide_row"] = True
                row["pd_ec_territory_detail_row"] = True
            elif dm in (eu_mn, rd_mn):
                row["pd_ec_territory_detail_row"] = True
            elif dm == res_mn:
                row["pd_ec_territory_detail_row"] = True
                row["pd_ec_territory_compact_hide_row"] = True
            elif row.get("entity_kind") == "tites_res_energy_unit_sum_check":
                row["pd_ec_territory_compact_hide_row"] = True
            elif _is_oes_summary_hidden_tites_verification_row(row):
                row["pd_ec_territory_compact_hide_row"] = True
            elif str(row.get("entity_kind") or "") == "oes_tites_aggregate_check":
                row["pd_ec_territory_compact_hide_row"] = True

        i = subtree_end


def _is_hidden_tites_ues_summary_entity(entity: SummaryEntity) -> bool:
    return (
        entity.demand_model_name == UnionEnergySystemEnergyConsumptionParameter.__name__
        and _is_oes_summary_hidden_tites_union_energy_system_label(entity.label)
    )


def _unwrap_hidden_tites_ues_entities(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    """Промотирует РЭС/ниже из скрытых ОЭС «ТИТЭС Сибири» / «ТИТЭС Востока»."""
    out: list[SummaryEntity] = []
    for entity in entities:
        if _is_hidden_tites_ues_summary_entity(entity):
            for child in entity.children:
                out.append(_shift_summary_entity_depth(child, -1))
        else:
            out.append(entity)
    return out


def _is_gaes_charge_summary_compact_hide_row(row: dict[str, Any]) -> bool:
    """Строки заряда ГАЭС: «Заряд ГАЭС», «… (заряд ГАЭС)» и «… (всего)»."""
    if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
        return True
    if str(row.get("gaes_charge_row_station_name") or "").strip().casefold() == "всего":
        return True
    label = str(row.get("entity_label") or "").strip()
    if label == _SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL:
        return True
    return label.endswith(_GAES_CHARGE_LABEL_SUFFIX)


def _summary_row_skips_perimeter_variant_year_bounds(row: dict[str, Any]) -> bool:
    return bool(row.get("pd_ec_skip_perimeter_variant_year_bounds"))


def _year_applies_to_summary_row_perimeter_variant(row: dict[str, Any], year: int) -> bool:
    if _summary_row_skips_perimeter_variant_year_bounds(row):
        return True
    code = row.get("perimeter_variant_code")
    if not code:
        return True
    fy, ty = perimeter_variant_year_bounds_for_code(str(code))
    if fy is not None and int(year) < int(fy):
        return False
    if ty is not None and int(year) > int(ty):
        return False
    return True


def mask_summary_rows_perimeter_variant_year_display(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """Скрыть значения и id строк вне периода «Год с» / «Год по» варианта периметра."""
    if not years:
        return
    n = len(years)
    for row in summary_rows:
        if _summary_row_skips_perimeter_variant_year_bounds(row):
            row.pop("perimeter_variant_from_year", None)
            row.pop("perimeter_variant_to_year", None)
            continue
        code = row.get("perimeter_variant_code")
        if not code:
            continue
        fy, ty = perimeter_variant_year_bounds_for_code(str(code))
        if fy is None and ty is None:
            continue
        row["perimeter_variant_from_year"] = fy
        row["perimeter_variant_to_year"] = ty
        yv = list(row.get("year_values") or [])
        tt = list(row.get("year_numeric_tooltips") or [])
        rids = list(row.get("year_row_ids") or [])
        while len(yv) < n:
            yv.append("—")
        while len(tt) < n:
            tt.append("")
        while len(rids) < n:
            rids.append(None)
        for ix, yr in enumerate(years):
            if _year_applies_to_summary_row_perimeter_variant(row, int(yr)):
                continue
            yv[ix] = "—"
            tt[ix] = ""
            rids[ix] = None
        row["year_values"] = yv
        row["year_numeric_tooltips"] = tt
        row["year_row_ids"] = rids


_SUMMARY_NO_PERIMETER_VARIANT_SELECT_MODELS = frozenset(
    {
        "EnergyZoneEnergyConsumptionParameter",
    }
)


def _summary_row_allows_perimeter_variant_select(row: dict[str, Any]) -> bool:
    """Строка блока сущности, для которой в сводке можно менять perimeter_variant_code."""
    if not row.get("show_entity_cell"):
        return False
    dm_name = str(row.get("demand_model_name") or "").strip()
    if not dm_name or dm_name in _SUMMARY_NO_PERIMETER_VARIANT_SELECT_MODELS:
        return False
    if _is_ec_summary_verification_row(row):
        return False
    if row.get("pd_ec_summary_readonly_row"):
        return False
    if row.get("entity_kind") == "ees_energy_consumption_composite":
        return False
    from app.energy_consumption.services.energy_consumption_parameter_services import (
        _summary_demand_model_class,
    )

    try:
        model_cls = _summary_demand_model_class(dm_name)
    except ValueError:
        return False
    if not model_supports_perimeter_variant(model_cls):
        return False
    options = row.get("perimeter_variant_options") or []
    if len(options) >= 2:
        return True
    is_gaes_charge = str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY
    has_code = bool(str(row.get("perimeter_variant_code") or "").strip())
    if is_gaes_charge or has_code or len(options) >= 1:
        return True
    return bool(row.get("pd_ec_perimeter_entity_kind"))


def _append_perimeter_variant_option_if_missing(
    row: dict[str, Any],
    code: object,
    *,
    pe_kind: str | None,
    pe_name: str | None,
    oes_summary: bool = False,
) -> None:
    """Текущий код варианта должен быть в select (в т.ч. o1 у изолированных энергорайонов)."""
    if not code or not row.get("show_entity_cell"):
        return
    code_s = str(code).strip()
    if not code_s:
        return
    opts = list(row.get("perimeter_variant_options") or [])
    if any(str(o.get("code") or "") == code_s for o in opts):
        return
    if oes_summary:
        from app.power_demand.services.demand_summary_services import (
            _oes_perimeter_variant_russian_label,
        )

        label = _oes_perimeter_variant_russian_label(
            code_s,
            binding=resolve_entity_perimeter_binding(pe_kind, pe_name),
            entity_kind=pe_kind,
            entity_name=pe_name,
            strip_gaes_suffix=False,
        )
    else:
        label = perimeter_variant_display_label_for_entity(code_s, pe_kind, pe_name) or code_s
    label = _ensure_gaes_suffix_in_perimeter_variant_label(label, code_s)
    opts.append({"code": code_s, "label": label})
    row["perimeter_variant_options"] = opts


def tag_energy_consumption_summary_rows_perimeter_variant_labels(
    summary_rows: list[dict[str, Any]],
    *,
    oes_summary: bool = False,
    use_summary_perimeter_options: bool = False,
) -> None:
    """Подпись и привязка варианта периметра для столбца сводки."""
    if use_summary_perimeter_options or oes_summary:
        from app.power_demand.services.demand_summary_services import (
            _oes_perimeter_variant_russian_label,
        )
    if use_summary_perimeter_options:
        from app.power_demand.services.demand_summary_services import (
            _perimeter_variant_options_for_oes_summary,
            _perimeter_variant_options_for_summary,
        )

    pe_context_cache: dict[tuple[str, str | None, int | None], tuple[str, str] | None] = {}
    for row in summary_rows:
        code = row.get("perimeter_variant_code")
        dm = row.get("demand_model_name") or ""
        pe_kind = row.get("pd_ec_perimeter_entity_kind")
        pe_name = row.get("pd_ec_perimeter_entity_name")
        if not pe_kind or not pe_name:
            cache_key = (
                str(dm),
                row.get("parent_fk_column"),
                row.get("parent_id"),
            )
            if cache_key not in pe_context_cache:
                pe_context_cache[cache_key] = perimeter_entity_context_for_model(
                    dm,
                    parent_fk_column=row.get("parent_fk_column"),
                    parent_id=row.get("parent_id"),
                )
            ctx = pe_context_cache[cache_key]
            if ctx is not None:
                pe_kind, pe_name = ctx
                row["pd_ec_perimeter_entity_kind"] = pe_kind
                row["pd_ec_perimeter_entity_name"] = pe_name
        if row.get("show_entity_cell") and pe_kind:
            if is_ees_unified_energy_system_type_entity(pe_kind, pe_name):
                nt_group = legacy_nt_group_for_perimeter_code(code)
                row["perimeter_variant_options"] = (
                    perimeter_variant_options_for_ees_unified_summary_nt_group(nt_group)
                )
            elif use_summary_perimeter_options:
                if oes_summary:
                    row["perimeter_variant_options"] = _perimeter_variant_options_for_oes_summary(
                        pe_kind,
                        pe_name,
                        strip_gaes_suffix=False,
                    )
                else:
                    row["perimeter_variant_options"] = _perimeter_variant_options_for_summary(
                        pe_kind, pe_name
                    )
            else:
                row["perimeter_variant_options"] = perimeter_variant_options_for_entity(
                    pe_kind, pe_name
                )
            allowed_codes = {
                str(opt.get("code") or "").strip()
                for opt in row["perimeter_variant_options"]
                if opt.get("code")
            }
            if (
                code
                and allowed_codes
                and str(code) not in allowed_codes
                and str(code) in (CODE_WITH_NT, CODE_WITHOUT_NT)
            ):
                code = None
                row["perimeter_variant_code"] = None
            _append_perimeter_variant_option_if_missing(
                row,
                code,
                pe_kind=pe_kind,
                pe_name=pe_name,
                oes_summary=oes_summary,
            )
        elif row.get("show_entity_cell"):
            row["perimeter_variant_options"] = []
            _append_perimeter_variant_option_if_missing(
                row,
                code,
                pe_kind=pe_kind,
                pe_name=pe_name,
                oes_summary=oes_summary,
            )
        if oes_summary and code:
            row["perimeter_variant_label"] = _oes_perimeter_variant_russian_label(
                str(code),
                binding=resolve_entity_perimeter_binding(pe_kind, pe_name),
                entity_kind=pe_kind,
                entity_name=pe_name,
                strip_gaes_suffix=False,
            )
            for opt in row.get("perimeter_variant_options") or []:
                if opt.get("code") == code:
                    row["perimeter_variant_label"] = opt.get("label") or row["perimeter_variant_label"]
                    break
        elif code:
            row["perimeter_variant_label"] = (
                perimeter_variant_display_label_for_entity(code, pe_kind, pe_name)
            )
        elif not str(row.get("perimeter_variant_label") or "").strip():
            row["perimeter_variant_label"] = ""
        if row.get("show_entity_cell"):
            row["perimeter_variant_options"] = [
                {
                    "code": str(opt.get("code") or ""),
                    "label": _ensure_gaes_suffix_in_perimeter_variant_label(
                        str(opt.get("label") or opt.get("code") or ""),
                        opt.get("code"),
                    ),
                }
                for opt in (row.get("perimeter_variant_options") or [])
                if opt.get("code")
            ]
            row["perimeter_variant_label"] = _ensure_gaes_suffix_in_perimeter_variant_label(
                str(row.get("perimeter_variant_label") or ""),
                code,
            )
        if code and not _summary_row_skips_perimeter_variant_year_bounds(row):
            fy, ty = perimeter_variant_year_bounds_for_code(str(code))
            row["perimeter_variant_from_year"] = fy
            row["perimeter_variant_to_year"] = ty
        elif _is_ec_summary_verification_row(row):
            pass
        else:
            row.pop("perimeter_variant_from_year", None)
            row.pop("perimeter_variant_to_year", None)
        if is_o1_perimeter_variant_code(code):
            row["pd_ec_o1_form_row"] = True
        else:
            row.pop("pd_ec_o1_form_row", None)
        row["show_perimeter_variant_select"] = _summary_row_allows_perimeter_variant_select(
            row
        )


def _summary_table_hide_gaes_charge_territory_row(row: dict[str, Any]) -> bool:
    """Заряд ГАЭС на уровнях РЭС / субъекта РФ / энергоузла не показываем в сводной таблице."""
    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
        return False
    dm = row.get("demand_model_name") or ""
    if dm in _TERRITORY_DETAIL_DEMAND_MODELS:
        return True
    return bool(row.get("pd_ec_territory_detail_relaxed_compact_nt_gaes"))


def _summary_table_hide_gaes_charge_aggregate_row(row: dict[str, Any]) -> bool:
    """Заряд ГАЭС для ЭЭС России, ЕЭС России и первой СЗ не показываем в сводной таблице."""
    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
        return False
    dm = str(row.get("demand_model_name") or "")
    base_label_cf = _summary_row_base_label_cf(row)
    if (
        dm == SynchronousAreaEnergyConsumptionParameter.__name__
        and base_label_cf.startswith(_FIRST_SYNC_AREA_BASE_LABEL_CF)
    ):
        return True
    if (
        dm == EnergySystemTypeEnergyConsumptionParameter.__name__
        and base_label_cf == EES_UNIFIED_REF_NAME.casefold()
    ):
        return True
    if (
        dm == EesRussiaEnergyConsumptionParameter.__name__
        and base_label_cf == EES_RUSSIA_AGGREGATE_NAME.casefold()
    ):
        return True
    return False


def filter_summary_table_gaes_charge_aggregate_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    return [
        row
        for row in summary_rows
        if not _summary_table_hide_gaes_charge_aggregate_row(row)
    ]


def keep_centralized_zone_rows_in_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Строки «ЦЗ России» остаются видимыми в режиме «Сводная таблица» на /summary/oes/ и /summary/federal_districts/."""
    for row in summary_rows:
        if _is_centralized_zone_russia_summary_row(row):
            row.pop("pd_ec_territory_compact_hide_row", None)


_OES_SUMMARY_HIDDEN_TITES_UES_LABELS_CF = frozenset(
    {
        TITES_EAST_UES_NAME_CF.replace(" ", ""),
        TITES_SIBERIA_UES_NAME_CF.replace(" ", ""),
    }
)


def _normalized_union_energy_system_label_cf(label: object) -> str:
    return str(label or "").strip().casefold().replace(" ", "")


def _is_oes_summary_hidden_tites_union_energy_system_label(label: object) -> bool:
    return _normalized_union_energy_system_label_cf(label) in _OES_SUMMARY_HIDDEN_TITES_UES_LABELS_CF


def _is_oes_summary_hidden_tites_union_energy_system_own_row(
    row: dict[str, Any],
) -> bool:
    """Строки показателей самой ОЭС «ТИТЭС Сибири» / «ТИТЭС Востока», без дочерних территорий."""
    if not _is_oes_summary_hidden_tites_union_energy_system_label(
        _summary_row_base_label_cf(row)
    ):
        return False
    return (
        row.get("demand_model_name") == UnionEnergySystemEnergyConsumptionParameter.__name__
        and row.get("parent_fk_column") == "id_union_energy_system"
    )


def _is_oes_summary_hidden_tites_verification_row(row: dict[str, Any]) -> bool:
    if row.get("entity_kind") not in (
        "ues_res_sum_check",
        "oes_south_oes_model_verification",
        "res_subject_sum_check",
        "tites_res_energy_unit_sum_check",
    ):
        return False
    label = str(row.get("entity_label") or "").strip()
    prefix = "Проверка для "
    if not label.startswith(prefix):
        return False
    target = label[len(prefix) :].strip()
    return _is_oes_summary_hidden_tites_union_energy_system_label(target)


def filter_oes_summary_hidden_tites_union_energy_system_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """На /summary/oes/ убирает строки ОЭС «ТИТЭС Сибири» / «ТИТЭС Востока» и «Проверка для …»."""
    if not summary_rows:
        return []
    return [
        row
        for row in summary_rows
        if not _is_oes_summary_hidden_tites_union_energy_system_own_row(row)
        and not _is_oes_summary_hidden_tites_verification_row(row)
    ]


_OES_MAX_SUMMARY_HIDDEN_RES_BASE_LABELS_CF = frozenset(
    {
        "эс г. норильска красноярского края".casefold().replace(" ", ""),
    }
)


def _normalized_summary_entity_base_label_compact_cf(label: object) -> str:
    base, _ = _strip_summary_table_variant_suffixes_from_label(str(label or ""))
    return base.casefold().replace(" ", "")


def _is_oes_max_summary_hidden_regional_energy_system_label(label: object) -> bool:
    return (
        _normalized_summary_entity_base_label_compact_cf(label)
        in _OES_MAX_SUMMARY_HIDDEN_RES_BASE_LABELS_CF
    )


def _is_oes_max_summary_hidden_res_verification_row(row: dict[str, Any]) -> bool:
    label = str(row.get("entity_label") or "").strip()
    prefix = "Проверка для "
    if not label.startswith(prefix):
        return False
    target = label[len(prefix) :].strip()
    if _is_oes_max_summary_hidden_regional_energy_system_label(target):
        return True
    base, _ = _strip_summary_table_variant_suffixes_from_label(target)
    return _is_oes_max_summary_hidden_regional_energy_system_label(base)


def _is_oes_max_summary_page_hidden_row(row: dict[str, Any]) -> bool:
    """Строки, не показываемые на /energy_consumption/summary/oes/ (режим максимумов).

    Строку «Заряд ГАЭС» (агрегат по России) убираем полностью.
    РЭС «ЭС г. Норильска Красноярского края» не показываем; энергорайоны остаются.
    """
    label = str(row.get("entity_label") or "").strip()
    if label == _SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL:
        return True
    compact = str(row.get("pd_ec_entity_label_compact") or "").strip()
    if compact == _SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL:
        return True
    if (
        row.get("demand_model_name")
        == RegionalEnergySystemEnergyConsumptionParameter.__name__
        and (
            _is_oes_max_summary_hidden_regional_energy_system_label(label)
            or _is_oes_max_summary_hidden_regional_energy_system_label(compact)
        )
    ):
        return True
    if _is_oes_max_summary_hidden_res_verification_row(row):
        return True
    return False


def filter_oes_max_summary_page_hidden_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """На /summary/oes/: без «Заряд ГАЭС» и без РЭС «ЭС г. Норильска …»."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            if _is_oes_max_summary_page_hidden_row(row):
                i += 1
                continue
            out.append(dict(row))
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        kept = [r for r in block if not _is_oes_max_summary_page_hidden_row(r)]
        if not kept:
            i += block_size
            continue
        for j, r in enumerate(kept):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(kept)
            if j == 0:
                rc["show_entity_note_cell"] = True
            out.append(rc)
        i += block_size
    return out


_SUMMARY_TABLE_HUB_HIDDEN_OES_TITES_VERIFICATION_KINDS = frozenset(
    {
        "ues_res_sum_check",
        "oes_south_oes_model_verification",
        "ues_nt_subject_sum_check",
        "tites_res_energy_unit_sum_check",
        "oes_tites_aggregate_check",
    }
)


def _is_summary_table_hub_hidden_oes_or_tites_verification_row(
    row: dict[str, Any],
) -> bool:
    """Строки «Проверка для …» по ОЭС/ТИТЭС — не показываем на /summary_table/ (корень)."""
    if _is_oes_summary_hidden_tites_verification_row(row):
        return True
    ek = str(row.get("entity_kind") or "")
    if ek not in _SUMMARY_TABLE_HUB_HIDDEN_OES_TITES_VERIFICATION_KINDS:
        return False
    return str(row.get("entity_label") or "").strip().startswith("Проверка для ")


def filter_summary_table_hub_oes_and_tites_verification_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """На /energy_consumption/summary_table/ убирает «Проверка для …» по ОЭС и ТИТЭС."""
    if not summary_rows:
        return []
    return [
        row
        for row in summary_rows
        if not _is_summary_table_hub_hidden_oes_or_tites_verification_row(row)
    ]


def filter_summary_rows_for_summary_table_page(
    summary_rows: list[dict[str, Any]],
    *,
    keep_gaes_charge_territory_rows: bool = False,
) -> list[dict[str, Any]]:
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    rd_model = RegionalDistrictEnergyConsumptionParameter.__name__
    for row in summary_rows:
        if row.get("demand_model_name") == rd_model:
            continue
        if (
            not keep_gaes_charge_territory_rows
            and _summary_table_hide_gaes_charge_territory_row(row)
        ):
            continue
        if row.get("pd_ec_territory_detail_row"):
            if (
                keep_gaes_charge_territory_rows
                and row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
            ):
                out.append(row)
            continue
        out.append(row)
    return out


def _find_summary_parameter_row(
    rows: list[dict[str, Any]],
    *,
    parameter_key: str,
    demand_model_name: str | None = None,
    parent_fk_column: str | None = None,
    parent_id: int | None = None,
    perimeter_variant_code: str | None = None,
    entity_kind: str | None = None,
) -> dict[str, Any] | None:
    for row in rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if demand_model_name is not None and row.get("demand_model_name") != demand_model_name:
            continue
        if parent_fk_column is not None and row.get("parent_fk_column") != parent_fk_column:
            continue
        if parent_id is not None and row.get("parent_id") != parent_id:
            continue
        if row.get("perimeter_variant_code") != perimeter_variant_code:
            continue
        if entity_kind is not None and row.get("entity_kind") != entity_kind:
            continue
        return row
    return None


def _sum_summary_parameter_rows_by_year(
    rows: list[dict[str, Any]],
    *,
    years: list[int],
    parameter_key: str,
    demand_model_name: str,
    id_union_energy_system: int | None = None,
    parent_fk_column: str | None = None,
    parent_id: int | None = None,
) -> dict[int, Decimal | None]:
    sums: dict[int, Decimal] = {}
    seen: set[int] = set()
    for row in rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if row.get("demand_model_name") != demand_model_name:
            continue
        if id_union_energy_system is not None and row.get("id_union_energy_system") != id_union_energy_system:
            continue
        if parent_fk_column is not None and row.get("parent_fk_column") != parent_fk_column:
            continue
        if parent_id is not None and row.get("parent_id") != parent_id:
            continue
        if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(
            row.get("perimeter_variant_code")
        ):
            continue
        values = _raw_year_values_from_summary_row(row, years)
        for year, value in values.items():
            if value is None:
                continue
            sums[year] = sums.get(year, Decimal(0)) + value
            seen.add(year)
    return {int(year): sums.get(int(year)) if int(year) in seen else None for year in years}


def _count_summary_entity_blocks(
    rows: list[dict[str, Any]],
    *,
    demand_model_name: str,
    parent_fk_column: str | None = None,
    parent_id: int | None = None,
) -> int:
    count = 0
    for row in rows:
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != demand_model_name:
            continue
        if parent_fk_column is not None and row.get("parent_fk_column") != parent_fk_column:
            continue
        if parent_id is not None and row.get("parent_id") != parent_id:
            continue
        count += 1
    return count


def _is_union_energy_system_oes_summary_top_block_start(row: dict[str, Any]) -> bool:
    """Строка уровня ОЭС на сводке (вариант периметра или агрегат, не заряд ГAЭС)."""
    if not row.get("show_entity_cell"):
        return False
    if row.get("demand_model_name") != UnionEnergySystemEnergyConsumptionParameter.__name__:
        return False
    if row.get("parent_fk_column") != "id_union_energy_system":
        return False
    if _summary_row_skip_oes_gaes_charge_verification(row):
        return False
    return str(row.get("entity_kind") or "") in ("group", "perimeter_variant")


def _is_union_energy_system_oes_summary_same_depth_sibling(
    row: dict[str, Any],
    *,
    ues_model: str,
    ues_id: Any,
) -> bool:
    return (
        row.get("demand_model_name") == ues_model
        and row.get("parent_fk_column") == "id_union_energy_system"
        and row.get("parent_id") == ues_id
    )


def _summary_subtree_end_index(
    summary_rows: list[dict[str, Any]],
    start_index: int,
    *,
    ues_model: str,
) -> int:
    """Последняя строка поддерева сущности (все дочерние РЭС/субъекты включительно)."""
    start = summary_rows[start_index]
    base_depth = int(start.get("entity_depth") or 0)
    ues_id = start.get("parent_id")
    end = start_index + max(int(start.get("entity_rowspan") or 1), 1) - 1
    i = end + 1
    while i < len(summary_rows):
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= base_depth:
                if _is_union_energy_system_oes_summary_same_depth_sibling(
                    row,
                    ues_model=ues_model,
                    ues_id=ues_id,
                ):
                    pass
                else:
                    break
            block_size = max(int(row.get("entity_rowspan") or 1), 1)
            end = i + block_size - 1
            i += block_size
        else:
            end = i
            i += 1
    return end


def _iter_union_energy_system_subtree_spans(
    summary_rows: list[dict[str, Any]],
) -> list[tuple[int, int, Any]]:
    """Интервалы [start, end] по каждой ОЭС (все варианты периметра и дочерние территории)."""
    ues_model = UnionEnergySystemEnergyConsumptionParameter.__name__
    spans: list[tuple[int, int, Any]] = []
    seen_ues_ids: set[Any] = set()
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_union_energy_system_oes_summary_top_block_start(row):
            i += 1
            continue
        ues_id = row.get("parent_id")
        if ues_id in seen_ues_ids:
            i += max(int(row.get("entity_rowspan") or 1), 1)
            continue
        seen_ues_ids.add(ues_id)
        end = _summary_subtree_end_index(summary_rows, i, ues_model=ues_model)
        spans.append((i, end, ues_id))
        i = end + 1
    return spans


_OES_RES_WITHOUT_GAES_VERIFICATION_TOOLTIP = (
    "Проверка = потребление ЭЭ РЭС с зарядом ГАЭС − "
    "сумма потребления ЭЭ субъектов РФ, входящих в РЭС "
    "(для субъектов с зарядом ГАЭС — значение «с зарядом ГАЭС»)"
)

_TITES_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP = (
    "Проверка для ЭС = потребление ЭЭ ЭС − "
    "сумма потребления ЭЭ энергорайонов без варианта o1, входящих в ЭС"
)

_EAST_EZ_O1_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP = (
    "Проверка = потребление ЭЭ РЭС (О-1) − "
    "сумма потребления ЭЭ энергорайонов (О-1), входящих в РЭС"
)
_CHUKOTKA_O1_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP = (
    "Проверка = потребление ЭЭ РЭС (О-1) − "
    "сумма потребления ЭЭ энергорайонов (О-1), входящих в РЭС; "
    f"вместо «{_CHAUN_BILIBINO_EU_LABEL}» — "
    f"«{_CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL}» (О-1)"
)


def _find_oes_res_with_gaes_main_parameter_row(
    rows: list[dict[str, Any]],
    *,
    res_id_int: int,
    parameter_key: str,
    demand_model_name: str,
) -> dict[str, Any] | None:
    """Строка потребления РЭС «с зарядом ГAЭС» для проверки блока «без заряда ГAЭС»."""
    for row in rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if row.get("demand_model_name") != demand_model_name:
            continue
        if row.get("parent_fk_column") != "id_regional_energy_system":
            continue
        if row.get("parent_id") != res_id_int:
            continue
        if row.get("pd_ec_res_without_gaes_injected_row"):
            continue
        if row.get("pd_ec_gaes_injected_row"):
            continue
        return row
    return None


def _is_oes_res_gaes_verification_subject_block_start(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != RegionalDistrictEnergyConsumptionParameter.__name__:
        return False
    if row.get("pd_ec_rd_without_gaes_injected_row"):
        return False
    if row.get("pd_ec_gaes_injected_row"):
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    return True


def _sum_oes_res_gaes_split_verification_subjects_by_year(
    rows: list[dict[str, Any]],
    *,
    res_start_index: int,
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    """Сумма субъектов РЭС для проверки «без заряда ГAЭС»: «с зарядом ГAЭС» / основное значение."""
    subject_block_starts = _res_subtree_direct_subject_block_start_indices(
        rows,
        res_start_index,
    )
    filtered_starts = [
        index
        for index in subject_block_starts
        if _is_oes_res_gaes_verification_subject_block_start(rows[index])
    ]
    return _sum_summary_entity_blocks_parameter_by_year(
        rows,
        filtered_starts,
        years=years,
        parameter_key=parameter_key,
        demand_model_name=RegionalDistrictEnergyConsumptionParameter.__name__,
    )


def _res_subtree_direct_subject_block_start_indices(
    summary_rows: list[dict[str, Any]],
    res_start_index: int,
) -> list[int]:
    """Индексы блоков субъектов РФ — прямых потомков РЭС в дереве сводки."""
    if res_start_index < 0 or res_start_index >= len(summary_rows):
        return []
    res_row = summary_rows[res_start_index]
    if (
        not res_row.get("show_entity_cell")
        or res_row.get("demand_model_name")
        != RegionalEnergySystemEnergyConsumptionParameter.__name__
    ):
        return []
    res_depth = int(res_row.get("entity_depth") or 0)
    rd_model = RegionalDistrictEnergyConsumptionParameter.__name__
    indices: list[int] = []
    index = res_start_index + max(int(res_row.get("entity_rowspan") or 1), 1)
    while index < len(summary_rows):
        row = summary_rows[index]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= res_depth:
                break
            if row.get("demand_model_name") == rd_model and row_depth == res_depth + 1:
                if not (
                    row.get("pd_ec_o1_form_row")
                    or is_o1_perimeter_variant_code(row.get("perimeter_variant_code"))
                ):
                    indices.append(index)
            index += max(int(row.get("entity_rowspan") or 1), 1)
        else:
            index += 1
    return indices


def _is_oes_non_o1_energy_unit_verification_block_start(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != EnergyUnitEnergyConsumptionParameter.__name__:
        return False
    if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(
        row.get("perimeter_variant_code")
    ):
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("pd_ec_gaes_injected_row"):
        return False
    return True


def _is_o1_energy_unit_verification_block_start(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != EnergyUnitEnergyConsumptionParameter.__name__:
        return False
    if not (
        row.get("pd_ec_o1_form_row")
        or is_o1_perimeter_variant_code(row.get("perimeter_variant_code"))
    ):
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("pd_ec_gaes_injected_row"):
        return False
    return True


def _res_subtree_o1_energy_unit_block_start_indices(
    summary_rows: list[dict[str, Any]],
    res_start_index: int,
) -> list[int]:
    """Индексы блоков энергорайонов (О-1) в поддереве РЭС."""
    if res_start_index < 0 or res_start_index >= len(summary_rows):
        return []
    res_row = summary_rows[res_start_index]
    if (
        not res_row.get("show_entity_cell")
        or res_row.get("demand_model_name")
        != RegionalEnergySystemEnergyConsumptionParameter.__name__
    ):
        return []
    res_depth = int(res_row.get("entity_depth") or 0)
    indices: list[int] = []
    index = res_start_index + max(int(res_row.get("entity_rowspan") or 1), 1)
    while index < len(summary_rows):
        row = summary_rows[index]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= res_depth:
                break
            if _is_o1_energy_unit_verification_block_start(row):
                indices.append(index)
            index += max(int(row.get("entity_rowspan") or 1), 1)
        else:
            index += 1
    return indices


def _res_subtree_end_index(
    summary_rows: list[dict[str, Any]],
    res_start_index: int,
) -> int:
    """Последняя строка поддерева РЭС (включая дочерние энергорайоны)."""
    if res_start_index < 0 or res_start_index >= len(summary_rows):
        return res_start_index
    res_row = summary_rows[res_start_index]
    res_depth = int(res_row.get("entity_depth") or 0)
    end = res_start_index + max(int(res_row.get("entity_rowspan") or 1), 1) - 1
    index = end + 1
    while index < len(summary_rows):
        row = summary_rows[index]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= res_depth:
                break
            block_size = max(int(row.get("entity_rowspan") or 1), 1)
            end = index + block_size - 1
            index += block_size
        else:
            end = index
            index += 1
    return end


def _res_subtree_non_o1_energy_unit_block_start_indices(
    summary_rows: list[dict[str, Any]],
    res_start_index: int,
) -> list[int]:
    """Индексы блоков энергорайонов без o1 в поддереве РЭС на сводке ОЭС."""
    if res_start_index < 0 or res_start_index >= len(summary_rows):
        return []
    res_row = summary_rows[res_start_index]
    if (
        not res_row.get("show_entity_cell")
        or res_row.get("demand_model_name")
        != RegionalEnergySystemEnergyConsumptionParameter.__name__
    ):
        return []
    res_depth = int(res_row.get("entity_depth") or 0)
    indices: list[int] = []
    index = res_start_index + max(int(res_row.get("entity_rowspan") or 1), 1)
    while index < len(summary_rows):
        row = summary_rows[index]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= res_depth:
                break
            if _is_oes_non_o1_energy_unit_verification_block_start(row):
                indices.append(index)
            index += max(int(row.get("entity_rowspan") or 1), 1)
        else:
            index += 1
    return indices


def _res_summary_row_belongs_to_tites_branch(
    summary_rows: list[dict[str, Any]],
    res_row: dict[str, Any],
) -> bool:
    """РЭС в ветке ТИТЭС — по id_union_energy_system и подписи родительской ОЭС в сводке."""
    ues_id = res_row.get("id_union_energy_system")
    if ues_id is None:
        return False
    ues_model = UnionEnergySystemEnergyConsumptionParameter.__name__
    tites_labels_cf = {
        _TITES_TYPE_LABEL_CF,
        TITES_EAST_UES_NAME_CF.replace(" ", ""),
        TITES_SIBERIA_UES_NAME_CF.replace(" ", ""),
    }
    for row in summary_rows:
        if row.get("demand_model_name") != ues_model:
            continue
        if row.get("parent_fk_column") != "id_union_energy_system":
            continue
        if row.get("parent_id") != ues_id:
            continue
        if not row.get("show_entity_cell"):
            continue
        if _summary_row_base_label_cf(row).replace(" ", "") in tites_labels_cf:
            return True
    return False


def _sum_summary_entity_blocks_parameter_by_year(
    rows: list[dict[str, Any]],
    block_start_indices: list[int],
    *,
    years: list[int],
    parameter_key: str,
    demand_model_name: str,
) -> dict[int, Decimal | None]:
    sums: dict[int, Decimal] = {}
    seen: set[int] = set()
    for start_index in block_start_indices:
        if start_index < 0 or start_index >= len(rows):
            continue
        block_size = max(int(rows[start_index].get("entity_rowspan") or 1), 1)
        for index in range(start_index, min(start_index + block_size, len(rows))):
            row = rows[index]
            if row.get("parameter_key") != parameter_key:
                continue
            if row.get("demand_model_name") != demand_model_name:
                continue
            values = _raw_year_values_from_summary_row(row, years)
            for year, value in values.items():
                if value is None:
                    continue
                sums[year] = sums.get(year, Decimal(0)) + value
                seen.add(year)
    return {int(year): sums.get(int(year)) if int(year) in seen else None for year in years}


def _insert_summary_rows_after_indices(
    summary_rows: list[dict[str, Any]],
    insertions_after: dict[int, list[dict[str, Any]]],
) -> None:
    if not insertions_after:
        return
    out: list[dict[str, Any]] = []
    for index, row in enumerate(summary_rows):
        out.append(row)
        extra = insertions_after.get(index)
        if extra:
            out.extend(extra)
    summary_rows[:] = out


def _append_summary_verification_rows_after_blocks(
    summary_rows: list[dict[str, Any]],
    rows_by_start_index: dict[int, list[dict[str, Any]]],
) -> None:
    if not rows_by_start_index:
        return
    out: list[dict[str, Any]] = []
    pending_by_end_index = dict(rows_by_start_index)
    for index, row in enumerate(summary_rows):
        out.append(row)
        if row.get("show_entity_cell"):
            block_size = int(row.get("entity_rowspan") or 1)
            if block_size < 1:
                block_size = 1
            last_block_index = index + block_size - 1
            verification_rows = pending_by_end_index.pop(index, None)
            if verification_rows is not None:
                pending_by_end_index[last_block_index] = verification_rows
        verification_rows = pending_by_end_index.pop(index, None)
        if verification_rows is not None:
            out.extend(verification_rows)
    summary_rows[:] = out


def _summary_row_skip_oes_gaes_charge_verification(row: dict[str, Any]) -> bool:
    """Строки «(заряд ГАЭС)» не участвуют в «Проверка для …» на сводке ОЭС."""
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return True
    if row.get("pd_ec_gaes_injected_row"):
        return True
    return "(заряд гаэс)" in str(row.get("entity_label") or "").casefold()


def _is_south_crimea_sev_res_summary_row(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != RegionalEnergySystemEnergyConsumptionParameter.__name__:
        return False
    if row.get("parent_fk_column") != "id_regional_energy_system":
        return False
    return _summary_row_base_label_cf(row) == SOUTH_CRIMEA_SEV_RES_BASE_LABEL_CF


def _sum_south_crimea_sev_res_parameter_by_year(
    rows: list[dict[str, Any]],
    *,
    years: list[int],
    parameter_key: str,
    ues_id_int: int,
) -> dict[int, Decimal | None]:
    sums: dict[int, Decimal] = {}
    seen: set[int] = set()
    for row in rows:
        if not _is_south_crimea_sev_res_summary_row(row):
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if row.get("id_union_energy_system") not in (None, ues_id_int):
            continue
        values = _raw_year_values_from_summary_row(row, years)
        for year, value in values.items():
            if value is None:
                continue
            sums[year] = sums.get(year, Decimal(0)) + value
            seen.add(year)
    return {int(year): sums.get(int(year)) if int(year) in seen else None for year in years}


def _exclude_south_crimea_sev_res_from_verification_sum_by_year(
    total: dict[int, Decimal | None],
    crimea: dict[int, Decimal | None],
    *,
    years: list[int],
    through_year: int = SOUTH_UES_VERIFICATION_EXCLUDE_CRIMEA_SEV_THROUGH_YEAR,
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        total_value = total.get(y)
        if total_value is None:
            out[y] = None
            continue
        if y <= int(through_year):
            crimea_value = crimea.get(y) or Decimal(0)
            out[y] = total_value - crimea_value
        else:
            out[y] = total_value
    return out


def _sum_south_nt_ec_for_verification(
    rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    south_ues_id: int,
) -> dict[int, Decimal | None]:
    """Потребление ЭЭ «Новыми территориями» под ОЭС Юга для проверки варианта с НТ."""
    ec_key = "energy_consumption_mln_kvt_ch"
    for row in rows:
        if row.get("entity_kind") != "fo_nt_under_south":
            continue
        if row.get("parameter_key") != ec_key:
            continue
        return _raw_year_values_from_summary_row(row, years)
    nt_rows = _build_new_territories_subjects_summary_rows(
        years=years,
        rounding_digits=rounding_digits,
        south_ues_id=south_ues_id,
        summary_rows=rows,
    )
    for row in nt_rows:
        if row.get("entity_kind") == "fo_nt_under_south" and row.get("parameter_key") == ec_key:
            return _raw_year_values_from_summary_row(row, years)
    return {int(y): None for y in years}


def inject_oes_summary_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    ues_res_sum_source_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Строки «Проверка для …» / «Проверка ЕЭС …» на сводке ОЭС (скрыты до кнопки «Проверка»)."""
    if not summary_rows or not source_rows or not years:
        return
    ues_res_rows = (
        ues_res_sum_source_rows
        if ues_res_sum_source_rows is not None
        else source_rows
    )
    if any(
        str(row.get("entity_kind") or "")
        in (
            "ues_res_sum_check",
            "res_subject_sum_check",
            "tites_res_energy_unit_sum_check",
            "oes_ees_model_verification",
            "oes_south_oes_model_verification",
        )
        for row in summary_rows
    ):
        return

    ues_model = UnionEnergySystemEnergyConsumptionParameter.__name__
    res_model = RegionalEnergySystemEnergyConsumptionParameter.__name__
    rd_model = RegionalDistrictEnergyConsumptionParameter.__name__
    eu_model = EnergyUnitEnergyConsumptionParameter.__name__
    ees_model = EesRussiaEnergyConsumptionParameter.__name__
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"

    insertions_after: dict[int, list[dict[str, Any]]] = {}
    ues_sum_ec: dict[int, Decimal | None] | None = None
    ues_sum_sipr: dict[int, Decimal | None] | None = None

    def _is_south_union_energy_system_summary_row(row: dict[str, Any]) -> bool:
        return _summary_row_base_label_cf(row) == SOUTH_UES_NAME_CF

    def _is_tites_east_union_energy_system_summary_row(row: dict[str, Any]) -> bool:
        base = _summary_row_base_label_cf(row).replace(" ", "")
        return base == TITES_EAST_UES_NAME_CF.replace(" ", "")

    def _build_ues_verification_at(start_index: int) -> list[dict[str, Any]] | None:
        nonlocal ues_sum_ec, ues_sum_sipr
        row = summary_rows[start_index]
        ues_id = row.get("parent_id")
        if ues_id is None:
            return None
        try:
            ues_id_int = int(ues_id)
        except (TypeError, ValueError):
            return None
        perimeter_variant_code = row.get("perimeter_variant_code")
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=ues_model,
            parent_fk_column="id_union_energy_system",
            parent_id=ues_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=ues_model,
            parent_fk_column="id_union_energy_system",
            parent_id=ues_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        if base_ec_row is None or base_sipr_row is None:
            return None
        child_ec = _sum_summary_parameter_rows_by_year(
            ues_res_rows,
            years=years,
            parameter_key=ec_key,
            demand_model_name=res_model,
            id_union_energy_system=ues_id_int,
        )
        child_sipr = _sum_summary_parameter_rows_by_year(
            ues_res_rows,
            years=years,
            parameter_key=sipr_key,
            demand_model_name=res_model,
            id_union_energy_system=ues_id_int,
        )
        is_south_ues = _is_south_union_energy_system_summary_row(row)
        if is_south_ues and str(perimeter_variant_code or "") != CODE_WITHOUT_NT_WITH_GAES:
            return None
        if (
            is_south_ues
            and str(perimeter_variant_code or "") == CODE_WITHOUT_NT_WITH_GAES
        ):
            crimea_ec = _sum_south_crimea_sev_res_parameter_by_year(
                ues_res_rows,
                years=years,
                parameter_key=ec_key,
                ues_id_int=ues_id_int,
            )
            crimea_sipr = _sum_south_crimea_sev_res_parameter_by_year(
                ues_res_rows,
                years=years,
                parameter_key=sipr_key,
                ues_id_int=ues_id_int,
            )
            child_ec = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                child_ec,
                crimea_ec,
                years=years,
            )
            child_sipr = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                child_sipr,
                crimea_sipr,
                years=years,
            )
        if is_south_ues and _nt_group_for_variant_code(
            str(perimeter_variant_code or "")
        ) == "with_nt":
            nt_ec = _sum_south_nt_ec_for_verification(
                source_rows,
                years=years,
                rounding_digits=rounding_digits,
                south_ues_id=ues_id_int,
            )
            child_ec = {
                int(y): (child_ec.get(int(y)) or Decimal(0))
                + (nt_ec.get(int(y)) or Decimal(0))
                for y in years
            }
        if perimeter_variant_code in (None, "", CODE_WITHOUT_NT, CODE_WITHOUT_NT_WITH_GAES):
            ues_sum_ec = (
                child_ec
                if ues_sum_ec is None
                else {
                    int(y): (ues_sum_ec.get(int(y)) or Decimal(0))
                    + (child_ec.get(int(y)) or Decimal(0))
                    for y in years
                }
            )
            ues_sum_sipr = (
                child_sipr
                if ues_sum_sipr is None
                else {
                    int(y): (ues_sum_sipr.get(int(y)) or Decimal(0))
                    + (child_sipr.get(int(y)) or Decimal(0))
                    for y in years
                }
            )
        verification_from_year = (
            TITES_EAST_VERIFICATION_FROM_YEAR
            if _is_tites_east_union_energy_system_summary_row(row)
            else None
        )
        return _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''}".strip(),
            entity_kind=(
                "oes_south_oes_model_verification"
                if is_south_ues
                else "ues_res_sum_check"
            ),
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            year_bounds_variant_code=str(perimeter_variant_code or "") or None,
            verification_from_year=verification_from_year,
        )

    def _build_res_verification_at(start_index: int) -> list[dict[str, Any]] | None:
        row = summary_rows[start_index]
        res_id = row.get("parent_id")
        if res_id is None:
            return None
        try:
            res_id_int = int(res_id)
        except (TypeError, ValueError):
            return None
        is_without_gaes_res = bool(row.get("pd_ec_res_without_gaes_injected_row"))
        subject_block_starts = _res_subtree_direct_subject_block_start_indices(
            source_rows,
            start_index,
        )
        if is_without_gaes_res:
            subject_block_starts = [
                index
                for index in subject_block_starts
                if _is_oes_res_gaes_verification_subject_block_start(source_rows[index])
            ]
        if len(subject_block_starts) <= 1:
            return None
        perimeter_variant_code = row.get("perimeter_variant_code")
        if is_without_gaes_res:
            base_ec_row = _find_oes_res_with_gaes_main_parameter_row(
                summary_rows,
                res_id_int=res_id_int,
                parameter_key=ec_key,
                demand_model_name=res_model,
            )
            base_sipr_row = _find_oes_res_with_gaes_main_parameter_row(
                summary_rows,
                res_id_int=res_id_int,
                parameter_key=sipr_key,
                demand_model_name=res_model,
            )
            child_ec = _sum_oes_res_gaes_split_verification_subjects_by_year(
                source_rows,
                res_start_index=start_index,
                years=years,
                parameter_key=ec_key,
            )
            child_sipr = _sum_oes_res_gaes_split_verification_subjects_by_year(
                source_rows,
                res_start_index=start_index,
                years=years,
                parameter_key=sipr_key,
            )
            formula_tooltip = _OES_RES_WITHOUT_GAES_VERIFICATION_TOOLTIP
        else:
            base_ec_row = _find_summary_parameter_row(
                summary_rows,
                parameter_key=ec_key,
                demand_model_name=res_model,
                parent_fk_column="id_regional_energy_system",
                parent_id=res_id_int,
                perimeter_variant_code=perimeter_variant_code,
            )
            base_sipr_row = _find_summary_parameter_row(
                summary_rows,
                parameter_key=sipr_key,
                demand_model_name=res_model,
                parent_fk_column="id_regional_energy_system",
                parent_id=res_id_int,
                perimeter_variant_code=perimeter_variant_code,
            )
            child_ec = _sum_summary_entity_blocks_parameter_by_year(
                source_rows,
                subject_block_starts,
                years=years,
                parameter_key=ec_key,
                demand_model_name=rd_model,
            )
            child_sipr = _sum_summary_entity_blocks_parameter_by_year(
                source_rows,
                subject_block_starts,
                years=years,
                parameter_key=sipr_key,
                demand_model_name=rd_model,
            )
            formula_tooltip = None
        if base_ec_row is None or base_sipr_row is None:
            return None
        return _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''}".strip(),
            entity_kind="res_subject_sum_check",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=formula_tooltip,
        )

    def _build_tites_res_energy_unit_verification_at(
        start_index: int,
    ) -> list[dict[str, Any]] | None:
        row = summary_rows[start_index]
        if not _res_summary_row_belongs_to_tites_branch(summary_rows, row):
            return None
        res_id = row.get("parent_id")
        if res_id is None:
            return None
        try:
            res_id_int = int(res_id)
        except (TypeError, ValueError):
            return None
        eu_block_starts = _res_subtree_non_o1_energy_unit_block_start_indices(
            source_rows,
            start_index,
        )
        if len(eu_block_starts) <= 1:
            return None
        perimeter_variant_code = row.get("perimeter_variant_code")
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=res_model,
            parent_fk_column="id_regional_energy_system",
            parent_id=res_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=res_model,
            parent_fk_column="id_regional_energy_system",
            parent_id=res_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        if base_ec_row is None or base_sipr_row is None:
            return None
        child_ec = _sum_summary_entity_blocks_parameter_by_year(
            source_rows,
            eu_block_starts,
            years=years,
            parameter_key=ec_key,
            demand_model_name=eu_model,
        )
        child_sipr = _sum_summary_entity_blocks_parameter_by_year(
            source_rows,
            eu_block_starts,
            years=years,
            parameter_key=sipr_key,
            demand_model_name=eu_model,
        )
        return _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''}".strip(),
            entity_kind="tites_res_energy_unit_sum_check",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=_TITES_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP,
        )

    def _inject_nt_subjects_verification_after_south_block() -> None:
        """Добавить «Проверка для Новых территорий» после проверок ОЭС Юга и РЭС (мультисубъектных)."""
        if any(
            str(r.get("entity_label") or "").strip() == "Проверка для Новых территорий"
            for r in summary_rows
        ):
            return
        # В юнит-тестах и при проблемах с БД нельзя ходить в справочники, поэтому
        # извлекаем id из уже построенных summary_rows.
        south_ues_id: int | None = None
        nt_ues_id: int | None = None
        for row in summary_rows:
            if row.get("demand_model_name") != ues_model:
                continue
            if row.get("parent_fk_column") != "id_union_energy_system":
                continue
            pid = row.get("parent_id")
            try:
                pid_int = int(pid) if pid is not None else None
            except (TypeError, ValueError):
                pid_int = None
            if pid_int is None:
                continue
            base_label_cf = _summary_row_base_label_cf(row)
            if base_label_cf == SOUTH_UES_NAME_CF:
                south_ues_id = pid_int
            if _NEW_TERRITORIES_UES_NAME_TOKEN_CF in base_label_cf:
                nt_ues_id = pid_int
        if south_ues_id is None or nt_ues_id is None:
            return

        def _find_ues_row_values(
            ues_id: int,
            parameter_key: str,
            *,
            perimeter_variant_code: str,
        ) -> dict[int, Decimal | None]:
            row = _find_summary_parameter_row(
                summary_rows,
                parameter_key=parameter_key,
                demand_model_name=ues_model,
                parent_fk_column="id_union_energy_system",
                parent_id=int(ues_id),
                perimeter_variant_code=perimeter_variant_code,
            )
            if row is not None:
                return _raw_year_values_from_summary_row(row, years)
            # Фоллбек: взять значения напрямую из БД по parent_id и perimeter_variant_code.
            return _year_values_from_parent_demand_rows(
                UnionEnergySystemEnergyConsumptionParameter,
                "id_union_energy_system",
                int(ues_id),
                years,
                parameter_key,
                perimeter_variant_code=perimeter_variant_code,
            )

        south_with_ec = _find_ues_row_values(
            south_ues_id, ec_key, perimeter_variant_code=CODE_WITH_NT_WITH_GAES
        )
        south_without_ec = _find_ues_row_values(
            south_ues_id, ec_key, perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES
        )
        south_with_sipr = _find_ues_row_values(
            south_ues_id, sipr_key, perimeter_variant_code=CODE_WITH_NT_WITH_GAES
        )
        south_without_sipr = _find_ues_row_values(
            south_ues_id, sipr_key, perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES
        )

        base_ec = _subtract_year_value_dicts(years, south_with_ec, south_without_ec)
        base_sipr = _subtract_year_value_dicts(years, south_with_sipr, south_without_sipr)
        if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
            return

        # Сумма субъектов «Новых территорий» (ДНР, ЛНР, Херсонская, Запорожская) по годам.
        sum_ec = _new_territories_parameter_year_values(years, ec_key)
        sum_sipr = _new_territories_parameter_year_values(years, sipr_key)
        if not sum_ec and not sum_sipr:
            return

        # Выравниваем глубину по строкам ОЭС (берём юг как ближайший ориентир).
        ues_depth = next(
            (
                int(r.get("entity_depth") or 1)
                for r in summary_rows
                if r.get("demand_model_name") == ues_model
                and r.get("parent_fk_column") == "id_union_energy_system"
                and r.get("parent_id") == int(south_ues_id)
                and r.get("parameter_key") == ec_key
                and str(r.get("perimeter_variant_code") or "") == CODE_WITH_NT_WITH_GAES
            ),
            1,
        )
        tooltip = (
            "Проверка для Новых территорий = "
            "ОЭС Юга с НТ с зарядом ГАЭС − "
            "ОЭС Юга без НТ с зарядом ГАЭС − "
            "сумма потребления ЭЭ субъектов ФО «Новые территории» "
            "(ДНР, ЛНР, Херсонская область, Запорожская область)"
        )
        rows = _build_ec_summary_verification_rows(
            entity_label="Проверка для Новых территорий",
            entity_kind="ues_nt_subject_sum_check",
            entity_depth=ues_depth,
            years=years,
            rounding_digits=rounding_digits,
            base_ec=base_ec,
            sum_ec=sum_ec,
            base_sipr=base_sipr,
            sum_sipr=sum_sipr,
            formula_tooltip=tooltip,
        )
        if not rows:
            return

        def _insert_after_rowspan_block(start_index: int) -> None:
            start_row = summary_rows[start_index]
            block_size = max(int(start_row.get("entity_rowspan") or 1), 1)
            end_index = min(start_index + block_size - 1, len(summary_rows) - 1)
            summary_rows[end_index + 1 : end_index + 1] = rows

        # Требование: вставить после «Проверка для ЭС Республики Крым и г. Севастополя»
        target_label = "Проверка для ЭС Республики Крым и г. Севастополя"
        for ix, row in enumerate(summary_rows):
            if not row.get("show_entity_cell"):
                continue
            if str(row.get("entity_label") or "").strip() == target_label:
                _insert_after_rowspan_block(ix)
                return

        # Фоллбек: если по какой-то причине целевой строки нет — после блока ОЭС Юга.
        last_south_index: int | None = None
        for ix, row in enumerate(summary_rows):
            if _summary_row_belongs_to_union_energy_system(row, south_ues_id):
                last_south_index = ix
        if last_south_index is None:
            return
        summary_rows[last_south_index + 1 : last_south_index + 1] = rows

    for start_index, end_index, _ues_id in _iter_union_energy_system_subtree_spans(
        summary_rows
    ):
        pending: list[dict[str, Any]] = []
        ues_block_starts: list[int] = []
        res_block_starts: list[int] = []
        index = start_index
        while index <= end_index:
            row = summary_rows[index]
            if row.get("show_entity_cell"):
                block_size = max(int(row.get("entity_rowspan") or 1), 1)
                if _is_union_energy_system_oes_summary_top_block_start(row):
                    ues_block_starts.append(index)
                elif row.get("demand_model_name") == res_model:
                    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY and not row.get(
                        "pd_ec_gaes_injected_row"
                    ):
                        res_block_starts.append(index)
                index += block_size
            else:
                index += 1
        for ues_index in ues_block_starts:
            ues_rows = _build_ues_verification_at(ues_index)
            if ues_rows:
                pending.extend(ues_rows)
        for res_index in res_block_starts:
            res_rows = _build_res_verification_at(res_index)
            if res_rows:
                pending.extend(res_rows)
            tites_res_eu_rows = _build_tites_res_energy_unit_verification_at(res_index)
            if tites_res_eu_rows:
                pending.extend(tites_res_eu_rows)
        if pending:
            insertions_after[end_index] = pending

    ees_rows_by_start: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != ees_model:
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if code and code not in (CODE_WITHOUT_NT, CODE_WITHOUT_NT_WITH_GAES):
            continue
        if ues_sum_ec is None or ues_sum_sipr is None:
            continue
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=ees_model,
            perimeter_variant_code=row.get("perimeter_variant_code"),
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=ees_model,
            perimeter_variant_code=row.get("perimeter_variant_code"),
        )
        if base_ec_row is None or base_sipr_row is None:
            continue
        # «Проверка ЕЭС России без НТ с зарядом ГАЭС» — в inject_first_sa_…_after_ees_russia_rows.
        if "without_nt" in code:
            continue
        label = "Проверка ЕЭС России"
        ees_rows_by_start[index] = _build_ec_summary_verification_rows(
            entity_label=label,
            entity_kind="oes_ees_model_verification",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=ues_sum_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=ues_sum_sipr,
        )
        break

    _insert_summary_rows_after_indices(summary_rows, insertions_after)
    _append_summary_verification_rows_after_blocks(summary_rows, ees_rows_by_start)
    _inject_nt_subjects_verification_after_south_block()


def _split_kaliningrad_suffix_from_label(label: str) -> tuple[str, str | None]:
    s = str(label or "").strip()
    for suffix in _KALININGRAD_ES_LABEL_SUFFIXES:
        parenthesized_suffix = f"({suffix.strip()})"
        if s.endswith(parenthesized_suffix):
            base = s[: -len(parenthesized_suffix)].strip()
            return (base if base else s), suffix.strip()
        if s.endswith(suffix):
            base = s[: -len(suffix)].strip()
            qual = suffix.strip()
            return (base if base else s), qual
    return s, None


def _format_gaes_related_entity_label(base_entity_label: str, infix: str) -> str:
    base, kal_suffix = _split_kaliningrad_suffix_from_label(base_entity_label)
    label = f"{base}{infix}".strip()
    if kal_suffix:
        return f"{label} ({kal_suffix})"
    return label


def _strip_summary_table_variant_suffixes_from_label(label: str) -> tuple[str, str | None]:
    base, kal_suffix = _split_kaliningrad_suffix_from_label(label)
    changed = True
    while changed:
        changed = False
        for suffix in _SUMMARY_TABLE_VARIANT_LABEL_STRIP_SUFFIXES:
            if base.endswith(suffix):
                base = base[: -len(suffix)].strip()
                changed = True
                break
    return (base if base else str(label or "").strip()), kal_suffix


def _nt_label_suffix_for_variant_code(code: str) -> str:
    nt_group = _nt_group_for_variant_code(code)
    if nt_group == "with_nt":
        return _NT_LABEL_SUFFIX_WITH
    if nt_group == "without_nt":
        return _NT_LABEL_SUFFIX_WITHOUT
    return ""


def _gaes_label_suffix_for_variant_code(code: str) -> str:
    if "with_gaes" in code:
        return _GAES_LABEL_SUFFIX_WITH
    if "without_gaes" in code:
        return _GAES_LABEL_SUFFIX_WITHOUT
    return ""


def _ensure_gaes_suffix_in_perimeter_variant_label(
    label: str,
    code: str | None,
) -> str:
    """Добавить «с/без заряда ГАЭС» по коду, если в справочнике суффикс без ГАЭС."""
    s = str(label or "").strip()
    code_s = str(code or "").strip()
    if not s or not code_s:
        return s
    gaes_suffix = _gaes_label_suffix_for_variant_code(code_s)
    if not gaes_suffix:
        return s
    if "гаэс" in s.casefold():
        return s
    return f"{s}{gaes_suffix}".strip()


def _kaliningrad_label_suffix_for_variant_code(code: str) -> str | None:
    if "_with_kaliningrad" in code:
        return _KALININGRAD_ES_LABEL_SUFFIX_WITH.strip()
    if "_without_kaliningrad" in code:
        return _KALININGRAD_ES_LABEL_SUFFIX_WITHOUT.strip()
    return None


def _format_summary_table_variant_entity_label(base_label: str, code: str) -> str:
    base, kal_suffix = _strip_summary_table_variant_suffixes_from_label(base_label)
    kal_suffix = _kaliningrad_label_suffix_for_variant_code(code) or kal_suffix
    label = f"{base}{_nt_label_suffix_for_variant_code(code)}{_gaes_label_suffix_for_variant_code(code)}".strip()
    if kal_suffix:
        return f"{label} ({kal_suffix})"
    return label


def _format_summary_table_entity_label_for_toggle_state(
    base_label: str,
    code: str,
    *,
    nt_detail_on: bool,
    gaes_detail_on: bool,
) -> str:
    base, kal_suffix = _strip_summary_table_variant_suffixes_from_label(base_label)
    kal_suffix = _kaliningrad_label_suffix_for_variant_code(code) or kal_suffix
    nt_suffix = _nt_label_suffix_for_variant_code(code) if nt_detail_on else ""
    gaes_suffix = _gaes_label_suffix_for_variant_code(code) if gaes_detail_on else ""
    label = f"{base}{nt_suffix}{gaes_suffix}".strip()
    if kal_suffix:
        return f"{label} ({kal_suffix})"
    return label


def _format_summary_table_gaes_charge_entity_label(base_label: str, nt_group: str) -> str:
    base, kal_suffix = _strip_summary_table_variant_suffixes_from_label(base_label)
    nt_suffix = ""
    if nt_group == "with_nt":
        nt_suffix = _NT_LABEL_SUFFIX_WITH
    elif nt_group == "without_nt":
        nt_suffix = _NT_LABEL_SUFFIX_WITHOUT
    label = f"{base}{nt_suffix}{_GAES_CHARGE_LABEL_SUFFIX}".strip()
    if kal_suffix:
        return f"{label} ({kal_suffix})"
    return label


def _format_summary_table_gaes_charge_entity_label_for_toggle_state(
    base_label: str,
    nt_group: str,
    *,
    nt_detail_on: bool,
) -> str:
    base, kal_suffix = _strip_summary_table_variant_suffixes_from_label(base_label)
    nt_suffix = ""
    if nt_detail_on:
        if nt_group == "with_nt":
            nt_suffix = _NT_LABEL_SUFFIX_WITH
        elif nt_group == "without_nt":
            nt_suffix = _NT_LABEL_SUFFIX_WITHOUT
    label = f"{base}{nt_suffix}{_GAES_CHARGE_LABEL_SUFFIX}".strip()
    if kal_suffix:
        return f"{label} ({kal_suffix})"
    return label


def apply_energy_consumption_summary_table_variant_toggle_rows(
    rows: list[dict[str, Any]],
) -> None:
    """Сводная таблица: переключатели «+ НТ» / «без заряда ГАЭС» по кодам варианта периметра."""
    reorder_centralized_zone_russia_variant_blocks_in_summary_rows(rows)
    # Если у сущности в данных присутствует только вариант «с НТ» (без «без НТ»),
    # то скрывать его при выключенной кнопке «+НТ» нельзя — иначе на экране не останется ни одной строки.
    # Такое возможно при настройке привязок вариантов периметра на странице /perimeter_variants/.
    nt_groups_by_entity: dict[tuple[Any, ...], set[str]] = {}
    for r in rows:
        code0 = str(r.get("perimeter_variant_code") or "")
        if not code0:
            continue
        pk0 = str(r.get("parameter_key") or "")
        if pk0 == GAES_CHARGE_PARAMETER_KEY:
            continue
        ek0 = (
            r.get("demand_model_name"),
            r.get("parent_fk_column"),
            r.get("parent_id"),
        )
        g0 = _nt_group_for_variant_code(code0)
        if g0 in ("with_nt", "without_nt"):
            nt_groups_by_entity.setdefault(ek0, set()).add(g0)

    current_entity_key: tuple[Any, ...] | None = None
    current_nt_group = ""

    for row in rows:
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        pk = str(row.get("parameter_key") or "")
        if entity_key != current_entity_key:
            current_entity_key = entity_key
            # Строка заряда ГАЭС у «ЕЭС России» идёт с другим demand_model, чем варианты
            # периметра (EesRussia* vs EnergySystemType*); группу НТ не сбрасываем.
            if pk != GAES_CHARGE_PARAMETER_KEY:
                current_nt_group = ""

        code = str(row.get("perimeter_variant_code") or "")

        row.pop("pd_ec_entity_label_compact", None)
        row.pop("pd_ec_entity_label_compact_nt", None)
        row.pop("pd_ec_entity_label_compact_nt_gaes", None)

        if code:
            nt_group = _nt_group_for_variant_code(code)
            if nt_group in ("with_nt", "without_nt"):
                current_nt_group = nt_group
            only_with_nt = (
                nt_group == "with_nt"
                and "with_nt" in nt_groups_by_entity.get(entity_key, set())
                and "without_nt" not in nt_groups_by_entity.get(entity_key, set())
            )
            row["pd_ec_nt_extra_row"] = (nt_group == "with_nt") and not only_with_nt
            row["pd_ec_nt_without_row"] = (nt_group == "without_nt")
            row["pd_ec_gaes_extra_row"] = "with_gaes" in code
            row["pd_ec_gaes_without_row"] = "without_gaes" in code
            base_label = str(row.get("entity_label") or "")
            if _is_kaliningrad_sync_area_summary_table_row(row):
                plain_label = _plain_kaliningrad_sync_area_entity_label(base_label)
                row["entity_label"] = plain_label
                row["pd_ec_entity_label_compact"] = plain_label
                row["pd_ec_entity_label_compact_nt"] = plain_label
                row["pd_ec_entity_label_compact_nt_gaes"] = plain_label
                continue
            row["entity_label"] = _format_summary_table_variant_entity_label(base_label, code)
            row["pd_ec_entity_label_compact"] = (
                _format_summary_table_entity_label_for_toggle_state(
                    base_label,
                    code,
                    nt_detail_on=True,
                    gaes_detail_on=False,
                )
            )
            row["pd_ec_entity_label_compact_nt"] = (
                _format_summary_table_entity_label_for_toggle_state(
                    base_label,
                    code,
                    nt_detail_on=False,
                    gaes_detail_on=True,
                )
            )
            row["pd_ec_entity_label_compact_nt_gaes"] = (
                _format_summary_table_entity_label_for_toggle_state(
                    base_label,
                    code,
                    nt_detail_on=False,
                    gaes_detail_on=False,
                )
            )
            continue

        if pk == GAES_CHARGE_PARAMETER_KEY:
            row["pd_ec_gaes_extra_row"] = True
            row["pd_ec_gaes_without_row"] = False
            row["pd_ec_nt_extra_row"] = current_nt_group == "with_nt"
            row["pd_ec_nt_without_row"] = current_nt_group == "without_nt"
            if current_nt_group in ("with_nt", "without_nt"):
                base_label = str(row.get("entity_label") or "")
                row["entity_label"] = _format_summary_table_gaes_charge_entity_label(
                    base_label, current_nt_group
                )
                row["pd_ec_entity_label_compact_nt"] = (
                    _format_summary_table_gaes_charge_entity_label_for_toggle_state(
                        base_label,
                        current_nt_group,
                        nt_detail_on=False,
                    )
                )
            continue

        row["pd_ec_nt_extra_row"] = False
        row["pd_ec_nt_without_row"] = False
        row["pd_ec_gaes_extra_row"] = False
        row["pd_ec_gaes_without_row"] = False

    _mark_non_o1_perimeter_rows_hidden_when_entity_has_o1_variants(rows)
    _mark_centralized_zone_without_nt_rows_skip_empty_hide(rows)
    _mark_centralized_zone_o1_manual_rows(rows)
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules(rows)
    _mark_summary_table_expanded_nt_gaes_variant_row_rules(rows)
    _mark_summary_table_nt_on_gaes_off_variant_row_rules(rows)
    _mark_collapsed_nt_gaes_visible_rows_skip_empty_hide(rows)


def _mark_collapsed_nt_gaes_visible_rows_skip_empty_hide(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Базовые строки «без НТ» (ОЭС Юга, ЕЭС России, …) не скрываются «Пустые строки»."""
    for row in summary_rows:
        if row.get("pd_ec_collapsed_nt_gaes_visible_row"):
            row["pd_ec_skip_empty_hide_row"] = True


def _is_plain_with_nt_perimeter_variant_code(code: str) -> bool:
    c = str(code or "").strip()
    return bool(c) and not is_o1_perimeter_variant_code(c) and c == CODE_WITH_NT


def _is_plain_without_nt_perimeter_variant_code(code: str) -> bool:
    c = str(code or "").strip()
    return bool(c) and not is_o1_perimeter_variant_code(c) and c == CODE_WITHOUT_NT


def _entity_has_without_nt_gaes_split_variants(codes: set[str]) -> bool:
    return any(
        "without_nt" in c and ("with_gaes" in c or "without_gaes" in c) for c in codes
    )


def _entity_has_with_nt_gaes_split_variants(codes: set[str]) -> bool:
    return any(
        "with_nt" in c and ("with_gaes" in c or "without_gaes" in c) for c in codes
    )


def _mark_summary_table_expanded_nt_gaes_variant_row_rules(
    rows: list[dict[str, Any]],
) -> None:
    """При включённых «+НТ» и «без заряда ГАЭС»: скрыть строку «… с НТ» без разбивки по ГАЭС."""
    codes_by_entity: dict[tuple[Any, ...], set[str]] = {}
    for row in rows:
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if not code or is_o1_perimeter_variant_code(code):
            continue
        entity_key = _perimeter_variant_entity_key(row)
        codes_by_entity.setdefault(entity_key, set()).add(code)

    for row in rows:
        row.pop("pd_ec_expanded_nt_gaes_redundant_row", None)

    for entity_key, codes in codes_by_entity.items():
        if _entity_has_with_nt_gaes_split_variants(codes):
            for row in rows:
                if _perimeter_variant_entity_key(row) != entity_key:
                    continue
                code = str(row.get("perimeter_variant_code") or "").strip()
                if _is_plain_with_nt_perimeter_variant_code(code):
                    row["pd_ec_expanded_nt_gaes_redundant_row"] = True
        if _entity_has_without_nt_gaes_split_variants(codes):
            for row in rows:
                if _perimeter_variant_entity_key(row) != entity_key:
                    continue
                code = str(row.get("perimeter_variant_code") or "").strip()
                if _is_plain_without_nt_perimeter_variant_code(code):
                    row["pd_ec_expanded_nt_gaes_redundant_row"] = True


def _collapsed_nt_gaes_primary_variant_codes_for_entity(
    codes: set[str],
) -> frozenset[str]:
    """Коды вариантов при выкл. «+НТ» и «без заряда ГАЭС»: предпочтительно «с зарядом ГАЭС»."""
    if not codes:
        return frozenset()
    without_nt_without_gaes = frozenset(
        c for c in codes if "without_nt" in c and "without_gaes" in c
    )
    without_nt_with_gaes = frozenset(
        c
        for c in codes
        if "without_nt" in c and "with_gaes" in c and "without_gaes" not in c
    )
    if without_nt_with_gaes:
        return without_nt_with_gaes
    if without_nt_without_gaes:
        return without_nt_without_gaes
    plain_without_nt = frozenset(
        c for c in codes if _nt_group_for_variant_code(c) == "without_nt"
    )
    return plain_without_nt


def _entity_has_with_charge_base_summary_row(
    rows: list[dict[str, Any]],
    entity_key: tuple[Any, ...],
) -> bool:
    """Есть ли у сущности строка «с зарядом» (не инжект «без заряда ГАЭС»).

    У ФО/субъектов РФ основная строка часто без кода варианта, а «без заряда»
    инжектится с ``without_*_without_gaes``. Без этой проверки fallback
    collapsed/nt_on_gaes_off делает инжект primary и дублирует ФО на экране.
    """
    for row in rows:
        if _perimeter_variant_entity_key(row) != entity_key:
            continue
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        if row.get("pd_ec_gaes_without_row"):
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if "without_gaes" in code:
            continue
        return True
    return False


def _plain_labels_for_with_gaes_row_without_stations(row: dict[str, Any]) -> None:
    """Подписи без «с зарядом ГАЭС», если у сущности нет станций ГАЭС."""
    code = str(row.get("perimeter_variant_code") or "").strip()
    base_label, kal_qual = _strip_summary_table_variant_suffixes_from_label(
        str(row.get("entity_label") or "")
    )
    if kal_qual:
        base_label = f"{base_label} ({kal_qual})"
    row["pd_ec_gaes_extra_row"] = False
    row["pd_ec_gaes_without_row"] = False
    row["entity_label"] = _format_summary_table_entity_label_for_toggle_state(
        base_label,
        code,
        nt_detail_on=True,
        gaes_detail_on=False,
    )
    row["pd_ec_entity_label_compact"] = (
        _format_summary_table_entity_label_for_toggle_state(
            base_label,
            code,
            nt_detail_on=True,
            gaes_detail_on=False,
        )
    )
    # При включённой «без заряда ГАЭС» тоже без приписки — split убран.
    row["pd_ec_entity_label_compact_nt"] = (
        _format_summary_table_entity_label_for_toggle_state(
            base_label,
            code,
            nt_detail_on=False,
            gaes_detail_on=False,
        )
    )
    row["pd_ec_entity_label_compact_nt_gaes"] = (
        _format_summary_table_entity_label_for_toggle_state(
            base_label,
            code,
            nt_detail_on=False,
            gaes_detail_on=False,
        )
    )


def collapse_gaes_variant_split_for_entities_without_stations(
    summary_rows: list[dict[str, Any]],
) -> None:
    """У сущностей без станций ГАЭС убираем дубли «с/без заряда» (значения совпадают).

    Пример: «Южный ФО» в привязках имеет with_gaes/without_gaes, но ГАЭС в округе нет —
    при нажатой «без заряда ГАЭС» обе строки одинаковы во всех годах.
    """
    if not summary_rows:
        return

    sample_row_by_entity: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in summary_rows:
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if "with_gaes" not in code and "without_gaes" not in code:
            continue
        ek = _perimeter_variant_entity_key(row)
        sample_row_by_entity.setdefault(ek, row)

    no_station: set[tuple[Any, ...]] = {
        ek
        for ek, sample in sample_row_by_entity.items()
        if not _summary_row_entity_has_gaes_charge(sample)
    }
    if not no_station:
        return

    kept: list[dict[str, Any]] = []
    for row in summary_rows:
        ek = _perimeter_variant_entity_key(row)
        if ek not in no_station:
            kept.append(row)
            continue
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if "without_gaes" in code:
            continue
        if "with_gaes" in code and "without_gaes" not in code:
            _plain_labels_for_with_gaes_row_without_stations(row)
        kept.append(row)
    summary_rows[:] = kept


def _mark_summary_table_collapsed_nt_gaes_variant_row_rules(
    rows: list[dict[str, Any]],
) -> None:
    """«+НТ» и «без заряда ГАЭС» выкл.: короткая подпись и строка «с зарядом ГАЭС»."""
    codes_by_entity: dict[tuple[Any, ...], set[str]] = {}
    for row in rows:
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if not code or is_o1_perimeter_variant_code(code):
            continue
        entity_key = _perimeter_variant_entity_key(row)
        codes_by_entity.setdefault(entity_key, set()).add(code)

    for row in rows:
        row.pop("pd_ec_collapsed_nt_gaes_visible_row", None)
        row.pop("pd_ec_collapsed_nt_gaes_redundant_row", None)

    for entity_key, codes in codes_by_entity.items():
        primary_codes = _collapsed_nt_gaes_primary_variant_codes_for_entity(codes)
        has_with_charge_base = _entity_has_with_charge_base_summary_row(rows, entity_key)
        if has_with_charge_base:
            # Базовая строка уже показывает «с зарядом»; «без заряда» — только по кнопке.
            primary_codes = frozenset(
                c for c in primary_codes if "without_gaes" not in c
            )
        if not primary_codes and not has_with_charge_base:
            continue
        for row in rows:
            if _perimeter_variant_entity_key(row) != entity_key:
                continue
            code = str(row.get("perimeter_variant_code") or "").strip()
            if not code:
                continue
            if code in primary_codes:
                row["pd_ec_collapsed_nt_gaes_visible_row"] = True
            elif "without_gaes" in code and has_with_charge_base:
                row["pd_ec_collapsed_nt_gaes_redundant_row"] = True
            elif _nt_group_for_variant_code(code) == "without_nt":
                row["pd_ec_collapsed_nt_gaes_redundant_row"] = True


def _gaes_kind_in_perimeter_variant_code(code: str) -> str | None:
    if "without_gaes" in code:
        return "without_gaes"
    if "with_gaes" in code:
        return "with_gaes"
    return None


def _mark_summary_table_nt_on_gaes_off_variant_row_rules(
    rows: list[dict[str, Any]],
) -> None:
    """«+НТ» вкл., «без заряда ГАЭС» выкл.: видимы варианты с зарядом ГАЭС (fallback — без)."""
    codes_by_entity: dict[tuple[Any, ...], set[str]] = {}
    for row in rows:
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "").strip()
        if not code or is_o1_perimeter_variant_code(code):
            continue
        entity_key = _perimeter_variant_entity_key(row)
        codes_by_entity.setdefault(entity_key, set()).add(code)

    for row in rows:
        row.pop("pd_ec_nt_on_gaes_off_visible_row", None)
        row.pop("pd_ec_nt_on_gaes_off_redundant_row", None)

    for entity_key, codes in codes_by_entity.items():
        if not any(_gaes_kind_in_perimeter_variant_code(c) for c in codes):
            continue
        has_with_gaes = any(
            _gaes_kind_in_perimeter_variant_code(c) == "with_gaes" for c in codes
        )
        has_with_charge_base = _entity_has_with_charge_base_summary_row(rows, entity_key)
        if has_with_gaes:
            visible_gaes_kind: str | None = "with_gaes"
        elif has_with_charge_base:
            # Базовая строка ФО/субъекта уже «с зарядом» — не поднимать инжект «без».
            visible_gaes_kind = None
        else:
            visible_gaes_kind = "without_gaes"

        visible_nt_groups: set[str] = set()
        if visible_gaes_kind is not None:
            for code in codes:
                if _gaes_kind_in_perimeter_variant_code(code) != visible_gaes_kind:
                    continue
                nt_group = _nt_group_for_variant_code(code)
                if nt_group in ("with_nt", "without_nt"):
                    visible_nt_groups.add(nt_group)

        for row in rows:
            if _perimeter_variant_entity_key(row) != entity_key:
                continue
            code = str(row.get("perimeter_variant_code") or "").strip()
            if not code:
                continue
            gaes_kind = _gaes_kind_in_perimeter_variant_code(code)
            if visible_gaes_kind is not None and gaes_kind == visible_gaes_kind:
                row["pd_ec_nt_on_gaes_off_visible_row"] = True
                base_label = str(row.get("entity_label") or "")
                row["pd_ec_entity_label_compact"] = (
                    _format_summary_table_entity_label_for_toggle_state(
                        base_label,
                        code,
                        nt_detail_on=True,
                        gaes_detail_on=False,
                    )
                )
            elif gaes_kind is not None:
                row["pd_ec_nt_on_gaes_off_redundant_row"] = True
            else:
                nt_group = _nt_group_for_variant_code(code)
                if nt_group in visible_nt_groups:
                    row["pd_ec_nt_on_gaes_off_redundant_row"] = True


def _perimeter_variant_entity_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("demand_model_name"),
        row.get("parent_fk_column"),
        row.get("parent_id"),
    )


def _mark_non_o1_perimeter_rows_hidden_when_entity_has_o1_variants(
    rows: list[dict[str, Any]],
) -> None:
    """При «Форма О-1» скрываем кодовые non-O-1 варианты (напр. ЦЗ с/без НТ), не базовые NULL."""
    entities_with_o1: set[tuple[Any, ...]] = set()
    for row in rows:
        code = str(row.get("perimeter_variant_code") or "")
        if not code or str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        if is_o1_perimeter_variant_code(code):
            entities_with_o1.add(_perimeter_variant_entity_key(row))

    for row in rows:
        row.pop("pd_ec_hide_when_isolated_eu_on", None)
        code = str(row.get("perimeter_variant_code") or "")
        # Базовые строки без варианта (NULL) всегда остаются — O-1 добавляются к ним.
        if not code or str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            continue
        if (
            _perimeter_variant_entity_key(row) in entities_with_o1
            and not is_o1_perimeter_variant_code(code)
        ):
            row["pd_ec_hide_when_isolated_eu_on"] = True


def _mark_centralized_zone_without_nt_rows_skip_empty_hide(
    summary_rows: list[dict[str, Any]],
) -> None:
    """«ЦЗ России без НТ» (включая O-1) не скрываются режимом «Пустые строки»."""
    for row in summary_rows:
        if not row.get("pd_ec_nt_without_row"):
            continue
        if not _is_centralized_zone_russia_summary_row(row):
            continue
        row["pd_ec_skip_empty_hide_row"] = True


def apply_summary_table_russia_federation_row_rules(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Сводная таблица: «Россия» — только with_nt; +НТ выкл. → «Россия», +НТ вкл. → «Россия с НТ»."""
    base_label = RUSSIA_FEDERATION_AGGREGATE_NAME
    label_with_nt = f"{base_label}{_NT_LABEL_SUFFIX_WITH}".strip()
    kept: list[dict[str, Any]] = []
    for row in summary_rows:
        if row.get("entity_kind") != ENTITY_KIND_RUSSIA_FEDERATION:
            kept.append(row)
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if code and not code.startswith("with_nt"):
            continue
        if not code and row.get("pd_ec_nt_without_row"):
            continue

        row["pd_ec_nt_extra_row"] = False
        row["pd_ec_nt_without_row"] = False
        row["pd_ec_skip_perimeter_variant_year_bounds"] = True
        pk = str(row.get("parameter_key") or "")
        if pk == GAES_CHARGE_PARAMETER_KEY:
            gaes_label = _SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL
            row["entity_label"] = gaes_label
            row["pd_ec_entity_label_compact"] = gaes_label
            row["pd_ec_entity_label_compact_nt"] = gaes_label
            row["pd_ec_entity_label_compact_nt_gaes"] = gaes_label
        else:
            row["entity_label"] = label_with_nt
            row["pd_ec_entity_label_compact"] = label_with_nt
            row["pd_ec_entity_label_compact_nt"] = base_label
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
        kept.append(row)
    summary_rows[:] = kept


def _resolve_union_energy_system_id_by_name_cf(name_cf: str) -> int | None:
    target = (name_cf or "").strip().casefold()
    if not target:
        return None
    query = UnionEnergySystem.query
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    for ues in query.all():
        if (getattr(ues, "name", None) or "").strip().casefold() == target:
            return int(ues.id)
    return None


def _resolve_federal_district_id_by_name_cf(name_cf: str) -> int | None:
    target = (name_cf or "").strip().casefold()
    if not target:
        return None
    query = FederalDistrict.query
    query = dps.filter_parents_by_version(query, FederalDistrict)
    for fd in query.all():
        if (getattr(fd, "name", None) or "").strip().casefold() == target:
            return int(fd.id)
    return None


def _resolve_new_territories_union_energy_system_id() -> int | None:
    query = UnionEnergySystem.query
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    for ues in query.all():
        name_cf = (getattr(ues, "name", None) or "").strip().casefold()
        if _NEW_TERRITORIES_UES_NAME_TOKEN_CF in name_cf:
            return int(ues.id)
    return None


def _regional_district_ids_for_union_energy_system(ues_id: int) -> list[int]:
    ues = db.session.get(UnionEnergySystem, int(ues_id))
    if ues is None:
        return []
    out: list[int] = []
    seen: set[int] = set()
    for res in ues.regional_energy_systems or []:
        for rd in res.regional_districts or []:
            if not _is_valid_named_item(rd):
                continue
            rd_id = int(rd.id)
            if rd_id in seen:
                continue
            seen.add(rd_id)
            out.append(rd_id)
    return out


def _load_new_territories_regional_districts() -> list[RegionalDistrict]:
    """Субъекты РФ, входящие в ФО «Новые территории» (текущая версия)."""
    query = FederalDistrict.query.options(selectinload(FederalDistrict.regional_districts))
    query = dps.filter_parents_by_version(query, FederalDistrict)
    fd = next(
        (
            f
            for f in query.all()
            if (getattr(f, "name", None) or "").strip().casefold() == _NEW_TERRITORIES_FD_NAME_CF
        ),
        None,
    )
    if fd is None:
        return []
    return [
        rd
        for rd in sorted(getattr(fd, "regional_districts", None) or [], key=_sort_by_name)
        if _is_valid_named_item(rd)
    ]


def _summary_row_belongs_to_union_energy_system(
    row: dict[str, Any],
    ues_id: int,
) -> bool:
    if row.get("id_union_energy_system") == ues_id:
        return True
    if (
        row.get("demand_model_name") == UnionEnergySystemEnergyConsumptionParameter.__name__
        and row.get("parent_fk_column") == "id_union_energy_system"
        and row.get("parent_id") == ues_id
    ):
        return True
    return False


def _resolve_regional_energy_system_id_for_nt_rd(
    ues: UnionEnergySystem,
    rd_id: int,
) -> int | None:
    for res in ues.regional_energy_systems or []:
        for regional_district in res.regional_districts or []:
            if int(regional_district.id) == int(rd_id):
                return int(res.id)
    valid_res = [
        res
        for res in sorted(ues.regional_energy_systems or [], key=_sort_by_name)
        if _is_valid_named_item(res)
    ]
    return int(valid_res[0].id) if valid_res else None


def _south_ues_res_entity_depth(
    summary_rows: list[dict[str, Any]],
    south_ues_id: int,
) -> int:
    for row in summary_rows:
        if not _summary_row_belongs_to_union_energy_system(row, south_ues_id):
            continue
        if (
            row.get("demand_model_name")
            == RegionalEnergySystemEnergyConsumptionParameter.__name__
        ):
            return int(row.get("entity_depth") or 2)
    return 2


def _build_nt_ues_under_south_summary_entity(
    *,
    south_ues_id: int,
    entity_depth: int,
) -> SummaryEntity | None:
    nt_ues_id = _resolve_new_territories_union_energy_system_id()
    if nt_ues_id is None:
        return None
    ues = db.session.get(UnionEnergySystem, int(nt_ues_id))
    if ues is None:
        return None
    # Для «Новых территорий» состав субъектов задаётся в справочнике субъектов через ФО.
    # Связи РЭС<->субъект могут быть неполными (например, при редактировании справочников),
    # поэтому используем ФО как источник истины.
    regional_districts = _load_new_territories_regional_districts()
    if not regional_districts:
        # Фоллбек: если по какой-то причине ФО не найден — берём из связей ОЭС->РЭС->субъекты.
        rd_ids = _regional_district_ids_for_union_energy_system(int(nt_ues_id))
        regional_districts = [
            rd
            for rd_id in rd_ids
            for rd in [db.session.get(RegionalDistrict, int(rd_id))]
            if rd is not None and _is_valid_named_item(rd)
        ]
    if not regional_districts:
        return None

    subject_depth = entity_depth + 1
    children: list[SummaryEntity] = []
    for regional_district in regional_districts:
        rd_id = int(regional_district.id)
        # Предпочитаем фактическую привязку субъекта к РЭС, если она есть и ведёт в ОЭС НТ.
        valid_res = [
            res
            for res in sorted(getattr(regional_district, "regional_energy_systems", []) or [], key=_sort_by_name)
            if _is_valid_named_item(res) and int(getattr(res, "id_union_energy_system", 0) or 0) == int(nt_ues_id)
        ]
        res_id = int(valid_res[0].id) if valid_res else _resolve_regional_energy_system_id_for_nt_rd(ues, rd_id)
        children.append(
            _build_regional_district_entity(
                regional_district,
                depth=subject_depth,
                ues_id=south_ues_id,
                res_id=res_id,
            )
        )
    if not children:
        return None

    return SummaryEntity(
        label=_NEW_TERRITORIES_SUBJECTS_AGGREGATE_LABEL,
        depth=entity_depth,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="fo_nt_under_south",
        children=children,
        demand_model_name=UnionEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_union_energy_system",
        parent_id=int(nt_ues_id),
        id_union_energy_system=south_ues_id,
    )


def _build_new_territories_subjects_summary_rows(
    *,
    years: list[int],
    rounding_digits: int,
    south_ues_id: int,
    summary_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    entity_depth = _south_ues_res_entity_depth(summary_rows or [], south_ues_id)
    entity = _build_nt_ues_under_south_summary_entity(
        south_ues_id=south_ues_id,
        entity_depth=entity_depth,
    )
    if entity is None:
        return []

    out = _flatten_entity(entity, years, rounding_digits)
    for row in out:
        row["pd_ec_nt_extra_row"] = True
        row["pd_ec_nt_without_row"] = False
        row["id_union_energy_system"] = south_ues_id
        if row.get("demand_model_name") == RegionalDistrictEnergyConsumptionParameter.__name__:
            row["pd_ec_nt_under_south_detail_row"] = True
            row["pd_ec_territory_detail_relaxed_compact_nt_gaes"] = True
    _apply_nt_under_south_subject_sum_formula(out, years, rounding_digits)
    return out


def _apply_nt_under_south_subject_sum_formula(
    nt_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    parent_block = [row for row in nt_rows if row.get("entity_kind") == "fo_nt_under_south"]
    if not parent_block:
        return
    subject_source_rows = [
        row
        for row in nt_rows
        if row.get("pd_ec_nt_under_south_detail_row")
        and not row.get("pd_ec_formula_derived_row")
        and row.get("parameter_key") in _FO_FORMULA_BASE_PARAMETER_KEYS
    ]
    if not subject_source_rows:
        return

    for parameter_key in _FO_FORMULA_BASE_PARAMETER_KEYS:
        target_row = next(
            (row for row in parent_block if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        raw_sum: dict[int, Decimal] = {}
        has_value: dict[int, bool] = {}
        for row in subject_source_rows:
            if row.get("parameter_key") != parameter_key:
                continue
            for year, value in _raw_year_values_from_summary_row(row, years).items():
                if value is None:
                    continue
                raw_sum[int(year)] = raw_sum.get(int(year), Decimal(0)) + value
                has_value[int(year)] = True
        summed = {
            int(year): raw_sum.get(int(year)) if has_value.get(int(year)) else None
            for year in years
        }
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            summed,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )
        if parameter_key == "energy_consumption_mln_kvt_ch":
            target_row["pd_ec_summary_row_formula_tooltip"] = _NT_UNDER_SOUTH_FORMULA_TOOLTIP

    for block_row in parent_block:
        block_row["pd_ec_formula_derived_row"] = True

    _recompute_growth_rows_from_base_series(
        parent_block,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        parent_block,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def inject_south_ues_new_territories_summary_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
) -> None:
    """После блока «ОЭС Юга» — сумма потребления субъектов ОЭС «Новые территории»."""
    if not summary_rows or not years:
        return
    if not south_ues_base_tree_includes_new_territories(years):
        return
    if any(row.get("entity_kind") == "fo_nt_under_south" for row in summary_rows):
        return
    if any(
        str(row.get("entity_label") or "").strip() == "Проверка для Новых территорий"
        for row in summary_rows
    ):
        return

    south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
    if south_ues_id is None:
        return

    nt_rows = _build_new_territories_subjects_summary_rows(
        years=years,
        rounding_digits=rounding_digits,
        south_ues_id=south_ues_id,
        summary_rows=summary_rows,
    )
    if not nt_rows:
        return

    def _build_nt_oes_subjects_verification_rows() -> list[dict[str, Any]]:
        nt_ues_id = _resolve_new_territories_union_energy_system_id()
        if nt_ues_id is None:
            return []
        ues_model = UnionEnergySystemEnergyConsumptionParameter.__name__
        ec_key = "energy_consumption_mln_kvt_ch"
        sipr_key = "energy_consumption_sipr_mln_kvt_ch"

        def _find_nt_ues_base_row(parameter_key: str) -> dict[str, Any] | None:
            # В сводке код варианта может быть None или "" (оба считаем базовыми).
            for row in summary_rows:
                if row.get("parameter_key") != parameter_key:
                    continue
                if row.get("demand_model_name") != ues_model:
                    continue
                if row.get("parent_fk_column") != "id_union_energy_system":
                    continue
                if row.get("parent_id") != int(nt_ues_id):
                    continue
                if row.get("perimeter_variant_code") in (None, ""):
                    return row
            # Фоллбек: если базовой строки нет, берём первую попавшуюся по ОЭС НТ.
            for row in summary_rows:
                if row.get("parameter_key") != parameter_key:
                    continue
                if row.get("demand_model_name") != ues_model:
                    continue
                if row.get("parent_fk_column") != "id_union_energy_system":
                    continue
                if row.get("parent_id") != int(nt_ues_id):
                    continue
                return row
            return None

        base_ec_row = _find_nt_ues_base_row(ec_key)
        base_sipr_row = _find_nt_ues_base_row(sipr_key)
        if base_ec_row is None or base_sipr_row is None:
            return []

        nt_agg_depth = next(
            (
                int(r.get("entity_depth") or 2)
                for r in nt_rows
                if r.get("entity_kind") == "fo_nt_under_south"
            ),
            2,
        )
        nt_sum_ec = next(
            (
                _raw_year_values_from_summary_row(r, years)
                for r in nt_rows
                if r.get("entity_kind") == "fo_nt_under_south"
                and r.get("parameter_key") == ec_key
            ),
            {int(y): None for y in years},
        )
        nt_sum_sipr = next(
            (
                _raw_year_values_from_summary_row(r, years)
                for r in nt_rows
                if r.get("entity_kind") == "fo_nt_under_south"
                and r.get("parameter_key") == sipr_key
            ),
            {int(y): None for y in years},
        )
        tooltip = (
            "Проверка = ОЭС «Новые территории» − "
            "сумма потребления ЭЭ всех субъектов РФ, входящих в ОЭС «Новые территории»"
        )
        return _build_ec_summary_verification_rows(
            entity_label="Проверка для Новых территорий",
            entity_kind="ues_nt_subject_sum_check",
            entity_depth=nt_agg_depth,
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=nt_sum_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=nt_sum_sipr,
            formula_tooltip=tooltip,
        )

    out: list[dict[str, Any]] = []
    index = 0
    total = len(summary_rows)
    while index < total:
        row = summary_rows[index]
        out.append(row)
        if _summary_row_belongs_to_union_energy_system(row, south_ues_id):
            next_index = index + 1
            while next_index < total and _summary_row_belongs_to_union_energy_system(
                summary_rows[next_index],
                south_ues_id,
            ):
                out.append(summary_rows[next_index])
                next_index += 1
            out.extend(nt_rows)
            out.extend(_build_nt_oes_subjects_verification_rows())
            index = next_index
            continue
        index += 1
    summary_rows[:] = out


def inject_south_fd_new_territories_summary_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
) -> None:
    """После поддерева «Южный ФО» — блок «Новые территории» (с субъектами), скрыт до кнопки «+НТ»."""
    if not summary_rows or not years:
        return
    if not south_ues_base_tree_includes_new_territories(years):
        return
    if any(row.get("entity_kind") == "fo_nt_under_south" for row in summary_rows):
        return

    south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
    if south_ues_id is None:
        return
    south_fd_id = _resolve_federal_district_id_by_name_cf(SOUTH_FD_NAME_CF)
    if south_fd_id is None:
        return

    # Южный ФО на сводке должен быть виден даже при включённом «Пустые строки»,
    # иначе при отсутствии данных по конкретным показателям пользователь не увидит сам факт наличия строки.
    # (Особенно важно для проверки поведения вариантов периметра «+НТ».)
    for row in summary_rows:
        if row.get("demand_model_name") != FederalDistrictEnergyConsumptionParameter.__name__:
            continue
        if row.get("parent_fk_column") != "id_federal_district":
            continue
        if row.get("parent_id") != int(south_fd_id):
            continue
        row["pd_ec_skip_empty_hide_row"] = True

    nt_rows = _build_new_territories_subjects_summary_rows(
        years=years,
        rounding_digits=rounding_digits,
        south_ues_id=south_ues_id,
        summary_rows=summary_rows,
    )
    if not nt_rows:
        return

    fd_model = FederalDistrictEnergyConsumptionParameter.__name__
    insert_at: int | None = None
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != fd_model:
            continue
        if row.get("parent_fk_column") != "id_federal_district":
            continue
        if row.get("parent_id") != int(south_fd_id):
            continue
        insert_at = _federal_district_subtree_end_index(summary_rows, i, fd_model=fd_model) + 1
        break
    if insert_at is None:
        return

    summary_rows[insert_at:insert_at] = nt_rows


def _is_top_ees_russia_aggregate_summary_table_row(row: dict[str, Any]) -> bool:
    """Верхний агрегат «ЕЭС России» на сводной таблице, не варианты под «ЕЭС России …» (тип ЭС)."""
    return row.get("entity_kind") == ENTITY_KIND_EES_RUSSIA


def _is_ees_russia_summary_table_row(row: dict[str, Any]) -> bool:
    if _is_top_ees_russia_aggregate_summary_table_row(row):
        return True
    return row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__


_EES_RUSSIA_NT_VARIANT_PREFIXES_CF = ("with_nt", "without_nt")


def _is_ees_russia_nt_gaes_variant_summary_row(row: dict[str, Any]) -> bool:
    """Строки «ЕЭС России» с вариантом с/без НТ (в т.ч. с/без заряда ГАЭС)."""
    if row.get("demand_model_name") != EesRussiaEnergyConsumptionParameter.__name__:
        return False
    if row.get("entity_kind") != ENTITY_KIND_EES_RUSSIA:
        return False
    code = str(row.get("perimeter_variant_code") or "").strip()
    if not code or is_o1_perimeter_variant_code(code):
        return False
    code_cf = code.casefold()
    if not any(code_cf.startswith(prefix) for prefix in _EES_RUSSIA_NT_VARIANT_PREFIXES_CF):
        return False
    if code in (CODE_WITH_NT, CODE_WITHOUT_NT):
        return True
    return "with_gaes" in code_cf or "without_gaes" in code_cf


def tag_ees_russia_sipr_integer_display_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    """В режиме «СиПР» — целые значения в строках потребления (СиПР), прироста (СиПР) и заряда ГАЭС."""
    for row in summary_rows:
        if row.get("parameter_key") in _SIPR_INTEGER_DISPLAY_PARAMETER_KEYS:
            row["pd_ec_sipr_integer_display_row"] = True


def apply_sipr_consumption_display_fallback_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """В ячейках строки СиПР без значения подставить отображение из строки потребления, млн кВт·ч."""
    if not years:
        return
    ec_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in summary_rows:
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            ec_rows[_summary_row_variant_param_key(row)[:-1]] = row

    for row in summary_rows:
        if row.get("parameter_key") != "energy_consumption_sipr_mln_kvt_ch":
            continue
        ec_row = ec_rows.get(_summary_row_variant_param_key(row)[:-1])
        if ec_row is None:
            continue
        yv = list(row.get("year_values") or [])
        tt = list(row.get("year_numeric_tooltips") or [])
        ec_yv = list(ec_row.get("year_values") or [])
        ec_tt = list(ec_row.get("year_numeric_tooltips") or [])
        changed = False
        for i, _year in enumerate(years):
            if i >= len(yv) or yv[i] != "—":
                continue
            if i >= len(ec_yv) or ec_yv[i] == "—":
                continue
            yv[i] = ec_yv[i]
            fallback_tt = ec_tt[i] if i < len(ec_tt) else ""
            if i < len(tt):
                tt[i] = fallback_tt
            else:
                while len(tt) <= i:
                    tt.append("")
                tt[i] = fallback_tt
            changed = True
        if changed:
            row["year_values"] = yv
            row["year_numeric_tooltips"] = tt


def recompute_sipr_growth_metrics_for_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Пересчёт прироста (СиПР) по отображаемому ряду потребления (СиПР), в т.ч. после fallback."""
    if not years:
        return
    blocks: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in summary_rows:
        entity_key = _summary_row_variant_param_key(row)[:-1]
        blocks.setdefault(entity_key, []).append(row)
    for block_rows in blocks.values():
        if not any(
            r.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch" for r in block_rows
        ):
            continue
        _recompute_growth_rows_from_base_series(
            block_rows,
            years,
            base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
            abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )


def _is_union_energy_system_summary_table_row(row: dict[str, Any]) -> bool:
    return (
        row.get("demand_model_name") == UnionEnergySystemEnergyConsumptionParameter.__name__
        and row.get("parent_fk_column") == "id_union_energy_system"
    )


def _summary_table_insert_index_after_russia_with_nt_before_gaes_charge(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    """Индекс вставки после показателей «Россия с НТ», перед строкой «Заряд ГАЭС»."""
    label_with_nt = f"{RUSSIA_FEDERATION_AGGREGATE_NAME}{_NT_LABEL_SUFFIX_WITH}".strip()
    for index, row in enumerate(summary_rows):
        if row.get("entity_kind") != ENTITY_KIND_RUSSIA_FEDERATION:
            continue
        if str(row.get("parameter_key") or "") == GAES_CHARGE_PARAMETER_KEY:
            return index
        if str(row.get("entity_label") or "").strip() == _SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL:
            return index
    last_nt_index: int | None = None
    for index, row in enumerate(summary_rows):
        if row.get("entity_kind") != ENTITY_KIND_RUSSIA_FEDERATION:
            continue
        if str(row.get("entity_label") or "").strip() == label_with_nt:
            last_nt_index = index
    return None if last_nt_index is None else last_nt_index + 1


def _pick_russia_with_nt_summary_parameter_row(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
) -> dict[str, Any] | None:
    label_with_nt = f"{RUSSIA_FEDERATION_AGGREGATE_NAME}{_NT_LABEL_SUFFIX_WITH}".strip()
    for row in summary_rows:
        if row.get("entity_kind") != ENTITY_KIND_RUSSIA_FEDERATION:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if str(row.get("entity_label") or "").strip() != label_with_nt:
            continue
        if row.get("demand_model_name") != RussiaFederationEnergyConsumptionParameter.__name__:
            continue
        return row
    return None


def _last_ees_russia_summary_table_row_index(summary_rows: list[dict[str, Any]]) -> int | None:
    """Последняя строка «ЕЭС России» непосредственно перед первой ОЭС (после синхронных зон)."""
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if _is_union_energy_system_summary_table_row(row):
            break
        if _is_ees_russia_summary_table_row(row):
            last_index = index
    return last_index


def _is_first_sync_area_summary_table_row(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
        return False
    return _summary_row_base_label_cf(row).startswith(_FIRST_SYNC_AREA_BASE_LABEL_CF)


def _last_first_sync_area_summary_table_row_index(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if _is_first_sync_area_summary_table_row(row):
            last_index = index
    return last_index


def _last_sync_area_summary_table_row_index_before_oes_ees(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    """Последняя строка синхронных зон перед первой ОЭС."""
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if _is_union_energy_system_summary_table_row(row):
            break
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__:
            last_index = index
    return last_index


def _is_kaliningrad_sync_area_summary_table_row(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
        return False
    return _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF in _summary_row_base_label_cf(row)


def _plain_kaliningrad_sync_area_entity_label(label: str) -> str:
    base, _ = _strip_summary_table_variant_suffixes_from_label(label)
    return base.strip() or label.strip()


def _last_kaliningrad_sync_area_summary_table_row_index(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if _is_kaliningrad_sync_area_summary_table_row(row):
            last_index = index
    return last_index


def _multiply_year_value_dicts_scalar(
    years: list[int],
    source: dict[int, Decimal | None],
    factor: Decimal | int,
) -> dict[int, Decimal | None]:
    multiplier = Decimal(factor)
    out: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        value = source.get(y)
        out[y] = value * multiplier if value is not None else None
    return out


def _subtract_year_value_dicts(
    years: list[int],
    left: dict[int, Decimal | None],
    right: dict[int, Decimal | None],
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        left_value = left.get(y)
        if left_value is None:
            out[y] = None
            continue
        right_value = right.get(y) or Decimal(0)
        out[y] = left_value - right_value
    return out


def _verification_display_value_is_nonzero(display: Any) -> bool:
    value = _decimal_or_none(display)
    if value is None:
        return False
    return value != 0


def _verification_year_red_flags_from_display(
    years: list[int],
    year_values: list[str],
    *,
    from_year: int | None = None,
    to_year: int | None = None,
) -> list[bool]:
    flags: list[bool] = []
    for ix, year in enumerate(years):
        y = int(year)
        if from_year is not None and y < int(from_year):
            flags.append(False)
            continue
        if to_year is not None and y > int(to_year):
            flags.append(False)
            continue
        disp = year_values[ix] if ix < len(year_values) else "—"
        flags.append(_verification_display_value_is_nonzero(disp))
    return flags


def _verification_year_in_bounds(
    year: int,
    *,
    from_year: int | None,
    to_year: int | None,
) -> bool:
    if from_year is not None and int(year) < int(from_year):
        return False
    if to_year is not None and int(year) > int(to_year):
        return False
    return True


def _build_ec_summary_verification_rows(
    *,
    entity_label: str,
    entity_kind: str,
    entity_depth: int,
    years: list[int],
    rounding_digits: int,
    base_ec: dict[int, Decimal | None],
    sum_ec: dict[int, Decimal | None],
    base_sipr: dict[int, Decimal | None],
    sum_sipr: dict[int, Decimal | None],
    formula_tooltip: str | None = None,
    year_bounds_variant_code: str | None = None,
    verification_from_year: int | None = None,
) -> list[dict[str, Any]]:
    from_year, to_year = perimeter_variant_year_bounds_for_code(year_bounds_variant_code)
    if verification_from_year is not None:
        if from_year is None or int(verification_from_year) > int(from_year):
            from_year = int(verification_from_year)
    demand_slices: list[_AggregatedYearDemandSlice] = []
    for year in years:
        y = int(year)
        if not _verification_year_in_bounds(
            y,
            from_year=from_year,
            to_year=to_year,
        ):
            demand_slices.append(
                _AggregatedYearDemandSlice(
                    year_number=y,
                    energy_consumption_mln_kvt_ch=None,
                    energy_consumption_sipr_mln_kvt_ch=None,
                )
            )
            continue
        base_ec_value = base_ec.get(y)
        base_sipr_value = base_sipr.get(y)
        sum_ec_value = sum_ec.get(y) or Decimal(0)
        sum_sipr_value = sum_sipr.get(y) or Decimal(0)
        demand_slices.append(
            _AggregatedYearDemandSlice(
                year_number=y,
                energy_consumption_mln_kvt_ch=(
                    None if base_ec_value is None else base_ec_value - sum_ec_value
                ),
                energy_consumption_sipr_mln_kvt_ch=(
                    None if base_sipr_value is None else base_sipr_value - sum_sipr_value
                ),
            )
        )

    display_digits = _EC_SUMMARY_VERIFY_FOR_DISPLAY_DECIMALS
    parameter_maps, tooltip_maps = _build_parameter_maps(
        demand_slices,
        PARAMETERS_ENERGY_CONSUMPTION,
        display_digits,
    )
    verification_parameters = _EC_SUMMARY_VERIFICATION_PARAMETERS
    if entity_label in _EC_SUMMARY_VERIFICATION_OMIT_SIPR_ABS_ENTITY_LABELS:
        verification_parameters = tuple(
            item
            for item in verification_parameters
            if item[0] != ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY
        )
    entity_rowspan = len(verification_parameters)
    out: list[dict[str, Any]] = []
    for index, (parameter_key, parameter_label) in enumerate(verification_parameters):
        values = parameter_maps.get(parameter_key, {})
        tooltips = tooltip_maps.get(parameter_key, {})
        year_values = [values.get(year, "—") for year in years]
        row: dict[str, Any] = {
            "entity_label": entity_label,
            "entity_rowspan": entity_rowspan,
            "entity_depth": entity_depth,
            "entity_kind": entity_kind,
            "show_entity_cell": index == 0,
            "parameter_key": parameter_key,
            "parameter_label": parameter_label,
            "demand_model_name": None,
            "parent_fk_column": None,
            "parent_id": None,
            "hist_row_id": None,
            "year_row_ids": [None for _ in years],
            "hist_value": "—",
            "year_values": year_values,
            "hist_numeric_tooltip": "",
            "year_numeric_tooltips": [tooltips.get(year, "") for year in years],
            "entity_note_text": "",
            "entity_note_row_id": None,
            "show_entity_note_cell": index == 0,
            "perimeter_variant_code": None,
            "show_perimeter_variant_select": False,
            "perimeter_variant_label": "",
            "perimeter_variant_options": [],
            "pd_ec_verification_full_precision": True,
            "pd_ec_verification_year_red": _verification_year_red_flags_from_display(
                years,
                year_values,
                from_year=from_year,
                to_year=to_year,
            ),
        }
        if entity_label in _EC_SUMMARY_VERIFICATION_OMIT_SIPR_ABS_ENTITY_LABELS:
            row["pd_ec_verification_omit_sipr_abs"] = True
        if formula_tooltip:
            row["pd_ec_verification_formula_tooltip"] = formula_tooltip
        if from_year is not None:
            row["perimeter_variant_from_year"] = from_year
        if to_year is not None:
            row["perimeter_variant_to_year"] = to_year
        out.append(row)
    return out


def _find_ees_russia_summary_parameter_row(
    summary_rows: list[dict[str, Any]],
    *,
    parameter_key: str,
    perimeter_variant_code: str,
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in summary_rows
            if row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__
            and row.get("parameter_key") == parameter_key
            and str(row.get("perimeter_variant_code") or "") == perimeter_variant_code
        ),
        None,
    )


def _merge_year_value_dicts_preferring_primary(
    years: list[int],
    primary: dict[int, Decimal | None],
    *fallbacks: dict[int, Decimal | None],
) -> dict[int, Decimal | None]:
    merged: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        value = primary.get(y)
        if value is not None:
            merged[y] = value
            continue
        for fallback in fallbacks:
            candidate = fallback.get(y)
            if candidate is not None:
                merged[y] = candidate
                break
        else:
            merged[y] = None
    return merged


def _ees_russia_gaes_verification_base_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
    *,
    perimeter_variant_code: str,
    formula_aggregate: dict[int, Decimal | None] | None = None,
) -> dict[int, Decimal | None]:
    """База проверки ЕЭС: строка сводной таблицы (все годы), иначе сумма по формуле, иначе БД."""
    ees_row = _find_ees_russia_summary_parameter_row(
        summary_rows,
        parameter_key=parameter_key,
        perimeter_variant_code=perimeter_variant_code,
    )
    raw: dict[int, Decimal | None] = {}
    if ees_row is not None:
        raw = _raw_year_values_from_summary_row(
            ees_row,
            years,
            ignore_perimeter_variant_year_bounds=True,
        )
    db_values = _year_values_from_parent_demand_rows(
        EesRussiaEnergyConsumptionParameter,
        None,
        None,
        years,
        parameter_key,
        perimeter_variant_code=perimeter_variant_code,
    )
    merged: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        value = raw.get(y)
        if value is None and formula_aggregate is not None:
            value = formula_aggregate.get(y)
        if value is None:
            value = db_values.get(y)
        merged[y] = value
    return merged if _year_values_have_any_numeric(merged) else {}


def _kaliningrad_sync_area_parameter_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    if kaliningrad_sa_id is not None:
        raw = _year_values_from_parent_demand_rows(
            SynchronousAreaEnergyConsumptionParameter,
            "id_synchronous_area",
            kaliningrad_sa_id,
            years,
            parameter_key,
        )
        if _year_values_have_any_numeric(raw):
            return raw

    for row in summary_rows:
        if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF not in _summary_row_base_label_cf(row):
            continue
        return _raw_year_values_from_summary_row(row, years)
    return {}


def _is_without_nt_with_gaes_without_kaliningrad_variant_row(row: dict[str, Any]) -> bool:
    return (
        str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT
    )


def _is_without_nt_with_gaes_with_kaliningrad_variant_row(row: dict[str, Any]) -> bool:
    return (
        str(row.get("perimeter_variant_code") or "")
        == CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES
    )


def _first_sa_without_nt_with_gaes_parameter_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    first_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_without_nt_with_gaes_without_kaliningrad_variant_row,
    )
    if first_sa_row is not None:
        raw = _raw_year_values_from_summary_row(
            first_sa_row,
            years,
            ignore_perimeter_variant_year_bounds=True,
        )
        if _year_values_have_any_numeric(raw):
            return raw

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return {}

    computed_without_kaliningrad = _year_values_sum_ues_in_first_sa_without_kaliningrad_es(
        first_sa_id,
        years,
        parameter_key,
    )
    if _year_values_have_any_numeric(computed_without_kaliningrad):
        return computed_without_kaliningrad

    for variant_code in (
        _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
    ):
        raw = _year_values_from_parent_demand_rows(
            SynchronousAreaEnergyConsumptionParameter,
            "id_synchronous_area",
            first_sa_id,
            years,
            parameter_key,
            perimeter_variant_code=variant_code,
        )
        if _year_values_have_any_numeric(raw):
            return raw

    source_maps = [
        _year_values_sum_ues_in_synchronous_area(
            first_sa_id,
            years,
            parameter_key,
            ues_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        ),
        _gaes_charge_year_values_for_first_sa_without_nt(
            summary_rows,
            years,
            first_sa_id=first_sa_id,
        ),
    ]
    source_maps = [item for item in source_maps if _year_values_have_any_numeric(item)]
    if not source_maps:
        return {}
    return _sum_year_value_dicts(years, *source_maps)


def _first_sa_with_nt_with_gaes_parameter_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    first_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_with_nt_with_gaes_variant_row,
    )
    if first_sa_row is not None:
        raw = _raw_year_values_from_summary_row(first_sa_row, years)
        if _year_values_have_any_numeric(raw):
            return raw

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return {}

    raw = _year_values_from_parent_demand_rows(
        SynchronousAreaEnergyConsumptionParameter,
        "id_synchronous_area",
        first_sa_id,
        years,
        parameter_key,
        perimeter_variant_code=_FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT,
    )
    if _year_values_have_any_numeric(raw):
        return raw

    return _year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es(
        first_sa_id,
        years,
        parameter_key,
    )


def _first_sa_without_nt_with_gaes_with_kaliningrad_parameter_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    first_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_without_nt_with_gaes_with_kaliningrad_variant_row,
    )
    if first_sa_row is not None:
        raw = _raw_year_values_from_summary_row(
            first_sa_row,
            years,
            ignore_perimeter_variant_year_bounds=True,
        )
        if _year_values_have_any_numeric(raw):
            return raw

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return {}

    for variant_code in (CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,):
        raw = _year_values_from_parent_demand_rows(
            SynchronousAreaEnergyConsumptionParameter,
            "id_synchronous_area",
            first_sa_id,
            years,
            parameter_key,
            perimeter_variant_code=variant_code,
        )
        if _year_values_have_any_numeric(raw):
            return raw

    without_kal = _first_sa_without_nt_with_gaes_parameter_year_values(
        summary_rows,
        years,
        parameter_key,
    )
    kal = _kaliningrad_sync_area_parameter_year_values(
        summary_rows,
        years,
        parameter_key,
    )
    if _year_values_have_any_numeric(without_kal) or _year_values_have_any_numeric(kal):
        return _sum_year_value_dicts(years, without_kal, kal)
    return {}


def _ees_russia_without_nt_with_gaes_formula_component_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> tuple[
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[int, Decimal | None],
]:
    first_sa_values = _first_sa_without_nt_with_gaes_with_kaliningrad_parameter_year_values(
        summary_rows,
        years,
        parameter_key,
    )

    second_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_SECOND_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_summary_table_base_perimeter_row,
    )
    if second_sa_row is not None:
        second_sa_values = _raw_year_values_from_summary_row(second_sa_row, years)
    else:
        second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
            _SECOND_SYNC_AREA_BASE_LABEL_CF
        )
        second_sa_values = (
            _year_values_from_parent_demand_rows(
                SynchronousAreaEnergyConsumptionParameter,
                "id_synchronous_area",
                second_sa_id,
                years,
                parameter_key,
            )
            if second_sa_id is not None
            else {}
        )

    tites_values = _year_values_for_tites_source(
        summary_rows,
        years,
        parameter_key,
    )
    return first_sa_values, second_sa_values, tites_values


def _ees_russia_with_nt_with_gaes_formula_component_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> tuple[
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[int, Decimal | None],
]:
    first_sa_values = _first_sa_with_nt_with_gaes_parameter_year_values(
        summary_rows,
        years,
        parameter_key,
    )

    second_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_SECOND_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_summary_table_base_perimeter_row,
    )
    if second_sa_row is not None:
        second_sa_values = _raw_year_values_from_summary_row(second_sa_row, years)
    else:
        second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
            _SECOND_SYNC_AREA_BASE_LABEL_CF
        )
        second_sa_values = (
            _year_values_from_parent_demand_rows(
                SynchronousAreaEnergyConsumptionParameter,
                "id_synchronous_area",
                second_sa_id,
                years,
                parameter_key,
            )
            if second_sa_id is not None
            else {}
        )

    kaliningrad_values = _kaliningrad_sync_area_parameter_year_values(
        summary_rows,
        years,
        parameter_key,
    )
    return first_sa_values, second_sa_values, kaliningrad_values


def _build_ees_russia_with_nt_with_gaes_kaliningrad_split_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    entity_depth: int,
) -> list[dict[str, Any]]:
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    base_ec = _year_values_from_parent_demand_rows(
        EesRussiaEnergyConsumptionParameter,
        None,
        None,
        years,
        ec_key,
        perimeter_variant_code=CODE_WITH_NT_WITH_GAES,
    )
    base_sipr = _year_values_from_parent_demand_rows(
        EesRussiaEnergyConsumptionParameter,
        None,
        None,
        years,
        sipr_key,
        perimeter_variant_code=CODE_WITH_NT_WITH_GAES,
    )
    if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
        ees_ec_row = _find_ees_russia_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            perimeter_variant_code=CODE_WITH_NT_WITH_GAES,
        )
        ees_sipr_row = _find_ees_russia_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            perimeter_variant_code=CODE_WITH_NT_WITH_GAES,
        )
        if ees_ec_row is None or ees_sipr_row is None:
            return []
        base_ec = _raw_year_values_from_summary_row(ees_ec_row, years)
        base_sipr = _raw_year_values_from_summary_row(ees_sipr_row, years)
        if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(
            base_sipr
        ):
            return []

    first_ec, second_ec, kal_ec = _ees_russia_with_nt_with_gaes_formula_component_values(
        summary_rows,
        years,
        ec_key,
    )
    first_sipr, second_sipr, kal_sipr = _ees_russia_with_nt_with_gaes_formula_component_values(
        summary_rows,
        years,
        sipr_key,
    )
    sum_ec = _sum_year_value_dicts(years, first_ec, second_ec)
    sum_sipr = _sum_year_value_dicts(years, first_sipr, second_sipr)
    diff_ec = _subtract_year_value_dicts(years, base_ec, sum_ec)
    diff_sipr = _subtract_year_value_dicts(years, base_sipr, sum_sipr)
    diff_ec = _subtract_year_value_dicts(years, diff_ec, kal_ec)
    diff_sipr = _subtract_year_value_dicts(years, diff_sipr, kal_sipr)

    zero_ec = {int(year): Decimal(0) for year in years}
    zero_sipr = {int(year): Decimal(0) for year in years}
    return _build_ec_summary_verification_rows(
        entity_label=_EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=entity_depth,
        years=years,
        rounding_digits=rounding_digits,
        base_ec=diff_ec,
        sum_ec=zero_ec,
        base_sipr=diff_sipr,
        sum_sipr=zero_sipr,
        formula_tooltip=_EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP,
        year_bounds_variant_code=CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    )


def _build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    entity_depth: int,
) -> list[dict[str, Any]]:
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    first_ec, second_ec, tites_ec = _ees_russia_without_nt_with_gaes_formula_component_values(
        summary_rows,
        years,
        ec_key,
    )
    first_sipr, second_sipr, tites_sipr = (
        _ees_russia_without_nt_with_gaes_formula_component_values(
            summary_rows,
            years,
            sipr_key,
        )
    )
    sum_ec = _sum_year_value_dicts(years, first_ec, second_ec, tites_ec)
    sum_sipr = _sum_year_value_dicts(years, first_sipr, second_sipr, tites_sipr)
    base_ec = _ees_russia_gaes_verification_base_year_values(
        summary_rows,
        years,
        ec_key,
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        formula_aggregate=sum_ec,
    )
    base_sipr = _ees_russia_gaes_verification_base_year_values(
        summary_rows,
        years,
        sipr_key,
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        formula_aggregate=sum_sipr,
    )
    if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
        return []
    diff_ec = _subtract_year_value_dicts(years, base_ec, sum_ec)
    diff_sipr = _subtract_year_value_dicts(years, base_sipr, sum_sipr)

    zero_ec = {int(year): Decimal(0) for year in years}
    zero_sipr = {int(year): Decimal(0) for year in years}
    return _build_ec_summary_verification_rows(
        entity_label=_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=entity_depth,
        years=years,
        rounding_digits=rounding_digits,
        base_ec=diff_ec,
        sum_ec=zero_ec,
        base_sipr=diff_sipr,
        sum_sipr=zero_sipr,
        formula_tooltip=_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP,
        year_bounds_variant_code=None,
    )


def _build_first_sa_without_nt_with_gaes_ues_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    first_sa_id: int,
    exclude_ues_ids: frozenset[int] | None,
    entity_depth: int,
    entity_label: str,
    formula_tooltip: str,
    first_sa_perimeter_variant_code: str,
    default_ues_variant_code: str,
    ues_variant_code_for_ues_id: Callable[[int], str | None] | None = None,
    year_bounds_variant_code: str | None = None,
    use_without_kaliningrad_es_sum: bool = False,
) -> list[dict[str, Any]]:
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    first_sa_ec_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=ec_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=lambda row: str(row.get("perimeter_variant_code") or "")
        == first_sa_perimeter_variant_code,
    )
    first_sa_sipr_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=sipr_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=lambda row: str(row.get("perimeter_variant_code") or "")
        == first_sa_perimeter_variant_code,
    )
    if first_sa_ec_row is not None and first_sa_sipr_row is not None:
        base_ec = _raw_year_values_from_summary_row(first_sa_ec_row, years)
        base_sipr = _raw_year_values_from_summary_row(first_sa_sipr_row, years)
    else:
        base_ec = {}
        base_sipr = {}
    if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
        base_ec = _year_values_from_parent_demand_rows(
            SynchronousAreaEnergyConsumptionParameter,
            "id_synchronous_area",
            first_sa_id,
            years,
            ec_key,
            perimeter_variant_code=first_sa_perimeter_variant_code,
        )
        base_sipr = _year_values_from_parent_demand_rows(
            SynchronousAreaEnergyConsumptionParameter,
            "id_synchronous_area",
            first_sa_id,
            years,
            sipr_key,
            perimeter_variant_code=first_sa_perimeter_variant_code,
        )
        if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(
            base_sipr
        ):
            return []

    sum_ec = (
        _year_values_sum_ues_in_first_sa_without_kaliningrad_es(
            first_sa_id,
            years,
            ec_key,
            exclude_ues_ids=exclude_ues_ids,
        )
        if use_without_kaliningrad_es_sum
        else _year_values_sum_ues_in_synchronous_area(
            first_sa_id,
            years,
            ec_key,
            ues_variant_code=default_ues_variant_code,
            exclude_ues_ids=exclude_ues_ids,
            ues_variant_code_for_ues_id=ues_variant_code_for_ues_id,
        )
    )
    sum_sipr = (
        _year_values_sum_ues_in_first_sa_without_kaliningrad_es(
            first_sa_id,
            years,
            sipr_key,
            exclude_ues_ids=exclude_ues_ids,
        )
        if use_without_kaliningrad_es_sum
        else _year_values_sum_ues_in_synchronous_area(
            first_sa_id,
            years,
            sipr_key,
            ues_variant_code=default_ues_variant_code,
            exclude_ues_ids=exclude_ues_ids,
            ues_variant_code_for_ues_id=ues_variant_code_for_ues_id,
        )
    )
    return _build_ec_summary_verification_rows(
        entity_label=entity_label,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=entity_depth,
        years=years,
        rounding_digits=rounding_digits,
        base_ec=base_ec,
        sum_ec=sum_ec,
        base_sipr=base_sipr,
        sum_sipr=sum_sipr,
        formula_tooltip=formula_tooltip,
        year_bounds_variant_code=year_bounds_variant_code,
    )


def inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
) -> None:
    """Проверки сводной таблицы: ЕЭС России — перед первой ОЭС; первая СЗ — после блока «Первая синхронная зона»."""
    if not summary_rows or not years:
        return

    verification_labels = (
        _EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
        _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        _FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
    )
    if any(
        row.get("entity_kind") == "oes_ees_sync_table_verification"
        and str(row.get("entity_label") or "").startswith(label)
        for row in summary_rows
        for label in verification_labels
    ):
        return

    ees_insert_after = _last_ees_russia_summary_table_row_index(summary_rows)
    first_sa_insert_after = _last_sync_area_summary_table_row_index_before_oes_ees(summary_rows)
    if ees_insert_after is None and first_sa_insert_after is None:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    ues_east_id = _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF)
    exclude_ues_ids = frozenset({int(ues_east_id)}) if ues_east_id is not None else None
    south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)

    def _with_kaliningrad_verification_ues_variant_code(ues_id: int) -> str | None:
        if south_ues_id is not None and int(ues_id) == int(south_ues_id):
            return CODE_WITHOUT_NT_WITH_GAES
        return CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES

    ees_verification_rows: list[dict[str, Any]] = []
    if ees_insert_after is not None:
        ees_entity_depth = int(summary_rows[ees_insert_after].get("entity_depth") or 0)
        ees_verification_rows = (
            _build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
                summary_rows,
                years=years,
                rounding_digits=rounding_digits,
                entity_depth=ees_entity_depth,
            )
        )

    first_sa_verification_rows: list[dict[str, Any]] = []
    if first_sa_insert_after is not None and first_sa_id is not None:
        first_sa_entity_depth = int(
            summary_rows[first_sa_insert_after].get("entity_depth") or 0
        )
        first_sa_verification_rows.extend(
            _build_first_sa_without_nt_with_gaes_ues_verification_rows(
                summary_rows,
                years=years,
                rounding_digits=rounding_digits,
                first_sa_id=first_sa_id,
                exclude_ues_ids=exclude_ues_ids,
                entity_depth=first_sa_entity_depth,
                entity_label=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
                formula_tooltip=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_TOOLTIP,
                first_sa_perimeter_variant_code=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
                default_ues_variant_code=CODE_WITHOUT_NT_WITH_GAES,
                year_bounds_variant_code=CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
                use_without_kaliningrad_es_sum=True,
            )
        )
        first_sa_verification_rows.extend(
            _build_first_sa_without_nt_with_gaes_ues_verification_rows(
                summary_rows,
                years=years,
                rounding_digits=rounding_digits,
                first_sa_id=first_sa_id,
                exclude_ues_ids=exclude_ues_ids,
                entity_depth=first_sa_entity_depth,
                entity_label=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
                formula_tooltip=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_TOOLTIP,
                first_sa_perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
                default_ues_variant_code=CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
                ues_variant_code_for_ues_id=_with_kaliningrad_verification_ues_variant_code,
                year_bounds_variant_code=CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
            )
        )

    if not ees_verification_rows and not first_sa_verification_rows:
        return

    pending_insertions: list[tuple[int, list[dict[str, Any]]]] = []
    if ees_verification_rows and ees_insert_after is not None:
        pending_insertions.append((ees_insert_after + 1, ees_verification_rows))
    if first_sa_verification_rows and first_sa_insert_after is not None:
        pending_insertions.append((first_sa_insert_after + 1, first_sa_verification_rows))
    for insert_at, rows in sorted(pending_insertions, key=lambda item: item[0], reverse=True):
        summary_rows[insert_at:insert_at] = rows


def _summary_row_base_label_cf(row: dict[str, Any]) -> str:
    base, _ = _strip_summary_table_variant_suffixes_from_label(str(row.get("entity_label") or ""))
    return base.casefold()


def _is_summary_table_base_perimeter_row(row: dict[str, Any]) -> bool:
    return not str(row.get("perimeter_variant_code") or "").strip()


def _is_without_nt_with_gaes_variant_row(row: dict[str, Any]) -> bool:
    code = str(row.get("perimeter_variant_code") or "")
    return (
        code.startswith("without_nt")
        and "with_gaes" in code
        and "without_gaes" not in code
    )


def _is_with_nt_with_gaes_variant_row(row: dict[str, Any]) -> bool:
    code = str(row.get("perimeter_variant_code") or "")
    return (
        code.startswith("with_nt")
        and "with_gaes" in code
        and "without_gaes" not in code
    )


def _new_territories_parameter_year_values(
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    """Сумма потребления субъектов ОЭС «Новые территории» по годам (из БД текущей версии)."""
    if parameter_key not in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        return {}
    nt_ues_id = _resolve_new_territories_union_energy_system_id()
    if nt_ues_id is None:
        return {}
    rd_ids = list(_regional_district_ids_for_union_energy_system(nt_ues_id))
    # В некоторых версиях справочника один из субъектов ФО «Новые территории» может быть
    # не привязан к ОЭС «Новые территории» (например, Запорожская область). Для формулы
    # проверки на сводке ОЭС нам нужна сумма по субъектам ФО «Новые территории»:
    # ДНР, ЛНР, Херсонская область, Запорожская область.
    try:
        tokens_cf = (
            "донецк",
            "луган",
            "херсон",
            "запорож",
        )
        query = RegionalDistrict.query
        query = dps.filter_parents_by_version(query, RegionalDistrict)
        for rd in query.all():
            if not _is_valid_named_item(rd):
                continue
            name_cf = (getattr(rd, "name", None) or "").strip().casefold()
            if not name_cf:
                continue
            if not any(t in name_cf for t in tokens_cf):
                continue
            rid = int(getattr(rd, "id"))
            if rid not in rd_ids:
                rd_ids.append(rid)
    except Exception:
        # best-effort: не ломаем расчёты при проблемах со справочником
        pass
    if not rd_ids:
        return {}

    field_name = parameter_key
    raw: dict[int, Decimal] = {}
    has_value: dict[int, bool] = {}
    for rd_id in rd_ids:
        demand_rows = dps.get_demand_rows(
            RegionalDistrictEnergyConsumptionParameter,
            "id_regional_district",
            rd_id,
        )
        for row in demand_rows:
            year_raw = getattr(row, "year_number", None)
            if year_raw is None:
                continue
            year_num = int(year_raw)
            value = getattr(row, field_name, None)
            if value is None:
                continue
            raw[year_num] = raw.get(year_num, Decimal(0)) + Decimal(str(value))
            has_value[year_num] = True

    return {
        int(year): raw.get(int(year)) if has_value.get(int(year)) else None
        for year in years
    }


def _resolve_first_synchronous_area_id() -> int | None:
    from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
        synchronous_area_display_order_sort_key,
    )

    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    areas = sorted(
        (sa for sa in query.all() if _is_valid_named_item(sa)),
        key=synchronous_area_display_order_sort_key,
    )
    if not areas:
        return None
    return int(areas[0].id)


def _resolve_synchronous_area_id_by_name_prefix_cf(prefix_cf: str) -> int | None:
    target = (prefix_cf or "").strip().casefold()
    if not target:
        return None
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        name_cf = (getattr(sa, "name", None) or "").strip().casefold()
        if name_cf.startswith(target):
            return int(sa.id)
    return None


def _resolve_kaliningrad_synchronous_area_id() -> int | None:
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        name_cf = (getattr(sa, "name", None) or "").strip().casefold()
        if _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF in name_cf:
            return int(sa.id)
    return None


def _resolve_regional_energy_system_id_by_name_cf(name_cf: str) -> int | None:
    target = (name_cf or "").strip().casefold()
    if not target:
        return None
    query = RegionalEnergySystem.query
    query = dps.filter_parents_by_version(query, RegionalEnergySystem)
    for res in query.all():
        if not _is_valid_named_item(res):
            continue
        if (getattr(res, "name", None) or "").strip().casefold() == target:
            return int(res.id)
    return None


def _year_values_from_parent_demand_rows(
    demand_model: type[Any],
    fk_column: str,
    parent_id: int,
    years: list[int],
    parameter_key: str,
    *,
    perimeter_variant_code: str | None = None,
) -> dict[int, Decimal | None]:
    if parameter_key not in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        return {}
    demand_rows = dps.get_demand_rows(
        demand_model,
        fk_column,
        parent_id,
        perimeter_variant_code=perimeter_variant_code,
    )
    raw: dict[int, Decimal] = {}
    has_value: dict[int, bool] = {}
    for row in demand_rows:
        year_raw = getattr(row, "year_number", None)
        if year_raw is None:
            continue
        year_num = int(year_raw)
        value = getattr(row, parameter_key, None)
        if value is None:
            continue
        raw[year_num] = raw.get(year_num, Decimal(0)) + Decimal(str(value))
        has_value[year_num] = True
    return {
        int(year): raw.get(int(year)) if has_value.get(int(year)) else None
        for year in years
    }


def _find_summary_parent_demand_row(
    summary_rows: list[dict[str, Any]],
    *,
    demand_model_name: str,
    parent_id: int,
    parameter_key: str,
    require_base_perimeter: bool = False,
) -> dict[str, Any] | None:
    for row in summary_rows:
        if row.get("demand_model_name") != demand_model_name:
            continue
        if row.get("parent_id") != parent_id:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if require_base_perimeter and not _is_summary_table_base_perimeter_row(row):
            continue
        return row
    return None


def _apply_sync_area_base_row_copy_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    synchronous_area_id: int,
    source_by_parameter: Callable[[str], dict[int, Decimal | None]],
    formula_tooltip: str,
    require_base_perimeter: bool = True,
) -> None:
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == synchronous_area_id
        and (not require_base_perimeter or _is_summary_table_base_perimeter_row(row))
    ]
    if not target_rows:
        return

    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = formula_tooltip

    wrote_any = False
    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        source = source_by_parameter(parameter_key)
        if not _year_values_have_any_numeric(source):
            continue
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            source,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )
        wrote_any = True

    if not wrote_any:
        return

    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_second_sa_from_ues_east_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Вторая синхронная зона = потребление ОЭС Востока."""
    if not summary_rows or not years:
        return

    second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(_SECOND_SYNC_AREA_BASE_LABEL_CF)
    ues_east_id = _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF)
    if second_sa_id is None or ues_east_id is None:
        return

    def _source(parameter_key: str) -> dict[int, Decimal | None]:
        row = _find_summary_parent_demand_row(
            summary_rows,
            demand_model_name=UnionEnergySystemEnergyConsumptionParameter.__name__,
            parent_id=ues_east_id,
            parameter_key=parameter_key,
            require_base_perimeter=True,
        )
        if row is not None:
            raw = _raw_year_values_from_summary_row(row, years)
            if _year_values_have_any_numeric(raw):
                return raw
        return _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            ues_east_id,
            years,
            parameter_key,
        )

    _apply_sync_area_base_row_copy_formula(
        summary_rows,
        years,
        rounding_digits,
        synchronous_area_id=second_sa_id,
        source_by_parameter=_source,
        formula_tooltip=_SECOND_SA_FROM_UES_EAST_FORMULA_TOOLTIP,
    )


def apply_kaliningrad_sa_from_kaliningrad_es_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Синхронная зона Калининградской области = потребление ЭС Калининградской области."""
    if not summary_rows or not years:
        return

    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    if kaliningrad_sa_id is None or kaliningrad_es_id is None:
        return

    def _source(parameter_key: str) -> dict[int, Decimal | None]:
        return _year_values_from_parent_demand_rows(
            RegionalEnergySystemEnergyConsumptionParameter,
            "id_regional_energy_system",
            kaliningrad_es_id,
            years,
            parameter_key,
        )

    _apply_sync_area_base_row_copy_formula(
        summary_rows,
        years,
        rounding_digits,
        synchronous_area_id=kaliningrad_sa_id,
        source_by_parameter=_source,
        formula_tooltip=_KALININGRAD_SA_FROM_ES_FORMULA_TOOLTIP,
        require_base_perimeter=False,
    )


def _union_energy_system_ids_for_synchronous_area(
    synchronous_area_id: int,
    *,
    ees_branch_only: bool = True,
) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    query = UnionEnergySystem.query.options(
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.regional_districts
        ),
        selectinload(UnionEnergySystem.energy_system_type),
    )
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    for ues in query.all():
        if not _is_valid_named_item(ues):
            continue
        if ees_branch_only and not _is_ees_branch(ues):
            continue
        ues_id = int(ues.id)
        if ues_id in seen:
            continue
        belongs = False
        for res in ues.regional_energy_systems or []:
            for rd in res.regional_districts or []:
                if getattr(rd, "id_synchronous_area", None) == synchronous_area_id:
                    belongs = True
                    break
            if belongs:
                break
        if belongs:
            seen.add(ues_id)
            out.append(ues_id)
    return out


def _kaliningrad_es_parameter_year_values(
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    if kaliningrad_es_id is None:
        return {}
    return _year_values_from_parent_demand_rows(
        RegionalEnergySystemEnergyConsumptionParameter,
        "id_regional_energy_system",
        kaliningrad_es_id,
        years,
        parameter_key,
    )


def _first_sa_with_nt_with_gaes_ues_exclude_ids() -> frozenset[int]:
    ues_east_id = _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF)
    if ues_east_id is None:
        return frozenset()
    return frozenset({int(ues_east_id)})


def _first_sa_without_nt_ues_exclude_ids() -> frozenset[int]:
    """ОЭС, не входящие в сумму первой СЗ для вариантов «без НТ» (без ОЭС «Новые территории»)."""
    excluded = set(_first_sa_with_nt_with_gaes_ues_exclude_ids())
    nt_ues_id = _resolve_new_territories_union_energy_system_id()
    if nt_ues_id is not None:
        excluded.add(int(nt_ues_id))
    return frozenset(excluded)


def _year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es(
    first_sa_id: int,
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    """Сумма ОЭС первой СЗ для варианта with_nt_with_gaes (с ЭС Калининграда).

    ОЭС Северо-Запада — обычная строка ``with_nt_with_gaes`` (без отдельного варианта
    with_kaliningrad_es). В сумму входят ОЭС первой СЗ и ОЭС «Новые территории»;
    исключается только ОЭС Востока.
    """
    exclude_ues_ids = _first_sa_with_nt_with_gaes_ues_exclude_ids()
    summed = _year_values_sum_ues_in_synchronous_area(
        first_sa_id,
        years,
        parameter_key,
        ues_variant_code=CODE_WITH_NT_WITH_GAES,
        exclude_ues_ids=exclude_ues_ids,
    )

    nt_ues_id = _resolve_new_territories_union_energy_system_id()
    if nt_ues_id is None:
        return summed
    if int(nt_ues_id) in _union_energy_system_ids_for_synchronous_area(first_sa_id):
        return summed

    nt_values = _year_values_from_parent_demand_rows(
        UnionEnergySystemEnergyConsumptionParameter,
        "id_union_energy_system",
        int(nt_ues_id),
        years,
        parameter_key,
        perimeter_variant_code=CODE_WITH_NT_WITH_GAES,
    )
    if not _year_values_have_any_numeric(nt_values):
        return summed
    return _sum_year_value_dicts(years, summed, nt_values)


def _first_sa_without_nt_with_gaes_ues_variant_codes() -> tuple[str | None, ...]:
    """Порядок вариантов периметра ОЭС для первой СЗ «без НТ с зарядом ГAЭС»."""
    return (
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
        None,
    )


def _year_values_from_ues_demand_first_variant_with_data(
    ues_id: int,
    years: list[int],
    parameter_key: str,
    variant_codes: tuple[str | None, ...],
) -> dict[int, Decimal | None]:
    if parameter_key not in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        return {}
    field_name = parameter_key
    for variant_code in variant_codes:
        demand_rows = dps.get_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            ues_id,
            perimeter_variant_code=variant_code,
        )
        if not demand_rows and variant_code is not None:
            demand_rows = dps.get_demand_rows(
                UnionEnergySystemEnergyConsumptionParameter,
                "id_union_energy_system",
                ues_id,
                perimeter_variant_code=None,
            )
        summed: dict[int, Decimal] = {}
        has_value: dict[int, bool] = {}
        for row in demand_rows:
            year_raw = getattr(row, "year_number", None)
            if year_raw is None:
                continue
            year_num = int(year_raw)
            value = getattr(row, field_name, None)
            if value is None:
                continue
            summed[year_num] = summed.get(year_num, Decimal(0)) + Decimal(str(value))
            has_value[year_num] = True
        if has_value:
            return {
                int(year): summed.get(int(year)) if has_value.get(int(year)) else None
                for year in years
            }
    return {int(year): None for year in years}


def _year_values_sum_ues_in_first_sa_without_kaliningrad_es(
    first_sa_id: int,
    years: list[int],
    parameter_key: str,
    *,
    exclude_ues_ids: frozenset[int] | None = None,
) -> dict[int, Decimal | None]:
    """Сумма ОЭС первой СЗ для варианта «без НТ с зарядом ГAЭС (без ЭС Калининграда)».

    Для каждой ОЭС: ``without_nt_with_gaes``, иначе ``with_kaliningrad_es``, иначе базовая строка;
    затем вычитается потребление ЭС Калининграда. ОЭС «Новые территории» и ОЭС Востока не входят.
    Отдельный заряд ГAЭС на уровне синхронной зоны не добавляется.
    """
    merged_exclude_ues_ids = _first_sa_without_nt_ues_exclude_ids()
    if exclude_ues_ids:
        merged_exclude_ues_ids = merged_exclude_ues_ids | exclude_ues_ids

    variant_codes = _first_sa_without_nt_with_gaes_ues_variant_codes()
    source_maps: list[dict[int, Decimal | None]] = []
    for ues_id in _union_energy_system_ids_for_synchronous_area(first_sa_id):
        if int(ues_id) in merged_exclude_ues_ids:
            continue
        ues_values = _year_values_from_ues_demand_first_variant_with_data(
            int(ues_id),
            years,
            parameter_key,
            variant_codes,
        )
        if _year_values_have_any_numeric(ues_values):
            source_maps.append(ues_values)
    if not source_maps:
        return {int(year): None for year in years}

    summed = _sum_year_value_dicts(years, *source_maps)
    kaliningrad_values = _kaliningrad_es_parameter_year_values(years, parameter_key)
    if not _year_values_have_any_numeric(kaliningrad_values):
        return summed
    return _subtract_year_value_dicts(years, summed, kaliningrad_values)


def _year_values_sum_ues_in_synchronous_area(
    synchronous_area_id: int,
    years: list[int],
    parameter_key: str,
    *,
    ues_variant_code: str | None,
    exclude_ues_ids: frozenset[int] | None = None,
    ues_variant_code_for_ues_id: Callable[[int], str | None] | None = None,
) -> dict[int, Decimal | None]:
    if parameter_key not in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        return {}
    field_name = parameter_key
    summed: dict[int, Decimal] = {}
    has_value: dict[int, bool] = {}
    for ues_id in _union_energy_system_ids_for_synchronous_area(synchronous_area_id):
        if exclude_ues_ids and int(ues_id) in exclude_ues_ids:
            continue
        variant_code = (
            ues_variant_code_for_ues_id(int(ues_id))
            if ues_variant_code_for_ues_id is not None
            else ues_variant_code
        )
        demand_rows = dps.get_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            ues_id,
            perimeter_variant_code=variant_code,
        )
        if not demand_rows and variant_code is not None:
            demand_rows = dps.get_demand_rows(
                UnionEnergySystemEnergyConsumptionParameter,
                "id_union_energy_system",
                ues_id,
                perimeter_variant_code=None,
            )
        for row in demand_rows:
            year_raw = getattr(row, "year_number", None)
            if year_raw is None:
                continue
            year_num = int(year_raw)
            value = getattr(row, field_name, None)
            if value is None:
                continue
            summed[year_num] = summed.get(year_num, Decimal(0)) + Decimal(str(value))
            has_value[year_num] = True
    return {
        int(year): summed.get(int(year)) if has_value.get(int(year)) else None
        for year in years
    }


def _gaes_charge_year_values_for_first_sa_without_nt(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    first_sa_id: int,
) -> dict[int, Decimal | None]:
    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    for row in summary_rows:
        if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
            continue
        if row.get("parent_id") != first_sa_id:
            continue
        if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
            continue
        label_cf = str(row.get("entity_label") or "").casefold()
        if "без нт" not in label_cf:
            continue
        if row.get("gaes_charge_row_station_name") == "всего":
            return _raw_year_values_from_summary_row(row, years)
        entity_key = _gaes_charge_entity_key(row)
        totals = gaes_totals.get(entity_key)
        if totals and _year_values_have_any_numeric(totals):
            return totals
    return {}


def _gaes_charge_year_values_for_first_sa_with_nt(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    first_sa_id: int,
) -> dict[int, Decimal | None]:
    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    for row in summary_rows:
        if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
            continue
        if row.get("parent_id") != first_sa_id:
            continue
        if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
            continue
        label_cf = str(row.get("entity_label") or "").casefold()
        if "с нт" not in label_cf:
            continue
        if row.get("gaes_charge_row_station_name") == "всего":
            return _raw_year_values_from_summary_row(row, years)
        entity_key = _gaes_charge_entity_key(row)
        totals = gaes_totals.get(entity_key)
        if totals and _year_values_have_any_numeric(totals):
            return totals
    return {}


def _mark_first_sa_variant_block_formula_derived(
    summary_rows: list[dict[str, Any]],
    *,
    first_sa_id: int,
    perimeter_variant_code: str,
) -> None:
    for row in summary_rows:
        if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
            continue
        if row.get("parent_id") != first_sa_id:
            continue
        if str(row.get("perimeter_variant_code") or "") != perimeter_variant_code:
            continue
        row["pd_ec_formula_derived_row"] = True


def apply_first_sa_with_nt_with_gaes_with_kaliningrad_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Первая СЗ с НТ с зарядом ГAЭС (с ЭС Калининграда) = сумма ОЭС первой СЗ."""
    if not summary_rows or not years:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return

    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT
    ]
    if not target_rows:
        return

    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        summed = _year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es(
            first_sa_id,
            years,
            parameter_key,
        )
        if not _year_values_have_any_numeric(summed):
            continue

        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            summed,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_first_sa_variant_block_formula_derived(
        summary_rows,
        first_sa_id=first_sa_id,
        perimeter_variant_code=_FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT,
    )
    for row in target_rows:
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = (
                _FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_FORMULA_TOOLTIP
            )

    block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT
    ]
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_first_sa_without_nt_with_gaes_without_kaliningrad_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Первая СЗ без НТ с зарядом ГAЭС (без Калининграда) = сумма ОЭС первой СЗ − ЭС Калининграда."""
    if not summary_rows or not years:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return

    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    if not target_rows:
        return

    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        summed = _year_values_sum_ues_in_first_sa_without_kaliningrad_es(
            first_sa_id,
            years,
            parameter_key,
        )
        if not _year_values_have_any_numeric(summed):
            continue

        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            summed,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_first_sa_variant_block_formula_derived(
        summary_rows,
        first_sa_id=first_sa_id,
        perimeter_variant_code=_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
    )
    for row in target_rows:
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = (
                _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP
            )

    block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_first_sa_with_nt_without_gaes_without_kaliningrad_diff_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Первая СЗ с НТ без заряда ГAЭС (без Калининграда) = с зарядом (с Калининградом) − заряд ГAЭС."""
    if not summary_rows or not years:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return

    source_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT
    ]
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    if not source_rows or not target_rows:
        return

    gaes_by_year = _gaes_charge_year_values_for_first_sa_with_nt(
        summary_rows,
        years,
        first_sa_id=first_sa_id,
    )
    if not _year_values_have_any_numeric(gaes_by_year):
        gaes_by_year = {}

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        source_row = next(
            (row for row in source_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if source_row is None or target_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_first_sa_variant_block_formula_derived(
        summary_rows,
        first_sa_id=first_sa_id,
        perimeter_variant_code=_FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT,
    )
    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        row["gaes_without_charge_formula_kind"] = (
            "first_sa_with_nt_without_kaliningrad_gaes_diff"
        )
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = (
                _FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP
            )

    block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_first_sa_without_nt_without_gaes_with_kaliningrad_diff_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Первая СЗ без НТ без заряда ГAЭС (с Калининградом) = с зарядом (с Калининградом) − заряд ГAЭС."""
    if not summary_rows or not years:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return

    source_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES
    ]
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT
    ]
    if not source_rows or not target_rows:
        return

    gaes_by_year = _gaes_charge_year_values_for_first_sa_without_nt(
        summary_rows,
        years,
        first_sa_id=first_sa_id,
    )
    if not _year_values_have_any_numeric(gaes_by_year):
        gaes_by_year = {}

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        source_row = next(
            (row for row in source_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if source_row is None or target_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_first_sa_variant_block_formula_derived(
        summary_rows,
        first_sa_id=first_sa_id,
        perimeter_variant_code=_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT,
    )
    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        row["gaes_without_charge_formula_kind"] = (
            "first_sa_without_nt_with_kaliningrad_gaes_diff"
        )
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = (
                _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_FORMULA_TOOLTIP
            )

    block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT
    ]
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_first_sa_without_nt_without_gaes_without_kaliningrad_diff_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Первая СЗ без НТ без заряда ГAЭС (без Калининграда) = с зарядом (без Калининграда) − заряд ГAЭС."""
    if not summary_rows or not years:
        return

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return

    source_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    if not source_rows or not target_rows:
        return

    gaes_by_year = _gaes_charge_year_values_for_first_sa_without_nt(
        summary_rows,
        years,
        first_sa_id=first_sa_id,
    )
    if not _year_values_have_any_numeric(gaes_by_year):
        gaes_by_year = {}

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        source_row = next(
            (row for row in source_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if source_row is None or target_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_first_sa_variant_block_formula_derived(
        summary_rows,
        first_sa_id=first_sa_id,
        perimeter_variant_code=_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT,
    )
    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        row["gaes_without_charge_formula_kind"] = (
            "first_sa_without_nt_without_kaliningrad_gaes_diff"
        )
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = (
                _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP
            )

    block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == first_sa_id
        and str(row.get("perimeter_variant_code") or "")
        == _FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT
    ]
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def _mark_ees_russia_variant_block_formula_derived(
    summary_rows: list[dict[str, Any]],
    *,
    perimeter_variant_code: str,
) -> None:
    for row in summary_rows:
        if row.get("demand_model_name") != EesRussiaEnergyConsumptionParameter.__name__:
            continue
        if row.get("entity_kind") != ENTITY_KIND_EES_RUSSIA:
            continue
        if str(row.get("perimeter_variant_code") or "") != perimeter_variant_code:
            continue
        row["pd_ec_formula_derived_row"] = True


@lru_cache(maxsize=1)
def _tites_union_energy_system_ids() -> frozenset[int]:
    query = UnionEnergySystem.query
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    return frozenset(
        int(ues.id)
        for ues in query.all()
        if _is_tites_branch(ues)
    )


def _is_sakha_yakutia_regional_energy_system_name(name: object) -> bool:
    normalized = str(name or "").casefold().replace("ё", "е")
    return all(marker in normalized for marker in _SAKHA_YAKUTIA_RES_NAME_MARKERS_CF)


@lru_cache(maxsize=1)
def _tites_sakha_yakutia_extra_energy_unit_ids() -> frozenset[int]:
    """Западный и Центральный энергорайоны ЭС Республики Саха (Якутия) входят в сумму ТИТЭС."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    extra: set[int] = set()
    for energy_unit in query.all():
        base_label = str(getattr(energy_unit, "name", None) or "").strip().casefold()
        if base_label not in _TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_CF:
            continue
        res = getattr(energy_unit, "regional_energy_system", None)
        if not _is_sakha_yakutia_regional_energy_system_name(getattr(res, "name", None)):
            continue
        extra.add(int(energy_unit.id))
    return frozenset(extra)


def _eu_row_in_tites_oes_formula_scope(
    row: dict[str, Any],
    *,
    tites_ues_ids: frozenset[int],
    sakha_extra_eu_ids: frozenset[int],
) -> bool:
    if (
        row.get("parent_fk_column") == "id_energy_unit"
        and row.get("parent_id") is not None
    ):
        try:
            eu_id = int(row["parent_id"])
        except (TypeError, ValueError):
            eu_id = None
        if eu_id is not None and eu_id in sakha_extra_eu_ids:
            return True
    ues_id = row.get("id_union_energy_system")
    return ues_id is not None and int(ues_id) in tites_ues_ids


def _year_values_have_any_numeric(raw_by_year: dict[int, Decimal | None]) -> bool:
    return any(value is not None for value in raw_by_year.values())


def _sum_year_value_dicts(
    years: list[int],
    *sources: dict[int, Decimal | None],
) -> dict[int, Decimal | None]:
    out: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        parts = [source.get(y) for source in sources if source.get(y) is not None]
        out[y] = sum(parts, Decimal(0)) if parts else None
    return out


def _find_sync_area_source_row(
    summary_rows: list[dict[str, Any]],
    *,
    parameter_key: str,
    base_label_prefix_cf: str,
    variant_predicate: Callable[[dict[str, Any]], bool],
) -> dict[str, Any] | None:
    matches = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parameter_key") == parameter_key
        and _summary_row_base_label_cf(row).startswith(base_label_prefix_cf)
        and variant_predicate(row)
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    for row in matches:
        if "with_kaliningrad_es" in str(row.get("perimeter_variant_code") or ""):
            return row
    return matches[0]


def _year_values_for_tites_source(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    type_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == EnergySystemTypeEnergyConsumptionParameter.__name__
        and row.get("parameter_key") == parameter_key
        and _summary_row_base_label_cf(row) == _TITES_TYPE_LABEL_CF
        and _is_summary_table_base_perimeter_row(row)
    ]
    if type_rows:
        raw = _raw_year_values_from_summary_row(type_rows[0], years)
        if _year_values_have_any_numeric(raw):
            return raw

    return _sum_tites_energy_units_by_parameter(
        summary_rows,
        years,
        parameter_key,
        parent_pvc=None,
    )


_NORTHWEST_UES_NAME_CF = "оэс северо-запада"
_CENTER_UES_NAME_CF = "оэс центра"
_CZ_RUSSIA_WITH_NT_FORMULA_COMPONENT_UES_BASE_LABELS_CF: tuple[str, ...] = (
    _NORTHWEST_UES_NAME_CF,
    _CENTER_UES_NAME_CF,
    MIDDLE_VOLGA_UES_NAME_CF,
    SOUTH_UES_NAME_CF,
    URAL_UES_NAME_CF,
)
_CZ_RUSSIA_WITH_NT_FORMULA_UES_VARIANT_CODES: tuple[str, ...] = (
    CODE_WITH_NT_WITH_GAES,
    CODE_WITH_NT,
)
_CZ_RUSSIA_WITHOUT_NT_FORMULA_UES_VARIANT_CODES: tuple[str, ...] = (
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT,
)
_CZ_RUSSIA_WITHOUT_NT_FORMULA_FROM_YEAR = 2022
_CZ_RUSSIA_WITH_NT_FORMULA_TOOLTIP = (
    "Потребление ЦЗ России с НТ, млн кВт·ч = "
    "ОЭС Северо-Запада + ОЭС Центра с зарядом ГАЭС + ОЭС Средней Волги + "
    "ОЭС Юга с НТ с зарядом ГАЭС + ОЭС Урала + "
    "Энергозона Сибири + Энергозона Востока"
)
_CZ_RUSSIA_WITHOUT_NT_FORMULA_TOOLTIP = (
    "Потребление ЦЗ России без НТ, млн кВт·ч = "
    "ОЭС Северо-Запада + ОЭС Центра с зарядом ГАЭС + ОЭС Средней Волги + "
    "ОЭС Юга без НТ с зарядом ГАЭС + ОЭС Урала + "
    "Энергозона Сибири + Энергозона Востока "
    f"(с {_CZ_RUSSIA_WITHOUT_NT_FORMULA_FROM_YEAR} г.)"
)
_SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL = "СПРАВОЧНО. Новые территории."
_SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_FROM_YEAR = 2024
_SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_TOOLTIP = (
    "Потребление «Справочно. Новые территории», млн кВт·ч = "
    "ЦЗ России с НТ − ЦЗ России без НТ "
    f"(с {_SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_FROM_YEAR} г.)"
)
_SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL = "Децентрализованная зона"
_SUMMARY_TABLE_DECENTRALIZED_ZONE_RUSSIA_SCALE = Decimal(1000)
_SUMMARY_TABLE_DECENTRALIZED_ZONE_FORMULA_TOOLTIP = (
    "Потребление «Децентрализованная зона», млн кВт·ч = "
    "Россия с НТ × 1000 − ЭЭС России без НТ с зарядом ГАЭС"
)


def _is_excluded_cz_formula_source_row(row: dict[str, Any]) -> bool:
    if "проверка" in str(row.get("entity_label") or "").casefold():
        return True
    entity_kind = str(row.get("entity_kind") or "")
    return entity_kind.endswith("_verification") or entity_kind == "oes_ees_sync_table_verification"


def _pick_ues_cz_formula_component_row(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
    *,
    base_label_cf: str,
    variant_codes: tuple[str, ...] = _CZ_RUSSIA_WITH_NT_FORMULA_UES_VARIANT_CODES,
) -> dict[str, Any] | None:
    candidates = [
        row
        for row in summary_rows
        if row.get("parameter_key") == parameter_key
        and row.get("demand_model_name") == UnionEnergySystemEnergyConsumptionParameter.__name__
        and _summary_row_base_label_cf(row) == base_label_cf
        and not _is_excluded_cz_formula_source_row(row)
    ]
    if not candidates:
        return None
    min_depth = min(int(row.get("entity_depth") or 0) for row in candidates)
    candidates = [
        row for row in candidates if int(row.get("entity_depth") or 0) == min_depth
    ]
    for variant_code in variant_codes:
        for row in candidates:
            if str(row.get("perimeter_variant_code") or "") == variant_code:
                return row
    return candidates[0]


def _pick_energy_zone_cz_formula_component_row(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
    *,
    entity_label: str,
) -> dict[str, Any] | None:
    target_label_cf = entity_label.strip().casefold()
    for row in summary_rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if int(row.get("entity_depth") or 0) != 0:
            continue
        if _is_excluded_cz_formula_source_row(row):
            continue
        if str(row.get("entity_label") or "").strip().casefold() != target_label_cf:
            continue
        return row
    return None


def _is_centralized_zone_o1_manual_row(row: dict[str, Any]) -> bool:
    """ЦЗ России, вариант О-1 (o1_with_nt / o1_without_nt) — ручной ввод на сводной таблице."""
    if row.get("demand_model_name") != CentralizedZoneEnergyConsumptionParameter.__name__:
        return False
    if not _is_centralized_zone_russia_summary_row(row):
        return False
    code = str(row.get("perimeter_variant_code") or "")
    return bool(code) and is_o1_perimeter_variant_code(code)


def _is_centralized_zone_o1_with_nt_manual_row(row: dict[str, Any]) -> bool:
    """Обратная совместимость: см. ``_is_centralized_zone_o1_manual_row``."""
    return _is_centralized_zone_o1_manual_row(row)


def _is_centralized_zone_with_nt_formula_target_row(row: dict[str, Any]) -> bool:
    if not _is_centralized_zone_russia_summary_row(row):
        return False
    if _is_centralized_zone_o1_manual_row(row):
        return False
    if row.get("pd_ec_nt_without_row"):
        return False
    label_cf = str(row.get("entity_label") or "").casefold()
    if "без нт" in label_cf:
        return False
    code = str(row.get("perimeter_variant_code") or "")
    if code and _nt_group_for_variant_code(code) == "without_nt":
        return False
    return bool(
        row.get("pd_ec_nt_extra_row")
        or " с нт" in label_cf
        or (code and _nt_group_for_variant_code(code) == "with_nt")
    )


def _is_centralized_zone_without_nt_formula_target_row(row: dict[str, Any]) -> bool:
    if not _is_centralized_zone_russia_summary_row(row):
        return False
    if _is_centralized_zone_o1_manual_row(row):
        return False
    label_cf = str(row.get("entity_label") or "").casefold()
    code = str(row.get("perimeter_variant_code") or "")
    if row.get("pd_ec_nt_without_row"):
        return True
    if "без нт" in label_cf:
        return True
    return bool(code and _nt_group_for_variant_code(code) == "without_nt")


def _mark_centralized_zone_o1_manual_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    for row in summary_rows:
        row.pop("pd_ec_cz_o1_manual_row", None)
        row.pop("pd_ec_cz_o1_with_nt_manual_row", None)
        if not _is_centralized_zone_o1_manual_row(row):
            continue
        row["pd_ec_cz_o1_manual_row"] = True
        row["pd_ec_cz_o1_with_nt_manual_row"] = True
        row.pop("pd_ec_formula_derived_row", None)
        row.pop("pd_ec_summary_row_formula_tooltip", None)


def _mark_centralized_zone_o1_with_nt_manual_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    _mark_centralized_zone_o1_manual_rows(summary_rows)


def _cz_formula_component_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
    *,
    ues_variant_codes: tuple[str, ...],
) -> dict[int, Decimal | None]:
    source_maps: list[dict[int, Decimal | None]] = []
    for base_label_cf in _CZ_RUSSIA_WITH_NT_FORMULA_COMPONENT_UES_BASE_LABELS_CF:
        component_row = _pick_ues_cz_formula_component_row(
            summary_rows,
            parameter_key,
            base_label_cf=base_label_cf,
            variant_codes=ues_variant_codes,
        )
        if component_row is None:
            continue
        raw = _raw_year_values_from_summary_row(component_row, years)
        if _year_values_have_any_numeric(raw):
            source_maps.append(raw)
    for entity_label in ("Энергозона Сибири", _EAST_ENERGY_ZONE_LABEL):
        component_row = _pick_energy_zone_cz_formula_component_row(
            summary_rows,
            parameter_key,
            entity_label=entity_label,
        )
        if component_row is None:
            continue
        raw = _raw_year_values_from_summary_row(component_row, years)
        if _year_values_have_any_numeric(raw):
            source_maps.append(raw)
    if not source_maps:
        return {int(year): None for year in years}
    return _sum_year_value_dicts(years, *source_maps)


def _cz_with_nt_formula_component_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    return _cz_formula_component_year_values(
        summary_rows,
        years,
        parameter_key,
        ues_variant_codes=_CZ_RUSSIA_WITH_NT_FORMULA_UES_VARIANT_CODES,
    )


def _cz_without_nt_formula_component_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    return _cz_formula_component_year_values(
        summary_rows,
        years,
        parameter_key,
        ues_variant_codes=_CZ_RUSSIA_WITHOUT_NT_FORMULA_UES_VARIANT_CODES,
    )


def _merge_cz_formula_values_from_year(
    years: list[int],
    calculated: dict[int, Decimal | None],
    existing: dict[int, Decimal | None],
    *,
    from_year: int,
) -> dict[int, Decimal | None]:
    merged: dict[int, Decimal | None] = {}
    for year in years:
        y = int(year)
        if y >= int(from_year):
            merged[y] = calculated.get(y)
        else:
            merged[y] = existing.get(y)
    return merged


def apply_centralized_zone_with_nt_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """ЦЗ России с НТ = сумма выбранных ОЭС и энергозон Сибири/Востока (сводная таблица)."""
    if not summary_rows or not years:
        return

    _mark_centralized_zone_o1_manual_rows(summary_rows)

    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == CentralizedZoneEnergyConsumptionParameter.__name__
        and _is_centralized_zone_with_nt_formula_target_row(row)
    ]
    if not target_rows:
        return

    wrote_any = False
    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        summed = _cz_with_nt_formula_component_year_values(
            summary_rows,
            years,
            parameter_key,
        )
        if not _year_values_have_any_numeric(summed):
            continue
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            summed,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )
        wrote_any = True

    if not wrote_any:
        return

    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = _CZ_RUSSIA_WITH_NT_FORMULA_TOOLTIP

    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_centralized_zone_without_nt_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """ЦЗ России без НТ = сумма ОЭС и энергозон (сводная таблица, с 2022 г.)."""
    if not summary_rows or not years:
        return

    _mark_centralized_zone_o1_manual_rows(summary_rows)

    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == CentralizedZoneEnergyConsumptionParameter.__name__
        and _is_centralized_zone_without_nt_formula_target_row(row)
    ]
    if not target_rows:
        return

    from_year = _CZ_RUSSIA_WITHOUT_NT_FORMULA_FROM_YEAR
    wrote_any = False
    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        summed = _cz_without_nt_formula_component_year_values(
            summary_rows,
            years,
            parameter_key,
        )
        if not _year_values_have_any_numeric(summed):
            continue
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        existing = _raw_year_values_from_summary_row(target_row, years)
        merged = _merge_cz_formula_values_from_year(
            years,
            summed,
            existing,
            from_year=from_year,
        )
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            merged,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )
        wrote_any = True

    if not wrote_any:
        return

    for row in target_rows:
        row["pd_ec_formula_derived_row"] = True
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = _CZ_RUSSIA_WITHOUT_NT_FORMULA_TOOLTIP

    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        target_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def _centralized_zone_russia_summary_row_match_key(
    row: dict[str, Any],
) -> tuple[str, str] | None:
    if not _is_centralized_zone_russia_summary_row(row):
        return None
    code = str(row.get("perimeter_variant_code") or "").strip()
    parameter_key = str(row.get("parameter_key") or "").strip()
    if not code or not parameter_key:
        return None
    return code, parameter_key


def _copy_summary_row_year_display_from_reference(
    target_row: dict[str, Any],
    reference_row: dict[str, Any],
    years: list[int],
    *,
    rounding_digits: int,
) -> None:
    source_values = list(reference_row.get("year_values") or [])
    source_tooltips = list(reference_row.get("year_numeric_tooltips") or [])
    if len(source_values) != len(years):
        raw = _raw_year_values_from_summary_row(reference_row, years)
        parameter_key = str(target_row.get("parameter_key") or "")
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            raw,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )
        return
    target_row["year_values"] = source_values
    target_row["year_numeric_tooltips"] = source_tooltips


def build_summary_table_hub_oes_formula_pipeline_summary_rows(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
) -> list[dict[str, Any]]:
    """Строки после пайплайна /energy_consumption/summary_table/ (корень ОЭС) + формулы ЦЗ.

    Нужны для PD: потребление ЦЗ / ЭЭС России / синхронных зон как в режиме
    «Сводная таблица» (+без ГАЭС).
    """
    from app.energy_consumption.pages._summary_page_transforms import (
        convert_context_to_summary_table_page,
    )

    ues_l, res_l, rd_l, eu_l = oes_territory_ordered or ((), (), (), ())
    context = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=(ues_l, res_l, rd_l, eu_l),
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_oes_summary_table_sync_sa_ees_verification=True,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = convert_context_to_summary_table_page(context)
    summary_rows = list(context.get("summary_rows") or [])
    years = list(context.get("years") or [])
    if not summary_rows or not years:
        return []
    append_summary_table_hub_energy_zone_footer_rows(
        summary_rows,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
    )
    apply_centralized_zone_with_nt_sum_formula(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
    )
    apply_centralized_zone_without_nt_sum_formula(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
    )
    return summary_rows


def _is_ees_or_synchronous_area_ec_summary_row(row: dict[str, Any]) -> bool:
    dm = str(row.get("demand_model_name") or "")
    return dm in (
        EesRussiaEnergyConsumptionParameter.__name__,
        SynchronousAreaEnergyConsumptionParameter.__name__,
    )


def build_summary_table_hub_centralized_zone_reference_summary_rows(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
) -> list[dict[str, Any]]:
    """Строки «ЦЗ России» после пайплайна /energy_consumption/summary_table/ (корень, разрез ОЭС)."""
    summary_rows = build_summary_table_hub_oes_formula_pipeline_summary_rows(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        oes_territory_ordered=oes_territory_ordered,
    )
    return [row for row in summary_rows if _is_centralized_zone_russia_summary_row(row)]


def build_summary_table_hub_ees_sa_reference_summary_rows(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
) -> list[dict[str, Any]]:
    """Строки ЭЭС России и синхронных зон после пайплайна summary_table (+без ГАЭС)."""
    summary_rows = build_summary_table_hub_oes_formula_pipeline_summary_rows(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        oes_territory_ordered=oes_territory_ordered,
    )
    return [
        row
        for row in summary_rows
        if _is_ees_or_synchronous_area_ec_summary_row(row)
        and str(row.get("parameter_key") or "") == "energy_consumption_mln_kvt_ch"
    ]


def apply_federal_district_centralized_zone_values_from_summary_table_hub(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    data_start_year: int | None = None,
    data_end_year: int | None = None,
) -> None:
    """На /summary/federal_districts/ и /summary/energy_zones/: «ЦЗ России …» как на /summary_table/."""
    if not summary_rows or not years:
        return
    if not any(_is_centralized_zone_russia_summary_row(row) for row in summary_rows):
        return

    dsy = data_start_year if data_start_year is not None else years[0]
    dey = data_end_year if data_end_year is not None else years[-1]
    reference_rows = build_summary_table_hub_centralized_zone_reference_summary_rows(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=dsy,
        data_end_year=dey,
        filter_year_list=filter_year_list,
    )
    if not reference_rows:
        return

    reference_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in reference_rows:
        key = _centralized_zone_russia_summary_row_match_key(row)
        if key is not None:
            reference_by_key[key] = row

    for target_row in summary_rows:
        key = _centralized_zone_russia_summary_row_match_key(target_row)
        if key is None:
            continue
        reference_row = reference_by_key.get(key)
        if reference_row is None:
            continue
        _copy_summary_row_year_display_from_reference(
            target_row,
            reference_row,
            years,
            rounding_digits=rounding_digits,
        )
        if reference_row.get("pd_ec_formula_derived_row"):
            target_row["pd_ec_formula_derived_row"] = True
        tooltip = reference_row.get("pd_ec_summary_row_formula_tooltip")
        if tooltip:
            target_row["pd_ec_summary_row_formula_tooltip"] = tooltip


def _pick_centralized_zone_nt_formula_summary_row(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
    *,
    with_nt: bool,
) -> dict[str, Any] | None:
    is_target = (
        _is_centralized_zone_with_nt_formula_target_row
        if with_nt
        else _is_centralized_zone_without_nt_formula_target_row
    )
    for row in summary_rows:
        if row.get("parameter_key") != parameter_key:
            continue
        if row.get("demand_model_name") != CentralizedZoneEnergyConsumptionParameter.__name__:
            continue
        if is_target(row):
            return row
    return None


def _summary_table_entity_block_start_index(
    summary_rows: list[dict[str, Any]],
    *,
    entity_kind: str,
) -> int | None:
    for index, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("entity_kind") == entity_kind:
            return index
    return None


def _summary_table_insert_index_after_centralized_zone_russia_blocks(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    """Индекс сразу после последней строки блока(ов) «ЦЗ России» (depth=0)."""
    last_end: int | None = None
    for index, row in enumerate(summary_rows):
        if not _is_centralized_zone_russia_summary_row(row):
            continue
        if int(row.get("entity_depth") or 0) != 0:
            continue
        last_end = index + 1
    return last_end


def inject_summary_table_cz_new_territories_reference_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Справочная строка после блоков «ЦЗ России»: ЦЗ с НТ − ЦЗ без НТ; видна только при «+НТ»."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_label") or "").strip() == _SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        for row in summary_rows
    ):
        return

    insert_at = _summary_table_insert_index_after_centralized_zone_russia_blocks(
        summary_rows
    )
    if insert_at is None:
        return

    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    cz_with_ec = _pick_centralized_zone_nt_formula_summary_row(
        summary_rows, ec_key, with_nt=True
    )
    cz_without_ec = _pick_centralized_zone_nt_formula_summary_row(
        summary_rows, ec_key, with_nt=False
    )
    cz_with_sipr = _pick_centralized_zone_nt_formula_summary_row(
        summary_rows, sipr_key, with_nt=True
    )
    cz_without_sipr = _pick_centralized_zone_nt_formula_summary_row(
        summary_rows, sipr_key, with_nt=False
    )
    if cz_with_ec is None or cz_without_ec is None:
        return

    from_year = _SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_FROM_YEAR
    diff_ec_raw = _subtract_year_value_dicts(
        years,
        _raw_year_values_from_summary_row(
            cz_with_ec, years, ignore_perimeter_variant_year_bounds=True
        ),
        _raw_year_values_from_summary_row(
            cz_without_ec, years, ignore_perimeter_variant_year_bounds=True
        ),
    )
    diff_ec = _merge_cz_formula_values_from_year(
        years,
        diff_ec_raw,
        {int(year): None for year in years},
        from_year=from_year,
    )
    if cz_with_sipr is not None and cz_without_sipr is not None:
        diff_sipr_raw = _subtract_year_value_dicts(
            years,
            _raw_year_values_from_summary_row(
                cz_with_sipr, years, ignore_perimeter_variant_year_bounds=True
            ),
            _raw_year_values_from_summary_row(
                cz_without_sipr, years, ignore_perimeter_variant_year_bounds=True
            ),
        )
        diff_sipr = _merge_cz_formula_values_from_year(
            years,
            diff_sipr_raw,
            {int(year): None for year in years},
            from_year=from_year,
        )
    else:
        diff_sipr = {}

    if not _year_values_have_any_numeric(diff_ec) and not _year_values_have_any_numeric(
        diff_sipr
    ):
        return

    template_row = cz_with_ec
    entity_depth = int(template_row.get("entity_depth") or 0)
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    new_block: list[dict[str, Any]] = []
    for idx, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        row = dict(template_row)
        row.pop("pd_ec_perimeter_entity_kind", None)
        row.pop("pd_ec_perimeter_entity_name", None)
        # Не наследовать флаги +НТ/+ГАЭС и compact-подписи с шаблона ЦЗ —
        # иначе строка выглядит как «ЦЗ России / не указано».
        for flag in (
            "pd_ec_nt_extra_row",
            "pd_ec_nt_without_row",
            "pd_ec_gaes_extra_row",
            "pd_ec_gaes_without_row",
            "pd_ec_collapsed_nt_gaes_visible_row",
            "pd_ec_collapsed_nt_gaes_redundant_row",
            "pd_ec_nt_on_gaes_off_visible_row",
            "pd_ec_nt_on_gaes_off_redundant_row",
            "pd_ec_expanded_nt_gaes_redundant_row",
            "pd_ec_territory_compact_hide_row",
            "pd_ec_territory_detail_row",
            "pd_ec_entity_label_compact",
            "pd_ec_entity_label_compact_nt",
            "pd_ec_entity_label_compact_nt_gaes",
            "show_perimeter_variant_select",
        ):
            row.pop(flag, None)
        row.update(
            {
                "entity_label": _SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL,
                "entity_rowspan": entity_rowspan,
                "entity_depth": entity_depth,
                "entity_kind": "summary_table_cz_nt_reference",
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "year_row_ids": [None for _ in years],
                "hist_row_id": None,
                "hist_value": "—",
                "year_values": ["—" for _ in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": ["" for _ in years],
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": idx == 0,
                "perimeter_variant_code": None,
                "perimeter_variant_label": "",
                "perimeter_variant_options": [],
                "pd_ec_entity_label_compact": _SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL,
                "pd_ec_entity_label_compact_nt": _SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL,
                "pd_ec_entity_label_compact_nt_gaes": _SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL,
                # Как блок «Новые территории»: скрыта до включения кнопки «+НТ».
                "pd_ec_nt_extra_row": True,
                "pd_ec_nt_without_row": False,
                "pd_ec_formula_derived_row": True,
                "pd_ec_skip_empty_hide_row": True,
                "pd_ec_skip_perimeter_variant_year_bounds": True,
            }
        )
        if parameter_key in (ec_key, sipr_key):
            row["pd_ec_summary_row_formula_tooltip"] = (
                _SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_TOOLTIP
            )
            row["pd_ec_formula_text_key"] = "summary_table_cz_nt_reference"
        new_block.append(row)

    if _year_values_have_any_numeric(diff_ec):
        target_ec = next(row for row in new_block if row.get("parameter_key") == ec_key)
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            diff_ec,
            parameter_key=ec_key,
            rounding_digits=rounding_digits,
        )
    if _year_values_have_any_numeric(diff_sipr):
        target_sipr = next(row for row in new_block if row.get("parameter_key") == sipr_key)
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            diff_sipr,
            parameter_key=sipr_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=ec_key,
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=sipr_key,
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )

    tag_energy_consumption_summary_rows_perimeter_variant_labels(new_block)
    summary_rows[insert_at:insert_at] = new_block


def inject_summary_table_decentralized_zone_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Сводная таблица (/summary_table/): расчётная строка после «Россия с НТ»."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_label") or "").strip() == _SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
        for row in summary_rows
    ):
        return

    insert_at = _summary_table_insert_index_after_russia_with_nt_before_gaes_charge(summary_rows)
    if insert_at is None:
        return

    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    russia_ec = _pick_russia_with_nt_summary_parameter_row(summary_rows, ec_key)
    russia_sipr = _pick_russia_with_nt_summary_parameter_row(summary_rows, sipr_key)
    ees_ec = _find_ees_russia_summary_parameter_row(
        summary_rows,
        parameter_key=ec_key,
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
    )
    ees_sipr = _find_ees_russia_summary_parameter_row(
        summary_rows,
        parameter_key=sipr_key,
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
    )
    if russia_ec is None or ees_ec is None:
        return

    diff_ec_raw = _subtract_year_value_dicts(
        years,
        _multiply_year_value_dicts_scalar(
            years,
            _raw_year_values_from_summary_row(
                russia_ec, years, ignore_perimeter_variant_year_bounds=True
            ),
            _SUMMARY_TABLE_DECENTRALIZED_ZONE_RUSSIA_SCALE,
        ),
        _raw_year_values_from_summary_row(
            ees_ec, years, ignore_perimeter_variant_year_bounds=True
        ),
    )
    if russia_sipr is not None and ees_sipr is not None:
        diff_sipr_raw = _subtract_year_value_dicts(
            years,
            _multiply_year_value_dicts_scalar(
                years,
                _raw_year_values_from_summary_row(
                    russia_sipr, years, ignore_perimeter_variant_year_bounds=True
                ),
                _SUMMARY_TABLE_DECENTRALIZED_ZONE_RUSSIA_SCALE,
            ),
            _raw_year_values_from_summary_row(
                ees_sipr, years, ignore_perimeter_variant_year_bounds=True
            ),
        )
    else:
        diff_sipr_raw = {}

    if not _year_values_have_any_numeric(diff_ec_raw) and not _year_values_have_any_numeric(
        diff_sipr_raw
    ):
        return

    template_row = russia_ec
    entity_depth = int(template_row.get("entity_depth") or 0)
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    new_block: list[dict[str, Any]] = []
    for idx, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        row = dict(template_row)
        row.pop("pd_ec_perimeter_entity_kind", None)
        row.pop("pd_ec_perimeter_entity_name", None)
        row.pop("pd_ec_nt_extra_row", None)
        row.pop("pd_ec_nt_without_row", None)
        row.update(
            {
                "entity_label": _SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL,
                "pd_ec_entity_label_compact": _SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL,
                "pd_ec_entity_label_compact_nt": _SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL,
                "pd_ec_entity_label_compact_nt_gaes": _SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL,
                "entity_rowspan": entity_rowspan,
                "entity_depth": entity_depth,
                "entity_kind": "summary_table_decentralized_zone",
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "year_row_ids": [None for _ in years],
                "hist_row_id": None,
                "hist_value": "—",
                "year_values": ["—" for _ in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": ["" for _ in years],
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": idx == 0,
                "perimeter_variant_code": None,
                "perimeter_variant_label": "",
                "perimeter_variant_options": [],
                "pd_ec_formula_derived_row": True,
                "pd_ec_skip_empty_hide_row": True,
                "pd_ec_skip_perimeter_variant_year_bounds": True,
            }
        )
        if parameter_key in (ec_key, sipr_key):
            row["pd_ec_summary_row_formula_tooltip"] = (
                _SUMMARY_TABLE_DECENTRALIZED_ZONE_FORMULA_TOOLTIP
            )
            row["pd_ec_formula_text_key"] = "summary_table_decentralized_zone"
        new_block.append(row)

    if _year_values_have_any_numeric(diff_ec_raw):
        target_ec = next(row for row in new_block if row.get("parameter_key") == ec_key)
        _write_numeric_year_values_to_summary_row(
            target_ec,
            years,
            diff_ec_raw,
            parameter_key=ec_key,
            rounding_digits=rounding_digits,
        )
    if _year_values_have_any_numeric(diff_sipr_raw):
        target_sipr = next(row for row in new_block if row.get("parameter_key") == sipr_key)
        _write_numeric_year_values_to_summary_row(
            target_sipr,
            years,
            diff_sipr_raw,
            parameter_key=sipr_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=ec_key,
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        new_block,
        years,
        base_parameter_key=sipr_key,
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )

    tag_energy_consumption_summary_rows_perimeter_variant_labels(new_block)
    summary_rows[insert_at:insert_at] = new_block


def _apply_ees_russia_with_gaes_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    target_variant_code: str,
    first_sa_variant_predicate: Callable[[dict[str, Any]], bool],
    extra_source_by_parameter: Callable[[str], dict[int, Decimal | None]] | None = None,
    formula_tooltip: str | None = None,
    include_kaliningrad_sync_area: bool = True,
    eu_source_rows_for_tites: list[dict[str, Any]] | None = None,
) -> None:
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__
        and row.get("entity_kind") == ENTITY_KIND_EES_RUSSIA
        and str(row.get("perimeter_variant_code") or "") == target_variant_code
    ]
    if not target_rows:
        return

    for parameter_key in _EES_RUSSIA_WITHOUT_NT_WITH_GAES_SUM_PARAM_KEYS:
        first_sa_row = _find_sync_area_source_row(
            summary_rows,
            parameter_key=parameter_key,
            base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
            variant_predicate=first_sa_variant_predicate,
        )
        second_sa_row = _find_sync_area_source_row(
            summary_rows,
            parameter_key=parameter_key,
            base_label_prefix_cf=_SECOND_SYNC_AREA_BASE_LABEL_CF,
            variant_predicate=_is_summary_table_base_perimeter_row,
        )
        kaliningrad_sa_row: dict[str, Any] | None = None
        if include_kaliningrad_sync_area:
            for row in summary_rows:
                if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
                    continue
                if row.get("parameter_key") != parameter_key:
                    continue
                if not _is_kaliningrad_sync_area_summary_table_row(row):
                    continue
                kaliningrad_sa_row = row
                break

        source_maps: list[dict[int, Decimal | None]] = []
        if first_sa_row is not None:
            source_maps.append(_raw_year_values_from_summary_row(first_sa_row, years))
        if second_sa_row is not None:
            source_maps.append(_raw_year_values_from_summary_row(second_sa_row, years))
        if kaliningrad_sa_row is not None:
            source_maps.append(_raw_year_values_from_summary_row(kaliningrad_sa_row, years))
        tites_rows = (
            eu_source_rows_for_tites
            if eu_source_rows_for_tites is not None
            else summary_rows
        )
        source_maps.append(
            _year_values_for_tites_source(tites_rows, years, parameter_key)
        )
        if extra_source_by_parameter is not None:
            extra = extra_source_by_parameter(parameter_key)
            if _year_values_have_any_numeric(extra):
                source_maps.append(extra)
        if not source_maps:
            continue

        summed = _sum_year_value_dicts(years, *source_maps)
        target_row = next(
            (row for row in target_rows if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None:
            continue
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            summed,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _mark_ees_russia_variant_block_formula_derived(
        summary_rows,
        perimeter_variant_code=target_variant_code,
    )
    for row in target_rows:
        if formula_tooltip and row.get("parameter_key") == "energy_consumption_mln_kvt_ch":
            row["pd_ec_summary_row_formula_tooltip"] = formula_tooltip

    ees_block_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__
        and row.get("entity_kind") == ENTITY_KIND_EES_RUSSIA
        and str(row.get("perimeter_variant_code") or "") == target_variant_code
    ]
    _recompute_growth_rows_from_base_series(
        ees_block_rows,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        ees_block_rows,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )


def apply_ees_russia_gaes_aggregate_formulas(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    eu_source_rows_for_tites: list[dict[str, Any]] | None = None,
) -> None:
    """Пересчёт строк «ЕЭС России» с зарядом ГАЭС (с/без НТ) после готовности ТИТЭС."""
    _apply_ees_russia_with_gaes_sum_formula(
        summary_rows,
        years,
        rounding_digits,
        target_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        first_sa_variant_predicate=_is_without_nt_with_gaes_with_kaliningrad_variant_row,
        formula_tooltip=_EES_RUSSIA_WITHOUT_NT_WITH_GAES_FORMULA_TOOLTIP,
        include_kaliningrad_sync_area=False,
        eu_source_rows_for_tites=eu_source_rows_for_tites,
    )
    _apply_ees_russia_with_gaes_sum_formula(
        summary_rows,
        years,
        rounding_digits,
        target_variant_code=CODE_WITH_NT_WITH_GAES,
        first_sa_variant_predicate=_is_with_nt_with_gaes_variant_row,
        formula_tooltip=_EES_RUSSIA_WITH_NT_WITH_GAES_FORMULA_TOOLTIP,
        eu_source_rows_for_tites=eu_source_rows_for_tites,
    )


def apply_summary_table_formula_calculations(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    eu_source_rows_for_tites: list[dict[str, Any]] | None = None,
) -> None:
    """Пересчёт строк сводной таблицы с формулами (как на /summary_table/)."""
    if not summary_rows or not years:
        return

    apply_first_sa_with_nt_with_gaes_with_kaliningrad_sum_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_first_sa_without_nt_with_gaes_without_kaliningrad_sum_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_second_sa_from_ues_east_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_kaliningrad_sa_from_kaliningrad_es_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_ees_russia_gaes_aggregate_formulas(
        summary_rows,
        years,
        rounding_digits,
        eu_source_rows_for_tites=eu_source_rows_for_tites,
    )
    apply_gaes_without_charge_formula_to_summary_rows(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_first_sa_with_nt_without_gaes_without_kaliningrad_diff_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_first_sa_without_nt_without_gaes_with_kaliningrad_diff_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_first_sa_without_nt_without_gaes_without_kaliningrad_diff_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_centralized_zone_with_nt_sum_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    apply_centralized_zone_without_nt_sum_formula(
        summary_rows,
        years,
        rounding_digits,
    )
    tag_ees_russia_sipr_integer_display_rows(summary_rows)


def apply_ees_russia_without_nt_with_gaes_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Сводная таблица: формулы ЕЭС России и «без заряда ГАЭС» (обратная совместимость)."""
    apply_summary_table_formula_calculations(summary_rows, years, rounding_digits)


_FO_FORMULA_BASE_PARAMETER_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
    }
)
_FO_FORMULA_TOOLTIP = (
    "Потребление по ФО = сумма потребления ЭЭ всех РЭС, входящих в данный ФО"
)
_SOUTH_FO_WITH_NT_FORMULA_TOOLTIP = (
    "Потребление по Южному ФО (+НТ) = сумма потребления ЭЭ всех РЭС, входящих в Южный ФО, "
    "+ сумма по блоку «Новые территории»"
)
_TITES_OES_SAKHA_EXTRA_TOOLTIP_SUFFIX = (
    "Западный и Центральный энергорайоны ЭС Республики Саха (Якутия) учитываются "
    f"только до {_TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR} года включительно"
)
_TITES_OES_FORMULA_TOOLTIP = (
    "Потребление ТИТЭС, млн кВт·ч = сумма потребления ЭЭ всех энергорайонов, "
    "входящих в ТИТЭС, + Западный и Центральный энергорайоны ЭС Республики Саха (Якутия) "
    "(строки с вариантом О-1 не учитываются). "
    f"{_TITES_OES_SAKHA_EXTRA_TOOLTIP_SUFFIX}"
)
_TITES_OES_AGGREGATE_VERIFICATION_LABEL = "Проверка для ТИТЭС"
_TITES_OES_AGGREGATE_VERIFICATION_TOOLTIP = (
    "Проверка для ТИТЭС = потребление ТИТЭС − "
    "сумма потребления ЭЭ всех энергорайонов, входящих в ТИТЭС, − "
    "Западный энергорайон − Центральный энергорайон Республики Саха (Якутия) "
    "(строки с вариантом О-1 не учитываются; "
    f"{_TITES_OES_SAKHA_EXTRA_TOOLTIP_SUFFIX.lower()})"
)


def _eu_row_matches_tites_parent_perimeter(
    eu_row: dict[str, Any],
    parent_pvc: str | None,
) -> bool:
    parent_code = str(parent_pvc or "").strip()
    eu_code = str(eu_row.get("perimeter_variant_code") or "").strip()
    if not parent_code:
        return not eu_code
    if eu_code == parent_code:
        return True
    agg = _fo_res_aggregate_variant_code(parent_pvc)
    if agg in (CODE_WITH_NT, CODE_WITHOUT_NT) and not eu_code:
        return True
    return False


def _sum_tites_energy_units_by_parameter(
    source_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
    parent_pvc: str | None,
    *,
    sakha_extra_mode: str = "include",
) -> dict[int, Decimal | None]:
    """Сумма энергорайонов для формулы ТИТЭС.

    sakha_extra_mode: include — ветка ТИТЭС + Западный/Центральный Саха (Якутия);
    exclude — только энергорайоны ветки ТИТЭС; only — только Западный/Центральный Саха.
    """
    tites_ids = _tites_union_energy_system_ids()
    sakha_extra_eu_ids = _tites_sakha_yakutia_extra_energy_unit_ids()
    eu_model = EnergyUnitEnergyConsumptionParameter.__name__
    res_model = RegionalEnergySystemEnergyConsumptionParameter.__name__
    summed: dict[int, Decimal] = {}
    eu_by_res_year: dict[int, dict[int, Decimal]] = {}

    def _include_tites_energy_unit_row(row: dict[str, Any]) -> bool:
        if row.get("pd_ec_gaes_injected_row"):
            return False
        if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(
            row.get("perimeter_variant_code")
        ):
            return False
        try:
            eu_id = (
                int(row["parent_id"])
                if row.get("parent_fk_column") == "id_energy_unit"
                and row.get("parent_id") is not None
                else None
            )
        except (TypeError, ValueError):
            eu_id = None
        ues_id = row.get("id_union_energy_system")
        in_sakha = eu_id is not None and eu_id in sakha_extra_eu_ids
        in_branch = ues_id is not None and int(ues_id) in tites_ids
        if sakha_extra_mode == "exclude":
            if in_sakha or not in_branch:
                return False
        elif sakha_extra_mode == "only":
            if not in_sakha:
                return False
        elif not _eu_row_in_tites_oes_formula_scope(
            row,
            tites_ues_ids=tites_ids,
            sakha_extra_eu_ids=sakha_extra_eu_ids,
        ):
            return False
        return _eu_row_matches_tites_parent_perimeter(row, parent_pvc)

    for row in source_rows:
        if row.get("demand_model_name") != eu_model:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if not _include_tites_energy_unit_row(row):
            continue
        res_id = row.get("id_regional_energy_system")
        try:
            eu_id_for_year = (
                int(row["parent_id"])
                if row.get("parent_fk_column") == "id_energy_unit"
                and row.get("parent_id") is not None
                else None
            )
        except (TypeError, ValueError):
            eu_id_for_year = None
        in_sakha_extra = eu_id_for_year is not None and eu_id_for_year in sakha_extra_eu_ids
        for year, value in _raw_year_values_from_summary_row(row, years).items():
            if value is None:
                continue
            y = int(year)
            if (
                in_sakha_extra
                and y > _TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR
            ):
                continue
            summed[y] = summed.get(y, Decimal(0)) + value
            if res_id is not None and sakha_extra_mode == "include":
                res_bucket = eu_by_res_year.setdefault(int(res_id), {})
                res_bucket[y] = res_bucket.get(y, Decimal(0)) + value

    if sakha_extra_mode == "include":
        for row in source_rows:
            if row.get("demand_model_name") != res_model:
                continue
            if row.get("parameter_key") != parameter_key:
                continue
            if row.get("pd_ec_gaes_injected_row"):
                continue
            if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(
                row.get("perimeter_variant_code")
            ):
                continue
            if not _res_summary_row_belongs_to_tites_branch(source_rows, row):
                continue
            if not _eu_row_matches_tites_parent_perimeter(row, parent_pvc):
                continue
            if row.get("parent_fk_column") != "id_regional_energy_system":
                continue
            try:
                res_id = int(row["parent_id"])
            except (TypeError, ValueError):
                continue
            for year, value in _raw_year_values_from_summary_row(row, years).items():
                if value is None:
                    continue
                y = int(year)
                if eu_by_res_year.get(res_id, {}).get(y, Decimal(0)) > 0:
                    continue
                summed[y] = summed.get(y, Decimal(0)) + value
    return dict(summed)


def _is_oes_ees_unified_summary_block_anchor_row(row: dict[str, Any]) -> bool:
    """Корневая строка блока «ЕЭС России» на сводке по ОЭС (тип энергосистемы)."""
    if not row.get("show_entity_cell"):
        return False
    type_model = EnergySystemTypeEnergyConsumptionParameter.__name__
    if row.get("demand_model_name") != type_model:
        return False
    if _summary_row_base_label_cf(row) != EES_UNIFIED_REF_NAME.casefold():
        return False
    return row.get("entity_kind") in (
        "group-root",
        "perimeter_variant",
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        "default",
    )


def _ues_row_included_for_oes_ees_unified_block_variant(
    row: dict[str, Any],
    ees_unified_perimeter_variant: str | None,
) -> bool:
    row_code = row.get("perimeter_variant_code")
    if row_code is None:
        return True
    target = ees_unified_perimeter_variant or CODE_WITHOUT_NT
    return str(row_code) == str(target)


def _sum_oes_ees_branch_ues_parameter_by_year(
    rows: list[dict[str, Any]],
    *,
    years: list[int],
    parameter_key: str,
    perimeter_variant_code: str | None,
) -> dict[int, Decimal | None]:
    """Сумма потребления по ОЭС ветки «ЕЭС России» (без ТИТЭС Сибири/Востока)."""
    ues_model = UnionEnergySystemEnergyConsumptionParameter.__name__
    target_pvc = perimeter_variant_code or CODE_WITHOUT_NT
    sums: dict[int, Decimal] = {}
    seen_years: set[int] = set()
    counted_ues: set[int] = set()
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        if row.get("demand_model_name") != ues_model:
            i += 1
            continue
        if row.get("parent_fk_column") != "id_union_energy_system":
            i += 1
            continue
        if _is_oes_summary_hidden_tites_union_energy_system_label(
            _summary_row_base_label_cf(row)
        ):
            i += 1
            continue
        if _summary_row_skip_oes_gaes_charge_verification(row):
            i += 1
            continue
        code = row.get("perimeter_variant_code")
        if not _ues_row_included_for_oes_ees_unified_block_variant(row, target_pvc):
            i += 1
            continue
        ues_id = row.get("parent_id")
        if ues_id is None:
            i += 1
            continue
        try:
            ues_id_int = int(ues_id)
        except (TypeError, ValueError):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        if ues_id_int in counted_ues:
            i += block_size
            continue
        counted_ues.add(ues_id_int)
        param_row = _find_summary_parameter_row(
            rows,
            parameter_key=parameter_key,
            demand_model_name=ues_model,
            parent_fk_column="id_union_energy_system",
            parent_id=ues_id_int,
            perimeter_variant_code=code,
        )
        if param_row is not None:
            for year, value in _raw_year_values_from_summary_row(param_row, years).items():
                if value is None:
                    continue
                y = int(year)
                sums[y] = sums.get(y, Decimal(0)) + value
                seen_years.add(y)
        i += block_size
    return {int(y): sums.get(int(y)) if int(y) in seen_years else None for y in years}


def _ees_unified_with_nt_year_addon(
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    if parameter_key not in _FO_FORMULA_BASE_PARAMETER_KEYS:
        return {int(y): None for y in years}
    return _new_territories_parameter_year_values(years, parameter_key)


def tag_oes_ees_unified_summary_nt_toggle_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    """«ЕЭС России»: при +НТ выкл. — одна подпись «ЕЭС России», не скрывать пустой блок."""
    type_model = EnergySystemTypeEnergyConsumptionParameter.__name__
    label_cf = EES_UNIFIED_REF_NAME.casefold()
    for row in summary_rows:
        if row.get("demand_model_name") != type_model:
            continue
        if _summary_row_base_label_cf(row) != label_cf:
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if code == CODE_WITHOUT_NT:
            row["pd_ec_entity_label_compact_nt"] = EES_UNIFIED_REF_NAME
            row["pd_ec_entity_label_compact_nt_gaes"] = EES_UNIFIED_REF_NAME
            row["pd_ec_skip_empty_hide_row"] = True
        elif code == CODE_WITH_NT:
            row["pd_ec_skip_empty_hide_row"] = True


def apply_oes_ees_unified_consumption_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    ues_source_rows: list[dict[str, Any]] | None = None,
) -> None:
    """«ЕЭС России» на /summary/oes/: mln/sipr = сумма ОЭС (+ НТ для варианта with_nt)."""
    if not summary_rows or not years:
        return

    ues_rows = ues_source_rows if ues_source_rows is not None else summary_rows

    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_oes_ees_unified_summary_block_anchor_row(row):
            i += 1
            continue

        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        parent_pvc = row.get("perimeter_variant_code")

        for parameter_key in _FO_FORMULA_BASE_PARAMETER_KEYS:
            target_row = next(
                (r for r in block if r.get("parameter_key") == parameter_key),
                None,
            )
            if target_row is None:
                continue
            computed_by_year = _sum_oes_ees_branch_ues_parameter_by_year(
                ues_rows,
                years=years,
                parameter_key=parameter_key,
                perimeter_variant_code=parent_pvc,
            )
            if _nt_group_for_variant_code(str(parent_pvc or "")) == "with_nt":
                nt_addon = _ees_unified_with_nt_year_addon(years, parameter_key)
                computed_by_year = {
                    int(y): (
                        (computed_by_year.get(int(y)) or Decimal(0))
                        + (nt_addon.get(int(y)) or Decimal(0))
                        if computed_by_year.get(int(y)) is not None
                        or nt_addon.get(int(y)) is not None
                        else None
                    )
                    for y in years
                }
            existing_by_year = _raw_year_values_from_summary_row(target_row, years)
            merged_by_year: dict[int, Decimal | None] = {}
            for year in years:
                y = int(year)
                computed = computed_by_year.get(y)
                if computed is not None:
                    merged_by_year[y] = computed
                else:
                    merged_by_year[y] = existing_by_year.get(y)
            _write_numeric_year_values_to_summary_row(
                target_row,
                years,
                merged_by_year,
                parameter_key=parameter_key,
                rounding_digits=rounding_digits,
            )
            target_row["pd_ec_formula_derived_row"] = True
            if parameter_key == "energy_consumption_mln_kvt_ch":
                formula_key = (
                    "oes_ees_russia_with_nt_mln"
                    if _nt_group_for_variant_code(str(parent_pvc or "")) == "with_nt"
                    else "oes_ees_russia_without_nt_mln"
                )
                target_row["pd_ec_formula_text_key"] = formula_key
                target_row["ees_aggregate_embedded_demand_rows"] = True

        for block_row in block:
            block_row["pd_ec_formula_derived_row"] = True

        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_mln_kvt_ch",
            abs_parameter_key=None,
            yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
            abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        i += block_size


def _is_oes_tites_root_summary_block_anchor_row(row: dict[str, Any]) -> bool:
    """Корневая строка блока «ТИТЭС» на сводке по ОЭС (тип энергосистемы)."""
    if not row.get("show_entity_cell"):
        return False
    type_model = EnergySystemTypeEnergyConsumptionParameter.__name__
    if row.get("demand_model_name") != type_model:
        return False
    if _summary_row_base_label_cf(row) != _TITES_TYPE_LABEL_CF:
        return False
    return row.get("entity_kind") in (
        "group-root",
        "perimeter_variant",
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        "default",
    )


def apply_oes_tites_root_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    eu_source_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Строка «ТИТЭС» на /summary/oes/: mln/sipr = сумма энергорайонов ветки ТИТЭС."""
    if not summary_rows or not years:
        return

    eu_rows = eu_source_rows if eu_source_rows is not None else summary_rows

    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_oes_tites_root_summary_block_anchor_row(row):
            i += 1
            continue

        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        parent_pvc = row.get("perimeter_variant_code")

        for parameter_key in _FO_FORMULA_BASE_PARAMETER_KEYS:
            target_row = next(
                (r for r in block if r.get("parameter_key") == parameter_key),
                None,
            )
            if target_row is None:
                continue
            computed_by_year = _sum_tites_energy_units_by_parameter(
                eu_rows,
                years,
                parameter_key,
                parent_pvc,
            )
            existing_by_year = _raw_year_values_from_summary_row(target_row, years)
            merged_by_year: dict[int, Decimal | None] = {}
            for year in years:
                y = int(year)
                computed = computed_by_year.get(y)
                if computed is not None:
                    merged_by_year[y] = computed
                else:
                    merged_by_year[y] = existing_by_year.get(y)
            _write_numeric_year_values_to_summary_row(
                target_row,
                years,
                merged_by_year,
                parameter_key=parameter_key,
                rounding_digits=rounding_digits,
            )
            target_row["pd_ec_formula_derived_row"] = True
            if parameter_key == "energy_consumption_mln_kvt_ch":
                target_row["pd_ec_tites_oes_root"] = True
                target_row["pd_ec_formula_text_key"] = "oes_tites_mln"
                target_row["pd_ec_summary_row_formula_tooltip"] = _TITES_OES_FORMULA_TOOLTIP

        for block_row in block:
            block_row["pd_ec_formula_derived_row"] = True
            if block_row.get("parameter_key") in (
                "energy_consumption_mln_kvt_ch",
                "energy_consumption_sipr_mln_kvt_ch",
            ):
                block_row["pd_ec_summary_row_formula_tooltip"] = _TITES_OES_FORMULA_TOOLTIP
        if block:
            block[0]["pd_ec_tites_oes_root"] = True

        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_mln_kvt_ch",
            abs_parameter_key=None,
            yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
            abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        i += block_size


def _find_oes_tites_root_parameter_rows(
    summary_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, int]:
    """Строки потребления корневого блока «ТИТЭС» на сводке ОЭС."""
    type_model = EnergySystemTypeEnergyConsumptionParameter.__name__
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    for index, row in enumerate(summary_rows):
        if not _is_oes_tites_root_summary_block_anchor_row(row):
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[index : index + block_size]
        ec_row = next(
            (
                block_row
                for block_row in block
                if block_row.get("parameter_key") == ec_key
                and block_row.get("pd_ec_tites_oes_root")
            ),
            None,
        )
        sipr_row = next(
            (
                block_row
                for block_row in block
                if block_row.get("parameter_key") == sipr_key
            ),
            None,
        )
        if ec_row is None:
            continue
        return (
            ec_row,
            sipr_row,
            row.get("perimeter_variant_code"),
            int(row.get("entity_depth") or 0),
        )
    return None, None, None, 0


def inject_oes_tites_aggregate_verification_row(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]] | None = None,
    years: list[int],
    rounding_digits: int,
) -> None:
    """В конец сводки ОЭС: «Проверка ТИТЭС» = ТИТЭС − энергорайоны ветки − Западный/Центральный Саха."""
    if not summary_rows or not years:
        return
    if any(
        str(row.get("entity_kind") or "") == "oes_tites_aggregate_check"
        for row in summary_rows
    ):
        return

    base_ec_row, base_sipr_row, parent_pvc, entity_depth = _find_oes_tites_root_parameter_rows(
        summary_rows
    )
    if base_ec_row is None:
        return

    eu_rows = source_rows if source_rows is not None else summary_rows
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    branch_ec = _sum_tites_energy_units_by_parameter(
        eu_rows, years, ec_key, parent_pvc, sakha_extra_mode="exclude"
    )
    sakha_ec = _sum_tites_energy_units_by_parameter(
        eu_rows, years, ec_key, parent_pvc, sakha_extra_mode="only"
    )
    sum_ec = _sum_year_value_dicts(years, branch_ec, sakha_ec)
    branch_sipr = _sum_tites_energy_units_by_parameter(
        eu_rows, years, sipr_key, parent_pvc, sakha_extra_mode="exclude"
    )
    sakha_sipr = _sum_tites_energy_units_by_parameter(
        eu_rows, years, sipr_key, parent_pvc, sakha_extra_mode="only"
    )
    sum_sipr = _sum_year_value_dicts(years, branch_sipr, sakha_sipr)

    verification_rows = _build_ec_summary_verification_rows(
        entity_label=_TITES_OES_AGGREGATE_VERIFICATION_LABEL,
        entity_kind="oes_tites_aggregate_check",
        entity_depth=entity_depth,
        years=years,
        rounding_digits=rounding_digits,
        base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
        sum_ec=sum_ec,
        base_sipr=_raw_year_values_from_summary_row(
            base_sipr_row if base_sipr_row is not None else base_ec_row,
            years,
        ),
        sum_sipr=sum_sipr,
        formula_tooltip=_TITES_OES_AGGREGATE_VERIFICATION_TOOLTIP,
    )
    if verification_rows:
        summary_rows.extend(verification_rows)


def apply_federal_district_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Строки ФО: mln/sipr как сумма РЭС округа; темпы прироста — от пересчитанной серии."""
    if not summary_rows or not years:
        return

    south_fd_id = _resolve_federal_district_id_by_name_cf(SOUTH_FD_NAME_CF)
    nt_sum_by_key: dict[str, dict[int, Decimal | None]] = {}
    if south_fd_id is not None and south_ues_base_tree_includes_new_territories(years):
        # Важно: инжект блока «Новые территории» под «Южный ФО» выполняется ПОСЛЕ применения
        # формулы ФО (см. маршруты). Поэтому добавку для «Южный ФО с НТ» вычисляем здесь
        # самостоятельно, тем же способом, что и для инжектируемого блока: суммой по субъектам.
        south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
        if south_ues_id is not None:
            nt_rows = _build_new_territories_subjects_summary_rows(
                years=years,
                rounding_digits=rounding_digits,
                south_ues_id=south_ues_id,
                summary_rows=summary_rows,
            )
            if nt_rows:
                for pk in _FO_FORMULA_BASE_PARAMETER_KEYS:
                    nt_row = next(
                        (
                            r
                            for r in nt_rows
                            if r.get("entity_kind") == "fo_nt_under_south"
                            and r.get("parameter_key") == pk
                        ),
                        None,
                    )
                    if nt_row is not None:
                        nt_sum_by_key[pk] = _raw_year_values_from_summary_row(nt_row, years)

    def _fo_res_aggregate_variant_code(source_pvc: Any) -> str | None:
        """Агрегаты РЭС обычно считаются только по базовым вариантам НТ.

        Для строк ФО с вариантами, содержащими суффиксы `with_gaes/without_gaes` (и/или другие уточнения),
        берём базовый вариант НТ, чтобы сумма РЭС корректно находилась.
        """
        code = str(source_pvc or "").strip()
        if code == "":
            return None
        if code in (CODE_WITH_NT, CODE_WITHOUT_NT):
            return code
        # Варианты с ГАЭС/Калининградом/и т.п. сводим к базовому варианту НТ.
        if code.startswith("with_nt") or code.startswith("o1_with_nt"):
            return CODE_WITH_NT
        if code.startswith("without_nt") or code.startswith("o1_without_nt"):
            return CODE_WITHOUT_NT
        # Фоллбек: пытаемся использовать исходный код как есть.
        return code

    fd_model = FederalDistrictEnergyConsumptionParameter.__name__
    aggregates = dps.compute_federal_district_res_aggregates()
    if not aggregates:
        return

    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        if row.get("demand_model_name") != fd_model:
            i += 1
            continue
        if row.get("entity_kind") not in ("group", "perimeter_variant"):
            i += 1
            continue

        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        parent_id = row.get("parent_id")
        if parent_id is None:
            i += block_size
            continue

        pvc = row.get("perimeter_variant_code")
        agg_pvc = _fo_res_aggregate_variant_code(pvc)
        by_year = aggregates.get((int(parent_id), agg_pvc), {})
        # Обратная совместимость: в данных РЭС вариант периметра может быть не задан (None/""),
        # при этом на уровне ФО может быть включено разбиение по базовым вариантам НТ.
        # В этом случае агрегаты по РЭС лежат под ключом (fd_id, None), и без фоллбека
        # строки, например, «Южный ФО» (with_nt/without_nt) останутся пустыми.
        if not by_year and agg_pvc in (CODE_WITH_NT, CODE_WITHOUT_NT):
            by_year = aggregates.get((int(parent_id), None), {}) or aggregates.get(
                (int(parent_id), ""), {}
            )
        include_south_nt = (
            south_fd_id is not None
            and int(parent_id) == int(south_fd_id)
            and agg_pvc == CODE_WITH_NT
            and bool(nt_sum_by_key)
        )

        for parameter_key in _FO_FORMULA_BASE_PARAMETER_KEYS:
            target_row = next(
                (r for r in block if r.get("parameter_key") == parameter_key),
                None,
            )
            if target_row is None:
                continue
            raw_by_year: dict[int, Decimal | None] = {}
            value_index = 0 if parameter_key == "energy_consumption_mln_kvt_ch" else 1
            for year in years:
                pair = by_year.get(int(year))
                base_val = pair[value_index] if pair is not None else None
                if include_south_nt:
                    nt_val = (nt_sum_by_key.get(parameter_key) or {}).get(int(year))
                    if base_val is None and nt_val is None:
                        raw_by_year[int(year)] = None
                    else:
                        raw_by_year[int(year)] = (base_val or Decimal(0)) + (nt_val or Decimal(0))
                else:
                    raw_by_year[int(year)] = base_val
            _write_numeric_year_values_to_summary_row(
                target_row,
                years,
                raw_by_year,
                parameter_key=parameter_key,
                rounding_digits=rounding_digits,
            )
            target_row["pd_ec_formula_derived_row"] = True
            if parameter_key == "energy_consumption_mln_kvt_ch":
                target_row["pd_ec_summary_row_formula_tooltip"] = (
                    _SOUTH_FO_WITH_NT_FORMULA_TOOLTIP
                    if include_south_nt
                    else _FO_FORMULA_TOOLTIP
                )

        for block_row in block:
            block_row["pd_ec_formula_derived_row"] = True

        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_mln_kvt_ch",
            abs_parameter_key=None,
            yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        _recompute_growth_rows_from_base_series(
            block,
            years,
            base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
            abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        i += block_size


def _fo_without_gaes_variant_code_for_source(source_pvc: str | None) -> str:
    code = str(source_pvc or "").strip()
    if code == CODE_WITH_NT:
        return CODE_WITH_NT_WITHOUT_GAES
    if code == CODE_WITHOUT_NT:
        return CODE_WITHOUT_NT_WITHOUT_GAES
    if "without_gaes" in code:
        return code
    if code.startswith("with_nt"):
        return CODE_WITH_NT_WITHOUT_GAES
    if code.startswith("without_nt"):
        return CODE_WITHOUT_NT_WITHOUT_GAES
    return CODE_WITHOUT_NT_WITHOUT_GAES


def _is_federal_district_summary_consumption_block_start(row: dict[str, Any]) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if row.get("demand_model_name") != FederalDistrictEnergyConsumptionParameter.__name__:
        return False
    if row.get("entity_kind") not in ("group", "perimeter_variant"):
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("gaes_without_charge_formula_kind") == "fo":
        return False
    code = str(row.get("perimeter_variant_code") or "")
    return "without_gaes" not in code


def _is_federal_district_gaes_charge_row(row: dict[str, Any], parent_id: int) -> bool:
    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("demand_model_name") != FederalDistrictEnergyConsumptionParameter.__name__:
        return False
    return row.get("parent_id") == parent_id


def _build_federal_district_without_gaes_block_rows(
    source_block: list[dict[str, Any]],
    years: list[int],
    gaes_by_year: dict[int, Decimal | None],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    if not source_block:
        return []
    anchor = source_block[0]
    source_pvc = anchor.get("perimeter_variant_code")
    target_pvc = _fo_without_gaes_variant_code_for_source(source_pvc)
    base_label, kal_qual = _strip_summary_table_variant_suffixes_from_label(
        str(anchor.get("entity_label") or "")
    )
    if kal_qual:
        base_label = f"{base_label} ({kal_qual})"
    entity_label = _format_summary_table_variant_entity_label(base_label, target_pvc)
    compact_nt = _format_summary_table_entity_label_for_toggle_state(
        base_label,
        target_pvc,
        nt_detail_on=True,
        gaes_detail_on=False,
    )
    compact_gaes = _format_summary_table_entity_label_for_toggle_state(
        base_label,
        target_pvc,
        nt_detail_on=False,
        gaes_detail_on=True,
    )
    compact_both = _format_summary_table_entity_label_for_toggle_state(
        base_label,
        target_pvc,
        nt_detail_on=False,
        gaes_detail_on=False,
    )
    nt_group = _nt_group_for_variant_code(str(source_pvc or ""))
    out: list[dict[str, Any]] = []
    block_size = len(source_block)
    for index, source_row in enumerate(source_block):
        new_row = copy.copy(source_row)
        new_row["entity_label"] = entity_label
        new_row["entity_rowspan"] = block_size
        new_row["show_entity_cell"] = index == 0
        new_row["show_entity_note_cell"] = index == 0
        new_row["perimeter_variant_code"] = target_pvc
        new_row["perimeter_variant_label"] = ""
        new_row["perimeter_variant_options"] = []
        new_row["show_perimeter_variant_select"] = False
        new_row["pd_ec_gaes_extra_row"] = True
        new_row["pd_ec_gaes_without_row"] = True
        new_row["pd_ec_nt_extra_row"] = nt_group == "with_nt"
        new_row["pd_ec_nt_without_row"] = nt_group == "without_nt"
        new_row["pd_ec_entity_label_compact"] = compact_nt
        new_row["pd_ec_entity_label_compact_nt"] = compact_gaes
        new_row["pd_ec_entity_label_compact_nt_gaes"] = compact_both
        new_row["pd_ec_formula_derived_row"] = True
        new_row["gaes_without_charge_formula_kind"] = "fo"
        new_row["pd_ec_fo_without_gaes_injected_row"] = True
        new_row.pop("pd_ec_summary_row_formula_tooltip", None)
        out.append(new_row)

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        target_row = next(
            (row for row in out if row.get("parameter_key") == parameter_key),
            None,
        )
        source_row = next(
            (row for row in source_block if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None or source_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    return out


def inject_federal_district_without_gaes_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Строки «ФО … без заряда ГАЭС»: расчёт = потребление ФО − заряд ГАЭС; видимость как у заряда ГАЭС."""
    if not summary_rows or not years:
        return

    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_federal_district_summary_consumption_block_start(row):
            i += 1
            continue

        parent_id = row.get("parent_id")
        if parent_id is None:
            i += 1
            continue

        fo_blocks: list[list[dict[str, Any]]] = []
        j = i
        while j < n:
            current = summary_rows[j]
            if _is_federal_district_summary_consumption_block_start(current) and current.get("parent_id") == parent_id:
                block_size = int(current.get("entity_rowspan") or 1)
                if block_size < 1:
                    block_size = 1
                fo_blocks.append(summary_rows[j : j + block_size])
                j += block_size
                continue
            if _is_federal_district_gaes_charge_row(current, int(parent_id)):
                j += 1
                continue
            break

        if not _summary_row_entity_has_gaes_charge(fo_blocks[0][0]):
            i = j
            continue

        entity_key = _gaes_charge_entity_key(fo_blocks[0][0])
        gaes_by_year = gaes_totals.get(entity_key, {})
        injected: list[dict[str, Any]] = []
        for block in fo_blocks:
            if any(item.get("pd_ec_fo_without_gaes_injected_row") for item in block):
                continue
            injected.extend(
                _build_federal_district_without_gaes_block_rows(
                    block,
                    years,
                    gaes_by_year,
                    rounding_digits,
                )
            )
        if injected:
            summary_rows[j:j] = injected
            n = len(summary_rows)
            i = j + len(injected)
        else:
            i = j


_FO_RES_SUM_VERIFICATION_TOOLTIP = (
    "Проверка для ФО = потребление ЭЭ по ФО − "
    "сумма потребления ЭЭ по всем РЭС данного ФО "
    "(строки О-1 не учитываются)"
)


def _is_federal_district_summary_same_depth_sibling(
    row: dict[str, Any],
    *,
    fd_model: str,
    fd_id: Any,
) -> bool:
    return (
        row.get("demand_model_name") == fd_model
        and row.get("parent_fk_column") == "id_federal_district"
        and row.get("parent_id") == fd_id
    )


def _federal_district_subtree_end_index(
    summary_rows: list[dict[str, Any]],
    start_index: int,
    *,
    fd_model: str,
) -> int:
    """Последняя строка поддерева ФО (все варианты периметра и дочерние РЭС включительно)."""
    start = summary_rows[start_index]
    base_depth = int(start.get("entity_depth") or 0)
    fd_id = start.get("parent_id")
    end = start_index + max(int(start.get("entity_rowspan") or 1), 1) - 1
    i = end + 1
    while i < len(summary_rows):
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= base_depth:
                if _is_federal_district_summary_same_depth_sibling(
                    row,
                    fd_model=fd_model,
                    fd_id=fd_id,
                ):
                    pass
                else:
                    break
            block_size = max(int(row.get("entity_rowspan") or 1), 1)
            end = i + block_size - 1
            i += block_size
        else:
            end = i
            i += 1
    return end


def _iter_federal_district_subtree_spans(
    summary_rows: list[dict[str, Any]],
) -> list[tuple[int, int, Any]]:
    """Интервалы [start, end] по каждому ФО (все варианты периметра и дочерние РЭС)."""
    fd_model = FederalDistrictEnergyConsumptionParameter.__name__
    spans: list[tuple[int, int, Any]] = []
    seen_fd_ids: set[Any] = set()
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_federal_district_summary_consumption_block_start(row):
            i += 1
            continue
        fd_id = row.get("parent_id")
        if fd_id in seen_fd_ids:
            i += max(int(row.get("entity_rowspan") or 1), 1)
            continue
        seen_fd_ids.add(fd_id)
        end = _federal_district_subtree_end_index(summary_rows, i, fd_model=fd_model)
        spans.append((i, end, fd_id))
        i = end + 1
    return spans


def _summary_row_skip_fo_res_verification_sum(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != RegionalEnergySystemEnergyConsumptionParameter.__name__:
        return True
    if _summary_row_skip_oes_gaes_charge_verification(row):
        return True
    if row.get("pd_ec_fo_without_gaes_injected_row"):
        return True
    if row.get("pd_ec_res_without_gaes_injected_row"):
        return True
    code = str(row.get("perimeter_variant_code") or "")
    if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(code):
        return True
    return False


def _sum_fo_subtree_res_parameter_by_year(
    rows: list[dict[str, Any]],
    *,
    start_index: int,
    end_index: int,
    years: list[int],
    parameter_key: str,
    perimeter_variant_code: str | None,
) -> dict[int, Decimal | None]:
    sums: dict[int, Decimal] = {}
    seen: set[int] = set()
    for index in range(start_index, end_index + 1):
        row = rows[index]
        if _summary_row_skip_fo_res_verification_sum(row):
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if row.get("perimeter_variant_code") != perimeter_variant_code:
            continue
        values = _raw_year_values_from_summary_row(row, years)
        for year, value in values.items():
            if value is None:
                continue
            sums[year] = sums.get(year, Decimal(0)) + value
            seen.add(year)
    return {int(year): sums.get(int(year)) if int(year) in seen else None for year in years}


def _sum_fo_subtree_res_without_gaes_parameter_by_year(
    rows: list[dict[str, Any]],
    *,
    start_index: int,
    end_index: int,
    years: list[int],
    parameter_key: str,
    perimeter_variant_code: str | None,
) -> dict[int, Decimal | None]:
    """Сумма по РЭС внутри ФО для injected-строк «без заряда ГАЭС»."""
    sums: dict[int, Decimal] = {}
    seen: set[int] = set()
    for index in range(start_index, end_index + 1):
        row = rows[index]
        if row.get("demand_model_name") != RegionalEnergySystemEnergyConsumptionParameter.__name__:
            continue
        if not row.get("pd_ec_res_without_gaes_injected_row"):
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        # Для injected РЭС «без ГАЭС» perimeter_variant_code может быть None; кроме того,
        # варианты периметра тут не должны влиять на сумму: проверяем именно сумму блоков «без ГАЭС».
        # perimeter_variant_code намеренно игнорируется
        code = str(row.get("perimeter_variant_code") or "")
        if row.get("pd_ec_o1_form_row") or is_o1_perimeter_variant_code(code):
            continue
        values = _raw_year_values_from_summary_row(row, years)
        for year, value in values.items():
            if value is None:
                continue
            sums[int(year)] = sums.get(int(year), Decimal(0)) + value
            seen.add(int(year))
    return {int(year): sums.get(int(year)) if int(year) in seen else None for year in years}


def inject_fo_summary_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    fo_res_sum_source_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Строки «Проверка для …» на сводке ФО (скрыты до кнопки «Проверка»)."""
    if not summary_rows or not source_rows or not years:
        return
    res_sum_rows = (
        fo_res_sum_source_rows if fo_res_sum_source_rows is not None else source_rows
    )
    if any(str(row.get("entity_kind") or "") == "fo_res_sum_check" for row in summary_rows):
        return

    fd_model = FederalDistrictEnergyConsumptionParameter.__name__
    res_model = RegionalEnergySystemEnergyConsumptionParameter.__name__
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    insertions_after: dict[int, list[dict[str, Any]]] = {}
    fo_without_gaes_tooltip = (
        "Проверка для ФО без ГАЭС = потребление ЭЭ по ФО без заряда ГАЭС − сумма потребления ЭЭ по всем РЭС данного ФО без заряда ГАЭС "
        "(строки О-1 не учитываются)"
    )

    def _sum_year_dicts(
        a: dict[int, Decimal | None],
        b: dict[int, Decimal | None],
        *,
        years: list[int],
    ) -> dict[int, Decimal | None]:
        out: dict[int, Decimal | None] = {}
        for y in years:
            ay = a.get(int(y))
            by = b.get(int(y))
            if ay is None and by is None:
                out[int(y)] = None
                continue
            out[int(y)] = (ay or Decimal(0)) + (by or Decimal(0))
        return out

    def _find_fd_row_values_by_label_cf(
        *,
        fd_label_cf: str,
        parameter_key: str,
        perimeter_variant_code: str | None,
    ) -> dict[int, Decimal | None]:
        """Значения строки ФО по названию (cf) и ключу параметра."""
        for r in summary_rows:
            if r.get("demand_model_name") != fd_model:
                continue
            if r.get("parameter_key") != parameter_key:
                continue
            if str(r.get("perimeter_variant_code") or "") != str(perimeter_variant_code or ""):
                continue
            if _summary_row_base_label_cf(r) != fd_label_cf:
                continue
            return _raw_year_values_from_summary_row(r, years)
        return {int(y): None for y in years}

    def _inject_south_ues_verification_after_north_caucasus_fd() -> None:
        """После «Проверка для Северо-Кавказский ФО» — проверка соответствия ОЭС Юга сумме ФО."""
        target_after_label = "Проверка для Северо-Кавказский ФО"
        insert_at: int | None = None
        for ix, r in enumerate(pending):
            if not r.get("show_entity_cell"):
                continue
            if str(r.get("entity_label") or "").strip() != target_after_label:
                continue
            block_size = max(int(r.get("entity_rowspan") or 1), 1)
            insert_at = ix + block_size
            break
        if insert_at is None:
            return

        south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
        if south_ues_id is None:
            return

        ec_key_local = "energy_consumption_mln_kvt_ch"
        sipr_key_local = "energy_consumption_sipr_mln_kvt_ch"

        south_ues_ec = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(south_ues_id),
            years,
            ec_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        south_ues_sipr = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(south_ues_id),
            years,
            sipr_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        if not _year_values_have_any_numeric(south_ues_ec) and not _year_values_have_any_numeric(
            south_ues_sipr
        ):
            return

        # Южный ФО на странице ФО должен браться именно «без НТ», а Северо-Кавказский ФО — как есть.
        south_fd_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=SOUTH_FD_NAME_CF,
            parameter_key=ec_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )
        south_fd_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=SOUTH_FD_NAME_CF,
            parameter_key=sipr_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )
        if not _year_values_have_any_numeric(south_fd_ec) and not _year_values_have_any_numeric(
            south_fd_sipr
        ):
            south_fd_ec = _find_fd_row_values_by_label_cf(
                fd_label_cf=SOUTH_FD_NAME_CF,
                parameter_key=ec_key_local,
                perimeter_variant_code=None,
            )
            south_fd_sipr = _find_fd_row_values_by_label_cf(
                fd_label_cf=SOUTH_FD_NAME_CF,
                parameter_key=sipr_key_local,
                perimeter_variant_code=None,
            )

        north_cauc_fd_label = "Северо-Кавказский ФО"
        north_cauc_fd_label_cf = north_cauc_fd_label.casefold()
        north_cauc_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=north_cauc_fd_label_cf,
            parameter_key=ec_key_local,
            perimeter_variant_code=None,
        )
        north_cauc_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=north_cauc_fd_label_cf,
            parameter_key=sipr_key_local,
            perimeter_variant_code=None,
        )
        if not _year_values_have_any_numeric(north_cauc_ec) and not _year_values_have_any_numeric(
            north_cauc_sipr
        ):
            north_cauc_ec = _find_fd_row_values_by_label_cf(
                fd_label_cf=north_cauc_fd_label_cf,
                parameter_key=ec_key_local,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
            north_cauc_sipr = _find_fd_row_values_by_label_cf(
                fd_label_cf=north_cauc_fd_label_cf,
                parameter_key=sipr_key_local,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
        # На сводке ОЭС “ОЭС Юга без НТ с ГАЭС” в проверках до некоторого года
        # сопоставляется без ЭС Республики Крым и г. Севастополя. Чтобы проверка на сводке ФО
        # не расходилась, синхронно исключаем Крым/Севастополь из суммы по Южному ФО
        # (до того же года), если строки РЭС доступны в исходных данных.
        try:
            crimea_ec = _sum_south_crimea_sev_res_parameter_by_year(
                res_sum_rows,
                years=years,
                parameter_key=ec_key_local,
                ues_id_int=int(south_ues_id),
            )
            crimea_sipr = _sum_south_crimea_sev_res_parameter_by_year(
                res_sum_rows,
                years=years,
                parameter_key=sipr_key_local,
                ues_id_int=int(south_ues_id),
            )
            south_fd_ec = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                south_fd_ec, crimea_ec, years=years
            )
            south_fd_sipr = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                south_fd_sipr, crimea_sipr, years=years
            )
        except Exception:
            # best-effort: не ломаем страницу при проблемах в справочниках/данных
            pass

        sum_fo_ec = _sum_year_dicts(south_fd_ec, north_cauc_ec, years=years)
        sum_fo_sipr = _sum_year_dicts(south_fd_sipr, north_cauc_sipr, years=years)

        tooltip = (
            "Проверка для ОЭС Юга = "
            "ОЭС Юга без НТ с ГАЭС − "
            "Южный ФО без НТ − "
            "Северо-Кавказский ФО"
        )
        depth = 0
        for r in pending:
            if r.get("show_entity_cell") and str(r.get("entity_label") or "").strip() == target_after_label:
                depth = int(r.get("entity_depth") or 0)
                break

        injected = _build_ec_summary_verification_rows(
            entity_label="Проверка для ОЭС Юга",
            entity_kind="fo_south_ues_verification",
            entity_depth=depth,
            years=years,
            rounding_digits=rounding_digits,
            base_ec=south_ues_ec,
            sum_ec=sum_fo_ec,
            base_sipr=south_ues_sipr,
            sum_sipr=sum_fo_sipr,
            formula_tooltip=tooltip,
            year_bounds_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        if injected:
            pending[insert_at:insert_at] = injected

    def _build_fd_verification_at(
        start_index: int,
        *,
        subtree_start: int,
        subtree_end: int,
    ) -> list[dict[str, Any]] | None:
        row = summary_rows[start_index]
        fd_id = row.get("parent_id")
        if fd_id is None:
            return None
        try:
            fd_id_int = int(fd_id)
        except (TypeError, ValueError):
            return None
        perimeter_variant_code = row.get("perimeter_variant_code")
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=fd_model,
            parent_fk_column="id_federal_district",
            parent_id=fd_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=fd_model,
            parent_fk_column="id_federal_district",
            parent_id=fd_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        if base_ec_row is None or base_sipr_row is None:
            return None
        child_ec = _sum_fo_subtree_res_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=ec_key,
            perimeter_variant_code=perimeter_variant_code,
        )
        child_sipr = _sum_fo_subtree_res_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=sipr_key,
            perimeter_variant_code=perimeter_variant_code,
        )
        return _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''}".strip(),
            entity_kind="fo_res_sum_check",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=_FO_RES_SUM_VERIFICATION_TOOLTIP,
            year_bounds_variant_code=str(perimeter_variant_code or "") or None,
        )

    def _build_fd_without_gaes_verification_at(
        start_index: int,
        *,
        subtree_start: int,
        subtree_end: int,
    ) -> list[dict[str, Any]] | None:
        row = summary_rows[start_index]
        fd_id = row.get("parent_id")
        if fd_id is None:
            return None
        try:
            fd_id_int = int(fd_id)
        except (TypeError, ValueError):
            return None

        source_pvc = row.get("perimeter_variant_code")
        target_pvc = _fo_without_gaes_variant_code_for_source(source_pvc)

        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=fd_model,
            parent_fk_column="id_federal_district",
            parent_id=fd_id_int,
            perimeter_variant_code=target_pvc,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=fd_model,
            parent_fk_column="id_federal_district",
            parent_id=fd_id_int,
            perimeter_variant_code=target_pvc,
        )
        if base_ec_row is None or base_sipr_row is None:
            return None
        if not base_ec_row.get("pd_ec_fo_without_gaes_injected_row"):
            return None

        child_ec = _sum_fo_subtree_res_without_gaes_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=ec_key,
            perimeter_variant_code=target_pvc,
        )
        child_sipr = _sum_fo_subtree_res_without_gaes_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=sipr_key,
            perimeter_variant_code=target_pvc,
        )

        out = _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''} без ГАЭС".strip(),
            entity_kind="fo_res_sum_check_without_gaes",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=fo_without_gaes_tooltip,
            year_bounds_variant_code=str(target_pvc or "") or None,
        )
        for r in out:
            r["pd_ec_gaes_without_row"] = True
        return out

    # Требование страницы /summary/federal_districts/: показываем только проверки соответствия
    # «ОЭС Юга» сумме ФО (Южный ФО + Северо-Кавказский ФО) и «ОЭС Урала»
    # (Уральский ФО + Приволжский ФО − ОЭС Урала − ОЭС Средней Волги). Все прочие строки
    # «Проверка …» по ФО здесь не добавляем.
    def _inject_ural_ues_verification() -> None:
        """После «Уральский ФО» — сверка ФО с ОЭС Урала и ОЭС Средней Волги."""
        ural_fd_label = "Уральский ФО"
        ural_fd_label_cf = ural_fd_label.casefold()
        privolzh_fd_label = "Приволжский ФО"
        privolzh_fd_label_cf = privolzh_fd_label.casefold()

        ural_ues_id = _resolve_union_energy_system_id_by_name_cf(URAL_UES_NAME_CF)
        mid_volga_ues_id = _resolve_union_energy_system_id_by_name_cf(MIDDLE_VOLGA_UES_NAME_CF)
        if ural_ues_id is None or mid_volga_ues_id is None:
            return

        ec_key_local = "energy_consumption_mln_kvt_ch"
        sipr_key_local = "energy_consumption_sipr_mln_kvt_ch"
        base_pvc = None

        ural_ues_ec = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(ural_ues_id),
            years,
            ec_key_local,
            perimeter_variant_code=base_pvc,
        )
        mid_volga_ues_ec = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(mid_volga_ues_id),
            years,
            ec_key_local,
            perimeter_variant_code=base_pvc,
        )
        ural_ues_sipr = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(ural_ues_id),
            years,
            sipr_key_local,
            perimeter_variant_code=base_pvc,
        )
        mid_volga_ues_sipr = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(mid_volga_ues_id),
            years,
            sipr_key_local,
            perimeter_variant_code=base_pvc,
        )
        if not _year_values_have_any_numeric(ural_ues_ec) and not _year_values_have_any_numeric(
            mid_volga_ues_ec
        ) and not _year_values_have_any_numeric(ural_ues_sipr) and not _year_values_have_any_numeric(
            mid_volga_ues_sipr
        ):
            return

        ural_fd_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=ural_fd_label_cf,
            parameter_key=ec_key_local,
            perimeter_variant_code=base_pvc,
        )
        ural_fd_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=ural_fd_label_cf,
            parameter_key=sipr_key_local,
            perimeter_variant_code=base_pvc,
        )
        privolzh_fd_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=privolzh_fd_label_cf,
            parameter_key=ec_key_local,
            perimeter_variant_code=base_pvc,
        )
        privolzh_fd_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=privolzh_fd_label_cf,
            parameter_key=sipr_key_local,
            perimeter_variant_code=base_pvc,
        )
        if not _year_values_have_any_numeric(ural_fd_ec) and not _year_values_have_any_numeric(
            ural_fd_sipr
        ) and not _year_values_have_any_numeric(privolzh_fd_ec) and not _year_values_have_any_numeric(
            privolzh_fd_sipr
        ):
            return

        sum_fo_ec = _sum_year_dicts(ural_fd_ec, privolzh_fd_ec, years=years)
        sum_fo_sipr = _sum_year_dicts(ural_fd_sipr, privolzh_fd_sipr, years=years)
        sum_ues_ec = _sum_year_dicts(ural_ues_ec, mid_volga_ues_ec, years=years)
        sum_ues_sipr = _sum_year_dicts(ural_ues_sipr, mid_volga_ues_sipr, years=years)

        tooltip = (
            "Проверка для ОЭС Урала = "
            "Уральский ФО + Приволжский ФО − ОЭС Урала − ОЭС Средней Волги"
        )

        injected = _build_ec_summary_verification_rows(
            entity_label="Проверка для ОЭС Урала",
            entity_kind="fo_ural_ues_verification",
            entity_depth=0,
            years=years,
            rounding_digits=rounding_digits,
            base_ec=sum_fo_ec,
            sum_ec=sum_ues_ec,
            base_sipr=sum_fo_sipr,
            sum_sipr=sum_ues_sipr,
            formula_tooltip=tooltip,
            year_bounds_variant_code=base_pvc,
        )
        if not injected:
            return

        fd_model = FederalDistrictEnergyConsumptionParameter.__name__
        insert_at = len(summary_rows)
        for ix, r in enumerate(summary_rows):
            if not r.get("show_entity_cell"):
                continue
            if _territory_gaes_entity_base_label(r).strip() != ural_fd_label:
                continue
            if not _is_federal_district_summary_consumption_block_start(r):
                block_size = max(int(r.get("entity_rowspan") or 1), 1)
                insert_at = ix + block_size
                break
            end_ix = _federal_district_subtree_end_index(summary_rows, ix, fd_model=fd_model)
            insert_at = end_ix + 1
            break
        summary_rows[insert_at:insert_at] = injected

    def _inject_only_south_ues_verification() -> None:
        south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
        if south_ues_id is None:
            return

        ec_key_local = "energy_consumption_mln_kvt_ch"
        sipr_key_local = "energy_consumption_sipr_mln_kvt_ch"

        south_ues_ec = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(south_ues_id),
            years,
            ec_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        south_ues_sipr = _year_values_from_parent_demand_rows(
            UnionEnergySystemEnergyConsumptionParameter,
            "id_union_energy_system",
            int(south_ues_id),
            years,
            sipr_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        if not _year_values_have_any_numeric(south_ues_ec) and not _year_values_have_any_numeric(
            south_ues_sipr
        ):
            return

        south_fd_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=SOUTH_FD_NAME_CF,
            parameter_key=ec_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )
        south_fd_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=SOUTH_FD_NAME_CF,
            parameter_key=sipr_key_local,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )
        if not _year_values_have_any_numeric(south_fd_ec) and not _year_values_have_any_numeric(
            south_fd_sipr
        ):
            south_fd_ec = _find_fd_row_values_by_label_cf(
                fd_label_cf=SOUTH_FD_NAME_CF,
                parameter_key=ec_key_local,
                perimeter_variant_code=None,
            )
            south_fd_sipr = _find_fd_row_values_by_label_cf(
                fd_label_cf=SOUTH_FD_NAME_CF,
                parameter_key=sipr_key_local,
                perimeter_variant_code=None,
            )

        north_cauc_fd_label = "Северо-Кавказский ФО"
        north_cauc_fd_label_cf = north_cauc_fd_label.casefold()
        north_cauc_ec = _find_fd_row_values_by_label_cf(
            fd_label_cf=north_cauc_fd_label_cf,
            parameter_key=ec_key_local,
            perimeter_variant_code=None,
        )
        north_cauc_sipr = _find_fd_row_values_by_label_cf(
            fd_label_cf=north_cauc_fd_label_cf,
            parameter_key=sipr_key_local,
            perimeter_variant_code=None,
        )
        if not _year_values_have_any_numeric(north_cauc_ec) and not _year_values_have_any_numeric(
            north_cauc_sipr
        ):
            north_cauc_ec = _find_fd_row_values_by_label_cf(
                fd_label_cf=north_cauc_fd_label_cf,
                parameter_key=ec_key_local,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
            north_cauc_sipr = _find_fd_row_values_by_label_cf(
                fd_label_cf=north_cauc_fd_label_cf,
                parameter_key=sipr_key_local,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )

        # Синхронизация с правилом проверки на сводке ОЭС:
        # исключаем Крым/Севастополь из Южного ФО в ранние годы, если они присутствуют в РЭС-строках.
        try:
            crimea_ec = _sum_south_crimea_sev_res_parameter_by_year(
                res_sum_rows,
                years=years,
                parameter_key=ec_key_local,
                ues_id_int=int(south_ues_id),
            )
            crimea_sipr = _sum_south_crimea_sev_res_parameter_by_year(
                res_sum_rows,
                years=years,
                parameter_key=sipr_key_local,
                ues_id_int=int(south_ues_id),
            )
            south_fd_ec = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                south_fd_ec, crimea_ec, years=years
            )
            south_fd_sipr = _exclude_south_crimea_sev_res_from_verification_sum_by_year(
                south_fd_sipr, crimea_sipr, years=years
            )
        except Exception:
            pass

        sum_fo_ec = _sum_year_dicts(south_fd_ec, north_cauc_ec, years=years)
        sum_fo_sipr = _sum_year_dicts(south_fd_sipr, north_cauc_sipr, years=years)

        tooltip = (
            "Проверка для ОЭС Юга = "
            "ОЭС Юга без НТ с ГАЭС − "
            "Южный ФО без НТ − "
            "Северо-Кавказский ФО"
        )

        injected = _build_ec_summary_verification_rows(
            entity_label="Проверка для ОЭС Юга",
            entity_kind="fo_south_ues_verification",
            entity_depth=0,
            years=years,
            rounding_digits=rounding_digits,
            base_ec=south_ues_ec,
            sum_ec=sum_fo_ec,
            base_sipr=south_ues_sipr,
            sum_sipr=sum_fo_sipr,
            formula_tooltip=tooltip,
            year_bounds_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        if not injected:
            return

        # Вставляем после всего поддерева «Северо-Кавказский ФО» (включая все РЭС),
        # иначе — перед «Приволжский ФО», иначе — в конец таблицы.
        insert_at = len(summary_rows)
        privolzh_fd_label = "Приволжский ФО"
        privolzh_ix: int | None = None
        for ix, r in enumerate(summary_rows):
            if not r.get("show_entity_cell"):
                continue
            base_entity = _territory_gaes_entity_base_label(r).strip()
            if base_entity == privolzh_fd_label and privolzh_ix is None:
                privolzh_ix = ix
            if base_entity != north_cauc_fd_label:
                continue
            if _is_federal_district_summary_consumption_block_start(r):
                end_ix = _federal_district_subtree_end_index(
                    summary_rows, ix, fd_model=fd_model
                )
                insert_at = end_ix + 1
            else:
                block_size = max(int(r.get("entity_rowspan") or 1), 1)
                insert_at = ix + block_size
            break
        if insert_at == len(summary_rows) and privolzh_ix is not None:
            insert_at = privolzh_ix
        summary_rows[insert_at:insert_at] = injected

    _inject_only_south_ues_verification()
    _inject_ural_ues_verification()
    return

    for subtree_start, subtree_end, _fd_id in _iter_federal_district_subtree_spans(
        summary_rows
    ):
        pending: list[dict[str, Any]] = []
        fd_block_starts: list[int] = []
        index = subtree_start
        while index <= subtree_end:
            row = summary_rows[index]
            if row.get("show_entity_cell"):
                block_size = max(int(row.get("entity_rowspan") or 1), 1)
                if _is_federal_district_summary_consumption_block_start(row):
                    fd_block_starts.append(index)
                index += block_size
            else:
                index += 1
        for fd_index in fd_block_starts:
            fd_rows = _build_fd_verification_at(
                fd_index,
                subtree_start=subtree_start,
                subtree_end=subtree_end,
            )
            if fd_rows:
                anchor = summary_rows[fd_index]
                # Для проверок ФО выводим заголовок без суффиксов «… ГАЭС» после названия.
                base_entity = _territory_gaes_entity_base_label(anchor).strip()
                plain_label = f"Проверка для {base_entity}".strip()
                # Для Южного ФО в UI различаем «с/без НТ» в конце названия.
                # По умолчанию (без НТ) показываем подпись без суффикса, а при включении НТ
                # JS подменяет на data-pd-ec-entity-label-compact-nt.
                south_fo = base_entity == "Южный ФО"
                label_without_nt = (
                    f"Проверка для {base_entity} без НТ".strip() if south_fo else plain_label
                )
                label_with_nt = (
                    f"Проверка для {base_entity} с НТ".strip() if south_fo else plain_label
                )
                for r in fd_rows:
                    r["entity_label"] = label_without_nt
                    if r.get("show_entity_cell"):
                        r["pd_ec_entity_label_compact"] = label_without_nt
                        r["pd_ec_entity_label_compact_nt"] = label_with_nt
                        r["pd_ec_entity_label_compact_nt_gaes"] = label_with_nt
                pending.extend(fd_rows)
        if pending:
            _inject_south_ues_verification_after_north_caucasus_fd()
        if pending:
            insertions_after[subtree_end] = pending

    _insert_summary_rows_after_indices(summary_rows, insertions_after)


_EZ_RES_SUM_VERIFICATION_TOOLTIP = (
    "Проверка для энергозоны = потребление ЭЭ по энергозоне − "
    "сумма потребления ЭЭ по всем РЭС данной энергозоны "
    "(строки О-1 не учитываются)"
)


def _is_energy_zone_summary_consumption_block_start(row: dict[str, Any]) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if row.get("demand_model_name") != EnergyZoneEnergyConsumptionParameter.__name__:
        return False
    if row.get("entity_kind") not in ("group", "perimeter_variant"):
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("gaes_without_charge_formula_kind") == "ez":
        return False
    code = str(row.get("perimeter_variant_code") or "")
    return "without_gaes" not in code


def _is_energy_zone_summary_same_depth_sibling(
    row: dict[str, Any],
    *,
    ez_model: str,
    ez_id: Any,
) -> bool:
    return (
        row.get("demand_model_name") == ez_model
        and row.get("parent_fk_column") == "id_energy_zone"
        and row.get("parent_id") == ez_id
    )


def _energy_zone_subtree_end_index(
    summary_rows: list[dict[str, Any]],
    start_index: int,
    *,
    ez_model: str,
) -> int:
    """Последняя строка поддерева энергозоны (все варианты периметра и дочерние РЭС)."""
    start = summary_rows[start_index]
    base_depth = int(start.get("entity_depth") or 0)
    ez_id = start.get("parent_id")
    end = start_index + max(int(start.get("entity_rowspan") or 1), 1) - 1
    i = end + 1
    while i < len(summary_rows):
        row = summary_rows[i]
        if row.get("show_entity_cell"):
            row_depth = int(row.get("entity_depth") or 0)
            if row_depth <= base_depth:
                if _is_energy_zone_summary_same_depth_sibling(
                    row,
                    ez_model=ez_model,
                    ez_id=ez_id,
                ):
                    pass
                else:
                    break
            block_size = max(int(row.get("entity_rowspan") or 1), 1)
            end = i + block_size - 1
            i += block_size
        else:
            end = i
            i += 1
    return end


def _iter_energy_zone_subtree_spans(
    summary_rows: list[dict[str, Any]],
) -> list[tuple[int, int, Any]]:
    """Интервалы [start, end] по каждой энергозоне (все варианты периметра и дочерние РЭС)."""
    ez_model = EnergyZoneEnergyConsumptionParameter.__name__
    spans: list[tuple[int, int, Any]] = []
    seen_ez_ids: set[Any] = set()
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_energy_zone_summary_consumption_block_start(row):
            i += 1
            continue
        ez_id = row.get("parent_id")
        if ez_id in seen_ez_ids:
            i += max(int(row.get("entity_rowspan") or 1), 1)
            continue
        seen_ez_ids.add(ez_id)
        end = _energy_zone_subtree_end_index(summary_rows, i, ez_model=ez_model)
        spans.append((i, end, ez_id))
        i = end + 1
    return spans


def inject_ez_summary_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    ez_res_sum_source_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Строки «Проверка для …» на сводке энергозон (скрыты до кнопки «Проверка»)."""
    if not summary_rows or not source_rows or not years:
        return
    res_sum_rows = (
        ez_res_sum_source_rows if ez_res_sum_source_rows is not None else source_rows
    )
    if any(str(row.get("entity_kind") or "") == "ez_res_sum_check" for row in summary_rows):
        return

    ez_model = EnergyZoneEnergyConsumptionParameter.__name__
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    insertions_after: dict[int, list[dict[str, Any]]] = {}

    def _build_ez_verification_at(
        start_index: int,
        *,
        subtree_start: int,
        subtree_end: int,
    ) -> list[dict[str, Any]] | None:
        row = summary_rows[start_index]
        ez_id = row.get("parent_id")
        if ez_id is None:
            return None
        try:
            ez_id_int = int(ez_id)
        except (TypeError, ValueError):
            return None
        perimeter_variant_code = row.get("perimeter_variant_code")
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=ez_model,
            parent_fk_column="id_energy_zone",
            parent_id=ez_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=ez_model,
            parent_fk_column="id_energy_zone",
            parent_id=ez_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        if base_ec_row is None or base_sipr_row is None:
            return None
        child_ec = _sum_fo_subtree_res_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=ec_key,
            perimeter_variant_code=perimeter_variant_code,
        )
        child_sipr = _sum_fo_subtree_res_parameter_by_year(
            res_sum_rows,
            start_index=subtree_start,
            end_index=subtree_end,
            years=years,
            parameter_key=sipr_key,
            perimeter_variant_code=perimeter_variant_code,
        )
        return _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {row.get('entity_label') or ''}".strip(),
            entity_kind="ez_res_sum_check",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=_EZ_RES_SUM_VERIFICATION_TOOLTIP,
            year_bounds_variant_code=str(perimeter_variant_code or "") or None,
        )

    for subtree_start, subtree_end, _ez_id in _iter_energy_zone_subtree_spans(summary_rows):
        pending: list[dict[str, Any]] = []
        ez_block_starts: list[int] = []
        index = subtree_start
        while index <= subtree_end:
            row = summary_rows[index]
            if row.get("show_entity_cell"):
                block_size = max(int(row.get("entity_rowspan") or 1), 1)
                if _is_energy_zone_summary_consumption_block_start(row):
                    ez_block_starts.append(index)
                index += block_size
            else:
                index += 1
        for ez_index in ez_block_starts:
            ez_rows = _build_ez_verification_at(
                ez_index,
                subtree_start=subtree_start,
                subtree_end=subtree_end,
            )
            if ez_rows:
                anchor = summary_rows[ez_index]
                base_entity = _territory_gaes_entity_base_label(anchor).strip()
                plain_label = f"Проверка для {base_entity}".strip()
                for r in ez_rows:
                    r["entity_label"] = plain_label
                    if r.get("show_entity_cell"):
                        r["pd_ec_entity_label_compact"] = plain_label
                pending.extend(ez_rows)
        if pending:
            insertions_after[subtree_end] = pending

    _insert_summary_rows_after_indices(summary_rows, insertions_after)


def _find_summary_row_in_res_subtree(
    summary_rows: list[dict[str, Any]],
    res_start_index: int,
    *,
    entity_label: str,
    parameter_key: str,
) -> dict[str, Any] | None:
    subtree_end = _res_subtree_end_index(summary_rows, res_start_index)
    target = entity_label.strip()
    for index in range(res_start_index, subtree_end + 1):
        row = summary_rows[index]
        if row.get("parameter_key") != parameter_key:
            continue
        if str(row.get("entity_label") or "").strip() == target:
            return row
    return None


def _sum_east_ez_o1_res_verification_children_by_year(
    summary_rows: list[dict[str, Any]],
    *,
    res_start_index: int,
    res_label: str,
    years: list[int],
    parameter_key: str,
    demand_model_name: str,
) -> dict[int, Decimal | None]:
    """Сумма энергорайонов (О-1) для проверки РЭС; для Чукотки — без «Чаун-Билибинский», со справочной строкой."""
    eu_block_starts = _res_subtree_o1_energy_unit_block_start_indices(
        summary_rows,
        res_start_index,
    )
    if str(res_label).strip() == _CHUKOTKA_RES_LABEL:
        eu_block_starts = [
            index
            for index in eu_block_starts
            if str(summary_rows[index].get("entity_label") or "").strip()
            != _CHAUN_BILIBINO_EU_LABEL
        ]
    child_sum = _sum_summary_entity_blocks_parameter_by_year(
        summary_rows,
        eu_block_starts,
        years=years,
        parameter_key=parameter_key,
        demand_model_name=demand_model_name,
    )
    if str(res_label).strip() != _CHUKOTKA_RES_LABEL:
        return child_sum
    reference_row = _find_summary_row_in_res_subtree(
        summary_rows,
        res_start_index,
        entity_label=_CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL,
        parameter_key=parameter_key,
    )
    if reference_row is None:
        return child_sum
    reference_values = _raw_year_values_from_summary_row(reference_row, years)
    return _sum_year_value_dicts(years, child_sum, reference_values)


def inject_east_energy_zone_o1_parent_verification_row(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """«Проверка для Энергозона Востока» в конце блока О-1 (режимы «Форма О-1» и «Проверка»)."""
    if not summary_rows or not source_rows or not years:
        return
    if any(
        str(row.get("entity_kind") or "") == "east_ez_o1_parent_sum_check"
        for row in summary_rows
    ):
        return
    block = _east_energy_zone_summary_block_slice(summary_rows)
    if block is None:
        return

    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    base_ec_row = next(
        (
            row
            for row in summary_rows
            if row.get("parameter_key") == ec_key
            and str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL
        ),
        None,
    )
    base_sipr_row = next(
        (
            row
            for row in summary_rows
            if row.get("parameter_key") == sipr_key
            and str(row.get("entity_label") or "").strip() == _EAST_ENERGY_ZONE_LABEL
        ),
        None,
    )
    if base_ec_row is None or base_sipr_row is None:
        return

    sum_ec = _sum_east_energy_zone_formula_from_summary_rows(
        source_rows,
        years,
        ec_key,
    )
    sum_sipr = _sum_east_energy_zone_formula_from_summary_rows(
        source_rows,
        years,
        sipr_key,
    )
    verify_rows = _build_ec_summary_verification_rows(
        entity_label=_EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_LABEL,
        entity_kind="east_ez_o1_parent_sum_check",
        entity_depth=int(base_ec_row.get("entity_depth") or 0),
        years=years,
        rounding_digits=rounding_digits,
        base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
        sum_ec=sum_ec,
        base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
        sum_sipr=sum_sipr,
        formula_tooltip=_EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_TOOLTIP,
    )
    if not verify_rows:
        return
    for verify_row in verify_rows:
        verify_row["pd_ec_verification_require_isolated_eu"] = True
    _insert_summary_rows_after_indices(
        summary_rows,
        {block.stop - 1: verify_rows},
    )


def inject_east_energy_zone_o1_res_energy_unit_verification_rows(
    summary_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Проверки РЭС (О-1) с несколькими энергорайонами в блоке «Энергозона Востока»."""
    if not summary_rows or not source_rows or not years:
        return
    if any(
        str(row.get("entity_kind") or "") == "east_ez_o1_res_energy_unit_sum_check"
        for row in summary_rows
    ):
        return
    block = _east_energy_zone_summary_block_slice(summary_rows)
    if block is None:
        return

    res_model = RegionalEnergySystemEnergyConsumptionParameter.__name__
    eu_model = EnergyUnitEnergyConsumptionParameter.__name__
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
    insertions_after: dict[int, list[dict[str, Any]]] = {}

    for res_index in range(block.start, block.stop):
        row = summary_rows[res_index]
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != res_model:
            continue
        if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
            continue
        if row.get("pd_ec_gaes_injected_row"):
            continue
        res_id = row.get("parent_id")
        if res_id is None:
            continue
        try:
            res_id_int = int(res_id)
        except (TypeError, ValueError):
            continue
        res_label = str(row.get("entity_label") or "").strip()
        eu_block_starts = _res_subtree_o1_energy_unit_block_start_indices(
            source_rows,
            res_index,
        )
        if len(eu_block_starts) <= 1:
            continue
        perimeter_variant_code = row.get("perimeter_variant_code")
        base_ec_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            demand_model_name=res_model,
            parent_fk_column="id_regional_energy_system",
            parent_id=res_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        base_sipr_row = _find_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            demand_model_name=res_model,
            parent_fk_column="id_regional_energy_system",
            parent_id=res_id_int,
            perimeter_variant_code=perimeter_variant_code,
        )
        if base_ec_row is None or base_sipr_row is None:
            continue
        child_ec = _sum_east_ez_o1_res_verification_children_by_year(
            source_rows,
            res_start_index=res_index,
            res_label=res_label,
            years=years,
            parameter_key=ec_key,
            demand_model_name=eu_model,
        )
        child_sipr = _sum_east_ez_o1_res_verification_children_by_year(
            source_rows,
            res_start_index=res_index,
            res_label=res_label,
            years=years,
            parameter_key=sipr_key,
            demand_model_name=eu_model,
        )
        formula_tooltip = (
            _CHUKOTKA_O1_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP
            if res_label == _CHUKOTKA_RES_LABEL
            else _EAST_EZ_O1_RES_ENERGY_UNIT_VERIFICATION_TOOLTIP
        )
        verify_rows = _build_ec_summary_verification_rows(
            entity_label=f"Проверка для {res_label}".strip(),
            entity_kind="east_ez_o1_res_energy_unit_sum_check",
            entity_depth=int(row.get("entity_depth") or 0),
            years=years,
            rounding_digits=rounding_digits,
            base_ec=_raw_year_values_from_summary_row(base_ec_row, years),
            sum_ec=child_ec,
            base_sipr=_raw_year_values_from_summary_row(base_sipr_row, years),
            sum_sipr=child_sipr,
            formula_tooltip=formula_tooltip,
        )
        if not verify_rows:
            continue
        for verify_row in verify_rows:
            verify_row["pd_ec_verification_require_isolated_eu"] = True
        subtree_end = _res_subtree_end_index(summary_rows, res_index)
        insertions_after[subtree_end] = insertions_after.get(subtree_end, []) + verify_rows

    _insert_summary_rows_after_indices(summary_rows, insertions_after)


def _is_regional_district_summary_consumption_block_start(row: dict[str, Any]) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if row.get("demand_model_name") != RegionalDistrictEnergyConsumptionParameter.__name__:
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("gaes_without_charge_formula_kind") == "rd":
        return False
    if row.get("pd_ec_rd_without_gaes_injected_row"):
        return False
    code = str(row.get("perimeter_variant_code") or "")
    return "without_gaes" not in code


def _is_regional_district_gaes_charge_row(row: dict[str, Any], parent_id: int) -> bool:
    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("demand_model_name") != RegionalDistrictEnergyConsumptionParameter.__name__:
        return False
    return row.get("parent_id") == parent_id


def _build_regional_district_without_gaes_block_rows(
    source_block: list[dict[str, Any]],
    years: list[int],
    gaes_by_year: dict[int, Decimal | None],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    if not source_block:
        return []
    anchor = source_block[0]
    base_label, kal_qual = _strip_summary_table_variant_suffixes_from_label(
        str(anchor.get("entity_label") or "")
    )
    if kal_qual:
        base_label = f"{base_label} ({kal_qual})"
    entity_label = _format_gaes_related_entity_label(base_label, _GAES_LABEL_SUFFIX_WITHOUT)
    out: list[dict[str, Any]] = []
    block_size = len(source_block)
    for index, source_row in enumerate(source_block):
        new_row = copy.copy(source_row)
        new_row["entity_label"] = entity_label
        new_row["entity_rowspan"] = block_size
        new_row["show_entity_cell"] = index == 0
        new_row["show_entity_note_cell"] = index == 0
        new_row["perimeter_variant_code"] = CODE_WITHOUT_NT_WITHOUT_GAES
        new_row["perimeter_variant_label"] = ""
        new_row["perimeter_variant_options"] = []
        new_row["show_perimeter_variant_select"] = False
        new_row["pd_ec_gaes_extra_row"] = True
        new_row["pd_ec_gaes_without_row"] = True
        new_row["pd_ec_nt_extra_row"] = False
        new_row["pd_ec_nt_without_row"] = False
        new_row["pd_ec_entity_label_compact"] = entity_label
        new_row["pd_ec_entity_label_compact_nt"] = entity_label
        new_row["pd_ec_entity_label_compact_nt_gaes"] = entity_label
        new_row["pd_ec_formula_derived_row"] = True
        new_row["gaes_without_charge_formula_kind"] = "rd"
        new_row["pd_ec_rd_without_gaes_injected_row"] = True
        new_row["pd_ec_territory_detail_relaxed_compact_nt_gaes"] = True
        new_row.pop("pd_ec_territory_detail_row", None)
        new_row.pop("pd_ec_summary_row_formula_tooltip", None)
        out.append(new_row)

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        target_row = next(
            (row for row in out if row.get("parameter_key") == parameter_key),
            None,
        )
        source_row = next(
            (row for row in source_block if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None or source_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    return out


def inject_regional_district_without_gaes_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Строки «субъект РФ … без заряда ГАЭС»: расчёт = потребление субъекта − заряд ГАЭС; видимость как у заряда ГАЭС."""
    if not summary_rows or not years:
        return

    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_regional_district_summary_consumption_block_start(row):
            i += 1
            continue

        parent_id = row.get("parent_id")
        if parent_id is None:
            i += 1
            continue

        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        source_block = summary_rows[i : i + block_size]
        j = i + block_size
        while j < n and _is_regional_district_gaes_charge_row(summary_rows[j], int(parent_id)):
            j += 1

        if any(item.get("pd_ec_rd_without_gaes_injected_row") for item in source_block):
            i = j
            continue

        if not _summary_row_entity_has_gaes_charge(source_block[0]):
            i = j
            continue

        entity_key = _gaes_charge_entity_key(source_block[0])
        gaes_by_year = gaes_totals.get(entity_key, {})
        injected = _build_regional_district_without_gaes_block_rows(
            source_block,
            years,
            gaes_by_year,
            rounding_digits,
        )
        if injected:
            summary_rows[j:j] = injected
            n = len(summary_rows)
            i = j + len(injected)
        else:
            i = j


def _build_oes_style_without_gaes_block_rows(
    source_block: list[dict[str, Any]],
    years: list[int],
    gaes_by_year: dict[int, Decimal | None],
    rounding_digits: int,
    *,
    injected_flag_key: str,
) -> list[dict[str, Any]]:
    if not source_block:
        return []
    anchor = source_block[0]
    base_label = _territory_gaes_entity_base_label(anchor)
    entity_label = _format_gaes_related_entity_label(
        base_label, _GAES_LABEL_SUFFIX_WITHOUT
    )
    out: list[dict[str, Any]] = []
    block_size = len(source_block)
    for index, source_row in enumerate(source_block):
        new_row = copy.copy(source_row)
        new_row["entity_label"] = entity_label
        new_row["entity_rowspan"] = block_size
        new_row["show_entity_cell"] = index == 0
        new_row["show_entity_note_cell"] = index == 0
        new_row["perimeter_variant_code"] = None
        new_row["perimeter_variant_label"] = ""
        new_row["perimeter_variant_options"] = []
        new_row["show_perimeter_variant_select"] = False
        new_row["pd_ec_gaes_extra_row"] = True
        new_row["pd_ec_gaes_without_row"] = True
        new_row["pd_ec_nt_extra_row"] = False
        new_row["pd_ec_nt_without_row"] = False
        new_row["pd_ec_entity_label_compact"] = base_label
        new_row["pd_ec_entity_label_compact_nt"] = entity_label
        new_row["pd_ec_entity_label_compact_nt_gaes"] = base_label
        new_row["pd_ec_formula_derived_row"] = True
        new_row["gaes_without_charge_formula_kind"] = "oes"
        new_row[injected_flag_key] = True
        new_row["entity_note_row_id"] = None
        new_row["entity_note_text"] = ""
        new_row["hist_row_id"] = None
        new_row["year_row_ids"] = [None for _ in years]
        new_row.pop("pd_ec_summary_row_formula_tooltip", None)
        out.append(new_row)

    for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
        target_row = next(
            (row for row in out if row.get("parameter_key") == parameter_key),
            None,
        )
        source_row = next(
            (row for row in source_block if row.get("parameter_key") == parameter_key),
            None,
        )
        if target_row is None or source_row is None:
            continue
        source_by_year = _raw_year_values_from_summary_row(source_row, years)
        adjusted: dict[int, Decimal | None] = {}
        for year in years:
            base_value = source_by_year.get(int(year))
            if base_value is None:
                adjusted[int(year)] = None
                continue
            gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
            adjusted[int(year)] = base_value - gaes_value
        _write_numeric_year_values_to_summary_row(
            target_row,
            years,
            adjusted,
            parameter_key=parameter_key,
            rounding_digits=rounding_digits,
        )

    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_mln_kvt_ch",
        abs_parameter_key=None,
        yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    _recompute_growth_rows_from_base_series(
        out,
        years,
        base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
        abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        rounding_digits=rounding_digits,
    )
    return out


def _build_union_energy_system_without_gaes_block_rows(
    source_block: list[dict[str, Any]],
    years: list[int],
    gaes_by_year: dict[int, Decimal | None],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    return _build_oes_style_without_gaes_block_rows(
        source_block,
        years,
        gaes_by_year,
        rounding_digits,
        injected_flag_key="pd_ec_ues_without_gaes_injected_row",
    )


def _is_oes_style_territory_summary_consumption_block_start(
    row: dict[str, Any],
    *,
    demand_model_name: str,
    injected_flag_key: str,
) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if row.get("demand_model_name") != demand_model_name:
        return False
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get(injected_flag_key):
        return False
    return not str(row.get("perimeter_variant_code") or "").strip()


def _is_oes_style_territory_gaes_charge_row(
    row: dict[str, Any],
    parent_id: int,
    *,
    demand_model_name: str,
) -> bool:
    if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
        return False
    if row.get("demand_model_name") != demand_model_name:
        return False
    return row.get("parent_id") == parent_id


def _inject_oes_style_without_gaes_summary_rows_for_model(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    demand_model_name: str,
    injected_flag_key: str,
) -> None:
    if not summary_rows or not years:
        return

    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_oes_style_territory_summary_consumption_block_start(
            row,
            demand_model_name=demand_model_name,
            injected_flag_key=injected_flag_key,
        ):
            i += 1
            continue
        if row.get("entity_kind") == "fo_nt_under_south":
            i += 1
            continue

        parent_id = row.get("parent_id")
        if parent_id is None:
            i += 1
            continue

        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        source_block = summary_rows[i : i + block_size]
        if any(item.get(injected_flag_key) for item in source_block):
            i += block_size
            continue

        j = i + block_size
        while j < n and _is_oes_style_territory_gaes_charge_row(
            summary_rows[j],
            int(parent_id),
            demand_model_name=demand_model_name,
        ):
            j += 1

        if j == i + block_size or not _summary_row_entity_has_gaes_charge(source_block[0]):
            i = j
            continue

        entity_key = _gaes_charge_entity_key(source_block[0])
        gaes_by_year = gaes_totals.get(entity_key, {})
        injected = _build_oes_style_without_gaes_block_rows(
            source_block,
            years,
            gaes_by_year,
            rounding_digits,
            injected_flag_key=injected_flag_key,
        )
        if injected:
            summary_rows[j:j] = injected
            n = len(summary_rows)
            i = j + len(injected)
        else:
            i = j


def inject_union_energy_system_without_gaes_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Для ОЭС без варианта добавляет формульный блок «без заряда ГАЭС» после строки заряда."""
    _inject_oes_style_without_gaes_summary_rows_for_model(
        summary_rows,
        years,
        rounding_digits,
        demand_model_name=UnionEnergySystemEnergyConsumptionParameter.__name__,
        injected_flag_key="pd_ec_ues_without_gaes_injected_row",
    )


def inject_oes_territory_detail_without_gaes_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """РЭС и субъекты РФ на /summary/oes/: блок «без заряда ГАЭС» как у ОЭС без варианта."""
    _inject_oes_style_without_gaes_summary_rows_for_model(
        summary_rows,
        years,
        rounding_digits,
        demand_model_name=RegionalEnergySystemEnergyConsumptionParameter.__name__,
        injected_flag_key="pd_ec_res_without_gaes_injected_row",
    )
    _inject_oes_style_without_gaes_summary_rows_for_model(
        summary_rows,
        years,
        rounding_digits,
        demand_model_name=RegionalDistrictEnergyConsumptionParameter.__name__,
        injected_flag_key="pd_ec_rd_without_gaes_injected_row",
    )


_TERRITORY_GAES_LABEL_DEMAND_MODELS = frozenset(
    {
        FederalDistrictEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
    }
)


def _entity_has_structural_gaes_perimeter_variants(
    summary_rows: list[dict[str, Any]],
    entity_key: tuple[Any, ...],
) -> bool:
    """True, если у сущности уже есть варианты с/без заряда ГАЭС в привязках (не инжект)."""
    for row in summary_rows:
        if (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        ) != entity_key:
            continue
        if row.get("pd_ec_fo_without_gaes_injected_row") or row.get(
            "pd_ec_rd_without_gaes_injected_row"
        ):
            continue
        if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if "with_gaes" in code or "without_gaes" in code:
            return True
    return False


def _collect_territory_entities_with_gaes_summary_blocks(
    summary_rows: list[dict[str, Any]],
) -> set[tuple[Any, ...]]:
    entities: set[tuple[Any, ...]] = set()
    for row in summary_rows:
        if row.get("demand_model_name") not in _TERRITORY_GAES_LABEL_DEMAND_MODELS:
            continue
        if row.get("parent_id") is None:
            continue
        if not (
            row.get("pd_ec_gaes_injected_row")
            or row.get("pd_ec_fo_without_gaes_injected_row")
            or row.get("pd_ec_rd_without_gaes_injected_row")
            or row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
        ):
            continue
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        # «Южный ФО» и подобные: подписи НТ/ГАЭС уже из кодов вариантов; не перезаписывать.
        if _entity_has_structural_gaes_perimeter_variants(summary_rows, entity_key):
            continue
        entities.add(entity_key)
    return entities


def _classify_territory_gaes_summary_row(row: dict[str, Any]) -> str | None:
    if row.get("demand_model_name") not in _TERRITORY_GAES_LABEL_DEMAND_MODELS:
        return None
    if row.get("pd_ec_fo_without_gaes_injected_row") or row.get(
        "pd_ec_rd_without_gaes_injected_row"
    ):
        return "without_gaes"
    if row.get("gaes_without_charge_formula_kind") in ("fo", "rd"):
        return "without_gaes"
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY or row.get(
        "pd_ec_gaes_injected_row"
    ):
        return "charge"
    return "main"


def _territory_gaes_entity_base_label(row: dict[str, Any]) -> str:
    base, kal_qual = _strip_summary_table_variant_suffixes_from_label(
        str(row.get("entity_label") or "")
    )
    if kal_qual:
        base = f"{base} ({kal_qual})"
    return base


def _territory_gaes_main_compact_nt_on_gaes_off(
    base_label: str,
    perimeter_variant_code: str | None,
) -> str:
    code = str(perimeter_variant_code or "").strip()
    if not code:
        return base_label
    return _format_summary_table_entity_label_for_toggle_state(
        base_label,
        code,
        nt_detail_on=True,
        gaes_detail_on=False,
    )


def apply_fo_rd_gaes_territory_entity_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Подписи ФО/субъект РФ с ГАЭС: «с зарядом», «(заряд)», «без заряда» при +Заряд ГАЭС."""
    if not summary_rows:
        return

    gaes_entities = _collect_territory_entities_with_gaes_summary_blocks(summary_rows)
    if not gaes_entities:
        return

    for row in summary_rows:
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        if entity_key not in gaes_entities:
            continue

        row_kind = _classify_territory_gaes_summary_row(row)
        if row_kind is None:
            continue

        base_label = _territory_gaes_entity_base_label(row)
        label_with_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITH
        )
        label_without_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITHOUT
        )
        label_charge = _format_gaes_related_entity_label(
            base_label, _GAES_CHARGE_LABEL_SUFFIX
        )
        compact_nt_on_gaes_off = _territory_gaes_main_compact_nt_on_gaes_off(
            base_label,
            row.get("perimeter_variant_code"),
        )

        if row_kind == "main":
            row["entity_label"] = label_with_gaes
            row["pd_ec_entity_label_compact"] = compact_nt_on_gaes_off
            row["pd_ec_entity_label_compact_nt"] = label_with_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            if not str(row.get("perimeter_variant_code") or "").strip():
                row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITH
        elif row_kind == "charge":
            row["entity_label"] = label_charge
            row["pd_ec_entity_label_compact"] = label_charge
            row["pd_ec_entity_label_compact_nt"] = label_charge
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
        else:
            row["entity_label"] = label_without_gaes
            row["pd_ec_entity_label_compact"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITHOUT


def _collect_union_energy_system_entities_with_gaes_summary_blocks(
    summary_rows: list[dict[str, Any]],
) -> set[tuple[Any, ...]]:
    entities: set[tuple[Any, ...]] = set()
    for row in summary_rows:
        if row.get("demand_model_name") != UnionEnergySystemEnergyConsumptionParameter.__name__:
            continue
        if row.get("parent_id") is None:
            continue
        if not (
            row.get("pd_ec_ues_without_gaes_injected_row")
            or row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
        ):
            continue
        entities.add(
            (
                row.get("demand_model_name"),
                row.get("parent_fk_column"),
                row.get("parent_id"),
            )
        )
    return entities


def _classify_union_energy_system_gaes_summary_row(
    row: dict[str, Any],
) -> str | None:
    if row.get("demand_model_name") != UnionEnergySystemEnergyConsumptionParameter.__name__:
        return None
    if str(row.get("perimeter_variant_code") or "").strip():
        return None
    if row.get("pd_ec_ues_without_gaes_injected_row") or row.get(
        "gaes_without_charge_formula_kind"
    ) == "oes":
        return "without_gaes"
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return "charge"
    return "main"


def apply_union_energy_system_gaes_entity_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Подписи ОЭС без варианта: «с зарядом», «(заряд)», «без заряда» при +Заряд ГАЭС."""
    if not summary_rows:
        return

    gaes_entities = _collect_union_energy_system_entities_with_gaes_summary_blocks(
        summary_rows
    )
    if not gaes_entities:
        return

    for row in summary_rows:
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        if entity_key not in gaes_entities:
            continue

        row_kind = _classify_union_energy_system_gaes_summary_row(row)
        if row_kind is None:
            continue

        base_label = _territory_gaes_entity_base_label(row)
        label_with_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITH
        )
        label_without_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITHOUT
        )
        label_charge = _format_gaes_related_entity_label(
            base_label, _GAES_CHARGE_LABEL_SUFFIX
        )

        if row_kind == "main":
            row["entity_label"] = label_with_gaes
            row["pd_ec_entity_label_compact"] = base_label
            row["pd_ec_entity_label_compact_nt"] = label_with_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITH
        elif row_kind == "charge":
            row["entity_label"] = label_charge
            row["pd_ec_entity_label_compact"] = label_charge
            row["pd_ec_entity_label_compact_nt"] = label_charge
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
        else:
            row["entity_label"] = label_without_gaes
            row["pd_ec_entity_label_compact"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITHOUT


_OES_TERRITORY_DETAIL_GAES_LABEL_DEMAND_MODELS = frozenset(
    {
        RegionalEnergySystemEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
    }
)

_OES_TERRITORY_DETAIL_WITHOUT_GAES_INJECTED_FLAGS = frozenset(
    {
        "pd_ec_res_without_gaes_injected_row",
        "pd_ec_rd_without_gaes_injected_row",
    }
)


def _collect_oes_territory_detail_entities_with_gaes_summary_blocks(
    summary_rows: list[dict[str, Any]],
) -> set[tuple[Any, ...]]:
    entities: set[tuple[Any, ...]] = set()
    for row in summary_rows:
        if row.get("demand_model_name") not in _OES_TERRITORY_DETAIL_GAES_LABEL_DEMAND_MODELS:
            continue
        if row.get("parent_id") is None:
            continue
        if str(row.get("perimeter_variant_code") or "").strip():
            continue
        if not (
            row.get("pd_ec_res_without_gaes_injected_row")
            or row.get("pd_ec_rd_without_gaes_injected_row")
            or row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
        ):
            continue
        entities.add(
            (
                row.get("demand_model_name"),
                row.get("parent_fk_column"),
                row.get("parent_id"),
            )
        )
    return entities


def _classify_oes_territory_detail_gaes_summary_row(
    row: dict[str, Any],
) -> str | None:
    if row.get("demand_model_name") not in _OES_TERRITORY_DETAIL_GAES_LABEL_DEMAND_MODELS:
        return None
    if str(row.get("perimeter_variant_code") or "").strip():
        return None
    if any(row.get(flag) for flag in _OES_TERRITORY_DETAIL_WITHOUT_GAES_INJECTED_FLAGS):
        return "without_gaes"
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        return "charge"
    return "main"


def apply_oes_territory_detail_gaes_entity_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Подписи РЭС/субъекта РФ на /summary/oes/: как у ОЭС без варианта."""
    if not summary_rows:
        return

    gaes_entities = _collect_oes_territory_detail_entities_with_gaes_summary_blocks(
        summary_rows
    )
    if not gaes_entities:
        return

    for row in summary_rows:
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        if entity_key not in gaes_entities:
            continue

        row_kind = _classify_oes_territory_detail_gaes_summary_row(row)
        if row_kind is None:
            continue

        base_label = _territory_gaes_entity_base_label(row)
        label_with_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITH
        )
        label_without_gaes = _format_gaes_related_entity_label(
            base_label, _GAES_LABEL_SUFFIX_WITHOUT
        )
        label_charge = _format_gaes_related_entity_label(
            base_label, _GAES_CHARGE_LABEL_SUFFIX
        )

        if row_kind == "main":
            row["entity_label"] = label_with_gaes
            row["pd_ec_entity_label_compact"] = base_label
            row["pd_ec_entity_label_compact_nt"] = label_with_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITH
        elif row_kind == "charge":
            row["entity_label"] = label_charge
            row["pd_ec_entity_label_compact"] = label_charge
            row["pd_ec_entity_label_compact_nt"] = label_charge
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
        else:
            row["entity_label"] = label_without_gaes
            row["pd_ec_entity_label_compact"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt"] = label_without_gaes
            row["pd_ec_entity_label_compact_nt_gaes"] = base_label
            row["perimeter_variant_label"] = _GAES_PERIMETER_VARIANT_LABEL_WITHOUT


def apply_oes_max_summary_formula_calculations(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    eu_source_rows_for_tites: list[dict[str, Any]] | None = None,
    apply_display_masks: bool = True,
) -> None:
    """Формулы строк сводки ОЭС как на /energy_consumption/summary/oes/ (до UI-фильтров)."""
    eu_source_rows = (
        eu_source_rows_for_tites
        if eu_source_rows_for_tites is not None
        else summary_rows
    )
    apply_oes_ees_unified_consumption_formula_to_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
        ues_source_rows=eu_source_rows,
    )
    apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
        eu_source_rows=eu_source_rows,
    )
    apply_summary_table_formula_calculations(
        summary_rows,
        years,
        rounding_digits,
        eu_source_rows_for_tites=eu_source_rows,
    )
    inject_south_ues_new_territories_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
    )
    inject_union_energy_system_without_gaes_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
    )
    inject_oes_territory_detail_without_gaes_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=rounding_digits,
    )
    if apply_display_masks:
        mask_summary_rows_perimeter_variant_year_display(summary_rows, years)
        apply_sipr_consumption_display_fallback_to_summary_rows(summary_rows, years)
        recompute_sipr_growth_metrics_for_summary_rows(
            summary_rows,
            years,
            rounding_digits,
        )


def build_summary_table_rows_with_formulas_for_version(
    *,
    database_version_id: int,
    years: list[int],
    rounding_digits: int = 1,
) -> list[dict[str, Any]]:
    """Строки сводки ОЭС с пересчитанными формулами для указанной версии БД."""
    from flask import g

    if not years:
        return []

    prev_version = getattr(g, "current_db_version", _VERSION_CONTEXT_UNSET)
    g.current_db_version = database_version_id
    try:
        sy, ey = min(years), max(years)
        ctx = build_oes_summary_context(
            rounding_digits,
            start_year=sy,
            end_year=ey,
            data_start_year=sy,
            data_end_year=ey,
            filter_year_list=sorted(years),
            ees_top_from_db=True,
            russia_country_summary_ec_divisor=1,
            include_ees_russia_rows=False,
            include_synchronous_area_rows=False,
            include_oes_summary_table_sync_sa_ees_verification=False,
            expand_south_ues_perimeter_variants=True,
            summary_table_top_order=True,
            ees_unified_use_ees_russia_gaes_variants=True,
        )
        summary_rows = list(ctx.get("summary_rows") or [])
        eu_source_rows = list(summary_rows)
        ctx_years = list(ctx.get("years") or years)
        apply_energy_consumption_summary_table_variant_toggle_rows(summary_rows)
        apply_summary_table_russia_federation_row_rules(summary_rows)
        apply_oes_max_summary_formula_calculations(
            summary_rows,
            ctx_years,
            rounding_digits,
            eu_source_rows_for_tites=eu_source_rows,
            apply_display_masks=False,
        )
        summary_rows = filter_oes_summary_hidden_tites_union_energy_system_rows(
            summary_rows
        )
        return filter_summary_table_gaes_charge_aggregate_rows(summary_rows)
    finally:
        if prev_version is _VERSION_CONTEXT_UNSET:
            if hasattr(g, "current_db_version"):
                delattr(g, "current_db_version")
        else:
            g.current_db_version = prev_version


def build_fo_summary_formula_rows_for_version(
    *,
    database_version_id: int,
    years: list[int],
    rounding_digits: int = 1,
) -> list[dict[str, Any]]:
    """Строки сводки по ФО с формулами (как на /summary/federal_districts/) для записи в БД."""
    from flask import g

    from app.energy_consumption.pages._summary_page_transforms import (
        apply_max_summary_page_variant_behaviour,
    )

    if not years:
        return []

    prev_version = getattr(g, "current_db_version", _VERSION_CONTEXT_UNSET)
    g.current_db_version = database_version_id
    try:
        sy, ey = min(years), max(years)
        ctx = build_federal_district_summary_context(
            rounding_digits,
            start_year=sy,
            end_year=ey,
            data_start_year=sy,
            data_end_year=ey,
            filter_year_list=sorted(years),
            fo_filter_sets=(frozenset(), frozenset()),
            expand_entity_perimeter_variants=True,
        )
        ctx["active_summary"] = "fo"
        ctx = apply_max_summary_page_variant_behaviour(ctx)
        return [
            row
            for row in (ctx.get("summary_rows") or [])
            if row.get("pd_ec_formula_derived_row")
        ]
    finally:
        if prev_version is _VERSION_CONTEXT_UNSET:
            if hasattr(g, "current_db_version"):
                delattr(g, "current_db_version")
        else:
            g.current_db_version = prev_version


def build_all_formula_summary_rows_for_version(
    *,
    database_version_id: int,
    years: list[int],
    rounding_digits: int = 1,
) -> list[dict[str, Any]]:
    """Объединённые расчётные строки сводной таблицы ОЭС и сводки по ФО."""
    oes_rows = build_summary_table_rows_with_formulas_for_version(
        database_version_id=database_version_id,
        years=years,
        rounding_digits=rounding_digits,
    )
    fo_rows = build_fo_summary_formula_rows_for_version(
        database_version_id=database_version_id,
        years=years,
        rounding_digits=rounding_digits,
    )
    if not fo_rows:
        return list(oes_rows)
    seen: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []
    for row in list(oes_rows) + list(fo_rows):
        if not row.get("pd_ec_formula_derived_row"):
            continue
        dedupe_key = (
            str(row.get("demand_model_name") or ""),
            str(row.get("parent_fk_column") or ""),
            int(row.get("parent_id") or 0),
            str(row.get("parameter_key") or ""),
            row.get("perimeter_variant_code"),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        merged.append(row)
    return merged


def tag_energy_consumption_summary_rows_for_ui_toggles(rows: list[dict[str, Any]]) -> None:
    """Помечает строки для кнопок «Заряд ГАЭС» и «НТ» на экране."""
    for row in rows:
        label = str(row.get("entity_label") or "")
        label_cf = label.casefold()
        pk = str(row.get("parameter_key") or "")
        ek = str(row.get("entity_kind") or "")

        row["pd_ec_nt_extra_row"] = (
            "(с нт)" in label_cf
            or " с нт" in label_cf
            or ek in ("fo_nt_under_south",)
            or "новые территории" in label_cf
        )
        if ek == "oes_south_without_nt":
            row["pd_ec_nt_extra_row"] = False

        row["pd_ec_gaes_extra_row"] = (
            pk == GAES_CHARGE_PARAMETER_KEY
            or "с зарядом гаэс" in label_cf
            or "(заряд гаэс)" in label_cf
        )


def _base_gaes_charge_sum_query(years: tuple[int, ...]):
    q = (
        db.session.query(
            StationGaesChargeConsumption.year_number,
            func.sum(StationGaesChargeConsumption.charge_consumption),
        )
        .select_from(StationGaesChargeConsumption)
        .join(Station, Station.id == StationGaesChargeConsumption.id_station)
    )
    q = dps.filter_parents_by_version(q, StationGaesChargeConsumption)
    q = dps.filter_parents_by_version(q, Station)
    if years:
        q = q.filter(StationGaesChargeConsumption.year_number.in_(years))
    return q


def _join_gaes_charge_energy_unit(q):
    return q.outerjoin(EnergyUnit, Station.id_energy_unit == EnergyUnit.id)


def _join_gaes_charge_regional_district(q):
    q = _join_gaes_charge_energy_unit(q)
    return q.outerjoin(
        RegionalDistrict,
        or_(
            Station.id_regional_district == RegionalDistrict.id,
            EnergyUnit.id_regional_district == RegionalDistrict.id,
        ),
    )


def _join_gaes_charge_regional_energy_system(q):
    q = _join_gaes_charge_energy_unit(q)
    return q.outerjoin(
        RegionalEnergySystem,
        or_(
            Station.id_regional_energy_system == RegionalEnergySystem.id,
            EnergyUnit.id_regional_energy_system == RegionalEnergySystem.id,
        ),
    )


_GAES_STATION_TYPE_NAME_CF = "гаэс"


def _apply_gaes_station_type_filter(q):
    q = q.join(StationType, Station.id_station_type == StationType.id)
    q = dps.filter_parents_by_version(q, StationType)
    return q.filter(func.lower(StationType.name) == _GAES_STATION_TYPE_NAME_CF)


def _gaes_stations_for_entity_query(
    demand_model_name: str | None,
    parent_id: int | None,
):
    """Все электростанции типа ГАЭС в территории сущности сводки (текущая версия БД)."""
    q = db.session.query(Station.id, Station.name).select_from(Station)
    q = dps.filter_parents_by_version(q, Station)
    q = _apply_gaes_station_type_filter(q)
    return _apply_gaes_charge_summary_entity_filter(q, demand_model_name, parent_id)


def _apply_gaes_charge_summary_entity_filter(
    q,
    demand_model_name: str | None,
    parent_id: int | None,
):
    """Территориальный фильтр станций заряда ГАЭС (как в сводке по сущности)."""
    if demand_model_name == EnergyUnitEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return q.filter(Station.id_energy_unit == parent_id)
    if demand_model_name == RegionalDistrictEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_energy_unit(q).filter(
            or_(
                Station.id_regional_district == parent_id,
                EnergyUnit.id_regional_district == parent_id,
            )
        )
    if demand_model_name == RegionalEnergySystemEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_energy_unit(q).filter(
            or_(
                Station.id_regional_energy_system == parent_id,
                EnergyUnit.id_regional_energy_system == parent_id,
            )
        )
    if demand_model_name == UnionEnergySystemEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_regional_energy_system(q).filter(
            RegionalEnergySystem.id_union_energy_system == parent_id
        )
    if demand_model_name == EnergySystemTypeEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_regional_energy_system(q).outerjoin(
            UnionEnergySystem,
            RegionalEnergySystem.id_union_energy_system == UnionEnergySystem.id,
        ).filter(UnionEnergySystem.id_energy_system_type == parent_id)
    if demand_model_name == SynchronousAreaEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_regional_district(q).filter(
            RegionalDistrict.id_synchronous_area == parent_id
        )
    if demand_model_name == FederalDistrictEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_regional_district(q).filter(
            RegionalDistrict.id_federal_district == parent_id
        )
    if demand_model_name == EnergyZoneEnergyConsumptionParameter.__name__:
        if parent_id is None:
            return None
        return _join_gaes_charge_regional_district(q).filter(
            RegionalDistrict.id_energy_zone == parent_id
        )
    if demand_model_name in {
        CentralizedZoneEnergyConsumptionParameter.__name__,
        RussiaFederationEnergyConsumptionParameter.__name__,
        EesRussiaEnergyConsumptionParameter.__name__,
    }:
        return q
    return None


def clear_gaes_charge_summary_cache() -> None:
    """Сброс LRU-кэша строк заряда ГАЭС после сохранения в БД."""
    _entity_has_gaes_charge_stations.cache_clear()
    _gaes_charge_raw_station_values_for_entity.cache_clear()


@lru_cache(maxsize=4096)
def _entity_has_gaes_charge_stations(
    current_version_id: int | None,
    demand_model_name: str | None,
    parent_id: int | None,
) -> bool:
    """True, если у сущности сводки есть электростанции типа ГАЭС (текущая версия БД)."""
    del current_version_id
    if not demand_model_name or parent_id is None:
        return False
    q = _gaes_stations_for_entity_query(demand_model_name, int(parent_id))
    if q is None:
        return False
    return q.limit(1).first() is not None


def _summary_row_entity_has_gaes_charge(row: dict[str, Any]) -> bool:
    parent_id = row.get("parent_id")
    if parent_id is None:
        return False
    return _entity_has_gaes_charge_stations(
        dps.get_current_version(),
        row.get("demand_model_name"),
        int(parent_id),
    )


@lru_cache(maxsize=4096)
def _gaes_charge_raw_station_values_for_entity(
    current_version_id: int | None,
    demand_model_name: str | None,
    parent_fk_column: str | None,
    parent_id: int | None,
    years: tuple[int, ...],
) -> tuple[tuple[int, str, tuple[tuple[int, Any], ...]], ...]:
    """Потребление ГАЭС на заряд по станциям типа ГАЭС для сущности и годов.

    В таблицу попадают все станции типа ГАЭС текущей версии БД в территории сущности,
    даже если по ним ещё нет сохранённых значений заряда.
    """
    del current_version_id, parent_fk_column
    if not demand_model_name or not years:
        return tuple()

    stations_q = _gaes_stations_for_entity_query(demand_model_name, parent_id)
    if stations_q is None:
        return tuple()

    station_rows = (
        stations_q.order_by(Station.name.asc().nullslast(), Station.id.asc()).all()
    )
    if not station_rows:
        return tuple()

    station_ids = [int(station_id) for station_id, _ in station_rows if station_id is not None]
    if not station_ids:
        return tuple()

    charge_q = (
        db.session.query(
            StationGaesChargeConsumption.id_station,
            StationGaesChargeConsumption.year_number,
            func.sum(StationGaesChargeConsumption.charge_consumption),
        )
        .filter(StationGaesChargeConsumption.id_station.in_(station_ids))
        .filter(StationGaesChargeConsumption.year_number.in_(years))
    )
    charge_q = dps.filter_parents_by_version(charge_q, StationGaesChargeConsumption)
    charge_rows = charge_q.group_by(
        StationGaesChargeConsumption.id_station,
        StationGaesChargeConsumption.year_number,
    ).all()

    values_by_station: dict[int, list[tuple[int, Any]]] = {
        sid: [] for sid in station_ids
    }
    for station_id, year, value in charge_rows:
        if station_id is None or year is None or value is None:
            continue
        values_by_station[int(station_id)].append((int(year), value))

    return tuple(
        (
            int(station_id),
            (station_name or "").strip() or "Без названия",
            tuple(values_by_station.get(int(station_id), ())),
        )
        for station_id, station_name in station_rows
        if station_id is not None
    )


def _is_gaes_charge_marker_entity(entity: SummaryEntity) -> bool:
    """Маркер слота «… (заряд ГАЭС)» между вариантами с/без заряда (пустые parameters)."""
    return (
        not entity.parameters
        and bool(entity.demand_model_name)
        and entity.parent_id is not None
        and entity.perimeter_variant_code is None
    )


def _empty_gaes_charge_placeholder_rows(
    entity: SummaryEntity,
    years: list[int],
) -> list[dict[str, Any]]:
    """Пустая строка заряда ГАЭС, чтобы слот был виден при «без заряда ГАЭС» без станций в ФО."""
    label = _format_gaes_related_entity_label(entity.label, " (заряд ГАЭС)")
    row: dict[str, Any] = {
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_depth": entity.depth,
        "entity_kind": entity.entity_kind,
        "show_entity_cell": True,
        "parameter_key": GAES_CHARGE_PARAMETER_KEY,
        "parameter_label": GAES_CHARGE_PARAMETER_LABEL,
        "demand_model_name": entity.demand_model_name,
        "parent_fk_column": entity.parent_fk_column,
        "parent_id": entity.parent_id,
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "year_values": ["—" for _ in years],
        "year_numeric_tooltips": ["" for _ in years],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": None,
        "pd_ec_gaes_injected_row": True,
        "pd_ec_skip_empty_hide_row": True,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "entity_note_row_id": None,
        "show_entity_note_cell": True,
        "entity_note_text": "",
        "gaes_charge_row_station_name": "всего",
    }
    ues_id_flat = getattr(entity, "id_union_energy_system", None)
    if (
        ues_id_flat is None
        and getattr(entity, "parent_fk_column", None) == "id_union_energy_system"
        and getattr(entity, "parent_id", None) is not None
    ):
        ues_id_flat = entity.parent_id
    if ues_id_flat is not None:
        row["id_union_energy_system"] = ues_id_flat
    return [row]


def _gaes_charge_rows_for_entity(
    entity: SummaryEntity,
    years: list[int],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    if entity.demand_model_name == CentralizedZoneEnergyConsumptionParameter.__name__:
        return []
    station_rows = _gaes_charge_raw_station_values_for_entity(
            dps.get_current_version(),
            entity.demand_model_name,
            entity.parent_fk_column,
            entity.parent_id,
            tuple(int(y) for y in years),
    )
    if not station_rows:
        # У «Южного ФО» варианты с/без заряда есть в привязках, а станций ГАЭС в ФО нет —
        # без строки «(заряд ГАЭС)» при нажатии «без заряда ГАЭС» слот пропадает.
        if _is_gaes_charge_marker_entity(entity):
            return _empty_gaes_charge_placeholder_rows(entity, years)
        return []
    entity_label_cf = str(entity.label or "").strip().casefold()
    south_ues_charge_totals_only = (
        entity.demand_model_name == UnionEnergySystemEnergyConsumptionParameter.__name__
        and entity_label_cf == SOUTH_UES_NAME_CF
    )
    totals_only = (
        (
            entity.demand_model_name == SynchronousAreaEnergyConsumptionParameter.__name__
            and entity_label_cf == "первая синхронная зона"
        )
        or (
            entity.demand_model_name == EnergySystemTypeEnergyConsumptionParameter.__name__
            and entity_label_cf == EES_UNIFIED_REF_NAME.casefold()
        )
        or (
            entity.demand_model_name == EesRussiaEnergyConsumptionParameter.__name__
            and entity_label_cf == EES_RUSSIA_AGGREGATE_NAME.casefold()
        )
        or south_ues_charge_totals_only
    )

    def _value_maps(raw_values: dict[int, Any]) -> tuple[list[str], list[str]]:
        return (
            [
                _format_summary_parameter_value(
                    raw_values.get(year),
                    GAES_CHARGE_PARAMETER_KEY,
                    rounding_digits,
                )
                if year in raw_values
                else "—"
                for year in years
            ],
            [_format_full_numeric_tooltip(raw_values.get(year)) if year in raw_values else "" for year in years],
        )

    label = _format_gaes_related_entity_label(entity.label, " (заряд ГАЭС)")
    base_row = {
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_depth": entity.depth,
        "entity_kind": entity.entity_kind,
        "show_entity_cell": True,
        "parameter_key": GAES_CHARGE_PARAMETER_KEY,
        "parameter_label": GAES_CHARGE_PARAMETER_LABEL,
        "demand_model_name": entity.demand_model_name,
        "parent_fk_column": entity.parent_fk_column,
        "parent_id": entity.parent_id,
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": None,
        "pd_ec_gaes_injected_row": True,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "entity_note_row_id": None,
        "show_entity_note_cell": True,
    }
    ues_id_flat = getattr(entity, "id_union_energy_system", None)
    if (
        ues_id_flat is None
        and getattr(entity, "parent_fk_column", None) == "id_union_energy_system"
        and getattr(entity, "parent_id", None) is not None
    ):
        ues_id_flat = entity.parent_id
    if ues_id_flat is not None:
        base_row["id_union_energy_system"] = ues_id_flat

    def _apply_gaes_charge_block_rowspan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rowspan = len(rows)
        for index, row in enumerate(rows):
            row["entity_rowspan"] = rowspan
            row["show_entity_cell"] = index == 0
            row["show_entity_note_cell"] = index == 0
        return rows

    out: list[dict[str, Any]] = []
    show_total_row = (
        entity.demand_model_name != UnionEnergySystemEnergyConsumptionParameter.__name__
        or south_ues_charge_totals_only
    )
    if show_total_row and (len(station_rows) > 1 or totals_only):
        total: dict[int, Any] = {}
        for _, _, values_tuple in station_rows:
            for year, value in values_tuple:
                total[year] = (total.get(year) or Decimal(0)) + value
        values, tooltips = _value_maps(total)
        out.append(
            {
                **base_row,
                "year_values": values,
                "year_numeric_tooltips": tooltips,
                "entity_note_text": "",
                "gaes_charge_row_station_name": "всего",
            }
        )
        if totals_only:
            return _apply_gaes_charge_block_rowspan(out)

    for station_id, station_name, values_tuple in station_rows:
        raw_values = dict(values_tuple)
        values, tooltips = _value_maps(raw_values)
        out.append(
            {
                **base_row,
                "year_values": values,
                "year_numeric_tooltips": tooltips,
                "entity_note_text": "",
                "gaes_charge_row_station_name": station_name,
                "gaes_station_id": station_id,
            }
        )
    return _apply_gaes_charge_block_rowspan(out)


_GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
    }
)


def _summary_row_entity_key(row: dict[str, Any]) -> tuple[Any, ...]:
    label = str(row.get("entity_label") or "").strip()
    if label.endswith(" (заряд ГАЭС)"):
        label = label[: -len(" (заряд ГАЭС)")].strip()
    base_label, _ = _strip_summary_table_variant_suffixes_from_label(label)
    return (
        row.get("demand_model_name"),
        row.get("parent_fk_column"),
        row.get("parent_id"),
        row.get("entity_kind"),
        base_label,
    )


def _summary_row_variant_param_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *_summary_row_entity_key(row),
        row.get("perimeter_variant_code"),
        row.get("parameter_key"),
    )


def _gaes_charge_scope_key(row: dict[str, Any]) -> str | None:
    code = str(row.get("perimeter_variant_code") or "").strip()
    if code:
        nt_group = _nt_group_for_variant_code(code)
        if nt_group in ("with_nt", "without_nt"):
            return nt_group
        return None
    if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
        if row.get("pd_ec_nt_extra_row"):
            return "with_nt"
        if row.get("pd_ec_nt_without_row"):
            return "without_nt"
    return None


def _gaes_charge_entity_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (*_summary_row_entity_key(row), _gaes_charge_scope_key(row))


def _gaes_charge_entity_key_aliases(row: dict[str, Any]) -> tuple[tuple[Any, ...], ...]:
    key = _gaes_charge_entity_key(row)
    label = str(row.get("entity_label") or "").strip()
    base_label, _ = _strip_summary_table_variant_suffixes_from_label(label)
    scope = _gaes_charge_scope_key(row)
    aliases = {key}
    if (
        row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
        and row.get("entity_kind") == "group"
        and scope in ("with_nt", "without_nt")
    ):
        aliases.add(
            (
                row.get("demand_model_name"),
                row.get("parent_fk_column"),
                row.get("parent_id"),
                "perimeter_variant",
                base_label,
                scope,
            )
        )

    if base_label.casefold() not in {
        EES_RUSSIA_AGGREGATE_NAME.casefold(),
        EES_UNIFIED_REF_NAME.casefold(),
    }:
        return tuple(aliases)

    aliases.update(
        {
            (
            EesRussiaEnergyConsumptionParameter.__name__,
            None,
            None,
            ENTITY_KIND_EES_RUSSIA,
            EES_RUSSIA_AGGREGATE_NAME,
            scope,
        ),
        (
            EesRussiaEnergyConsumptionParameter.__name__,
            None,
            None,
            ENTITY_KIND_EES_RUSSIA,
            EES_UNIFIED_REF_NAME,
            scope,
        ),
        (
            EesRussiaEnergyConsumptionParameter.__name__,
            None,
            None,
            "perimeter_variant",
            EES_RUSSIA_AGGREGATE_NAME,
            scope,
        ),
        (
            EesRussiaEnergyConsumptionParameter.__name__,
            None,
            None,
            "perimeter_variant",
            EES_UNIFIED_REF_NAME,
            scope,
        ),
        }
    )
    return tuple(aliases)


def _with_gaes_variant_code(code: str | None) -> str | None:
    s = str(code or "").strip()
    if not s or "without_gaes" not in s:
        return None
    return s.replace("without_gaes", "with_gaes", 1)


def _raw_year_values_from_summary_row(
    row: dict[str, Any],
    years: list[int],
    *,
    ignore_perimeter_variant_year_bounds: bool = False,
) -> dict[int, Decimal | None]:
    values = row.get("year_values") or []
    tooltips = row.get("year_numeric_tooltips") or []
    out: dict[int, Decimal | None] = {}
    for index, year in enumerate(years):
        if (
            not ignore_perimeter_variant_year_bounds
            and not _year_applies_to_summary_row_perimeter_variant(row, int(year))
        ):
            out[int(year)] = None
            continue
        raw: Any = "—"
        if index < len(tooltips) and tooltips[index]:
            raw = tooltips[index]
        elif index < len(values):
            raw = values[index]
        out[int(year)] = _decimal_or_none(raw)
    return out


def _write_numeric_year_values_to_summary_row(
    row: dict[str, Any],
    years: list[int],
    raw_by_year: dict[int, Decimal | None],
    *,
    parameter_key: str,
    rounding_digits: int,
) -> None:
    values: list[str] = []
    tooltips: list[str] = []
    for year in years:
        raw = raw_by_year.get(int(year))
        if raw is None:
            values.append("—")
            tooltips.append("")
            continue
        tooltips.append(_format_full_numeric_tooltip(raw))
        if parameter_key in (
            ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
            ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
        ):
            values.append(_format_yoy_pct_for_display(raw))
        else:
            values.append(_format_summary_parameter_value(raw, parameter_key, rounding_digits))
    row["year_values"] = values
    row["year_numeric_tooltips"] = tooltips


def _collect_gaes_charge_totals_by_entity(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> dict[tuple[Any, ...], dict[int, Decimal | None]]:
    totals: dict[tuple[Any, ...], dict[int, Decimal | None]] = {}
    station_sums: dict[tuple[Any, ...], dict[int, Decimal]] = {}
    for row in summary_rows:
        if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
            continue
        entity_keys = _gaes_charge_entity_key_aliases(row)
        year_values = _raw_year_values_from_summary_row(row, years)
        if row.get("gaes_charge_row_station_name") == "всего":
            for entity_key in entity_keys:
                totals[entity_key] = year_values
            continue
        for entity_key in entity_keys:
            bucket = station_sums.setdefault(entity_key, {})
            for year, value in year_values.items():
                if value is None:
                    continue
                bucket[year] = bucket.get(year, Decimal(0)) + value
    out: dict[tuple[Any, ...], dict[int, Decimal | None]] = {}
    entity_keys = set(totals) | set(station_sums)
    for entity_key in entity_keys:
        if entity_key in totals:
            out[entity_key] = totals[entity_key]
        else:
            out[entity_key] = dict(station_sums.get(entity_key, {}))
    return out


def _gaes_without_charge_formula_kind_for_row(row: dict[str, Any]) -> str | None:
    code = str(row.get("perimeter_variant_code") or "")
    if "without_gaes" not in code:
        return None
    dm = str(row.get("demand_model_name") or "")
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    if dm == EnergyZoneEnergyConsumptionParameter.__name__:
        return "ez"
    if dm == EesRussiaEnergyConsumptionParameter.__name__:
        return (
            "ees_russia_with_nt_gaes_diff"
            if code.startswith("with_nt")
            else "ees_russia_without_nt_gaes_diff"
        )
    if dm == EnergySystemTypeEnergyConsumptionParameter.__name__:
        if label_cf == EES_UNIFIED_REF_NAME.casefold():
            return (
                "ees_russia_with_nt_gaes_diff"
                if code.startswith("with_nt")
                else "ees_russia_without_nt_gaes_diff"
            )
        return "ees_russia_ez"
    if dm == SynchronousAreaEnergyConsumptionParameter.__name__:
        if _summary_row_base_label_cf(row).startswith(_FIRST_SYNC_AREA_BASE_LABEL_CF):
            if code.startswith("with_nt"):
                if "without_kaliningrad_es" in code:
                    return "first_sa_with_nt_without_kaliningrad_gaes_diff"
                return "first_sa_with_nt_gaes_diff"
            if "with_kaliningrad_es" in code:
                return "first_sa_without_nt_with_kaliningrad_gaes_diff"
            if "without_kaliningrad_es" in code:
                return "first_sa_without_nt_without_kaliningrad_gaes_diff"
        return "synchronous_area"
    if dm == FederalDistrictEnergyConsumptionParameter.__name__:
        return "fo"
    if dm == UnionEnergySystemEnergyConsumptionParameter.__name__:
        return "oes"
    return "generic"


def _recompute_growth_rows_from_base_series(
    block_rows: list[dict[str, Any]],
    years: list[int],
    *,
    base_parameter_key: str,
    abs_parameter_key: str | None,
    yoy_parameter_key: str | None,
    rounding_digits: int,
) -> None:
    base_by_year: dict[int, Decimal | None] = {}
    for row in block_rows:
        if row.get("parameter_key") == base_parameter_key:
            base_by_year = _raw_year_values_from_summary_row(row, years)
            break
    if abs_parameter_key:
        abs_row = next(
            (r for r in block_rows if r.get("parameter_key") == abs_parameter_key),
            None,
        )
        if abs_row is not None:
            abs_values: dict[int, Decimal | None] = {}
            for index, year in enumerate(years):
                if index == 0:
                    abs_values[int(year)] = None
                    continue
                abs_values[int(year)] = _abs_diff_value(
                    base_by_year.get(int(year)),
                    base_by_year.get(int(years[index - 1])),
                )
            _write_numeric_year_values_to_summary_row(
                abs_row,
                years,
                abs_values,
                parameter_key=abs_parameter_key,
                rounding_digits=rounding_digits,
            )
    if yoy_parameter_key:
        yoy_row = next(
            (r for r in block_rows if r.get("parameter_key") == yoy_parameter_key),
            None,
        )
        if yoy_row is not None:
            yoy_values: dict[int, Decimal | None] = {}
            for index, year in enumerate(years):
                if index == 0:
                    yoy_values[int(year)] = None
                    continue
                yoy_values[int(year)] = _yoy_growth_pct_value(
                    base_by_year.get(int(year)),
                    base_by_year.get(int(years[index - 1])),
                )
            _write_numeric_year_values_to_summary_row(
                yoy_row,
                years,
                yoy_values,
                parameter_key=yoy_parameter_key,
                rounding_digits=rounding_digits,
            )


def _summary_row_is_south_ues_without_nt_without_gaes_db_row(
    row: dict[str, Any],
) -> bool:
    """ОЭС Юга «без НТ без заряда ГАЭС»: при наличии чисел в БД формулу не пересчитываем."""
    if (
        str(row.get("demand_model_name") or "")
        != UnionEnergySystemEnergyConsumptionParameter.__name__
    ):
        return False
    if str(row.get("perimeter_variant_code") or "") != CODE_WITHOUT_NT_WITHOUT_GAES:
        return False
    return _summary_row_base_label_cf(row) == SOUTH_UES_NAME_CF


def _south_ues_without_nt_without_gaes_has_db_values(
    row: dict[str, Any],
    years: list[int],
    row_by_variant_param: dict[tuple[Any, ...], dict[str, Any]],
) -> bool:
    """True, если в блоке уже есть самостоятельные (не скопированные) значения из БД.

    Ранний вызов формулы (до разметки строк заряда по НТ) может заполнить блок
    значениями «с зарядом ГАЭС» без вычитания — такие значения не считаем БД.
    """
    if not _summary_row_is_south_ues_without_nt_without_gaes_db_row(row):
        return False
    entity_key = _gaes_charge_entity_key(row)
    ec_row = row_by_variant_param.get(
        (
            *entity_key,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            "energy_consumption_mln_kvt_ch",
        )
    )
    if ec_row is None:
        return True
    ec_values = _raw_year_values_from_summary_row(ec_row, years)
    if not _year_values_have_any_numeric(ec_values):
        return False
    with_gaes_code = _with_gaes_variant_code(CODE_WITHOUT_NT_WITHOUT_GAES)
    if not with_gaes_code:
        return True
    source_row = row_by_variant_param.get(
        (*entity_key, with_gaes_code, "energy_consumption_mln_kvt_ch")
    )
    if source_row is None:
        return True
    source_values = _raw_year_values_from_summary_row(source_row, years)
    if ec_values == source_values:
        return False
    return True


def apply_gaes_without_charge_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    if not summary_rows or not years:
        return

    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    row_by_variant_param = {
        (
            *_gaes_charge_entity_key(row),
            row.get("perimeter_variant_code"),
            row.get("parameter_key"),
        ): row
        for row in summary_rows
    }

    for row in summary_rows:
        code = str(row.get("perimeter_variant_code") or "")
        if "with_gaes" in code:
            row["pd_ec_gaes_with_charge_db_block"] = True

    processed_blocks: set[tuple[Any, ...]] = set()
    for row in summary_rows:
        code = str(row.get("perimeter_variant_code") or "")
        if "without_gaes" not in code:
            continue
        if _south_ues_without_nt_without_gaes_has_db_values(
            row, years, row_by_variant_param
        ):
            continue
        block_key = (
            *_summary_row_entity_key(row),
            code,
        )
        if block_key in processed_blocks:
            continue
        processed_blocks.add(block_key)

        with_gaes_code = _with_gaes_variant_code(code)
        if not with_gaes_code:
            continue
        entity_key = _gaes_charge_entity_key(row)
        gaes_by_year = gaes_totals.get(entity_key, {})
        formula_kind = _gaes_without_charge_formula_kind_for_row(row)
        block_rows = [
            item
            for item in summary_rows
            if _gaes_charge_entity_key(item) == entity_key
            and str(item.get("perimeter_variant_code") or "") == code
        ]
        for block_row in block_rows:
            block_row["pd_ec_formula_derived_row"] = True
            block_row["gaes_without_charge_formula_kind"] = formula_kind

        for parameter_key in _GAES_WITHOUT_CHARGE_FORMULA_PARAM_KEYS:
            source_row = row_by_variant_param.get(
                (*entity_key, with_gaes_code, parameter_key)
            )
            target_row = row_by_variant_param.get((*entity_key, code, parameter_key))
            if source_row is None or target_row is None:
                continue
            source_by_year = _raw_year_values_from_summary_row(source_row, years)
            adjusted: dict[int, Decimal | None] = {}
            for year in years:
                base_value = source_by_year.get(int(year))
                if base_value is None:
                    adjusted[int(year)] = None
                    continue
                gaes_value = gaes_by_year.get(int(year)) or Decimal(0)
                adjusted[int(year)] = base_value - gaes_value
            _write_numeric_year_values_to_summary_row(
                target_row,
                years,
                adjusted,
                parameter_key=parameter_key,
                rounding_digits=rounding_digits,
            )

        _recompute_growth_rows_from_base_series(
            block_rows,
            years,
            base_parameter_key="energy_consumption_mln_kvt_ch",
            abs_parameter_key=None,
            yoy_parameter_key=ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )
        _recompute_growth_rows_from_base_series(
            block_rows,
            years,
            base_parameter_key="energy_consumption_sipr_mln_kvt_ch",
            abs_parameter_key=ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            yoy_parameter_key=ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            rounding_digits=rounding_digits,
        )


def _flatten_entities(
    entities: list[SummaryEntity],
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
    hidden_demand_model_names: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for entity in entities:
        flattened.extend(
            _flatten_entity(
                entity,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
                hidden_demand_model_names=hidden_demand_model_names,
            )
        )
    apply_gaes_without_charge_formula_to_summary_rows(
        flattened,
        years,
        rounding_digits,
    )
    return flattened


def _slice_row_ids(demand_rows: list[Any]) -> dict[Any, int]:
    """Номер года → id строки параметров."""
    out: dict[Any, int] = {}
    for row in demand_rows:
        y = getattr(row, "year_number", None)
        if y is None:
            continue
        rid = getattr(row, "id", None)
        if rid is not None:
            out[int(y)] = int(rid)
    return out


def _flatten_entity(
    entity: SummaryEntity,
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
    hidden_demand_model_names: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    entity_rows: list[dict[str, Any]] = []
    if entity.demand_model_name in hidden_demand_model_names:
        for child in entity.children:
            entity_rows.extend(
                _flatten_entity(
                    child,
                    years,
                    rounding_digits,
                    avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
                    hidden_demand_model_names=hidden_demand_model_names,
                )
            )
        return entity_rows
    parameters = entity.parameters
    gaes_rows = (
        []
        if entity.perimeter_variant_code is not None
        else _gaes_charge_rows_for_entity(entity, years, rounding_digits)
    )
    parameter_maps, tooltip_maps = _build_parameter_maps(
        entity.demand_rows,
        parameters,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    slice_ids = _slice_row_ids(entity.demand_rows)
    dm_name = entity.demand_model_name
    ues_id_flat = getattr(entity, "id_union_energy_system", None)
    if (
        ues_id_flat is None
        and getattr(entity, "parent_fk_column", None) == "id_union_energy_system"
        and getattr(entity, "parent_id", None) is not None
    ):
        ues_id_flat = entity.parent_id

    anchor_y = years[0] if years else None
    note_row = None
    if anchor_y is not None:
        for r in entity.demand_rows:
            if getattr(r, "year_number", None) == anchor_y:
                note_row = r
                break
    entity_note_rid = getattr(note_row, "id", None) if note_row is not None else None
    raw_note = getattr(note_row, "note", None) if note_row is not None else None
    entity_note_text = "" if raw_note in (None, "") else str(raw_note)

    pe_ctx = perimeter_entity_context_for_model(
        dm_name or "",
        parent_fk_column=entity.parent_fk_column,
        parent_id=entity.parent_id,
    )

    entity_rowspan = len(parameters)
    for index, (parameter_key, parameter_label) in enumerate(parameters):
        values = parameter_maps.get(parameter_key, {})
        tt = tooltip_maps.get(parameter_key, {})
        year_row_ids = [slice_ids.get(year) for year in years]
        row_data: dict[str, Any] = {
            "entity_label": entity.label,
            "entity_rowspan": entity_rowspan,
            "entity_depth": entity.depth,
            "entity_kind": entity.entity_kind,
            "show_entity_cell": index == 0,
            "parameter_key": parameter_key,
            "parameter_label": parameter_label,
            "demand_model_name": dm_name,
            "parent_fk_column": entity.parent_fk_column,
            "parent_id": entity.parent_id,
            "hist_row_id": None,
            "year_row_ids": year_row_ids,
            "hist_value": "—",
            "year_values": [values.get(year, "—") for year in years],
            "hist_numeric_tooltip": "",
            "year_numeric_tooltips": [tt.get(year, "") for year in years],
            "id_union_energy_system": ues_id_flat,
            "id_regional_energy_system": getattr(entity, "id_regional_energy_system", None),
            "entity_note_text": entity_note_text,
            "entity_note_row_id": entity_note_rid,
            "show_entity_note_cell": index == 0,
            "perimeter_variant_code": entity.perimeter_variant_code,
        }
        if pe_ctx is not None:
            row_data["pd_ec_perimeter_entity_kind"] = pe_ctx[0]
            row_data["pd_ec_perimeter_entity_name"] = pe_ctx[1]
        entity_rows.append(row_data)
        if entity.is_decentralized_zone_energy_unit:
            entity_rows[-1]["pd_ec_decentralized_zone_mark"] = True

    entity_rows.extend(gaes_rows)

    for child in entity.children:
        entity_rows.extend(
            _flatten_entity(
                child,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
                hidden_demand_model_names=hidden_demand_model_names,
            )
        )
    return entity_rows


def _format_full_numeric_tooltip(value: Any) -> str:
    """Полное отображение числа для title (как format_decimal_trim(0) на странице energy_consumption_edit)."""
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=0)
    return apply_thousand_grouping_to_display(s) if s else ""


def _build_parameter_maps(
    demand_rows: list[Any],
    parameters: tuple[tuple[str, str], ...],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> tuple[dict[str, dict[Any, str]], dict[str, dict[Any, str]]]:
    del avg_temp_uses_global_rounding
    result: dict[str, dict[Any, str]] = {param_key: {} for param_key, _ in parameters}
    param_keys = {pk for pk, _ in parameters}
    tooltip_keys = param_keys & _NUMERIC_ROUNDING_TOOLTIP_KEYS
    tooltips: dict[str, dict[Any, str]] = {pk: {} for pk in tooltip_keys}

    raw_ec: dict[int, Any] = {}
    raw_sipr: dict[int, Any] = {}
    for row in demand_rows:
        y = getattr(row, "year_number", None)
        if y is None:
            continue
        sk = int(y)
        raw_ec[sk] = getattr(row, "energy_consumption_mln_kvt_ch", None)
        raw_sipr[sk] = getattr(row, "energy_consumption_sipr_mln_kvt_ch", None)

        if "energy_consumption_mln_kvt_ch" in result:
            result["energy_consumption_mln_kvt_ch"][sk] = _format_summary_parameter_value(
                raw_ec[sk],
                "energy_consumption_mln_kvt_ch",
                rounding_digits,
            )
        if "energy_consumption_mln_kvt_ch" in tooltips:
            tooltips["energy_consumption_mln_kvt_ch"][sk] = _format_full_numeric_tooltip(raw_ec[sk])

        if "energy_consumption_sipr_mln_kvt_ch" in result:
            effective_sipr = _effective_energy_consumption_sipr_raw(
                raw_sipr.get(sk),
                raw_ec.get(sk),
            )
            result["energy_consumption_sipr_mln_kvt_ch"][sk] = _format_summary_parameter_value(
                effective_sipr,
                "energy_consumption_sipr_mln_kvt_ch",
                rounding_digits,
            )

    effective_sipr = _effective_sipr_values_by_year(raw_ec, raw_sipr)

    if "energy_consumption_sipr_mln_kvt_ch" in result:
        sipr_hover: dict[Any, str] = {}
        for sk, value in effective_sipr.items():
            sipr_hover[sk] = _format_full_numeric_tooltip(value)
        tooltips["energy_consumption_sipr_mln_kvt_ch"] = sipr_hover

    if ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY in result:
        for sk, curr in effective_sipr.items():
            diff_v = _abs_diff_value(curr, effective_sipr.get(sk - 1))
            result[ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY][sk] = _format_numeric(
                diff_v, rounding_digits
            )
            if ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY in tooltips:
                tooltips[ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY][sk] = _format_full_numeric_tooltip(
                    diff_v
                )

    if ENERGY_CONSUMPTION_YOY_PARAMETER_KEY in result:
        for sk, curr in raw_ec.items():
            pct = _yoy_growth_pct_value(curr, raw_ec.get(sk - 1))
            disp = _format_yoy_pct_for_display(pct)
            result[ENERGY_CONSUMPTION_YOY_PARAMETER_KEY][sk] = disp
            if ENERGY_CONSUMPTION_YOY_PARAMETER_KEY in tooltips:
                tooltips[ENERGY_CONSUMPTION_YOY_PARAMETER_KEY][sk] = (
                    disp if pct is not None else ""
                )

    if ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY in result:
        for sk, curr in effective_sipr.items():
            pct_s = _yoy_growth_pct_value(curr, effective_sipr.get(sk - 1))
            disp_s = _format_yoy_pct_for_display(pct_s)
            result[ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY][sk] = disp_s
            if ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY in tooltips:
                tooltips[ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY][sk] = (
                    disp_s if pct_s is not None else ""
                )

    return result, tooltips


def _format_numeric(value: Any, digits: int) -> str:
    shown = format_decimal_trim_for_display(value, digits=digits)
    return _dash(apply_thousand_grouping_to_display(shown) if shown else shown)


def _format_summary_parameter_value(
    value: Any,
    parameter_key: str,
    rounding_digits: int,
) -> str:
    digits = _display_digits_for_summary_parameter(parameter_key, rounding_digits)
    return _format_numeric(value, digits)


def _format_yoy_pct_for_display(value: Any) -> str:
    """Годовой темп прироста: ровно два знака после запятой (например 2,30)."""
    if value is None:
        return "—"
    s = format_decimal_for_display(value, digits=_ENERGY_CONSUMPTION_YOY_DISPLAY_DECIMALS)
    return apply_thousand_grouping_to_display(s) if s else "—"


def _dash(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def _standalone_entity(
    label: str,
    demand_model: Any,
    parameters: tuple[tuple[str, str], ...],
    *,
    entity_kind: str = "default",
    perimeter_variant_code: str | None = None,
) -> SummaryEntity:
    return SummaryEntity(
        label=label,
        depth=0,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(
            demand_model,
            None,
            None,
            perimeter_variant_code=perimeter_variant_code,
        ),
        entity_kind=entity_kind,
        demand_model_name=demand_model.__name__,
        parent_fk_column=None,
        parent_id=None,
        perimeter_variant_code=perimeter_variant_code,
    )


def _build_ues_entities_filtered(
    ues_predicate: Callable[[UnionEnergySystem], bool],
    *,
    always_show_subject_row_under_res: bool = False,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    query = UnionEnergySystem.query.options(
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.regional_districts
        ).selectinload(
            RegionalDistrict.energy_units
        ),
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.energy_units
        ),
        selectinload(UnionEnergySystem.energy_system_type),
    )
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    query = query.order_by(
        UnionEnergySystem.display_order.asc().nullslast(),
        UnionEnergySystem.name.asc(),
        UnionEnergySystem.id.asc(),
    )

    entities: list[SummaryEntity] = []
    for ues in query.all():
        if not _is_valid_named_item(ues):
            continue
        if not ues_predicate(ues):
            continue

        child_entities = [
            _build_regional_energy_system_entity(
                res,
                ues_id=ues.id,
                always_show_subject_row_under_res=always_show_subject_row_under_res,
            )
            for res in sorted(ues.regional_energy_systems, key=_sort_by_name)
            if _is_valid_named_item(res)
        ]
        base = SummaryEntity(
            label=ues.name,
            depth=1,
            parameters=PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=dps.get_demand_rows(
                UnionEnergySystemEnergyConsumptionParameter,
                "id_union_energy_system",
                ues.id,
            ),
            entity_kind="group",
            children=child_entities,
            demand_model_name=UnionEnergySystemEnergyConsumptionParameter.__name__,
            parent_fk_column="id_union_energy_system",
            parent_id=ues.id,
            id_union_energy_system=ues.id,
        )
        entities.extend(
            _expand_summary_entity_perimeter_variants(
                base,
                binding_entity_kind="union_energy_system",
                binding_entity_name=ues.name,
                expand=expand_entity_perimeter_variants,
                tree_years=tree_years,
            )
        )
    return entities


def _build_regional_energy_system_entity(
    res,
    *,
    ues_id: int,
    always_show_subject_row_under_res: bool = False,
    perimeter_variant_code: str | None = None,
) -> SummaryEntity:
    regional_districts = [
        regional_district
        for regional_district in sorted(res.regional_districts, key=_sort_by_name)
        if _is_valid_named_item(regional_district)
    ]
    # Один субъект в РЭС: строки субъекта в дереве не дублируем (сразу ЭУ), но id субъекта нужен
    # для фильтров сводки ds_rd и для согласованного матчинга листьев при ds_res+ds_rd.
    single_rd_id: int | None = regional_districts[0].id if len(regional_districts) == 1 else None

    subject_children: list[SummaryEntity]
    if len(regional_districts) > 1:
        # «Совмещенный на ЭС» — пока в РЭС несколько субъектов (эта ветка — уже ≥2 после фильтра имени).
        # Сводка по ОЭС: для субъектов РФ не показываем «на ФО» и «на централизованную зону»
        subject_children = [
            _build_regional_district_entity(
                regional_district,
                depth=3,
                energy_units=_energy_units_for_federal_district_subject(
                    regional_district.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                ues_id=ues_id,
                res_id=res.id,
                perimeter_variant_code=perimeter_variant_code,
            )
            for regional_district in regional_districts
        ]
    elif (
        len(regional_districts) == 1
        and always_show_subject_row_under_res
    ):
        rd0 = regional_districts[0]
        subject_children = [
            _build_regional_district_entity(
                rd0,
                depth=3,
                energy_units=_energy_units_for_federal_district_subject(
                    rd0.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                ues_id=ues_id,
                res_id=res.id,
                perimeter_variant_code=perimeter_variant_code,
            )
        ]
    else:
        if len(regional_districts) == 1:
            rd0 = regional_districts[0]
            energy_units = _energy_units_for_federal_district_subject(
                rd0.energy_units,
                res.id,
            )
            if not energy_units:
                energy_units = _filter_valid_items(res.energy_units)
        else:
            energy_units = _filter_valid_items(res.energy_units)
        subject_children = _build_energy_unit_entities(
            energy_units,
            depth=3,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res.id,
            id_regional_district=single_rd_id,
            perimeter_variant_code=perimeter_variant_code,
        )

    return SummaryEntity(
        label=res.name,
        depth=2,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=dps.get_demand_rows_with_single_variant_fallback(
            RegionalEnergySystemEnergyConsumptionParameter,
            "id_regional_energy_system",
            res.id,
            display_perimeter_variant_code=perimeter_variant_code,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res.id,
        id_regional_district=single_rd_id,
        perimeter_variant_code=perimeter_variant_code,
    )


def _build_regional_energy_system_entity_for_energy_zone(
    res: RegionalEnergySystem,
    regional_districts_in_zone: list[RegionalDistrict],
    *,
    energy_zone_id: int,
) -> SummaryEntity:
    """РЭС внутри энергозоны: при одном субъекте в зоне — ЭС под субъектом; при нескольких — только ЭС без строк субъектов."""
    regional_districts = sorted(
        [rd for rd in regional_districts_in_zone if _is_valid_named_item(rd)],
        key=_sort_by_name,
    )
    subject_children: list[SummaryEntity]
    if len(regional_districts) > 1:
        # Сводка по энергозонам: при нескольких субъектах в РЭС не показываем строки по субъектам —
        # только энергоузлы РЭС в зоне (как при одном субъекте), без промежуточного уровня «субъект».
        combined_eus: list[EnergyUnit] = []
        seen_eu_ids: set[int] = set()
        for regional_district in regional_districts:
            for eu in _filter_energy_units_for_res(
                regional_district.energy_units,
                res.id,
            ):
                euid = getattr(eu, "id", None)
                if euid is None or euid in seen_eu_ids:
                    continue
                seen_eu_ids.add(euid)
                combined_eus.append(eu)
        subject_children = _build_energy_unit_entities(
            combined_eus,
            depth=2,
            id_energy_zone=energy_zone_id,
            id_regional_energy_system=res.id,
        )
    elif len(regional_districts) == 1:
        subject_children = _build_energy_unit_entities(
            _filter_energy_units_for_res(regional_districts[0].energy_units, res.id),
            depth=2,
            id_energy_zone=energy_zone_id,
            id_regional_energy_system=res.id,
            id_regional_district=regional_districts[0].id,
        )
    else:
        subject_children = []

    return SummaryEntity(
        label=res.name,
        depth=1,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemEnergyConsumptionParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_energy_zone=energy_zone_id,
        id_regional_energy_system=res.id,
    )


def _build_energy_zone_entities() -> list[SummaryEntity]:
    ez_query = EnergyZone.query.options(selectinload(EnergyZone.regional_districts))
    ez_query = dps.filter_parents_by_version(ez_query, EnergyZone)
    zones = sorted(
        [z for z in ez_query.all() if _is_valid_named_item(z)],
        key=_energy_zone_number_sort_key,
    )

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts).selectinload(
            RegionalDistrict.energy_units
        ),
        selectinload(RegionalEnergySystem.energy_units),
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [r for r in res_query.all() if _is_valid_named_item(r)]

    entities: list[SummaryEntity] = []
    for ez in zones:
        zone_rd_ids = {rd.id for rd in ez.regional_districts}
        res_children: list[SummaryEntity] = []
        for res in sorted(all_res, key=_sort_by_name):
            if _is_tites_regional_energy_system(res):
                continue
            rds_in_zone = [rd for rd in res.regional_districts if rd.id in zone_rd_ids]
            if not rds_in_zone:
                continue
            res_children.append(
                _build_regional_energy_system_entity_for_energy_zone(
                    res, rds_in_zone, energy_zone_id=ez.id
                )
            )
        entities.append(
            SummaryEntity(
                label=f"{ez.number} — {ez.name}",
                depth=0,
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=dps.get_demand_rows(
                    EnergyZoneEnergyConsumptionParameter,
                    "id_energy_zone",
                    ez.id,
                ),
                entity_kind="group",
                children=res_children,
                demand_model_name=EnergyZoneEnergyConsumptionParameter.__name__,
                parent_fk_column="id_energy_zone",
                parent_id=ez.id,
                id_energy_zone=ez.id,
            )
        )
    return entities


def _build_synchronous_area_entities(
    *,
    depth: int = 0,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Строки сводки по ОЭС: одна сущность на каждую синхронную зону (как энергозона по показателям).

    В сводке по ОЭС вложены под «ЕЭС России (без НТ)» — depth=1, чтобы шли после агрегата и перед ОЭС.
    """
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    query = query.order_by(
        SynchronousArea.display_order.asc().nullslast(),
        SynchronousArea.name.asc(),
        SynchronousArea.id.asc(),
    )
    entities: list[SummaryEntity] = []
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        base = SummaryEntity(
            label=_synchronous_area_display_label(sa),
            depth=depth,
            parameters=PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=dps.get_demand_rows(
                SynchronousAreaEnergyConsumptionParameter,
                "id_synchronous_area",
                sa.id,
            ),
            entity_kind="synchronous_area",
            demand_model_name=SynchronousAreaEnergyConsumptionParameter.__name__,
            parent_fk_column="id_synchronous_area",
            parent_id=sa.id,
            id_synchronous_area=sa.id,
        )
        entities.extend(
            _expand_summary_entity_perimeter_variants(
                base,
                binding_entity_kind="synchronous_area",
                binding_entity_name=sa.name,
                expand=expand_entity_perimeter_variants,
                tree_years=tree_years,
            )
        )
    return entities


def _build_energy_system_type_entities(
    name: str,
    ues_predicate: Callable[[UnionEnergySystem], bool],
    *,
    depth: int = 0,
    always_show_subject_row_under_res: bool = False,
    expand_entity_perimeter_variants: bool = False,
    ees_unified_use_ees_russia_gaes_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    energy_system_type = _get_energy_system_type_by_name(name)
    children = [
        _shift_summary_entity_depth(child, depth)
        for child in _build_ues_entities_filtered(
            ues_predicate,
            always_show_subject_row_under_res=always_show_subject_row_under_res,
            expand_entity_perimeter_variants=expand_entity_perimeter_variants,
            tree_years=tree_years,
        )
    ]
    if energy_system_type is None and not children:
        return []

    if energy_system_type is None:
        base = SummaryEntity(
            label=name,
            depth=depth,
            parameters=PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            entity_kind="group-root",
            children=children,
            demand_model_name=None,
            parent_fk_column=None,
            parent_id=None,
        )
        return [base]

    base = SummaryEntity(
        label=getattr(energy_system_type, "name", None) or name,
        depth=depth,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=dps.get_demand_rows(
            EnergySystemTypeEnergyConsumptionParameter,
            "id_energy_system_type",
            energy_system_type.id,
        ),
        entity_kind="group-root",
        children=children,
        demand_model_name=EnergySystemTypeEnergyConsumptionParameter.__name__,
        parent_fk_column="id_energy_system_type",
        parent_id=energy_system_type.id,
    )
    expanded = _expand_summary_entity_perimeter_variants(
        base,
        binding_entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        binding_entity_name=getattr(energy_system_type, "name", None) or name,
        expand=expand_entity_perimeter_variants,
        tree_years=tree_years,
        use_ees_russia_gaes_variants=(
            ees_unified_use_ees_russia_gaes_variants
            and str(name or "").casefold() == EES_UNIFIED_REF_NAME.casefold()
        ),
    )
    return expanded or [base]


def _build_tites_entity() -> SummaryEntity | None:
    entities = _build_energy_system_type_entities("ТИТЭС", _is_tites_branch)
    return entities[0] if entities else None


def _build_regional_district_entity(
    regional_district: RegionalDistrict,
    *,
    depth: int,
    energy_units: list[EnergyUnit] | None = None,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_CONSUMPTION,
    ues_id: int | None = None,
    res_id: int | None = None,
    id_federal_district: int | None = None,
    perimeter_variant_code: str | None = None,
) -> SummaryEntity:
    return SummaryEntity(
        label=regional_district.name,
        depth=depth,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(
            RegionalDistrictEnergyConsumptionParameter,
            "id_regional_district",
            regional_district.id,
            perimeter_variant_code=perimeter_variant_code,
        ),
        entity_kind="child",
        children=_build_energy_unit_entities(
            energy_units if energy_units is not None else _filter_valid_items(regional_district.energy_units),
            depth=depth + 1,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res_id,
            id_regional_district=regional_district.id,
            perimeter_variant_code=perimeter_variant_code,
        ),
        demand_model_name=RegionalDistrictEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_district",
        parent_id=regional_district.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res_id,
        id_regional_district=regional_district.id,
        id_federal_district=id_federal_district,
        perimeter_variant_code=perimeter_variant_code,
    )


def _build_energy_unit_entities(
    energy_units: list[EnergyUnit],
    *,
    depth: int,
    id_union_energy_system: int | None = None,
    id_regional_energy_system: int | None = None,
    id_regional_district: int | None = None,
    id_energy_zone: int | None = None,
    perimeter_variant_code: str | None = None,
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for energy_unit in energy_units:
        if not _is_valid_named_item(energy_unit):
            continue
        ues = id_union_energy_system
        if ues is None:
            res_obj = getattr(energy_unit, "regional_energy_system", None)
            ues_obj = getattr(res_obj, "union_energy_system", None) if res_obj else None
            ues = getattr(ues_obj, "id", None)
        res_id = id_regional_energy_system or getattr(
            energy_unit, "id_regional_energy_system", None
        )
        rd_id = id_regional_district or getattr(energy_unit, "id_regional_district", None)
        pvc = perimeter_variant_code or _energy_unit_summary_perimeter_variant_code(
            energy_unit
        )
        out.append(
            SummaryEntity(
                label=energy_unit.name,
                depth=depth,
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=dps.get_demand_rows(
                    EnergyUnitEnergyConsumptionParameter,
                    "id_energy_unit",
                    energy_unit.id,
                    perimeter_variant_code=pvc,
                ),
                entity_kind="child",
                demand_model_name=EnergyUnitEnergyConsumptionParameter.__name__,
                parent_fk_column="id_energy_unit",
                parent_id=energy_unit.id,
                id_union_energy_system=ues,
                id_regional_energy_system=res_id,
                id_regional_district=rd_id,
                id_energy_unit=energy_unit.id,
                id_energy_zone=id_energy_zone,
                perimeter_variant_code=pvc,
                is_decentralized_zone_energy_unit=_energy_unit_belongs_to_placeholder_res(
                    energy_unit
                ),
            )
        )
    return out


def _regional_energy_systems_for_federal_district(
    federal_district: FederalDistrict,
    all_res: list[RegionalEnergySystem],
) -> list[RegionalEnergySystem]:
    fd_rd_ids = {rd.id for rd in federal_district.regional_districts}
    return sorted(
        [
            res
            for res in all_res
            if any(rd.id in fd_rd_ids for rd in res.regional_districts)
        ],
        key=_sort_by_name,
    )


def _regional_districts_for_res_in_federal_district(
    res: RegionalEnergySystem,
    fd_rd_ids: set[int],
) -> list[RegionalDistrict]:
    return sorted(
        [
            rd
            for rd in res.regional_districts
            if rd.id in fd_rd_ids and _is_valid_named_item(rd)
        ],
        key=_sort_by_name,
    )


def _build_federal_district_regional_district_entity(
    regional_district: RegionalDistrict,
    *,
    federal_district_id: int,
    res_id: int,
) -> SummaryEntity:
    return _build_regional_district_entity(
        regional_district,
        depth=2,
        energy_units=_energy_units_for_federal_district_subject(
            regional_district.energy_units,
            res_id,
        ),
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        res_id=res_id,
        id_federal_district=federal_district_id,
    )


def _build_federal_district_res_entity(
    res: RegionalEnergySystem,
    *,
    federal_district_id: int,
    fd_rd_ids: set[int],
) -> SummaryEntity:
    regional_districts_in_fd = _regional_districts_for_res_in_federal_district(
        res,
        fd_rd_ids,
    )
    single_rd_id = (
        regional_districts_in_fd[0].id if len(regional_districts_in_fd) == 1 else None
    )
    subject_children: list[SummaryEntity] = []
    if len(regional_districts_in_fd) > 1:
        subject_children = [
            _build_federal_district_regional_district_entity(
                regional_district,
                federal_district_id=federal_district_id,
                res_id=res.id,
            )
            for regional_district in regional_districts_in_fd
        ]
    elif len(regional_districts_in_fd) == 1:
        rd0 = regional_districts_in_fd[0]
        eus = _energy_units_for_federal_district_subject(rd0.energy_units, res.id)
        if not eus:
            eus = _filter_valid_items(res.energy_units)
        subject_children = _build_energy_unit_entities(
            eus,
            depth=2,
            id_regional_energy_system=res.id,
            id_regional_district=rd0.id,
        )
    return SummaryEntity(
        label=res.name,
        depth=1,
        parameters=PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemEnergyConsumptionParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_federal_district=federal_district_id,
        id_regional_energy_system=res.id,
        id_regional_district=single_rd_id,
    )


def _build_federal_district_entities(
    *,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    query = FederalDistrict.query.options(selectinload(FederalDistrict.regional_districts))
    query = dps.filter_parents_by_version(query, FederalDistrict)
    query = query.order_by(
        FederalDistrict.display_order.asc().nullslast(),
        FederalDistrict.name.asc(),
        FederalDistrict.id.asc(),
    )

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts).selectinload(
            RegionalDistrict.energy_units
        ).selectinload(EnergyUnit.regional_energy_system),
        selectinload(RegionalEnergySystem.energy_units),
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [res for res in res_query.all() if _is_valid_named_item(res)]

    entities: list[SummaryEntity] = []
    for federal_district in query.all():
        if not _is_valid_named_item(federal_district):
            continue
        if _federal_district_excluded_from_summary(federal_district):
            continue

        fd_rd_ids = {rd.id for rd in federal_district.regional_districts}
        child_entities = [
            _build_federal_district_res_entity(
                res,
                federal_district_id=federal_district.id,
                fd_rd_ids=fd_rd_ids,
            )
            for res in _regional_energy_systems_for_federal_district(
                federal_district,
                all_res,
            )
        ]
        base = SummaryEntity(
            label=federal_district.name,
            depth=0,
            parameters=PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=dps.get_demand_rows(
                FederalDistrictEnergyConsumptionParameter,
                "id_federal_district",
                federal_district.id,
            ),
            entity_kind="group",
            children=child_entities,
            demand_model_name=FederalDistrictEnergyConsumptionParameter.__name__,
            parent_fk_column="id_federal_district",
            parent_id=federal_district.id,
            id_federal_district=federal_district.id,
        )
        entities.extend(
            _expand_summary_entity_perimeter_variants(
                base,
                binding_entity_kind="federal_district",
                binding_entity_name=federal_district.name,
                expand=expand_entity_perimeter_variants,
                tree_years=tree_years,
            )
        )
    return entities


def _is_ees_branch(ues: UnionEnergySystem) -> bool:
    type_name = ((getattr(ues.energy_system_type, "name", None) or "").strip()).upper()
    return "ЕЭС" in type_name and "ТИТЭС" not in type_name


def _is_tites_branch(ues: UnionEnergySystem) -> bool:
    type_name = ((getattr(ues.energy_system_type, "name", None) or "").strip()).upper()
    return "ТИТЭС" in type_name


def _is_tites_regional_energy_system(res: RegionalEnergySystem) -> bool:
    """РЭС, входящие в ОЭС ветки ТИТЭС (не показываются в агрегациях по энергозонам)."""
    ues_id = getattr(res, "id_union_energy_system", None)
    if ues_id is None:
        return False
    return int(ues_id) in _tites_union_energy_system_ids()


def _filter_energy_units_for_res(
    energy_units: list[EnergyUnit],
    regional_energy_system_id: int,
) -> list[EnergyUnit]:
    return _filter_valid_items(
        [
            energy_unit
            for energy_unit in energy_units
            if getattr(energy_unit, "id_regional_energy_system", None) == regional_energy_system_id
        ]
    )


def _energy_unit_belongs_to_placeholder_res(energy_unit: EnergyUnit) -> bool:
    res_obj = getattr(energy_unit, "regional_energy_system", None)
    res_name = (getattr(res_obj, "name", None) or "").strip().casefold()
    return res_name in PLACEHOLDER_NAMES


def _energy_unit_summary_perimeter_variant_code(
    energy_unit: EnergyUnit,
) -> str | None:
    """Вариант периметра для строк энергорайона на сводке.

    Энергорайоны с РЭС «не указано» ведутся по форме О-1 (код ``o1``).
    Явная привязка из каталога периметра имеет приоритет.
    """
    eu_name = (getattr(energy_unit, "name", None) or "").strip()
    binding = resolve_entity_perimeter_variants("energy_unit", eu_name)
    if binding is not None:
        tree_variants = ordered_tree_variants_for_display(binding)
        if len(tree_variants) == 1:
            return tree_variants[0].code
        for vdef in tree_variants:
            if is_o1_perimeter_variant_code(vdef.code):
                return vdef.code
    if _energy_unit_belongs_to_placeholder_res(energy_unit):
        return resolve_catalog_o1_perimeter_variant_code()
    return None


def _filter_energy_units_with_placeholder_res(
    energy_units: list[EnergyUnit],
) -> list[EnergyUnit]:
    return _filter_valid_items(
        [
            energy_unit
            for energy_unit in energy_units
            if _energy_unit_belongs_to_placeholder_res(energy_unit)
        ]
    )


def _energy_units_for_federal_district_subject(
    energy_units: list[EnergyUnit],
    regional_energy_system_id: int,
) -> list[EnergyUnit]:
    """Энергорайоны субъекта для строки РЭС на сводках по ФО и ОЭС.

    Сначала — энергорайоны, привязанные к выбранной РЭС; в конце — энергорайоны с РЭС
    «не указано», не входящие в энергосистемы.
    """
    res_eus = _filter_energy_units_for_res(energy_units, regional_energy_system_id)
    seen_ids = {getattr(eu, "id", None) for eu in res_eus}
    for eu in _filter_energy_units_with_placeholder_res(energy_units):
        euid = getattr(eu, "id", None)
        if euid is None or euid in seen_ids:
            continue
        res_eus.append(eu)
        seen_ids.add(euid)
    return res_eus


def _get_energy_system_type_by_name(name: str) -> EnergySystemType | None:
    query = EnergySystemType.query
    query = dps.filter_parents_by_version(query, EnergySystemType)
    return query.filter(EnergySystemType.name == name).first()


def _is_valid_named_item(item: Any) -> bool:
    name = (getattr(item, "name", None) or "").strip()
    return bool(name) and name.casefold() not in PLACEHOLDER_NAMES


def _filter_valid_items(items: list[Any]) -> list[Any]:
    return [item for item in sorted(items, key=_sort_by_name) if _is_valid_named_item(item)]


def _energy_zone_number_sort_key(ez: EnergyZone) -> tuple[int, Any, int]:
    """Номер энергозоны как целое: 1, 2, …, 10, а не лексикографически 1, 10, 2."""
    raw = (getattr(ez, "number", None) or "").strip()
    eid = getattr(ez, "id", 0)
    if not raw:
        return (2, 0, eid)
    try:
        return (0, int(raw), eid)
    except ValueError:
        return (1, raw.casefold(), eid)


def _sort_by_name(item: Any) -> tuple[str, int]:
    return ((getattr(item, "name", None) or "").casefold(), getattr(item, "id", 0))


def _oes_territory_filters_active(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
) -> bool:
    """Хотя бы один территориальный фильтр сводки по ОЭС задан в URL."""
    return bool(f_ues or f_res or f_rd or f_eu)


def prune_summary_entities_oes(
    entities: list[SummaryEntity],
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    f_sa: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_oes_summary_context` и ослабление фильтров в :func:`_prune_one_oes`."""
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_oes(e, f_ues, f_res, f_rd, f_eu, f_sa)
        if pe is not None:
            out.append(pe)
    return out


def _oes_leaf_matches_filters(
    e: SummaryEntity,
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
) -> bool:
    if f_ues:
        if e.id_union_energy_system is None or e.id_union_energy_system not in f_ues:
            return False
    if f_res:
        if e.id_regional_energy_system is None or e.id_regional_energy_system not in f_res:
            return False
    if f_rd:
        if e.id_regional_district is None or e.id_regional_district not in f_rd:
            return False
    if f_eu:
        if e.id_energy_unit is None or e.id_energy_unit not in f_eu:
            return False
    return True


def _oes_is_union_energy_system_group(e: SummaryEntity) -> bool:
    return (
        e.entity_kind == "group"
        and e.demand_model_name == UnionEnergySystemEnergyConsumptionParameter.__name__
        and e.id_union_energy_system is not None
    )


def _oes_is_regional_energy_system_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalEnergySystemEnergyConsumptionParameter.__name__
        and e.id_regional_energy_system is not None
    )


def _oes_is_regional_district_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalDistrictEnergyConsumptionParameter.__name__
        and e.id_regional_district is not None
    )


def _oes_res_scope_for_ues_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    ues_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_res на уровне узла ОЭС (аналог :func:`_ez_res_scope_for_energy_zone_subtree`)."""
    if not f_res:
        return frozenset()
    if not f_ues:
        return f_res
    child_res_ids = {
        c.id_regional_energy_system for c in ues_children if c.id_regional_energy_system is not None
    }
    if not child_res_ids:
        return f_res
    inter = f_res & child_res_ids
    return inter if inter else frozenset()


def _oes_rd_scope_for_res_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    res_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_rd на уровне узла РЭС (прямые потомки — субъекты РФ или энергорайоны)."""
    if not f_rd:
        return frozenset()
    if not f_ues and not f_res:
        return f_rd
    child_rd_ids: set[int] = set()
    for c in res_children:
        if c.id_regional_district is not None:
            child_rd_ids.add(int(c.id_regional_district))
    if not child_rd_ids:
        return f_rd
    inter = f_rd & child_rd_ids
    return inter if inter else frozenset()


def _oes_eu_scope_for_rd_subtree(
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    rd_children: list[SummaryEntity],
) -> frozenset[int]:
    """Сужение ds_eu (энергорайон) на уровне узла субъекта РФ."""
    if not f_eu:
        return frozenset()
    if not f_ues and not f_res and not f_rd:
        return f_eu
    child_eu_ids = {c.id_energy_unit for c in rd_children if c.id_energy_unit is not None}
    if not child_eu_ids:
        return f_eu
    inter = f_eu & child_eu_ids
    return inter if inter else frozenset()


def _prune_one_oes(
    e: SummaryEntity,
    f_ues: frozenset[int],
    f_res: frozenset[int],
    f_rd: frozenset[int],
    f_eu: frozenset[int],
    f_sa: frozenset[int],
) -> SummaryEntity | None:
    filters_on = _oes_territory_filters_active(f_ues, f_res, f_rd, f_eu)
    if e.entity_kind == "synchronous_area":
        # Синхронные зоны только без территориального фильтра; при выборе ОЭС/РЭС/субъекта/ЭУ — скрываем
        if filters_on:
            return None
        if f_sa and (e.id_synchronous_area is None or e.id_synchronous_area not in f_sa):
            return None
        return e
    # Верхние агрегаты по стране/ЕЭС без привязки к ОЭС/РЭС — при фильтрах не показываем
    if e.entity_kind == "oes_top_aggregate":
        return None if filters_on else e
    # «ЭЭС России … без НТ», «ТИТЭС»: агрегат + дочерняя территориальная ветка
    if e.entity_kind == "group-root" or (
        e.entity_kind == ENTITY_KIND_EES_RUSSIA
        and int(e.depth or 0) == 0
        and e.demand_model_name == _EES_RUSSIA_DEMAND_MODEL_NAME
        and e.children
    ):
        new_ch: list[SummaryEntity] = []
        for c in e.children:
            pc = _prune_one_oes(c, f_ues, f_res, f_rd, f_eu, f_sa)
            if pc is not None:
                new_ch.append(pc)
        if filters_on and not new_ch:
            return None
        return replace(e, children=new_ch)
    res_c, rd_c, eu_c = f_res, f_rd, f_eu
    if f_ues and _oes_is_union_energy_system_group(e) and e.children:
        res_c = _oes_res_scope_for_ues_subtree(f_ues, f_res, e.children)
    elif (f_ues or f_res) and _oes_is_regional_energy_system_node(e) and e.children:
        rd_c = _oes_rd_scope_for_res_subtree(f_ues, f_res, f_rd, e.children)
    elif (f_ues or f_res or f_rd) and _oes_is_regional_district_node(e) and e.children:
        eu_c = _oes_eu_scope_for_rd_subtree(f_ues, f_res, f_rd, f_eu, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_oes(c, f_ues, res_c, rd_c, eu_c, f_sa)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _oes_leaf_matches_filters(e2, f_ues, f_res, f_rd, f_eu):
        return replace(e2, children=[])
    return None


def _fo_res_only_flat_mode(f_fd: frozenset[int], f_res: frozenset[int]) -> bool:
    """Только ``ds_res`` без ``ds_fd``: строки РЭС без родительской строки ФО."""
    return bool(f_res) and not bool(f_fd)


def prune_summary_entities_fo(
    entities: list[SummaryEntity],
    f_fd: frozenset[int],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_federal_district_summary_context`.

    Режим «плоско по РЭС» включается только в :func:`_fo_res_only_flat_mode`;
    при непустом ``f_fd`` строки ФО сохраняются; ``f_res`` сужает РЭС **внутри каждого ФО**
    через :func:`_fo_res_scope_for_fd_subtree` (пустой ``f_res`` = все РЭС выбранных ФО).
    """
    promote_res_without_fd_row = _fo_res_only_flat_mode(f_fd, f_res)
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_fo(e, f_fd, f_res)
        if pe is None:
            continue
        if (
            promote_res_without_fd_row
            and pe.entity_kind == "group"
            and pe.id_federal_district is not None
            and pe.children
        ):
            for c in pe.children:
                d = int(c.depth) if c.depth is not None else 0
                out.append(replace(c, depth=max(0, d - 1)))
            continue
        out.append(pe)
    return out


def _fo_leaf_matches(e: SummaryEntity, f_fd: frozenset[int], f_res: frozenset[int]) -> bool:
    """Совпадение листа/узла с фильтром.

    Пустой ``f_res`` не ограничивает РЭС: при заданном ``f_fd`` остаются все РЭС
    выбранных ФО. Непустой ``f_res`` сужает до перечисленных РЭС; при этом ``f_fd``,
    если задан, дополнительно ограничивает по округу (РЭС должна входить в один из ФО).
    """
    if not f_fd and not f_res:
        return True
    if f_fd:
        if e.id_federal_district is None or e.id_federal_district not in f_fd:
            return False
    if f_res:
        if e.id_regional_energy_system is None or e.id_regional_energy_system not in f_res:
            return False
    return True


def _fo_res_scope_for_fd_subtree(
    f_fd: frozenset[int],
    f_res: frozenset[int],
    fd_children: list[SummaryEntity],
) -> frozenset[int]:
    """Ограничение по РЭС для прямых потомков одного узла ФО.

    При выбранных в URL ``ds_fd`` и ``ds_res``: если среди отмеченных РЭС есть хотя бы одна
    из этого ФО — показываем только пересечение; иначе (все отмеченные из других ФО) —
    для этого ФО поддерева фильтр по РЭС снимаем — все РЭС округа.

    Режим только ``ds_res`` (пустой ``f_fd``): без ослабления — глобальный список РЭС.
    """
    if not f_res:
        return frozenset()
    if not f_fd:
        return f_res
    child_res_ids = {
        c.id_regional_energy_system for c in fd_children if c.id_regional_energy_system is not None
    }
    if not child_res_ids:
        return f_res
    inter = f_res & child_res_ids
    return inter if inter else frozenset()


_SUMMARY_TABLE_TOP_AGGREGATE_ENTITY_KINDS = frozenset(
    {
        ENTITY_KIND_RUSSIA_FEDERATION,
        ENTITY_KIND_CENTRALIZED_ZONE,
        "centralized_zone",
        ENTITY_KIND_EES_RUSSIA,
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        "synchronous_area",
    }
)


def _prune_one_fo(e: SummaryEntity, f_fd: frozenset[int], f_res: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_fd or f_res)
    if e.entity_kind in _SUMMARY_TABLE_TOP_AGGREGATE_ENTITY_KINDS:
        return None if filters_on else e
    res_for_children = f_res
    if f_fd and e.entity_kind == "group" and e.id_federal_district is not None and e.children:
        res_for_children = _fo_res_scope_for_fd_subtree(f_fd, f_res, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_fo(c, f_fd, res_for_children)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _fo_leaf_matches(e2, f_fd, f_res):
        return replace(e2, children=[])
    return None


def prune_summary_entities_ez(
    entities: list[SummaryEntity],
    f_ez: frozenset[int],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_energy_zones_summary_context` и :func:`_ez_res_scope_for_energy_zone_subtree`."""
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_ez(e, f_ez, f_res)
        if pe is not None:
            out.append(pe)
    return out


def _ez_res_only_flat_mode(f_ez: frozenset[int], f_res: frozenset[int]) -> bool:
    """Только ``ds_res`` без ``ds_ez``: строки РЭС без родительской строки энергозоны."""
    return bool(f_res) and not bool(f_ez)


def _ez_res_scope_for_energy_zone_subtree(
    f_ez: frozenset[int],
    f_res: frozenset[int],
    ez_children: list[SummaryEntity],
) -> frozenset[int]:
    """Ограничение по РЭС для прямых потомков одной энергозоны (аналог :func:`_fo_rd_scope_for_fd_subtree`)."""
    if not f_res:
        return frozenset()
    if not f_ez:
        return f_res
    child_res_ids = {
        c.id_regional_energy_system for c in ez_children if c.id_regional_energy_system is not None
    }
    if not child_res_ids:
        return f_res
    inter = f_res & child_res_ids
    return inter if inter else frozenset()


def _flatten_energy_zone_parents_when_res_filtered(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    """
    При фильтре по РЭС (ds_res) не показывать строку-агрегат энергозоны — только РЭС и ниже,
    аналогично сводке по ФО при фильтре по РЭС.
    """
    out: list[SummaryEntity] = []
    for e in entities:
        if e.entity_kind == "group" and e.id_energy_zone is not None and e.children:
            for c in e.children:
                d = int(c.depth) if c.depth is not None else 0
                out.append(replace(c, depth=max(0, d - 1)))
            continue
        out.append(e)
    return out


def _ez_leaf_matches(e: SummaryEntity, f_ez: frozenset[int], f_res: frozenset[int]) -> bool:
    if e.entity_kind in _SUMMARY_TABLE_TOP_AGGREGATE_ENTITY_KINDS:
        return True
    if not f_ez and not f_res:
        return True
    if f_ez:
        if e.id_energy_zone is None or e.id_energy_zone not in f_ez:
            return False
    if f_res:
        if e.id_regional_energy_system is None or e.id_regional_energy_system not in f_res:
            return False
    return True


def _prune_one_ez(e: SummaryEntity, f_ez: frozenset[int], f_res: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_ez or f_res)
    if e.entity_kind in _SUMMARY_TABLE_TOP_AGGREGATE_ENTITY_KINDS:
        return None if filters_on else e
    res_for_children = f_res
    if f_ez and e.entity_kind == "group" and e.id_energy_zone is not None and e.children:
        res_for_children = _ez_res_scope_for_energy_zone_subtree(f_ez, f_res, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_ez(c, f_ez, res_for_children)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _ez_leaf_matches(e2, f_ez, f_res):
        return replace(e2, children=[])
    return None


def get_demand_summary_filter_refdata() -> dict[str, Any]:
    """Справочники для multiselect-фильтров сводки (как на station_list)."""
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_unit_get_services import (
        get_energy_unit_list_full,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_zone_get_services import (
        get_energy_zone_list_full,
    )

    ues_objs = get_union_energy_system_list_full()
    union_energy_system_list = [{"id": x.id, "name": x.name} for x in ues_objs]

    res_objs = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": x.id, "name": x.name} for x in res_objs]

    rd_tuples = get_regional_district_list_full()
    regional_district_list = [{"id": rid, "name": rname} for rid, rname in rd_tuples]

    eu_objs = get_energy_unit_list_full()
    energy_unit_list = [{"id": x.id, "name": x.name} for x in eu_objs]

    fd_objs = get_federal_district_list_full()
    federal_district_list = [{"id": x.id, "name": x.name} for x in fd_objs]

    ez_objs = get_energy_zone_list_full()
    ez_objs_sorted = sorted(ez_objs, key=_energy_zone_number_sort_key)
    energy_zone_list = [{"id": x.id, "name": f"{x.number} — {x.name}"} for x in ez_objs_sorted]

    return {
        "union_energy_system_list": union_energy_system_list,
        "regional_energy_system_list": regional_energy_system_list,
        "regional_district_list": regional_district_list,
        "energy_unit_list": energy_unit_list,
        "federal_district_list": federal_district_list,
        "energy_zone_list": energy_zone_list,
    }


def get_energy_consumption_oes_filter_cascade_data() -> dict[str, Any]:
    """
    Списки и маппинги для каскадных фильтров сводки по ОЭС (как station_list / filters-data).
    Дополнительно — связи энергорайонов (EnergyUnit) с ОЭС/РЭС/субъектом.
    """
    from collections import defaultdict

    from app.common.services.get_services.energy_systems.energy_unit_get_services import (
        get_energy_unit_list_full,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_ues_id_map,
    )
    from app.generation.services.station_services.filters_services import (
        get_territorial_filter_reference_data,
    )

    t = get_territorial_filter_reference_data()
    res_to_ues_one = get_res_to_ues_id_map()

    ues_to_eu: dict[int, list[int]] = defaultdict(list)
    res_to_eu: dict[int, list[int]] = defaultdict(list)
    rd_to_eu: dict[int, list[int]] = defaultdict(list)
    eu_to_res: dict[int, int] = {}
    eu_to_rd: dict[int, int] = {}
    eu_to_ues: dict[int, int] = {}

    eu_objs = get_energy_unit_list_full()
    for eu in eu_objs:
        eid = int(eu.id)
        res_id = int(eu.id_regional_energy_system)
        rd_id = int(eu.id_regional_district)
        res_to_eu[res_id].append(eid)
        rd_to_eu[rd_id].append(eid)
        eu_to_res[eid] = res_id
        eu_to_rd[eid] = rd_id
        ues_id = res_to_ues_one.get(res_id)
        if ues_id is not None:
            ues_to_eu[int(ues_id)].append(eid)
            eu_to_ues[eid] = int(ues_id)

    return {
        "union_energy_system_list": t["union_energy_system_list"],
        "regional_energy_system_list": t["regional_energy_system_list"],
        "regional_district_list": t["regional_district_list"],
        "energy_unit_list": [{"id": x.id, "name": x.name} for x in eu_objs],
        "ues_to_res_mapping": t["regional_energy_system_mapping"],
        "ues_to_rd_mapping": t["ues_to_rd_mapping"],
        "res_to_rd_mapping": t["res_to_rd_mapping"],
        "res_to_ues_mapping_one": t["res_to_ues_mapping_one"],
        "rd_to_res_mapping": t["rd_to_res_mapping"],
        "rd_to_ues_mapping": t["rd_to_ues_mapping"],
        "ues_to_eu_ids": {str(k): v for k, v in ues_to_eu.items()},
        "res_to_eu_ids": {str(k): v for k, v in res_to_eu.items()},
        "rd_to_eu_ids": {str(k): v for k, v in rd_to_eu.items()},
        "eu_to_res_id": {str(k): v for k, v in eu_to_res.items()},
        "eu_to_rd_id": {str(k): v for k, v in eu_to_rd.items()},
        "eu_to_ues_id": {str(k): v for k, v in eu_to_ues.items()},
        "skip_territory_filter_cascade": False,
    }


def get_energy_consumption_fo_filter_cascade_data() -> dict[str, Any]:
    """
    Списки и маппинги для каскадных фильтров сводки по ФО (ФО ↔ РЭС),
    связь как при построении дерева сводки (РЭС входит в ФО, если есть субъект округа в составе РЭС).
    """
    from collections import defaultdict

    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
    )

    fd_objs = get_federal_district_list_full()
    federal_district_list = [{"id": x.id, "name": x.name} for x in fd_objs]

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [res for res in res_query.all() if _is_valid_named_item(res)]

    fd_query = FederalDistrict.query.options(selectinload(FederalDistrict.regional_districts))
    fd_query = dps.filter_parents_by_version(fd_query, FederalDistrict)
    federal_districts = [
        fd
        for fd in fd_query.all()
        if _is_valid_named_item(fd) and not _federal_district_excluded_from_summary(fd)
    ]

    fd_to_res: dict[int, list[int]] = {}
    res_to_fd_ids: dict[int, list[int]] = defaultdict(list)

    for fd in federal_districts:
        fd_rd_ids = {rd.id for rd in fd.regional_districts}
        res_ids: list[int] = []
        for res in all_res:
            if not any(rd.id in fd_rd_ids for rd in res.regional_districts):
                continue
            rid = int(res.id)
            res_ids.append(rid)
            fid = int(fd.id)
            lst = res_to_fd_ids[rid]
            if fid not in lst:
                lst.append(fid)
        fd_to_res[int(fd.id)] = res_ids

    res_objs = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": x.id, "name": x.name} for x in res_objs]

    return {
        "federal_district_list": federal_district_list,
        "regional_energy_system_list": regional_energy_system_list,
        "fd_to_res_mapping": {str(k): v for k, v in fd_to_res.items()},
        "res_to_fd_mapping": {str(k): v for k, v in res_to_fd_ids.items()},
        "skip_territory_filter_cascade": False,
    }


def get_energy_consumption_ez_filter_cascade_data() -> dict[str, Any]:
    """
    Каскад энергозона ↔ РЭС для сводки по энергозонам (связь как при построении дерева сводки).
    """
    from collections import defaultdict

    from sqlalchemy.orm import selectinload

    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
    )
    from app.refdata.models.energy_systems.energy_zone_model import EnergyZone

    ez_query = EnergyZone.query.options(selectinload(EnergyZone.regional_districts))
    ez_query = dps.filter_parents_by_version(ez_query, EnergyZone)
    zones = sorted(
        [z for z in ez_query.all() if _is_valid_named_item(z)],
        key=_energy_zone_number_sort_key,
    )

    res_query = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_query = dps.filter_parents_by_version(res_query, RegionalEnergySystem)
    all_res = [r for r in res_query.all() if _is_valid_named_item(r)]

    ez_to_res: dict[int, list[int]] = {}
    res_to_ez_ids: dict[int, list[int]] = defaultdict(list)

    for ez in zones:
        zone_rd_ids = {rd.id for rd in getattr(ez, "regional_districts", []) or []}
        res_ids: list[int] = []
        for res in all_res:
            rds_in_zone = [rd for rd in res.regional_districts if rd.id in zone_rd_ids]
            if not rds_in_zone:
                continue
            rid = int(res.id)
            res_ids.append(rid)
            eid = int(ez.id)
            lst = res_to_ez_ids[rid]
            if eid not in lst:
                lst.append(eid)
        ez_to_res[int(ez.id)] = res_ids

    res_objs = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": x.id, "name": x.name} for x in res_objs]

    energy_zone_list = [{"id": x.id, "name": f"{x.number} — {x.name}"} for x in zones]

    return {
        "energy_zone_list": energy_zone_list,
        "regional_energy_system_list": regional_energy_system_list,
        "ez_to_res_mapping": {str(k): v for k, v in ez_to_res.items()},
        "res_to_ez_mapping": {str(k): v for k, v in res_to_ez_ids.items()},
        "skip_territory_filter_cascade": False,
    }
