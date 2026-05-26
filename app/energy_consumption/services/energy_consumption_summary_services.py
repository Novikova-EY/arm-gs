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
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
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
    ordered_tree_variants_for_display,
    perimeter_variant_applies_to_year,
    perimeter_entity_context_for_model,
    perimeter_variant_display_label_for_entity,
    perimeter_variant_options_for_entity,
    perimeter_catalog_source,
    resolve_entity_perimeter_binding,
    resolve_entity_perimeter_variants,
)
from app.common.perimeter_variant.registry_types import EntityPerimeterBinding, PerimeterVariantDefinition
from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.help_services import format_decimal_for_display, format_decimal_trim_for_display
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
    SOUTH_UES_NAME_CF,
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


PLACEHOLDER_NAMES = {"не указано", "не указано2"}
_VERSION_CONTEXT_UNSET = object()

# Не показывать в сводке по ФО (экран и Excel).
_FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF = frozenset({"новые территории"})
_NEW_TERRITORIES_SUBJECTS_AGGREGATE_LABEL = "Новые территории"
_NEW_TERRITORIES_UES_NAME_TOKEN_CF = "новые территории"
_FIRST_SYNC_AREA_BASE_LABEL_CF = "первая синхронная зона"
_SECOND_SYNC_AREA_BASE_LABEL_CF = "вторая синхронная зона"
_KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF = "калининград"
_TITES_TYPE_LABEL_CF = "титэс"
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_FORMULA_TOOLTIP = (
    "Потребление ЭЭС России без НТ с зарядом ГАЭС, млн кВт·ч = "
    "Первая синхронная зона без НТ с зарядом ГАЭС + "
    "Вторая синхронная зона + "
    "Синхронная зона Калининградской области + "
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
    "(в т.ч. ОЭС Северо-Запада без ЭС Калининградской области) + "
    "заряд ГАЭС"
)
_FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT = (
    "without_nt_without_gaes_without_kaliningrad_es"
)
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
    "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада без ЭС Калининградской области), без ОЭС Востока; "
    "для ОЭС Юга — without_nt_with_gaes"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL = (
    "Проверка первой синхронной зоны без НТ с зарядом ГАЭС "
    "(с ЭС Калининградской области)"
)
_FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_TOOLTIP = (
    "Проверка = Первая синхронная зона без НТ с зарядом ГАЭС "
    "(с ЭС Калининградской области) − "
    "сумма потреблений ЭЭ всех ОЭС, входящих в первую синхронную зону "
    "(в т.ч. ОЭС Северо-Запада с ЭС Калининградской области), без ОЭС Востока; "
    "для ОЭС Юга — without_nt_with_gaes"
)
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL = (
    "Проверка ЕЭС России без НТ с зарядом ГАЭС"
)
_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP = (
    "Проверка = ЕЭС России без НТ с зарядом ГАЭС − "
    "(Первая синхронная зона без НТ с зарядом ГАЭС + "
    "Вторая синхронная зона + ТИТЭС) − "
    "Синхронная зона Калининградской области"
)
_VERIFICATION_DIFF_NONZERO_EPS = Decimal("0.00005")
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
    summary_ec_mln_display_divisor: int = 1


_EES_RUSSIA_DEMAND_MODEL_NAME = EesRussiaEnergyConsumptionParameter.__name__


def _is_ees_russia_without_nt_tree_root(e: SummaryEntity) -> bool:
    """Корень дерева ОЭС: агрегат «ЭЭС России … без НТ» (ветка ОЭС/СЗ/РЭС под ним)."""
    if e.demand_model_name != _EES_RUSSIA_DEMAND_MODEL_NAME:
        return False
    if int(e.depth or 0) != 0:
        return False
    if e.entity_kind not in (ENTITY_KIND_EES_RUSSIA, "group-root"):
        return False
    return e.perimeter_variant_code in (None, CODE_WITHOUT_NT) and bool(e.children)


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
        if perimeter_catalog_source() != "database":
            out = [
                _top_entity(CODE_WITH_NT),
                _top_entity(CODE_WITHOUT_NT),
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
                    key=lambda entity: allowed_order[
                        str(entity.perimeter_variant_code or "")
                    ]
                )
            if not out:
                return []
            return _order_variants_with_gaes_charge_rows(
                out,
                _gaes_charge_marker_entity(out[0]),
            )
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
    if normalized.startswith("with_nt") or normalized.startswith("o1_with_nt"):
        return "with_nt"
    if normalized.startswith("without_nt") or normalized.startswith("o1_without_nt"):
        return "without_nt"
    return "other"


def _kaliningrad_group_for_variant_code(code: str) -> str:
    if "with_kaliningrad_es" in code:
        return "with_kaliningrad_es"
    if "without_kaliningrad_es" in code:
        return "without_kaliningrad_es"
    return "other"


def _has_gaes_variant_codes(entities: list[SummaryEntity]) -> bool:
    return any("with_gaes" in str(e.perimeter_variant_code or "") or "without_gaes" in str(e.perimeter_variant_code or "") for e in entities)


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
    return tuple(v for v in variants if v.code not in {CODE_WITH_NT, CODE_WITHOUT_NT})


def _ees_unified_gaes_variant_uses_ees_russia_aggregate(variant_code: str) -> bool:
    """Строки «ЕЭС России … с/без зарядом ГАЭС» в Excel и БД — агрегат ``EesRussia*``, не ``EnergySystemType*``."""
    code = str(variant_code or "")
    return "with_gaes" in code or "without_gaes" in code


def _gaes_charge_marker_entity(entity: SummaryEntity) -> SummaryEntity:
    return replace(
        entity,
        parameters=tuple(),
        demand_rows=[],
        children=[],
        perimeter_variant_code=None,
    )


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
        before, after = _split_variants_around_gaes_charge_rows(variant_entities)
        return before + [charge_marker] + after

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
            before = [
                e
                for e in grouped
                if "without_gaes" not in str(e.perimeter_variant_code or "")
            ]
            before.sort(
                key=lambda e: 0
                if "with_gaes" in str(e.perimeter_variant_code or "")
                else 1
            )
            after = [
                e
                for e in grouped
                if "without_gaes" in str(e.perimeter_variant_code or "")
            ]
            result.extend(before)
            if before:
                result.append(charge_marker)
            result.extend(after)
    return result


def _expand_summary_entity_perimeter_variants(
    entity: SummaryEntity,
    *,
    binding_entity_kind: str,
    expand: bool,
    tree_years: list[int] | None = None,
    binding_entity_name: str | None = None,
) -> list[SummaryEntity]:
    """Дублирует только строку сущности по вариантам периметра, не её дочернюю ветку."""
    if not expand:
        return [entity]
    binding = resolve_entity_perimeter_binding(
        binding_entity_kind,
        binding_entity_name or entity.label,
    )
    if binding is None:
        return [entity]
    variants = _perimeter_variants_for_entity_binding(
        binding,
        tree_years,
        all_bound_variants=expand,
    )
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


def _build_oes_summary_table_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
    include_russia_top_row: bool = True,
    include_ees_russia_rows: bool = True,
    include_synchronous_area_rows: bool = True,
    russia_country_summary_ec_divisor: int = 1,
    expand_south_ues_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    """Плоский верхний порядок для страницы «Сводная таблица».

    На этой странице сначала идут агрегаты периметра, затем синхронные зоны и только после них
    блоки по типам энергосистем. Детальные территории позднее скрываются compact-фильтром.
    """
    entities: list[SummaryEntity] = []

    if include_russia_top_row:
        aggregate_kwargs = dict(
            russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
            all_bound_variants=True,
            tree_years=tree_years,
        )
        entities.extend(
            _build_perimeter_aggregate_entities(
                entity_kind=ENTITY_KIND_CENTRALIZED_ZONE,
                entity_name=CENTRALIZED_ZONE_AGGREGATE_NAME,
                demand_model=CentralizedZoneEnergyConsumptionParameter,
                display_label=CENTRALIZED_ZONE_AGGREGATE_NAME,
                **aggregate_kwargs,
            )
        )
        entities.extend(
            _build_perimeter_aggregate_entities(
                entity_kind=ENTITY_KIND_RUSSIA_FEDERATION,
                entity_name=RUSSIA_FEDERATION_AGGREGATE_NAME,
                demand_model=RussiaFederationEnergyConsumptionParameter,
                display_label=RUSSIA_FEDERATION_AGGREGATE_NAME,
                perimeter_variant_codes=(CODE_WITH_NT,),
                **aggregate_kwargs,
            )
        )
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
        ctx["summary_rows"] = summary_rows
        return ctx

    if summary_table_top_order:
        entities = _build_oes_summary_table_raw_entities(
            always_show_subject_row_under_res=False,
            include_russia_top_row=include_russia_top_row,
            include_ees_russia_rows=include_ees_russia_rows,
            include_synchronous_area_rows=include_synchronous_area_rows,
            russia_country_summary_ec_divisor=russia_country_summary_ec_divisor,
            expand_south_ues_perimeter_variants=expand_south_ues_perimeter_variants,
            tree_years=years,
        )
    else:
        entities = _build_oes_raw_entities(
            always_show_subject_row_under_res=False,
            **oes_raw_kwargs,
        )
    return _build_summary_context(
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
    """Сводка по ФО и субъектам РФ (GET ds_fd, ds_rd).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — ЦЗ и полное дерево по всем ФО со всеми субъектами.

    Только ``ds_fd`` — каждая выбранная строка ФО и **все** субъекты этих округов.

    ``ds_fd`` + ``ds_rd`` — строка по каждому выбранному ФО; субъекты сужаются **отдельно по
    каждому округу**: если в ``ds_rd`` есть субъекты этого ФО — показываются только они, если
    все отмеченные субъекты из других ФО — под данным ФО выводятся **все** его субъекты.

    Только ``ds_rd`` (без ``ds_fd``) — плоский список строк по субъектам без уровня ФО (как в Excel).
    """
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    tree_years = list(range(dsy, dey + 1))
    if expand_entity_perimeter_variants:
        entities = list(
            _build_perimeter_aggregate_entities(
                entity_kind=ENTITY_KIND_CENTRALIZED_ZONE,
                entity_name=CENTRALIZED_ZONE_AGGREGATE_NAME,
                demand_model=CentralizedZoneEnergyConsumptionParameter,
            )
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
        f_fd, f_rd = fo_filter_sets
        if f_fd or f_rd:
            entities = prune_summary_entities_fo(entities, f_fd, f_rd)

    return _build_summary_context(
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


def _build_ez_raw_entities(
    *,
    expand_entity_perimeter_variants: bool = False,
    tree_years: list[int] | None = None,
) -> list[SummaryEntity]:
    if expand_entity_perimeter_variants:
        entities = list(
            _build_perimeter_aggregate_entities(
                entity_kind=ENTITY_KIND_CENTRALIZED_ZONE,
                entity_name=CENTRALIZED_ZONE_AGGREGATE_NAME,
                demand_model=CentralizedZoneEnergyConsumptionParameter,
            )
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
    return _build_summary_context(
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
        gaes_detail_on=not summary_table_page,
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
        return True

    mode_hide = (opts.sipr_on and pk in _PD_EC_EXPORT_NORMAL_PARAM_KEYS) or (
        not opts.sipr_on and pk in _PD_EC_EXPORT_SIPR_PARAM_KEYS
    )
    if not (user_show and not mode_hide):
        return False

    if not is_ver and row.get("pd_ec_o1_form_row") and not opts.isolated_energy_units_on:
        return False
    if not is_ver and row.get("pd_ec_gaes_extra_row") and not opts.gaes_detail_on:
        return False
    if not is_ver and row.get("pd_ec_nt_extra_row") and not opts.nt_detail_on:
        return False
    if (
        not is_ver
        and opts.territory_compact_on
        and row.get("pd_ec_territory_detail_row")
    ):
        relaxed = row.get("pd_ec_territory_detail_relaxed_compact_nt_gaes")
        if not (relaxed and opts.gaes_detail_on and opts.nt_detail_on):
            return False
    if not is_ver and opts.territory_compact_on and row.get("pd_ec_territory_compact_hide_row"):
        if not opts.summary_table_page:
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


def _is_ees_russia_gaes_charge_summary_row(row: dict[str, Any]) -> bool:
    return (
        row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
        and row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__
        and row.get("pd_ec_gaes_injected_row")
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


def tag_energy_consumption_summary_rows_for_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Метки строк, скрываемых в режиме «Сводная таблица»."""
    first_ees_russia_gaes_hidden = False
    for row in summary_rows:
        if _is_centralized_zone_russia_summary_row(row):
            row["pd_ec_territory_compact_hide_row"] = True
            continue
        dm = row.get("demand_model_name") or ""
        if dm in _TERRITORY_DETAIL_DEMAND_MODELS and int(row.get("entity_depth") or 0) > 0:
            if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
                row["pd_ec_territory_detail_relaxed_compact_nt_gaes"] = True
                continue
            row["pd_ec_territory_detail_row"] = True
        if not first_ees_russia_gaes_hidden and _is_ees_russia_gaes_charge_summary_row(row):
            row["pd_ec_territory_compact_hide_row"] = True
            first_ees_russia_gaes_hidden = True


def tag_energy_consumption_summary_rows_perimeter_variant_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Подпись и привязка варианта периметра для столбца сводки."""
    for row in summary_rows:
        code = row.get("perimeter_variant_code")
        dm = row.get("demand_model_name") or ""
        pe_kind = row.get("pd_ec_perimeter_entity_kind")
        pe_name = row.get("pd_ec_perimeter_entity_name")
        if not pe_kind or not pe_name:
            ctx = perimeter_entity_context_for_model(
                dm,
                parent_fk_column=row.get("parent_fk_column"),
                parent_id=row.get("parent_id"),
            )
            if ctx is not None:
                pe_kind, pe_name = ctx
                row["pd_ec_perimeter_entity_kind"] = pe_kind
                row["pd_ec_perimeter_entity_name"] = pe_name
        row["perimeter_variant_label"] = (
            perimeter_variant_display_label_for_entity(code, pe_kind, pe_name) if code else ""
        )
        if is_o1_perimeter_variant_code(code):
            row["pd_ec_o1_form_row"] = True
        else:
            row.pop("pd_ec_o1_form_row", None)
        if row.get("show_entity_cell") and pe_kind:
            row["perimeter_variant_options"] = perimeter_variant_options_for_entity(
                pe_kind, pe_name
            )
        elif row.get("show_entity_cell"):
            row["perimeter_variant_options"] = []


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
        if row.get("pd_ec_territory_detail_row"):
            if (
                keep_gaes_charge_territory_rows
                and row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY
            ):
                out.append(row)
            continue
        out.append(row)
    return out


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
    """Сводная таблица: переключатели «+ НТ» / «+ Заряд ГАЭС» по кодам варианта периметра."""
    current_entity_key: tuple[Any, ...] | None = None
    current_nt_group = ""

    for row in rows:
        entity_key = (
            row.get("demand_model_name"),
            row.get("parent_fk_column"),
            row.get("parent_id"),
        )
        if entity_key != current_entity_key:
            current_entity_key = entity_key
            current_nt_group = ""

        code = str(row.get("perimeter_variant_code") or "")
        pk = str(row.get("parameter_key") or "")

        row.pop("pd_ec_entity_label_compact", None)
        row.pop("pd_ec_entity_label_compact_nt", None)
        row.pop("pd_ec_entity_label_compact_nt_gaes", None)

        if code:
            nt_group = _nt_group_for_variant_code(code)
            if nt_group in ("with_nt", "without_nt"):
                current_nt_group = nt_group
            row["pd_ec_nt_extra_row"] = nt_group == "with_nt"
            row["pd_ec_nt_without_row"] = nt_group == "without_nt"
            row["pd_ec_gaes_extra_row"] = "with_gaes" in code
            row["pd_ec_gaes_without_row"] = "without_gaes" in code
            base_label = str(row.get("entity_label") or "")
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


def _build_new_territories_subjects_summary_rows(
    *,
    years: list[int],
    rounding_digits: int,
    south_ues_id: int,
) -> list[dict[str, Any]]:
    nt_ues_id = _resolve_new_territories_union_energy_system_id()
    if nt_ues_id is None:
        return []
    rd_ids = _regional_district_ids_for_union_energy_system(nt_ues_id)
    if not rd_ids:
        return []

    raw_ec: dict[int, Decimal] = {}
    raw_sipr: dict[int, Decimal] = {}
    has_ec: dict[int, bool] = {}
    has_sipr: dict[int, bool] = {}
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
            ec = getattr(row, "energy_consumption_mln_kvt_ch", None)
            if ec is not None:
                raw_ec[year_num] = raw_ec.get(year_num, Decimal(0)) + Decimal(str(ec))
                has_ec[year_num] = True
            sipr = getattr(row, "energy_consumption_sipr_mln_kvt_ch", None)
            if sipr is not None:
                raw_sipr[year_num] = raw_sipr.get(year_num, Decimal(0)) + Decimal(str(sipr))
                has_sipr[year_num] = True

    aggregated_rows: list[_AggregatedYearDemandSlice] = []
    for year in years:
        ec_val = raw_ec.get(year) if has_ec.get(year) else None
        sipr_val = raw_sipr.get(year) if has_sipr.get(year) else None
        if ec_val is None and sipr_val is None:
            continue
        aggregated_rows.append(
            _AggregatedYearDemandSlice(
                year_number=year,
                energy_consumption_mln_kvt_ch=ec_val,
                energy_consumption_sipr_mln_kvt_ch=sipr_val,
            )
        )
    if not aggregated_rows:
        return []

    parameter_maps, tooltip_maps = _build_parameter_maps(
        aggregated_rows,
        PARAMETERS_ENERGY_CONSUMPTION,
        rounding_digits,
    )
    entity_rowspan = len(PARAMETERS_ENERGY_CONSUMPTION)
    out: list[dict[str, Any]] = []
    for index, (parameter_key, parameter_label) in enumerate(PARAMETERS_ENERGY_CONSUMPTION):
        values = parameter_maps.get(parameter_key, {})
        tt = tooltip_maps.get(parameter_key, {})
        out.append(
            {
                "entity_label": _NEW_TERRITORIES_SUBJECTS_AGGREGATE_LABEL,
                "entity_rowspan": entity_rowspan,
                "entity_depth": 1,
                "entity_kind": "fo_nt_under_south",
                "show_entity_cell": index == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": None,
                "parent_fk_column": None,
                "parent_id": None,
                "hist_row_id": None,
                "year_row_ids": [None for _ in years],
                "hist_value": "—",
                "year_values": [values.get(year, "—") for year in years],
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": [tt.get(year, "") for year in years],
                "id_union_energy_system": south_ues_id,
                "entity_note_text": "",
                "entity_note_row_id": None,
                "show_entity_note_cell": index == 0,
                "perimeter_variant_code": None,
                "pd_ec_nt_extra_row": True,
                "pd_ec_nt_without_row": False,
                "pd_ec_formula_derived_row": True,
                "show_perimeter_variant_select": False,
                "perimeter_variant_label": "",
                "perimeter_variant_options": [],
            }
        )
    return out


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

    south_ues_id = _resolve_union_energy_system_id_by_name_cf(SOUTH_UES_NAME_CF)
    if south_ues_id is None:
        return

    nt_rows = _build_new_territories_subjects_summary_rows(
        years=years,
        rounding_digits=rounding_digits,
        south_ues_id=south_ues_id,
    )
    if not nt_rows:
        return

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
            index = next_index
            continue
        index += 1
    summary_rows[:] = out


def _is_top_ees_russia_aggregate_summary_table_row(row: dict[str, Any]) -> bool:
    """Верхний агрегат «ЕЭС России» на сводной таблице, не варианты под «ЕЭС России …» (тип ЭС)."""
    return row.get("entity_kind") == ENTITY_KIND_EES_RUSSIA


def _last_ees_russia_summary_table_row_index(summary_rows: list[dict[str, Any]]) -> int | None:
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__:
            break
        if _is_top_ees_russia_aggregate_summary_table_row(row):
            last_index = index
    return last_index


def _is_kaliningrad_sync_area_summary_table_row(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
        return False
    return _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF in _summary_row_base_label_cf(row)


def _last_kaliningrad_sync_area_summary_table_row_index(
    summary_rows: list[dict[str, Any]],
) -> int | None:
    last_index: int | None = None
    for index, row in enumerate(summary_rows):
        if _is_kaliningrad_sync_area_summary_table_row(row):
            last_index = index
    return last_index


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


def _verification_year_red_flags(
    years: list[int],
    raw_by_year: dict[int, Decimal | None],
) -> list[bool]:
    flags: list[bool] = []
    for year in years:
        value = raw_by_year.get(int(year))
        flags.append(
            value is not None and abs(value) > _VERIFICATION_DIFF_NONZERO_EPS
        )
    return flags


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
) -> list[dict[str, Any]]:
    demand_slices: list[_AggregatedYearDemandSlice] = []
    for year in years:
        y = int(year)
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

    parameter_maps, tooltip_maps = _build_parameter_maps(
        demand_slices,
        PARAMETERS_ENERGY_CONSUMPTION,
        rounding_digits,
    )
    verification_parameters = _EC_SUMMARY_VERIFICATION_PARAMETERS
    ec_diff = _subtract_year_value_dicts(years, base_ec, sum_ec)
    sipr_diff = _subtract_year_value_dicts(years, base_sipr, sum_sipr)
    out: list[dict[str, Any]] = []
    for index, (parameter_key, parameter_label) in enumerate(verification_parameters):
        values = parameter_maps.get(parameter_key, {})
        tooltips = tooltip_maps.get(parameter_key, {})
        row: dict[str, Any] = {
            "entity_label": entity_label,
            "entity_rowspan": 1,
            "entity_depth": entity_depth,
            "entity_kind": entity_kind,
            "show_entity_cell": True,
            "parameter_key": parameter_key,
            "parameter_label": parameter_label,
            "demand_model_name": None,
            "parent_fk_column": None,
            "parent_id": None,
            "hist_row_id": None,
            "year_row_ids": [None for _ in years],
            "hist_value": "—",
            "year_values": [values.get(year, "—") for year in years],
            "hist_numeric_tooltip": "",
            "year_numeric_tooltips": [tooltips.get(year, "") for year in years],
            "entity_note_text": "",
            "entity_note_row_id": None,
            "show_entity_note_cell": True,
            "perimeter_variant_code": None,
            "show_perimeter_variant_select": False,
            "perimeter_variant_label": "",
            "perimeter_variant_options": [],
            "pd_ec_verification_full_precision": True,
        }
        if formula_tooltip and parameter_key == "energy_consumption_mln_kvt_ch":
            row["pd_ec_verification_formula_tooltip"] = formula_tooltip
        if parameter_key == "energy_consumption_mln_kvt_ch":
            row["pd_ec_verification_year_red"] = _verification_year_red_flags(years, ec_diff)
        elif parameter_key == "energy_consumption_sipr_mln_kvt_ch":
            row["pd_ec_verification_year_red"] = _verification_year_red_flags(years, sipr_diff)
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


def _first_sa_without_nt_with_gaes_parameter_year_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> dict[int, Decimal | None]:
    first_sa_row = _find_sync_area_source_row(
        summary_rows,
        parameter_key=parameter_key,
        base_label_prefix_cf=_FIRST_SYNC_AREA_BASE_LABEL_CF,
        variant_predicate=_is_without_nt_with_gaes_variant_row,
    )
    if first_sa_row is not None:
        raw = _raw_year_values_from_summary_row(first_sa_row, years)
        if _year_values_have_any_numeric(raw):
            return raw

    first_sa_id = _resolve_first_synchronous_area_id()
    if first_sa_id is None:
        return {}

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


def _ees_russia_without_nt_with_gaes_formula_component_values(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
) -> tuple[
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[int, Decimal | None],
]:
    first_sa_values = _first_sa_without_nt_with_gaes_parameter_year_values(
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
    tites_values = _year_values_for_tites_source(summary_rows, years, parameter_key)
    return first_sa_values, second_sa_values, kaliningrad_values, tites_values


def _build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
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
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
    )
    base_sipr = _year_values_from_parent_demand_rows(
        EesRussiaEnergyConsumptionParameter,
        None,
        None,
        years,
        sipr_key,
        perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
    )
    if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
        ees_ec_row = _find_ees_russia_summary_parameter_row(
            summary_rows,
            parameter_key=ec_key,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        ees_sipr_row = _find_ees_russia_summary_parameter_row(
            summary_rows,
            parameter_key=sipr_key,
            perimeter_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        )
        if ees_ec_row is None or ees_sipr_row is None:
            return []
        base_ec = _raw_year_values_from_summary_row(ees_ec_row, years)
        base_sipr = _raw_year_values_from_summary_row(ees_sipr_row, years)
        if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(
            base_sipr
        ):
            return []

    first_ec, second_ec, kal_ec, tites_ec = _ees_russia_without_nt_with_gaes_formula_component_values(
        summary_rows,
        years,
        ec_key,
    )
    first_sipr, second_sipr, kal_sipr, tites_sipr = (
        _ees_russia_without_nt_with_gaes_formula_component_values(
            summary_rows,
            years,
            sipr_key,
        )
    )
    sum_ec = _sum_year_value_dicts(years, first_ec, second_ec, tites_ec)
    sum_sipr = _sum_year_value_dicts(years, first_sipr, second_sipr, tites_sipr)
    diff_ec = _subtract_year_value_dicts(years, base_ec, sum_ec)
    diff_sipr = _subtract_year_value_dicts(years, base_sipr, sum_sipr)
    diff_ec = _subtract_year_value_dicts(years, diff_ec, kal_ec)
    diff_sipr = _subtract_year_value_dicts(years, diff_sipr, kal_sipr)

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
) -> list[dict[str, Any]]:
    ec_key = "energy_consumption_mln_kvt_ch"
    sipr_key = "energy_consumption_sipr_mln_kvt_ch"
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
    if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(base_sipr):
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
        if first_sa_ec_row is None or first_sa_sipr_row is None:
            return []
        base_ec = _raw_year_values_from_summary_row(first_sa_ec_row, years)
        base_sipr = _raw_year_values_from_summary_row(first_sa_sipr_row, years)
        if not _year_values_have_any_numeric(base_ec) and not _year_values_have_any_numeric(
            base_sipr
        ):
            return []

    sum_ec = _year_values_sum_ues_in_synchronous_area(
        first_sa_id,
        years,
        ec_key,
        ues_variant_code=default_ues_variant_code,
        exclude_ues_ids=exclude_ues_ids,
        ues_variant_code_for_ues_id=ues_variant_code_for_ues_id,
    )
    sum_sipr = _year_values_sum_ues_in_synchronous_area(
        first_sa_id,
        years,
        sipr_key,
        ues_variant_code=default_ues_variant_code,
        exclude_ues_ids=exclude_ues_ids,
        ues_variant_code_for_ues_id=ues_variant_code_for_ues_id,
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
    )


def inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
) -> None:
    """Проверки сводной таблицы: ЕЭС России — после блока «ЕЭС России»; первая СЗ — после «Синхронная зона Калининградской области»."""
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
    kaliningrad_insert_after = _last_kaliningrad_sync_area_summary_table_row_index(summary_rows)
    if ees_insert_after is None and kaliningrad_insert_after is None:
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
        ees_verification_rows = _build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
            summary_rows,
            years=years,
            rounding_digits=rounding_digits,
            entity_depth=ees_entity_depth,
        )

    first_sa_verification_rows: list[dict[str, Any]] = []
    if kaliningrad_insert_after is not None and first_sa_id is not None:
        first_sa_entity_depth = int(
            summary_rows[kaliningrad_insert_after].get("entity_depth") or 0
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
            )
        )

    if not ees_verification_rows and not first_sa_verification_rows:
        return

    if ees_verification_rows and ees_insert_after is not None:
        summary_rows[ees_insert_after + 1 : ees_insert_after + 1] = ees_verification_rows

    if first_sa_verification_rows and kaliningrad_insert_after is not None:
        kaliningrad_insert_after += len(ees_verification_rows)
        summary_rows[kaliningrad_insert_after + 1 : kaliningrad_insert_after + 1] = (
            first_sa_verification_rows
        )


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
    rd_ids = _regional_district_ids_for_union_energy_system(nt_ues_id)
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
) -> None:
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == SynchronousAreaEnergyConsumptionParameter.__name__
        and row.get("parent_id") == synchronous_area_id
        and _is_summary_table_base_perimeter_row(row)
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
    """Первая СЗ с НТ с зарядом ГAЭС (с ЭС Калининграда) = сумма ОЭС + заряд ГAЭС + НТ."""
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
        source_maps: list[dict[int, Decimal | None]] = [
            _year_values_sum_ues_in_synchronous_area(
                first_sa_id,
                years,
                parameter_key,
                ues_variant_code=CODE_WITH_NT_WITH_GAES,
            ),
            _gaes_charge_year_values_for_first_sa_with_nt(
                summary_rows,
                years,
                first_sa_id=first_sa_id,
            ),
            _new_territories_parameter_year_values(years, parameter_key),
        ]
        source_maps = [item for item in source_maps if _year_values_have_any_numeric(item)]
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
    """Первая СЗ без НТ с зарядом ГAЭС (без Калининграда) = сумма ОЭС + заряд ГAЭС."""
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
        source_maps: list[dict[int, Decimal | None]] = [
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

    tites_ids = _tites_union_energy_system_ids()
    summed: dict[int, Decimal] = {}
    for row in summary_rows:
        if row.get("demand_model_name") != UnionEnergySystemEnergyConsumptionParameter.__name__:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if not _is_summary_table_base_perimeter_row(row):
            continue
        parent_id = row.get("parent_id")
        if parent_id is None or int(parent_id) not in tites_ids:
            continue
        for year, value in _raw_year_values_from_summary_row(row, years).items():
            if value is None:
                continue
            summed[int(year)] = summed.get(int(year), Decimal(0)) + value
    return dict(summed)


def _apply_ees_russia_with_gaes_sum_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    target_variant_code: str,
    first_sa_variant_predicate: Callable[[dict[str, Any]], bool],
    extra_source_by_parameter: Callable[[str], dict[int, Decimal | None]] | None = None,
    formula_tooltip: str | None = None,
) -> None:
    target_rows = [
        row
        for row in summary_rows
        if row.get("demand_model_name") == EesRussiaEnergyConsumptionParameter.__name__
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
        for row in summary_rows:
            if row.get("demand_model_name") != SynchronousAreaEnergyConsumptionParameter.__name__:
                continue
            if row.get("parameter_key") != parameter_key:
                continue
            if not _is_summary_table_base_perimeter_row(row):
                continue
            if _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF not in _summary_row_base_label_cf(row):
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
        source_maps.append(_year_values_for_tites_source(summary_rows, years, parameter_key))
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


def apply_summary_table_formula_calculations(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Пересчёт строк сводной таблицы с формулами (как на /summary-table/)."""
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
    _apply_ees_russia_with_gaes_sum_formula(
        summary_rows,
        years,
        rounding_digits,
        target_variant_code=CODE_WITHOUT_NT_WITH_GAES,
        first_sa_variant_predicate=_is_without_nt_with_gaes_variant_row,
        formula_tooltip=_EES_RUSSIA_WITHOUT_NT_WITH_GAES_FORMULA_TOOLTIP,
    )
    _apply_ees_russia_with_gaes_sum_formula(
        summary_rows,
        years,
        rounding_digits,
        target_variant_code=CODE_WITH_NT_WITH_GAES,
        first_sa_variant_predicate=_is_with_nt_with_gaes_variant_row,
        extra_source_by_parameter=lambda pk: _new_territories_parameter_year_values(years, pk),
        formula_tooltip=_EES_RUSSIA_WITH_NT_WITH_GAES_FORMULA_TOOLTIP,
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
    apply_first_sa_without_nt_without_gaes_without_kaliningrad_diff_formula(
        summary_rows,
        years,
        rounding_digits,
    )


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


def apply_federal_district_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Строки ФО: mln/sipr как сумма РЭС округа; темпы прироста — от пересчитанной серии."""
    if not summary_rows or not years:
        return

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
        by_year = aggregates.get((int(parent_id), pvc), {})
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
                raw_by_year[int(year)] = pair[value_index] if pair is not None else None
            _write_numeric_year_values_to_summary_row(
                target_row,
                years,
                raw_by_year,
                parameter_key=parameter_key,
                rounding_digits=rounding_digits,
            )
            target_row["pd_ec_formula_derived_row"] = True
            if parameter_key == "energy_consumption_mln_kvt_ch":
                target_row["pd_ec_summary_row_formula_tooltip"] = _FO_FORMULA_TOOLTIP

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

        entity_key = _summary_row_entity_key(fo_blocks[0][0])
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

        entity_key = _summary_row_entity_key(source_block[0])
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


_TERRITORY_GAES_LABEL_DEMAND_MODELS = frozenset(
    {
        FederalDistrictEnergyConsumptionParameter.__name__,
        RegionalDistrictEnergyConsumptionParameter.__name__,
    }
)


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
        entities.add(
            (
                row.get("demand_model_name"),
                row.get("parent_fk_column"),
                row.get("parent_id"),
            )
        )
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
            row["perimeter_variant_label"] = _GAES_LABEL_SUFFIX_WITHOUT.strip()


def build_summary_table_rows_with_formulas_for_version(
    *,
    database_version_id: int,
    years: list[int],
    rounding_digits: int = 1,
) -> list[dict[str, Any]]:
    """Строки сводной таблицы ОЭС с пересчитанными формулами для указанной версии БД."""
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
            expand_south_ues_perimeter_variants=True,
            summary_table_top_order=True,
        )
        summary_rows = list(ctx.get("summary_rows") or [])
        ctx_years = list(ctx.get("years") or years)
        tag_energy_consumption_summary_rows_for_territory_compact(summary_rows)
        summary_rows = filter_summary_rows_for_summary_table_page(summary_rows)
        apply_energy_consumption_summary_table_variant_toggle_rows(summary_rows)
        apply_summary_table_russia_federation_row_rules(summary_rows)
        apply_summary_table_formula_calculations(
            summary_rows,
            ctx_years,
            rounding_digits,
        )
        return summary_rows
    finally:
        if prev_version is _VERSION_CONTEXT_UNSET:
            if hasattr(g, "current_db_version"):
                delattr(g, "current_db_version")
        else:
            g.current_db_version = prev_version


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


@lru_cache(maxsize=4096)
def _entity_has_gaes_charge_stations(
    current_version_id: int | None,
    demand_model_name: str | None,
    parent_id: int | None,
) -> bool:
    """True, если у сущности сводки есть станции ГАЭС с данными заряда (любой год)."""
    del current_version_id
    if not demand_model_name or parent_id is None:
        return False
    q = (
        db.session.query(Station.id)
        .select_from(StationGaesChargeConsumption)
        .join(Station, Station.id == StationGaesChargeConsumption.id_station)
    )
    q = dps.filter_parents_by_version(q, StationGaesChargeConsumption)
    q = dps.filter_parents_by_version(q, Station)
    q = _apply_gaes_charge_summary_entity_filter(q, demand_model_name, int(parent_id))
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
    """Потребление ГАЭС на заряд по станциям для выбранной сущности и годов."""
    del current_version_id, parent_fk_column
    if not demand_model_name or not years:
        return tuple()

    q = (
        db.session.query(
            Station.id,
            Station.name,
            StationGaesChargeConsumption.year_number,
            func.sum(StationGaesChargeConsumption.charge_consumption),
        )
        .select_from(StationGaesChargeConsumption)
        .join(Station, Station.id == StationGaesChargeConsumption.id_station)
    )
    q = dps.filter_parents_by_version(q, StationGaesChargeConsumption)
    q = dps.filter_parents_by_version(q, Station)
    q = q.filter(StationGaesChargeConsumption.year_number.in_(years))
    q = _apply_gaes_charge_summary_entity_filter(q, demand_model_name, parent_id)
    if q is None:
        return tuple()

    rows = (
        q.group_by(Station.id, Station.name, StationGaesChargeConsumption.year_number)
        .order_by(
            Station.name.asc().nullslast(),
            Station.id.asc(),
            StationGaesChargeConsumption.year_number.asc(),
        )
        .all()
    )
    grouped: dict[int, dict[str, Any]] = {}
    for station_id, station_name, year, value in rows:
        if station_id is None or year is None or value is None:
            continue
        sid = int(station_id)
        item = grouped.setdefault(
            sid,
            {
                "name": (station_name or "").strip() or "Без названия",
                "values": [],
            },
        )
        item["values"].append((int(year), value))
    return tuple(
        (sid, str(data["name"]), tuple(data["values"]))
        for sid, data in grouped.items()
    )


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
        return []
    entity_label_cf = str(entity.label or "").strip().casefold()
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
    )

    def _value_maps(raw_values: dict[int, Any]) -> tuple[list[str], list[str]]:
        return (
            [_format_numeric(raw_values.get(year), rounding_digits) if year in raw_values else "—" for year in years],
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
        "show_perimeter_variant_select": False,
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
    show_total_row = entity.demand_model_name != UnionEnergySystemEnergyConsumptionParameter.__name__
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
    return (
        row.get("demand_model_name"),
        row.get("parent_fk_column"),
        row.get("parent_id"),
        str(row.get("entity_label") or "").strip(),
    )


def _summary_row_variant_param_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *_summary_row_entity_key(row),
        row.get("perimeter_variant_code"),
        row.get("parameter_key"),
    )


def _gaes_charge_entity_key(row: dict[str, Any]) -> tuple[Any, ...]:
    label = str(row.get("entity_label") or "").strip()
    gaes_suffix = " (заряд ГАЭС)"
    if label.endswith(gaes_suffix):
        label = label[: -len(gaes_suffix)]
    return (
        row.get("demand_model_name"),
        row.get("parent_fk_column"),
        row.get("parent_id"),
        label,
    )


def _with_gaes_variant_code(code: str | None) -> str | None:
    s = str(code or "").strip()
    if not s or "without_gaes" not in s:
        return None
    return s.replace("without_gaes", "with_gaes", 1)


def _raw_year_values_from_summary_row(
    row: dict[str, Any],
    years: list[int],
) -> dict[int, Decimal | None]:
    values = row.get("year_values") or []
    tooltips = row.get("year_numeric_tooltips") or []
    out: dict[int, Decimal | None] = {}
    for index, year in enumerate(years):
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
            values.append(_format_numeric(raw, rounding_digits))
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
        entity_key = _gaes_charge_entity_key(row)
        year_values = _raw_year_values_from_summary_row(row, years)
        if row.get("gaes_charge_row_station_name") == "всего":
            totals[entity_key] = year_values
            continue
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


def apply_gaes_without_charge_formula_to_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    if not summary_rows or not years:
        return

    gaes_totals = _collect_gaes_charge_totals_by_entity(summary_rows, years)
    row_by_variant_param = {
        _summary_row_variant_param_key(row): row for row in summary_rows
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
        entity_key = _summary_row_entity_key(row)
        gaes_by_year = gaes_totals.get(entity_key, {})
        formula_kind = _gaes_without_charge_formula_kind_for_row(row)
        block_rows = [
            item
            for item in summary_rows
            if _summary_row_entity_key(item) == entity_key
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
            "entity_note_text": entity_note_text,
            "entity_note_row_id": entity_note_rid,
            "show_entity_note_cell": index == 0,
            "perimeter_variant_code": entity.perimeter_variant_code,
        }
        if pe_ctx is not None:
            row_data["pd_ec_perimeter_entity_kind"] = pe_ctx[0]
            row_data["pd_ec_perimeter_entity_name"] = pe_ctx[1]
        entity_rows.append(row_data)

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
    return s if s else ""


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
            result["energy_consumption_mln_kvt_ch"][sk] = _format_numeric(
                raw_ec[sk],
                rounding_digits,
            )
        if "energy_consumption_mln_kvt_ch" in tooltips:
            tooltips["energy_consumption_mln_kvt_ch"][sk] = _format_full_numeric_tooltip(raw_ec[sk])

        if "energy_consumption_sipr_mln_kvt_ch" in result:
            result["energy_consumption_sipr_mln_kvt_ch"][sk] = _format_numeric(
                raw_sipr[sk],
                rounding_digits,
            )

    if "energy_consumption_sipr_mln_kvt_ch" in result:
        sipr_hover: dict[Any, str] = {}
        for sk in set(raw_ec.keys()) | set(raw_sipr.keys()):
            sipr_hover[sk] = _format_full_numeric_tooltip(raw_ec.get(sk))
        tooltips["energy_consumption_sipr_mln_kvt_ch"] = sipr_hover

    if ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY in result:
        for sk, curr in raw_sipr.items():
            diff_v = _abs_diff_value(curr, raw_sipr.get(sk - 1))
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
        for sk, curr in raw_sipr.items():
            pct_s = _yoy_growth_pct_value(curr, raw_sipr.get(sk - 1))
            disp_s = _format_yoy_pct_for_display(pct_s)
            result[ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY][sk] = disp_s
            if ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY in tooltips:
                tooltips[ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY][sk] = (
                    disp_s if pct_s is not None else ""
                )

    return result, tooltips


def _format_numeric(value: Any, digits: int) -> str:
    return _dash(format_decimal_trim_for_display(value, digits=digits))


def _format_yoy_pct_for_display(value: Any) -> str:
    """Годовой темп прироста: ровно два знака после запятой (например 2,30)."""
    if value is None:
        return "—"
    s = format_decimal_for_display(value, digits=_ENERGY_CONSUMPTION_YOY_DISPLAY_DECIMALS)
    return s if s else "—"


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
                energy_units=_filter_energy_units_for_res(
                    regional_district.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                ues_id=ues_id,
                res_id=res.id,
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
                energy_units=_filter_energy_units_for_res(
                    rd0.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                ues_id=ues_id,
                res_id=res.id,
            )
        ]
    else:
        subject_children = _build_energy_unit_entities(
            _filter_valid_items(res.energy_units),
            depth=3,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res.id,
            id_regional_district=single_rd_id,
        )

    return SummaryEntity(
        label=res.name,
        depth=2,
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
        id_union_energy_system=ues_id,
        id_regional_energy_system=res.id,
        id_regional_district=single_rd_id,
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
) -> SummaryEntity:
    return SummaryEntity(
        label=regional_district.name,
        depth=depth,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(
            RegionalDistrictEnergyConsumptionParameter,
            "id_regional_district",
            regional_district.id,
        ),
        entity_kind="child",
        children=_build_energy_unit_entities(
            energy_units if energy_units is not None else _filter_valid_items(regional_district.energy_units),
            depth=depth + 1,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res_id,
            id_regional_district=regional_district.id,
        ),
        demand_model_name=RegionalDistrictEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_district",
        parent_id=regional_district.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res_id,
        id_regional_district=regional_district.id,
    )


def _build_energy_unit_entities(
    energy_units: list[EnergyUnit],
    *,
    depth: int,
    id_union_energy_system: int | None = None,
    id_regional_energy_system: int | None = None,
    id_regional_district: int | None = None,
    id_energy_zone: int | None = None,
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for energy_unit in _filter_valid_items(energy_units):
        ues = id_union_energy_system
        if ues is None:
            res_obj = getattr(energy_unit, "regional_energy_system", None)
            ues_obj = getattr(res_obj, "union_energy_system", None) if res_obj else None
            ues = getattr(ues_obj, "id", None)
        res_id = id_regional_energy_system or getattr(
            energy_unit, "id_regional_energy_system", None
        )
        rd_id = id_regional_district or getattr(energy_unit, "id_regional_district", None)
        out.append(
            SummaryEntity(
                label=energy_unit.name,
                depth=depth,
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=dps.get_demand_rows(
                    EnergyUnitEnergyConsumptionParameter,
                    "id_energy_unit",
                    energy_unit.id,
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
            )
        )
    return out


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

    entities: list[SummaryEntity] = []
    for federal_district in query.all():
        if not _is_valid_named_item(federal_district):
            continue
        if _federal_district_excluded_from_summary(federal_district):
            continue

        child_entities = [
            SummaryEntity(
                label=regional_district.name,
                depth=1,
                parameters=PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=dps.get_demand_rows(
                    RegionalDistrictEnergyConsumptionParameter,
                    "id_regional_district",
                    regional_district.id,
                ),
                entity_kind="child",
                demand_model_name=RegionalDistrictEnergyConsumptionParameter.__name__,
                parent_fk_column="id_regional_district",
                parent_id=regional_district.id,
                id_federal_district=federal_district.id,
                id_regional_district=regional_district.id,
            )
            for regional_district in sorted(federal_district.regional_districts, key=_sort_by_name)
            if _is_valid_named_item(regional_district)
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


def _fo_subjects_only_flat_mode(f_fd: frozenset[int], f_rd: frozenset[int]) -> bool:
    """Только ``ds_rd`` без ``ds_fd``: строки субъектов без родительской строки ФО."""
    return bool(f_rd) and not bool(f_fd)


def prune_summary_entities_fo(
    entities: list[SummaryEntity],
    f_fd: frozenset[int],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """См. :func:`build_federal_district_summary_context`.

    Режим «плоско по субъектам» включается только в :func:`_fo_subjects_only_flat_mode`;
    при непустом ``f_fd`` строки ФО сохраняются; ``f_rd`` сужает субъектов **внутри каждого ФО**
    через :func:`_fo_rd_scope_for_fd_subtree` (пустой ``f_rd`` = все субъекты выбранных ФО).
    """
    promote_subjects_without_fd_row = _fo_subjects_only_flat_mode(f_fd, f_rd)
    out: list[SummaryEntity] = []
    for e in entities:
        pe = _prune_one_fo(e, f_fd, f_rd)
        if pe is None:
            continue
        if (
            promote_subjects_without_fd_row
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


def _fo_leaf_matches(e: SummaryEntity, f_fd: frozenset[int], f_rd: frozenset[int]) -> bool:
    """Совпадение листа/узла с фильтром.

    Пустой ``f_rd`` не ограничивает субъекты: при заданном ``f_fd`` остаются все субъекты
    выбранных ФО. Непустой ``f_rd`` сужает до перечисленных субъектов; при этом ``f_fd``,
    если задан, дополнительно ограничивает по округу (субъект должен принадлежать одному из ФО).
    """
    if not f_fd and not f_rd:
        return True
    if f_fd:
        if e.id_federal_district is None or e.id_federal_district not in f_fd:
            return False
    if f_rd:
        if e.id_regional_district is None or e.id_regional_district not in f_rd:
            return False
    return True


def _fo_rd_scope_for_fd_subtree(
    f_fd: frozenset[int],
    f_rd: frozenset[int],
    fd_children: list[SummaryEntity],
) -> frozenset[int]:
    """Ограничение по субъектам для прямых потомков одного узла ФО.

    При выбранных в URL ``ds_fd`` и ``ds_rd``: если среди отмеченных субъектов есть хотя бы один
    из этого ФО — показываем только пересечение; иначе (все отмеченные из других ФО) —
    для этого ФО поддерева фильтр по субъектам снимаем — все субъекты округа.

    Режим только ``ds_rd`` (пустой ``f_fd``): без ослабления — глобальный список субъектов.
    """
    if not f_rd:
        return frozenset()
    if not f_fd:
        return f_rd
    child_rd_ids = {c.id_regional_district for c in fd_children if c.id_regional_district is not None}
    if not child_rd_ids:
        return f_rd
    inter = f_rd & child_rd_ids
    return inter if inter else frozenset()


def _prune_one_fo(e: SummaryEntity, f_fd: frozenset[int], f_rd: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_fd or f_rd)
    if e.entity_kind == "centralized_zone":
        return None if filters_on else e
    rd_for_children = f_rd
    if f_fd and e.entity_kind == "group" and e.id_federal_district is not None and e.children:
        rd_for_children = _fo_rd_scope_for_fd_subtree(f_fd, f_rd, e.children)
    new_ch: list[SummaryEntity] = []
    for c in e.children:
        pc = _prune_one_fo(c, f_fd, rd_for_children)
        if pc is not None:
            new_ch.append(pc)
    e2 = replace(e, children=new_ch)
    if new_ch:
        return e2
    if _fo_leaf_matches(e2, f_fd, f_rd):
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
    аналогично сводке по ФО при фильтре по субъектам.
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
    if e.entity_kind == "centralized_zone":
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
    if e.entity_kind == "centralized_zone":
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
    Списки и маппинги для каскадных фильтров сводки по ФО (ФО ↔ субъект РФ),
    те же связи, что в get_territorial_filter_reference_data / выгрузке Excel.
    """
    from app.generation.services.station_services.filters_services import (
        get_territorial_filter_reference_data,
    )

    t = get_territorial_filter_reference_data()
    fd_to_rd = t["fd_to_rd_mapping"]
    rd_to_fd_one = t["rd_to_fd_mapping_one"]
    return {
        "federal_district_list": t["federal_district_list"],
        "regional_district_list": t["regional_district_list"],
        "fd_to_rd_mapping": {
            str(k): (v if isinstance(v, list) else list(v)) for k, v in fd_to_rd.items()
        },
        "rd_to_fd_mapping_one": {str(k): int(v) for k, v in rd_to_fd_one.items()},
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
