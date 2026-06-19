from __future__ import annotations

import copy
import math
from collections.abc import Callable
from functools import lru_cache
from dataclasses import dataclass, field, replace
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import selectinload

from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.help_services import (
    apply_thousand_grouping_to_display,
    format_decimal_trim_for_display,
)
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
    RegionalEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.common.perimeter_variant.constants import (
    CODE_TERRITORIAL_BOUNDARIES,
    ENTITY_KIND_EES_RUSSIA,
    ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    ENTITY_KIND_RUSSIA_FEDERATION,
    EES_RUSSIA_AGGREGATE_NAME,
    EES_UNIFIED_REF_NAME,
    RUSSIA_FEDERATION_AGGREGATE_NAME,
    perimeter_variant_codes_in_legacy_nt_group,
)
from app.common.perimeter_variant.registry import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    entity_perimeter_bindings,
    is_o1_perimeter_variant_code,
    ordered_tree_variants_for_display,
    perimeter_entity_context_for_model,
    perimeter_variant_definitions,
    perimeter_variant_display_label_for_entity,
    perimeter_variant_options_for_entity,
    perimeter_variant_year_bounds_for_code,
    resolve_entity_perimeter_binding,
    resolve_entity_perimeter_variants,
    variant_label_for_entity,
    model_supports_perimeter_variant,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
    EnergyZoneDemandParameter,
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
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    synchronous_area_display_order_sort_key,
)


PLACEHOLDER_NAMES = {"не указано", "не указано2"}
_DECENTRALIZED_ZONE_REF_NAME = "Децентрализованная зона"
_TITES_AND_DZ_AGGREGATE_LABEL = "ТИТЭС и децентрализованная зона"
_TITES_SIBERIA_UES_NAME_CF = "титэссибири"
_TITES_EAST_UES_NAME_CF = "титэсвостока"
# Энергорайоны, входящие в формулу «Расчетный максимум …» (ЭЭС России) поверх ветки ТИТЭС.
_EES_AGGREGATE_TITES_EU_NAME_SPECS: tuple[tuple[str, ...], ...] = (
    ("таймыр", "норильск"),
    ("чаун", "билибин"),
    ("анад", "ский"),
    ("центральный", "магадан"),
    ("центральный", "камчат"),
    ("центральный", "сахалин"),
)
_CHUKOTKA_RD_LABEL = "Чукотский АО"
_CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL = "Чукотский АО (в территориальных границах)"
_CHUKOTKA_RES_LABEL = "ЭС Чукотского АО"
_CHUKOTKA_CHERSKY_TRANSFER_MW = 3.0
_EES_AGGREGATE_TITES_EU_MAX_POWER_SUBTRACT_MW: dict[tuple[str, ...], float] = {
    ("таймыр", "норильск"): 12.0,
    ("чаун", "билибин"): 6.6,
    ("анад", "ский"): -0.4,
    ("центральный", "магадан"): 27.0,
    ("центральный", "камчат"): 174.4,
    ("центральный", "сахалин"): -177.0,
}
_EES_AGGREGATE_TITES_EU_BASE_SUBTRACT_MW: dict[tuple[str, ...], float] = {
    ("таймыр", "норильск"): 12.0,
    ("чаун", "билибин"): 6.6,
}
_EES_AGGREGATE_TITES_EU_CHAUN_UNADJUSTED_MAX_POWER_MW = 62.0
# Если max_power «ЕЭС России без НТ» сильно выше (первая СЗ − ТИТЭС + corr), берём legacy-путь.
_EES_FORMULA_USE_LEGACY_FIRST_SA_THRESHOLD_MW = 1500.0
# Поправка к сумме ветки ТИТЭС при вычитании из первой синхронной зоны (МВт).
_EES_FORMULA_TITES_BRANCH_SUBTRACT_CORRECTION_MW = (
    _EES_AGGREGATE_TITES_EU_MAX_POWER_SUBTRACT_MW[("таймыр", "норильск")]
    + _EES_AGGREGATE_TITES_EU_MAX_POWER_SUBTRACT_MW[("чаун", "билибин")]
    + _CHUKOTKA_CHERSKY_TRANSFER_MW
)

# Не показывать в сводке по ФО (экран и Excel).
_FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF = frozenset({"новые территории"})
_NEW_TERRITORIES_NAME = "Новые территории"
_SOUTH_UES_LABELS_CF = frozenset({"оэс юга"})
_FIRST_SYNC_AREA_BASE_LABEL_CF = "первая синхронная зона"
_SECOND_SYNC_AREA_BASE_LABEL_CF = "вторая синхронная зона"
_KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF = "калининград"
_KALININGRAD_ES_NAME_CF = "эс калининградской области"


def _federal_district_excluded_from_summary(fd: FederalDistrict) -> bool:
    name = (getattr(fd, "name", None) or "").strip()
    cf = name.casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(prefix) :].strip()
            break
    return cf in _FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF

# Расчётные максимумы (МВт): всегда не более 3 знаков после запятой, независимо от «Округл».
CALCULATED_MAX_MW_ROUNDING_DIGITS = 3
CALCULATED_MAX_PARAMETER_KEYS = frozenset(
    {
        "calculated_max_power_mw",
        "calculated_max_fo_mw",
        "calculated_max_ez_mw",
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_power_consumption_mw",
    }
)

# Округление из URL влияет только на эти показатели; полная точность — в title/data-db-full.
_NUMERIC_ROUNDING_TOOLTIP_KEYS = frozenset(
    {
        "max_power",
        "combined_on_oes",
        "combined_on_ees",
        "combined_on_es",
        "combined_on_ez",
        "combined_on_fo",
        "combined_on_cz",
        "calculated_max_power_mw",
        "calculated_max_fo_mw",
        "calculated_max_ez_mw",
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_power_consumption_mw",
    }
)

BASE_PARAMETERS: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# Блок «ТИТЭС и децентрализованная зона» на сводке по ОЭС — только базовые показатели.
PARAMETERS_TITES_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# На сводке /power_demand/summary/oes/ исторический столбец только у базовых показателей.
OES_SUMMARY_HIST_PARAMETER_KEYS: frozenset[str] = frozenset(pk for pk, _ in BASE_PARAMETERS)
# Строка объединённой энергосистемы (ОЭС) в сводке «по энергосистемам».
PARAMETERS_UES_OES: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("calculated_max_power_mw", "Расчетный максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт"),
    (
        "calculated_combined_on_ees_mw",
        "Расчетный совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт",
    ),
)
# Тип энергосистемы ОЭС для расчёта «Расчетный максимум потребления мощности ЕЭС (через ОЭС)».
EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME = "ЕЭС России"

# Агрегаты «Россия с/без НТ» на сводке по ОЭС (без «Среднесуточная ТНВ»).
PARAMETERS_RUSSIA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
)
# Агрегаты «ЭЭС России с/без НТ» на сводке по ОЭС (без «Среднесуточная ТНВ»).
PARAMETERS_EES_AGGREGATE_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    (
        "calculated_max_power_consumption_mw",
        "Расчетный максимум потребления мощности, МВт",
    ),
    ("peak_datetime", "Дата и время, мск"),
)
# Агрегаты «ЕЭС России с/без НТ» на сводке по ОЭС.
PARAMETERS_EES_RUSSIA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("calculated_max_ees_russia_mw", "Расчетный максимум потребления мощности, МВт"),
    ("calculated_max_ees_via_oes_mw", "Расчетный максимум потребления мощности (через ОЭС), МВт"),
    ("calculated_max_ees_via_es_mw", "Расчетный максимум потребления мощности (через РЭС), МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
_EES_RUSSIA_AGGREGATE_DM_NAME = EesRussiaDemandParameter.__name__
PARAMETERS_WITH_OES_AND_EES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_oes", "Совмещенный максимум потребления мощности РЭС на ОЭС, МВт"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности РЭС на ЕЭС, МВт"),
)
# Энергорайон на сводке по ОЭС (и в поддереве РЭС на прочих сводках).
PARAMETERS_ENERGY_UNIT_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_es", "Совмещенный максимум потребления мощности ЭР на РЭС, МВт"),
    ("combined_on_oes", "Совмещенный максимум потребления мощности ЭР на ОЭС, МВт"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности ЭР на ЕЭС, МВт"),
)
PARAMETERS_WITH_OES_EES_AND_ES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    (
        "combined_on_es",
        "Совмещенный максимум потребления мощности субъекта РФ на РЭС, МВт",
    ),
    (
        "combined_on_oes",
        "Совмещенный максимум потребления мощности субъекта РФ на ОЭС, МВт",
    ),
    (
        "combined_on_ees",
        "Совмещенный максимум потребления мощности субъекта РФ на ЕЭС, МВт",
    ),
)
# Федеральный округ
PARAMETERS_FEDERAL_DISTRICT: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("calculated_max_fo_mw", "Расчетный максимум ФО, МВт"),
    ("combined_on_cz", "Совмещенный ФО на ЦЗ России, МВт"),
    (
        "calculated_combined_on_cz_mw",
        "Расчетный совмещенный на ЦЗ России, МВт",
    ),
)
# Субъект РФ на сводке по ФО: без ОЭС / ЕЭС / ЭС / ценовой зоны (только базовые + «на ФО»)
PARAMETERS_SUBJECT_FD_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенный на ФО, МВт"),
)
# Региональная энергосистема на сводке по энергозонам: «на энергозону» (ОЭС/ЕЭС — на странице по ОЭС)
PARAMETERS_RES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_ez", "Совмещенный на энергозону, МВт"),
)
# РЭС на сводке «коэффициенты по ФО» (дерево ФО→РЭС): на ФО и на ЦЗ России, без «на энергозону»
PARAMETERS_RES_FO_COEFF: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенный на ФО, МВт"),
    ("combined_on_cz", "Совмещенный на ЦЗ России, МВт"),
)
# Энергозона (в модели только базовые показатели + совмещённый на ЕЭС)
PARAMETERS_ENERGY_ZONE: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("calculated_max_ez_mw", "Расчетный максимум энергозоны, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности ЕЭС, МВт"),
)
# Синхронная зона на сводке по ОЭС: расчётный совмещённый максимум = сумма «Совмещенный максимум потребления мощности РЭС на ЕЭС, МВт» по РЭС зоны.
PARAMETERS_SYNCHRONOUS_AREA: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("calculated_max_power_mw", "Расчетный максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности СЗ на ЕЭС, МВт"),
    ("calculated_max_sa_mw", "Расчетный совмещенный максимум потребления мощности СЗ на ЕЭС, МВт"),
)
# «Первая синхронная зона с/без НТ» на сводке по ОЭС (без «Среднесуточная ТНВ»).
PARAMETERS_FIRST_SYNCHRONOUS_AREA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимум потребления мощности, МВт"),
    ("calculated_max_power_mw", "Расчетный максимум потребления мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности СЗ на ЕЭС, МВт"),
    ("calculated_max_sa_mw", "Расчетный совмещенный максимум потребления мощности СЗ на ЕЭС, МВт"),
)


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
    # Вариант периметра ОЭС Юга (with_nt / without_nt / without_crimea_sev); для прочих ОЭС — None.
    perimeter_variant_code: str | None = None
    # Субъекты этого ФО, с которыми связана РЭС (для фильтров ds_rd на сводке ФО→РЭС).
    fo_res_linked_regional_district_ids: frozenset[int] | None = None
    # Энергорайон децентрализованной зоны (РЭС «не указано» в справочнике).
    is_decentralized_zone_energy_unit: bool = False


def _synchronous_area_display_label(sa: SynchronousArea) -> str:
    return (getattr(sa, "name", None) or "").strip()


def _is_first_synchronous_area_name(name: str | None) -> bool:
    return (name or "").strip().casefold().startswith(_FIRST_SYNC_AREA_BASE_LABEL_CF)


def _is_second_synchronous_area_name(name: str | None) -> bool:
    return (name or "").strip().casefold().startswith(_SECOND_SYNC_AREA_BASE_LABEL_CF)


def _is_kaliningrad_synchronous_area_name(name: str | None) -> bool:
    return _KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF in (name or "").strip().casefold()


def _resolve_kaliningrad_synchronous_area_id() -> int | None:
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        if _is_kaliningrad_synchronous_area_name(sa.name):
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


def _res_parameter_year_floats_from_summary_rows(
    summary_rows: list[dict[str, Any]],
    *,
    res_id: int,
    parameter_key: str,
    years: list[int],
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Значения показателя РЭС по годам из плоских строк сводки."""
    n_y = len(years)
    dm_res = RegionalEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_res:
            continue
        if r.get("parameter_key") != parameter_key:
            continue
        row_res_id = _regional_energy_system_id_from_flat_row(r)
        if row_res_id != res_id:
            continue
        yvals = r.get("year_values") or []
        out: list[float | None] = [None] * n_y
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            out[j] = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
        return out
    return [None] * n_y


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


def _pd_nt_perimeter_variant_defs(
    binding: Any,
) -> list[Any]:
    """Варианты with_nt / without_nt для кнопки «+ НТ» на сводке нагрузок."""
    defs = perimeter_variant_definitions()
    want = (CODE_WITH_NT, CODE_WITHOUT_NT)
    if binding is not None and binding.variants:
        by_code = {v.code: v for v in binding.variants}
        picked = [by_code[c] for c in want if c in by_code]
        if picked:
            return picked
    return [defs[CODE_WITH_NT], defs[CODE_WITHOUT_NT]]


def _shift_summary_entity_depth(e: SummaryEntity, delta: int) -> SummaryEntity:
    d = int(e.depth) if e.depth is not None else 0
    new_d = max(0, d + delta)
    new_children = [_shift_summary_entity_depth(c, delta) for c in e.children]
    return replace(e, depth=new_d, children=new_children)


def _is_ees_russia_without_nt_entity(e: SummaryEntity) -> bool:
    """Агрегат «ЕЭС России без НТ» — group-root с деревом ОЭС/РЭС."""
    if e.demand_model_name != _EES_RUSSIA_AGGREGATE_DM_NAME:
        return False
    if e.perimeter_variant_code == CODE_WITHOUT_NT and e.entity_kind == "group-root":
        return True
    return e.entity_kind == "group-root" and (e.label or "").strip() == "ЕЭС России без НТ"


def _oes_promote_subjects_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по субъекту — под «ЕЭС России без НТ» только субъекты (без уровней ОЭС и РЭС)."""
    if not f_rd:
        return entities
    ues_dn = UnionEnergySystemDemandParameter.__name__
    rd_dn = RegionalDistrictDemandParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if not _is_ees_russia_without_nt_entity(e):
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
    """При фильтре по энергоузлу — под «ЕЭС России без НТ» только энергоузлы (без ОЭС, РЭС, субъекта)."""
    if not f_eu:
        return entities
    eu_dn = EnergyUnitDemandParameter.__name__

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
        if not _is_ees_russia_without_nt_entity(e):
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
    ues_dn = UnionEnergySystemDemandParameter.__name__
    res_dn = RegionalEnergySystemDemandParameter.__name__
    out: list[SummaryEntity] = []
    for e in entities:
        if not _is_ees_russia_without_nt_entity(e):
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


def _build_oes_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    """Полное дерево сводки по ОЭС без территориальных фильтров (для объединения выборов и «без фильтра»)."""
    entities: list[SummaryEntity] = (
        _build_russia_perimeter_entities()
        + _build_ees_perimeter_entities()
        + _build_ees_russia_perimeter_entities(
            always_show_subject_row_under_res=always_show_subject_row_under_res,
        )
    )

    tites_entity = _build_tites_entity()
    if tites_entity is not None:
        entities.append(tites_entity)
    return entities


def _strip_oes_ees_russia_nt_parent_aggregate(entities: list[SummaryEntity]) -> list[SummaryEntity]:
    """Убирает строки-показатели у агрегата «ЕЭС России без НТ» при территориальном фильтре."""
    out: list[SummaryEntity] = []
    for e in entities:
        if _is_ees_russia_without_nt_entity(e):
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


def _prepare_summary_demand_bulk_load() -> None:
    """Пакетная загрузка строк нагрузок (один SELECT на модель) для сводок."""
    from app.power_demand.services.pd_demand_rows_bulk_cache import (
        activate_power_demand_rows_bulk,
        preload_power_demand_rows_for_summary,
    )

    activate_power_demand_rows_bulk()
    preload_power_demand_rows_for_summary()


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
    for_client_render_shell: bool = False,
) -> dict[str, Any]:
    """Сводка по ОЭС (GET ds_ues, ds_res, ds_rd, ds_eu).

    Набор строк показателей по каждой сущности не урезается территориальными фильтрами; скрытие
    отдельных параметров — только через модальное окно «Наименование параметров» (и ``visible_rows`` при выгрузке).

    При сочетании фильтров нижний уровень сужается **отдельно в каждой ветке родителя** (как на
    сводках по ФО и энергозонам): например, выбранные субъекты РФ относятся только к одной ОЭС —
    под остальными выбранными ОЭС показываются все РЭС/субъекты/энергорайоны этой ветки; то же
    для РЭС ↔ субъектов и субъектов ↔ энергорайонов.

    Ровно один id: для одной РЭС, одного субъекта или одного энергорайона — прежнее поднятие
    строки под «ЕЭС России без НТ»; для одной ОЭС — полное поддерево (РЭС и ниже).

    ``for_client_render_shell=True`` — только метаданные страницы (годы, заголовок); строки
    таблицы загружаются отдельным JSON-запросом.
    """
    if for_client_render_shell:
        ctx = _build_summary_context(
            entities=[],
            page_title="Максимумы потребления мощности по энергосистемам",
            active_summary="oes",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        ctx["summary_rows"] = []
        return ctx
    _prepare_summary_demand_bulk_load()
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    years = list(range(dsy, dey + 1))
    ues_l, res_l, rd_l, eu_l = ([], [], [], [])
    if oes_territory_ordered is not None:
        ues_l, res_l, rd_l, eu_l = oes_territory_ordered

    has_territory_selection = bool(ues_l or res_l or rd_l or eu_l)

    if has_territory_selection:
        base_entities = copy.deepcopy(
            _build_oes_raw_entities(always_show_subject_row_under_res=bool(rd_l))
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
            page_title="Максимумы потребления мощности по энергосистемам",
            active_summary="oes",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        ctx["summary_rows"] = summary_rows
        tag_power_demand_summary_rows_for_nt_toggle(ctx["summary_rows"])
        tag_power_demand_summary_rows_for_territory_compact(ctx["summary_rows"])
        tag_power_demand_summary_rows_perimeter_variant_labels(ctx["summary_rows"])
        _inject_chukotka_rd_calculated_max_rows(
            ctx["summary_rows"], list(ctx["years"]), rounding_digits
        )
        _enrich_oes_summary_calculated_max_from_res(ctx, rounding_digits)
        _inject_oes_summary_verification_rows(ctx["summary_rows"], list(ctx["years"]))
        _inject_oes_peak_usage_hours_rows(ctx, rounding_digits)
        _attach_oes_summary_live_calc_context(ctx)
        return ctx

    entities = _build_oes_raw_entities(always_show_subject_row_under_res=False)
    ctx = _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по энергосистемам",
        active_summary="oes",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    tag_power_demand_summary_rows_for_nt_toggle(ctx["summary_rows"])
    tag_power_demand_summary_rows_for_territory_compact(ctx["summary_rows"])
    tag_power_demand_summary_rows_perimeter_variant_labels(ctx["summary_rows"])
    _inject_chukotka_rd_calculated_max_rows(
        ctx["summary_rows"], list(ctx["years"]), rounding_digits
    )
    _enrich_oes_summary_calculated_max_from_res(ctx, rounding_digits)
    _inject_oes_summary_verification_rows(ctx["summary_rows"], list(ctx["years"]))
    _inject_oes_peak_usage_hours_rows(ctx, rounding_digits)
    _attach_oes_summary_live_calc_context(ctx)
    return ctx


def _inject_oes_peak_usage_hours_rows(ctx: dict[str, Any], rounding_digits: int) -> None:
    from app.power_demand.services.pd_peak_usage_hours_services import (
        inject_oes_peak_usage_hours_rows,
    )

    inject_oes_peak_usage_hours_rows(
        ctx["summary_rows"],
        list(ctx["years"]),
        rounding_digits,
    )


# «Расчетный максимум потребления мощности …»: после каждой строки — своя «Проверка для …».
# formula_pair: (a_key, b_key) для a−b; None — формула будет добавлена позже.
_OES_VERIFY_AFTER_CALC_MAX_POWER_CONSUMPTION_SPECS: tuple[
    tuple[str, str, str, tuple[str, str] | None],
    ...,
] = (
    (
        "calculated_max_power_consumption_mw",
        "verify_for_calculated_max_power_consumption_mw",
        "Проверка максимума потребления мощности, МВт",
        ("calculated_max_power_consumption_mw", "max_power"),
    ),
    (
        "calculated_max_ees_russia_mw",
        "verify_for_calculated_max_ees_russia_mw",
        "Проверка максимума потребления мощности, МВт",
        ("calculated_max_ees_russia_mw", "max_power"),
    ),
    (
        "calculated_max_ees_via_oes_mw",
        "verify_for_calculated_max_ees_via_oes_mw",
        "Проверка максимума потребления мощности (через ОЭС), МВт",
        ("calculated_max_ees_via_oes_mw", "max_power"),
    ),
    (
        "calculated_max_ees_via_es_mw",
        "verify_for_calculated_max_ees_via_es_mw",
        "Проверка максимума потребления мощности (через ЭС), МВт",
        ("calculated_max_ees_via_es_mw", "max_power"),
    ),
    (
        "calculated_max_sa_mw",
        "verify_for_calculated_max_sa_mw",
        "Проверка расчетного совмещенного максимума потребления мощности СЗ на ЕЭС, МВт",
        ("calculated_max_sa_mw", "combined_on_ees"),
    ),
)


def _attach_oes_summary_live_calc_context(ctx: dict[str, Any]) -> None:
    """Данные для клиентского пересчёта строк «Проверка для …» на /summary/oes/."""
    res_to_sa = _build_res_to_synchronous_area_ids_map()
    second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
        _SECOND_SYNC_AREA_BASE_LABEL_CF
    )
    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    south_ues_ids = sorted(
        _south_ues_ids_for_nt_enrichment(ctx.get("summary_rows") or [])
    )
    ctx["pd_oes_live_calc_js"] = {
        "ees_russia_ues_ids": sorted(
            _union_energy_system_ids_for_energy_system_type(
                EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME
            )
        ),
        "tites_ues_ids": sorted(_tites_union_energy_system_ids()),
        "ees_aggregate_tites_eu_ids": sorted(
            _ees_aggregate_formula_tites_energy_unit_ids()
        ),
        "ees_aggregate_tites_eu_subtract_mw": {
            str(eu_id): subtract
            for eu_id, subtract in _ees_aggregate_formula_tites_eu_subtract_by_id().items()
        },
        "ees_aggregate_tites_eu_base_subtract_mw": {
            str(eu_id): subtract
            for eu_id, subtract in _ees_aggregate_formula_tites_eu_base_subtract_by_id().items()
        },
        "ees_formula_tites_branch_subtract_correction_mw": (
            _EES_FORMULA_TITES_BRANCH_SUBTRACT_CORRECTION_MW
        ),
        "ees_formula_use_legacy_first_sa_threshold_mw": (
            _EES_FORMULA_USE_LEGACY_FIRST_SA_THRESHOLD_MW
        ),
        "ees_aggregate_tites_eu_chaun_unadjusted_max_power_mw": (
            _EES_AGGREGATE_TITES_EU_CHAUN_UNADJUSTED_MAX_POWER_MW
        ),
        "first_sync_area_id": _resolve_synchronous_area_id_by_name_prefix_cf(
            _FIRST_SYNC_AREA_BASE_LABEL_CF
        ),
        "default_perimeter_variant": CODE_WITHOUT_NT,
        "res_to_sa_ids": {
            str(res_id): sorted(sa_ids) for res_id, sa_ids in res_to_sa.items()
        },
        "second_sync_area_id": second_sa_id,
        "kaliningrad_sync_area_id": kaliningrad_sa_id,
        "kaliningrad_es_id": kaliningrad_es_id,
        "south_ues_ids": south_ues_ids,
        "south_ues_id": south_ues_ids[0] if south_ues_ids else None,
        "nt_regional_district_ids": sorted(_new_territories_regional_district_ids()),
    }


def _inject_oes_summary_verification_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """
    Сводка «Максимумы» по ОЭС: добавить скрытые строки «Проверка для …» в каждом блоке сущности.

    Формулы (значения по годам — целое число; в title при наведении — до 3 знаков после запятой):
    - «Проверка максимума потребления мощности , МВт» =
        «Расчетный максимум потребления мощности, МВт» − «Максимум потребления мощности, МВт»
    - «Проверка совмещенного максимума потребления мощности ОЭС на ЕЭС, МВт» =
        «Расчетный совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт» − «Совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт»
    - После каждой строки «Расчетный максимум потребления мощности …» — своя «Проверка для …»
      (для части показателей формула будет добавлена позже).
    """
    if not summary_rows or not years:
        return

    n_y = len(years)

    def _diff_year_values(
        a_row: dict[str, Any] | None, b_row: dict[str, Any] | None
    ) -> tuple[list[str], list[str]]:
        """a - b (строки могут быть None или пустыми)."""
        if a_row is None or b_row is None:
            return (["—"] * n_y, [""] * n_y)
        a_vals = a_row.get("year_values") or []
        b_vals = b_row.get("year_values") or []
        out_vals: list[str] = []
        out_tt: list[str] = []
        for j in range(n_y):
            av = _parse_summary_cell_float(a_vals[j] if j < len(a_vals) else None)
            bv = _parse_summary_cell_float(b_vals[j] if j < len(b_vals) else None)
            if av is None or bv is None:
                out_vals.append("—")
                out_tt.append("")
                continue
            d = float(av) - float(bv)
            out_vals.append(_format_numeric(d, -1))
            out_tt.append(_format_calculated_max_mw(d))
        return out_vals, out_tt

    def _inject_one(
        *,
        block_start: int,
        block_size: int,
        insert_after_parameter_key: str,
        new_parameter_key: str,
        new_parameter_label: str,
        a_parameter_key: str | None = None,
        b_parameter_key: str | None = None,
    ) -> None:
        if block_size < 1:
            return
        end = min(block_start + block_size, len(summary_rows))
        block0 = summary_rows[block_start]
        # Индекс вставки — сразу после строки insert_after_parameter_key, иначе в конец блока.
        insert_at = end
        a_row = None
        b_row = None
        for i in range(block_start, end):
            pk = str(summary_rows[i].get("parameter_key") or "")
            if pk == insert_after_parameter_key:
                insert_at = i + 1
            if a_parameter_key and pk == a_parameter_key:
                a_row = summary_rows[i]
            if b_parameter_key and pk == b_parameter_key:
                b_row = summary_rows[i]
        if a_parameter_key and b_parameter_key:
            year_values, year_tooltips = _diff_year_values(a_row, b_row)
        else:
            year_values, year_tooltips = (["—"] * n_y, [""] * n_y)

        old_span = block_size
        new_span = old_span + 1
        for k in range(block_start, end):
            summary_rows[k]["entity_rowspan"] = new_span

        note_text = str(block0.get("entity_note_text") or "")
        note_rid = block0.get("entity_note_row_id")
        new_row: dict[str, Any] = {
            "entity_label": block0.get("entity_label"),
            "entity_rowspan": new_span,
            "entity_depth": block0.get("entity_depth", 0),
            "entity_kind": block0.get("entity_kind"),
            "show_entity_cell": False,
            "parameter_key": new_parameter_key,
            "parameter_label": new_parameter_label,
            "demand_model_name": None,
            "parent_fk_column": block0.get("parent_fk_column"),
            "parent_id": block0.get("parent_id"),
            "hist_row_id": None,
            "year_row_ids": [None] * n_y,
            "hist_value": "",
            "year_values": list(year_values),
            "hist_numeric_tooltip": "",
            "year_numeric_tooltips": list(year_tooltips),
            "id_union_energy_system": block0.get("id_union_energy_system"),
            "year_coeff_k_stored": [],
            "entity_note_text": note_text,
            "entity_note_row_id": note_rid,
            "show_entity_note_cell": False,
            "pd_pd_verify_for_row": True,
            "pd_pd_nt_extra_row": block0.get("pd_pd_nt_extra_row"),
            "pd_pd_entity_label_compact_nt": block0.get(
                "pd_pd_entity_label_compact_nt"
            ),
            "perimeter_variant_code": block0.get("perimeter_variant_code"),
        }
        if a_parameter_key and b_parameter_key:
            new_row["pd_pd_verify_a_parameter_key"] = a_parameter_key
            new_row["pd_pd_verify_b_parameter_key"] = b_parameter_key
        summary_rows.insert(insert_at, new_row)

    # Проходим блоки сущностей по show_entity_cell и entity_rowspan.
    i = 0
    while i < len(summary_rows):
        row0 = summary_rows[i]
        if not row0.get("show_entity_cell"):
            i += 1
            continue
        span = int(row0.get("entity_rowspan") or 1)
        if span < 1:
            span = 1
        # Ключи в блоке — определяем, что именно можно проверять.
        end = min(i + span, len(summary_rows))
        keys_in_block = {str(summary_rows[j].get("parameter_key") or "") for j in range(i, end)}

        # 1) ОЭС: расчетный максимум ОЭС − максимум.
        if {"calculated_max_power_mw", "max_power"} <= keys_in_block:
            _inject_one(
                block_start=i,
                block_size=span,
                insert_after_parameter_key="calculated_max_power_mw",
                new_parameter_key="verify_for_calculated_max_power_mw",
                new_parameter_label="Проверка максимума потребления мощности, МВт",
                a_parameter_key="calculated_max_power_mw",
                b_parameter_key="max_power",
            )
            span += 1
            end += 1
            keys_in_block.add("verify_for_calculated_max_power_mw")

        # 2) ОЭС: расчетный совмещенный на ЕЭС − совмещенный на ЕЭС.
        if {"calculated_combined_on_ees_mw", "combined_on_ees"} <= keys_in_block:
            _inject_one(
                block_start=i,
                block_size=span,
                insert_after_parameter_key="calculated_combined_on_ees_mw",
                new_parameter_key="verify_for_calculated_combined_on_ees_mw",
                new_parameter_label="Проверка совмещенного максимума потребления мощности ОЭС на ЕЭС, МВт",
                a_parameter_key="calculated_combined_on_ees_mw",
                b_parameter_key="combined_on_ees",
            )
            span += 1
            end += 1
            keys_in_block.add("verify_for_calculated_combined_on_ees_mw")

        # 3) «Расчетный максимум потребления мощности …»: своя «Проверка для …» сразу после строки.
        for (
            calc_key,
            verify_key,
            verify_label,
            formula_pair,
        ) in _OES_VERIFY_AFTER_CALC_MAX_POWER_CONSUMPTION_SPECS:
            if calc_key not in keys_in_block or verify_key in keys_in_block:
                continue
            if (
                calc_key == "calculated_max_sa_mw"
                and str(row0.get("entity_kind") or "") != "synchronous_area"
            ):
                continue
            a_key, b_key = formula_pair if formula_pair else (None, None)
            _inject_one(
                block_start=i,
                block_size=span,
                insert_after_parameter_key=calc_key,
                new_parameter_key=verify_key,
                new_parameter_label=verify_label,
                a_parameter_key=a_key,
                b_parameter_key=b_key,
            )
            span += 1
            end += 1
            keys_in_block.add(verify_key)

        i += max(span, 1)


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
    fo_aggregate_by_res: bool = False,
    for_client_render_shell: bool = False,
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

    При ``fo_aggregate_by_res=True`` под каждым ФО выводятся строки РЭС; если в РЭС в этом ФО
    больше одного субъекта — дополнительно строки субъектов (без энергоузлов). Фильтр ``ds_res``
    оставляет РЭС, связанные хотя бы с одним из выбранных субъектов данного ФО, и сужает
    дочерние строки субъектов.

    ``for_client_render_shell=True`` — только метаданные страницы без строк таблицы.
    """
    if for_client_render_shell:
        return _build_summary_context(
            entities=[],
            page_title="Максимумы потребления мощности по ФО",
            active_summary="fo",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
    _prepare_summary_demand_bulk_load()
    entities: list[SummaryEntity] = [
        _standalone_entity(
            "ЦЗ России",
            CentralizedZoneDemandParameter,
            BASE_PARAMETERS,
            entity_kind="centralized_zone",
        ),
    ]
    entities.extend(
        _build_federal_district_entities_by_res()
        if fo_aggregate_by_res
        else _build_federal_district_entities()
    )

    if fo_filter_sets is not None:
        f_fd, f_res = fo_filter_sets
        if f_fd or f_res:
            entities = prune_summary_entities_fo(entities, f_fd, f_res)

    ctx = _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по ФО",
        active_summary="fo",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    _enrich_fo_summary_calculated_max_from_res(ctx, rounding_digits)
    _inject_fo_max_cz_russia_calculated_max_row(
        ctx["summary_rows"],
        list(ctx["years"]),
        int(ctx["rounding_digits"]),
    )
    tag_power_demand_summary_rows_for_nt_toggle(ctx["summary_rows"])
    tag_power_demand_summary_rows_for_territory_compact(ctx["summary_rows"])
    tag_power_demand_summary_rows_perimeter_variant_labels(ctx["summary_rows"])
    return ctx


def _inject_fo_max_cz_russia_calculated_max_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """На сводке «Максимумы по ФО»: строка под «ЦЗ России» = сумма «Совмещенный ФО на ЦЗ России, МВт» по всем ФО."""
    if not summary_rows or not years:
        return

    cz_start: int | None = None
    cz_span = 0
    block0: dict[str, Any] | None = None
    for i, row in enumerate(summary_rows):
        if row.get("show_entity_cell") and row.get("entity_kind") == "centralized_zone":
            cz_start = i
            cz_span = int(row.get("entity_rowspan") or 1)
            block0 = row
            break
    if cz_start is None or block0 is None or cz_span < 1:
        return

    # Вставляем сразу после строки «Среднесуточная ТНВ, °C» в блоке ЦЗ России (если она есть).
    insert_at = cz_start + cz_span
    for j in range(cz_start, min(cz_start + cz_span, len(summary_rows))):
        if str(summary_rows[j].get("parameter_key") or "") == "avg_temp":
            insert_at = j + 1
            break

    n_y = len(years)
    fd_dm = FederalDistrictDemandParameter.__name__
    sum_vals = [0.0] * n_y
    any_vals = [False] * n_y
    for r in summary_rows:
        if str(r.get("demand_model_name") or "") != fd_dm:
            continue
        if str(r.get("parameter_key") or "") != "combined_on_cz":
            continue
        yv = r.get("year_values") or []
        for ix in range(n_y):
            cell = yv[ix] if ix < len(yv) else None
            v = _parse_summary_cell_float(cell)
            if v is None:
                continue
            sum_vals[ix] += float(v)
            any_vals[ix] = True

    year_values: list[str] = []
    year_tooltips: list[str] = []
    year_row_ids: list[int | None] = [None] * n_y
    for ix in range(n_y):
        if not any_vals[ix]:
            year_values.append("—")
            year_tooltips.append("")
            continue
        v = float(sum_vals[ix])
        year_values.append(_format_numeric(v, rounding_digits))
        year_tooltips.append(_format_full_numeric_tooltip(v))

    old_span = cz_span
    new_span = old_span + 1
    for k in range(cz_start, min(cz_start + old_span, len(summary_rows))):
        summary_rows[k]["entity_rowspan"] = new_span

    note_text = str(block0.get("entity_note_text") or "")
    note_rid = block0.get("entity_note_row_id")
    summary_rows.insert(
        insert_at,
        {
            "entity_label": block0.get("entity_label"),
            "entity_rowspan": new_span,
            "entity_depth": block0.get("entity_depth", 0),
            "entity_kind": block0.get("entity_kind"),
            "show_entity_cell": False,
            "parameter_key": "cz_calculated_max_cz_russia_mw",
            "parameter_label": "Расчетный максимум ЦЗ России, МВт",
            "demand_model_name": None,
            "parent_fk_column": block0.get("parent_fk_column"),
            "parent_id": block0.get("parent_id"),
            "hist_row_id": None,
            "year_row_ids": list(year_row_ids),
            "hist_value": "",
            "year_values": list(year_values),
            "hist_numeric_tooltip": "",
            "year_numeric_tooltips": list(year_tooltips),
            "id_union_energy_system": block0.get("id_union_energy_system"),
            "year_coeff_k_stored": [],
            "entity_note_text": note_text,
            "entity_note_row_id": note_rid,
            "show_entity_note_cell": False,
            "pd_fo_cz_calc_max_tooltip": (
                "Расчетный максимум ЦЗ России, МВт = "
                "Σ(«Совмещенный ФО на ЦЗ России, МВт») по всем федеральным округам."
            ),
            "pd_formula_text_key": "fo_cz_calc_max",
        },
    )


def _build_ez_raw_entities() -> list[SummaryEntity]:
    entities: list[SummaryEntity] = [
        SummaryEntity(
            label=EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME,
            depth=0,
            parameters=(
                *BASE_PARAMETERS,
                ("calculated_max_ees_russia_mw", "Расчетный максимум потребления мощности ЕЭС России, МВт"),
            ),
            demand_rows=dps.get_demand_rows_for_summary_block(
                EesRussiaDemandParameter,
                None,
                None,
                display_perimeter_variant_code=CODE_WITHOUT_NT,
            ),
            entity_kind="ees_russia",
            demand_model_name=EesRussiaDemandParameter.__name__,
            parent_fk_column=None,
            parent_id=None,
            perimeter_variant_code=CODE_WITHOUT_NT,
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
    for_client_render_shell: bool = False,
) -> dict[str, Any]:
    """Сводка по энергозонам (GET ds_ez, ds_res).

    Набор строк показателей по сущности не урезается территориальными фильтрами; скрытие
    параметров — модальное окно «Наименование параметров» и ``visible_rows`` при выгрузке.

    Без фильтров — «ЕЭС России» и полное дерево энергозона → РЭС → …

    Только ``ds_ez`` — выбранные зоны со всеми РЭС внутри.

    ``ds_ez`` + ``ds_res`` — каждая выбранная зона; РЭС сужаются **по зоне**: если в ``ds_res``
    есть РЭС из этой зоны — только они, иначе все РЭС зоны (как на сводке по ФО).

    Только ``ds_res`` (без ``ds_ez``) — плоский список по выбранным РЭС без строки энергозоны.

    ``for_client_render_shell=True`` — только метаданные страницы без строк таблицы.
    """
    if for_client_render_shell:
        return _build_summary_context(
            entities=[],
            page_title="Максимумы потребления мощности по энергозонам",
            active_summary="ez",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
    _prepare_summary_demand_bulk_load()
    dsy, dey = _effective_data_year_bounds(
        start_year, end_year, data_start_year, data_end_year
    )
    years = list(range(dsy, dey + 1))
    ez_l: list[int] = []
    res_l: list[int] = []
    if ez_territory_ordered is not None:
        ez_l, res_l = ez_territory_ordered

    if ez_l or res_l:
        base_entities = copy.deepcopy(_build_ez_raw_entities())
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
            page_title="Максимумы потребления мощности по энергозонам",
            active_summary="ez",
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            data_start_year=data_start_year,
            data_end_year=data_end_year,
            filter_year_list=filter_year_list,
            avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
        )
        ctx["summary_rows"] = summary_rows
        _enrich_ez_summary_calculated_max_from_res(ctx, rounding_digits)
        tag_power_demand_summary_rows_for_nt_toggle(ctx["summary_rows"])
        tag_power_demand_summary_rows_for_territory_compact(ctx["summary_rows"])
        tag_power_demand_summary_rows_perimeter_variant_labels(ctx["summary_rows"])
        return ctx

    entities = _build_ez_raw_entities()
    ctx = _build_summary_context(
        entities=entities,
        page_title="Максимумы потребления мощности по энергозонам",
        active_summary="ez",
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    _enrich_ez_summary_calculated_max_from_res(ctx, rounding_digits)
    tag_power_demand_summary_rows_for_nt_toggle(ctx["summary_rows"])
    tag_power_demand_summary_rows_for_territory_compact(ctx["summary_rows"])
    tag_power_demand_summary_rows_perimeter_variant_labels(ctx["summary_rows"])
    return ctx


def build_oes_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
) -> dict[str, Any]:
    """Те же данные и логика, что у «Максимумы по энергосистемам»; отдельный экран и заголовок."""
    ctx = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=oes_territory_ordered,
        avg_temp_uses_global_rounding=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергосистемам"
    return ctx


def _inject_fo_coeff_cz_total_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Три вычисляемые строки сразу под параметрами «ЦЗ России» на сводке coeff по ФО (дерево ФО→РЭС)."""
    if not summary_rows or not years:
        return
    cz_dm = CentralizedZoneDemandParameter.__name__
    fd_dm = FederalDistrictDemandParameter.__name__
    res_dm = RegionalEnergySystemDemandParameter.__name__
    n_y = len(years)
    cz_start: int | None = None
    old_span = 0
    block0: dict[str, Any] | None = None
    for i, row in enumerate(summary_rows):
        if row.get("show_entity_cell") and row.get("entity_kind") == "centralized_zone":
            cz_start = i
            old_span = int(row.get("entity_rowspan") or 1)
            block0 = row
            break
    if cz_start is None or block0 is None or old_span < 1:
        return
    insert_at = cz_start + old_span

    cz_max_vals: list[float | None] = [None] * n_y
    sum_max_power_fd_res = [0.0] * n_y
    sum_max_power_any = [False] * n_y
    sum_res = [0.0] * n_y
    sum_res_any = [False] * n_y

    for r in summary_rows:
        dm = str(r.get("demand_model_name") or "")
        pk = str(r.get("parameter_key") or "")
        yv = r.get("year_values") or []
        for j in range(n_y):
            cell = yv[j] if j < len(yv) else None
            v = _parse_summary_cell_float(cell)
            if v is None:
                continue
            if dm == cz_dm and pk == "max_power":
                cz_max_vals[j] = float(v)
            elif dm == fd_dm and pk == "max_power":
                sum_max_power_fd_res[j] += float(v)
                sum_max_power_any[j] = True
            elif dm == res_dm and pk == "max_power":
                sum_max_power_fd_res[j] += float(v)
                sum_max_power_any[j] = True
            elif dm == res_dm and pk == "combined_on_cz":
                sum_res[j] += float(v)
                sum_res_any[j] = True

    imb: list[float | None] = []
    imb_any: list[bool] = []
    for j in range(n_y):
        c = cz_max_vals[j]
        if not sum_res_any[j]:
            imb.append(None)
            imb_any.append(False)
            continue
        s = sum_res[j]
        if c is None:
            imb.append(None)
            imb_any.append(False)
        else:
            imb.append(float(c) - float(s))
            imb_any.append(True)

    def _fmt_vals(vals: list[float | None], any_flag: list[bool]) -> tuple[list[str], list[str], list[int | None]]:
        yv_out: list[str] = []
        yt_out: list[str] = []
        yr_ids: list[int | None] = [None] * n_y
        for j in range(n_y):
            v = vals[j]
            if not any_flag[j] or v is None:
                yv_out.append("—")
                yt_out.append("")
            else:
                yv_out.append(_format_numeric(v, rounding_digits))
                yt_out.append(_format_full_numeric_tooltip(v))
        return yv_out, yt_out, yr_ids

    y1, t1, id1 = _fmt_vals(
        [sum_max_power_fd_res[j] if sum_max_power_any[j] else None for j in range(n_y)],
        sum_max_power_any,
    )
    y2, t2, id2 = _fmt_vals(
        [sum_res[j] if sum_res_any[j] else None for j in range(n_y)],
        sum_res_any,
    )
    y3, t3, id3 = _fmt_vals(imb, imb_any)

    tt = (
        "Сумма значений «Максимум потребления мощности, МВт» по строкам федеральных округов "
        "и по строкам региональных энергосистем, отображаемым в таблице (без строки «ЦЗ России»). "
        "Учитываются максимумы и на уровне ФО, и на уровне РЭС под округами.",
        "Сумма значений «Совмещенный на ЦЗ России, МВт» по всем строкам региональных энергосистем, "
        "показанным в таблице под соответствующими федеральными округами.",
        "Разность между «Максимум потребления мощности, МВт» для сущности «ЦЗ России» "
        "и суммой совмещённых на ЦЗ России максимумов региональных энергосистем (предыдущая строка блока).",
    )
    new_specs: tuple[tuple[str, str, list[str], list[str], list[int | None], str, str], ...] = (
        (
            "cz_total_sum_fo_max_power",
            "Сумма максимумов потребления ФО, МВт",
            y1,
            t1,
            id1,
            tt[0],
            "fo_coeff_cz_total_sum_fo_max",
        ),
        (
            "cz_total_sum_res_combined_cz",
            "Сумма совмещенных на ЦЗ России максимумов региональных энергосистем, МВт",
            y2,
            t2,
            id2,
            tt[1],
            "fo_coeff_cz_total_sum_res_combined_cz",
        ),
        (
            "cz_total_imbalance_mw",
            "Небаланс, МВт",
            y3,
            t3,
            id3,
            tt[2],
            "fo_coeff_cz_total_imbalance",
        ),
    )
    new_span = old_span + len(new_specs)
    for j in range(cz_start, min(cz_start + old_span, len(summary_rows))):
        summary_rows[j]["entity_rowspan"] = new_span

    note_text = str(block0.get("entity_note_text") or "")
    note_rid = block0.get("entity_note_row_id")

    to_insert: list[dict[str, Any]] = []
    for pk, label, yv_l, ynt_l, yrid_l, tt_expl, formula_key in new_specs:
        to_insert.append(
            {
                "entity_label": block0.get("entity_label"),
                "entity_rowspan": new_span,
                "entity_depth": block0.get("entity_depth", 0),
                "entity_kind": block0.get("entity_kind"),
                "show_entity_cell": False,
                "parameter_key": pk,
                "parameter_label": label,
                "demand_model_name": None,
                "parent_fk_column": block0.get("parent_fk_column"),
                "parent_id": block0.get("parent_id"),
                "hist_row_id": None,
                "year_row_ids": list(yrid_l),
                "hist_value": "—",
                "year_values": list(yv_l),
                "hist_numeric_tooltip": "",
                "year_numeric_tooltips": list(ynt_l),
                "id_union_energy_system": block0.get("id_union_energy_system"),
                "year_coeff_k_stored": [],
                "entity_note_text": note_text,
                "entity_note_row_id": note_rid,
                "show_entity_note_cell": False,
                "pd_fo_coeff_cz_total": True,
                "pd_fo_coeff_cz_total_tooltip": tt_expl,
                "pd_formula_text_key": formula_key,
            }
        )
    for ii, nr in enumerate(to_insert):
        summary_rows.insert(insert_at + ii, nr)


def build_federal_district_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    fo_filter_sets: tuple[frozenset[int], frozenset[int]] | None = None,
) -> dict[str, Any]:
    ctx = build_federal_district_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        fo_filter_sets=fo_filter_sets,
        avg_temp_uses_global_rounding=True,
        fo_aggregate_by_res=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по ФО"
    _inject_fo_coeff_cz_total_rows(
        ctx["summary_rows"],
        list(ctx["years"]),
        int(ctx["rounding_digits"]),
    )
    return ctx


def build_energy_zones_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    ez_territory_ordered: tuple[list[int], list[int]] | None = None,
) -> dict[str, Any]:
    ctx = build_energy_zones_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        ez_territory_ordered=ez_territory_ordered,
        avg_temp_uses_global_rounding=True,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергозонам"
    return ctx


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
    return {
        "page_title": page_title,
        "summary_rows": _flatten_entities(
            entities, years, rounding_digits, avg_temp_uses_global_rounding=avg_temp_uses_global_rounding
        ),
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
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_oes",
        "calculated_max_power_mw",
        "combined_on_ees",
        "calculated_combined_on_ees_mw",
        "calculated_max_sa_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "combined_on_es",
        "calculated_max_power_consumption_mw",
    }
)
FO_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "cz_calculated_max_cz_russia_mw",
        "calculated_max_fo_mw",
        "calculated_combined_on_cz_mw",
        "combined_on_fo",
    }
)
# Экран «Коэффициенты по ФО»: под ФО — РЭС (на ФО, на ЦЗ России), без субъектов.
FO_COEFF_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "combined_on_fo",
        # Итоговые строки под «ЦЗ России» (только экран coeff/ФО).
        "cz_total_sum_fo_max_power",
        "cz_total_sum_res_combined_cz",
        "cz_total_imbalance_mw",
    }
)
# Служебные строки-суммы под блоком «ЦЗ России» на сводке coeff по ФО.
FO_COEFF_CZ_TOTAL_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "cz_total_sum_fo_max_power",
        "cz_total_sum_res_combined_cz",
        "cz_total_imbalance_mw",
    }
)
EZ_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "calculated_max_ees_russia_mw",
        "calculated_max_ez_mw",
        "combined_on_ez",
        "combined_on_ees",
    }
)


_PD_OES_NT_EXTRA_ENTITY_LABELS = frozenset(
    {
        "Россия с НТ",
        "ЭЭС России с НТ",
        "ЕЭС России с НТ",
        "Первая синхронная зона с НТ",
        "ОЭС Юга с НТ",
    }
)
_PD_OES_NT_COMPACT_ENTITY_LABELS: dict[str, str] = {
    "Россия без НТ": "Россия",
    "ЭЭС России без НТ": "ЭЭС России",
    "ЕЭС России без НТ": "ЕЭС России",
    "Первая синхронная зона без НТ": "Первая синхронная зона",
    "ОЭС Юга без НТ": "ОЭС Юга",
}
_EES_DEMAND_MODEL_NAME = EesDemandParameter.__name__
_EES_RUSSIA_DEMAND_MODEL_NAME = EesRussiaDemandParameter.__name__
_UES_DEMAND_MODEL_NAME = UnionEnergySystemDemandParameter.__name__

def tag_power_demand_summary_rows_for_nt_toggle(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Метки для кнопки «+ НТ» на сводках ОЭС/ФО/энергозон (скрытие «с НТ», короткие подписи «без НТ»)."""
    if not summary_rows:
        return
    stack: list[int] = []
    for row in summary_rows:
        label = str(row.get("entity_label") or "").strip()
        ek = str(row.get("entity_kind") or "")
        d = int(row.get("entity_depth", 0) or 0)

        pvc_row = row.get("perimeter_variant_code")

        if row.get("show_entity_cell"):
            while stack and d <= stack[-1]:
                stack.pop()
            if (
                _NEW_TERRITORIES_NAME in label
                or (ek == "group-root" and _NEW_TERRITORIES_NAME in label)
                or pvc_row == CODE_WITH_NT
                or (
                    ek == "perimeter_variant"
                    and CODE_WITH_NT in label.casefold()
                )
            ):
                stack.append(d)

        in_nt_tree = bool(stack)

        if pvc_row == CODE_WITH_NT:
            row["pd_pd_nt_extra_row"] = True
        elif (
            pvc_row == CODE_WITHOUT_NT
            and row.get("demand_model_name") == _EES_DEMAND_MODEL_NAME
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = EES_RUSSIA_AGGREGATE_NAME
        elif (
            pvc_row == CODE_WITHOUT_NT
            and row.get("demand_model_name") == _EES_RUSSIA_DEMAND_MODEL_NAME
            and ek in ("oes_top_aggregate", "group-root")
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = EES_UNIFIED_REF_NAME
        elif pvc_row == CODE_WITHOUT_NT and label.startswith("Россия"):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = "Россия"
        elif pvc_row == CODE_WITHOUT_NT and label.startswith("ЕЭС России"):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = "ЕЭС России"
        elif (
            pvc_row == CODE_WITHOUT_NT
            and row.get("demand_model_name") == _UES_DEMAND_MODEL_NAME
            and ek == "perimeter_variant"
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = "ОЭС Юга"
        elif label in _PD_OES_NT_COMPACT_ENTITY_LABELS:
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = _PD_OES_NT_COMPACT_ENTITY_LABELS[label]
        elif label in _PD_OES_NT_EXTRA_ENTITY_LABELS:
            row["pd_pd_nt_extra_row"] = True
        else:
            row["pd_pd_nt_extra_row"] = in_nt_tree

        if row.get("pd_pd_entity_label_compact_nt"):
            row["pd_pd_skip_empty_hide_row"] = True


def tag_power_demand_oes_summary_rows_for_nt_toggle(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Обратная совместимость: см. :func:`tag_power_demand_summary_rows_for_nt_toggle`."""
    tag_power_demand_summary_rows_for_nt_toggle(summary_rows)


_PD_SUMMARY_NO_PERIMETER_VARIANT_SELECT_MODELS = frozenset(
    {
        "EnergyZoneDemandParameter",
        "EnergySystemTypeDemandParameter",
    }
)


def _pd_summary_row_allows_perimeter_variant_select(row: dict[str, Any]) -> bool:
    """Строка блока сущности, для которой в сводке можно менять perimeter_variant_code."""
    if not row.get("show_entity_cell"):
        return False
    dm_name = str(row.get("demand_model_name") or "").strip()
    if not dm_name or dm_name in _PD_SUMMARY_NO_PERIMETER_VARIANT_SELECT_MODELS:
        return False
    if row.get("pd_pd_verify_for_row"):
        return False
    if row.get("pd_pd_aggregation_level_row"):
        return False
    from app.power_demand.services import demand_parameter_services as dps

    try:
        model_cls = dps._summary_demand_model_class(dm_name)
    except ValueError:
        return False
    if not model_supports_perimeter_variant(model_cls):
        return False
    has_code = bool(str(row.get("perimeter_variant_code") or "").strip())
    options = row.get("perimeter_variant_options") or []
    if has_code or len(options) >= 1:
        return True
    return bool(row.get("pd_ec_perimeter_entity_kind"))


def tag_power_demand_summary_rows_perimeter_variant_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Подпись и привязка варианта периметра для столбца сводки нагрузок."""
    from app.power_demand.services import demand_parameter_services as dps

    pe_context_cache: dict[tuple[str, str | None, int | None], tuple[str, str] | None] = {}
    for row in summary_rows:
        code = row.get("perimeter_variant_code")
        dm = row.get("demand_model_name") or ""
        if row.get("show_entity_cell") and dm:
            try:
                model_cls = dps._summary_demand_model_class(dm)
                code = dps.resolve_stored_perimeter_variant_for_summary_block(
                    model_cls,
                    parent_fk_column=row.get("parent_fk_column"),
                    parent_id=row.get("parent_id"),
                    display_perimeter_variant_code=code,
                )
                if code:
                    row["perimeter_variant_code"] = code
            except ValueError:
                pass
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
        row["perimeter_variant_label"] = (
            perimeter_variant_display_label_for_entity(code, pe_kind, pe_name) if code else ""
        )
        if code:
            fy, ty = perimeter_variant_year_bounds_for_code(str(code))
            row["perimeter_variant_from_year"] = fy
            row["perimeter_variant_to_year"] = ty
        else:
            row.pop("perimeter_variant_from_year", None)
            row.pop("perimeter_variant_to_year", None)
        if is_o1_perimeter_variant_code(code):
            row["pd_ec_o1_form_row"] = True
        else:
            row.pop("pd_ec_o1_form_row", None)
        if row.get("show_entity_cell") and pe_kind:
            row["perimeter_variant_options"] = perimeter_variant_options_for_entity(
                pe_kind, pe_name
            )
            allowed_codes = {
                str(opt.get("code") or "").strip()
                for opt in row["perimeter_variant_options"]
                if opt.get("code")
            }
            if code and allowed_codes and str(code) not in allowed_codes:
                if str(code) in (CODE_WITH_NT, CODE_WITHOUT_NT):
                    code = None
                    row["perimeter_variant_code"] = None
        elif row.get("show_entity_cell"):
            row["perimeter_variant_options"] = []
        row["show_perimeter_variant_select"] = _pd_summary_row_allows_perimeter_variant_select(
            row
        )


def tag_power_demand_summary_rows_for_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Метки для кнопки «Сводная таблица»: скрытие РЭС, субъектов РФ и энергорайонов."""
    res_mn = RegionalEnergySystemDemandParameter.__name__
    rd_mn = RegionalDistrictDemandParameter.__name__
    eu_mn = EnergyUnitDemandParameter.__name__
    for row in summary_rows:
        if row.get("pd_pd_nt_extra_row"):
            row["pd_pd_territory_detail_row"] = False
            continue
        dm_l = str(row.get("demand_model_name") or "").strip()
        row["pd_pd_territory_detail_row"] = dm_l in (res_mn, rd_mn, eu_mn)


def apply_power_demand_summary_territory_compact_export_ui(
    summary_rows: list[dict[str, Any]],
    *,
    territory_compact_on: bool,
) -> list[dict[str, Any]]:
    """Выгрузка Excel: те же строки, что на экране при включённой «Сводная таблица»."""
    if not territory_compact_on:
        return list(summary_rows)
    return [row for row in summary_rows if not row.get("pd_pd_territory_detail_row")]


def apply_power_demand_summary_nt_export_ui(
    summary_rows: list[dict[str, Any]],
    *,
    nt_detail_on: bool,
) -> list[dict[str, Any]]:
    """Выгрузка Excel: те же строки и подписи, что на экране при выключенной кнопке «+ НТ»."""
    if nt_detail_on:
        return list(summary_rows)
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        if row.get("pd_pd_nt_extra_row"):
            continue
        rc = dict(row)
        compact = row.get("pd_pd_entity_label_compact_nt")
        if compact:
            rc["entity_label"] = compact
        out.append(rc)
    return out


def apply_power_demand_oes_summary_nt_export_ui(
    summary_rows: list[dict[str, Any]],
    *,
    nt_detail_on: bool,
) -> list[dict[str, Any]]:
    """Обратная совместимость: см. :func:`apply_power_demand_summary_nt_export_ui`."""
    return apply_power_demand_summary_nt_export_ui(
        summary_rows, nt_detail_on=nt_detail_on
    )


def parse_power_demand_export_nt_detail(*, default: bool = False) -> bool:
    from flask import request

    raw = request.args.get("export_nt_detail")
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def parse_power_demand_export_territory_compact(*, default: bool = False) -> bool:
    from flask import request

    raw = request.args.get("export_territory_compact")
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


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
        filtered_block = [
            r
            for r in block
            if r.get("pd_pd_aggregation_level_row")
            or (r.get("parameter_key") or "") in keys
        ]
        for j, r in enumerate(filtered_block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(filtered_block)
            out.append(rc)
        i += block_size
    return out


def slice_power_demand_summary_context_for_export_years(
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
    new_context["year_is_plan"] = {y: bool(yip_all.get(y, False)) for y in export_years}
    new_rows: list[dict[str, Any]] = []
    list_keys = (
        "year_values",
        "year_row_ids",
        "year_numeric_tooltips",
        "year_k_values",
        "year_k_full_tooltips",
        "year_coeff_k_stored",
    )
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


COEFF_K_CALC_DECIMAL_PLACES = 6


def _round_coeff_k_calc(value: float) -> float:
    """Ограничение точности при расчёте k = значение / макс. мощность (сводки «Коэффициенты…»)."""
    if not math.isfinite(value):
        return value
    return round(value, COEFF_K_CALC_DECIMAL_PLACES)


def _parse_summary_cell_float(value: Any) -> float | None:
    """Разбор числа из ячейки сводки (как на экране: пробелы, запятая)."""
    if value in (None, ""):
        return None
    s = str(value).strip()
    if s in ("—", "-"):
        return None
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    s = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def _ues_row_uses_standard_oes_aggregation(row: dict[str, Any]) -> bool:
    """Одна строка ОЭС в суммах/расчётах по РЭС (для вариантов — только территориальный базовый)."""
    code = row.get("perimeter_variant_code")
    if code is None:
        return True
    return str(code) == CODE_WITHOUT_NT


def _ues_row_included_for_ees_russia_aggregate_variant(
    row: dict[str, Any],
    ees_russia_perimeter_variant: str | None,
) -> bool:
    """Строка ОЭС для «Расчетный максимум потребления мощности ЕЭС России»: вариант ОЭС согласован с агрегатом с/без НТ."""
    row_code = row.get("perimeter_variant_code")
    if row_code is None:
        return True
    target = ees_russia_perimeter_variant or CODE_WITHOUT_NT
    target_s = str(target)
    row_s = str(row_code)
    if target_s in perimeter_variant_codes_in_legacy_nt_group(CODE_WITH_NT):
        return row_s in perimeter_variant_codes_in_legacy_nt_group(CODE_WITH_NT)
    if target_s in perimeter_variant_codes_in_legacy_nt_group(CODE_WITHOUT_NT):
        return row_s in perimeter_variant_codes_in_legacy_nt_group(CODE_WITHOUT_NT)
    return row_s == target_s


def _union_energy_system_id_from_flat_row(row: dict[str, Any]) -> int | None:
    """id ОЭС в строке сводки: id_union_energy_system или parent_id при parent_fk = id_union_energy_system."""
    raw = row.get("id_union_energy_system")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if row.get("parent_fk_column") == "id_union_energy_system" and row.get("parent_id") is not None:
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            pass
    return None


def _regional_energy_system_id_from_flat_row(row: dict[str, Any]) -> int | None:
    """id РЭС в строке сводки."""
    raw = row.get("id_regional_energy_system")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if (
        row.get("parent_fk_column") == "id_regional_energy_system"
        and row.get("parent_id") is not None
    ):
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            pass
    return None


def _regional_district_id_from_flat_row(row: dict[str, Any]) -> int | None:
    """id субъекта РФ в строке сводки."""
    raw = row.get("id_regional_district")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if (
        row.get("parent_fk_column") == "id_regional_district"
        and row.get("parent_id") is not None
    ):
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            pass
    return None


def _synchronous_area_id_from_flat_row(row: dict[str, Any]) -> int | None:
    """id синхронной зоны в строке сводки."""
    raw = row.get("id_synchronous_area")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    if (
        row.get("parent_fk_column") == "id_synchronous_area"
        and row.get("parent_id") is not None
    ):
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            pass
    return None


def _build_res_to_synchronous_area_ids_map() -> dict[int, frozenset[int]]:
    """РЭС → синхронные зоны по субъектам РФ (RegionalDistrict.id_synchronous_area)."""
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_synchronous_area_ids_map,
    )

    return get_res_to_synchronous_area_ids_map()


def _coeff_union_res_sum_year(y: int, coeff_base_year: int) -> bool:
    """Год входит в отчётный интервал (N−9…N) или среднесрочный (N+1…N+6) сводки коэффициентов."""
    return (
        (coeff_base_year - 9) <= y <= coeff_base_year
        or (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
    )


def slice_coeff_summary_for_lazy_long_segment(
    context: dict[str, Any],
    coeff_n: int,
    *,
    include_long: bool,
) -> None:
    """
    Без coeff_include_long в URL на «Коэффициенты…» не отдаём долгосрочные годы (N+7…N+18) в разметке.
    Полный диапазон остаётся в экспорте и при coeff_include_long=1.
    """
    context["coeff_include_long"] = include_long
    if include_long:
        return
    years_full: list[int] = list(context.get("years") or [])
    if not years_full:
        return
    cutoff = int(coeff_n) + 6
    keep_idx = [i for i, y in enumerate(years_full) if int(y) <= cutoff]
    if len(keep_idx) == len(years_full):
        return
    new_years = [years_full[i] for i in keep_idx]
    context["years"] = new_years
    yip = context.get("year_is_plan") or {}
    context["year_is_plan"] = {y: bool(yip.get(y, False)) for y in new_years}
    context["start_year"] = min(new_years)
    context["end_year"] = max(new_years)
    slice_keys = (
        "year_values",
        "year_row_ids",
        "year_numeric_tooltips",
        "year_k_values",
        "year_k_full_tooltips",
    )
    for row in context.get("summary_rows") or []:
        if not isinstance(row, dict):
            continue
        for key in slice_keys:
            lst = row.get(key)
            if not isinstance(lst, list) or not keep_idx:
                continue
            if len(lst) == len(years_full):
                row[key] = [lst[i] for i in keep_idx]
            elif all(i < len(lst) for i in keep_idx):
                row[key] = [lst[i] for i in keep_idx]


def _iter_res_level_aggregation_source_rows(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
    *,
    res_ids_with_energy_units: frozenset[int] | None = None,
):
    """
    Строки-источники для агрегирования по РЭС.

    В сумму входят только строки RegionalEnergySystemDemandParameter;
    значения энергорайонов в агрегаты не включаются.
    """
    del res_ids_with_energy_units
    dm_res = RegionalEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("parameter_key") != parameter_key:
            continue
        if r.get("demand_model_name") != dm_res:
            continue
        res_id = _regional_energy_system_id_from_flat_row(r)
        if res_id is None:
            continue
        yield r


def _subject_parameter_sums_by_res_year_index(
    summary_rows: list[dict[str, Any]],
    parameter_key: str,
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[tuple[int, int], float]:
    """Сумма показателя по субъектам РФ для РЭС с несколькими субъектами (ключ: res_id, year_index)."""
    dm_rd = RegionalDistrictDemandParameter.__name__
    out: dict[tuple[int, int], float] = {}
    n_y = len(years)
    for r in summary_rows:
        if r.get("parameter_key") != parameter_key:
            continue
        if r.get("demand_model_name") != dm_rd:
            continue
        res_id = r.get("id_regional_energy_system")
        if res_id is None:
            continue
        res_id = int(res_id)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            key = (res_id, j)
            if key in out:
                out[key] = float(out[key]) + float(add)
            else:
                out[key] = float(add)
    return out


def _res_level_aggregation_year_value(
    res_row: dict[str, Any],
    year_index: int,
    *,
    subject_fallback: dict[tuple[int, int], float] | None = None,
) -> float | None:
    """Значение РЭС для агрегата; при пустой строке РЭС — сумма по субъектам этой РЭС."""
    yvals = res_row.get("year_values") or []
    add = _parse_summary_cell_float(yvals[year_index] if year_index < len(yvals) else None)
    if add is not None:
        return float(add)
    if subject_fallback is None:
        return None
    res_id = _regional_energy_system_id_from_flat_row(res_row)
    if res_id is None:
        return None
    return subject_fallback.get((res_id, year_index))


def _aggregate_res_combined_on_oes_mw_sum_by_union(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности ОЭС, МВт» по строкам РЭС внутри каждого ОЭС."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_oes", years, year_included=year_included
    )

    def _tot(uid: int) -> list[float | None]:
        if uid not in out:
            out[uid] = [None] * n_y
        return out[uid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_oes"):
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        row_tot = _tot(uid)
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _res_level_aggregation_year_value(
                r, j, subject_fallback=subject_fallback
            )
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _sum_optional_floats(
    a: float | None,
    b: float | None,
) -> float | None:
    if a is None and b is None:
        return None
    return float(a or 0.0) + float(b or 0.0)


def _merge_optional_float_year_lists(
    a: list[float | None],
    b: list[float | None],
) -> list[float | None]:
    n = max(len(a), len(b))
    return [
        _sum_optional_floats(
            a[i] if i < len(a) else None,
            b[i] if i < len(b) else None,
        )
        for i in range(n)
    ]


def _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    parameter_key: str,
    south_ues_id: int,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма показателя субъектов ФО «Новые территории» под ОЭС Юга."""
    n_y = len(years)
    year_tot: list[float | None] = [None] * n_y
    nt_rd_ids = _new_territories_regional_district_ids()
    if not nt_rd_ids:
        return year_tot
    dm_rd = RegionalDistrictDemandParameter.__name__
    for r in summary_rows:
        if r.get("parameter_key") != parameter_key:
            continue
        if r.get("demand_model_name") != dm_rd:
            continue
        rd_id = _regional_district_id_from_flat_row(r)
        if rd_id is None:
            continue
        if rd_id not in nt_rd_ids:
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None or int(uid) != int(south_ues_id):
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


def _aggregate_nt_subjects_combined_on_es_mw_sum_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    south_ues_id: int,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Совмещенный максимум потребления мощности субъекта РФ на РЭС» по ФО «Новые территории»."""
    return _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
        summary_rows,
        years,
        parameter_key="combined_on_es",
        south_ues_id=south_ues_id,
        year_included=year_included,
    )


def _aggregate_nt_subjects_combined_on_ees_mw_sum_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    south_ues_id: int,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Совмещенный максимум потребления мощности субъекта РФ на ЕЭС» по ФО «Новые территории»."""
    return _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
        summary_rows,
        years,
        parameter_key="combined_on_ees",
        south_ues_id=south_ues_id,
        year_included=year_included,
    )


def _nt_combined_on_es_year_sums_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма combined_on_es субъектов «Новые территории» под ОЭС Юга (как для «ОЭС Юга с НТ»)."""
    out: list[float | None] = []
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    for south_id in south_ids:
        part = _aggregate_nt_subjects_combined_on_es_mw_sum_for_south_ues(
            summary_rows,
            years,
            south_ues_id=south_id,
            year_included=year_included,
        )
        out = _merge_optional_float_year_lists(out, part)
    return out


def _nt_combined_on_ees_year_sums_for_ees_russia_with_nt(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма combined_on_ees субъектов «Новые территории» для агрегата «ЕЭС России с НТ»."""
    out: list[float | None] = []
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    for south_id in south_ids:
        part = _aggregate_nt_subjects_combined_on_ees_mw_sum_for_south_ues(
            summary_rows,
            years,
            south_ues_id=south_id,
            year_included=year_included,
        )
        out = _merge_optional_float_year_lists(out, part)
    return out


def _south_ues_ids_for_nt_enrichment(
    summary_rows: list[dict[str, Any]],
) -> frozenset[int]:
    """id ОЭС Юга по строкам «… с НТ» на сводке (на случай нескольких версий справочника)."""
    out: set[int] = set()
    for r in summary_rows:
        if r.get("perimeter_variant_code") != CODE_WITH_NT:
            continue
        label_cf = str(r.get("entity_label") or "").strip().casefold()
        if "юга" not in label_cf:
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is not None:
            out.add(int(uid))
    if out:
        return frozenset(out)
    south = _find_union_energy_system_by_name("оэс юга")
    if south is not None:
        return frozenset({int(south.id)})
    return frozenset()


def enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«ОЭС Юга с НТ»: расчётный максимум = сумма по РЭС + сумма combined_on_es субъектов «Новые территории»."""
    if not summary_rows or not years:
        return
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    if not south_ids:
        return
    res_sums_by_union = _aggregate_res_combined_on_oes_mw_sum_by_union(
        summary_rows, years, year_included=year_included
    )
    n_y = len(years)
    combined_by_union: dict[int, list[float | None]] = {}
    for south_id in south_ids:
        nt_year_sums = _aggregate_nt_subjects_combined_on_es_mw_sum_for_south_ues(
            summary_rows, years, south_ues_id=south_id, year_included=year_included
        )
        res_mids = res_sums_by_union.get(south_id) or [None] * n_y
        combined_by_union[south_id] = [
            _sum_optional_floats(
                res_mids[j] if j < len(res_mids) else None,
                nt_year_sums[j] if j < len(nt_year_sums) else None,
            )
            for j in range(n_y)
        ]

    def _south_with_nt_row(row: dict[str, Any]) -> bool:
        if row.get("perimeter_variant_code") != CODE_WITH_NT:
            return False
        label_cf = str(row.get("entity_label") or "").strip().casefold()
        if "юга" not in label_cf:
            return False
        uid = _union_energy_system_id_from_flat_row(row)
        return uid is not None and int(uid) in south_ids

    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_max_power_mw",
        sums_by_union=combined_by_union,
        year_included=year_included,
        row_include_predicate=_south_with_nt_row,
    )


def _apply_ues_calculated_mw_from_res_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    ues_parameter_key: str,
    sums_by_union: dict[int, list[float | None]],
    year_included: Callable[[int], bool] | None = None,
    row_include_predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    """Подставляет в строку УЭС суммы по РЭС (годовые столбцы; исторический столбец очищается)."""
    n_y = len(years)
    for r in summary_rows:
        if r.get("demand_model_name") != UnionEnergySystemDemandParameter.__name__:
            continue
        if r.get("parameter_key") != ues_parameter_key:
            continue
        if row_include_predicate is not None:
            if not row_include_predicate(r):
                continue
        elif not _ues_row_uses_standard_oes_aggregation(r):
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        mids = sums_by_union.get(uid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        # Столбец «Исторический собственный максимум» для расчётных строк УЭС не заполняется.
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def _aggregate_res_combined_on_fo_mw_sum_by_federal_district(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный на ФО, МВт» по строкам РЭС внутри каждого ФО."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(fid: int) -> list[float | None]:
        if fid not in out:
            out[fid] = [None] * n_y
        return out[fid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_fo"):
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(fid)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_combined_on_cz_mw_sum_by_federal_district(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный на ЦЗ России, МВт» по строкам РЭС внутри каждого ФО."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(fid: int) -> list[float | None]:
        if fid not in out:
            out[fid] = [None] * n_y
        return out[fid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_cz"):
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(fid)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def enrich_fo_summary_calculated_max_from_res_combined_on_fo(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум ФО, МВт» = сумма «Совмещенный на ФО, МВт» по РЭС данного ФО."""
    sums = _aggregate_res_combined_on_fo_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    n_y = len(years)
    dm_fd = FederalDistrictDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_fd:
            continue
        if r.get("parameter_key") != "calculated_max_fo_mw":
            continue
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue
        mids = sums.get(fid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        # В «max»-сводках исторический максимум для ФО — не про эту расчётную строку.
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_fo_summary_calculated_combined_on_cz_from_res_combined(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный совмещенный на ЦЗ России, МВт» = сумма «Совмещенный на ЦЗ России, МВт» по РЭС данного ФО."""
    sums = _aggregate_res_combined_on_cz_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    n_y = len(years)
    dm_fd = FederalDistrictDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_fd:
            continue
        if r.get("parameter_key") != "calculated_combined_on_cz_mw":
            continue
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue
        mids = sums.get(fid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        # В «max»-сводках исторический максимум для ФО — не про эту расчётную строку.
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def _aggregate_res_combined_on_ez_mw_sum_by_energy_zone(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный на энергозону, МВт» по строкам РЭС внутри каждой энергозоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(ezid: int) -> list[float | None]:
        if ezid not in out:
            out[ezid] = [None] * n_y
        return out[ezid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ez"):
        raw_ezid = r.get("id_energy_zone")
        if raw_ezid is None:
            continue
        try:
            ezid = int(raw_ezid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(ezid)
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_combined_on_ees_mw_sum_by_synchronous_area(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    res_to_sa_ids: dict[int, frozenset[int]],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности РЭС на ЕЭС, МВт» по РЭС внутри каждой синхронной зоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_ees", years, year_included=year_included
    )

    def _tot(said: int) -> list[float | None]:
        if said not in out:
            out[said] = [None] * n_y
        return out[said]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ees"):
        res_id = _regional_energy_system_id_from_flat_row(r)
        if res_id is None:
            continue
        sa_ids = res_to_sa_ids.get(res_id)
        if not sa_ids:
            continue
        for said in sa_ids:
            row_tot = _tot(said)
            for j in range(n_y):
                y = years[j]
                if year_included is not None and not year_included(y):
                    continue
                add = _res_level_aggregation_year_value(
                    r, j, subject_fallback=subject_fallback
                )
                if add is None:
                    continue
                if row_tot[j] is None:
                    row_tot[j] = float(add)
                else:
                    row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_combined_on_oes_mw_sum_by_synchronous_area(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    res_to_sa_ids: dict[int, frozenset[int]],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности РЭС на ОЭС, МВт» по РЭС внутри каждой синхронной зоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_oes", years, year_included=year_included
    )

    def _tot(said: int) -> list[float | None]:
        if said not in out:
            out[said] = [None] * n_y
        return out[said]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_oes"):
        res_id = _regional_energy_system_id_from_flat_row(r)
        if res_id is None:
            continue
        sa_ids = res_to_sa_ids.get(res_id)
        if not sa_ids:
            continue
        for said in sa_ids:
            row_tot = _tot(said)
            for j in range(n_y):
                y = years[j]
                if year_included is not None and not year_included(y):
                    continue
                add = _res_level_aggregation_year_value(
                    r, j, subject_fallback=subject_fallback
                )
                if add is None:
                    continue
                if row_tot[j] is None:
                    row_tot[j] = float(add)
                else:
                    row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_max_power_mw_sum_by_synchronous_area(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    res_to_sa_ids: dict[int, frozenset[int]],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Максимум потребления мощности, МВт» по РЭС внутри каждой синхронной зоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(said: int) -> list[float | None]:
        if said not in out:
            out[said] = [None] * n_y
        return out[said]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "max_power"):
        res_id = _regional_energy_system_id_from_flat_row(r)
        if res_id is None:
            continue
        sa_ids = res_to_sa_ids.get(res_id)
        if not sa_ids:
            continue
        yvals = r.get("year_values") or []
        for said in sa_ids:
            row_tot = _tot(said)
            for j in range(n_y):
                y = years[j]
                if year_included is not None and not year_included(y):
                    continue
                add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
                if add is None:
                    continue
                if row_tot[j] is None:
                    row_tot[j] = float(add)
                else:
                    row_tot[j] = float(row_tot[j]) + float(add)
    return out


def enrich_oes_summary_calculated_max_power_sa_from_res_max_power(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности, МВт» по синхронной зоне.

    Для «Вторая синхронная зона» — сумма «Совмещенный максимум потребления мощности РЭС на ОЭС, МВт»;
    для «Синхронная зона Калининградской области» — «Максимум потребления мощности, МВт» ЭС Калининградской области;
    для первой синхронной зоны — сумма «Максимум потребления мощности, МВт» по РЭС зоны.
    """
    res_to_sa_ids = _build_res_to_synchronous_area_ids_map()
    sums_max = _aggregate_res_max_power_mw_sum_by_synchronous_area(
        summary_rows, years, res_to_sa_ids, year_included=year_included
    )
    sums_oes = _aggregate_res_combined_on_oes_mw_sum_by_synchronous_area(
        summary_rows, years, res_to_sa_ids, year_included=year_included
    )
    second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
        _SECOND_SYNC_AREA_BASE_LABEL_CF
    )
    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    kaliningrad_max = (
        _res_parameter_year_floats_from_summary_rows(
            summary_rows,
            res_id=kaliningrad_es_id,
            parameter_key="max_power",
            years=years,
            year_included=year_included,
        )
        if kaliningrad_es_id is not None
        else None
    )
    n_y = len(years)
    dm_sa = SynchronousAreaDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_sa:
            continue
        if r.get("parameter_key") != "calculated_max_power_mw":
            continue
        said = _synchronous_area_id_from_flat_row(r)
        if said is None:
            continue
        if (
            kaliningrad_sa_id is not None
            and said == kaliningrad_sa_id
            and kaliningrad_max is not None
        ):
            mids = kaliningrad_max
        elif second_sa_id is not None and said == second_sa_id:
            mids = sums_oes.get(said)
        else:
            mids = sums_max.get(said)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_oes_summary_calculated_max_sa_from_res_combined_on_ees(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный совмещенный максимум потребления мощности СЗ на ЕЭС, МВт».

    Для первой и второй синхронной зоны — сумма «Совмещенный максимум потребления мощности РЭС на ЕЭС, МВт»
    по РЭС зоны; для Калининграда — значение ЭС Калининградской области.
    """
    res_to_sa_ids = _build_res_to_synchronous_area_ids_map()
    sums = _aggregate_res_combined_on_ees_mw_sum_by_synchronous_area(
        summary_rows, years, res_to_sa_ids, year_included=year_included
    )
    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    kaliningrad_ees = (
        _res_parameter_year_floats_from_summary_rows(
            summary_rows,
            res_id=kaliningrad_es_id,
            parameter_key="combined_on_ees",
            years=years,
            year_included=year_included,
        )
        if kaliningrad_es_id is not None
        else None
    )
    n_y = len(years)
    dm_sa = SynchronousAreaDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_sa:
            continue
        if r.get("parameter_key") != "calculated_max_sa_mw":
            continue
        said = _synchronous_area_id_from_flat_row(r)
        if said is None:
            continue
        if (
            kaliningrad_sa_id is not None
            and said == kaliningrad_sa_id
            and kaliningrad_ees is not None
        ):
            mids = kaliningrad_ees
        else:
            mids = sums.get(said)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_ez_summary_calculated_max_from_res_combined_on_ez(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум энергозоны, МВт» = сумма «Совмещенный на энергозону, МВт» по РЭС данной энергозоны."""
    sums = _aggregate_res_combined_on_ez_mw_sum_by_energy_zone(
        summary_rows, years, year_included=year_included
    )
    n_y = len(years)
    dm_ez = EnergyZoneDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_ez:
            continue
        if r.get("parameter_key") != "calculated_max_ez_mw":
            continue
        raw_ezid = r.get("id_energy_zone")
        if raw_ezid is None:
            continue
        try:
            ezid = int(raw_ezid)
        except (TypeError, ValueError):
            continue
        mids = sums.get(ezid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                yv_p[j] = _format_calculated_max_mw(s)
                ynt_p[j] = _format_calculated_max_mw(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        # В «max»-сводках исторический максимум для энергозоны — не про эту расчётную строку.
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def _enrich_ez_summary_calculated_max_from_res(
    context: dict[str, Any], rounding_digits: int
) -> None:
    rows = context.get("summary_rows") or []
    years = list(context.get("years") or [])
    enrich_ez_summary_calculated_max_from_res_combined_on_ez(rows, years, rounding_digits)
    # «ЕЭС России»: расчетный максимум = сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по всем энергозонам.
    n_y = len(years)
    if not rows or n_y == 0:
        return
    ez_dm = EnergyZoneDemandParameter.__name__
    year_tot: list[float | None] = [None] * n_y
    for r in rows:
        if r.get("demand_model_name") != ez_dm:
            continue
        if r.get("parameter_key") != "combined_on_ees":
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    _apply_ees_russia_calculated_parameter_rows(
        rows,
        years,
        rounding_digits,
        "calculated_max_ees_russia_mw",
        year_tot,
        None,
    )


def _clear_oes_summary_hist_non_base_parameters(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Сводка по ОЭС: «Исторический собственный максимум» только у max_power, peak_datetime, avg_temp."""
    for r in summary_rows:
        if (r.get("parameter_key") or "") in OES_SUMMARY_HIST_PARAMETER_KEYS:
            continue
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_oes_summary_calculated_max_power_from_res_combined(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности, МВт» = сумма «Совмещенный максимум потребления мощности ОЭС, МВт» по РЭС того же ОЭС."""
    sums = _aggregate_res_combined_on_oes_mw_sum_by_union(
        summary_rows, years, year_included=year_included
    )
    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_max_power_mw",
        sums_by_union=sums,
        year_included=year_included,
    )


def _aggregate_res_combined_on_ees_mw_sum_by_union(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам РЭС внутри каждого ОЭС."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_ees", years, year_included=year_included
    )

    def _tot(uid: int) -> list[float | None]:
        if uid not in out:
            out[uid] = [None] * n_y
        return out[uid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ees"):
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        row_tot = _tot(uid)
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _res_level_aggregation_year_value(
                r, j, subject_fallback=subject_fallback
            )
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def enrich_oes_summary_calculated_combined_on_ees_from_res_combined(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт» = сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по РЭС того же ОЭС."""
    sums = _aggregate_res_combined_on_ees_mw_sum_by_union(
        summary_rows, years, year_included=year_included
    )
    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_combined_on_ees_mw",
        sums_by_union=sums,
        year_included=year_included,
    )


def _oes_summary_entity_block_end(summary_rows: list[dict[str, Any]], start_idx: int) -> int:
    span = int(summary_rows[start_idx].get("entity_rowspan") or 1)
    return start_idx + max(span, 1)


def _union_energy_system_ids_for_energy_system_type(type_name: str) -> frozenset[int]:
    """id ОЭС (UnionEnergySystem) с заданным наименованием типа энергосистемы."""
    est = _get_energy_system_type_by_name(type_name)
    if est is None:
        return frozenset()
    query = UnionEnergySystem.query
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    return frozenset(
        int(ues.id)
        for ues in query.filter(UnionEnergySystem.id_energy_system_type == est.id).all()
        if getattr(ues, "id", None) is not None
    )


def _sum_ues_combined_on_ees_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    allowed_ues_ids: frozenset[int] | None = None,
    year_included: Callable[[int], bool] | None = None,
    ues_perimeter_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[list[float | None], float | None]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам ОЭС в flat-таблице сводки."""
    n_y = len(years)
    year_tot: list[float | None] = [None] * n_y
    hist_tot: float | None = None
    ues_dm = UnionEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != ues_dm:
            continue
        if r.get("parameter_key") != "combined_on_ees":
            continue
        if ues_perimeter_filter is not None:
            if not ues_perimeter_filter(r):
                continue
        elif not _ues_row_uses_standard_oes_aggregation(r):
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        if allowed_ues_ids is not None and uid not in allowed_ues_ids:
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
        if year_included is None:
            add_h = _parse_summary_cell_float(r.get("hist_value"))
            if add_h is not None:
                if hist_tot is None:
                    hist_tot = float(add_h)
                else:
                    hist_tot = float(hist_tot) + float(add_h)
    return year_tot, hist_tot


def _sum_res_combined_on_ees_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    allowed_ues_ids: frozenset[int] | None = None,
    year_included: Callable[[int], bool] | None = None,
) -> tuple[list[float | None], float | None]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам РЭС (фильтр по ОЭС — тип «ЕЭС России»)."""
    n_y = len(years)
    year_tot: list[float | None] = [None] * n_y
    hist_tot: float | None = None
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_ees", years, year_included=year_included
    )
    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ees"):
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None:
            continue
        if allowed_ues_ids is not None and uid not in allowed_ues_ids:
            continue
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _res_level_aggregation_year_value(
                r, j, subject_fallback=subject_fallback
            )
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
        if year_included is None:
            add_h = _parse_summary_cell_float(r.get("hist_value"))
            if add_h is not None:
                if hist_tot is None:
                    hist_tot = float(add_h)
                else:
                    hist_tot = float(hist_tot) + float(add_h)
    return year_tot, hist_tot


def _apply_ees_russia_calculated_mw_row(
    row: dict[str, Any],
    years: list[int],
    rounding_digits: int,
    year_sums: list[float | None],
    hist_sum: float | None,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    n_y = len(years)
    yv_p = list(row.get("year_values") or [])
    ynt_p = list(row.get("year_numeric_tooltips") or [])
    while len(yv_p) < n_y:
        yv_p.append("—")
    while len(ynt_p) < n_y:
        ynt_p.append("")
    for jj in range(n_y):
        if year_included is not None and not year_included(years[jj]):
            continue
        s = year_sums[jj] if jj < len(year_sums) else None
        if s is not None:
            yv_p[jj] = _format_numeric(s, CALCULATED_MAX_MW_ROUNDING_DIGITS)
            ynt_p[jj] = _format_calculated_max_mw(s)
        else:
            yv_p[jj] = "—"
            ynt_p[jj] = ""
    row["year_values"] = yv_p
    row["year_numeric_tooltips"] = ynt_p
    row["hist_value"] = ""
    row["hist_numeric_tooltip"] = ""


def _apply_ees_russia_calculated_mw_to_entity_block(
    summary_rows: list[dict[str, Any]],
    block_start: int,
    years: list[int],
    rounding_digits: int,
    parameter_key: str,
    year_sums: list[float | None],
    hist_sum: float | None,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    i0, i1 = block_start, _oes_summary_entity_block_end(summary_rows, block_start)
    for j in range(i0, i1):
        r = summary_rows[j]
        if r.get("parameter_key") != parameter_key:
            continue
        _apply_ees_russia_calculated_mw_row(
            r,
            years,
            rounding_digits,
            year_sums,
            hist_sum,
            year_included=year_included,
        )


def _ees_russia_year_sums_with_nt_addon(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    block_variant: str | None,
    year_sums: list[float | None],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Для «ЕЭС России с НТ» добавляет суммы combined_on_ees субъектов «Новые территории»."""
    if (
        block_variant is None
        or str(block_variant) not in perimeter_variant_codes_in_legacy_nt_group(CODE_WITH_NT)
    ):
        return year_sums
    nt_sums = _nt_combined_on_ees_year_sums_for_ees_russia_with_nt(
        summary_rows, years, year_included=year_included
    )
    return _merge_optional_float_year_lists(year_sums, nt_sums)


def _apply_ees_russia_calculated_parameter_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    parameter_key: str,
    year_sums: list[float | None],
    hist_sum: float | None,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != _EES_RUSSIA_AGGREGATE_DM_NAME:
            continue
        i0, i1 = i, _oes_summary_entity_block_end(summary_rows, i)
        for j in range(i0, i1):
            r = summary_rows[j]
            if r.get("parameter_key") != parameter_key:
                continue
            _apply_ees_russia_calculated_mw_row(
                r,
                years,
                rounding_digits,
                year_sums,
                hist_sum,
                year_included=year_included,
            )


def enrich_oes_ees_russia_calculated_max_via_oes(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности ЕЭС (через ОЭС)» = сумма «Совмещенный максимум потребления мощности ЕЭС» по ОЭС типа «ЕЭС России»."""
    if not summary_rows or not years:
        return
    ues_ids = _union_energy_system_ids_for_energy_system_type(
        EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME
    )
    calc_models = frozenset({_EES_RUSSIA_AGGREGATE_DM_NAME})
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") not in calc_models:
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums, hist_sum = _sum_ues_combined_on_ees_in_summary_rows(
            summary_rows,
            years,
            allowed_ues_ids=ues_ids,
            year_included=year_included,
            ues_perimeter_filter=lambda r, v=block_variant: (
                _ues_row_included_for_ees_russia_aggregate_variant(r, v)
            ),
        )
        year_sums = _ees_russia_year_sums_with_nt_addon(
            summary_rows,
            years,
            block_variant,
            year_sums,
            year_included=year_included,
        )
        _apply_ees_russia_calculated_mw_to_entity_block(
            summary_rows,
            i,
            years,
            rounding_digits,
            "calculated_max_ees_via_oes_mw",
            year_sums,
            hist_sum,
            year_included=year_included,
        )


def enrich_oes_ees_russia_calculated_max_via_es(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности ЕЭС (через ЭС)» = сумма «Совмещенный максимум потребления мощности ЕЭС» по РЭС под ОЭС типа «ЕЭС России»."""
    if not summary_rows or not years:
        return
    ues_ids = _union_energy_system_ids_for_energy_system_type(
        EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME
    )
    calc_models = frozenset({_EES_RUSSIA_AGGREGATE_DM_NAME})
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") not in calc_models:
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums, hist_sum = _sum_res_combined_on_ees_in_summary_rows(
            summary_rows,
            years,
            allowed_ues_ids=ues_ids,
            year_included=year_included,
        )
        year_sums = _ees_russia_year_sums_with_nt_addon(
            summary_rows,
            years,
            block_variant,
            year_sums,
            year_included=year_included,
        )
        _apply_ees_russia_calculated_mw_to_entity_block(
            summary_rows,
            i,
            years,
            rounding_digits,
            "calculated_max_ees_via_es_mw",
            year_sums,
            hist_sum,
            year_included=year_included,
        )


@lru_cache(maxsize=1)
def _tites_union_energy_system_ids() -> frozenset[int]:
    """Id ОЭС ветки ТИТЭС (UnionEnergySystem)."""
    query = UnionEnergySystem.query
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    return frozenset(
        int(ues.id)
        for ues in query.all()
        if _is_tites_branch(ues)
    )


def _energy_unit_name_matches_spec(name: str | None, spec: tuple[str, ...]) -> bool:
    normalized = (name or "").strip().casefold().replace("ё", "е")
    return all(marker in normalized for marker in spec)


@lru_cache(maxsize=1)
def _ees_aggregate_formula_tites_energy_unit_ids() -> frozenset[int]:
    """Id энергорайонов из формулы «ЭЭС России» (ветка ТИТЭС)."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    matched: set[int] = set()
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        name = getattr(energy_unit, "name", None)
        for spec in _EES_AGGREGATE_TITES_EU_NAME_SPECS:
            if _energy_unit_name_matches_spec(name, spec):
                matched.add(int(energy_unit.id))
                break
    return frozenset(matched)


@lru_cache(maxsize=1)
def _ees_aggregate_formula_tites_eu_base_subtract_by_id() -> dict[int, float]:
    """Базовые поправки энергорайонов формулы ЭЭС: только Норильск и Чаун-Билибино."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    out: dict[int, float] = {}
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        name = getattr(energy_unit, "name", None)
        for spec, subtract in _EES_AGGREGATE_TITES_EU_BASE_SUBTRACT_MW.items():
            if _energy_unit_name_matches_spec(name, spec):
                out[int(energy_unit.id)] = float(subtract)
                break
    return out


def _ees_formula_eu_net_max_power(
    eu_id: int,
    raw: float,
    *,
    legacy_adjustments: bool,
) -> float:
    if legacy_adjustments:
        subtract = _ees_aggregate_formula_tites_eu_subtract_by_id().get(eu_id, 0.0)
        return float(raw) - float(subtract)
    base = _ees_aggregate_formula_tites_eu_base_subtract_by_id()
    subtract = base.get(eu_id, 0.0)
    if (
        subtract == _EES_AGGREGATE_TITES_EU_BASE_SUBTRACT_MW[("чаун", "билибин")]
        and float(raw) <= _EES_AGGREGATE_TITES_EU_CHAUN_UNADJUSTED_MAX_POWER_MW
    ):
        subtract = 0.0
    return float(raw) - float(subtract)


def _ees_russia_max_power_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Максимум потребления мощности, МВт» агрегата «ЕЭС России без НТ» по годам."""
    n_y = len(years)
    out: list[float | None] = [None] * n_y
    for r in summary_rows:
        if not r.get("show_entity_cell"):
            continue
        if r.get("demand_model_name") != _EES_RUSSIA_AGGREGATE_DM_NAME:
            continue
        if r.get("perimeter_variant_code") != CODE_WITHOUT_NT:
            continue
        if r.get("parameter_key") != "max_power":
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            parsed = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if parsed is None:
                continue
            out[j] = float(parsed)
        return out
    return out


def _first_sync_minus_tites_formula_ees_part_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Промежуточная часть «ЕЭС»: первая СЗ без НТ − (ТИТЭС − corr)."""
    tites_branch_sums = _sum_tites_branch_max_power_in_summary_rows(
        summary_rows, years, year_included=year_included
    )
    first_sa_sums = _first_sync_calculated_max_power_by_variant(
        summary_rows, years, CODE_WITHOUT_NT
    )
    n_y = len(years)
    out: list[float | None] = [None] * n_y
    for j in range(n_y):
        if year_included is not None and not year_included(years[j]):
            continue
        fs = first_sa_sums[j] if j < len(first_sa_sums) else None
        tb = tites_branch_sums[j] if j < len(tites_branch_sums) else None
        if fs is None and tb is None:
            continue
        tites_net = float(tb or 0.0) - _EES_FORMULA_TITES_BRANCH_SUBTRACT_CORRECTION_MW
        out[j] = float(fs or 0.0) - tites_net
    return out


@lru_cache(maxsize=1)
def _ees_aggregate_formula_tites_eu_subtract_by_id() -> dict[int, float]:
    """Поправки к «Максимум …» энергорайонов формулы ЭЭС (МВт вычитаются перед суммированием)."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    out: dict[int, float] = {}
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        name = getattr(energy_unit, "name", None)
        for spec, subtract in _EES_AGGREGATE_TITES_EU_MAX_POWER_SUBTRACT_MW.items():
            if _energy_unit_name_matches_spec(name, spec):
                out[int(energy_unit.id)] = float(subtract)
                break
    return out


def _sum_tites_branch_max_power_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Максимум потребления мощности, МВт» по всей ветке «ТИТЭС и децентрализованная зона»."""
    n_y = len(years)
    tites_ids = _tites_union_energy_system_ids()
    if not tites_ids:
        return [None] * n_y

    year_tot: list[float | None] = [None] * n_y
    for r in summary_rows:
        if r.get("parameter_key") != "max_power":
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is None or int(uid) not in tites_ids:
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


def _first_sync_calculated_max_power_by_variant(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    perimeter_variant_code: str | None,
) -> list[float | None]:
    """«Расчетный максимум потребления мощности, МВт» первой синхронной зоны (по варианту НТ)."""
    n_y = len(years)
    sa_dm = SynchronousAreaDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != sa_dm:
            continue
        if r.get("parameter_key") != "calculated_max_power_mw":
            continue
        if not _is_first_synchronous_area_name(r.get("entity_label")):
            continue
        if r.get("perimeter_variant_code") != perimeter_variant_code:
            continue
        yvals = r.get("year_values") or []
        return [
            _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            for j in range(n_y)
        ]
    return [None] * n_y


def _energy_unit_id_from_flat_row(row: dict[str, Any]) -> int | None:
    raw = row.get("id_energy_unit")
    if raw is not None:
        return int(raw)
    if row.get("parent_fk_column") == "id_energy_unit" and row.get("parent_id") is not None:
        return int(row["parent_id"])
    return None


def _sum_ees_aggregate_formula_tites_energy_units_max_power(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
    legacy_adjustments: bool = True,
) -> list[float | None]:
    """Сумма «Максимум потребления мощности, МВт» по энергорайонам формулы ЭЭС России."""
    n_y = len(years)
    eu_ids = _ees_aggregate_formula_tites_energy_unit_ids()
    if not eu_ids:
        return [None] * n_y

    eu_dm = EnergyUnitDemandParameter.__name__
    year_tot: list[float | None] = [None] * n_y
    for r in summary_rows:
        if r.get("demand_model_name") != eu_dm:
            continue
        if r.get("parameter_key") != "max_power":
            continue
        eu_id = _energy_unit_id_from_flat_row(r)
        if eu_id is None or eu_id not in eu_ids:
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            value = _ees_formula_eu_net_max_power(
                int(eu_id),
                float(add),
                legacy_adjustments=legacy_adjustments,
            )
            if year_tot[j] is None:
                year_tot[j] = value
            else:
                year_tot[j] = float(year_tot[j]) + value
    return year_tot


def _ees_calculated_max_power_consumption_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Расчетный максимум …» (ЭЭС России без НТ).

    Если «Максимум …» ЕЭС России без НТ согласован с (первая СЗ − ТИТЭС) — сумма с ним
    и энергорайонами (−12 МВт Норильск, −6,6 МВт Чаун-Билибино при необходимости).
    Иначе — legacy: (первая СЗ − ТИТЭС + corr) + энергорайоны со всеми поправками.
    """
    formula_ees = _first_sync_minus_tites_formula_ees_part_year_sums(
        summary_rows, years, year_included=year_included
    )
    ees_row = _ees_russia_max_power_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    eu_legacy = _sum_ees_aggregate_formula_tites_energy_units_max_power(
        summary_rows, years, year_included=year_included, legacy_adjustments=True
    )
    eu_base = _sum_ees_aggregate_formula_tites_energy_units_max_power(
        summary_rows, years, year_included=year_included, legacy_adjustments=False
    )
    n_y = len(years)
    year_sums: list[float | None] = [None] * n_y
    threshold = _EES_FORMULA_USE_LEGACY_FIRST_SA_THRESHOLD_MW
    for j in range(n_y):
        if year_included is not None and not year_included(years[j]):
            continue
        fe = formula_ees[j] if j < len(formula_ees) else None
        er = ees_row[j] if j < len(ees_row) else None
        if fe is None and er is None:
            continue
        use_legacy = (
            fe is not None
            and er is not None
            and float(er) > float(fe) + threshold
        )
        if use_legacy:
            ees_part = float(fe)
            eu_part = float(eu_legacy[j] or 0.0) if j < len(eu_legacy) else 0.0
        elif er is not None:
            ees_part = float(er)
            eu_part = float(eu_base[j] or 0.0) if j < len(eu_base) else 0.0
        else:
            ees_part = float(fe or 0.0)
            eu_part = float(eu_legacy[j] or 0.0) if j < len(eu_legacy) else 0.0
        year_sums[j] = ees_part + eu_part
    return year_sums


def enrich_oes_ees_calculated_max_power_consumption(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности, МВт» (ЭЭС России).

    Без НТ: первая СЗ − ТИТЭС + энергорайоны формулы.
    С НТ: то же, что без НТ, + сумма combined_on_es субъектов «Новые территории» (как ОЭС Юга с НТ).
    """
    if not summary_rows or not years:
        return
    without_nt_sums = _ees_calculated_max_power_consumption_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    nt_addon_sums = _nt_combined_on_es_year_sums_for_south_ues(
        summary_rows, years, year_included=year_included
    )
    with_nt_sums = _merge_optional_float_year_lists(without_nt_sums, nt_addon_sums)
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != _EES_DEMAND_MODEL_NAME:
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums = (
            with_nt_sums
            if block_variant == CODE_WITH_NT
            else without_nt_sums
        )
        _apply_ees_russia_calculated_mw_to_entity_block(
            summary_rows,
            i,
            years,
            rounding_digits,
            "calculated_max_power_consumption_mw",
            year_sums,
            None,
            year_included=year_included,
        )


def enrich_oes_ees_russia_calculated_max_russia_mw(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    filter_year_list: list[int],
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности ЕЭС России, МВт» = сумма «Совмещенный максимум потребления мощности ЕЭС» по ОЭС типа «ЕЭС России».

    Для агрегата «ЕЭС России с/без НТ» берётся соответствующий вариант ОЭС Юга.
    """
    _ = filter_year_list
    if not summary_rows or not years:
        return
    ues_ids = _union_energy_system_ids_for_energy_system_type(
        EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME
    )
    calc_max_russia_mw_models = frozenset({_EES_RUSSIA_AGGREGATE_DM_NAME})
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") not in calc_max_russia_mw_models:
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums, hist_sum = _sum_ues_combined_on_ees_in_summary_rows(
            summary_rows,
            years,
            allowed_ues_ids=ues_ids,
            year_included=year_included,
            ues_perimeter_filter=lambda r, v=block_variant: (
                _ues_row_included_for_ees_russia_aggregate_variant(r, v)
            ),
        )
        year_sums = _ees_russia_year_sums_with_nt_addon(
            summary_rows,
            years,
            block_variant,
            year_sums,
            year_included=year_included,
        )
        _apply_ees_russia_calculated_mw_to_entity_block(
            summary_rows,
            i,
            years,
            rounding_digits,
            "calculated_max_ees_russia_mw",
            year_sums,
            hist_sum,
            year_included=year_included,
        )


def _enrich_oes_summary_calculated_max_from_res(
    context: dict[str, Any], rounding_digits: int
) -> None:
    rows = context.get("summary_rows") or []
    years = list(context.get("years") or [])
    enrich_oes_summary_calculated_max_power_from_res_combined(
        rows, years, rounding_digits
    )
    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
        rows, years, rounding_digits
    )
    enrich_oes_summary_calculated_combined_on_ees_from_res_combined(
        rows, years, rounding_digits
    )
    enrich_oes_ees_russia_calculated_max_russia_mw(
        rows,
        years,
        rounding_digits,
        filter_year_list=list(context.get("filter_year_list") or years),
    )
    enrich_oes_ees_russia_calculated_max_via_oes(rows, years, rounding_digits)
    enrich_oes_ees_russia_calculated_max_via_es(rows, years, rounding_digits)
    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(
        rows, years, rounding_digits
    )
    enrich_oes_summary_calculated_max_sa_from_res_combined_on_ees(
        rows, years, rounding_digits
    )
    enrich_oes_ees_calculated_max_power_consumption(rows, years, rounding_digits)
    _clear_oes_summary_hist_non_base_parameters(rows)


def _enrich_fo_summary_calculated_max_from_res(
    context: dict[str, Any], rounding_digits: int
) -> None:
    rows = context.get("summary_rows") or []
    years = list(context.get("years") or [])
    enrich_fo_summary_calculated_max_from_res_combined_on_fo(
        rows, years, rounding_digits
    )
    enrich_fo_summary_calculated_combined_on_cz_from_res_combined(
        rows, years, rounding_digits
    )


def _aggregate_res_combined_on_oes_mw_sum_by_union_for_medium_years(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    coeff_base_year: int,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности ОЭС, МВт» по строкам РЭС (отчётный N−9…N и среднесрочный N+1…N+6).

    На УЭС для «Расчетный максимум потребления мощности, МВт» эти годы задаются этой суммой.
    """
    return _aggregate_res_combined_on_oes_mw_sum_by_union(
        summary_rows,
        years,
        year_included=lambda y: _coeff_union_res_sum_year(y, coeff_base_year),
    )


def _aggregate_res_combined_on_ees_mw_sum_by_union_for_medium_years(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    coeff_base_year: int,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам РЭС (отчётный N−9…N и среднесрочный N+1…N+6).

    На УЭС для «Расчетный совмещенный максимум потребления мощности ОЭС на ЕЭС, МВт» эти годы задаются этой суммой.
    """
    return _aggregate_res_combined_on_ees_mw_sum_by_union(
        summary_rows,
        years,
        year_included=lambda y: _coeff_union_res_sum_year(y, coeff_base_year),
    )


def enrich_summary_rows_coeff_k_columns(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    year_is_plan: dict[int, bool],
    *,
    rounding_digits_k: int | None = None,
    coeff_base_year: int | None = None,
) -> None:
    """k = значение показателя / макс. мощность того же года (строка max_power в блоке — знаменатель; для самой строки max_power k не считается)."""
    rd_k = rounding_digits_k if rounding_digits_k is not None else rounding_digits
    n_y = len(years)
    res_ees_sum_by_union: dict[int, list[float | None]] = {}
    res_oes_sum_by_union: dict[int, list[float | None]] = {}
    if coeff_base_year is not None:
        res_ees_sum_by_union = _aggregate_res_combined_on_ees_mw_sum_by_union_for_medium_years(
            summary_rows, years, coeff_base_year
        )
        res_oes_sum_by_union = _aggregate_res_combined_on_oes_mw_sum_by_union_for_medium_years(
            summary_rows, years, coeff_base_year
        )
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
        max_row = next((r for r in block if r.get("parameter_key") == "max_power"), None)
        denoms: list[float | None] = [None] * n_y
        if max_row is not None:
            yv = max_row.get("year_values") or []
            denoms = [
                _parse_summary_cell_float(yv[j] if j < len(yv) else None) for j in range(n_y)
            ]

        block_uid = _union_energy_system_id_from_flat_row(block[0])
        for r in block:
            pk = r.get("parameter_key") or ""
            if pk in FO_COEFF_CZ_TOTAL_PARAMETER_KEYS:
                r["year_k_values"] = ["—"] * n_y
                r["year_k_full_tooltips"] = [""] * n_y
                continue
            dm_n_pre = r.get("demand_model_name")
            if (
                coeff_base_year is not None
                and dm_n_pre == UnionEnergySystemDemandParameter.__name__
                and pk == "calculated_max_power_mw"
                and block_uid is not None
                and _ues_row_uses_standard_oes_aggregation(r)
            ):
                _apply_ues_calculated_mw_from_res_sums(
                    [r],
                    years,
                    rounding_digits,
                    ues_parameter_key="calculated_max_power_mw",
                    sums_by_union=res_oes_sum_by_union,
                    year_included=lambda y: _coeff_union_res_sum_year(y, coeff_base_year),
                )
            if (
                coeff_base_year is not None
                and dm_n_pre == UnionEnergySystemDemandParameter.__name__
                and pk == "calculated_combined_on_ees_mw"
                and block_uid is not None
                and _ues_row_uses_standard_oes_aggregation(r)
            ):
                _apply_ues_calculated_mw_from_res_sums(
                    [r],
                    years,
                    rounding_digits,
                    ues_parameter_key="calculated_combined_on_ees_mw",
                    sums_by_union=res_ees_sum_by_union,
                    year_included=lambda y: _coeff_union_res_sum_year(y, coeff_base_year),
                )
            yvals = r.get("year_values") or []
            k_list: list[str] = []
            k_tt: list[str] = []
            for j in range(n_y):
                y = years[j]
                dm_n = r.get("demand_model_name")
                res_oes_or_ees_medium = (
                    coeff_base_year is not None
                    and (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
                    and pk in ("combined_on_oes", "combined_on_ees")
                    and dm_n == "RegionalEnergySystemDemandParameter"
                )
                ues_plan_k_exempt = False
                if (
                    coeff_base_year is not None
                    and dm_n == UnionEnergySystemDemandParameter.__name__
                ):
                    if pk in ("calculated_max_power_mw", "calculated_combined_on_ees_mw"):
                        ues_plan_k_exempt = _coeff_union_res_sum_year(y, coeff_base_year)
                    elif pk == "combined_on_ees":
                        ues_plan_k_exempt = (
                            (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
                        )
                yrsk = r.get("year_coeff_k_stored") or []
                sk_val = yrsk[j] if j < len(yrsk) else None
                sk_parsed = (
                    _parse_summary_cell_float(sk_val)
                    if sk_val not in (None, "", "—")
                    else None
                )
                if sk_parsed is not None and pk not in (
                    "peak_datetime",
                    "avg_temp",
                    "max_power",
                ):
                    if dm_n == "RegionalEnergySystemDemandParameter" and pk in (
                        "combined_on_oes",
                        "combined_on_ees",
                    ):
                        sk_rounded = _round_coeff_k_calc(sk_parsed)
                        k_list.append(_format_numeric(sk_rounded, rd_k))
                        k_tt.append(_format_full_numeric_tooltip(sk_rounded))
                        continue
                    if dm_n == "UnionEnergySystemDemandParameter" and pk in (
                        "calculated_max_power_mw",
                        "combined_on_ees",
                        "calculated_combined_on_ees_mw",
                    ):
                        if (
                            coeff_base_year is not None
                            and pk
                            in (
                                "calculated_max_power_mw",
                                "calculated_combined_on_ees_mw",
                            )
                            and _coeff_union_res_sum_year(y, coeff_base_year)
                        ):
                            # МВт для этих лет только что заданы суммой по РЭС (см. выше).
                            # Старый coeff_k из БД мог относиться к другой семантике — пересчитываем k из year_values/max_power.
                            pass
                        else:
                            sk_rounded = _round_coeff_k_calc(sk_parsed)
                            k_list.append(_format_numeric(sk_rounded, rd_k))
                            k_tt.append(_format_full_numeric_tooltip(sk_rounded))
                            continue
                if (
                    year_is_plan.get(y)
                    and pk != "max_power"
                    and not res_oes_or_ees_medium
                    and not ues_plan_k_exempt
                ):
                    k_list.append("—")
                    k_tt.append("")
                    continue
                if pk in ("peak_datetime", "avg_temp", "max_power"):
                    k_list.append("—")
                    k_tt.append("")
                    continue
                num = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
                d = denoms[j] if j < len(denoms) else None
                if num is not None and d is not None and d > 0:
                    ratio = _round_coeff_k_calc(num / d)
                    k_list.append(_format_numeric(ratio, rd_k))
                    k_tt.append(_format_full_numeric_tooltip(ratio))
                else:
                    k_list.append("—")
                    k_tt.append("")
            r["year_k_values"] = k_list
            r["year_k_full_tooltips"] = k_tt
            if (
                coeff_base_year is not None
                and r.get("demand_model_name") == UnionEnergySystemDemandParameter.__name__
                and (r.get("parameter_key") or "")
                in ("calculated_max_power_mw", "calculated_combined_on_ees_mw")
            ):
                yc = list(r.get("year_coeff_k_stored") or [])
                if len(yc) < n_y:
                    yc.extend(["—"] * (n_y - len(yc)))
                for j in range(n_y):
                    yt = years[j]
                    if _coeff_union_res_sum_year(yt, coeff_base_year):
                        yc[j] = k_list[j] if j < len(k_list) else "—"
                r["year_coeff_k_stored"] = yc
            dm_block = r.get("demand_model_name")
            pk_medium_res = ("combined_on_oes", "combined_on_ees")
            pk_medium_ues_sync = (
                "calculated_max_power_mw",
                "combined_on_ees",
            )
            if coeff_base_year is not None and dm_block == "RegionalEnergySystemDemandParameter" and pk in pk_medium_res:
                yv_mw = list(r.get("year_values") or [])
                if len(yv_mw) < n_y:
                    yv_mw.extend(["—"] * (n_y - len(yv_mw)))
                ynt = list(r.get("year_numeric_tooltips") or [])
                if len(ynt) < n_y:
                    ynt.extend([""] * (n_y - len(ynt)))
                for j in range(n_y):
                    y = years[j]
                    if not ((coeff_base_year + 1) <= y <= (coeff_base_year + 6)):
                        continue
                    k_parsed = _parse_summary_cell_float(k_list[j] if j < len(k_list) else None)
                    d = denoms[j] if j < len(denoms) else None
                    if k_parsed is None or d is None or not (d > 0):
                        continue
                    prod = k_parsed * d
                    yv_mw[j] = _format_numeric(prod, rounding_digits)
                    ynt[j] = _format_full_numeric_tooltip(prod)
                r["year_values"] = yv_mw
                r["year_numeric_tooltips"] = ynt
            elif coeff_base_year is not None and dm_block == "UnionEnergySystemDemandParameter" and pk in pk_medium_ues_sync:
                yv_mw = list(r.get("year_values") or [])
                if len(yv_mw) < n_y:
                    yv_mw.extend(["—"] * (n_y - len(yv_mw)))
                ynt = list(r.get("year_numeric_tooltips") or [])
                if len(ynt) < n_y:
                    ynt.extend([""] * (n_y - len(ynt)))
                for j in range(n_y):
                    y = years[j]
                    if not _coeff_union_res_sum_year(y, coeff_base_year):
                        continue
                    k_parsed = _parse_summary_cell_float(k_list[j] if j < len(k_list) else None)
                    d = denoms[j] if j < len(denoms) else None
                    if k_parsed is None or d is None or not (d > 0):
                        continue
                    prod = k_parsed * d
                    if pk == "calculated_max_power_mw":
                        yv_mw[j] = _format_calculated_max_mw(prod)
                    else:
                        yv_mw[j] = _format_numeric(prod, rounding_digits)
                    ynt[j] = _format_full_numeric_tooltip(prod)
                r["year_values"] = yv_mw
                r["year_numeric_tooltips"] = ynt
        i += block_size
    if coeff_base_year is not None:
        _coeff_years = lambda y: _coeff_union_res_sum_year(y, coeff_base_year)
        enrich_oes_ees_russia_calculated_max_via_oes(
            summary_rows,
            years,
            rounding_digits,
            year_included=_coeff_years,
        )
        enrich_oes_ees_russia_calculated_max_via_es(
            summary_rows,
            years,
            rounding_digits,
            year_included=_coeff_years,
        )


def _flatten_entities(
    entities: list[SummaryEntity],
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for entity in entities:
        flattened.extend(
            _flatten_entity(
                entity,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
            )
        )
    return flattened


def _slice_row_ids(demand_rows: list[Any]) -> dict[Any, int]:
    """Ключ среза «hist» или номер года → id строки параметров."""
    out: dict[Any, int] = {}
    for row in demand_rows:
        if getattr(row, "is_historical_maximum", False):
            sk: Any = "hist"
        else:
            sk = getattr(row, "year_number", None)
        if sk is not None:
            rid = getattr(row, "id", None)
            if rid is not None:
                out[sk] = int(rid)
    return out


def _indexed_demand_rows_by_slice(demand_rows: list[Any]) -> dict[Any, Any]:
    """hist → объект строки; календарный год → объект строки."""
    out: dict[Any, Any] = {}
    for row in demand_rows:
        if getattr(row, "is_historical_maximum", False):
            out["hist"] = row
        else:
            yn = getattr(row, "year_number", None)
            if yn is not None:
                out[int(yn)] = row
    return out


_COEFF_PARAM_TO_K_ATTR = {
    "combined_on_oes": "coeff_k_combined_on_oes",
    "combined_on_ees": "coeff_k_combined_on_ees",
    "calculated_max_power_mw": "coeff_k_calculated_max_power_mw",
    "calculated_combined_on_ees_mw": "coeff_k_calculated_combined_on_ees_mw",
}


def _year_coeff_k_stored_for_flat(
    *,
    parameter_key: str,
    demand_model_name: str | None,
    years: list[int],
    by_slice: dict[Any, Any],
    rounding_digits: int,
) -> list[str]:
    """Подписи сохранённого k для строки параметра сводки (совпадают с округлением столбца k)."""
    if demand_model_name not in (
        "RegionalEnergySystemDemandParameter",
        "UnionEnergySystemDemandParameter",
    ):
        return []
    attr = _COEFF_PARAM_TO_K_ATTR.get(parameter_key)
    if attr is None:
        return []
    if demand_model_name == "RegionalEnergySystemDemandParameter":
        if parameter_key not in ("combined_on_oes", "combined_on_ees"):
            return []
    elif demand_model_name == "UnionEnergySystemDemandParameter":
        if parameter_key not in (
            "calculated_max_power_mw",
            "combined_on_ees",
            "calculated_combined_on_ees_mw",
        ):
            return []
    out: list[str] = []
    for year in years:
        row = by_slice.get(year)
        if row is None:
            out.append("—")
            continue
        v = getattr(row, attr, None)
        if v is None:
            out.append("—")
        else:
            out.append(_format_numeric(v, rounding_digits))
    return out


def _aggregation_level_header_row(
    entity: SummaryEntity,
    years: list[int],
) -> dict[str, Any]:
    """Строка уровня агрегации без показателей (только подпись сущности)."""
    n_y = len(years)
    return {
        "entity_label": entity.label,
        "entity_rowspan": 1,
        "entity_depth": entity.depth,
        "entity_kind": entity.entity_kind,
        "show_entity_cell": True,
        "parameter_key": "",
        "parameter_label": "",
        "demand_model_name": None,
        "parent_fk_column": None,
        "parent_id": None,
        "hist_row_id": None,
        "year_row_ids": [None for _ in years],
        "hist_value": "—",
        "year_values": ["—" for _ in years],
        "hist_numeric_tooltip": "",
        "year_numeric_tooltips": ["" for _ in years],
        "id_union_energy_system": getattr(entity, "id_union_energy_system", None),
        "id_regional_energy_system": getattr(entity, "id_regional_energy_system", None),
        "id_regional_district": getattr(entity, "id_regional_district", None),
        "id_federal_district": getattr(entity, "id_federal_district", None),
        "id_energy_zone": getattr(entity, "id_energy_zone", None),
        "id_synchronous_area": getattr(entity, "id_synchronous_area", None),
        "perimeter_variant_code": getattr(entity, "perimeter_variant_code", None),
        "year_coeff_k_stored": [],
        "entity_note_text": "",
        "entity_note_row_id": None,
        "show_entity_note_cell": False,
        "pd_pd_aggregation_level_row": True,
        "pd_pd_aggregation_level_full_row": True,
        "pd_pd_skip_empty_hide_row": True,
    }


def _flatten_entity(
    entity: SummaryEntity,
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> list[dict[str, Any]]:
    entity_rows: list[dict[str, Any]] = []
    if entity.entity_kind == "aggregation_level" and not entity.parameters:
        entity_rows.append(_aggregation_level_header_row(entity, years))
        for child in entity.children:
            entity_rows.extend(
                _flatten_entity(
                    child,
                    years,
                    rounding_digits,
                    avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
                )
            )
        return entity_rows
    parameter_maps, tooltip_maps = _build_parameter_maps(
        entity.demand_rows,
        entity.parameters,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    slice_ids = _slice_row_ids(entity.demand_rows)
    dm_name = entity.demand_model_name
    demand_by_slice = _indexed_demand_rows_by_slice(entity.demand_rows)
    ues_id_flat = getattr(entity, "id_union_energy_system", None)
    if (
        ues_id_flat is None
        and getattr(entity, "parent_fk_column", None) == "id_union_energy_system"
        and getattr(entity, "parent_id", None) is not None
    ):
        ues_id_flat = entity.parent_id

    hist_note_row = next(
        (r for r in entity.demand_rows if getattr(r, "is_historical_maximum", False)),
        None,
    )
    entity_note_rid = getattr(hist_note_row, "id", None) if hist_note_row is not None else None
    raw_note = getattr(hist_note_row, "note", None) if hist_note_row is not None else None
    entity_note_text = "" if raw_note in (None, "") else str(raw_note)

    for index, (parameter_key, parameter_label) in enumerate(entity.parameters):
        values = parameter_maps.get(parameter_key, {})
        tt = tooltip_maps.get(parameter_key, {})
        year_row_ids = [slice_ids.get(year) for year in years]
        entity_rows.append(
            {
                "entity_label": entity.label,
                "entity_rowspan": len(entity.parameters),
                "entity_depth": entity.depth,
                "entity_kind": entity.entity_kind,
                "show_entity_cell": index == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": dm_name,
                "parent_fk_column": entity.parent_fk_column,
                "parent_id": entity.parent_id,
                "hist_row_id": slice_ids.get("hist"),
                "year_row_ids": year_row_ids,
                "hist_value": values.get("hist", "—"),
                "year_values": [values.get(year, "—") for year in years],
                "hist_numeric_tooltip": tt.get("hist", ""),
                "year_numeric_tooltips": [tt.get(year, "") for year in years],
                "id_union_energy_system": ues_id_flat,
                "id_regional_energy_system": getattr(
                    entity, "id_regional_energy_system", None
                ),
                "id_regional_district": getattr(entity, "id_regional_district", None),
                "id_federal_district": getattr(entity, "id_federal_district", None),
                "id_energy_zone": getattr(entity, "id_energy_zone", None),
                "id_synchronous_area": getattr(entity, "id_synchronous_area", None),
                "id_energy_unit": getattr(entity, "id_energy_unit", None),
                "perimeter_variant_code": getattr(entity, "perimeter_variant_code", None),
                "year_coeff_k_stored": _year_coeff_k_stored_for_flat(
                    parameter_key=parameter_key,
                    demand_model_name=dm_name,
                    years=years,
                    by_slice=demand_by_slice,
                    rounding_digits=rounding_digits,
                ),
                "entity_note_text": entity_note_text,
                "entity_note_row_id": entity_note_rid,
                "show_entity_note_cell": index == 0,
            }
        )
        if entity.is_decentralized_zone_energy_unit:
            entity_rows[-1]["pd_pd_decentralized_zone_mark"] = True

    for child in entity.children:
        entity_rows.extend(
            _flatten_entity(
                child,
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
            )
        )
    return entity_rows


def _format_full_numeric_tooltip(value: Any) -> str:
    """Полное отображение числа для title (как format_decimal_trim(0) на странице demand_edit)."""
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
    result: dict[str, dict[Any, str]] = {param_key: {} for param_key, _ in parameters}
    param_keys = {pk for pk, _ in parameters}
    tooltip_keys = param_keys & _NUMERIC_ROUNDING_TOOLTIP_KEYS
    tooltips: dict[str, dict[Any, str]] = {pk: {} for pk in tooltip_keys}
    if avg_temp_uses_global_rounding and "avg_temp" in param_keys:
        tooltips["avg_temp"] = {}

    for row in demand_rows:
        slice_key = "hist" if getattr(row, "is_historical_maximum", False) else getattr(row, "year_number", None)
        if slice_key is None:
            continue

        if "max_power" in result:
            result["max_power"][slice_key] = _format_numeric(
                getattr(row, "max_power_consumption_mw", None),
                rounding_digits,
            )
        if "max_power" in tooltips:
            tooltips["max_power"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "max_power_consumption_mw", None)
            )
        if "peak_datetime" in result:
            result["peak_datetime"][slice_key] = _dash(
                dps.format_peak_datetime_for_slice(
                    getattr(row, "peak_datetime_msk", None),
                    slice_key == "hist",
                )
            )
        if "avg_temp" in result:
            result["avg_temp"][slice_key] = _format_numeric(
                getattr(row, "avg_daily_air_temp_c", None),
                rounding_digits if avg_temp_uses_global_rounding else 0,
            )
        if "avg_temp" in tooltips:
            tooltips["avg_temp"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "avg_daily_air_temp_c", None)
            )
        if "combined_on_oes" in result:
            result["combined_on_oes"][slice_key] = _format_numeric(
                getattr(row, "combined_on_oes", None),
                rounding_digits,
            )
        if "combined_on_oes" in tooltips:
            tooltips["combined_on_oes"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_oes", None)
            )
        if "combined_on_ees" in result:
            result["combined_on_ees"][slice_key] = _format_numeric(
                getattr(row, "combined_on_ees", None),
                rounding_digits,
            )
        if "combined_on_ees" in tooltips:
            tooltips["combined_on_ees"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_ees", None)
            )
        if "calculated_max_power_mw" in result:
            result["calculated_max_power_mw"][slice_key] = _format_calculated_max_mw(
                getattr(row, "calculated_max_power_mw", None),
            )
        if "calculated_max_power_mw" in tooltips:
            tooltips["calculated_max_power_mw"][slice_key] = _format_calculated_max_mw(
                getattr(row, "calculated_max_power_mw", None)
            )
        if "calculated_combined_on_ees_mw" in result:
            result["calculated_combined_on_ees_mw"][slice_key] = _format_calculated_max_mw(
                getattr(row, "calculated_combined_on_ees_mw", None),
            )
        if "calculated_combined_on_ees_mw" in tooltips:
            tooltips["calculated_combined_on_ees_mw"][slice_key] = _format_calculated_max_mw(
                getattr(row, "calculated_combined_on_ees_mw", None)
            )
        if "combined_on_es" in result:
            result["combined_on_es"][slice_key] = _format_numeric(
                getattr(row, "combined_on_es", None),
                rounding_digits,
            )
        if "combined_on_es" in tooltips:
            tooltips["combined_on_es"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_es", None)
            )
        if "combined_on_ez" in result:
            result["combined_on_ez"][slice_key] = _format_numeric(
                getattr(row, "combined_on_ez", None),
                rounding_digits,
            )
        if "combined_on_ez" in tooltips:
            tooltips["combined_on_ez"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_ez", None)
            )
        if "combined_on_fo" in result:
            result["combined_on_fo"][slice_key] = _format_numeric(
                getattr(row, "combined_on_fo", None),
                rounding_digits,
            )
        if "combined_on_fo" in tooltips:
            tooltips["combined_on_fo"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_fo", None)
            )
        if "combined_on_cz" in result:
            result["combined_on_cz"][slice_key] = _format_numeric(
                getattr(row, "combined_on_cz", None),
                rounding_digits,
            )
        if "combined_on_cz" in tooltips:
            tooltips["combined_on_cz"][slice_key] = _format_full_numeric_tooltip(
                getattr(row, "combined_on_cz", None)
            )

    return result, tooltips


def _rounding_digits_for_parameter(parameter_key: str, rounding_digits: int) -> int:
    if parameter_key in CALCULATED_MAX_PARAMETER_KEYS:
        return CALCULATED_MAX_MW_ROUNDING_DIGITS
    return rounding_digits


def _format_numeric(value: Any, digits: int) -> str:
    shown = format_decimal_trim_for_display(value, digits=digits)
    return _dash(apply_thousand_grouping_to_display(shown) if shown else shown)


def _format_calculated_max_mw(value: Any) -> str:
    """Расчётные максимумы: не более 3 знаков после запятой, без хвоста нулей (100, не 100,000)."""
    return _format_numeric(value, CALCULATED_MAX_MW_ROUNDING_DIGITS)


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
) -> SummaryEntity:
    return SummaryEntity(
        label=label,
        depth=0,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(demand_model, None, None),
        entity_kind=entity_kind,
        demand_model_name=demand_model.__name__,
        parent_fk_column=None,
        parent_id=None,
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _is_south_oes_name(name: str | None) -> bool:
    if not name or not str(name).strip():
        return False
    return str(name).strip().casefold() in _SOUTH_UES_LABELS_CF


def _get_federal_district_by_name(name: str) -> FederalDistrict | None:
    query = FederalDistrict.query
    query = dps.filter_parents_by_version(query, FederalDistrict)
    return query.filter(FederalDistrict.name == name).first()


def _south_ues_res_ids() -> frozenset[int]:
    """Id РЭС, входящих в ОЭС Юга (для позиции блока «Новые территории»)."""
    south = _find_south_union_energy_system()
    if south is None:
        return frozenset()
    return frozenset(
        int(res.id)
        for res in (south.regional_energy_systems or [])
        if _is_valid_named_item(res)
    )


def _regional_district_linked_to_south_ues(
    regional_district: RegionalDistrict,
    south_res_ids: frozenset[int],
) -> bool:
    if not south_res_ids:
        return False
    for res in regional_district.regional_energy_systems or []:
        if _is_valid_named_item(res) and int(res.id) in south_res_ids:
            return True
    return False


def _insert_child_after_south_ues_block(
    children: list[SummaryEntity],
    entity: SummaryEntity,
    *,
    last_south_child_index: int,
) -> list[SummaryEntity]:
    """Вставляет сущность сразу после последней строки РЭС/субъекта ОЭС Юга в списке детей."""
    new_ch = list(children)
    if last_south_child_index >= 0:
        new_ch.insert(last_south_child_index + 1, entity)
    else:
        new_ch.append(entity)
    return new_ch


def _find_south_union_energy_system() -> UnionEnergySystem | None:
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
        if _is_south_oes_name(getattr(ues, "name", None)):
            return ues
    return None


def _find_new_territories_union_energy_system() -> UnionEnergySystem | None:
    target_cf = _NEW_TERRITORIES_NAME.casefold()
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
        if str(getattr(ues, "name", None) or "").strip().casefold() == target_cf:
            return ues
    return None


def _south_federal_district_for_nt_attachment() -> tuple[FederalDistrict | None, int | None]:
    south = _find_south_union_energy_system()
    if south is None:
        return None, None
    fd_ids: set[int] = set()
    for res in south.regional_energy_systems or []:
        for rd in res.regional_districts or []:
            fid = getattr(rd, "id_federal_district", None)
            if fid is not None:
                fd_ids.add(int(fid))
    if not fd_ids:
        return None, south.id
    q = FederalDistrict.query.filter(FederalDistrict.id.in_(fd_ids))
    q = dps.filter_parents_by_version(q, FederalDistrict)
    candidates = [fd for fd in q.all() if _is_valid_named_item(fd)]
    if not candidates:
        return None, south.id
    big = 10**9
    best = min(
        candidates,
        key=lambda fd: (fd.display_order if fd.display_order is not None else big, fd.id),
    )
    return best, south.id


def _new_territories_regional_district_ids() -> frozenset[int]:
    return frozenset(int(rd.id) for rd in _load_new_territories_regional_districts())


def _load_new_territories_regional_districts() -> list[RegionalDistrict]:
    query = FederalDistrict.query.options(
        selectinload(FederalDistrict.regional_districts).selectinload(
            RegionalDistrict.regional_energy_systems
        ),
        selectinload(FederalDistrict.regional_districts).selectinload(RegionalDistrict.energy_units),
    )
    query = dps.filter_parents_by_version(query, FederalDistrict)
    federal_district = query.filter(FederalDistrict.name == _NEW_TERRITORIES_NAME).first()
    if federal_district is None:
        return []
    return [
        rd
        for rd in sorted(federal_district.regional_districts, key=_sort_by_name)
        if _is_valid_named_item(rd)
    ]


_NT_SUM_NUMERIC_FIELDS_FROM_SUBJECTS: tuple[str, ...] = (
    "max_power_consumption_mw",
    "combined_on_oes",
    "combined_on_ees",
    "combined_on_es",
    "combined_on_fo",
    "combined_on_cz",
    "combined_on_ez",
)


def _new_territories_demand_rows_summed_from_subjects() -> list[SimpleNamespace]:
    """Сумма числовых показателей по субъектам ФО «Новые территории» (для строки-агрегата НТ)."""
    by_year: dict[int, dict[str, list[Decimal]]] = {}
    for rd in _load_new_territories_regional_districts():
        rows = dps.get_demand_rows(
            RegionalDistrictDemandParameter,
            "id_regional_district",
            rd.id,
        )
        for r in rows:
            y = getattr(r, "year_number", None)
            if y is None:
                continue
            yi = int(y)
            bucket = by_year.setdefault(yi, {})
            for field in _NT_SUM_NUMERIC_FIELDS_FROM_SUBJECTS:
                v = _decimal_or_none(getattr(r, field, None))
                if v is not None:
                    bucket.setdefault(field, []).append(v)
    years = sorted(by_year.keys())
    out: list[SimpleNamespace] = []
    for y in years:
        parts = by_year.get(y, {})
        kwargs: dict[str, Any] = {"year_number": y}
        for field in _NT_SUM_NUMERIC_FIELDS_FROM_SUBJECTS:
            vals = parts.get(field, [])
            kwargs[field] = sum(vals, Decimal(0)) if vals else None
        out.append(SimpleNamespace(**kwargs))
    return out


def _new_territories_parent_demand_rows(nt_fd: FederalDistrict | None) -> list[Any]:
    summed = _new_territories_demand_rows_summed_from_subjects()
    if summed:
        return summed
    if nt_fd is not None:
        return dps.get_demand_rows(
            FederalDistrictDemandParameter,
            "id_federal_district",
            nt_fd.id,
        )
    return []


def _res_id_for_nt_rd(regional_district: RegionalDistrict, south_ues_id: int) -> int | None:
    valid_res = [
        res
        for res in sorted(regional_district.regional_energy_systems, key=_sort_by_name)
        if _is_valid_named_item(res)
    ]
    for res in valid_res:
        if getattr(res, "id_union_energy_system", None) == south_ues_id:
            return int(res.id)
    if valid_res:
        return int(valid_res[0].id)
    return None


def _build_nt_subject_entities_for_under_south(
    *,
    south_ues_id: int,
    rd_depth: int,
    subject_parameters: tuple[tuple[str, str], ...],
    id_federal_district_for_rd: int | None = None,
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for regional_district in _load_new_territories_regional_districts():
        res_id = _res_id_for_nt_rd(regional_district, south_ues_id)
        eus_param: list[EnergyUnit] | None = None
        if res_id is not None:
            eus = _filter_energy_units_for_res(regional_district.energy_units, res_id)
            if not eus:
                res_obj = next(
                    (r for r in regional_district.regional_energy_systems if r.id == res_id),
                    None,
                )
                if res_obj is not None:
                    eus = _filter_valid_items(res_obj.energy_units)
            eus_param = eus
        out.append(
            _build_regional_district_entity(
                regional_district,
                depth=rd_depth,
                energy_units=eus_param,
                parameters=subject_parameters,
                ues_id=south_ues_id,
                res_id=res_id,
                id_federal_district=id_federal_district_for_rd,
            )
        )
    return out


def _build_nt_under_south_res_level_entity_oes(
    south_ues_id: int,
    nt_fd: FederalDistrict | None,
) -> SummaryEntity | None:
    children = _build_nt_subject_entities_for_under_south(
        south_ues_id=south_ues_id,
        rd_depth=3,
        subject_parameters=PARAMETERS_WITH_OES_EES_AND_ES,
    )
    if not children:
        return None
    if nt_fd is None:
        nt_fd = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    return SummaryEntity(
        label=getattr(nt_fd, "name", None) or _NEW_TERRITORIES_NAME,
        depth=2,
        parameters=tuple(),
        demand_rows=[],
        entity_kind="aggregation_level",
        children=children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        id_union_energy_system=south_ues_id,
    )


def _build_south_ues_base_group_entity(south: UnionEnergySystem) -> SummaryEntity:
    """Дерево РЭС/субъектов ОЭС Юга (без строки параметров на уровне ОЭС)."""
    child_entities = [
        _build_regional_energy_system_entity(
            res,
            ues_id=south.id,
        )
        for res in sorted(south.regional_energy_systems, key=_sort_by_name)
        if _is_valid_named_item(res)
    ]
    return SummaryEntity(
        label=south.name or "",
        depth=1,
        parameters=PARAMETERS_UES_OES,
        demand_rows=[],
        entity_kind="group",
        children=child_entities,
        demand_model_name=UnionEnergySystemDemandParameter.__name__,
        parent_fk_column="id_union_energy_system",
        parent_id=south.id,
        id_union_energy_system=south.id,
        perimeter_variant_code=None,
    )


def _build_russia_perimeter_entities() -> list[SummaryEntity]:
    """Строки «Россия» по привязке entity_kind=russia_federation (каталог /perimeter_variants/)."""
    binding = resolve_entity_perimeter_binding(
        ENTITY_KIND_RUSSIA_FEDERATION,
        RUSSIA_FEDERATION_AGGREGATE_NAME,
    )
    if binding is None or not binding.variants:
        return [
            SummaryEntity(
                label="Россия с НТ",
                depth=0,
                parameters=PARAMETERS_RUSSIA_OES_SUMMARY,
                demand_rows=dps.get_demand_rows_for_summary_block(
                    RussiaFederationDemandParameter,
                    None,
                    None,
                    display_perimeter_variant_code=CODE_WITH_NT,
                ),
                entity_kind="oes_top_aggregate",
                demand_model_name=RussiaFederationDemandParameter.__name__,
                parent_fk_column=None,
                parent_id=None,
                perimeter_variant_code=CODE_WITH_NT,
            ),
            SummaryEntity(
                label="Россия без НТ",
                depth=0,
                parameters=PARAMETERS_RUSSIA_OES_SUMMARY,
                demand_rows=dps.get_demand_rows_for_summary_block(
                    RussiaFederationDemandParameter,
                    None,
                    None,
                    display_perimeter_variant_code=CODE_WITHOUT_NT,
                ),
                entity_kind="oes_top_aggregate",
                demand_model_name=RussiaFederationDemandParameter.__name__,
                parent_fk_column=None,
                parent_id=None,
                perimeter_variant_code=CODE_WITHOUT_NT,
            ),
        ]

    model = RussiaFederationDemandParameter
    mn = model.__name__
    out: list[SummaryEntity] = []
    for vdef in binding.variants:
        out.append(
            SummaryEntity(
                label=variant_label_for_entity(binding, vdef),
                depth=0,
                parameters=PARAMETERS_RUSSIA_OES_SUMMARY,
                demand_rows=dps.get_demand_rows(
                    model,
                    None,
                    None,
                    perimeter_variant_code=vdef.code,
                ),
                entity_kind="oes_top_aggregate",
                demand_model_name=mn,
                parent_fk_column=None,
                parent_id=None,
                perimeter_variant_code=vdef.code,
            )
        )
    return out


def _build_ees_perimeter_entities() -> list[SummaryEntity]:
    """Строки «ЭЭС России» (EesDemandParameter) по привязке entity_kind=ees_russia."""
    binding = resolve_entity_perimeter_binding(
        ENTITY_KIND_EES_RUSSIA,
        EES_RUSSIA_AGGREGATE_NAME,
    )
    model = EesDemandParameter
    mn = model.__name__

    def _entity(vcode: str, label: str) -> SummaryEntity:
        return SummaryEntity(
            label=label,
            depth=0,
            parameters=PARAMETERS_EES_AGGREGATE_OES_SUMMARY,
            demand_rows=dps.get_demand_rows_for_summary_block(
                model,
                None,
                None,
                display_perimeter_variant_code=vcode,
            ),
            entity_kind="oes_top_aggregate",
            demand_model_name=mn,
            parent_fk_column=None,
            parent_id=None,
            perimeter_variant_code=vcode,
        )

    if binding is None or not binding.variants:
        return [
            _entity(CODE_WITH_NT, "ЭЭС России с НТ"),
            _entity(CODE_WITHOUT_NT, "ЭЭС России без НТ"),
        ]

    variants = ordered_tree_variants_for_display(binding)
    if not variants:
        return [
            _entity(CODE_WITH_NT, "ЭЭС России с НТ"),
            _entity(CODE_WITHOUT_NT, "ЭЭС России без НТ"),
        ]

    return [
        _entity(
            vdef.code,
            variant_label_for_entity(binding, vdef),
        )
        for vdef in variants
    ]


def _build_ees_russia_perimeter_entities(
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    """ЕЭС России (ЕЭС): with_nt — верхний агрегат; without_nt — group-root с ОЭС/СЗ."""
    binding = resolve_entity_perimeter_binding(
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        EES_UNIFIED_REF_NAME,
    )
    model = EesRussiaDemandParameter
    mn = model.__name__

    def _without_nt_group(label: str) -> SummaryEntity:
        ues_list = _build_ues_entities_filtered(
            _is_ees_branch,
            always_show_subject_row_under_res=always_show_subject_row_under_res,
        )
        ues_list = _inject_perimeter_variant_entities(
            ues_list, entity_kind="union_energy_system"
        )
        return SummaryEntity(
            label=label,
            depth=0,
            parameters=PARAMETERS_EES_RUSSIA_OES_SUMMARY,
            demand_rows=dps.get_demand_rows_for_summary_block(
                model,
                None,
                None,
                display_perimeter_variant_code=CODE_WITHOUT_NT,
            ),
            entity_kind="group-root",
            children=_build_synchronous_area_entities(depth=1) + ues_list,
            demand_model_name=mn,
            parent_fk_column=None,
            parent_id=None,
            perimeter_variant_code=CODE_WITHOUT_NT,
        )

    def _with_nt_top(label: str, vcode: str) -> SummaryEntity:
        return SummaryEntity(
            label=label,
            depth=0,
            parameters=PARAMETERS_EES_RUSSIA_OES_SUMMARY,
            demand_rows=dps.get_demand_rows_for_summary_block(
                model,
                None,
                None,
                display_perimeter_variant_code=vcode,
            ),
            entity_kind="oes_top_aggregate",
            demand_model_name=mn,
            parent_fk_column=None,
            parent_id=None,
            perimeter_variant_code=vcode,
        )

    variants = _pd_nt_perimeter_variant_defs(binding)
    out: list[SummaryEntity] = []
    for vdef in variants:
        if binding is not None:
            lbl = variant_label_for_entity(binding, vdef)
        elif vdef.code == CODE_WITH_NT:
            lbl = f"{EES_UNIFIED_REF_NAME} с НТ"
        else:
            lbl = f"{EES_UNIFIED_REF_NAME} без НТ"
        if vdef.code == CODE_WITHOUT_NT:
            out.append(_without_nt_group(lbl))
        else:
            out.append(_with_nt_top(lbl, vdef.code))
    return out


def _inject_perimeter_variant_entities(
    entities: list[SummaryEntity],
    *,
    entity_kind: str,
) -> list[SummaryEntity]:
    """Строки вариантов периметра по привязкам из справочника.

    Для ОЭС на сводке показываем ровно привязанные варианты, в порядке sort_order.
    Дерево РЭС висит у варианта с галочкой «Базовый»; для ОЭС Юга туда же добавляется
    блок «Новые территории». Позиция самой ОЭС в списке — по display_order справочника ОЭС.
    """
    ues_mn = UnionEnergySystemDemandParameter.__name__
    replacements: dict[int, tuple[tuple[int, str, int], list[SummaryEntity]]] = {}

    for binding in entity_perimeter_bindings():
        if binding.entity_kind != entity_kind:
            continue
        if entity_kind == "union_energy_system":
            parent = _find_union_energy_system_by_name(binding.entity_name_cf)
            if parent is None:
                continue
            parent_id = int(parent.id)
            is_south = binding.entity_name_cf == "оэс юга"
            base = _build_south_ues_base_group_entity(parent)
            res_children = list(base.children)
            territorial_children = list(res_children)
            if is_south:
                nt_fd = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
                nt_entity = _build_nt_under_south_res_level_entity_oes(
                    parent_id, nt_fd
                )
                if nt_entity is not None:
                    territorial_children.append(nt_entity)
            variant_defs = (
                _pd_nt_perimeter_variant_defs(binding)
                if is_south
                else tuple(binding.variants)
            )
            base_code = (
                CODE_WITHOUT_NT
                if is_south
                else (variant_defs[0].code if variant_defs else None)
            )
            variant_entities: list[SummaryEntity] = []
            for vdef in variant_defs:
                children: list[SummaryEntity] = []
                if vdef.code == base_code:
                    children = list(territorial_children)
                variant_entities.append(
                    SummaryEntity(
                        label=variant_label_for_entity(binding, vdef),
                        depth=1,
                        parameters=PARAMETERS_UES_OES,
                        demand_rows=dps.get_demand_rows(
                            UnionEnergySystemDemandParameter,
                            "id_union_energy_system",
                            parent_id,
                            perimeter_variant_code=vdef.code,
                        ),
                        entity_kind="perimeter_variant",
                        children=children,
                        demand_model_name=ues_mn,
                        parent_fk_column="id_union_energy_system",
                        parent_id=parent_id,
                        id_union_energy_system=parent_id,
                        perimeter_variant_code=vdef.code,
                    )
                )
            replacements[parent_id] = (_ues_summary_sort_key(parent), variant_entities)

    if not replacements:
        return entities

    nt_ues = _find_new_territories_union_energy_system()
    nt_ues_id = int(nt_ues.id) if nt_ues is not None else None
    scoped: list[SummaryEntity] = []
    for e in entities:
        skip = False
        if e.demand_model_name == ues_mn and e.id_union_energy_system is not None:
            uid = int(e.id_union_energy_system)
            if uid in replacements:
                skip = True
            if nt_ues_id is not None and uid == nt_ues_id:
                skip = True
        if not skip:
            scoped.append(e)

    final: list[SummaryEntity] = list(scoped)
    for _pid, (sort_key, variant_list) in sorted(
        replacements.items(), key=lambda x: x[1][0]
    ):
        group_keys = _oes_group_sort_keys_by_ues_id(final)
        insert_at = len(final)
        for i, e in enumerate(final):
            if e.entity_kind != "group" or e.id_union_energy_system is None:
                continue
            row_key = group_keys.get(
                int(e.id_union_energy_system),
                (10**9, (e.label or "").casefold(), int(e.id_union_energy_system)),
            )
            if row_key > sort_key:
                insert_at = i
                break
        final = final[:insert_at] + variant_list + final[insert_at:]
    return final


def _find_union_energy_system_by_name(name_cf: str) -> UnionEnergySystem | None:
    query = UnionEnergySystem.query.options(
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.regional_districts
        ),
        selectinload(UnionEnergySystem.regional_energy_systems).selectinload(
            RegionalEnergySystem.energy_units
        ),
    )
    query = dps.filter_parents_by_version(query, UnionEnergySystem)
    for ues in query.all():
        if not _is_valid_named_item(ues):
            continue
        if str(getattr(ues, "name", None) or "").strip().casefold() == name_cf:
            return ues
    return None


def _build_fo_nt_under_south_entity(
    south_fd: FederalDistrict,
    south_ues_id: int,
    nt_fd: FederalDistrict | None,
    *,
    res_parameters: tuple[tuple[str, str], ...],
    subject_parameters: tuple[tuple[str, str], ...],
) -> SummaryEntity | None:
    children = _build_nt_subject_entities_for_under_south(
        south_ues_id=south_ues_id,
        rd_depth=2,
        subject_parameters=subject_parameters,
        id_federal_district_for_rd=int(south_fd.id),
    )
    if not children:
        return None
    if nt_fd is None:
        nt_fd = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    south_fd_id = int(south_fd.id)
    return SummaryEntity(
        label=getattr(nt_fd, "name", None) or _NEW_TERRITORIES_NAME,
        depth=1,
        parameters=tuple(),
        demand_rows=[],
        entity_kind="aggregation_level",
        children=children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        id_federal_district=south_fd_id,
        id_union_energy_system=south_ues_id,
    )


def _build_new_territories_energy_zone_entity(
    *,
    depth: int = 0,
    subject_depth: int | None = None,
    entity_kind: str = "group-root",
    id_energy_zone: int | None = None,
) -> SummaryEntity | None:
    """Ветка «Новые территории» на сводке по энергозонам: субъекты РФ (без уровня РЭС)."""
    federal_district = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    regional_districts = _load_new_territories_regional_districts()
    if federal_district is None and not regional_districts:
        return None

    rd_depth = subject_depth if subject_depth is not None else depth + 1
    children: list[SummaryEntity] = []
    parent_id = getattr(federal_district, "id", None)
    for regional_district in regional_districts:
        valid_res = [
            res
            for res in sorted(regional_district.regional_energy_systems, key=_sort_by_name)
            if _is_valid_named_item(res)
        ]
        if not valid_res:
            continue
        res = valid_res[0]
        uid = getattr(res, "id_union_energy_system", None)
        children.append(
            _build_regional_district_entity(
                regional_district,
                depth=rd_depth,
                energy_units=_filter_energy_units_for_res(
                    regional_district.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_RES,
                ues_id=int(uid) if uid is not None else None,
                res_id=res.id,
                id_federal_district=parent_id,
                id_energy_zone=id_energy_zone,
            )
        )

    if not children:
        return None

    return SummaryEntity(
        label=getattr(federal_district, "name", None) or _NEW_TERRITORIES_NAME,
        depth=depth,
        parameters=tuple(),
        demand_rows=[],
        entity_kind="aggregation_level",
        children=children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        id_federal_district=parent_id,
        id_energy_zone=id_energy_zone,
    )


def _build_ues_entities_filtered(
    ues_predicate: Callable[[UnionEnergySystem], bool],
    *,
    always_show_subject_row_under_res: bool = False,
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
        if _is_south_oes_name(getattr(ues, "name", None)):
            continue
        entities.append(
            SummaryEntity(
                label=ues.name,
                depth=1,
                parameters=PARAMETERS_UES_OES,
                demand_rows=dps.get_demand_rows(
                    UnionEnergySystemDemandParameter,
                    "id_union_energy_system",
                    ues.id,
                    perimeter_variant_code=None,
                ),
                entity_kind="group",
                children=child_entities,
                demand_model_name=UnionEnergySystemDemandParameter.__name__,
                parent_fk_column="id_union_energy_system",
                parent_id=ues.id,
                id_union_energy_system=ues.id,
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
        # Совмещенный максимум потребления мощности субъекта РФ на РЭС — пока в РЭС несколько субъектов (эта ветка — уже ≥2 после фильтра имени).
        # Сводка по ОЭС: для субъектов РФ не показываем «на ФО» и «на централизованную зону»
        subject_children = [
            _build_regional_district_entity(
                regional_district,
                depth=3,
                energy_units=_filter_energy_units_for_res(
                    regional_district.energy_units,
                    res.id,
                ),
                parameters=PARAMETERS_WITH_OES_EES_AND_ES,
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
                parameters=PARAMETERS_WITH_OES_EES_AND_ES,
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
        parameters=PARAMETERS_WITH_OES_AND_EES,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemDemandParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemDemandParameter.__name__,
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
        parameters=PARAMETERS_RES,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemDemandParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=subject_children,
        demand_model_name=RegionalEnergySystemDemandParameter.__name__,
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
    south_res_ids = _south_ues_res_ids()

    entities: list[SummaryEntity] = []
    inject_zone_index = -1
    inject_after_res_index = -1
    inject_zone_id: int | None = None
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
            if int(res.id) in south_res_ids:
                inject_zone_index = len(entities)
                inject_after_res_index = len(res_children) - 1
                inject_zone_id = ez.id
        entities.append(
            SummaryEntity(
                label=f"{ez.number} — {ez.name}",
                depth=0,
                parameters=PARAMETERS_ENERGY_ZONE,
                demand_rows=dps.get_demand_rows(
                    EnergyZoneDemandParameter,
                    "id_energy_zone",
                    ez.id,
                ),
                entity_kind="group",
                children=res_children,
                demand_model_name=EnergyZoneDemandParameter.__name__,
                parent_fk_column="id_energy_zone",
                parent_id=ez.id,
                id_energy_zone=ez.id,
            )
        )
    if inject_zone_index >= 0:
        nt_entity = _build_new_territories_energy_zone_entity(
            depth=1,
            subject_depth=2,
            entity_kind="child",
            id_energy_zone=inject_zone_id,
        )
        if nt_entity is not None:
            zone_ent = entities[inject_zone_index]
            new_ch = _insert_child_after_south_ues_block(
                list(zone_ent.children),
                nt_entity,
                last_south_child_index=inject_after_res_index,
            )
            entities[inject_zone_index] = replace(zone_ent, children=new_ch)
    else:
        nt_entity = _build_new_territories_energy_zone_entity()
        if nt_entity is not None:
            entities.append(nt_entity)
    return entities


def _build_synchronous_area_entities(*, depth: int = 0) -> list[SummaryEntity]:
    """Строки сводки по ОЭС: одна сущность на каждую синхронную зону (как энергозона по показателям).

    «Первая синхронная зона» — варианты периметра with_nt / without_nt (как у «Россия»).

    Порядок — по ``SynchronousArea.display_order`` (как в справочнике), затем имя и id.

    В сводке по ОЭС вложены под «ЕЭС России без НТ» — depth=1, чтобы шли после агрегата и перед ОЭС.
    """
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    query = query.order_by(
        SynchronousArea.display_order.asc().nullslast(),
        SynchronousArea.name.asc(),
        SynchronousArea.id.asc(),
    )
    sa_list = [sa for sa in query.all() if _is_valid_named_item(sa)]
    sa_list.sort(key=synchronous_area_display_order_sort_key)
    entities: list[SummaryEntity] = []
    mn = SynchronousAreaDemandParameter.__name__
    for sa in sa_list:
        base_label = _synchronous_area_display_label(sa)
        if _is_first_synchronous_area_name(sa.name):
            binding = resolve_entity_perimeter_binding("synchronous_area", sa.name)
            for vdef in _pd_nt_perimeter_variant_defs(binding):
                if binding is not None:
                    lbl = variant_label_for_entity(binding, vdef)
                elif vdef.code == CODE_WITH_NT:
                    lbl = f"{base_label} с НТ"
                else:
                    lbl = f"{base_label} без НТ"
                entities.append(
                    SummaryEntity(
                        label=lbl,
                        depth=depth,
                        parameters=PARAMETERS_FIRST_SYNCHRONOUS_AREA_OES_SUMMARY,
                        demand_rows=dps.get_demand_rows(
                            SynchronousAreaDemandParameter,
                            "id_synchronous_area",
                            sa.id,
                            perimeter_variant_code=vdef.code,
                        ),
                        entity_kind="synchronous_area",
                        demand_model_name=mn,
                        parent_fk_column="id_synchronous_area",
                        parent_id=sa.id,
                        id_synchronous_area=sa.id,
                        perimeter_variant_code=vdef.code,
                    )
                )
            continue
        entities.append(
            SummaryEntity(
                label=base_label,
                depth=depth,
                parameters=PARAMETERS_SYNCHRONOUS_AREA,
                demand_rows=dps.get_demand_rows(
                    SynchronousAreaDemandParameter,
                    "id_synchronous_area",
                    sa.id,
                    perimeter_variant_code=CODE_WITHOUT_NT,
                ),
                entity_kind="synchronous_area",
                demand_model_name=mn,
                parent_fk_column="id_synchronous_area",
                parent_id=sa.id,
                id_synchronous_area=sa.id,
                perimeter_variant_code=CODE_WITHOUT_NT,
            )
        )
    return entities


def _energy_unit_belongs_to_placeholder_res(energy_unit: EnergyUnit) -> bool:
    """Энергорайон без привязки к ЕЭС/ТИТЭС (РЭС «не указано» в справочнике)."""
    res_obj = getattr(energy_unit, "regional_energy_system", None)
    res_name = (getattr(res_obj, "name", None) or "").strip().casefold()
    return res_name in PLACEHOLDER_NAMES


def _normalized_union_energy_system_label_cf(label: object) -> str:
    return str(label or "").strip().casefold().replace(" ", "")


def _is_tites_siberia_ues(ues: UnionEnergySystem) -> bool:
    return _normalized_union_energy_system_label_cf(getattr(ues, "name", None)) == _TITES_SIBERIA_UES_NAME_CF


def _is_tites_east_ues(ues: UnionEnergySystem) -> bool:
    return _normalized_union_energy_system_label_cf(getattr(ues, "name", None)) == _TITES_EAST_UES_NAME_CF


def _decentralized_energy_units_by_regional_district() -> dict[int, list[EnergyUnit]]:
    """Энергорайоны без привязки к ЕЭС/ТИТЭС, сгруппированные по субъекту РФ."""
    query = EnergyUnit.query.options(
        selectinload(EnergyUnit.regional_district),
        selectinload(EnergyUnit.regional_energy_system),
    )
    query = dps.filter_parents_by_version(query, EnergyUnit)
    by_rd: dict[int, list[EnergyUnit]] = {}
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        if not _energy_unit_belongs_to_placeholder_res(energy_unit):
            continue
        rd_id = getattr(energy_unit, "id_regional_district", None)
        if rd_id is None:
            continue
        by_rd.setdefault(int(rd_id), []).append(energy_unit)
    return {rd_id: _filter_valid_items(units) for rd_id, units in by_rd.items()}


def _is_chukotka_regional_district(regional_district: RegionalDistrict) -> bool:
    return (
        str(getattr(regional_district, "name", None) or "").strip().casefold()
        == _CHUKOTKA_RD_LABEL.casefold()
    )


def _chukotka_energy_units_max_power_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> list[float | None]:
    """Сумма «Максимум потребления мощности, МВт» по энергорайонам ЭС Чукотского АО."""
    chukotka_res_id: int | None = None
    for row in summary_rows:
        if not row.get("show_entity_cell"):
            continue
        if str(row.get("entity_label") or "").strip() != _CHUKOTKA_RES_LABEL:
            continue
        raw = row.get("id_regional_energy_system")
        if raw is not None:
            chukotka_res_id = int(raw)
        break
    if chukotka_res_id is None:
        return [None] * len(years)

    n_y = len(years)
    sums = [0.0] * n_y
    any_vals = [False] * n_y
    eu_dm = EnergyUnitDemandParameter.__name__
    for row in summary_rows:
        if row.get("demand_model_name") != eu_dm:
            continue
        if row.get("parameter_key") != "max_power":
            continue
        if row.get("id_regional_energy_system") != chukotka_res_id:
            continue
        year_values = row.get("year_values") or []
        for ix in range(n_y):
            parsed = _parse_summary_cell_float(
                year_values[ix] if ix < len(year_values) else None
            )
            if parsed is None:
                continue
            sums[ix] += float(parsed)
            any_vals[ix] = True
    return [sums[ix] if any_vals[ix] else None for ix in range(n_y)]


def _inject_chukotka_rd_calculated_max_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
) -> None:
    """Чукотский АО (оба варианта периметра): расчётный максимум по сумме энергорайонов."""
    if not summary_rows or not years:
        return

    eu_sums = _chukotka_energy_units_max_power_sums(summary_rows, years)
    n_y = len(years)
    targets: list[tuple[int, int, dict[str, Any], float, str]] = []
    specs: tuple[tuple[str, str, str | None, float, str], ...] = (
        (
            _CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL,
            "chukotka_territorial_boundaries",
            CODE_TERRITORIAL_BOUNDARIES,
            _CHUKOTKA_CHERSKY_TRANSFER_MW,
            "chukotka_rd_territorial_calc_max_mw",
        ),
        (
            _CHUKOTKA_RD_LABEL,
            "child",
            None,
            0.0,
            "chukotka_rd_calc_max_mw",
        ),
    )
    for label, entity_kind, pvc, subtract_mw, formula_key in specs:
        block_start: int | None = None
        block_span = 0
        block0: dict[str, Any] | None = None
        for i, row in enumerate(summary_rows):
            if not row.get("show_entity_cell"):
                continue
            if str(row.get("entity_label") or "").strip() != label:
                continue
            if str(row.get("entity_kind") or "") != entity_kind:
                continue
            row_pvc = row.get("perimeter_variant_code")
            if pvc is None:
                if row_pvc is not None:
                    continue
            elif row_pvc != pvc:
                continue
            block_start = i
            block_span = int(row.get("entity_rowspan") or 1)
            block0 = row
            break
        if block_start is None or block0 is None or block_span < 1:
            continue
        targets.append((block_start, block_span, block0, subtract_mw, formula_key))

    for block_start, block_span, block0, subtract_mw, formula_key in sorted(
        targets, key=lambda item: item[0], reverse=True
    ):
        year_values: list[str] = []
        year_tooltips: list[str] = []
        for ix in range(n_y):
            base = eu_sums[ix]
            if base is None:
                year_values.append("—")
                year_tooltips.append("")
                continue
            value = float(base) - float(subtract_mw)
            year_values.append(_format_calculated_max_mw(value))
            year_tooltips.append(_format_calculated_max_mw(value))

        block_end = min(block_start + block_span, len(summary_rows))
        for j in range(block_start, block_end):
            if summary_rows[j].get("parameter_key") == "calculated_max_power_mw":
                summary_rows[j]["year_values"] = list(year_values)
                summary_rows[j]["year_numeric_tooltips"] = list(year_tooltips)
                summary_rows[j]["pd_formula_text_key"] = formula_key
                break
        else:
            insert_at = block_end
            for j in range(block_start, block_end):
                if str(summary_rows[j].get("parameter_key") or "") == "avg_temp":
                    insert_at = j + 1
                    break
            new_span = block_span + 1
            for k in range(block_start, block_end):
                summary_rows[k]["entity_rowspan"] = new_span
            note_text = str(block0.get("entity_note_text") or "")
            note_rid = block0.get("entity_note_row_id")
            summary_rows.insert(
                insert_at,
                {
                    "entity_label": block0.get("entity_label"),
                    "entity_rowspan": new_span,
                    "entity_depth": block0.get("entity_depth", 0),
                    "entity_kind": block0.get("entity_kind"),
                    "show_entity_cell": False,
                    "parameter_key": "calculated_max_power_mw",
                    "parameter_label": "Расчетный максимум потребления мощности, МВт",
                    "demand_model_name": None,
                    "parent_fk_column": block0.get("parent_fk_column"),
                    "parent_id": block0.get("parent_id"),
                    "hist_row_id": None,
                    "year_row_ids": [None] * n_y,
                    "hist_value": "",
                    "year_values": list(year_values),
                    "hist_numeric_tooltip": "",
                    "year_numeric_tooltips": list(year_tooltips),
                    "id_union_energy_system": block0.get("id_union_energy_system"),
                    "id_regional_energy_system": block0.get(
                        "id_regional_energy_system"
                    ),
                    "id_regional_district": block0.get("id_regional_district"),
                    "perimeter_variant_code": block0.get("perimeter_variant_code"),
                    "year_coeff_k_stored": [],
                    "entity_note_text": note_text,
                    "entity_note_row_id": note_rid,
                    "show_entity_note_cell": False,
                    "pd_formula_text_key": formula_key,
                },
            )


def _build_chukotka_territorial_boundaries_subject_entity(
    source: SummaryEntity,
) -> SummaryEntity:
    """Строка субъекта РФ после «Чукотский АО» на сводке по ОЭС (без дочерних РЭС/ЭР)."""
    rd_id = source.parent_id or source.id_regional_district
    return replace(
        source,
        label=_CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL,
        entity_kind="chukotka_territorial_boundaries",
        children=[],
        demand_rows=dps.get_demand_rows(
            RegionalDistrictDemandParameter,
            "id_regional_district",
            rd_id,
            perimeter_variant_code=CODE_TERRITORIAL_BOUNDARIES,
        ),
        perimeter_variant_code=CODE_TERRITORIAL_BOUNDARIES,
    )


def _build_tites_res_entity_for_subject(
    res: RegionalEnergySystem,
    regional_district: RegionalDistrict,
    *,
    ues_id: int,
    decentralized_energy_units: list[EnergyUnit] | None = None,
) -> SummaryEntity:
    """РЭС под субъектом РФ в ветке ТИТЭС Востока: сначала энергорайоны ТИТЭС, затем ДЗ."""
    energy_units = _filter_energy_units_for_res(regional_district.energy_units, res.id)
    if not energy_units:
        energy_units = _filter_valid_items(res.energy_units)
    tites_children = _build_energy_unit_entities(
        energy_units,
        depth=3,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res.id,
        id_regional_district=regional_district.id,
        parameters=PARAMETERS_TITES_OES_SUMMARY,
    )
    dz_children: list[SummaryEntity] = []
    if decentralized_energy_units:
        existing_eu_ids = {c.id_energy_unit for c in tites_children if c.id_energy_unit is not None}
        dz_units = [
            eu
            for eu in _filter_valid_items(decentralized_energy_units)
            if getattr(eu, "id", None) not in existing_eu_ids
        ]
        if dz_units:
            dz_children = _build_energy_unit_entities(
                dz_units,
                depth=3,
                id_union_energy_system=ues_id,
                id_regional_energy_system=res.id,
                id_regional_district=regional_district.id,
                is_decentralized_zone_energy_unit=True,
                parameters=PARAMETERS_TITES_OES_SUMMARY,
            )
    return SummaryEntity(
        label=res.name,
        depth=2,
        parameters=PARAMETERS_TITES_OES_SUMMARY,
        demand_rows=dps.get_demand_rows(
            RegionalEnergySystemDemandParameter,
            "id_regional_energy_system",
            res.id,
        ),
        entity_kind="child",
        children=tites_children + dz_children,
        demand_model_name=RegionalEnergySystemDemandParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=res.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res.id,
        id_regional_district=regional_district.id,
    )


def _collect_tites_siberia_energy_unit_entities(
    ues: UnionEnergySystem,
) -> list[SummaryEntity]:
    """Энергорайоны ТИТЭС Сибири без строк субъекта РФ и РЭС."""
    out: list[SummaryEntity] = []
    for res in sorted(ues.regional_energy_systems, key=_sort_by_name):
        if not _is_valid_named_item(res):
            continue
        for regional_district in sorted(res.regional_districts, key=_sort_by_name):
            if not _is_valid_named_item(regional_district):
                continue
            energy_units = _filter_energy_units_for_res(
                regional_district.energy_units,
                res.id,
            )
            if not energy_units:
                energy_units = _filter_valid_items(res.energy_units)
            out.extend(
                _build_energy_unit_entities(
                    energy_units,
                    depth=1,
                    id_union_energy_system=ues.id,
                    id_regional_energy_system=res.id,
                    id_regional_district=regional_district.id,
                    parameters=PARAMETERS_TITES_OES_SUMMARY,
                )
            )
    return sorted(out, key=lambda e: ((e.label or "").casefold(), e.id_energy_unit or 0))


def _build_tites_subject_entities() -> list[SummaryEntity]:
    """ТИТЭС + ДЗ: Сибирь (ЭР) → Восток (субъект→РЭС→ЭР) → одиночные ЭР ДЗ."""
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

    siberia_children: list[SummaryEntity] = []
    east_by_rd: dict[int, list[tuple[RegionalDistrict, RegionalEnergySystem, int]]] = {}

    for ues in query.all():
        if not _is_valid_named_item(ues) or not _is_tites_branch(ues):
            continue
        if _is_tites_siberia_ues(ues):
            siberia_children.extend(_collect_tites_siberia_energy_unit_entities(ues))
            continue
        if not _is_tites_east_ues(ues):
            continue
        for res in sorted(ues.regional_energy_systems, key=_sort_by_name):
            if not _is_valid_named_item(res):
                continue
            for regional_district in sorted(res.regional_districts, key=_sort_by_name):
                if not _is_valid_named_item(regional_district):
                    continue
                east_by_rd.setdefault(regional_district.id, []).append(
                    (regional_district, res, ues.id)
                )

    dz_by_rd = _decentralized_energy_units_by_regional_district()
    east_rd_ids = set(east_by_rd.keys())

    east_subject_entities: list[SummaryEntity] = []
    for regional_district in sorted(
        (items[0][0] for items in east_by_rd.values()),
        key=_sort_by_name,
    ):
        items = east_by_rd[regional_district.id]
        dz_eus = dz_by_rd.get(regional_district.id, [])
        res_children = [
            _build_tites_res_entity_for_subject(
                res,
                rd,
                ues_id=ues_id,
                decentralized_energy_units=dz_eus if idx == 0 else None,
            )
            for idx, (rd, res, ues_id) in enumerate(
                sorted(items, key=lambda item: _sort_by_name(item[1]))
            )
        ]
        ues_ids = {ues_id for _, _, ues_id in items}
        subject_entity = SummaryEntity(
            label=regional_district.name,
            depth=1,
            parameters=PARAMETERS_TITES_OES_SUMMARY,
            demand_rows=dps.get_demand_rows(
                RegionalDistrictDemandParameter,
                "id_regional_district",
                regional_district.id,
            ),
            entity_kind="child",
            children=res_children,
            demand_model_name=RegionalDistrictDemandParameter.__name__,
            parent_fk_column="id_regional_district",
            parent_id=regional_district.id,
            id_regional_district=regional_district.id,
            id_union_energy_system=(
                next(iter(ues_ids)) if len(ues_ids) == 1 else None
            ),
        )
        if _is_chukotka_regional_district(regional_district):
            territorial_entity = replace(
                _build_chukotka_territorial_boundaries_subject_entity(subject_entity),
                depth=1,
            )
            subject_entity = replace(
                subject_entity,
                children=[territorial_entity, *res_children],
            )
        east_subject_entities.append(subject_entity)

    solo_dz_children: list[SummaryEntity] = []
    for rd_id in sorted(dz_by_rd.keys()):
        if rd_id in east_rd_ids:
            continue
        solo_dz_children.extend(
            _build_energy_unit_entities(
                dz_by_rd[rd_id],
                depth=1,
                id_regional_district=rd_id,
                is_decentralized_zone_energy_unit=True,
                parameters=PARAMETERS_TITES_OES_SUMMARY,
            )
        )
    solo_dz_children.sort(key=lambda e: ((e.label or "").casefold(), e.id_energy_unit or 0))

    return siberia_children + east_subject_entities + solo_dz_children


def _build_tites_entity() -> SummaryEntity | None:
    """Корень ТИТЭС + ДЗ — только уровень агрегации, без ввода показателей."""
    children = _build_tites_subject_entities()
    if not children:
        return None

    return SummaryEntity(
        label=_TITES_AND_DZ_AGGREGATE_LABEL,
        depth=0,
        parameters=tuple(),
        demand_rows=[],
        entity_kind="aggregation_level",
        children=children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
    )


def _build_regional_district_entity(
    regional_district: RegionalDistrict,
    *,
    depth: int,
    energy_units: list[EnergyUnit] | None = None,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_EES_AND_ES,
    ues_id: int | None = None,
    res_id: int | None = None,
    id_federal_district: int | None = None,
    id_energy_zone: int | None = None,
) -> SummaryEntity:
    return SummaryEntity(
        label=regional_district.name,
        depth=depth,
        parameters=parameters,
        demand_rows=dps.get_demand_rows(
            RegionalDistrictDemandParameter,
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
            id_energy_zone=id_energy_zone,
        ),
        demand_model_name=RegionalDistrictDemandParameter.__name__,
        parent_fk_column="id_regional_district",
        parent_id=regional_district.id,
        id_union_energy_system=ues_id,
        id_regional_energy_system=res_id,
        id_regional_district=regional_district.id,
        id_federal_district=id_federal_district,
        id_energy_zone=id_energy_zone,
    )


def _build_energy_unit_entities(
    energy_units: list[EnergyUnit],
    *,
    depth: int,
    id_union_energy_system: int | None = None,
    id_regional_energy_system: int | None = None,
    id_regional_district: int | None = None,
    id_energy_zone: int | None = None,
    is_decentralized_zone_energy_unit: bool = False,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_UNIT_OES_SUMMARY,
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
                parameters=parameters,
                demand_rows=dps.get_demand_rows(
                    EnergyUnitDemandParameter,
                    "id_energy_unit",
                    energy_unit.id,
                ),
                entity_kind="child",
                demand_model_name=EnergyUnitDemandParameter.__name__,
                parent_fk_column="id_energy_unit",
                parent_id=energy_unit.id,
                id_union_energy_system=ues,
                id_regional_energy_system=res_id,
                id_regional_district=rd_id,
                id_energy_unit=energy_unit.id,
                id_energy_zone=id_energy_zone,
                is_decentralized_zone_energy_unit=is_decentralized_zone_energy_unit,
            )
        )
    return out


def _build_federal_district_entities() -> list[SummaryEntity]:
    query = FederalDistrict.query.options(
        selectinload(FederalDistrict.regional_districts).selectinload(
            RegionalDistrict.regional_energy_systems
        ),
        selectinload(FederalDistrict.regional_districts).selectinload(
            RegionalDistrict.energy_units
        ),
    )
    query = dps.filter_parents_by_version(query, FederalDistrict)
    query = query.order_by(
        FederalDistrict.display_order.asc().nullslast(),
        FederalDistrict.name.asc(),
        FederalDistrict.id.asc(),
    )

    entities: list[SummaryEntity] = []
    south_attach_fd, south_ues_id = _south_federal_district_for_nt_attachment()
    nt_fd_attach = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    south_res_ids = _south_ues_res_ids()
    for federal_district in query.all():
        if not _is_valid_named_item(federal_district):
            continue
        if _federal_district_excluded_from_summary(federal_district):
            continue

        child_entities: list[SummaryEntity] = []
        last_south_child_idx = -1
        for regional_district in sorted(
            federal_district.regional_districts, key=_sort_by_name
        ):
            if not _is_valid_named_item(regional_district):
                continue
            child_entities.append(
                SummaryEntity(
                    label=regional_district.name,
                    depth=1,
                    parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
                    demand_rows=dps.get_demand_rows(
                        RegionalDistrictDemandParameter,
                        "id_regional_district",
                        regional_district.id,
                    ),
                    entity_kind="child",
                    demand_model_name=RegionalDistrictDemandParameter.__name__,
                    parent_fk_column="id_regional_district",
                    parent_id=regional_district.id,
                    id_federal_district=federal_district.id,
                    id_regional_district=regional_district.id,
                )
            )
            if _regional_district_linked_to_south_ues(regional_district, south_res_ids):
                last_south_child_idx = len(child_entities) - 1
        if (
            south_attach_fd is not None
            and south_ues_id is not None
            and federal_district.id == south_attach_fd.id
        ):
            nt_under = _build_fo_nt_under_south_entity(
                south_attach_fd,
                south_ues_id,
                nt_fd_attach,
                res_parameters=PARAMETERS_FEDERAL_DISTRICT,
                subject_parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
            )
            if nt_under is not None:
                child_entities = _insert_child_after_south_ues_block(
                    child_entities,
                    nt_under,
                    last_south_child_index=last_south_child_idx,
                )
        entities.append(
            SummaryEntity(
                label=federal_district.name,
                depth=0,
                parameters=PARAMETERS_FEDERAL_DISTRICT,
                demand_rows=dps.get_demand_rows(
                    FederalDistrictDemandParameter,
                    "id_federal_district",
                    federal_district.id,
                ),
                entity_kind="group",
                children=child_entities,
                demand_model_name=FederalDistrictDemandParameter.__name__,
                parent_fk_column="id_federal_district",
                parent_id=federal_district.id,
                id_federal_district=federal_district.id,
            )
        )
    return entities


def _build_federal_district_entities_by_res() -> list[SummaryEntity]:
    """Дерево ФО → РЭС; при >1 субъекте РЭС в ФО — строки субъектов (без энергоузлов)."""
    query = FederalDistrict.query.options(
        selectinload(FederalDistrict.regional_districts).selectinload(
            RegionalDistrict.regional_energy_systems
        ),
    )
    query = dps.filter_parents_by_version(query, FederalDistrict)
    query = query.order_by(
        FederalDistrict.display_order.asc().nullslast(),
        FederalDistrict.name.asc(),
        FederalDistrict.id.asc(),
    )

    entities: list[SummaryEntity] = []
    south_attach_fd, south_ues_id = _south_federal_district_for_nt_attachment()
    nt_fd_attach = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    south_res_ids = _south_ues_res_ids()
    for federal_district in query.all():
        if not _is_valid_named_item(federal_district):
            continue
        if _federal_district_excluded_from_summary(federal_district):
            continue

        res_by_id: dict[int, RegionalEnergySystem] = {}
        for regional_district in sorted(
            federal_district.regional_districts,
            key=_sort_by_name,
        ):
            if not _is_valid_named_item(regional_district):
                continue
            for res in regional_district.regional_energy_systems:
                if _is_valid_named_item(res) and res.id not in res_by_id:
                    res_by_id[res.id] = res

        child_entities: list[SummaryEntity] = []
        last_south_res_idx = -1
        for res in sorted(res_by_id.values(), key=_sort_by_name):
            rd_in_fd = [
                rd
                for rd in sorted(res.regional_districts, key=_sort_by_name)
                if rd.id_federal_district == federal_district.id and _is_valid_named_item(rd)
            ]
            rd_ids_in_fd = frozenset(rd.id for rd in rd_in_fd)
            if not rd_ids_in_fd:
                continue
            subject_children: list[SummaryEntity] = []
            if len(rd_in_fd) > 2:
                ues_id = getattr(res, "id_union_energy_system", None)
                subject_children = [
                    SummaryEntity(
                        label=rd.name,
                        depth=2,
                        parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
                        demand_rows=dps.get_demand_rows(
                            RegionalDistrictDemandParameter,
                            "id_regional_district",
                            rd.id,
                        ),
                        entity_kind="child",
                        demand_model_name=RegionalDistrictDemandParameter.__name__,
                        parent_fk_column="id_regional_district",
                        parent_id=rd.id,
                        id_federal_district=federal_district.id,
                        id_regional_district=rd.id,
                        id_regional_energy_system=res.id,
                        id_union_energy_system=ues_id,
                    )
                    for rd in rd_in_fd
                ]
            child_entities.append(
                SummaryEntity(
                    label=res.name,
                    depth=1,
                    parameters=PARAMETERS_RES_FO_COEFF,
                    demand_rows=dps.get_demand_rows(
                        RegionalEnergySystemDemandParameter,
                        "id_regional_energy_system",
                        res.id,
                    ),
                    entity_kind="child",
                    children=subject_children,
                    demand_model_name=RegionalEnergySystemDemandParameter.__name__,
                    parent_fk_column="id_regional_energy_system",
                    parent_id=res.id,
                    id_federal_district=federal_district.id,
                    id_regional_energy_system=res.id,
                    id_union_energy_system=getattr(res, "id_union_energy_system", None),
                    fo_res_linked_regional_district_ids=rd_ids_in_fd,
                )
            )
            if int(res.id) in south_res_ids:
                last_south_res_idx = len(child_entities) - 1

        if (
            south_attach_fd is not None
            and south_ues_id is not None
            and federal_district.id == south_attach_fd.id
        ):
            nt_under = _build_fo_nt_under_south_entity(
                south_attach_fd,
                south_ues_id,
                nt_fd_attach,
                res_parameters=PARAMETERS_RES_FO_COEFF,
                subject_parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
            )
            if nt_under is not None:
                child_entities = _insert_child_after_south_ues_block(
                    child_entities,
                    nt_under,
                    last_south_child_index=last_south_res_idx,
                )

        entities.append(
            SummaryEntity(
                label=federal_district.name,
                depth=0,
                parameters=PARAMETERS_FEDERAL_DISTRICT,
                demand_rows=dps.get_demand_rows(
                    FederalDistrictDemandParameter,
                    "id_federal_district",
                    federal_district.id,
                ),
                entity_kind="group",
                children=child_entities,
                demand_model_name=FederalDistrictDemandParameter.__name__,
                parent_fk_column="id_federal_district",
                parent_id=federal_district.id,
                id_federal_district=federal_district.id,
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


def _ues_summary_sort_key(ues: UnionEnergySystem) -> tuple[int, str, int]:
    """Порядок ОЭС на сводке — как в справочнике (display_order, имя, id)."""
    big = 10**9
    return (
        int(ues.display_order) if ues.display_order is not None else big,
        (getattr(ues, "name", None) or "").casefold(),
        int(ues.id),
    )


def _oes_group_sort_keys_by_ues_id(entities: list[SummaryEntity]) -> dict[int, tuple[int, str, int]]:
    ues_ids = {
        int(e.id_union_energy_system)
        for e in entities
        if e.entity_kind == "group" and e.id_union_energy_system is not None
    }
    if not ues_ids:
        return {}
    q = UnionEnergySystem.query.filter(UnionEnergySystem.id.in_(ues_ids))
    q = dps.filter_parents_by_version(q, UnionEnergySystem)
    return {int(u.id): _ues_summary_sort_key(u) for u in q.all()}


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
        and e.demand_model_name == UnionEnergySystemDemandParameter.__name__
        and e.id_union_energy_system is not None
    )


def _oes_is_regional_energy_system_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalEnergySystemDemandParameter.__name__
        and e.id_regional_energy_system is not None
    )


def _oes_is_regional_district_node(e: SummaryEntity) -> bool:
    return (
        e.demand_model_name == RegionalDistrictDemandParameter.__name__
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
    # «ЕЭС России без НТ», «ТИТЭС», «Децентрализованная зона»: агрегат + дочерняя ветка
    if e.entity_kind in ("group-root", "aggregation_level"):
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

    На сводке по ФО под округами показываются РЭС.
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


def _prune_one_fo(e: SummaryEntity, f_fd: frozenset[int], f_res: frozenset[int]) -> SummaryEntity | None:
    filters_on = bool(f_fd or f_res)
    if e.entity_kind == "centralized_zone":
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
    if e.entity_kind == "ees_russia":
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
    if e.entity_kind == "ees_russia":
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


def get_power_demand_oes_filter_cascade_data() -> dict[str, Any]:
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


def get_power_demand_fo_filter_cascade_data() -> dict[str, Any]:
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


def get_power_demand_ez_filter_cascade_data() -> dict[str, Any]:
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
