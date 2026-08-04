from __future__ import annotations

import copy
import math
import re
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
    format_decimal_for_display,
    format_decimal_trim_for_display,
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
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CENTRALIZED_ZONE_AGGREGATE_NAME,
    CENTRALIZED_ZONE_AGGREGATE_NAME_CF,
    ENTITY_KIND_CENTRALIZED_ZONE,
    ENTITY_KIND_EES_RUSSIA,
    ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    ENTITY_KIND_RUSSIA_FEDERATION,
    EES_RUSSIA_AGGREGATE_NAME,
    EES_UNIFIED_REF_NAME,
    RUSSIA_FEDERATION_AGGREGATE_NAME,
    legacy_nt_group_for_perimeter_code,
    perimeter_variant_codes_in_legacy_nt_group,
)
from app.common.perimeter_variant.registry import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    entity_perimeter_bindings,
    is_kaliningrad_sync_area_entity_name,
    is_o1_perimeter_variant_code,
    kaliningrad_sync_area_year_bounds,
    perimeter_entity_context_for_model,
    perimeter_variant_display_label_for_entity,
    perimeter_variant_options_for_entity,
    perimeter_variant_year_bounds_for_code,
    ordered_tree_variants_for_display,
    perimeter_variant_codes_for_entity,
    resolve_catalog_o1_perimeter_variant_code,
    resolve_entity_perimeter_binding,
    resolve_entity_perimeter_variants,
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
_TITES_COMPACT_AGGREGATE_LABEL = "ТИТЭС"
_TITES_SIBERIA_UES_NAME_CF = "титэссибири"
_TITES_EAST_UES_NAME_CF = "титэсвостока"
# Западный/Центральный энергорайоны ЭС Саха (Якутия): до 2018 в ТИТЭС, с 2019 — в ОЭС Востока.
_SAKHA_YAKUTIA_RES_NAME_MARKERS_CF = ("саха", "якутия")
_TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_ORDERED: tuple[str, ...] = (
    "западный энергорайон",
    "центральный энергорайон",
)
_TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_CF = frozenset(
    _TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_ORDERED
)
_TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR = 2018
_SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND = "sakha_tites_through_year"
# В «Сводной таблице» под ТИТЭС: вместо РЭС «ЭС г. Норильска…» — энергорайон Таймыр/Туруханск/Норильск.
_NORILSK_RES_LABEL = "ЭС г. Норильска Красноярского края"
_NORILSK_RES_LABEL_CF = _NORILSK_RES_LABEL.casefold().replace(" ", "")
_TAIMYR_NORILSK_EU_LABEL = (
    "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
    "и городской округ г. Норильск Красноярского края"
)
_TAIMYR_NORILSK_EU_LABEL_CF = _TAIMYR_NORILSK_EU_LABEL.casefold().replace(" ", "")
# Энергорайоны, входящие в формулу «Расчетный максимум …» (ЭЭС России) поверх ветки ТИТЭС.
_EES_AGGREGATE_TITES_EU_NAME_SPECS: tuple[tuple[str, ...], ...] = (
    ("таймыр", "норильск"),
    ("чаун", "билибин"),
    ("анад", "ский"),
    ("центральный", "магадан"),
    ("центральный", "камчат"),
    ("центральный", "сахалин"),
)
# Дальневосточный ФО: те же энергорайоны формулы ЭЭС, кроме Норильска (Сибирь).
_FAR_EAST_FD_FORMULA_EU_NAME_SPECS: tuple[tuple[str, ...], ...] = (
    ("чаун", "билибин"),
    ("анад", "ский"),
    ("центральный", "магадан"),
    ("центральный", "камчат"),
    ("центральный", "сахалин"),
)
_FAR_EAST_FEDERAL_DISTRICT_NAME_MARKER_CF = "дальневосточн"
_CHUKOTKA_RD_LABEL = "Чукотский АО"
_CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL = "Чукотский АО (в территориальных границах)"
_CHUKOTKA_RES_LABEL = "ЭС Чукотского АО"
_CHUKOTKA_CHERSKY_TRANSFER_MW = 3.0

# Не показывать в сводке по ФО (экран и Excel).
_FEDERAL_DISTRICT_SUMMARY_EXCLUDED_NAMES_CF = frozenset({"новые территории"})
_NEW_TERRITORIES_NAME = "Новые территории"
_SOUTH_UES_LABELS_CF = frozenset({"оэс юга"})
_FIRST_SYNC_AREA_BASE_LABEL_CF = "первая синхронная зона"
_SECOND_SYNC_AREA_BASE_LABEL_CF = "вторая синхронная зона"
_KALININGRAD_SYNC_AREA_LABEL_TOKEN_CF = "калининград"
_KALININGRAD_ES_NAME_CF = "эс калининградской области"
_UES_EAST_NAME_CF = "оэс востока"
# Показатель строки «Вторая синхронная зона» → показатель «ОЭС Востока».
_SECOND_SA_FROM_UES_EAST_SOURCE_PARAM: dict[str, str] = {
    "max_power": "max_power",
    "calculated_max_power_mw": "calculated_max_power_mw",
    "peak_datetime": "peak_datetime",
    "avg_temp": "avg_temp",
    "combined_on_ees": "combined_on_ees",
    "calculated_max_sa_mw": "calculated_combined_on_ees_mw",
    "peak_max_power_usage_hours": "peak_max_power_usage_hours",
    "peak_combined_on_ees_usage_hours": "peak_combined_on_ees_usage_hours",
}
_SECOND_SA_FROM_UES_EAST_FORMULA_KEY: dict[str, str] = {
    "max_power": "sa_second_max_power_from_ues_east",
    "calculated_max_power_mw": "sa_second_calc_max_power_mw",
    "peak_datetime": "sa_second_peak_datetime_from_ues_east",
    "avg_temp": "sa_second_avg_temp_from_ues_east",
    "combined_on_ees": "sa_second_combined_on_ees_from_ues_east",
    "calculated_max_sa_mw": "sa_second_calc_max_sa_mw",
    "peak_max_power_usage_hours": "sa_second_chi_from_ues_east",
    "peak_combined_on_ees_usage_hours": "sa_second_chi_combined_from_ues_east",
}
# Показатель строки «Синхронная зона Калининградской области» → показатель «ЭС Калининградской области».
_KALININGRAD_SA_FROM_ES_SOURCE_PARAM: dict[str, str] = {
    "max_power": "max_power",
    "calculated_max_power_mw": "max_power",
    "peak_datetime": "peak_datetime",
    "avg_temp": "avg_temp",
    "combined_on_ees": "combined_on_ees",
    "calculated_max_sa_mw": "combined_on_ees",
    "peak_max_power_usage_hours": "peak_max_power_usage_hours",
    "peak_combined_on_ees_usage_hours": "peak_combined_on_ees_usage_hours",
}
_KALININGRAD_SA_FROM_ES_FORMULA_KEY: dict[str, str] = {
    "max_power": "sa_kaliningrad_max_power_from_es",
    "calculated_max_power_mw": "sa_kaliningrad_calc_max_power_mw",
    "peak_datetime": "sa_kaliningrad_peak_datetime_from_es",
    "avg_temp": "sa_kaliningrad_avg_temp_from_es",
    "combined_on_ees": "sa_kaliningrad_combined_on_ees_from_es",
    "calculated_max_sa_mw": "sa_kaliningrad_calc_max_sa_mw",
    "peak_max_power_usage_hours": "sa_kaliningrad_chi_from_es",
    "peak_combined_on_ees_usage_hours": "sa_kaliningrad_chi_combined_from_es",
}


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
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_ees_via_ez_mw",
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
        "calculated_max_sa_mw",
        "calculated_combined_on_cz_mw",
        "calculated_combined_on_ees_mw",
        "calculated_max_ees_russia_mw",
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_ees_via_ez_mw",
        "calculated_max_power_consumption_mw",
    }
)

BASE_PARAMETERS: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# Блок «ТИТЭС и децентрализованная зона» на сводке по ОЭС — только базовые показатели.
PARAMETERS_TITES_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# На сводках /power_demand/summary/{oes,federal_districts,energy_zones}/ исторический столбец только у базовых показателей.
SUMMARY_HIST_PARAMETER_KEYS: frozenset[str] = frozenset(pk for pk, _ in BASE_PARAMETERS)
OES_SUMMARY_HIST_PARAMETER_KEYS = SUMMARY_HIST_PARAMETER_KEYS  # обратная совместимость
# Строка объединённой энергосистемы (ОЭС) в сводке «по энергосистемам».
PARAMETERS_UES_OES: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_power_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт"),
    (
        "calculated_combined_on_ees_mw",
        "Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт",
    ),
)
# Тип энергосистемы ОЭС для расчёта «Расчетный максимум потребления мощности ЕЭС (через ОЭС)».
EES_RUSSIA_ENERGY_SYSTEM_TYPE_NAME = "ЕЭС России"

# Агрегаты «ЦЗ России с/без НТ» на сводке по ОЭС (без «Среднесуточная ТНВ»).
PARAMETERS_CZ_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    (
        "calculated_max_power_mw",
        "Расчетное максимальное потребление мощности, МВт",
    ),
    ("peak_datetime", "Дата и время, мск"),
)
# ЦЗ России на сводках ФО / ЭЗ (как ОЭС + среднесуточная ТНВ).
PARAMETERS_CZ_FO_SUMMARY: tuple[tuple[str, str], ...] = (
    *PARAMETERS_CZ_OES_SUMMARY,
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# Агрегат «Россия» на сводке ФО (без расчётного максимума ЦЗ).
PARAMETERS_RUSSIA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
)
# Агрегаты «ЭЭС России с/без НТ» на сводке по ОЭС (без «Среднесуточная ТНВ»).
PARAMETERS_EES_AGGREGATE_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    (
        "calculated_max_power_consumption_mw",
        "Расчетное максимальное потребление мощности, МВт",
    ),
    ("peak_datetime", "Дата и время, мск"),
)
# Агрегаты «ЕЭС России с/без НТ» на сводке по ОЭС.
PARAMETERS_EES_RUSSIA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_ees_russia_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("calculated_max_ees_via_oes_mw", "Расчетное максимальное потребление мощности (через ОЭС), МВт"),
    ("calculated_max_ees_via_es_mw", "Расчетное максимальное потребление мощности (через РЭС), МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# То же на сводке по энергозонам (+ «через ЭЗ»).
PARAMETERS_EES_RUSSIA_EZ_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_ees_russia_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("calculated_max_ees_via_oes_mw", "Расчетное максимальное потребление мощности (через ОЭС), МВт"),
    ("calculated_max_ees_via_es_mw", "Расчетное максимальное потребление мощности (через РЭС), МВт"),
    ("calculated_max_ees_via_ez_mw", "Расчетное максимальное потребление мощности (через ЭЗ), МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
_EES_UNIFIED_DEMAND_MODEL_NAME = EnergySystemTypeDemandParameter.__name__
_EES_AGGREGATE_DEMAND_MODEL_NAME = EesRussiaDemandParameter.__name__
_EES_RUSSIA_AGGREGATE_DM_NAME = _EES_UNIFIED_DEMAND_MODEL_NAME
PARAMETERS_WITH_OES_AND_EES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_oes", "Совмещенное потребление мощности на час прохождения максимума ОЭС, МВт"),
    ("combined_on_ees", "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт"),
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
        "Совмещенное потребление мощности на час прохождения максимума ЭС, МВт",
    ),
    (
        "combined_on_oes",
        "Совмещенное потребление мощности на час прохождения максимума ОЭС, МВт",
    ),
    (
        "combined_on_ees",
        "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт",
    ),
)
# Субъекты ФО «Новые территории» на сводке по ОЭС: без «совмещённого на ЭС».
PARAMETERS_NT_SUBJECT_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    (
        "combined_on_oes",
        "Совмещенное потребление мощности на час прохождения максимума ОЭС, МВт",
    ),
    (
        "combined_on_ees",
        "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт",
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
# Федеральный округ на сводке «Максимумы по ФО» (как ОЭС на /summary/oes/ + показатели ФО).
PARAMETERS_FEDERAL_DISTRICT_MAX: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_power_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_cz", "Совмещенное потребление мощности на час максимума ЦЗ России, МВт"),
    (
        "calculated_combined_on_cz_mw",
        "Расчетное совмещенное потребление мощности на час максимума ЦЗ России, МВт",
    ),
)
# Субъект РФ на сводке по ФО: без ОЭС / ЕЭС / ЭС / ценовой зоны (только базовые + «на ФО»)
PARAMETERS_SUBJECT_FD_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенное потребление мощности на час прохождения максимума ФО, МВт"),
)
# Энергорайон на сводке по ФО (в модели ЭР нет combined_on_fo — совмещённый на РЭС).
PARAMETERS_ENERGY_UNIT_FD_SUMMARY: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_es", "Совмещенный максимум потребления мощности ЭР на РЭС, МВт"),
)
# Региональная энергосистема на сводке по энергозонам: «на энергозону» (ОЭС/ЕЭС — на странице по ОЭС)
PARAMETERS_RES: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_ez", "Совмещенное потребление мощности на час прохождения максимума ЭЗ, МВт"),
)
# РЭС на сводке «коэффициенты по ФО» (дерево ФО→РЭС): на ФО и на ЦЗ России, без «на энергозону»
PARAMETERS_RES_FO_COEFF: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенное потребление мощности на час прохождения максимума ФО, МВт"),
    ("combined_on_cz", "Совмещенное потребление мощности на час прохождения максимума ЦЗ России, МВт"),
)
# РЭС на сводке «Максимумы по ФО» (дерево ФО→РЭС): + совмещённый на ЕЭС.
PARAMETERS_RES_FO_MAX: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_fo", "Совмещенное потребление мощности на час максимума ФО, МВт"),
    (
        "combined_on_cz",
        "Совмещенное потребление мощности на час максимума ЦЗ России, МВт",
    ),
)
# Энергозона (в модели только базовые показатели + совмещённый на ЕЭС)
PARAMETERS_ENERGY_ZONE: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенный максимум потребления мощности ЕЭС, МВт"),
)
# Энергозона на сводке «Максимумы по энергозонам» (как ОЭС на /summary/oes/).
PARAMETERS_ENERGY_ZONE_MAX: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_power_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
    ("combined_on_ees", "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт"),
    (
        "calculated_combined_on_ees_mw",
        "Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт",
    ),
)
# РЭС на сводке «Максимумы по энергозонам»: «на энергозону» и «на ЕЭС».
PARAMETERS_RES_EZ_MAX: tuple[tuple[str, str], ...] = (
    *BASE_PARAMETERS,
    ("combined_on_ees", "Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт"),
    ("combined_on_ez", "Совмещенное потребление мощности на час прохождения максимума ЭЗ, МВт"),
)
# Синхронная зона на сводной таблице (ОЭС / ФО / энергозоны): без совмещённого на ЕЭС и его расчёта/проверки.
PARAMETERS_SYNCHRONOUS_AREA: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_power_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
    ("avg_temp", "Среднесуточная ТНВ, °C"),
)
# «Первая синхронная зона с/без НТ» на сводке (без «Среднесуточная ТНВ»).
PARAMETERS_FIRST_SYNCHRONOUS_AREA_OES_SUMMARY: tuple[tuple[str, str], ...] = (
    ("max_power", "Максимальное потребление мощности, МВт"),
    ("calculated_max_power_mw", "Расчетное максимальное потребление мощности, МВт"),
    ("peak_datetime", "Дата и время, мск"),
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
    # Строка уже развёрнута по варианту периметра (включая code=None → «не указано»).
    summary_perimeter_variant_row: bool = False
    # Сводка ФО: «ЦЗ России O-1» по данным with_nt / without_nt (не o1_*).
    centralized_zone_o1_display_row: bool = False
    # Субъекты этого ФО, с которыми связана РЭС (для фильтров ds_rd на сводке ФО→РЭС).
    fo_res_linked_regional_district_ids: frozenset[int] | None = None
    # Энергорайон децентрализованной зоны (РЭС «не указано» в справочнике).
    is_decentralized_zone_energy_unit: bool = False
    # Копия Западный/Центральный Саха (Якутия) под ТИТЭС (годы ≤ 2018), без строки РЭС.
    sakha_yakutia_tites_through_year_row: bool = False
    # РЭС на сводке ЭЗ: True, если все субъекты РЭС входят в эту энергозону.
    # False — частичное пересечение: полный показатель РЭС в агрегат зоны не берём.
    ez_res_fully_in_zone: bool | None = None


def _synchronous_area_display_label(sa: SynchronousArea) -> str:
    return (getattr(sa, "name", None) or "").strip()


def _is_first_synchronous_area_name(name: str | None) -> bool:
    return (name or "").strip().casefold().startswith(_FIRST_SYNC_AREA_BASE_LABEL_CF)


def _is_second_synchronous_area_name(name: str | None) -> bool:
    return (name or "").strip().casefold().startswith(_SECOND_SYNC_AREA_BASE_LABEL_CF)


def _is_kaliningrad_synchronous_area_name(name: str | None) -> bool:
    return is_kaliningrad_sync_area_entity_name(name)


def _is_kaliningrad_sync_area_summary_row(row: dict[str, Any]) -> bool:
    if row.get("demand_model_name") != SynchronousAreaDemandParameter.__name__:
        return False
    label = str(row.get("entity_label") or "")
    return is_kaliningrad_sync_area_entity_name(label)


def _is_first_synchronous_area_summary_row(row: dict[str, Any]) -> bool:
    """Строка блока «Первая синхронная зона …» на сводке (с/без НТ и т.п.)."""
    if row.get("demand_model_name") != SynchronousAreaDemandParameter.__name__:
        return False
    return _is_first_synchronous_area_name(str(row.get("entity_label") or ""))


def _kaliningrad_sync_area_entity_with_stored_variant(
    entity: SummaryEntity,
) -> SummaryEntity:
    """Одна строка СЗ Калининграда с кодом варианта, сохранённым в БД (если есть)."""
    try:
        model_cls = dps._summary_demand_model_class(str(entity.demand_model_name or ""))
    except ValueError:
        return entity
    if entity.parent_fk_column is None or entity.parent_id is None:
        return entity
    stored = dps.peek_stored_perimeter_variant_code_for_parent(
        model_cls,
        entity.parent_fk_column,
        entity.parent_id,
    )
    if not stored:
        return entity
    if str(entity.perimeter_variant_code or "") == str(stored):
        return entity
    demand_rows = dps.get_demand_rows(
        model_cls,
        entity.parent_fk_column,
        entity.parent_id,
        perimeter_variant_code=stored,
    )
    return replace(
        entity,
        perimeter_variant_code=stored,
        demand_rows=demand_rows,
    )


def _perimeter_variant_code_has_kaliningrad(code: str | None) -> bool:
    """Вариант первой СЗ с добавкой ``_kaliningrad`` в коде периметра."""
    return "_kaliningrad" in str(code or "")


def _resolve_kaliningrad_synchronous_area_id() -> int | None:
    query = SynchronousArea.query
    query = dps.filter_parents_by_version(query, SynchronousArea)
    for sa in query.all():
        if not _is_valid_named_item(sa):
            continue
        if _is_kaliningrad_synchronous_area_name(sa.name):
            return int(sa.id)
    return None


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
            out[j] = _summary_row_year_float(r, j)
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


def _demand_rows_by_stored_perimeter_variant(
    model: Any,
    parent_fk_column: str | None,
    parent_id: int | None,
    *,
    binding: Any = None,
) -> list[tuple[str | None, list[Any]]]:
    """Группы строк параметров по фактически сохраненному варианту периметра."""
    if parent_fk_column is not None and parent_id is None:
        return []
    q = model.query
    q = dps.filter_demand_by_version(q, model)
    if parent_fk_column is not None:
        q = q.filter(getattr(model, parent_fk_column) == parent_id)
    rows = q.order_by(
        model.is_historical_maximum.desc(),
        model.year_number.asc().nullsfirst(),
    ).all()
    if not rows:
        return []

    grouped: dict[str | None, list[Any]] = {}
    for row in rows:
        code = (
            getattr(row, "perimeter_variant_code", None)
            if model_supports_perimeter_variant(model)
            else None
        )
        grouped.setdefault(code, []).append(row)

    catalog_order = [
        str(v.code)
        for v in getattr(binding, "variants", ())
        if getattr(v, "code", None)
    ]
    order_index = {code: idx for idx, code in enumerate(catalog_order)}

    def _key(item: tuple[str | None, list[Any]]) -> tuple[int, int, str]:
        code = item[0]
        if code in order_index:
            return (0, order_index[str(code)], str(code))
        if code is None:
            return (1, 0, "")
        return (2, 0, str(code))

    out: list[tuple[str | None, list[Any]]] = []
    for code, group_rows in sorted(grouped.items(), key=_key):
        out.append((code, group_rows))
    return out


def _territorial_children_base_variant_code(binding: Any) -> str | None:
    """Код варианта периметра, к которому привязано поддерево РЭС/субъектов (базовый «без НТ»)."""
    display_codes = _oes_perimeter_variant_codes_for_summary(binding)
    if CODE_WITHOUT_NT in display_codes:
        return CODE_WITHOUT_NT
    without_nt_codes = [
        str(v.code)
        for v in getattr(binding, "variants", ())
        if legacy_nt_group_for_perimeter_code(getattr(v, "code", None)) == CODE_WITHOUT_NT
    ]
    for preferred in (
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT,
    ):
        if preferred in without_nt_codes:
            return preferred
    for code in without_nt_codes:
        if not _oes_summary_excludes_perimeter_variant_code(code):
            return code
    return without_nt_codes[0] if without_nt_codes else None


def _oes_summary_excludes_perimeter_variant_code(code: str | None) -> bool:
    """Варианты с зарядом ГАЭС не отображаются в сводках максимумов."""
    from app.common.perimeter_variant.registry import (
        summary_excludes_gaes_perimeter_variant_code,
    )

    return summary_excludes_gaes_perimeter_variant_code(code)


def _oes_perimeter_variant_codes_for_summary(binding: Any) -> tuple[str | None, ...]:
    """Коды вариантов периметра для сводки ОЭС: как в /perimeter_variants/, без «с зарядом ГАЭС»."""
    if binding is None or not getattr(binding, "variants", ()):
        return ()
    codes = tuple(
        getattr(v, "code", None)
        for v in binding.variants
        if not _oes_summary_excludes_perimeter_variant_code(getattr(v, "code", None))
    )
    if codes:
        return codes
    return tuple(
        v.code
        for v in ordered_tree_variants_for_display(binding)
        if not _oes_summary_excludes_perimeter_variant_code(v.code)
    )


def _pd_ensure_gaes_suffix_in_perimeter_variant_label(
    label: str,
    code: str | None,
) -> str:
    """Добавить «с/без заряда ГАЭС» по коду, если в справочнике суффикс без ГАЭС."""
    s = str(label or "").strip()
    code_s = str(code or "").strip()
    if not s or not code_s:
        return s
    gaes_suffix = _pd_gaes_label_suffix_for_variant_code(code_s)
    if not gaes_suffix:
        return s
    if "гаэс" in s.casefold():
        return s
    return f"{s}{gaes_suffix}".strip()


def _oes_perimeter_variant_russian_label(
    code: str,
    *,
    binding: Any,
    entity_kind: str | None,
    entity_name: str | None,
    strip_gaes_suffix: bool = True,
) -> str:
    """Подпись варианта для select на /summary/oes/ (опционально без «с/без заряда ГАЭС»)."""
    if binding is not None:
        for vdef in getattr(binding, "variants", ()) or ():
            if getattr(vdef, "code", None) == code:
                label = str(getattr(vdef, "label_suffix", "") or code)
                if strip_gaes_suffix:
                    label = _pd_strip_gaes_text_from_label_fragment(label)
                else:
                    label = _pd_ensure_gaes_suffix_in_perimeter_variant_label(label, code)
                return label
    label = perimeter_variant_display_label_for_entity(code, entity_kind, entity_name)
    label = label if label else str(code)
    if strip_gaes_suffix:
        label = _pd_strip_gaes_text_from_label_fragment(label)
    else:
        label = _pd_ensure_gaes_suffix_in_perimeter_variant_label(label, code)
    return label


def _perimeter_variant_options_for_summary(
    entity_kind: str | None,
    entity_name: str | None,
) -> list[dict[str, str]]:
    return [
        opt
        for opt in perimeter_variant_options_for_entity(entity_kind, entity_name)
        if not _oes_summary_excludes_perimeter_variant_code(opt.get("code"))
    ]


def _perimeter_variant_options_for_oes_summary(
    entity_kind: str | None,
    entity_name: str | None,
    *,
    strip_gaes_suffix: bool = True,
) -> list[dict[str, str]]:
    """Опции select в столбце «Варианты периметра» на /summary/oes/ (русский текст)."""
    binding = resolve_entity_perimeter_binding(entity_kind, entity_name)
    codes = _oes_perimeter_variant_codes_for_summary(binding)
    if not codes:
        binding = resolve_entity_perimeter_binding(entity_kind, entity_name)
        if binding is not None and getattr(binding, "variants", ()):
            codes = tuple(
                str(getattr(v, "code", "") or "")
                for v in binding.variants
                if getattr(v, "code", None)
                and not _oes_summary_excludes_perimeter_variant_code(getattr(v, "code", None))
            )
        if not codes:
            return [
                {
                    "code": str(o["code"]),
                    "label": _oes_perimeter_variant_russian_label(
                        str(o["code"]),
                        binding=binding,
                        entity_kind=entity_kind,
                        entity_name=entity_name,
                        strip_gaes_suffix=strip_gaes_suffix,
                    ),
                }
                for o in _perimeter_variant_options_for_summary(entity_kind, entity_name)
            ]
    return [
        {
            "code": str(code),
            "label": _oes_perimeter_variant_russian_label(
                str(code),
                binding=binding,
                entity_kind=entity_kind,
                entity_name=entity_name,
                strip_gaes_suffix=strip_gaes_suffix,
            ),
        }
        for code in codes
        if code
    ]


def _demand_rows_for_perimeter_variant_entity(
    model: Any,
    parent_fk_column: str | None,
    parent_id: int | None,
    variant_code: str | None,
) -> list[Any]:
    """Строки параметров для строки сводки по коду варианта (включая legacy with_nt/without_nt).

    Для ``*_without_gaes`` всегда идём через ``get_demand_rows_for_summary_block`` по
    НТ-группе: иначе при наличии хотя бы одной строки с этим PVC остальные годы с
    ``NULL`` пропадают с сводки, и сохранение ТНВ / совмещённого / даты ломается.
    """
    if parent_fk_column is not None and parent_id is None:
        return []
    if variant_code in (None, CODE_WITH_NT, CODE_WITHOUT_NT):
        return dps.get_demand_rows_for_summary_block(
            model,
            parent_fk_column,
            parent_id,
            display_perimeter_variant_code=variant_code,
        )
    legacy = legacy_nt_group_for_perimeter_code(variant_code)
    if legacy in (CODE_WITH_NT, CODE_WITHOUT_NT) and "without_gaes" in str(
        variant_code or ""
    ):
        return dps.get_demand_rows_for_summary_block(
            model,
            parent_fk_column,
            parent_id,
            display_perimeter_variant_code=legacy,
        )
    return dps.get_demand_rows(
        model,
        parent_fk_column,
        parent_id,
        perimeter_variant_code=variant_code,
    )


def _demand_row_groups_for_all_binding_variants(
    model: Any,
    parent_fk_column: str | None,
    parent_id: int | None,
    *,
    binding: Any,
) -> list[tuple[str | None, list[Any]]]:
    """``не указано`` + все варианты из привязки /perimeter_variants/ — даже без строк в БД."""
    if binding is None or not getattr(binding, "variants", ()):
        stored = _demand_rows_by_stored_perimeter_variant(
            model,
            parent_fk_column,
            parent_id,
            binding=binding,
        )
        filtered = [
            (code, rows)
            for code, rows in stored
            if not _oes_summary_excludes_perimeter_variant_code(code)
        ]
        if not any(code is None for code, _rows in filtered):
            filtered.insert(
                0,
                (
                    None,
                    _demand_rows_for_perimeter_variant_entity(
                        model,
                        parent_fk_column,
                        parent_id,
                        None,
                    ),
                ),
            )
        return filtered
    codes = _oes_perimeter_variant_codes_for_summary(binding)
    if not codes:
        codes = tuple(
            getattr(v, "code", None)
            for v in binding.variants
            if not _oes_summary_excludes_perimeter_variant_code(getattr(v, "code", None))
        )
    null_rows = _demand_rows_for_perimeter_variant_entity(
        model,
        parent_fk_column,
        parent_id,
        None,
    )
    out: list[tuple[str | None, list[Any]]] = []
    # «Не указано» — только если в БД есть строки без варианта или в привязке нет вариантов.
    if null_rows or not codes:
        out.append((None, null_rows))
    for code in codes:
        out.append(
            (
                code,
                _demand_rows_for_perimeter_variant_entity(
                    model,
                    parent_fk_column,
                    parent_id,
                    code,
                ),
            )
        )
    return out


def _drop_null_perimeter_variant_group_when_nt_pairs_exist(
    groups: list[tuple[str | None, list[Any]]],
) -> list[tuple[str | None, list[Any]]]:
    """Не дублировать строку «не указано», если в привязке есть и «с НТ», и «без НТ»."""
    codes = [code for code, _rows in groups if code is not None and str(code).strip()]
    has_with_nt = any(
        legacy_nt_group_for_perimeter_code(code) == CODE_WITH_NT for code in codes
    )
    has_without_nt = any(
        legacy_nt_group_for_perimeter_code(code) == CODE_WITHOUT_NT for code in codes
    )
    if has_with_nt and has_without_nt:
        return [(code, rows) for code, rows in groups if code is not None]
    return groups


def _demand_row_groups_for_oes_top_aggregate(
    model: Any,
    parent_fk_column: str | None,
    parent_id: int | None,
    *,
    binding: Any,
) -> list[tuple[str | None, list[Any]]]:
    """Варианты периметра для верхних агрегатов на /summary/oes/: без «не указано»."""
    return [
        (code, rows)
        for code, rows in _demand_row_groups_for_all_binding_variants(
            model,
            parent_fk_column,
            parent_id,
            binding=binding,
        )
        if code is not None and str(code).strip() != ""
    ]


def _summary_variant_entity_label(
    binding: Any,
    base_label: str,
    code: str | None,
    entity_kind: str | None,
    entity_name: str | None,
) -> str:
    """Подпись энергосистемы на /power_demand/: база + «с/без НТ» по коду варианта.

    Не берёт ``label_suffix`` / префикс из /perimeter_variants/ (там могут быть
    «без заряда ГАЭС», «(Калин)», «O-1 …» и произвольные переименования).
    Метка О-1 — только у кнопки/бейджа, не в названии строки.
    """
    _ = (binding, entity_kind, entity_name)
    base = str(base_label or "").strip()
    if code is None:
        return base
    base, _kal = _pd_strip_variant_suffixes_from_label(base)
    base = _pd_strip_gaes_text_from_label_fragment(base)
    base = _pd_strip_catalog_annotation_parentheticals(base)
    base = _pd_strip_o1_marker_from_entity_label(base)
    nt_suffix = _pd_nt_label_suffix_for_variant_code(str(code))
    return f"{base}{nt_suffix}".strip()


def _summary_entity_is_already_variant_expanded(entity: SummaryEntity) -> bool:
    if entity.summary_perimeter_variant_row:
        return True
    return entity.perimeter_variant_code is not None


def _perimeter_binding_for_summary_entity(entity: SummaryEntity) -> tuple[str, str, Any] | None:
    if not entity.demand_model_name:
        return None
    try:
        model_cls = dps._summary_demand_model_class(entity.demand_model_name)
    except ValueError:
        return None
    if not model_supports_perimeter_variant(model_cls):
        return None
    ctx = perimeter_entity_context_for_model(
        entity.demand_model_name,
        parent_fk_column=entity.parent_fk_column,
        parent_id=entity.parent_id,
    )
    if ctx is None:
        return None
    pe_kind, pe_name = ctx
    binding = resolve_entity_perimeter_binding(pe_kind, pe_name)
    if binding is None or not getattr(binding, "variants", ()):
        return None
    return pe_kind, pe_name, binding


def _expand_summary_entity_perimeter_variants(
    entity: SummaryEntity,
    *,
    inside_tites_subtree: bool = False,
) -> list[SummaryEntity]:
    inside_tites_subtree = inside_tites_subtree or (
        entity.entity_kind == "aggregation_level"
        and str(entity.label or "").strip() == _TITES_AND_DZ_AGGREGATE_LABEL
    )
    expanded_children: list[SummaryEntity] = []
    for child in entity.children:
        expanded_children.extend(
            _expand_summary_entity_perimeter_variants(
                child,
                inside_tites_subtree=inside_tites_subtree,
            )
        )

    base_entity = replace(entity, children=expanded_children)
    if inside_tites_subtree and str(base_entity.demand_model_name or "") in (
        RegionalEnergySystemDemandParameter.__name__,
        EnergyUnitDemandParameter.__name__,
        RegionalDistrictDemandParameter.__name__,
    ):
        return [base_entity]
    if _summary_entity_is_already_variant_expanded(base_entity):
        return [base_entity]

    if (
        base_entity.entity_kind == "synchronous_area"
        and is_kaliningrad_sync_area_entity_name(base_entity.label)
    ):
        return [_kaliningrad_sync_area_entity_with_stored_variant(base_entity)]

    binding_ctx = _perimeter_binding_for_summary_entity(base_entity)
    if binding_ctx is None:
        return [base_entity]
    pe_kind, pe_name, binding = binding_ctx

    try:
        model_cls = dps._summary_demand_model_class(str(base_entity.demand_model_name))
    except ValueError:
        return [base_entity]

    groups = _demand_row_groups_for_all_binding_variants(
        model_cls,
        base_entity.parent_fk_column,
        base_entity.parent_id,
        binding=binding,
    )
    groups = _drop_null_perimeter_variant_group_when_nt_pairs_exist(groups)
    if not groups:
        return [base_entity]

    children_variant_code = _territorial_children_base_variant_code(binding)
    out: list[SummaryEntity] = []
    for code, demand_rows in groups:
        out.append(
            replace(
                base_entity,
                label=_summary_variant_entity_label(
                    binding,
                    base_entity.label,
                    code,
                    pe_kind,
                    pe_name,
                ),
                demand_rows=demand_rows,
                children=expanded_children if code == children_variant_code else [],
                entity_kind=(
                    "perimeter_variant"
                    if base_entity.entity_kind in ("group", "child", "default")
                    else base_entity.entity_kind
                ),
                perimeter_variant_code=code,
                summary_perimeter_variant_row=True,
            )
        )
    return out


def _expand_summary_entities_perimeter_variants(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for entity in entities:
        out.extend(_expand_summary_entity_perimeter_variants(entity))
    return out


def _shift_summary_entity_depth(e: SummaryEntity, delta: int) -> SummaryEntity:
    d = int(e.depth) if e.depth is not None else 0
    new_d = max(0, d + delta)
    new_children = [_shift_summary_entity_depth(c, delta) for c in e.children]
    return replace(e, depth=new_d, children=new_children)


def _is_ues_oes_top_level_tree(e: SummaryEntity) -> bool:
    """Верхнеуровневый узел ОЭС на сводке /summary/oes/ (с поддеревом РЭС и ниже)."""
    return (
        e.demand_model_name == UnionEnergySystemDemandParameter.__name__
        and e.id_union_energy_system is not None
        and e.entity_kind in ("group", "perimeter_variant")
    )


def _oes_promote_to_top_level_depth(e: SummaryEntity) -> SummaryEntity:
    d = int(e.depth) if e.depth is not None else 0
    return _shift_summary_entity_depth(e, -d)


def _oes_promote_subjects_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_rd: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по субъекту — только субъекты РФ (без уровней ОЭС и РЭС)."""
    if not f_rd:
        return entities
    rd_dn = RegionalDistrictDemandParameter.__name__
    out: list[SummaryEntity] = []
    promoted: list[SummaryEntity] = []
    for e in entities:
        if not _is_ues_oes_top_level_tree(e):
            out.append(e)
            continue
        for res in e.children:
            for sub in res.children:
                if sub.demand_model_name != rd_dn:
                    continue
                rid = sub.id_regional_district
                if rid is None or rid not in f_rd:
                    continue
                promoted.append(_oes_promote_to_top_level_depth(sub))
    return out + promoted


def _oes_promote_energy_units_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_eu: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по энергоузлу — только энергоузлы (без ОЭС, РЭС, субъекта)."""
    if not f_eu:
        return entities
    eu_dn = EnergyUnitDemandParameter.__name__

    def walk_collect(node: SummaryEntity, promoted: list[SummaryEntity]) -> None:
        if node.demand_model_name == eu_dn:
            euid = node.id_energy_unit
            if euid is not None and euid in f_eu:
                promoted.append(_oes_promote_to_top_level_depth(node))
                return
        for c in node.children:
            walk_collect(c, promoted)

    out: list[SummaryEntity] = []
    promoted: list[SummaryEntity] = []
    for e in entities:
        if not _is_ues_oes_top_level_tree(e):
            out.append(e)
            continue
        walk_collect(e, promoted)
    return out + promoted


def _oes_promote_res_only_under_ees_russia(
    entities: list[SummaryEntity],
    f_res: frozenset[int],
) -> list[SummaryEntity]:
    """При фильтре по РЭС — только строки РЭС (без ОЭС, субъектов и энергоузлов)."""
    if not f_res:
        return entities
    res_dn = RegionalEnergySystemDemandParameter.__name__
    out: list[SummaryEntity] = []
    promoted: list[SummaryEntity] = []
    for e in entities:
        if not _is_ues_oes_top_level_tree(e):
            out.append(e)
            continue
        for res in e.children:
            if res.demand_model_name != res_dn:
                continue
            rid = res.id_regional_energy_system
            if rid is None or rid not in f_res:
                continue
            promoted.append(
                replace(_oes_promote_to_top_level_depth(res), children=[])
            )
    return out + promoted


def _build_national_and_sync_zone_prefix_entities(
    *,
    cz_parameters: tuple[tuple[str, str], ...] = PARAMETERS_CZ_OES_SUMMARY,
    ees_russia_parameters: tuple[tuple[str, str], ...] = PARAMETERS_EES_RUSSIA_OES_SUMMARY,
) -> list[SummaryEntity]:
    """Общий префикс режима «Сводная таблица» для сводок ОЭС / ФО / энергозон.

    Порядок: ЦЗ России с/без НТ → ЭЭС России с/без НТ → ЕЭС России с/без НТ →
    Первая синхронная зона с/без НТ → Вторая синхронная зона →
    Синхронная зона Калининградской области.
    """
    return (
        _build_centralized_zone_perimeter_entities(parameters=cz_parameters)
        + _build_ees_perimeter_entities()
        + _build_ees_russia_perimeter_entities(parameters=ees_russia_parameters)
        + _build_synchronous_area_entities(depth=0)
    )


def _summary_rows_include_ues_blocks(summary_rows: list[dict[str, Any]]) -> bool:
    """True, если в таблице уже есть строки ОЭС (на /summary/oes/ источники для префикса на месте)."""
    ues_dm = UnionEnergySystemDemandParameter.__name__
    return any(r.get("demand_model_name") == ues_dm for r in summary_rows)


def _build_oes_national_prefix_source_rows(
    years: list[int],
    rounding_digits: int,
    *,
    avg_temp_uses_global_rounding: bool = False,
) -> list[dict[str, Any]]:
    """Скрытое дерево ОЭС (+ ТИТЭС) для формул префикса ЕЭС/СЗ на сводках ФО и энергозон.

    Не попадает в ``summary_rows`` страницы: только временный хвост при обогащении,
    чтобы цифры совпадали с /summary/oes/.
    """
    if not years:
        return []
    entities: list[SummaryEntity] = list(_build_oes_union_energy_system_entities())
    tites_entity = _build_tites_entity()
    if tites_entity is not None:
        entities.append(tites_entity)
    flat = _flatten_entities(
        entities,
        years,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    _inject_south_ues_nt_rows_after_res(
        flat,
        years=years,
        rounding_digits=rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    mask_sakha_yakutia_tites_oes_east_year_membership(flat, years)
    return flat


def _enrich_national_prefix_calculated_max_like_oes(
    working_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    filter_year_list: list[int],
) -> None:
    """Расчётные показатели префикса ЦЗ / ЕЭС / СЗ / ЭЭС — как в ``_enrich_oes_summary_calculated_max_from_res``."""
    enrich_oes_summary_calculated_max_power_from_res_combined(
        working_rows, years, rounding_digits
    )
    enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
        working_rows, years, rounding_digits
    )
    enrich_oes_summary_calculated_combined_on_ees_from_res_combined(
        working_rows, years, rounding_digits
    )
    enrich_south_ues_perimeter_calculated_combined_on_ees_from_res(
        working_rows, years, rounding_digits
    )
    enrich_oes_ees_russia_calculated_max_russia_mw(
        working_rows,
        years,
        rounding_digits,
        filter_year_list=list(filter_year_list or years),
    )
    enrich_oes_ees_russia_calculated_max_via_oes(working_rows, years, rounding_digits)
    enrich_oes_ees_russia_calculated_max_via_es(working_rows, years, rounding_digits)
    enrich_ees_russia_calculated_max_via_ez(working_rows, years, rounding_digits)
    enrich_oes_summary_calculated_max_power_sa_from_res_max_power(
        working_rows, years, rounding_digits
    )
    enrich_oes_summary_calculated_max_sa_from_res_combined_on_ees(
        working_rows, years, rounding_digits
    )
    enrich_oes_ees_calculated_max_power_consumption(
        working_rows, years, rounding_digits
    )
    enrich_cz_russia_calculated_max_power_mw(working_rows, years, rounding_digits)


def _apply_national_prefix_oes_formulas(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    filter_year_list: list[int] | None = None,
    avg_temp_uses_global_rounding: bool = False,
    enrich_calculated: bool = True,
    oes_source_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Заполняет префикс ЕЭС/СЗ на ФО/ЭЗ формулами ОЭС; возвращает кэш скрытых строк-источников.

    Строки префикса в ``summary_rows`` мутируются на месте (те же объекты dict).
    """
    if not summary_rows or not years:
        return list(oes_source_rows or [])

    if _summary_rows_include_ues_blocks(summary_rows):
        sources: list[dict[str, Any]] = []
        working = summary_rows
    else:
        sources = (
            list(oes_source_rows)
            if oes_source_rows is not None
            else _build_oes_national_prefix_source_rows(
                years,
                rounding_digits,
                avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
            )
        )
        working = summary_rows + sources

    if enrich_calculated:
        _enrich_national_prefix_calculated_max_like_oes(
            working,
            years,
            rounding_digits,
            filter_year_list=list(filter_year_list or years),
        )
    apply_second_sa_from_ues_east_formula(working, years, rounding_digits)
    apply_kaliningrad_sa_from_kaliningrad_es_formula(working, years, rounding_digits)
    return sources


def _build_oes_raw_entities(
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    """Полное дерево сводки по ОЭС без территориальных фильтров (для объединения выборов и «без фильтра»).

    Верхний порядок уровней: ЦЗ России → ЭЭС России → тип энергосистемы «ЕЭС России» → синхронные зоны
    → ОЭС (с РЭС / субъектами / энергорайонами) → ТИТЭС и ДЗ.
    """
    entities: list[SummaryEntity] = (
        _build_national_and_sync_zone_prefix_entities(
            cz_parameters=PARAMETERS_CZ_OES_SUMMARY,
        )
        + _build_oes_union_energy_system_entities(
            always_show_subject_row_under_res=always_show_subject_row_under_res,
        )
    )

    tites_entity = _build_tites_entity()
    if tites_entity is not None:
        entities.append(tites_entity)
    return entities


def _build_oes_union_energy_system_entities(
    *,
    always_show_subject_row_under_res: bool = False,
) -> list[SummaryEntity]:
    """ОЭС ветки ЕЭС России: варианты периметра и поддерево РЭС → субъект → энергорайон."""
    ues_list = _build_ues_entities_filtered(
        _is_ees_branch,
        always_show_subject_row_under_res=always_show_subject_row_under_res,
        ues_depth=0,
    )
    return _inject_perimeter_variant_entities(
        ues_list,
        entity_kind="union_energy_system",
        ues_depth=0,
    )


def _strip_oes_ees_russia_nt_parent_aggregate(entities: list[SummaryEntity]) -> list[SummaryEntity]:
    """Сохранено для совместимости вызовов при территориальном фильтре (плоское дерево — без изменений)."""
    return list(entities)


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


def _summary_data_segments_requested(
    data_segments: frozenset[str] | None,
    segment: str,
) -> bool:
    from app.power_demand.services.pd_summary_data_segments import needs_full_summary_build

    return needs_full_summary_build(data_segments) or segment in (data_segments or frozenset())


def _tag_common_power_demand_summary_rows(
    rows: list[dict[str, Any]],
    *,
    oes_summary: bool = False,
) -> None:
    tag_power_demand_summary_rows_for_nt_toggle(rows)
    tag_power_demand_summary_rows_for_territory_compact(rows)
    tag_power_demand_summary_rows_perimeter_variant_labels(
        rows,
        oes_summary=oes_summary,
    )
    if oes_summary:
        tag_power_demand_south_ues_without_nt_manual_rows(rows)


def _filter_power_demand_summary_context_segments(
    ctx: dict[str, Any],
    data_segments: frozenset[str] | None,
    *,
    scope: str,
) -> None:
    if data_segments is None:
        return
    from app.power_demand.services.pd_summary_data_segments import (
        filter_summary_rows_for_data_segments,
    )

    ctx["summary_rows"] = filter_summary_rows_for_data_segments(
        ctx["summary_rows"],
        data_segments,
        scope=scope,
    )


def _finalize_oes_summary_context(
    ctx: dict[str, Any],
    rounding_digits: int,
    data_segments: frozenset[str] | None,
) -> None:
    from app.power_demand.services.pd_summary_data_segments import (
        PD_SUMMARY_SEGMENT_CALC_MAX,
        PD_SUMMARY_SEGMENT_CHI,
        PD_SUMMARY_SEGMENT_EE,
        PD_SUMMARY_SEGMENT_VERIFY,
    )

    rows = ctx["summary_rows"]
    years = list(ctx["years"])
    _inject_south_ues_nt_rows_after_res(
        rows,
        years=years,
        rounding_digits=rounding_digits,
        avg_temp_uses_global_rounding=bool(
            ctx.get("avg_temp_uses_global_rounding")
        ),
    )
    _tag_common_power_demand_summary_rows(rows, oes_summary=True)
    # До формул ЭЭС/ТИТЭС: Западный/Центральный Саха — ≤2018 под ТИТЭС, ≥2019 под ОЭС Востока.
    mask_sakha_yakutia_tites_oes_east_year_membership(rows, years)

    need_calc_max_enrichment = _summary_data_segments_requested(
        data_segments, PD_SUMMARY_SEGMENT_CALC_MAX
    ) or _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_VERIFY)
    if need_calc_max_enrichment:
        _inject_chukotka_rd_calculated_max_rows(rows, years, rounding_digits)
        _propagate_pd_territory_compact_hide_flags(rows)
        _enrich_oes_summary_calculated_max_from_res(ctx, rounding_digits)
    apply_second_sa_from_ues_east_formula(rows, years, rounding_digits)
    apply_kaliningrad_sa_from_kaliningrad_es_formula(rows, years, rounding_digits)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_VERIFY):
        _inject_oes_summary_verification_rows(rows, years)
        tag_power_demand_summary_rows_for_territory_compact(rows)
        _clear_south_ues_with_nt_formula_years_before(rows, years)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_CHI):
        _inject_oes_peak_usage_hours_rows(ctx, rounding_digits)
        tag_power_demand_summary_rows_for_territory_compact(rows)
        # ЧЧИ 2-й СЗ и СЗ Калининграда: числитель из ОЭС Востока / ЭС Калининграда (как max_power).
        apply_second_sa_from_ues_east_formula(rows, years, rounding_digits)
        apply_kaliningrad_sa_from_kaliningrad_es_formula(rows, years, rounding_digits)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_EE):
        from app.power_demand.services.pd_peak_usage_hours_services import (
            inject_energy_consumption_rows,
        )

        inject_energy_consumption_rows(rows, years, rounding_digits)
        tag_power_demand_summary_rows_for_territory_compact(rows)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_VERIFY):
        _attach_oes_summary_live_calc_context(ctx)

    mask_power_demand_summary_rows_perimeter_variant_year_display(
        rows,
        years,
        unrestricted_perimeter_variant_input=True,
    )
    _clear_summary_hist_non_base_parameters(rows)
    rows = filter_oes_summary_hidden_tites_union_energy_system_rows(rows)
    rows = filter_oes_summary_hidden_chukotka_rd_rows(rows)
    rows = exclude_o1_perimeter_variant_summary_rows(rows)
    ctx["summary_rows"] = _rebuild_summary_entity_row_blocks(rows)
    from app.power_demand.services.pd_summary_entity_pagination import (
        tag_summary_rows_before_section_blocks,
    )

    tag_summary_rows_before_section_blocks(ctx["summary_rows"], "oes")

    _filter_power_demand_summary_context_segments(ctx, data_segments, scope="oes")


def _finalize_fo_summary_context(
    ctx: dict[str, Any],
    rounding_digits: int,
    data_segments: frozenset[str] | None,
) -> None:
    from app.power_demand.services.pd_summary_data_segments import (
        PD_SUMMARY_SEGMENT_CALC_MAX,
        PD_SUMMARY_SEGMENT_CHI,
        PD_SUMMARY_SEGMENT_EE,
        PD_SUMMARY_SEGMENT_VERIFY,
    )

    rows = ctx["summary_rows"]
    years = list(ctx["years"])
    avg_temp_global = bool(ctx.get("avg_temp_uses_global_rounding"))
    filter_years = list(ctx.get("filter_year_list") or years)
    # Порядок ЦЗ с НТ → без НТ (в т.ч. o1_with_nt / o1_without_nt).
    reorder_centralized_zone_russia_variant_blocks_in_summary_rows(rows)
    ctx["summary_rows"] = exclude_o1_perimeter_variant_summary_rows(rows)
    rows = ctx["summary_rows"]
    need_calc_max = _summary_data_segments_requested(
        data_segments, PD_SUMMARY_SEGMENT_CALC_MAX
    )
    need_verify = _summary_data_segments_requested(
        data_segments, PD_SUMMARY_SEGMENT_VERIFY
    )
    if need_calc_max or need_verify:
        _enrich_fo_summary_calculated_max_from_res(ctx, rounding_digits)
    if need_calc_max:
        _inject_fo_max_cz_russia_calculated_max_row(
            rows, years, int(ctx["rounding_digits"]),
            fo_max_extended_parameters=bool(ctx.get("fo_max_extended_parameters")),
        )
    # Префикс ЦЗ→ЭЭС→ЕЭС→СЗ: те же формулы, что на /summary/oes/ (скрытое дерево ОЭС).
    oes_sources = _apply_national_prefix_oes_formulas(
        rows,
        years,
        rounding_digits,
        filter_year_list=filter_years,
        avg_temp_uses_global_rounding=avg_temp_global,
        enrich_calculated=need_calc_max or need_verify,
    )
    _tag_common_power_demand_summary_rows(rows, oes_summary=True)
    if need_verify:
        _inject_oes_summary_verification_rows(rows, years)
        tag_power_demand_summary_rows_for_territory_compact(rows)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_CHI):
        from app.power_demand.services.pd_peak_usage_hours_services import (
            inject_combined_peak_usage_hours_rows,
            inject_peak_usage_hours_rows,
        )

        inject_peak_usage_hours_rows(rows, years, rounding_digits)
        inject_combined_peak_usage_hours_rows(rows, years, rounding_digits)
        # ЧЧИ 2-й СЗ / СЗ Калининграда — как на ОЭС: числитель из ОЭС Востока / ЭС Калининграда.
        _apply_national_prefix_oes_formulas(
            rows,
            years,
            rounding_digits,
            filter_year_list=filter_years,
            avg_temp_uses_global_rounding=avg_temp_global,
            enrich_calculated=False,
            oes_source_rows=oes_sources,
        )
        tag_power_demand_summary_rows_for_territory_compact(rows)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_EE):
        from app.power_demand.services.pd_peak_usage_hours_services import (
            inject_energy_consumption_rows,
        )

        inject_energy_consumption_rows(rows, years, rounding_digits)
        tag_power_demand_summary_rows_for_territory_compact(rows)

    mask_power_demand_summary_rows_perimeter_variant_year_display(
        rows,
        years,
        unrestricted_perimeter_variant_input=True,
    )
    _clear_summary_hist_non_base_parameters(rows)
    from app.power_demand.services.pd_summary_entity_pagination import (
        tag_summary_rows_before_section_blocks,
    )

    tag_summary_rows_before_section_blocks(rows, "fo")

    _filter_power_demand_summary_context_segments(ctx, data_segments, scope="fo")


def _finalize_ez_summary_context(
    ctx: dict[str, Any],
    rounding_digits: int,
    data_segments: frozenset[str] | None,
) -> None:
    from app.power_demand.services.pd_summary_data_segments import (
        PD_SUMMARY_SEGMENT_CALC_MAX,
        PD_SUMMARY_SEGMENT_CHI,
        PD_SUMMARY_SEGMENT_EE,
        PD_SUMMARY_SEGMENT_VERIFY,
    )

    rows = ctx["summary_rows"]
    years = list(ctx["years"])
    avg_temp_global = bool(ctx.get("avg_temp_uses_global_rounding"))
    filter_years = list(ctx.get("filter_year_list") or years)
    reorder_centralized_zone_russia_variant_blocks_in_summary_rows(rows)
    need_calc_max = _summary_data_segments_requested(
        data_segments, PD_SUMMARY_SEGMENT_CALC_MAX
    )
    need_verify = _summary_data_segments_requested(
        data_segments, PD_SUMMARY_SEGMENT_VERIFY
    )
    if need_calc_max or need_verify:
        _enrich_ez_summary_calculated_max_from_res(ctx, rounding_digits)
    # Префикс ЦЗ→ЭЭС→ЕЭС→СЗ: те же формулы, что на /summary/oes/ (скрытое дерево ОЭС).
    oes_sources = _apply_national_prefix_oes_formulas(
        rows,
        years,
        rounding_digits,
        filter_year_list=filter_years,
        avg_temp_uses_global_rounding=avg_temp_global,
        enrich_calculated=need_calc_max or need_verify,
    )
    # Префикс ЦЗ→ЭЭС→ЕЭС→СЗ есть и на max, и на coeff.
    _tag_common_power_demand_summary_rows(rows, oes_summary=True)
    tag_power_demand_ez_summary_group_rows_skip_empty_hide(rows)
    if need_verify:
        _inject_oes_summary_verification_rows(rows, years)
        tag_power_demand_summary_rows_for_territory_compact(rows)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_CHI):
        from app.power_demand.services.pd_peak_usage_hours_services import (
            inject_combined_peak_usage_hours_rows,
            inject_peak_usage_hours_rows,
        )

        inject_peak_usage_hours_rows(rows, years, rounding_digits)
        inject_combined_peak_usage_hours_rows(rows, years, rounding_digits)
        _apply_national_prefix_oes_formulas(
            rows,
            years,
            rounding_digits,
            filter_year_list=filter_years,
            avg_temp_uses_global_rounding=avg_temp_global,
            enrich_calculated=False,
            oes_source_rows=oes_sources,
        )
        tag_power_demand_summary_rows_for_territory_compact(rows)
    if _summary_data_segments_requested(data_segments, PD_SUMMARY_SEGMENT_EE):
        from app.power_demand.services.pd_peak_usage_hours_services import (
            inject_energy_consumption_rows,
        )

        inject_energy_consumption_rows(rows, years, rounding_digits)
        tag_power_demand_summary_rows_for_territory_compact(rows)

    mask_power_demand_summary_rows_perimeter_variant_year_display(
        rows,
        list(ctx["years"]),
        unrestricted_perimeter_variant_input=True,
    )
    _clear_summary_hist_non_base_parameters(rows)
    rows = exclude_o1_perimeter_variant_summary_rows(rows)
    ctx["summary_rows"] = rows
    from app.power_demand.services.pd_summary_entity_pagination import (
        tag_summary_rows_before_section_blocks,
    )

    tag_summary_rows_before_section_blocks(ctx["summary_rows"], "ez")

    _filter_power_demand_summary_context_segments(ctx, data_segments, scope="ez")


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
    data_segments: frozenset[str] | None = None,
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
        ent = _expand_summary_entities_perimeter_variants(ent)
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
        _finalize_oes_summary_context(ctx, rounding_digits, data_segments)
        return ctx

    entities = _expand_summary_entities_perimeter_variants(
        _build_oes_raw_entities(always_show_subject_row_under_res=False)
    )
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
    _finalize_oes_summary_context(ctx, rounding_digits, data_segments)
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
        "Проверка максимального потребления мощности, МВт",
        ("calculated_max_power_consumption_mw", "max_power"),
    ),
    (
        "calculated_max_ees_russia_mw",
        "verify_for_calculated_max_ees_russia_mw",
        "Проверка максимального потребления мощности, МВт",
        ("calculated_max_ees_russia_mw", "max_power"),
    ),
    (
        "calculated_max_ees_via_oes_mw",
        "verify_for_calculated_max_ees_via_oes_mw",
        "Проверка максимального потребления мощности (через ОЭС), МВт",
        ("calculated_max_ees_via_oes_mw", "max_power"),
    ),
    (
        "calculated_max_ees_via_es_mw",
        "verify_for_calculated_max_ees_via_es_mw",
        "Проверка максимального потребления мощности (через ЭС), МВт",
        ("calculated_max_ees_via_es_mw", "max_power"),
    ),
    (
        "calculated_max_ees_via_ez_mw",
        "verify_for_calculated_max_ees_via_ez_mw",
        "Проверка максимального потребления мощности (через ЭЗ), МВт",
        ("calculated_max_ees_via_ez_mw", "max_power"),
    ),
    (
        "calculated_max_sa_mw",
        "verify_for_calculated_max_sa_mw",
        "Проверка расчетного совмещенного потребления мощности на час прохождения максимума ЕЭС, МВт",
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
        "sakha_tites_extra_eu_ids": sorted(
            _tites_sakha_yakutia_extra_energy_unit_ids()
        ),
        "sakha_tites_extra_through_year": (
            _TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR
        ),
        "ees_aggregate_tites_eu_ids": sorted(
            _ees_aggregate_formula_tites_energy_unit_ids()
        ),
        "first_sync_area_id": _resolve_synchronous_area_id_by_name_prefix_cf(
            _FIRST_SYNC_AREA_BASE_LABEL_CF
        ),
        "default_perimeter_variant": None,
        "res_to_sa_ids": {
            str(res_id): sorted(sa_ids) for res_id, sa_ids in res_to_sa.items()
        },
        "second_sync_area_id": second_sa_id,
        "kaliningrad_sync_area_id": kaliningrad_sa_id,
        "kaliningrad_es_id": kaliningrad_es_id,
        "ues_east_id": _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF),
        "south_ues_ids": south_ues_ids,
        "south_ues_id": south_ues_ids[0] if south_ues_ids else None,
        "nt_regional_district_ids": sorted(_new_territories_regional_district_ids()),
    }
    from app.power_demand.services.perimeter_variant_tree_rules import (
        NEW_TERRITORIES_FROM_YEAR,
    )

    ctx["pd_oes_live_calc_js"]["new_territories_from_year"] = int(
        NEW_TERRITORIES_FROM_YEAR
    )


def _inject_oes_summary_verification_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """
    Сводка «Максимумы» по ОЭС: добавить скрытые строки «Проверка для …» в каждом блоке сущности.

    Формулы (значения по годам — целое число; в title при наведении — до 3 знаков после запятой):
    - «Проверка максимального потребления мощности , МВт» =
        «Расчетное максимальное потребление мощности, МВт» − «Максимальное потребление мощности, МВт»
    - «Проверка расчетного совмещенного потребления мощности на час прохождения максимума ЕЭС, МВт» =
        «Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» − «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт»
    - «Проверка расчетного совмещенного … на ЦЗ России, МВт» (ФО) =
        «Расчетное/Расчетный совмещенный … на ЦЗ России, МВт» − «Совмещенное/Совмещенный … на ЦЗ России, МВт»
    - После каждой строки «Расчетный максимум потребления мощности …» — своя «Проверка для …»
      (для части показателей формула будет добавлена позже).
    """
    if not summary_rows or not years:
        return

    n_y = len(years)

    def _diff_year_values(
        a_row: dict[str, Any] | None,
        b_row: dict[str, Any] | None,
        *,
        bounds_row: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        """a - b (строки могут быть None или пустыми)."""
        if a_row is None or b_row is None:
            return (["—"] * n_y, [""] * n_y)
        out_vals: list[str] = []
        out_tt: list[str] = []
        for j in range(n_y):
            if bounds_row is not None and not _formula_year_applies_to_row_perimeter_variant(
                bounds_row, int(years[j])
            ):
                out_vals.append("—")
                out_tt.append("")
                continue
            av = _summary_row_year_float(a_row, j)
            bv = _summary_row_year_float(b_row, j)
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
            year_values, year_tooltips = _diff_year_values(
                a_row, b_row, bounds_row=block0
            )
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
            # Якорь блока для клиентского merge по fingerprint (demand_summary_client_render.js).
            "demand_model_name": block0.get("demand_model_name"),
            "parent_fk_column": block0.get("parent_fk_column"),
            "parent_id": block0.get("parent_id"),
            "id_regional_energy_system": block0.get("id_regional_energy_system"),
            "id_regional_district": block0.get("id_regional_district"),
            "id_energy_unit": block0.get("id_energy_unit"),
            "id_synchronous_area": block0.get("id_synchronous_area"),
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
            "pd_pd_territory_compact_hide_row": block0.get(
                "pd_pd_territory_compact_hide_row"
            ),
            "pd_pd_territory_detail_row": block0.get("pd_pd_territory_detail_row"),
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
                new_parameter_label="Проверка максимального потребления мощности, МВт",
                a_parameter_key="calculated_max_power_mw",
                b_parameter_key="max_power",
            )
            span += 1
            end += 1
            keys_in_block.add("verify_for_calculated_max_power_mw")

        # 1b) ФО: расчётный совмещённый на ЦЗ − совмещённый на ЦЗ (только у федерального округа).
        if (
            {"calculated_combined_on_cz_mw", "combined_on_cz"} <= keys_in_block
            and str(row0.get("demand_model_name") or "")
            == FederalDistrictDemandParameter.__name__
            and "verify_for_calculated_combined_on_cz_mw" not in keys_in_block
        ):
            calc_cz_label = next(
                (
                    str(summary_rows[j].get("parameter_label") or "")
                    for j in range(i, end)
                    if str(summary_rows[j].get("parameter_key") or "")
                    == "calculated_combined_on_cz_mw"
                ),
                "",
            )
            # Как на /summary/federal_districts/ (PARAMETERS_FEDERAL_DISTRICT_MAX).
            # Короткие подписи «…совмещенного на ЦЗ…» — только для legacy coeff без max-набора.
            if "потребления" in calc_cz_label.casefold() or "час максимума" in calc_cz_label.casefold():
                verify_cz_label = (
                    "Проверка расчетного совмещенного потребления мощности "
                    "на час максимума ЦЗ России, МВт"
                )
            else:
                verify_cz_label = "Проверка расчетного совмещенного на ЦЗ России, МВт"
            _inject_one(
                block_start=i,
                block_size=span,
                insert_after_parameter_key="calculated_combined_on_cz_mw",
                new_parameter_key="verify_for_calculated_combined_on_cz_mw",
                new_parameter_label=verify_cz_label,
                a_parameter_key="calculated_combined_on_cz_mw",
                b_parameter_key="combined_on_cz",
            )
            span += 1
            end += 1
            keys_in_block.add("verify_for_calculated_combined_on_cz_mw")

        # 2) ОЭС: расчетный совмещенный на ЕЭС − совмещенный на ЕЭС.
        if {"calculated_combined_on_ees_mw", "combined_on_ees"} <= keys_in_block:
            _inject_one(
                block_start=i,
                block_size=span,
                insert_after_parameter_key="calculated_combined_on_ees_mw",
                new_parameter_key="verify_for_calculated_combined_on_ees_mw",
                new_parameter_label="Проверка расчетного совмещенного потребления мощности на час прохождения максимума ЕЭС, МВт",
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
    fo_max_extended_parameters: bool = False,
    for_client_render_shell: bool = False,
    data_segments: frozenset[str] | None = None,
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
    больше одного субъекта — строки субъектов с энергорайонами; при одном субъекте —
    энергорайоны сразу под РЭС (как на сводке потребления ЭЭ по ФО). Фильтр ``ds_res``
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
    fd_parameters = (
        PARAMETERS_FEDERAL_DISTRICT_MAX
        if fo_max_extended_parameters
        else PARAMETERS_FEDERAL_DISTRICT
    )
    res_parameters = (
        PARAMETERS_RES_FO_MAX if fo_max_extended_parameters else PARAMETERS_RES_FO_COEFF
    )
    entities: list[SummaryEntity] = list(
        # Тот же префикс «Сводной таблицы», что на max и coeff ОЭС / ФО / ЭЗ.
        _build_national_and_sync_zone_prefix_entities(
            cz_parameters=PARAMETERS_CZ_OES_SUMMARY,
        )
    )
    entities.extend(
        _build_federal_district_entities_by_res(
            fd_parameters=fd_parameters,
            res_parameters=res_parameters,
        )
        if fo_aggregate_by_res
        else _build_federal_district_entities()
    )

    if fo_filter_sets is not None:
        f_fd, f_res = fo_filter_sets
        if f_fd or f_res:
            entities = prune_summary_entities_fo(entities, f_fd, f_res)

    entities = _expand_summary_entities_perimeter_variants(entities)
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
    ctx["fo_max_extended_parameters"] = fo_max_extended_parameters
    _finalize_fo_summary_context(ctx, rounding_digits, data_segments)
    return ctx


def _inject_fo_max_cz_russia_calculated_max_row(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    fo_max_extended_parameters: bool = False,
) -> None:
    """На сводке «Максимумы по ФО»: строка под «ЦЗ России» = сумма combined_on_cz по всем ФО."""
    if not summary_rows or not years:
        return

    fd_combined_on_cz_label = (
        "Совмещенное потребление мощности на час максимума ЦЗ России, МВт"
        if fo_max_extended_parameters
        else "Совмещенный ФО на ЦЗ России, МВт"
    )

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
                f"Σ(«{fd_combined_on_cz_label}») по всем федеральным округам."
            ),
            "pd_formula_text_key": "fo_cz_calc_max",
        },
    )


def _build_ez_raw_entities(*, ez_max_extended_parameters: bool = False) -> list[SummaryEntity]:
    """Префикс «Сводной таблицы» (ЦЗ→ЭЭС→ЕЭС→СЗ) + дерево энергозон (без ТИТЭС)."""
    entities: list[SummaryEntity] = list(
        _build_national_and_sync_zone_prefix_entities(
            cz_parameters=PARAMETERS_CZ_OES_SUMMARY,
            ees_russia_parameters=PARAMETERS_EES_RUSSIA_EZ_SUMMARY,
        )
    )
    entities.extend(
        _build_energy_zone_entities(
            ez_max_extended_parameters=ez_max_extended_parameters,
        )
    )
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
    ez_max_extended_parameters: bool = False,
    for_client_render_shell: bool = False,
    data_segments: frozenset[str] | None = None,
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
        base_entities = copy.deepcopy(
            _build_ez_raw_entities(
                ez_max_extended_parameters=ez_max_extended_parameters,
            )
        )
        f_ez = frozenset(ez_l)
        f_res = frozenset(res_l)
        ent = prune_summary_entities_ez(base_entities, f_ez, f_res)
        if _ez_res_only_flat_mode(f_ez, f_res):
            ent = _flatten_energy_zone_parents_when_res_filtered(ent)
        ent = _expand_summary_entities_perimeter_variants(ent)
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
        ctx["ez_max_extended_parameters"] = ez_max_extended_parameters
        _finalize_ez_summary_context(ctx, rounding_digits, data_segments)
        return ctx

    entities = _expand_summary_entities_perimeter_variants(
        _build_ez_raw_entities(ez_max_extended_parameters=ez_max_extended_parameters)
    )
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
    ctx["ez_max_extended_parameters"] = ez_max_extended_parameters
    _finalize_ez_summary_context(ctx, rounding_digits, data_segments)
    return ctx


def build_oes_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]] | None = None,
    for_client_render_shell: bool = False,
    data_segments: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Коэффициенты по ОЭС: тот же префикс «Сводной таблицы» (ЦЗ→ЭЭС→ЕЭС→СЗ), что на max."""
    ctx = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=oes_territory_ordered,
        avg_temp_uses_global_rounding=True,
        for_client_render_shell=for_client_render_shell,
        data_segments=data_segments,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергосистемам"
    if not for_client_render_shell:
        tag_power_demand_coeff_summary_rows_without_gaes_entity_labels(
            ctx["summary_rows"]
        )
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
        "Сумма значений «Максимальное потребление мощности, МВт» по строкам федеральных округов "
        "и по строкам региональных энергосистем, отображаемым в таблице (без строки «ЦЗ России»). "
        "Учитываются максимумы и на уровне ФО, и на уровне РЭС под округами.",
        "Сумма значений «Совмещенное потребление мощности на час максимума ЦЗ России, МВт» по всем строкам региональных энергосистем, "
        "показанным в таблице под соответствующими федеральными округами.",
        "Разность между «Максимальное потребление мощности, МВт» для сущности «ЦЗ России» "
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
    for_client_render_shell: bool = False,
    data_segments: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Коэффициенты по ФО: префикс «Сводной таблицы» (ЦЗ→ЭЭС→ЕЭС→СЗ) + дерево ФО→РЭС.

    Набор расчётных/проверочных строк и формулы — как на /summary/federal_districts/
    (``fo_max_extended_parameters=True``).
    """
    ctx = build_federal_district_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        fo_filter_sets=fo_filter_sets,
        avg_temp_uses_global_rounding=True,
        fo_aggregate_by_res=True,
        fo_max_extended_parameters=True,
        for_client_render_shell=for_client_render_shell,
        data_segments=data_segments,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по ФО"
    if not for_client_render_shell:
        _inject_fo_coeff_cz_total_rows(
            ctx["summary_rows"],
            list(ctx["years"]),
            int(ctx["rounding_digits"]),
        )
    # Подписи энергосистем — как на /summary/federal_districts/ (кнопка «+ НТ»),
    # без принудительного «без НТ / без заряда ГАЭС» в compact-режиме.
    return ctx


def build_energy_zones_summary_context_coeff(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    filter_year_list: list[int],
    ez_territory_ordered: tuple[list[int], list[int]] | None = None,
    for_client_render_shell: bool = False,
    data_segments: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Коэффициенты по энергозонам: префикс «Сводной таблицы» (ЦЗ→ЭЭС→ЕЭС→СЗ) + дерево ЭЗ.

    Набор расчётных/проверочных строк и формулы — как на /summary/energy_zones/
    (``ez_max_extended_parameters=True``).
    """
    ctx = build_energy_zones_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        filter_year_list=filter_year_list,
        ez_territory_ordered=ez_territory_ordered,
        avg_temp_uses_global_rounding=True,
        ez_max_extended_parameters=True,
        for_client_render_shell=for_client_render_shell,
        data_segments=data_segments,
    )
    ctx["page_title"] = "Коэффициенты и совмещенные максимумы по энергозонам"
    # Подписи — как на /summary/energy_zones/ (кнопка «+ НТ»).
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


# Кнопки ЭЭ / ЧЧИ / «Проверка» и расчётные максимумы — тоже в Excel при видимости на экране.
_PD_EXPORT_TOGGLE_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "peak_max_power_usage_hours",
        "peak_combined_on_ees_usage_hours",
        "peak_combined_on_oes_usage_hours",
        "peak_combined_on_es_usage_hours",
        "peak_combined_on_fo_usage_hours",
        "peak_combined_on_cz_usage_hours",
        "peak_combined_on_ez_usage_hours",
        "verify_for_calculated_max_power_mw",
        "verify_for_calculated_combined_on_cz_mw",
        "verify_for_calculated_combined_on_ees_mw",
        "verify_for_calculated_max_sa_mw",
        "verify_for_calculated_max_ees_russia_mw",
        "verify_for_calculated_max_ees_via_oes_mw",
        "verify_for_calculated_max_ees_via_es_mw",
        "verify_for_calculated_max_ees_via_ez_mw",
        "verify_for_calculated_max_power_consumption_mw",
    }
)

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
    | _PD_EXPORT_TOGGLE_PARAMETER_KEYS
)
FO_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "cz_calculated_max_cz_russia_mw",
        "calculated_max_power_mw",
        "calculated_combined_on_cz_mw",
        "combined_on_fo",
        "combined_on_es",
        "peak_max_power_usage_hours",
        "verify_for_calculated_max_power_mw",
        "verify_for_calculated_combined_on_cz_mw",
        "verify_for_calculated_combined_on_ees_mw",
    }
    | _PD_EXPORT_TOGGLE_PARAMETER_KEYS
)
# Экран «Коэффициенты по ФО»: под ФО — РЭС (на ФО, на ЦЗ России), субъекты и энергорайоны.
FO_COEFF_EXPORT_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_cz",
        "combined_on_fo",
        "combined_on_es",
        "calculated_max_power_mw",
        "calculated_max_fo_mw",
        "calculated_combined_on_cz_mw",
        # Итоговые строки под «ЦЗ России» (только экран coeff/ФО).
        "cz_total_sum_fo_max_power",
        "cz_total_sum_res_combined_cz",
        "cz_total_imbalance_mw",
    }
    | _PD_EXPORT_TOGGLE_PARAMETER_KEYS
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
        "calculated_max_ees_via_oes_mw",
        "calculated_max_ees_via_es_mw",
        "calculated_max_ees_via_ez_mw",
        "calculated_max_power_mw",
        "calculated_combined_on_ees_mw",
        "combined_on_ez",
        "combined_on_ees",
        "peak_max_power_usage_hours",
        "verify_for_calculated_max_power_mw",
        "verify_for_calculated_combined_on_ees_mw",
    }
    | _PD_EXPORT_TOGGLE_PARAMETER_KEYS
)


_PD_OES_NT_EXTRA_ENTITY_LABELS = frozenset(
    {
        "Россия с НТ",
        "ЭЭС России с НТ",
        "ЕЭС России с НТ",
        "Первая синхронная зона с НТ",
        "ОЭС Юга с НТ",
        f"{CENTRALIZED_ZONE_AGGREGATE_NAME} с НТ",
    }
)
_PD_OES_NT_COMPACT_ENTITY_LABELS: dict[str, str] = {
    "Россия без НТ": "Россия",
    "ЭЭС России без НТ": "ЭЭС России",
    "ЕЭС России без НТ": "ЕЭС России",
    "Первая синхронная зона без НТ": "Первая синхронная зона",
    "ОЭС Юга без НТ": "ОЭС Юга",
    f"{CENTRALIZED_ZONE_AGGREGATE_NAME} без НТ": CENTRALIZED_ZONE_AGGREGATE_NAME,
}
_PD_NT_LABEL_SUFFIX_WITH = " с НТ"
_PD_NT_LABEL_SUFFIX_WITHOUT = " без НТ"
_PD_GAES_LABEL_SUFFIX_WITH = " с зарядом ГАЭС"
_PD_GAES_LABEL_SUFFIX_WITHOUT = " без заряда ГАЭС"
_PD_KALININGRAD_LABEL_SUFFIX_WITH = " с ЭС Калининградской области"
_PD_KALININGRAD_LABEL_SUFFIX_WITHOUT = " без ЭС Калининградской области"
_PD_VARIANT_LABEL_STRIP_SUFFIXES = (
    _PD_GAES_LABEL_SUFFIX_WITH,
    _PD_GAES_LABEL_SUFFIX_WITHOUT,
    _PD_NT_LABEL_SUFFIX_WITH,
    _PD_NT_LABEL_SUFFIX_WITHOUT,
    _PD_KALININGRAD_LABEL_SUFFIX_WITH,
    _PD_KALININGRAD_LABEL_SUFFIX_WITHOUT,
)
_EES_DEMAND_MODEL_NAME = _EES_AGGREGATE_DEMAND_MODEL_NAME
_EES_RUSSIA_DEMAND_MODEL_NAME = _EES_UNIFIED_DEMAND_MODEL_NAME
_UES_DEMAND_MODEL_NAME = UnionEnergySystemDemandParameter.__name__


def _pd_split_kaliningrad_suffix_from_label(label: str) -> tuple[str, str | None]:
    s = str(label or "").strip()
    for suffix in (
        _PD_KALININGRAD_LABEL_SUFFIX_WITH,
        _PD_KALININGRAD_LABEL_SUFFIX_WITHOUT,
    ):
        parenthesized = f"({suffix.strip()})"
        if s.endswith(parenthesized):
            base = s[: -len(parenthesized)].strip()
            return (base if base else s), suffix.strip()
        if s.endswith(suffix):
            base = s[: -len(suffix)].strip()
            return (base if base else s), suffix.strip()
    return s, None


def _pd_strip_catalog_annotation_parentheticals(label: str) -> str:
    """Убрать хвостовые пометки вида «(Калин)» из подписей справочника /perimeter_variants/."""
    s = str(label or "").strip()
    while True:
        m = re.search(r"\s*\(([^()]*)\)\s*$", s)
        if not m:
            break
        inner = (m.group(1) or "").strip().casefold()
        is_catalog = (
            "калин" in inner
            or "гаэс" in inner
            or "заряд" in inner
            or inner in {"с нт", "без нт", "o-1", "о-1", "o1", "о1"}
        )
        if not is_catalog:
            break
        s = s[: m.start()].rstrip()
    return s


def _pd_strip_o1_marker_from_entity_label(label: str) -> str:
    """Убрать «O-1» / «О-1» из названия энергосистемы (метка — у кнопки «Форма О-1»)."""
    s = str(label or "").strip()
    if not s:
        return s
    for marker in ("O-1", "o-1", "O‑1", "О-1", "о-1", "О‑1"):
        s = s.replace(marker, " ")
    return " ".join(s.split())


def _pd_strip_variant_suffixes_from_label(label: str) -> tuple[str, str | None]:
    base, kal_suffix = _pd_split_kaliningrad_suffix_from_label(label)
    base = _pd_strip_catalog_annotation_parentheticals(base)
    changed = True
    while changed:
        changed = False
        for suffix in _PD_VARIANT_LABEL_STRIP_SUFFIXES:
            if base.endswith(suffix):
                base = base[: -len(suffix)].strip()
                changed = True
                break
        if not changed:
            cleaned = _pd_strip_catalog_annotation_parentheticals(base)
            if cleaned != base:
                base = cleaned
                changed = True
    return (base if base else str(label or "").strip()), kal_suffix


def _pd_normalize_perimeter_variant_code(code: str) -> str:
    return str(code or "").strip().casefold().replace("о1", "o1")


def _pd_nt_group_for_variant_code(code: str) -> str:
    """Группа НТ для кода варианта (включая o1_with_nt / o1_without_nt)."""
    normalized = _pd_normalize_perimeter_variant_code(code)
    if "without_nt" in normalized:
        return "without_nt"
    if "with_nt" in normalized:
        return "with_nt"
    return "other"


def _pd_nt_label_suffix_for_variant_code(code: str) -> str:
    s = str(code or "").strip()
    if s == CODE_WITH_NT or s.startswith(f"{CODE_WITH_NT}_"):
        return _PD_NT_LABEL_SUFFIX_WITH
    if s == CODE_WITHOUT_NT or s.startswith(f"{CODE_WITHOUT_NT}_"):
        return _PD_NT_LABEL_SUFFIX_WITHOUT
    nt_group = _pd_nt_group_for_variant_code(code)
    if nt_group == "with_nt":
        return _PD_NT_LABEL_SUFFIX_WITH
    if nt_group == "without_nt":
        return _PD_NT_LABEL_SUFFIX_WITHOUT
    nt_group = legacy_nt_group_for_perimeter_code(code)
    if nt_group == CODE_WITH_NT:
        return _PD_NT_LABEL_SUFFIX_WITH
    if nt_group == CODE_WITHOUT_NT:
        return _PD_NT_LABEL_SUFFIX_WITHOUT
    return ""


def _pd_gaes_label_suffix_for_variant_code(code: str) -> str:
    if "with_gaes" in code:
        return _PD_GAES_LABEL_SUFFIX_WITH
    if "without_gaes" in code:
        return _PD_GAES_LABEL_SUFFIX_WITHOUT
    return ""


def _pd_format_full_variant_entity_label_for_coeff(base_label: str, code: str) -> str:
    """Полная подпись варианта на coeff (с/без НТ и заряда ГАЭС), без усечения имени сущности."""
    base, _kal_suffix = _pd_strip_variant_suffixes_from_label(base_label)
    return (
        f"{base}{_pd_nt_label_suffix_for_variant_code(code)}"
        f"{_pd_gaes_label_suffix_for_variant_code(code)}"
    ).strip()


def _is_pd_centralized_zone_russia_summary_row(row: dict[str, Any]) -> bool:
    if row.get("entity_kind") == ENTITY_KIND_CENTRALIZED_ZONE:
        return True
    if row.get("demand_model_name") != CentralizedZoneDemandParameter.__name__:
        return False
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    return label_cf.startswith(CENTRALIZED_ZONE_AGGREGATE_NAME_CF)


def _is_pd_centralized_zone_russia_o1_summary_row(row: dict[str, Any]) -> bool:
    if not _is_pd_centralized_zone_russia_summary_row(row):
        return False
    code = row.get("perimeter_variant_code")
    return bool(code) and is_o1_perimeter_variant_code(code)


def _is_o1_form_summary_entity_row(row: dict[str, Any]) -> bool:
    """Строка варианта «форма О-1»: код o1_*, метка pd_ec_o1_form_row или «O-1» в названии."""
    if str(row.get("entity_kind") or "") == "chukotka_territorial_boundaries":
        return False
    if row.get("pd_ec_o1_form_row"):
        return True
    if is_o1_perimeter_variant_code(row.get("perimeter_variant_code")):
        return True
    label_cf = str(row.get("entity_label") or "").casefold()
    return any(marker in label_cf for marker in ("o-1", "о-1", "(o-1)", "(о-1)"))


def _rebuild_summary_entity_row_blocks(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Пересчитать show_entity_cell / entity_rowspan по фактическим границам блоков."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            out.append(dict(row))
            i += 1
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        j = i + 1
        while j < n:
            nr = summary_rows[j]
            if nr.get("pd_pd_aggregation_level_row"):
                break
            if nr.get("show_entity_cell"):
                break
            j += 1
        block = summary_rows[i:j]
        for k, r in enumerate(block):
            rc = dict(r)
            rc["show_entity_cell"] = k == 0
            rc["entity_rowspan"] = len(block)
            out.append(rc)
        i = j
    return out


def exclude_o1_perimeter_variant_summary_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Не показывать блоки с вариантом периметра O-1 (o1_*, «… O-1» в названии).

    Исключение: «ЦЗ России» ``o1_with_nt`` / ``o1_without_nt`` остаются на сводках
    ОЭС / ФО / ЭЗ (префикс «Сводной таблицы»).
    """
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            out.append(dict(row))
            i += 1
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        head = block[0]
        if _is_o1_form_summary_entity_row(head) and not _is_pd_centralized_zone_russia_o1_summary_row(
            head
        ):
            i += block_size
            continue
        for j, r in enumerate(block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(block)
            out.append(rc)
        i += block_size
    return out


def _pd_strip_o1_from_centralized_zone_label(label: str) -> str:
    """Убирает «O-1» / «О-1» из подписи «ЦЗ России» (метка О-1 — только в столбце варианта)."""
    s = str(label or "").strip()
    if not s.casefold().startswith(CENTRALIZED_ZONE_AGGREGATE_NAME_CF):
        return s
    base, _kal_suffix = _pd_split_kaliningrad_suffix_from_label(s)
    base_cf = base.casefold().replace(" ", "")
    # Латинская и кириллическая «О» в маркере формы О-1.
    if "o-1" in base.casefold() or "о-1" in base.casefold() or "o1" in base_cf.replace(
        "-", ""
    ).replace("о", "o"):
        for marker in ("O-1", "o-1", "O‑1", "О-1", "о-1", "О‑1"):
            base = base.replace(marker, "")
        base = " ".join(base.split())
        if not base.casefold().startswith(CENTRALIZED_ZONE_AGGREGATE_NAME_CF):
            base = CENTRALIZED_ZONE_AGGREGATE_NAME
    return base if base else CENTRALIZED_ZONE_AGGREGATE_NAME


def _pd_centralized_zone_o1_entity_display_label(full_label: str) -> str:
    """Подпись «ЦЗ России» без «O-1» и без «с/без НТ» (различие — в столбце варианта периметра)."""
    base, _kal = _pd_strip_variant_suffixes_from_label(full_label)
    return _pd_strip_o1_from_centralized_zone_label(base)


def _pd_tag_centralized_zone_o1_display_row_for_nt_toggle(
    row: dict[str, Any],
    *,
    label: str,
    pvc_row: object,
    entity_kind: str,
) -> bool:
    """«ЦЗ России» на сводке ФО: with_nt / without_nt и с/без НТ при «+ НТ» (без метки O-1)."""
    if row.get("demand_model_name") != CentralizedZoneDemandParameter.__name__:
        return False
    if entity_kind != "centralized_zone":
        return False
    if not row.get("pd_pd_centralized_zone_o1_display_row"):
        return False
    if is_o1_perimeter_variant_code(pvc_row):
        return False
    nt_group = _pd_nt_group_for_variant_code(str(pvc_row or ""))
    row["pd_pd_nt_extra_row"] = nt_group == "with_nt"
    o1_label = _pd_centralized_zone_o1_entity_display_label(label)
    row["pd_pd_entity_label_compact_nt"] = o1_label
    nt_suffix = _pd_nt_label_suffix_for_variant_code(str(pvc_row or ""))
    row["pd_pd_entity_label_nt_detail"] = f"{o1_label}{nt_suffix}".strip()
    row["entity_label"] = row["pd_pd_entity_label_nt_detail"]
    if nt_group == "without_nt":
        row["pd_pd_skip_empty_hide_row"] = True
    return True


def _centralized_zone_russia_variant_block_sort_key(
    block: list[dict[str, Any]],
) -> tuple[int, int]:
    code = str((block[0] if block else {}).get("perimeter_variant_code") or "")
    nt_group = _pd_nt_group_for_variant_code(code)
    nt_order = {"with_nt": 0, "without_nt": 1}.get(nt_group, 2)
    return (nt_order, 1 if is_o1_perimeter_variant_code(code) else 0)


def reorder_centralized_zone_russia_variant_blocks_in_summary_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    """С НТ → с НТ O-1 → без НТ → без НТ O-1 для подряд идущих блоков «ЦЗ России» (depth=0)."""
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not _is_pd_centralized_zone_russia_summary_row(row):
            i += 1
            continue
        if int(row.get("entity_depth") or 0) != 0:
            i += 1
            continue
        start = i
        segment_end = start
        while segment_end < n:
            segment_row = summary_rows[segment_end]
            if not _is_pd_centralized_zone_russia_summary_row(segment_row):
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


def _pd_strip_gaes_text_from_label_fragment(text: str) -> str:
    """Убрать «с/без заряда ГАЭС» из подписи (на сводке нагрузок ГАЭС не используется)."""
    s = str(text or "").strip()
    for suffix in (_PD_GAES_LABEL_SUFFIX_WITH, _PD_GAES_LABEL_SUFFIX_WITHOUT):
        while suffix in s:
            s = s.replace(suffix, "")
    return " ".join(s.split())


def _pd_format_oes_entity_label_for_toggle_state(
    full_label: str,
    code: str,
    *,
    nt_detail_on: bool,
) -> str:
    """Подпись «Энергосистема»: с/без НТ, без ГАЭС и без приписки из каталога вариантов."""
    base, _kal_suffix = _pd_strip_variant_suffixes_from_label(full_label)
    base = _pd_strip_gaes_text_from_label_fragment(base)
    base = _pd_strip_catalog_annotation_parentheticals(base)
    base = _pd_strip_o1_marker_from_entity_label(base)
    nt_suffix = _pd_nt_label_suffix_for_variant_code(code) if nt_detail_on else ""
    return f"{base}{nt_suffix}".strip()


def _pd_oes_entity_label_for_nt_detail_on(full_label: str, code: str) -> str:
    """Подпись в столбце «Энергосистема» при включённой кнопке «+ НТ»: с/без НТ, без ГАЭС."""
    return _pd_format_oes_entity_label_for_toggle_state(
        full_label, code, nt_detail_on=True
    )


def _pd_oes_entity_label_compact_nt_off(full_label: str, code: str) -> str:
    """Подпись в столбце «Энергосистема» при выключенной кнопке «+ НТ»: без с/без НТ и ГАЭС."""
    return _pd_format_oes_entity_label_for_toggle_state(
        full_label, code, nt_detail_on=False
    )


def _pd_perimeter_variant_code_for_entity_label_toggle(row: dict[str, Any]) -> str | None:
    """Код варианта для подписи «с/без НТ», в т.ч. если в строке только текст из справочника."""
    code = row.get("perimeter_variant_code")
    if code:
        return str(code)
    label = str(row.get("entity_label") or "").strip()
    if label in _PD_OES_NT_EXTRA_ENTITY_LABELS:
        return CODE_WITH_NT
    if label in _PD_OES_NT_COMPACT_ENTITY_LABELS:
        return CODE_WITHOUT_NT
    return None


def _pd_oes_apply_entity_label_toggle_variants(row: dict[str, Any]) -> None:
    if not row.get("show_entity_cell"):
        return
    code_s = _pd_perimeter_variant_code_for_entity_label_toggle(row)
    if not code_s:
        return
    full = str(row.get("entity_label") or "").strip()
    if not full:
        return
    if (
        row.get("demand_model_name") == CentralizedZoneDemandParameter.__name__
        and str(row.get("entity_kind") or "") == "centralized_zone"
    ):
        full = _pd_strip_o1_from_centralized_zone_label(full)
    row["pd_pd_entity_label_nt_detail"] = _pd_oes_entity_label_for_nt_detail_on(
        full, code_s
    )
    row["pd_pd_entity_label_compact_nt"] = _pd_oes_entity_label_compact_nt_off(
        full, code_s
    )
    row["entity_label"] = row["pd_pd_entity_label_nt_detail"]

def _entity_row_is_nt_subtree_root(entity: SummaryEntity) -> bool:
    """Скрывать поддерево по «+ НТ» только у веток «с НТ» с территориальными потомками."""
    if not entity.children:
        return False
    if legacy_nt_group_for_perimeter_code(
        getattr(entity, "perimeter_variant_code", None)
    ) == CODE_WITH_NT:
        return True
    label = str(entity.label or "")
    if _NEW_TERRITORIES_NAME in label:
        return True
    if entity.entity_kind == "group-root" and _NEW_TERRITORIES_NAME in label:
        return True
    return False


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
        pvc_nt_group = legacy_nt_group_for_perimeter_code(pvc_row)

        if row.get("show_entity_cell"):
            while stack and d <= stack[-1]:
                stack.pop()
            if row.get("pd_pd_nt_subtree_root"):
                stack.append(d)

        in_nt_tree = bool(stack)

        if _pd_tag_centralized_zone_o1_display_row_for_nt_toggle(
            row,
            label=label,
            pvc_row=pvc_row,
            entity_kind=ek,
        ):
            pass
        elif pvc_nt_group == CODE_WITH_NT:
            row["pd_pd_nt_extra_row"] = True
        elif (
            pvc_nt_group == CODE_WITHOUT_NT
            and row.get("demand_model_name") == _EES_DEMAND_MODEL_NAME
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = EES_RUSSIA_AGGREGATE_NAME
        elif (
            pvc_nt_group == CODE_WITHOUT_NT
            and row.get("demand_model_name") == _EES_RUSSIA_DEMAND_MODEL_NAME
            and ek in ("oes_top_aggregate", "group-root")
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = EES_UNIFIED_REF_NAME
        elif pvc_nt_group == CODE_WITHOUT_NT and label.startswith("Россия"):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = "Россия"
        elif (
            pvc_nt_group == CODE_WITHOUT_NT
            and row.get("demand_model_name") == CentralizedZoneDemandParameter.__name__
            and ek == "centralized_zone"
            and not is_o1_perimeter_variant_code(pvc_row)
        ):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = CENTRALIZED_ZONE_AGGREGATE_NAME
        elif (
            row.get("demand_model_name") == CentralizedZoneDemandParameter.__name__
            and ek == "centralized_zone"
            and is_o1_perimeter_variant_code(pvc_row)
        ):
            # Подписи: «ЦЗ России с/без НТ»; «О-1 …» только в столбце варианта периметра.
            nt_group = _pd_nt_group_for_variant_code(str(pvc_row or ""))
            row["pd_pd_nt_extra_row"] = nt_group == "with_nt"
            cz_base = CENTRALIZED_ZONE_AGGREGATE_NAME
            nt_suffix = _pd_nt_label_suffix_for_variant_code(str(pvc_row or ""))
            row["pd_pd_entity_label_compact_nt"] = cz_base
            row["pd_pd_entity_label_nt_detail"] = f"{cz_base}{nt_suffix}".strip()
            row["entity_label"] = row["pd_pd_entity_label_nt_detail"]
            if nt_group == "without_nt":
                row["pd_pd_skip_empty_hide_row"] = True
        elif pvc_nt_group == CODE_WITHOUT_NT and label.startswith("ЕЭС России"):
            row["pd_pd_nt_extra_row"] = False
            row["pd_pd_entity_label_compact_nt"] = "ЕЭС России"
        elif (
            pvc_nt_group == CODE_WITHOUT_NT
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

        if row.get("show_entity_cell"):
            if (
                not _is_pd_centralized_zone_russia_o1_summary_row(row)
                and not row.get("pd_pd_centralized_zone_o1_display_row")
            ):
                _pd_oes_apply_entity_label_toggle_variants(row)

        # Строки по привязке /perimeter_variants/ всегда в core: пустые блоки для ввода данных.
        if row.get("pd_pd_summary_perimeter_variant_row"):
            if (
                _is_pd_centralized_zone_russia_o1_summary_row(row)
                or row.get("pd_pd_centralized_zone_o1_display_row")
            ):
                pass
            elif _pd_nt_group_for_variant_code(str(pvc_row or "")) == "with_nt":
                row["pd_pd_nt_extra_row"] = True
            elif _pd_nt_group_for_variant_code(str(pvc_row or "")) == "without_nt":
                row["pd_pd_nt_extra_row"] = False
            elif pvc_nt_group != CODE_WITH_NT:
                row["pd_pd_nt_extra_row"] = False


def tag_power_demand_oes_summary_rows_for_nt_toggle(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Обратная совместимость: см. :func:`tag_power_demand_summary_rows_for_nt_toggle`."""
    tag_power_demand_summary_rows_for_nt_toggle(summary_rows)


def tag_power_demand_coeff_summary_rows_without_gaes_entity_labels(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Coeff-страницы: полные подписи вариантов ``*_without_gaes`` (столбца периметра нет)."""
    for row in summary_rows:
        if not row.get("show_entity_cell"):
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if "without_gaes" not in code:
            continue
        base = str(row.get("entity_label") or "").strip()
        if not base:
            continue
        if (
            row.get("demand_model_name") == CentralizedZoneDemandParameter.__name__
            and str(row.get("entity_kind") or "") == "centralized_zone"
        ):
            base = _pd_strip_o1_from_centralized_zone_label(base)
        full = _pd_format_full_variant_entity_label_for_coeff(base, code)
        row["entity_label"] = full
        row["pd_pd_entity_label_nt_detail"] = full
        row["pd_pd_entity_label_compact_nt"] = full


def _pd_summary_row_allows_perimeter_variant_select(row: dict[str, Any]) -> bool:
    """Строка блока сущности, для которой в сводке можно менять perimeter_variant_code."""
    if not row.get("show_entity_cell"):
        return False
    dm_name = str(row.get("demand_model_name") or "").strip()
    if not dm_name:
        return False
    if row.get("pd_pd_verify_for_row"):
        return False
    if row.get("pd_pd_aggregation_level_row"):
        return False
    try:
        model_cls = dps._summary_demand_model_class(dm_name)
    except ValueError:
        return False
    if not model_supports_perimeter_variant(model_cls):
        return False
    options = row.get("perimeter_variant_options") or []
    if len(options) >= 2:
        return True
    has_code = bool(str(row.get("perimeter_variant_code") or "").strip())
    if has_code or len(options) >= 1:
        return True
    return bool(row.get("pd_ec_perimeter_entity_kind"))


def tag_power_demand_summary_rows_perimeter_variant_labels(
    summary_rows: list[dict[str, Any]],
    *,
    oes_summary: bool = False,
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
                if not model_supports_perimeter_variant(model_cls):
                    code = None
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
        if row.get("show_entity_cell") and pe_kind:
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
        elif row.get("show_entity_cell"):
            row["perimeter_variant_options"] = []
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
        else:
            row["perimeter_variant_label"] = (
                perimeter_variant_display_label_for_entity(code, pe_kind, pe_name)
                if code
                else ""
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
        row["show_perimeter_variant_select"] = _pd_summary_row_allows_perimeter_variant_select(
            row
        )


def _pd_summary_row_skips_perimeter_variant_year_bounds(row: dict[str, Any]) -> bool:
    return bool(row.get("pd_pd_skip_perimeter_variant_year_bounds"))


def _formula_year_applies_to_row_perimeter_variant(row: dict[str, Any], year: int) -> bool:
    """Формулы считаются только в интервале «Год с»/«Год по» варианта периметра.

    Исключение: «Первая синхронная зона» — формулы пишутся по всем годам; «Год с»
    ограничивает только вычитание Калининграда (``_apply_first_sa_kaliningrad_es_subtract_from_year``).

    Исключение: «ОЭС Юга с НТ» и «Южный ФО с НТ» — без ограничения «с 2023»; пустота
    ячейки задаётся наличием ненулевой суммы по субъектам НТ.

    В отличие от ``_year_applies_to_pd_summary_row_perimeter_variant``, не учитывает
    ``pd_pd_skip_perimeter_variant_year_bounds`` (на /summary/oes|fo|ez и coeff ввод по
    годам не ограничен, но формулы по-прежнему только в периоде варианта).
    """
    if _is_first_synchronous_area_summary_row(row):
        return True
    if _pd_south_with_nt_formula_ignores_perimeter_year_bounds(row):
        return True
    code = row.get("perimeter_variant_code")
    if code:
        fy, ty = perimeter_variant_year_bounds_for_code(str(code))
    elif _is_kaliningrad_sync_area_summary_row(row):
        fy, ty = kaliningrad_sync_area_year_bounds()
    else:
        return True
    if fy is not None and int(year) < int(fy):
        return False
    if ty is not None and int(year) > int(ty):
        return False
    return True


def _pd_south_with_nt_formula_ignores_perimeter_year_bounds(row: dict[str, Any]) -> bool:
    """ОЭС Юга / Южный ФО с НТ: формулы не режем по «Год с» варианта (раньше 2023)."""
    if not _perimeter_variant_codes_match_nt_target(
        row.get("perimeter_variant_code"), CODE_WITH_NT
    ):
        return False
    dm = row.get("demand_model_name")
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    if dm == UnionEnergySystemDemandParameter.__name__:
        return "юга" in label_cf
    if dm == FederalDistrictDemandParameter.__name__:
        if "южн" in label_cf:
            return True
        south_fd, _ = _south_federal_district_for_nt_attachment()
        if south_fd is None:
            return False
        raw_fid = row.get("id_federal_district")
        if raw_fid is None:
            return False
        try:
            return int(raw_fid) == int(south_fd.id)
        except (TypeError, ValueError):
            return False
    return False


def _year_applies_to_pd_summary_row_perimeter_variant(row: dict[str, Any], year: int) -> bool:
    if _pd_summary_row_skips_perimeter_variant_year_bounds(row):
        return True
    return _formula_year_applies_to_row_perimeter_variant(row, year)


def _pd_should_apply_formula_for_year(
    row: dict[str, Any],
    year: int,
    year_included: Callable[[int], bool] | None = None,
) -> bool:
    """Нужно ли писать результат формулы в ячейку года (с учётом year_included и периметра)."""
    if year_included is not None and not year_included(int(year)):
        return False
    return _formula_year_applies_to_row_perimeter_variant(row, int(year))


def mask_power_demand_summary_rows_perimeter_variant_year_display(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    unrestricted_perimeter_variant_input: bool = False,
) -> None:
    """Скрыть значения и id строк вне периода «Год с» / «Год по» варианта периметра.

    ``unrestricted_perimeter_variant_input``: на /summary/oes|fo|ez|coeff не ограничивать
    ввод для строк с вариантом периметра, отличным от «не указано». Формулы при этом
    по-прежнему считаются только в интервале «Год с»/«Год по» (см.
    ``_pd_should_apply_formula_for_year`` / ``_formula_year_applies_to_row_perimeter_variant``).
    Границы «Год с»/«Год по» на строке сохраняются и при skip — для формул и live JS.
    """
    if not years:
        return
    if unrestricted_perimeter_variant_input:
        for row in summary_rows:
            code = str(row.get("perimeter_variant_code") or "").strip()
            if not code:
                continue
            if _is_kaliningrad_sync_area_summary_row(row):
                continue
            row["pd_pd_skip_perimeter_variant_year_bounds"] = True
            fy, ty = perimeter_variant_year_bounds_for_code(code)
            row["perimeter_variant_from_year"] = fy
            row["perimeter_variant_to_year"] = ty
    n = len(years)
    for row in summary_rows:
        if _pd_summary_row_skips_perimeter_variant_year_bounds(row):
            continue
        code = row.get("perimeter_variant_code")
        if code:
            fy, ty = perimeter_variant_year_bounds_for_code(str(code))
            if (
                fy is None
                and ty is None
                and _is_kaliningrad_sync_area_summary_row(row)
            ):
                fy, ty = kaliningrad_sync_area_year_bounds()
        elif _is_kaliningrad_sync_area_summary_row(row):
            fy, ty = kaliningrad_sync_area_year_bounds()
        else:
            continue
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
            if _year_applies_to_pd_summary_row_perimeter_variant(row, int(yr)):
                continue
            yv[ix] = "—"
            tt[ix] = ""
            rids[ix] = None
        row["year_values"] = yv
        row["year_numeric_tooltips"] = tt
        row["year_row_ids"] = rids


def _is_sakha_yakutia_regional_energy_system_name(name: object) -> bool:
    normalized = str(name or "").casefold().replace("ё", "е")
    return all(marker in normalized for marker in _SAKHA_YAKUTIA_RES_NAME_MARKERS_CF)


def _load_tites_sakha_yakutia_extra_energy_units() -> list[EnergyUnit]:
    """Западный и Центральный энергорайоны ЭС Республики Саха (Якутия)."""
    query = EnergyUnit.query.options(selectinload(EnergyUnit.regional_energy_system))
    query = dps.filter_parents_by_version(query, EnergyUnit)
    matched: dict[str, EnergyUnit] = {}
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        base_label = str(getattr(energy_unit, "name", None) or "").strip().casefold()
        if base_label not in _TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_CF:
            continue
        if base_label in matched:
            continue
        res = getattr(energy_unit, "regional_energy_system", None)
        if not _is_sakha_yakutia_regional_energy_system_name(getattr(res, "name", None)):
            continue
        matched[base_label] = energy_unit
    return [
        matched[label]
        for label in _TITES_SAKHA_YAKUTIA_EXTRA_EU_BASE_LABELS_ORDERED
        if label in matched
    ]


@lru_cache(maxsize=1)
def _tites_sakha_yakutia_extra_energy_unit_ids() -> frozenset[int]:
    return frozenset(
        int(energy_unit.id)
        for energy_unit in _load_tites_sakha_yakutia_extra_energy_units()
        if getattr(energy_unit, "id", None) is not None
    )


def _build_tites_sakha_yakutia_extra_energy_unit_entities() -> list[SummaryEntity]:
    """Две строки под ТИТЭС (без РЭС): Западный и Центральный энергорайоны Саха (Якутия)."""
    out: list[SummaryEntity] = []
    for energy_unit in _load_tites_sakha_yakutia_extra_energy_units():
        entities = _build_energy_unit_entities(
            [energy_unit],
            depth=1,
            parameters=PARAMETERS_TITES_OES_SUMMARY,
        )
        for entity in entities:
            out.append(
                replace(
                    entity,
                    entity_kind=_SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
                    sakha_yakutia_tites_through_year_row=True,
                    id_union_energy_system=None,
                    id_regional_energy_system=None,
                    id_regional_district=None,
                )
            )
    return out


def _clear_summary_row_years_where(
    row: dict[str, Any],
    years: list[int],
    *,
    clear_year: Callable[[int], bool],
) -> None:
    n = len(years)
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
        if not clear_year(int(yr)):
            continue
        yv[ix] = "—"
        tt[ix] = ""
        rids[ix] = None
    row["year_values"] = yv
    row["year_numeric_tooltips"] = tt
    row["year_row_ids"] = rids


def mask_sakha_yakutia_tites_oes_east_year_membership(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """Западный/Центральный Саха: ≤2018 только в строках под ТИТЭС, ≥2019 — под ОЭС Востока."""
    if not summary_rows or not years:
        return
    sakha_ids = _tites_sakha_yakutia_extra_energy_unit_ids()
    if not sakha_ids:
        return
    through_year = _TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR
    for row in summary_rows:
        eu_id = _energy_unit_id_from_flat_row(row)
        if eu_id is None or int(eu_id) not in sakha_ids:
            continue
        row["sakha_membership_through_year"] = through_year
        if row.get("pd_pd_sakha_tites_through_year_row") or str(
            row.get("entity_kind") or ""
        ) == _SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND:
            row["pd_pd_sakha_tites_through_year_row"] = True
            _clear_summary_row_years_where(
                row, years, clear_year=lambda y: y > through_year
            )
        else:
            row["pd_pd_sakha_oes_east_from_year_row"] = True
            _clear_summary_row_years_where(
                row, years, clear_year=lambda y: y <= through_year
            )


def _hide_nt_aggregation_subtree_for_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Раньше скрывал блок «Новые территории» в «Сводной таблице».

    Сейчас блок управляется только кнопкой «+ НТ» (``pd_pd_nt_extra_row``),
    в т.ч. при нажатой «Сводная таблица» — как в полном дереве ОЭС.
    """
    _ = summary_rows


def _propagate_pd_territory_compact_hide_flags(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Все строки блока сущности наследуют pd_pd_territory_compact_hide_row от заголовка."""
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        if row.get("pd_pd_territory_compact_hide_row"):
            for j in range(i, min(i + block_size, n)):
                summary_rows[j]["pd_pd_territory_compact_hide_row"] = True
        i += block_size


def _is_tites_aggregate_header_row(row: dict[str, Any]) -> bool:
    return bool(
        row.get("pd_pd_aggregation_level_row")
        and str(row.get("entity_label") or "").strip() == _TITES_AND_DZ_AGGREGATE_LABEL
    )


def _is_tites_branch_regional_energy_system_row(row: dict[str, Any]) -> bool:
    if (
        str(row.get("demand_model_name") or "").strip()
        != RegionalEnergySystemDemandParameter.__name__
    ):
        return False
    if row.get("pd_pd_decentralized_zone_mark"):
        return False
    ues_id = row.get("id_union_energy_system")
    if ues_id is None:
        return False
    return int(ues_id) in _tites_union_energy_system_ids()


def _normalized_summary_entity_label_compact_cf(label: object) -> str:
    return str(label or "").strip().casefold().replace(" ", "")


def _is_norilsk_regional_energy_system_label(label: object) -> bool:
    return _normalized_summary_entity_label_compact_cf(label) == _NORILSK_RES_LABEL_CF


def _is_taimyr_norilsk_energy_unit_label(label: object) -> bool:
    return (
        _normalized_summary_entity_label_compact_cf(label) == _TAIMYR_NORILSK_EU_LABEL_CF
    )


def _apply_tites_subtree_territory_compact_rules(
    summary_rows: list[dict[str, Any]],
) -> None:
    """В «Сводной таблице»: блок ТИТЭС — «ТИТЭС» + РЭС Востока и энергорайон Таймыр/Норильск."""
    ues_mn = UnionEnergySystemDemandParameter.__name__
    res_mn = RegionalEnergySystemDemandParameter.__name__
    rd_mn = RegionalDistrictDemandParameter.__name__
    eu_mn = EnergyUnitDemandParameter.__name__

    i = 0
    n = len(summary_rows)
    while i < n:
        if not _is_tites_aggregate_header_row(summary_rows[i]):
            i += 1
            continue

        header = summary_rows[i]
        header["pd_pd_entity_label_territory_compact"] = _TITES_COMPACT_AGGREGATE_LABEL
        base_depth = int(header.get("entity_depth", 0) or 0)

        subtree_end = i + 1
        while subtree_end < n:
            child = summary_rows[subtree_end]
            if child.get("pd_pd_aggregation_level_row"):
                if int(child.get("entity_depth", 0) or 0) <= base_depth:
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
            label = str(row.get("entity_label") or "").strip()
            res_id = row.get("id_regional_energy_system")
            in_tites_res_block = res_id is not None and int(res_id) in tites_res_ids

            if (
                in_tites_res_block
                and dm == res_mn
                and _is_norilsk_regional_energy_system_label(label)
            ):
                # Пустой РЭС Норильска скрываем; вместо него — энергорайон Таймыр/Туруханск/Норильск.
                row["pd_pd_territory_compact_hide_row"] = True
                row["pd_pd_territory_detail_row"] = True
            elif in_tites_res_block and dm == eu_mn and _is_taimyr_norilsk_energy_unit_label(
                label
            ):
                row.pop("pd_pd_territory_detail_row", None)
                row.pop("pd_pd_territory_compact_hide_row", None)
            elif in_tites_res_block and dm == res_mn:
                row.pop("pd_pd_territory_detail_row", None)
                row.pop("pd_pd_territory_compact_hide_row", None)
            elif in_tites_res_block and (
                row.get("pd_pd_chi_row") or row.get("pd_pd_ee_row")
            ):
                if _is_norilsk_regional_energy_system_label(label):
                    row["pd_pd_territory_compact_hide_row"] = True
                    row["pd_pd_territory_detail_row"] = True
                elif _is_taimyr_norilsk_energy_unit_label(label) or dm == res_mn:
                    row.pop("pd_pd_territory_detail_row", None)
                    row.pop("pd_pd_territory_compact_hide_row", None)
                else:
                    row["pd_pd_territory_detail_row"] = True
            elif row.get("pd_pd_decentralized_zone_mark") or dm == ues_mn:
                row["pd_pd_territory_compact_hide_row"] = True
                row["pd_pd_territory_detail_row"] = True
            elif dm in (eu_mn, rd_mn):
                row["pd_pd_territory_detail_row"] = True
            elif dm == res_mn:
                row["pd_pd_territory_detail_row"] = True
                row["pd_pd_territory_compact_hide_row"] = True
            elif row.get("entity_kind") == "tites_res_energy_unit_sum_check":
                row["pd_pd_territory_compact_hide_row"] = True
            elif _is_oes_summary_hidden_tites_verification_row(row):
                row["pd_pd_territory_compact_hide_row"] = True

        i = subtree_end


def tag_power_demand_summary_rows_for_territory_compact(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Метки для кнопки «Сводная таблица»: скрытие РЭС, субъектов РФ и энергорайонов.

    Блок «Новые территории» (``pd_pd_nt_extra_row``) не помечается как скрытый
    compact: его видимость задаёт только «+ НТ», в т.ч. вместе со «Сводной таблицей».
    """
    res_mn = RegionalEnergySystemDemandParameter.__name__
    rd_mn = RegionalDistrictDemandParameter.__name__
    eu_mn = EnergyUnitDemandParameter.__name__
    for row in summary_rows:
        row.pop("pd_pd_entity_label_territory_compact", None)
        row.pop("pd_pd_territory_compact_hide_row", None)
        row.pop("pd_pd_territory_detail_row", None)
        ek = str(row.get("entity_kind") or "")
        label = str(row.get("entity_label") or "").strip()
        if (
            ek == "chukotka_territorial_boundaries"
            or label == _CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL
            or label == _CHUKOTKA_RD_LABEL
        ):
            row["pd_pd_territory_compact_hide_row"] = True
        dm_l = str(row.get("demand_model_name") or "").strip()
        is_nt_block_row = bool(row.get("pd_pd_nt_extra_row")) and (
            row.get("pd_pd_aggregation_level_row")
            or label == _NEW_TERRITORIES_NAME
            or dm_l in (res_mn, rd_mn, eu_mn)
        )
        is_territory_detail = dm_l in (res_mn, rd_mn, eu_mn) and not is_nt_block_row
        row["pd_pd_territory_detail_row"] = is_territory_detail
        if row.get("pd_pd_chi_row") and is_territory_detail:
            row["pd_pd_territory_compact_hide_row"] = True
        if row.get("pd_pd_ee_row") and is_territory_detail:
            row["pd_pd_territory_compact_hide_row"] = True
        if row.get("pd_pd_verify_for_row") and (
            is_territory_detail
            or ek == "chukotka_territorial_boundaries"
            or label == _CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL
        ):
            row["pd_pd_territory_compact_hide_row"] = True
    _hide_nt_aggregation_subtree_for_territory_compact(summary_rows)
    _propagate_pd_territory_compact_hide_flags(summary_rows)
    _apply_tites_subtree_territory_compact_rules(summary_rows)


def tag_power_demand_ez_summary_group_rows_skip_empty_hide(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Не скрывать заголовки энергозон кнопкой «Пустые строки».

    На сводке по энергозонам значения часто заполнены только на уровне РЭС; без метки
    блоки энергозон (и строка «ЕЭС России») исчезают при скрытии пустых строк.
    """
    if not summary_rows:
        return
    ez_dm = EnergyZoneDemandParameter.__name__
    est_dm = EnergySystemTypeDemandParameter.__name__
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        dm = row.get("demand_model_name")
        ek = str(row.get("entity_kind") or "")
        if (dm == ez_dm and ek == "group") or (
            dm == est_dm and ek in ("ees_russia", "oes_top_aggregate")
        ):
            for j in range(block_size):
                if i + j < n:
                    summary_rows[i + j]["pd_pd_skip_empty_hide_row"] = True
        i += block_size


def apply_power_demand_summary_territory_compact_export_ui(
    summary_rows: list[dict[str, Any]],
    *,
    territory_compact_on: bool,
) -> list[dict[str, Any]]:
    """Выгрузка Excel: те же строки, что на экране для режима «Сводная таблица»."""
    if not territory_compact_on:
        return [
            row
            for row in summary_rows
            if not row.get("pd_pd_summary_table_only_row")
        ]
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        # Блок «Новые территории» уже отфильтрован флагом export_nt_detail.
        if row.get("pd_pd_nt_extra_row"):
            rc = dict(row)
            out.append(rc)
            continue
        if row.get("pd_pd_territory_detail_row") or row.get(
            "pd_pd_territory_compact_hide_row"
        ):
            continue
        rc = dict(row)
        compact_label = row.get("pd_pd_entity_label_territory_compact")
        if compact_label:
            rc["entity_label"] = compact_label
        out.append(rc)
    return out


def apply_power_demand_summary_nt_export_ui(
    summary_rows: list[dict[str, Any]],
    *,
    nt_detail_on: bool,
) -> list[dict[str, Any]]:
    """Выгрузка Excel: скрыть «с НТ» и выставить подписи режима «+ НТ».

    При совместном использовании со «Сводной таблицей» финальные подписи
    лучше проставлять через :func:`apply_power_demand_summary_screen_entity_labels`.
    """
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        if not nt_detail_on and row.get("pd_pd_nt_extra_row"):
            continue
        rc = dict(row)
        rc["entity_label"] = resolve_power_demand_summary_display_entity_label(
            row,
            nt_detail_on=nt_detail_on,
            territory_compact_on=False,
        )
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


def _power_demand_summary_export_entity_key(row: dict[str, Any]) -> str:
    """Стабильный ключ блока энергосистемы для сопоставления с подписью с экрана."""

    def _s(value: Any) -> str:
        return "" if value is None else str(value)

    return "\x1f".join(
        [
            _s(row.get("demand_model_name")),
            _s(row.get("parent_fk_column")),
            _s(row.get("parent_id")),
            _s(row.get("id_union_energy_system")),
            _s(row.get("id_regional_energy_system")),
            _s(row.get("id_regional_district")),
            _s(row.get("id_energy_unit")),
            _s(row.get("id_synchronous_area")),
            _s(row.get("id_energy_zone")),
            _s(row.get("perimeter_variant_code")),
            "1" if row.get("pd_pd_nt_extra_row") else "0",
            "1" if row.get("pd_pd_aggregation_level_row") else "0",
        ]
    )


def resolve_power_demand_summary_display_entity_label(
    row: dict[str, Any],
    *,
    nt_detail_on: bool,
    territory_compact_on: bool,
) -> str:
    """Подпись столбца «Энергосистема» как на экране (кнопки «Сводная таблица» / «+ НТ»)."""
    terr = row.get("pd_pd_entity_label_territory_compact")
    if territory_compact_on and terr:
        return str(terr)
    if nt_detail_on:
        nt_detail = row.get("pd_pd_entity_label_nt_detail")
        if nt_detail:
            return str(nt_detail)
        return str(row.get("entity_label") or "")
    compact = row.get("pd_pd_entity_label_compact_nt")
    if compact:
        return str(compact)
    code = _pd_perimeter_variant_code_for_entity_label_toggle(row)
    full = str(
        row.get("pd_pd_entity_label_nt_detail") or row.get("entity_label") or ""
    ).strip()
    if code and full:
        return _pd_oes_entity_label_compact_nt_off(full, code)
    return str(row.get("entity_label") or "")


def apply_power_demand_summary_screen_entity_labels(
    summary_rows: list[dict[str, Any]],
    *,
    nt_detail_on: bool,
    territory_compact_on: bool,
) -> list[dict[str, Any]]:
    """Проставить entity_label так же, как syncPdPdNtAdjustedEntityLabels на странице."""
    out: list[dict[str, Any]] = []
    for row in summary_rows:
        rc = dict(row)
        rc["entity_label"] = resolve_power_demand_summary_display_entity_label(
            row,
            nt_detail_on=nt_detail_on,
            territory_compact_on=territory_compact_on,
        )
        out.append(rc)
    return out


def apply_power_demand_summary_export_entity_label_overrides(
    summary_rows: list[dict[str, Any]],
    overrides: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """Подставить подписи, собранные с экрана (DOM), по ключу блока энергосистемы."""
    if not overrides:
        return list(summary_rows or [])
    out: list[dict[str, Any]] = []
    for row in summary_rows or []:
        rc = dict(row)
        key = _power_demand_summary_export_entity_key(row)
        label = overrides.get(key)
        if label:
            rc["entity_label"] = label
        out.append(rc)
    return out


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


def parse_power_demand_export_hist(*, default: bool = False) -> bool:
    """GET export_hist=1 — столбец «Ист. макс.» как при нажатой кнопке на экране."""
    from flask import request

    raw = request.args.get("export_hist")
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def parse_power_demand_export_hide_empty(*, default: bool = False) -> bool:
    """GET export_hide_empty=1 — скрыть пустые блоки энергосистем (как без «Пустые строки»)."""
    from flask import request

    raw = request.args.get("export_hide_empty")
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _export_row_skipped_in_empty_entity_check(row: dict[str, Any]) -> bool:
    """Как на экране: ЭЭ / ЧЧИ / расчётные / проверка не участвуют в оценке «пустого» блока."""
    if row.get("pd_pd_aggregation_level_row"):
        return True
    if row.get("pd_pd_verify_for_row") or row.get("pd_pd_ee_row") or row.get("pd_pd_chi_row"):
        return True
    pk = str(row.get("parameter_key") or "")
    if pk.startswith("verify_for_"):
        return True
    if pk.startswith("calculated_") or pk.startswith("cz_calculated_"):
        return True
    if pk == "energy_consumption_mln_kvt_ch" or pk == "peak_max_power_usage_hours":
        return True
    if pk.startswith("peak_combined_on_") and pk.endswith("_usage_hours"):
        return True
    return False


def _export_cell_has_meaningful_value(value: Any, *, parameter_key: str) -> bool:
    if value in (None, ""):
        return False
    s = str(value).strip()
    if s in ("", "—", "-"):
        return False
    if parameter_key == "peak_datetime":
        return True
    parsed = _parse_summary_cell_float(s)
    if parsed is None:
        return True
    return parsed != 0.0


def _export_param_row_is_empty(row: dict[str, Any]) -> bool:
    pk = str(row.get("parameter_key") or "")
    if _export_cell_has_meaningful_value(row.get("hist_value"), parameter_key=pk):
        return False
    for cell in row.get("year_values") or []:
        if _export_cell_has_meaningful_value(cell, parameter_key=pk):
            return False
    return True


def _export_entity_block_is_empty(block: list[dict[str, Any]]) -> bool:
    for row in block:
        if _export_row_skipped_in_empty_entity_check(row):
            continue
        if not _export_param_row_is_empty(row):
            return False
    return True


def filter_summary_rows_hide_empty_entity_blocks(
    summary_rows: list[dict[str, Any]],
    *,
    hide_empty: bool,
) -> list[dict[str, Any]]:
    """Убрать блоки энергосистем без значимых значений (кнопка «Пустые строки» выкл.)."""
    if not hide_empty or not summary_rows:
        return list(summary_rows or [])
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            out.append(dict(row))
            i += 1
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        block = summary_rows[i : i + block_size]
        skip_hide = any(r.get("pd_pd_skip_empty_hide_row") for r in block)
        if hide_empty and _export_entity_block_is_empty(block) and not skip_hide:
            i += block_size
            continue
        for j, r in enumerate(block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(block)
            out.append(rc)
        i += block_size
    return out


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
DEFAULT_COEFF_K_ROUNDING_DIGITS = 3


def _round_coeff_k_calc(value: float) -> float:
    """Ограничение точности при расчёте k = значение / макс. мощность (сводки «Коэффициенты…»)."""
    if not math.isfinite(value):
        return value
    # Через строку toFixed-эквивалент, чтобы не оставлять binary float (0.999 → 0.998999999…).
    return float(f"{value:.{COEFF_K_CALC_DECIMAL_PLACES}f}")


def _format_coeff_k_numeric(value: Any, digits: int) -> str:
    """Отображение k: фиксированное число знаков (как «Округл (k)» / JS formatCoeffK), без обрезки нулей."""
    if digits == 0:
        # «Не округлять» — не более 6 знаков после запятой (как Numeric(25, 6) / расчёт).
        return _dash(
            format_decimal_trim_for_display(value, digits=COEFF_K_CALC_DECIMAL_PLACES)
        )
    # 1–3 знака или целое (−1): без strip хвостовых нулей (1 → 1,000 при 3 знаках).
    return _dash(format_decimal_for_display(value, digits=digits))


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


def _summary_row_year_float(
    row: dict[str, Any] | None, year_index: int
) -> float | None:
    """Число года для агрегатов/проверок: полный title, иначе отображаемое year_values.

    При округлении «до целого» сумма по уже округлённым year_values РЭС расходится
    с максимумом ФО/ОЭС (например Сибирский ФО 2022–2024).
    """
    if row is None:
        return None
    tooltips = row.get("year_numeric_tooltips") or []
    if year_index < len(tooltips):
        parsed_tt = _parse_summary_cell_float(tooltips[year_index])
        if parsed_tt is not None:
            return float(parsed_tt)
    yvals = row.get("year_values") or []
    parsed = _parse_summary_cell_float(
        yvals[year_index] if year_index < len(yvals) else None
    )
    return float(parsed) if parsed is not None else None


def _ues_row_uses_standard_oes_aggregation(row: dict[str, Any]) -> bool:
    """Одна строка ОЭС в суммах/расчётах по РЭС (для вариантов — только территориальный базовый)."""
    code = row.get("perimeter_variant_code")
    if code is None:
        return True
    return str(code) == CODE_WITHOUT_NT


def _perimeter_variant_codes_match_nt_target(
    row_code: str | None,
    target_code: str | None,
) -> bool:
    """Совпадение кодов варианта периметра с целевым (legacy-группа с/без НТ или точное совпадение)."""
    if target_code is None:
        return row_code is None
    if row_code is None:
        return False
    target_s = str(target_code)
    row_s = str(row_code)
    target_group = legacy_nt_group_for_perimeter_code(target_s)
    row_group = legacy_nt_group_for_perimeter_code(row_s)
    if target_group is not None and row_group is not None:
        return target_group == row_group
    if target_group == CODE_WITH_NT and row_s.startswith("with_nt"):
        return True
    if target_group == CODE_WITHOUT_NT and row_s.startswith("without_nt"):
        return True
    if row_group == CODE_WITH_NT and target_s.startswith("with_nt"):
        return True
    if row_group == CODE_WITHOUT_NT and target_s.startswith("without_nt"):
        return True
    return row_s == target_s


def _ues_ids_with_explicit_nt_variant_in_summary(
    summary_rows: list[dict[str, Any]],
    nt_group: str,
) -> frozenset[int]:
    """ОЭС, у которых в сводке есть строка с явным вариантом периметра из legacy-группы nt_group."""
    ues_dm = UnionEnergySystemDemandParameter.__name__
    out: set[int] = set()
    for r in summary_rows:
        if r.get("demand_model_name") != ues_dm:
            continue
        row_code = r.get("perimeter_variant_code")
        if row_code is None:
            continue
        if not _perimeter_variant_codes_match_nt_target(str(row_code), nt_group):
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is not None:
            out.add(int(uid))
    return frozenset(out)


def _ees_russia_aggregate_ues_sum_perimeter_variant(
    ees_russia_perimeter_variant: str | None,
) -> str | None:
    """Вариант ОЭС для суммы в «ЕЭС России».

    Для «с НТ» база — те же ОЭС, что у «без НТ»; вклад НТ добавляется отдельно
    (:func:`_ees_russia_year_sums_with_nt_addon`), чтобы выполнялось
    «ЕЭС с НТ = ЕЭС без НТ + ΣНТ».
    """
    if ees_russia_perimeter_variant is None:
        return None
    if (
        legacy_nt_group_for_perimeter_code(str(ees_russia_perimeter_variant))
        == CODE_WITH_NT
    ):
        return CODE_WITHOUT_NT
    return ees_russia_perimeter_variant


def _make_ues_perimeter_filter_for_ees_russia_aggregate(
    summary_rows: list[dict[str, Any]],
    ees_russia_perimeter_variant: str | None,
) -> Callable[[dict[str, Any]], bool]:
    """Фильтр ОЭС для агрегата «ЕЭС России»: явный вариант или базовая строка без варианта."""
    target = _ees_russia_aggregate_ues_sum_perimeter_variant(
        ees_russia_perimeter_variant
    )
    target_s = str(target) if target else None
    explicit: frozenset[int] = frozenset()
    target_group = legacy_nt_group_for_perimeter_code(target_s) if target_s else None
    if target_group == CODE_WITH_NT:
        explicit = _ues_ids_with_explicit_nt_variant_in_summary(
            summary_rows, CODE_WITH_NT
        )
    elif target_group == CODE_WITHOUT_NT:
        explicit = _ues_ids_with_explicit_nt_variant_in_summary(
            summary_rows, CODE_WITHOUT_NT
        )

    def _filter(row: dict[str, Any]) -> bool:
        return _ues_row_included_for_ees_russia_aggregate_variant(
            row,
            target,
            ues_ids_with_explicit_nt_variant=explicit,
        )

    return _filter


def _ues_row_included_for_ees_russia_aggregate_variant(
    row: dict[str, Any],
    ees_russia_perimeter_variant: str | None,
    *,
    ues_ids_with_explicit_nt_variant: frozenset[int] | None = None,
) -> bool:
    """Строка ОЭС для «Расчетный максимум потребления мощности ЕЭС России»: вариант ОЭС согласован с агрегатом с/без НТ."""
    row_code = row.get("perimeter_variant_code")
    target = ees_russia_perimeter_variant
    if not target:
        return row_code is None
    if _perimeter_variant_codes_match_nt_target(row_code, target):
        return True
    if row_code is not None:
        return False
    target_group = legacy_nt_group_for_perimeter_code(str(target))
    if target_group not in (CODE_WITH_NT, CODE_WITHOUT_NT):
        return False
    uid = _union_energy_system_id_from_flat_row(row)
    if uid is None:
        return True
    if ues_ids_with_explicit_nt_variant is not None:
        return int(uid) not in ues_ids_with_explicit_nt_variant
    return False


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
        for j in range(n_y):
            if year_included is not None and not year_included(years[j]):
                continue
            add = _summary_row_year_float(r, j)
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
    add = _summary_row_year_float(res_row, year_index)
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


def _sum_base_and_nt_if_nt_nonzero(
    base: float | None,
    nt_sum: float | None,
) -> float | None:
    """ОЭС Юга / Южный ФО с НТ: base + НТ только если сумма по субъектам НТ ≠ 0; иначе пусто."""
    if nt_sum is None:
        return None
    try:
        if float(nt_sum) == 0.0:
            return None
    except (TypeError, ValueError):
        return None
    return _sum_optional_floats(base, nt_sum)


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
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


def _aggregate_nt_subjects_combined_on_oes_mw_sum_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    south_ues_id: int,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ОЭС» по ФО «Новые территории»."""
    return _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
        summary_rows,
        years,
        parameter_key="combined_on_oes",
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС» по ФО «Новые территории»."""
    return _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
        summary_rows,
        years,
        parameter_key="combined_on_ees",
        south_ues_id=south_ues_id,
        year_included=year_included,
    )


def _nt_combined_on_oes_year_sums_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма combined_on_oes субъектов «Новые территории» под ОЭС Юга (как для «ОЭС Юга с НТ»)."""
    out: list[float | None] = []
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    for south_id in south_ids:
        part = _aggregate_nt_subjects_combined_on_oes_mw_sum_for_south_ues(
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
        if not _perimeter_variant_codes_match_nt_target(
            r.get("perimeter_variant_code"), CODE_WITH_NT
        ):
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


def _pd_summary_row_is_south_ues_without_nt_manual_row(row: dict[str, Any]) -> bool:
    """ОЭС Юга «без НТ»: значения из БД, без перезаписи расчётными суммами по РЭС."""
    if row.get("demand_model_name") != UnionEnergySystemDemandParameter.__name__:
        return False
    if not _perimeter_variant_codes_match_nt_target(
        row.get("perimeter_variant_code"), CODE_WITHOUT_NT
    ):
        return False
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    if "юга" not in label_cf:
        return False
    if " с нт" in f" {label_cf} ":
        return False
    return True


def tag_power_demand_south_ues_without_nt_manual_rows(
    summary_rows: list[dict[str, Any]],
) -> None:
    for row in summary_rows:
        if _pd_summary_row_is_south_ues_without_nt_manual_row(row):
            row["pd_pd_south_ues_without_nt_manual_row"] = True


def _south_ues_perimeter_variant_row(
    row: dict[str, Any],
    south_ids: frozenset[int],
    nt_group: str,
) -> bool:
    label_cf = str(row.get("entity_label") or "").strip().casefold()
    if "юга" not in label_cf:
        return False
    uid = _union_energy_system_id_from_flat_row(row)
    if uid is None or int(uid) not in south_ids:
        return False
    return _perimeter_variant_codes_match_nt_target(
        row.get("perimeter_variant_code"), nt_group
    )


def _clear_south_ues_with_nt_formula_years_before(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> None:
    """ОЭС Юга с НТ: строки проверки вне периода варианта периметра — пустые.

    Расчётные показатели вне периода не затираем: остаются значения из БД (ввод на
    oes/fo/ez не ограничен «Год с»/«Год по», формулы туда не пишутся).
    """
    if not summary_rows or not years:
        return
    south_ids: set[int] = set()
    for r in summary_rows:
        if not _perimeter_variant_codes_match_nt_target(
            r.get("perimeter_variant_code"), CODE_WITH_NT
        ):
            continue
        label_cf = str(r.get("entity_label") or "").strip().casefold()
        if "юга" not in label_cf:
            continue
        uid = _union_energy_system_id_from_flat_row(r)
        if uid is not None:
            south_ids.add(int(uid))
    if not south_ids:
        return
    south_ids_frozen = frozenset(south_ids)
    verify_keys = frozenset(
        {
            "verify_for_calculated_max_power_mw",
            "verify_for_calculated_combined_on_ees_mw",
        }
    )
    n_y = len(years)
    for r in summary_rows:
        pk = str(r.get("parameter_key") or "")
        if pk not in verify_keys:
            continue
        if not _south_ues_perimeter_variant_row(r, south_ids_frozen, CODE_WITH_NT):
            continue
        yv = list(r.get("year_values") or [])
        ynt = list(r.get("year_numeric_tooltips") or [])
        while len(yv) < n_y:
            yv.append("—")
        while len(ynt) < n_y:
            ynt.append("")
        for j, y in enumerate(years):
            if _formula_year_applies_to_row_perimeter_variant(r, int(y)):
                continue
            yv[j] = "—"
            ynt[j] = ""
        r["year_values"] = yv
        r["year_numeric_tooltips"] = ynt


def enrich_south_ues_perimeter_calculated_combined_on_ees_from_res(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное совмещенное … на ЕЭС» для ОЭС Юга с/без НТ (как расчётный максимум ОЭС)."""
    if not summary_rows or not years:
        return
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    if not south_ids:
        return
    res_sums_by_union = _aggregate_res_combined_on_ees_mw_sum_by_union(
        summary_rows, years, year_included=year_included
    )
    n_y = len(years)
    combined_with_nt_by_union: dict[int, list[float | None]] = {}
    for south_id in south_ids:
        nt_year_sums = _aggregate_nt_subjects_combined_on_ees_mw_sum_for_south_ues(
            summary_rows,
            years,
            south_ues_id=south_id,
            year_included=year_included,
        )
        res_mids = res_sums_by_union.get(south_id) or [None] * n_y
        combined_with_nt_by_union[south_id] = [
            _sum_base_and_nt_if_nt_nonzero(
                res_mids[j] if j < len(res_mids) else None,
                nt_year_sums[j] if j < len(nt_year_sums) else None,
            )
            for j in range(n_y)
        ]

    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_combined_on_ees_mw",
        sums_by_union=res_sums_by_union,
        year_included=year_included,
        row_include_predicate=lambda r, ids=south_ids: _south_ues_perimeter_variant_row(
            r, ids, CODE_WITHOUT_NT
        ),
    )
    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_combined_on_ees_mw",
        sums_by_union=combined_with_nt_by_union,
        year_included=year_included,
        row_include_predicate=lambda r, ids=south_ids: _south_ues_perimeter_variant_row(
            r, ids, CODE_WITH_NT
        ),
    )


def enrich_south_ues_with_nt_calculated_max_power_from_res_and_nt_subjects(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«ОЭС Юга с НТ»: расчётный максимум = сумма по РЭС + сумма combined_on_oes субъектов НТ.

    Если сумма по субъектам «Новые территории» равна 0 или пуста — ячейка пустая.
    """
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
        nt_year_sums = _aggregate_nt_subjects_combined_on_oes_mw_sum_for_south_ues(
            summary_rows,
            years,
            south_ues_id=south_id,
            year_included=year_included,
        )
        res_mids = res_sums_by_union.get(south_id) or [None] * n_y
        combined_by_union[south_id] = [
            _sum_base_and_nt_if_nt_nonzero(
                res_mids[j] if j < len(res_mids) else None,
                nt_year_sums[j] if j < len(nt_year_sums) else None,
            )
            for j in range(n_y)
        ]

    def _south_with_nt_row(row: dict[str, Any]) -> bool:
        return _south_ues_perimeter_variant_row(row, south_ids, CODE_WITH_NT)

    _apply_ues_calculated_mw_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ues_parameter_key="calculated_max_power_mw",
        sums_by_union=res_sums_by_union,
        year_included=year_included,
        row_include_predicate=lambda r, ids=south_ids: _south_ues_perimeter_variant_row(
            r, ids, CODE_WITHOUT_NT
        ),
    )
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
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
                continue
            if _pd_summary_row_is_south_ues_without_nt_manual_row(r):
                current = yv_p[j] if j < len(yv_p) else "—"
                if str(current or "").strip() not in ("", "—", "–"):
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ФО, МВт» по строкам РЭС внутри каждого ФО."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(fid: int) -> list[float | None]:
        if fid not in out:
            out[fid] = [None] * n_y
        return out[fid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_fo"):
        # В т.ч. РЭС ветки ТИТЭС (Норильск и др.): географически в ФО — входят в максимум ФО.
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(fid)
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЦЗ России, МВт» по строкам РЭС внутри каждого ФО."""
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
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _aggregate_res_combined_on_ees_mw_sum_by_federal_district(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенное … на ЕЭС, МВт» по строкам РЭС внутри каждого ФО."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(fid: int) -> list[float | None]:
        if fid not in out:
            out[fid] = [None] * n_y
        return out[fid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ees"):
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(fid)
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
            if add is None:
                continue
            if row_tot[j] is None:
                row_tot[j] = float(add)
            else:
                row_tot[j] = float(row_tot[j]) + float(add)
    return out


def _apply_fd_parameter_from_res_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    fd_parameter_key: str,
    sums_by_federal_district: dict[int, list[float | None]],
    year_included: Callable[[int], bool] | None = None,
    use_calculated_mw_format: bool = False,
    row_include_predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    """Подставляет в строку ФО суммы по РЭС (годовые столбцы; исторический столбец очищается)."""
    n_y = len(years)
    dm_fd = FederalDistrictDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_fd:
            continue
        if r.get("parameter_key") != fd_parameter_key:
            continue
        if row_include_predicate is not None and not row_include_predicate(r):
            continue
        raw_fid = r.get("id_federal_district")
        if raw_fid is None:
            continue
        try:
            fid = int(raw_fid)
        except (TypeError, ValueError):
            continue
        mids = sums_by_federal_district.get(fid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                if use_calculated_mw_format:
                    yv_p[j] = _format_calculated_max_mw(s)
                    ynt_p[j] = _format_calculated_max_mw(s)
                else:
                    yv_p[j] = _format_numeric(s, rounding_digits)
                    ynt_p[j] = _format_full_numeric_tooltip(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_fo_summary_combined_on_ees_from_res(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Совмещенное … на ЕЭС, МВт» по ФО = сумма «Совмещенное … на ЕЭС, МВт» по РЭС данного ФО."""
    sums = _aggregate_res_combined_on_ees_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    _apply_fd_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        fd_parameter_key="combined_on_ees",
        sums_by_federal_district=sums,
        year_included=year_included,
        use_calculated_mw_format=False,
    )


def enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» по ФО = сумма «Совмещенное потребление мощности на час прохождения максимума ФО, МВт» по РЭС."""
    sums = _aggregate_res_combined_on_fo_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    _apply_fd_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        fd_parameter_key="calculated_max_power_mw",
        sums_by_federal_district=sums,
        year_included=year_included,
        use_calculated_mw_format=True,
    )


def enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    fd_parameter_key: str = "calculated_max_power_mw",
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Южный ФО с НТ»: расчётный max = сумма РЭС (как «без НТ»)
    + сумма combined_on_fo субъектов «Новые территории».

    Если сумма по субъектам НТ равна 0 или пуста — ячейка пустая.
    """
    if not summary_rows or not years:
        return
    south_fd, south_ues_id = _south_federal_district_for_nt_attachment()
    if south_fd is None:
        return
    south_fd_id = int(south_fd.id)
    n_y = len(years)

    res_sums = _aggregate_res_combined_on_fo_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    base = res_sums.get(south_fd_id) or [None] * n_y

    nt_sums: list[float | None] = [None] * n_y
    if south_ues_id is not None:
        nt_sums = _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
            summary_rows,
            years,
            parameter_key="combined_on_fo",
            south_ues_id=int(south_ues_id),
            year_included=year_included,
        )
    if all(v is None for v in nt_sums):
        demand_sums = _nt_combined_on_fo_year_sums_from_demand(years)
        nt_sums = [
            demand_sums[j] if j < len(demand_sums) else None for j in range(n_y)
        ]

    combined_by_fd = {
        south_fd_id: [
            _sum_base_and_nt_if_nt_nonzero(
                base[j] if j < len(base) else None,
                nt_sums[j] if j < len(nt_sums) else None,
            )
            for j in range(n_y)
        ]
    }

    def _south_fd_with_nt_row(row: dict[str, Any]) -> bool:
        raw_fid = row.get("id_federal_district")
        if raw_fid is None:
            return False
        try:
            if int(raw_fid) != south_fd_id:
                return False
        except (TypeError, ValueError):
            return False
        return _perimeter_variant_codes_match_nt_target(
            row.get("perimeter_variant_code"), CODE_WITH_NT
        )

    _apply_fd_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        fd_parameter_key=fd_parameter_key,
        sums_by_federal_district=combined_by_fd,
        year_included=year_included,
        use_calculated_mw_format=True,
        row_include_predicate=_south_fd_with_nt_row,
    )


def _is_far_east_federal_district_name(name: object) -> bool:
    cf = str(name or "").strip().casefold().replace("ё", "е")
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(p) :].strip()
            break
    return _FAR_EAST_FEDERAL_DISTRICT_NAME_MARKER_CF in cf


@lru_cache(maxsize=1)
def _far_east_federal_district_id() -> int | None:
    query = FederalDistrict.query
    query = dps.filter_parents_by_version(query, FederalDistrict)
    for fd in query.all():
        if not _is_valid_named_item(fd):
            continue
        if _is_far_east_federal_district_name(getattr(fd, "name", None)):
            return int(fd.id)
    return None


@lru_cache(maxsize=1)
def _far_east_fd_formula_energy_unit_ids() -> frozenset[int]:
    """Id энергорайонов формулы Дальневосточного ФО (ТИТЭС ДВ без Норильска)."""
    query = EnergyUnit.query
    query = dps.filter_parents_by_version(query, EnergyUnit)
    matched: set[int] = set()
    for energy_unit in query.all():
        if not _is_valid_named_item(energy_unit):
            continue
        name = getattr(energy_unit, "name", None)
        for spec in _FAR_EAST_FD_FORMULA_EU_NAME_SPECS:
            if _energy_unit_name_matches_spec(name, spec):
                matched.add(int(energy_unit.id))
                break
    return frozenset(matched)


def _sum_far_east_fd_formula_energy_units_max_power(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма max_power энергорайонов формулы Дальневосточного ФО (из строк сводки)."""
    n_y = len(years)
    eu_ids = _far_east_fd_formula_energy_unit_ids()
    if not eu_ids:
        return [None] * n_y

    eu_dm = EnergyUnitDemandParameter.__name__
    year_tot: list[float | None] = [None] * n_y
    seen_eu_year: set[tuple[int, int]] = set()
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
            key = (int(eu_id), int(y))
            if key in seen_eu_year:
                continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            seen_eu_year.add(key)
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


def _sum_far_east_fd_formula_energy_units_max_power_from_demand(
    years: list[int],
) -> list[float | None]:
    """Сумма max_power энергорайонов формулы Дальневосточного ФО из таблиц нагрузки."""
    n_y = len(years)
    eu_ids = _far_east_fd_formula_energy_unit_ids()
    if not eu_ids:
        return [None] * n_y
    o1_code = resolve_catalog_o1_perimeter_variant_code()
    year_tot: list[float | None] = [None] * n_y
    for eu_id in sorted(eu_ids):
        rows = dps.get_demand_rows(
            EnergyUnitDemandParameter,
            "id_energy_unit",
            eu_id,
            perimeter_variant_code=o1_code,
        )
        if not rows or all(
            getattr(r, "max_power_consumption_mw", None) is None for r in rows
        ):
            rows = dps.get_demand_rows(
                EnergyUnitDemandParameter,
                "id_energy_unit",
                eu_id,
                perimeter_variant_code=None,
            )
        part = _max_power_year_floats_from_demand_rows(rows, years)
        year_tot = _merge_optional_float_year_lists(year_tot, part)
    return year_tot


def enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    fd_parameter_key: str = "calculated_max_power_mw",
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """Дальневосточный ФО: расчётный max = сумма РЭС (combined_on_fo)
    + сумма max_power энергорайонов формулы (Сахалин, Камчатка, Чукотка, Магадан).
    """
    if not summary_rows or not years:
        return
    far_east_fd_id = _far_east_federal_district_id()
    if far_east_fd_id is None:
        # Fallback: определить по подписи строк сводки (тесты без БД).
        for r in summary_rows:
            if r.get("demand_model_name") != FederalDistrictDemandParameter.__name__:
                continue
            if not _is_far_east_federal_district_name(r.get("entity_label")):
                continue
            raw_fid = r.get("id_federal_district")
            if raw_fid is None:
                continue
            try:
                far_east_fd_id = int(raw_fid)
            except (TypeError, ValueError):
                continue
            break
    if far_east_fd_id is None:
        return

    n_y = len(years)
    res_sums = _aggregate_res_combined_on_fo_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    base = res_sums.get(far_east_fd_id) or [None] * n_y

    eu_sums = _sum_far_east_fd_formula_energy_units_max_power(
        summary_rows, years, year_included=year_included
    )
    if all(v is None for v in eu_sums):
        eu_sums = _sum_far_east_fd_formula_energy_units_max_power_from_demand(years)

    combined_by_fd = {
        far_east_fd_id: [
            _sum_optional_floats(
                base[j] if j < len(base) else None,
                eu_sums[j] if j < len(eu_sums) else None,
            )
            for j in range(n_y)
        ]
    }

    def _far_east_fd_row(row: dict[str, Any]) -> bool:
        raw_fid = row.get("id_federal_district")
        if raw_fid is None:
            return False
        try:
            if int(raw_fid) != far_east_fd_id:
                return False
        except (TypeError, ValueError):
            return False
        return True

    _apply_fd_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        fd_parameter_key=fd_parameter_key,
        sums_by_federal_district=combined_by_fd,
        year_included=year_included,
        use_calculated_mw_format=True,
        row_include_predicate=_far_east_fd_row,
    )

    formula_key = (
        "fo_calc_max_power_mw_far_east"
        if fd_parameter_key == "calculated_max_power_mw"
        else "fo_calc_max_mw_far_east"
    )
    dm_fd = FederalDistrictDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_fd:
            continue
        if r.get("parameter_key") != fd_parameter_key:
            continue
        if not _far_east_fd_row(r):
            continue
        r["pd_formula_text_key"] = formula_key


def enrich_fo_summary_calculated_combined_on_ees_from_res(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное совмещенное … на ЕЭС, МВт» по ФО = сумма «Совмещенное … на ЕЭС, МВт» по РЭС."""
    sums = _aggregate_res_combined_on_ees_mw_sum_by_federal_district(
        summary_rows, years, year_included=year_included
    )
    _apply_fd_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        fd_parameter_key="calculated_combined_on_ees_mw",
        sums_by_federal_district=sums,
        year_included=year_included,
        use_calculated_mw_format=True,
    )


def enrich_fo_summary_calculated_max_from_res_combined_on_fo(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум ФО, МВт» = сумма «Совмещенное потребление мощности на час прохождения максимума ФО, МВт» по РЭС данного ФО."""
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
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
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
    """«Расчетный совмещенный на ЦЗ России, МВт» = сумма «Совмещенное потребление мощности на час прохождения максимума ЦЗ России, МВт» по РЭС данного ФО."""
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
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЭЗ, МВт» по строкам РЭС внутри каждой энергозоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}

    def _tot(ezid: int) -> list[float | None]:
        if ezid not in out:
            out[ezid] = [None] * n_y
        return out[ezid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ez"):
        # Частичное пересечение РЭС с зоной: полный показатель РЭС не суммируем.
        if r.get("pd_pd_ez_res_fully_in_zone") is False:
            continue
        raw_ezid = r.get("id_energy_zone")
        if raw_ezid is None:
            continue
        try:
            ezid = int(raw_ezid)
        except (TypeError, ValueError):
            continue

        row_tot = _tot(ezid)
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» по РЭС внутри каждой синхронной зоны."""
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
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ОЭС, МВт» по РЭС внутри каждой синхронной зоны."""
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
    """Сумма «Максимальное потребление мощности, МВт» по РЭС внутри каждой синхронной зоны."""
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
        for said in sa_ids:
            row_tot = _tot(said)
            for j in range(n_y):
                y = years[j]
                if year_included is not None and not year_included(y):
                    continue
                add = _summary_row_year_float(r, j)
                if add is None:
                    continue
                if row_tot[j] is None:
                    row_tot[j] = float(add)
                else:
                    row_tot[j] = float(row_tot[j]) + float(add)
    return out


@lru_cache(maxsize=8)
def _union_energy_system_ids_for_synchronous_area(
    synchronous_area_id: int,
    *,
    ees_branch_only: bool = True,
) -> frozenset[int]:
    """id ОЭС, у которых есть субъекты РФ в данной синхронной зоне."""
    out: set[int] = set()
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
        belongs = False
        for res in ues.regional_energy_systems or []:
            for rd in res.regional_districts or []:
                if getattr(rd, "id_synchronous_area", None) == synchronous_area_id:
                    belongs = True
                    break
            if belongs:
                break
        if belongs:
            out.add(int(ues.id))
    return frozenset(out)


def _first_sa_ues_exclude_ids_for_nt_group(nt_group: str | None) -> frozenset[int]:
    """ОЭС, не входящие в сумму первой СЗ (Восток всегда; НТ — только для «без НТ»)."""
    excluded: set[int] = set()
    ues_east_id = _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF)
    if ues_east_id is not None:
        excluded.add(int(ues_east_id))
    if nt_group == CODE_WITHOUT_NT:
        nt_ues = _find_new_territories_union_energy_system()
        if nt_ues is not None and getattr(nt_ues, "id", None) is not None:
            excluded.add(int(nt_ues.id))
    return frozenset(excluded)


def _make_ues_perimeter_filter_for_first_sa(
    summary_rows: list[dict[str, Any]],
    nt_group: str | None,
) -> Callable[[dict[str, Any]], bool]:
    """Фильтр ОЭС для суммы первой СЗ: вариант с/без НТ без remap «с НТ»→«без НТ» (как у ЕЭС России)."""
    target = nt_group if nt_group in (CODE_WITH_NT, CODE_WITHOUT_NT) else CODE_WITHOUT_NT
    explicit = _ues_ids_with_explicit_nt_variant_in_summary(summary_rows, target)

    def _filter(row: dict[str, Any]) -> bool:
        return _ues_row_included_for_ees_russia_aggregate_variant(
            row,
            target,
            ues_ids_with_explicit_nt_variant=explicit,
        )

    return _filter


def _first_sa_ues_combined_on_ees_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    first_sa_id: int,
    *,
    nt_group: str | None,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» ОЭС первой СЗ (по группе с/без НТ)."""
    target = nt_group if nt_group in (CODE_WITH_NT, CODE_WITHOUT_NT) else CODE_WITHOUT_NT
    allowed = set(_union_energy_system_ids_for_synchronous_area(int(first_sa_id)))
    allowed -= set(_first_sa_ues_exclude_ids_for_nt_group(target))
    if not allowed:
        return [None] * len(years)
    ues_filter = _make_ues_perimeter_filter_for_first_sa(summary_rows, target)
    year_tot, _ = _sum_ues_combined_on_ees_in_summary_rows(
        summary_rows,
        years,
        allowed_ues_ids=frozenset(allowed),
        year_included=year_included,
        ues_perimeter_filter=ues_filter,
    )
    return year_tot


def _apply_first_sa_kaliningrad_es_subtract_from_year(
    year_sums: list[float | None],
    kaliningrad_combined_on_ees: list[float | None] | None,
    years: list[int],
    perimeter_variant_code: str | None,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Для вариантов с ``_kaliningrad`` вычесть combined_on_ees ЭС Калининграда начиная с «Год с».

    «Год с» — со страницы /perimeter_variants/. С этого года Калининград —
    отдельная СЗ, поэтому его ЭС убираем из суммы ОЭС первой СЗ.
    """
    if not _perimeter_variant_code_has_kaliningrad(perimeter_variant_code):
        return list(year_sums)
    if not kaliningrad_combined_on_ees:
        return list(year_sums)
    fy, _ty = perimeter_variant_year_bounds_for_code(str(perimeter_variant_code))
    n_y = len(years)
    out: list[float | None] = [None] * n_y
    for j in range(n_y):
        y = years[j]
        if year_included is not None and not year_included(y):
            continue
        base = year_sums[j] if j < len(year_sums) else None
        if base is None:
            continue
        subtract_here = fy is None or int(y) >= int(fy)
        if not subtract_here:
            out[j] = float(base)
            continue
        kal = (
            kaliningrad_combined_on_ees[j]
            if j < len(kaliningrad_combined_on_ees)
            else None
        )
        out[j] = float(base) - float(kal or 0.0)
    return out


def _find_ues_summary_row(
    summary_rows: list[dict[str, Any]],
    *,
    ues_id: int,
    parameter_key: str,
) -> dict[str, Any] | None:
    dm_ues = UnionEnergySystemDemandParameter.__name__
    for row in summary_rows:
        if row.get("demand_model_name") != dm_ues:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if _union_energy_system_id_from_flat_row(row) == ues_id:
            return row
    return None


def _find_res_summary_row(
    summary_rows: list[dict[str, Any]],
    *,
    res_id: int,
    parameter_key: str,
) -> dict[str, Any] | None:
    dm_res = RegionalEnergySystemDemandParameter.__name__
    for row in summary_rows:
        if row.get("demand_model_name") != dm_res:
            continue
        if row.get("parameter_key") != parameter_key:
            continue
        if _regional_energy_system_id_from_flat_row(row) == res_id:
            return row
    return None


def _copy_pd_summary_row_display_from_reference(
    target_row: dict[str, Any],
    reference_row: dict[str, Any],
    years: list[int],
) -> None:
    n_y = len(years)
    source_values = list(reference_row.get("year_values") or [])
    source_tooltips = list(reference_row.get("year_numeric_tooltips") or [])
    while len(source_values) < n_y:
        source_values.append("—")
    while len(source_tooltips) < n_y:
        source_tooltips.append("")
    existing_values = list(target_row.get("year_values") or [])
    existing_tooltips = list(target_row.get("year_numeric_tooltips") or [])
    values: list[str] = []
    tooltips: list[str] = []
    for index, year in enumerate(years):
        if not _formula_year_applies_to_row_perimeter_variant(target_row, int(year)):
            values.append(
                existing_values[index] if index < len(existing_values) else "—"
            )
            tooltips.append(
                existing_tooltips[index] if index < len(existing_tooltips) else ""
            )
            continue
        values.append(source_values[index] if index < len(source_values) else "—")
        tooltips.append(source_tooltips[index] if index < len(source_tooltips) else "")
    target_row["year_values"] = values
    target_row["year_numeric_tooltips"] = tooltips
    pk = str(target_row.get("parameter_key") or "")
    if pk in SUMMARY_HIST_PARAMETER_KEYS:
        target_row["hist_value"] = reference_row.get("hist_value", "")
        target_row["hist_numeric_tooltip"] = reference_row.get("hist_numeric_tooltip", "")


def apply_second_sa_from_ues_east_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    _rounding_digits: int,
) -> None:
    """Вторая синхронная зона на сводке по ОЭС = показатели ОЭС Востока (только отображение)."""
    if not summary_rows or not years:
        return

    second_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
        _SECOND_SYNC_AREA_BASE_LABEL_CF
    )
    ues_east_id = _resolve_union_energy_system_id_by_name_cf(_UES_EAST_NAME_CF)
    if second_sa_id is None or ues_east_id is None:
        return

    dm_sa = SynchronousAreaDemandParameter.__name__
    for target_row in summary_rows:
        if target_row.get("demand_model_name") != dm_sa:
            continue
        if _synchronous_area_id_from_flat_row(target_row) != second_sa_id:
            continue
        target_pk = str(target_row.get("parameter_key") or "")
        source_pk = _SECOND_SA_FROM_UES_EAST_SOURCE_PARAM.get(target_pk)
        if not source_pk:
            continue
        source_row = _find_ues_summary_row(
            summary_rows,
            ues_id=ues_east_id,
            parameter_key=source_pk,
        )
        if source_row is None:
            continue
        _copy_pd_summary_row_display_from_reference(target_row, source_row, years)
        target_row["pd_pd_formula_derived_row"] = True
        formula_key = _SECOND_SA_FROM_UES_EAST_FORMULA_KEY.get(target_pk)
        if formula_key:
            target_row["pd_formula_text_key"] = formula_key


def apply_kaliningrad_sa_from_kaliningrad_es_formula(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    _rounding_digits: int,
) -> None:
    """Синхронная зона Калининградской области на сводке по ОЭС = ЭС Калининградской области (только отображение)."""
    if not summary_rows or not years:
        return

    kaliningrad_sa_id = _resolve_kaliningrad_synchronous_area_id()
    kaliningrad_es_id = _resolve_regional_energy_system_id_by_name_cf(_KALININGRAD_ES_NAME_CF)
    if kaliningrad_sa_id is None or kaliningrad_es_id is None:
        return

    dm_sa = SynchronousAreaDemandParameter.__name__
    for target_row in summary_rows:
        if target_row.get("demand_model_name") != dm_sa:
            continue
        if _synchronous_area_id_from_flat_row(target_row) != kaliningrad_sa_id:
            continue
        target_pk = str(target_row.get("parameter_key") or "")
        source_pk = _KALININGRAD_SA_FROM_ES_SOURCE_PARAM.get(target_pk)
        if not source_pk:
            continue
        source_row = _find_res_summary_row(
            summary_rows,
            res_id=kaliningrad_es_id,
            parameter_key=source_pk,
        )
        if source_row is None:
            continue
        _copy_pd_summary_row_display_from_reference(target_row, source_row, years)
        target_row["pd_pd_formula_derived_row"] = True
        formula_key = _KALININGRAD_SA_FROM_ES_FORMULA_KEY.get(target_pk)
        if formula_key:
            target_row["pd_formula_text_key"] = formula_key


def enrich_oes_summary_calculated_max_power_sa_from_res_max_power(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» по синхронной зоне.

    Для «Вторая синхронная зона» — сумма «Совмещенное потребление мощности на час прохождения максимума ОЭС, МВт»;
    для «Синхронная зона Калининградской области» — «Максимальное потребление мощности, МВт» ЭС Калининградской области;
    для первой синхронной зоны — сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт»
    по ОЭС зоны (с/без НТ по варианту); сумма пишется по всем годам (не ограничена «Год с» варианта);
    если в коде периметра есть ``_kaliningrad``, с «Год с» вычитается combined_on_ees ЭС Калининградской области.
    """
    del rounding_digits
    res_to_sa_ids = _build_res_to_synchronous_area_ids_map()
    sums_max = _aggregate_res_max_power_mw_sum_by_synchronous_area(
        summary_rows, years, res_to_sa_ids, year_included=year_included
    )
    sums_oes = _aggregate_res_combined_on_oes_mw_sum_by_synchronous_area(
        summary_rows, years, res_to_sa_ids, year_included=year_included
    )
    first_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
        _FIRST_SYNC_AREA_BASE_LABEL_CF
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
    kaliningrad_combined_on_ees = (
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
    first_sa_ues_sums_by_nt: dict[str, list[float | None]] = {}

    def _first_sa_sums_for_nt(nt_group: str | None) -> list[float | None]:
        key = nt_group if nt_group in (CODE_WITH_NT, CODE_WITHOUT_NT) else CODE_WITHOUT_NT
        if key not in first_sa_ues_sums_by_nt:
            first_sa_ues_sums_by_nt[key] = _first_sa_ues_combined_on_ees_year_sums(
                summary_rows,
                years,
                int(first_sa_id),
                nt_group=key,
                year_included=year_included,
            )
        return first_sa_ues_sums_by_nt[key]

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
        elif first_sa_id is not None and said == first_sa_id:
            row_code = r.get("perimeter_variant_code")
            nt_group = legacy_nt_group_for_perimeter_code(
                str(row_code) if row_code else None
            )
            if nt_group is None and row_code:
                # Коды вида without_nt_without_gaes_kaliningrad не в legacy-группе GAES.
                if str(row_code).startswith("with_nt"):
                    nt_group = CODE_WITH_NT
                elif str(row_code).startswith("without_nt"):
                    nt_group = CODE_WITHOUT_NT
            base_sums = _first_sa_sums_for_nt(nt_group)
            mids = _apply_first_sa_kaliningrad_es_subtract_from_year(
                base_sums,
                kaliningrad_combined_on_ees,
                years,
                row_code,
                year_included=year_included,
            )
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
        # Первая СЗ: сумма ОЭС пишется по всем годам; «Год с» влияет только на
        # вычитание Калининграда (_apply_first_sa_kaliningrad_es_subtract_from_year).
        is_first_sa_row = first_sa_id is not None and said == first_sa_id
        for j in range(n_y):
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
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
        if is_first_sa_row:
            r["pd_pd_formula_derived_row"] = True
            r["pd_formula_text_key"] = "sa_first_calc_max_power_mw"


def enrich_oes_summary_calculated_max_sa_from_res_combined_on_ees(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт».

    Для первой и второй синхронной зоны — сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт»
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
    first_sa_id = _resolve_synchronous_area_id_by_name_prefix_cf(
        _FIRST_SYNC_AREA_BASE_LABEL_CF
    )
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
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
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
        if first_sa_id is not None and said == first_sa_id:
            r["pd_pd_formula_derived_row"] = True
            r["pd_formula_text_key"] = "sa_first_calc_max_sa_mw"


def _aggregate_res_combined_on_ees_mw_sum_by_energy_zone(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» по РЭС внутри каждой энергозоны."""
    n_y = len(years)
    out: dict[int, list[float | None]] = {}
    subject_fallback = _subject_parameter_sums_by_res_year_index(
        summary_rows, "combined_on_ees", years, year_included=year_included
    )

    def _tot(ezid: int) -> list[float | None]:
        if ezid not in out:
            out[ezid] = [None] * n_y
        return out[ezid]

    for r in _iter_res_level_aggregation_source_rows(summary_rows, "combined_on_ees"):
        # Частичное пересечение РЭС с зоной: полный показатель РЭС не суммируем.
        if r.get("pd_pd_ez_res_fully_in_zone") is False:
            continue
        raw_ezid = r.get("id_energy_zone")
        if raw_ezid is None:
            continue
        try:
            ezid = int(raw_ezid)
        except (TypeError, ValueError):
            continue
        row_tot = _tot(ezid)
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


def _apply_ez_parameter_from_res_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    ez_parameter_key: str,
    sums_by_energy_zone: dict[int, list[float | None]],
    year_included: Callable[[int], bool] | None = None,
    use_calculated_mw_format: bool = False,
) -> None:
    """Подставляет в строку энергозоны суммы по РЭС (годовые столбцы; исторический столбец очищается)."""
    n_y = len(years)
    dm_ez = EnergyZoneDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != dm_ez:
            continue
        if r.get("parameter_key") != ez_parameter_key:
            continue
        raw_ezid = r.get("id_energy_zone")
        if raw_ezid is None:
            continue
        try:
            ezid = int(raw_ezid)
        except (TypeError, ValueError):
            continue
        mids = sums_by_energy_zone.get(ezid)
        if mids is None:
            mids = [None] * n_y
        yv_p = list(r.get("year_values") or [])
        ynt_p = list(r.get("year_numeric_tooltips") or [])
        while len(yv_p) < n_y:
            yv_p.append("—")
        while len(ynt_p) < n_y:
            ynt_p.append("")
        for j in range(n_y):
            if not _pd_should_apply_formula_for_year(r, years[j], year_included):
                continue
            s = mids[j] if j < len(mids) else None
            if s is not None:
                if use_calculated_mw_format:
                    yv_p[j] = _format_calculated_max_mw(s)
                    ynt_p[j] = _format_calculated_max_mw(s)
                else:
                    yv_p[j] = _format_numeric(s, rounding_digits)
                    ynt_p[j] = _format_full_numeric_tooltip(s)
            else:
                yv_p[j] = "—"
                ynt_p[j] = ""
        r["year_values"] = yv_p
        r["year_numeric_tooltips"] = ynt_p
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def enrich_ez_summary_calculated_max_power_from_res_combined_on_ez(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» = сумма «Совмещенное потребление мощности на час прохождения максимума ЭЗ, МВт» по РЭС данной энергозоны."""
    sums = _aggregate_res_combined_on_ez_mw_sum_by_energy_zone(
        summary_rows, years, year_included=year_included
    )
    _apply_ez_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ez_parameter_key="calculated_max_power_mw",
        sums_by_energy_zone=sums,
        year_included=year_included,
        use_calculated_mw_format=True,
    )


def enrich_ez_summary_calculated_combined_on_ees_from_res(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное совмещенное … на ЕЭС, МВт» = сумма «Совмещенное … на ЕЭС, МВт» по РЭС данной энергозоны."""
    sums = _aggregate_res_combined_on_ees_mw_sum_by_energy_zone(
        summary_rows, years, year_included=year_included
    )
    _apply_ez_parameter_from_res_sums(
        summary_rows,
        years,
        rounding_digits,
        ez_parameter_key="calculated_combined_on_ees_mw",
        sums_by_energy_zone=sums,
        year_included=year_included,
        use_calculated_mw_format=True,
    )


def _enrich_ez_summary_calculated_max_from_res(
    context: dict[str, Any], rounding_digits: int
) -> None:
    rows = context.get("summary_rows") or []
    years = list(context.get("years") or [])
    if context.get("ez_max_extended_parameters"):
        enrich_ez_summary_calculated_max_power_from_res_combined_on_ez(
            rows, years, rounding_digits
        )
        enrich_ez_summary_calculated_combined_on_ees_from_res(
            rows, years, rounding_digits
        )
    # Расчётные максимумы «ЕЭС России с/без НТ» — как на /summary/oes/ (из demand_rows / формул ОЭС),
    # а не единая сумма combined_on_ees по энергозонам (раньше была одна строка «ЕЭС России»).
    enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits)


def _clear_summary_hist_non_base_parameters(
    summary_rows: list[dict[str, Any]],
) -> None:
    """Сводки ОЭС/ФО/ЭЗ: «Исторический собственный максимум» только у max_power, peak_datetime, avg_temp."""
    for r in summary_rows:
        if (r.get("parameter_key") or "") in SUMMARY_HIST_PARAMETER_KEYS:
            continue
        r["hist_value"] = ""
        r["hist_numeric_tooltip"] = ""


def _clear_oes_summary_hist_non_base_parameters(
    summary_rows: list[dict[str, Any]],
) -> None:
    _clear_summary_hist_non_base_parameters(summary_rows)


def enrich_oes_summary_calculated_max_power_from_res_combined(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» = сумма «Совмещенный максимум потребления мощности ОЭС, МВт» по РЭС того же ОЭС."""
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
    """«Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» = сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по РЭС того же ОЭС."""
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


def _sum_ues_parameter_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    parameter_key: str,
    *,
    allowed_ues_ids: frozenset[int] | None = None,
    year_included: Callable[[int], bool] | None = None,
    ues_perimeter_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[list[float | None], float | None]:
    """Сумма значений показателя УЭС по строкам ОЭС в flat-таблице сводки."""
    n_y = len(years)
    year_tot: list[float | None] = [None] * n_y
    hist_tot: float | None = None
    ues_dm = UnionEnergySystemDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != ues_dm:
            continue
        if r.get("parameter_key") != parameter_key:
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
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
        if year_included is None:
            add_h = _parse_summary_cell_float(r.get("hist_numeric_tooltip"))
            if add_h is None:
                add_h = _parse_summary_cell_float(r.get("hist_value"))
            if add_h is not None:
                if hist_tot is None:
                    hist_tot = float(add_h)
                else:
                    hist_tot = float(hist_tot) + float(add_h)
    return year_tot, hist_tot


def _sum_ues_combined_on_ees_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    allowed_ues_ids: frozenset[int] | None = None,
    year_included: Callable[[int], bool] | None = None,
    ues_perimeter_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[list[float | None], float | None]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам ОЭС в flat-таблице сводки."""
    return _sum_ues_parameter_in_summary_rows(
        summary_rows,
        years,
        "combined_on_ees",
        allowed_ues_ids=allowed_ues_ids,
        year_included=year_included,
        ues_perimeter_filter=ues_perimeter_filter,
    )


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
        if not _pd_should_apply_formula_for_year(row, years[jj], year_included):
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
            ues_perimeter_filter=_make_ues_perimeter_filter_for_ees_russia_aggregate(
                summary_rows, block_variant
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


def _sum_ez_combined_on_ees_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> tuple[list[float | None], float | None]:
    """Сумма «Совмещенный максимум потребления мощности ЕЭС, МВт» по строкам энергозон."""
    n_y = len(years)
    year_tot: list[float | None] = [None] * n_y
    hist_tot: float | None = None
    ez_dm = EnergyZoneDemandParameter.__name__
    for r in summary_rows:
        if r.get("demand_model_name") != ez_dm:
            continue
        if r.get("parameter_key") != "combined_on_ees":
            continue
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            add = _summary_row_year_float(r, j)
            if add is None:
                continue
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
        if year_included is None:
            add_h = _parse_summary_cell_float(r.get("hist_numeric_tooltip"))
            if add_h is None:
                add_h = _parse_summary_cell_float(r.get("hist_value"))
            if add_h is not None:
                if hist_tot is None:
                    hist_tot = float(add_h)
                else:
                    hist_tot = float(hist_tot) + float(add_h)
    return year_tot, hist_tot


def enrich_ees_russia_calculated_max_via_ez(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности (через ЭЗ)» = сумма combined_on_ees по энергозонам ЕЭС России без НТ."""
    if not summary_rows or not years:
        return
    if not any(
        r.get("demand_model_name") == EnergyZoneDemandParameter.__name__
        and r.get("parameter_key") == "combined_on_ees"
        for r in summary_rows
    ):
        return
    calc_models = frozenset({_EES_RUSSIA_AGGREGATE_DM_NAME})
    year_sums_base, hist_sum = _sum_ez_combined_on_ees_in_summary_rows(
        summary_rows,
        years,
        year_included=year_included,
    )
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") not in calc_models:
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums = _ees_russia_year_sums_with_nt_addon(
            summary_rows,
            years,
            block_variant,
            year_sums_base,
            year_included=year_included,
        )
        _apply_ees_russia_calculated_mw_to_entity_block(
            summary_rows,
            i,
            years,
            rounding_digits,
            "calculated_max_ees_via_ez_mw",
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



def _ees_russia_max_power_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Максимальное потребление мощности, МВт» агрегата «ЕЭС России без НТ» по годам."""
    n_y = len(years)
    out: list[float | None] = [None] * n_y
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != _EES_RUSSIA_AGGREGATE_DM_NAME:
            continue
        if not _perimeter_variant_codes_match_nt_target(
            row.get("perimeter_variant_code"), CODE_WITHOUT_NT
        ):
            continue
        i0, i1 = i, _oes_summary_entity_block_end(summary_rows, i)
        max_power_row = None
        for j in range(i0, i1):
            if summary_rows[j].get("parameter_key") == "max_power":
                max_power_row = summary_rows[j]
                break
        if max_power_row is None:
            continue
        yvals = max_power_row.get("year_values") or []
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


def _sum_tites_branch_max_power_in_summary_rows(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма «Максимальное потребление мощности, МВт» по всей ветке «ТИТЭС и децентрализованная зона».

    Западный/Центральный энергорайоны Саха (Якутия) входят в сумму только до
    ``_TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR`` включительно.
    """
    n_y = len(years)
    tites_ids = _tites_union_energy_system_ids()
    sakha_extra_eu_ids = _tites_sakha_yakutia_extra_energy_unit_ids()
    if not tites_ids and not sakha_extra_eu_ids:
        return [None] * n_y

    year_tot: list[float | None] = [None] * n_y
    seen_sakha_year: set[tuple[int, int]] = set()
    through_year = _TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR
    for r in summary_rows:
        if r.get("parameter_key") != "max_power":
            continue
        eu_id = _energy_unit_id_from_flat_row(r)
        in_sakha = eu_id is not None and int(eu_id) in sakha_extra_eu_ids
        uid = _union_energy_system_id_from_flat_row(r)
        in_tites = (
            uid is not None and tites_ids and int(uid) in tites_ids and not in_sakha
        )
        if not in_tites and not in_sakha:
            continue
        yvals = r.get("year_values") or []
        for j in range(n_y):
            y = years[j]
            if year_included is not None and not year_included(y):
                continue
            if in_sakha and int(y) > through_year:
                continue
            if in_sakha:
                sakha_key = (int(eu_id), int(y))
                if sakha_key in seen_sakha_year:
                    continue
            add = _parse_summary_cell_float(yvals[j] if j < len(yvals) else None)
            if add is None:
                continue
            if in_sakha:
                seen_sakha_year.add((int(eu_id), int(y)))
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


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
) -> list[float | None]:
    """Сумма «Максимальное потребление мощности, МВт» по энергорайонам формулы ЭЭС России (без поправок)."""
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
            if year_tot[j] is None:
                year_tot[j] = float(add)
            else:
                year_tot[j] = float(year_tot[j]) + float(add)
    return year_tot


def _ees_calculated_max_power_consumption_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Расчетное максимальное потребление мощности, МВт» (ЭЭС России без НТ).

    = max_power «ЕЭС России без НТ»
      + сумма max_power энергорайонов формулы (Норильск, Сахалин, Камчатка,
        Чаун-Билибино, Анадырский, Магадан) без поправок.
    """
    ees_row = _ees_russia_max_power_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    eu_sums = _sum_ees_aggregate_formula_tites_energy_units_max_power(
        summary_rows, years, year_included=year_included
    )
    return _merge_optional_float_year_lists(ees_row, eu_sums)


def _nt_max_power_year_sums_for_south_ues(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """Сумма max_power субъектов «Новые территории» под ОЭС Юга (для «ЭЭС России с НТ»)."""
    out: list[float | None] = []
    south_ids = _south_ues_ids_for_nt_enrichment(summary_rows)
    for south_id in south_ids:
        part = _aggregate_nt_subjects_parameter_mw_sum_for_south_ues(
            summary_rows,
            years,
            parameter_key="max_power",
            south_ues_id=south_id,
            year_included=year_included,
        )
        out = _merge_optional_float_year_lists(out, part)
    return out


def enrich_oes_ees_calculated_max_power_consumption(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» (ЭЭС России).

    Без НТ: max_power ЕЭС России без НТ + max_power энергорайонов формулы.
    С НТ: то же, что без НТ, + сумма max_power субъектов «Новые территории».
    """
    if not summary_rows or not years:
        return
    without_nt_sums = _ees_calculated_max_power_consumption_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    nt_addon_sums = _nt_max_power_year_sums_for_south_ues(
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
            if block_variant is not None
            and legacy_nt_group_for_perimeter_code(str(block_variant)) == CODE_WITH_NT
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



def _ees_aggregate_max_power_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Максимальное потребление мощности, МВт» агрегата «ЭЭС России без НТ» по годам."""
    n_y = len(years)
    out: list[float | None] = [None] * n_y
    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != _EES_AGGREGATE_DEMAND_MODEL_NAME:
            continue
        if not _perimeter_variant_codes_match_nt_target(
            row.get("perimeter_variant_code"), CODE_WITHOUT_NT
        ):
            continue
        i0, i1 = i, _oes_summary_entity_block_end(summary_rows, i)
        max_power_row = None
        for j in range(i0, i1):
            if summary_rows[j].get("parameter_key") == "max_power":
                max_power_row = summary_rows[j]
                break
        if max_power_row is None:
            continue
        yvals = max_power_row.get("year_values") or []
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


def _ees_aggregate_max_power_without_nt_from_demand(
    years: list[int],
) -> list[float | None]:
    """max_power «ЭЭС России без НТ» из таблицы параметров нагрузки."""
    rows = _pick_demand_rows_for_nt_group_no_parent(
        EesRussiaDemandParameter,
        CODE_WITHOUT_NT,
    )
    return _max_power_year_floats_from_demand_rows(rows, years)


def _pick_demand_rows_for_nt_group_no_parent(
    model: type,
    nt_group: str | None,
) -> list[Any]:
    """Строки demand без FK-родителя (ЭЭС России и т.п.) для группы с/без НТ."""
    codes: list[str | None] = []
    if nt_group in (CODE_WITH_NT, CODE_WITHOUT_NT):
        codes.extend(perimeter_variant_codes_in_legacy_nt_group(nt_group))
    codes.append(None)
    seen: set[str | None] = set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        rows = dps.get_demand_rows(
            model,
            None,
            None,
            perimeter_variant_code=code,
        )
        if any(getattr(r, "max_power_consumption_mw", None) is not None for r in rows):
            return list(rows)
    return list(
        dps.get_demand_rows(
            model,
            None,
            None,
            perimeter_variant_code=None,
        )
    )


def _ees_russia_max_power_without_nt_from_demand(
    years: list[int],
) -> list[float | None]:
    """max_power «ЕЭС России без НТ» из таблицы параметров нагрузки."""
    est = _get_energy_system_type_by_name(EES_UNIFIED_REF_NAME)
    if est is None:
        return [None] * len(years)
    rows = _pick_demand_rows_for_nt_group(
        EnergySystemTypeDemandParameter,
        "id_energy_system_type",
        int(est.id),
        CODE_WITHOUT_NT,
    )
    return _max_power_year_floats_from_demand_rows(rows, years)


def _sum_ees_aggregate_formula_tites_energy_units_max_power_from_demand(
    years: list[int],
) -> list[float | None]:
    """Сумма max_power энергорайонов формулы ЭЭС из таблиц нагрузки.

    Как на сводке: сначала вариант О-1 (если есть данные), иначе базовый периметр.
    """
    n_y = len(years)
    eu_ids = _ees_aggregate_formula_tites_energy_unit_ids()
    if not eu_ids:
        return [None] * n_y
    o1_code = resolve_catalog_o1_perimeter_variant_code()
    year_tot: list[float | None] = [None] * n_y
    for eu_id in sorted(eu_ids):
        rows = dps.get_demand_rows(
            EnergyUnitDemandParameter,
            "id_energy_unit",
            eu_id,
            perimeter_variant_code=o1_code,
        )
        if not rows or all(
            getattr(r, "max_power_consumption_mw", None) is None for r in rows
        ):
            rows = dps.get_demand_rows(
                EnergyUnitDemandParameter,
                "id_energy_unit",
                eu_id,
                perimeter_variant_code=None,
            )
        part = _max_power_year_floats_from_demand_rows(rows, years)
        year_tot = _merge_optional_float_year_lists(year_tot, part)
    return year_tot


def _nt_max_power_year_sums_from_demand(
    years: list[int],
) -> list[float | None]:
    """Сумма max_power субъектов ФО «Новые территории» из таблиц нагрузки."""
    summed = _new_territories_demand_rows_summed_from_subjects()
    return _max_power_year_floats_from_demand_rows(summed, years)


def _nt_combined_on_fo_year_sums_from_demand(
    years: list[int],
) -> list[float | None]:
    """Сумма combined_on_fo субъектов ФО «Новые территории» из таблиц нагрузки."""
    summed = _new_territories_demand_rows_summed_from_subjects()
    return _demand_field_year_floats_from_rows(summed, years, "combined_on_fo")


def _max_power_year_floats_from_demand_rows(
    demand_rows: list[Any],
    years: list[int],
) -> list[float | None]:
    return _demand_field_year_floats_from_rows(
        demand_rows, years, "max_power_consumption_mw"
    )


def _demand_field_year_floats_from_rows(
    demand_rows: list[Any],
    years: list[int],
    field_name: str,
) -> list[float | None]:
    by_year: dict[int, float] = {}
    for dr in demand_rows:
        if getattr(dr, "is_historical_maximum", False):
            continue
        y = getattr(dr, "year_number", None)
        if y is None:
            continue
        raw = getattr(dr, field_name, None)
        if raw is None:
            continue
        try:
            by_year[int(y)] = float(raw)
        except (TypeError, ValueError):
            continue
    return [by_year.get(int(y)) for y in years]


def _pick_demand_rows_for_nt_group(
    model: type,
    parent_fk: str,
    parent_id: int,
    nt_group: str | None,
) -> list[Any]:
    """Подбирает строки demand с вариантом периметра нужной группы НТ (иначе без варианта)."""
    codes: list[str | None] = []
    if nt_group in (CODE_WITH_NT, CODE_WITHOUT_NT):
        codes.extend(perimeter_variant_codes_in_legacy_nt_group(nt_group))
    codes.append(None)
    seen: set[str | None] = set()
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        rows = dps.get_demand_rows(
            model,
            parent_fk,
            parent_id,
            perimeter_variant_code=code,
        )
        if any(getattr(r, "max_power_consumption_mw", None) is not None for r in rows):
            return list(rows)
    return list(
        dps.get_demand_rows(
            model,
            parent_fk,
            parent_id,
            perimeter_variant_code=None,
        )
    )


def _cz_russia_calculated_max_power_without_nt_year_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    *,
    year_included: Callable[[int], bool] | None = None,
) -> list[float | None]:
    """«Расчетное максимальное потребление мощности, МВт» (ЦЗ России без НТ).

    = max_power «ЕЭС России без НТ»
      + сумма max_power энергорайонов формулы ЭЭС (Норильск, Сахалин, Камчатка,
        Чаун-Билибино, Анадырский, Магадан) — та же база, что у расчётного ЭЭС.
    """
    ees_row = _ees_russia_max_power_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    if all(v is None for v in ees_row):
        ees_row = _ees_russia_max_power_without_nt_from_demand(years)

    eu_sums = _sum_ees_aggregate_formula_tites_energy_units_max_power(
        summary_rows, years, year_included=year_included
    )
    if all(v is None for v in eu_sums):
        eu_sums = _sum_ees_aggregate_formula_tites_energy_units_max_power_from_demand(
            years
        )
    return _merge_optional_float_year_lists(ees_row, eu_sums)


def enrich_cz_russia_calculated_max_power_mw(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетное максимальное потребление мощности, МВт» для ЦЗ России с/без НТ.

    Без НТ: max_power ЕЭС России без НТ + max_power энергорайонов формулы ЭЭС.
    С НТ: то же, что без НТ, + сумма max_power субъектов «Новые территории».
    """
    if not summary_rows or not years:
        return
    without_nt_sums = _cz_russia_calculated_max_power_without_nt_year_sums(
        summary_rows, years, year_included=year_included
    )
    cz_dm = CentralizedZoneDemandParameter.__name__
    has_with_nt_cz = any(
        r.get("show_entity_cell")
        and r.get("demand_model_name") == cz_dm
        and r.get("entity_kind") in (None, "centralized_zone")
        and r.get("perimeter_variant_code") is not None
        and _pd_nt_group_for_variant_code(str(r.get("perimeter_variant_code")))
        == "with_nt"
        for r in summary_rows
    )
    nt_addon_sums: list[float | None] = [None] * len(years)
    if has_with_nt_cz:
        nt_addon_sums = _nt_max_power_year_sums_for_south_ues(
            summary_rows, years, year_included=year_included
        )
        if all(v is None for v in nt_addon_sums):
            nt_addon_sums = _nt_max_power_year_sums_from_demand(years)
    with_nt_sums = _merge_optional_float_year_lists(without_nt_sums, nt_addon_sums)

    for i, row in enumerate(summary_rows):
        if not row.get("show_entity_cell"):
            continue
        if row.get("demand_model_name") != cz_dm:
            continue
        if row.get("entity_kind") not in (None, "centralized_zone"):
            continue
        block_variant = row.get("perimeter_variant_code")
        year_sums = (
            with_nt_sums
            if block_variant is not None
            and _pd_nt_group_for_variant_code(str(block_variant)) == "with_nt"
            else without_nt_sums
        )
        i0, i1 = i, _oes_summary_entity_block_end(summary_rows, i)
        for j in range(i0, i1):
            r = summary_rows[j]
            if r.get("parameter_key") != "calculated_max_power_mw":
                continue
            _apply_ees_russia_calculated_mw_row(
                r,
                years,
                rounding_digits,
                year_sums,
                None,
                year_included=year_included,
            )
            r["pd_pd_formula_derived_row"] = True
            r["pd_formula_text_key"] = "cz_russia_calc_max_mw"


def enrich_oes_ees_russia_calculated_max_russia_mw(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    rounding_digits: int,
    *,
    filter_year_list: list[int],
    year_included: Callable[[int], bool] | None = None,
) -> None:
    """«Расчетный максимум потребления мощности ЕЭС России, МВт» = сумма «Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» по ОЭС типа «ЕЭС России».

    Для «без НТ» — сумма combined_on_ees по ОЭС (у Юга — вариант без НТ).
    Для «с НТ» — та же база, что у «без НТ», плюс сумма combined_on_ees субъектов «Новые территории».
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
            ues_perimeter_filter=_make_ues_perimeter_filter_for_ees_russia_aggregate(
                summary_rows, block_variant
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
    enrich_south_ues_perimeter_calculated_combined_on_ees_from_res(
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
    enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits)
    _clear_south_ues_with_nt_formula_years_before(rows, years)


def _enrich_fo_summary_calculated_max_from_res(
    context: dict[str, Any], rounding_digits: int
) -> None:
    rows = context.get("summary_rows") or []
    years = list(context.get("years") or [])
    fo_max = bool(context.get("fo_max_extended_parameters"))
    if not fo_max:
        enrich_fo_summary_calculated_max_from_res_combined_on_fo(
            rows, years, rounding_digits
        )
        enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
            rows,
            years,
            rounding_digits,
            fd_parameter_key="calculated_max_fo_mw",
        )
        enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
            rows,
            years,
            rounding_digits,
            fd_parameter_key="calculated_max_fo_mw",
        )
    enrich_fo_summary_calculated_combined_on_cz_from_res_combined(
        rows, years, rounding_digits
    )
    if fo_max:
        enrich_fo_summary_calculated_max_power_from_res_combined_on_fo(
            rows, years, rounding_digits
        )
        enrich_south_fd_with_nt_calculated_max_from_res_and_nt_subjects(
            rows,
            years,
            rounding_digits,
            fd_parameter_key="calculated_max_power_mw",
        )
        enrich_far_east_fd_calculated_max_from_res_and_tites_eus(
            rows,
            years,
            rounding_digits,
            fd_parameter_key="calculated_max_power_mw",
        )
    enrich_cz_russia_calculated_max_power_mw(rows, years, rounding_digits)


def _aggregate_res_combined_on_oes_mw_sum_by_union_for_medium_years(
    summary_rows: list[dict[str, Any]],
    years: list[int],
    coeff_base_year: int,
) -> dict[int, list[float | None]]:
    """Сумма «Совмещенный максимум потребления мощности ОЭС, МВт» по строкам РЭС (отчётный N−9…N и среднесрочный N+1…N+6).

    На УЭС для «Расчетное максимальное потребление мощности, МВт» эти годы задаются этой суммой.
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

    На УЭС для «Расчетное совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» эти годы задаются этой суммой.
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
    rd_k = (
        rounding_digits_k
        if rounding_digits_k is not None
        else DEFAULT_COEFF_K_ROUNDING_DIGITS
    )
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
                formula_year_ok = _formula_year_applies_to_row_perimeter_variant(r, y)
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
                        k_list.append(_format_coeff_k_numeric(sk_rounded, rd_k))
                        k_tt.append(_format_coeff_k_tooltip(sk_rounded))
                        continue
                    if dm_n == "UnionEnergySystemDemandParameter" and pk in (
                        "calculated_max_power_mw",
                        "combined_on_ees",
                        "calculated_combined_on_ees_mw",
                    ):
                        if (
                            formula_year_ok
                            and coeff_base_year is not None
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
                            k_list.append(_format_coeff_k_numeric(sk_rounded, rd_k))
                            k_tt.append(_format_coeff_k_tooltip(sk_rounded))
                            continue
                if not formula_year_ok:
                    k_list.append("—")
                    k_tt.append("")
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
                    k_list.append(_format_coeff_k_numeric(ratio, rd_k))
                    k_tt.append(_format_coeff_k_tooltip(ratio))
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
                    if not _formula_year_applies_to_row_perimeter_variant(r, yt):
                        continue
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
                    if not _formula_year_applies_to_row_perimeter_variant(r, y):
                        continue
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
                    if not _formula_year_applies_to_row_perimeter_variant(r, y):
                        continue
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
            out.append(_format_coeff_k_numeric(v, rounding_digits))
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
        "pd_pd_summary_perimeter_variant_row": bool(
            getattr(entity, "summary_perimeter_variant_row", False)
        ),
        "year_coeff_k_stored": [],
        "entity_note_text": "",
        "entity_note_row_id": None,
        "show_entity_note_cell": False,
        "pd_pd_aggregation_level_row": True,
        "pd_pd_aggregation_level_full_row": True,
        "pd_pd_skip_empty_hide_row": True,
        "pd_pd_nt_subtree_root": _entity_row_is_nt_subtree_root(entity),
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
    entity_display_label = entity.label
    if entity.entity_kind == "centralized_zone":
        entity_display_label = _pd_strip_o1_from_centralized_zone_label(
            entity_display_label
        )

    for index, (parameter_key, parameter_label) in enumerate(entity.parameters):
        values = parameter_maps.get(parameter_key, {})
        tt = tooltip_maps.get(parameter_key, {})
        year_row_ids = [slice_ids.get(year) for year in years]
        entity_rows.append(
            {
                "entity_label": entity_display_label,
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
                "pd_pd_summary_perimeter_variant_row": bool(
                    getattr(entity, "summary_perimeter_variant_row", False)
                ),
                "pd_pd_centralized_zone_o1_display_row": bool(
                    getattr(entity, "centralized_zone_o1_display_row", False)
                ),
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
                "pd_pd_nt_subtree_root": index == 0 and _entity_row_is_nt_subtree_root(entity),
            }
        )
        if entity.is_decentralized_zone_energy_unit:
            entity_rows[-1]["pd_pd_decentralized_zone_mark"] = True
            entity_rows[-1]["pd_pd_skip_empty_hide_row"] = True
        if entity.sakha_yakutia_tites_through_year_row:
            entity_rows[-1]["pd_pd_sakha_tites_through_year_row"] = True
            entity_rows[-1]["sakha_membership_through_year"] = (
                _TITES_OES_SAKHA_YAKUTIA_EXTRA_ENERGY_UNITS_THROUGH_YEAR
            )
        if entity.ez_res_fully_in_zone is not None:
            entity_rows[-1]["pd_pd_ez_res_fully_in_zone"] = bool(
                entity.ez_res_fully_in_zone
            )

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


def _format_coeff_k_tooltip(value: Any) -> str:
    """Title для k: не более 6 знаков (без двоичного хвоста float вроде 0,998999999…)."""
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=COEFF_K_CALC_DECIMAL_PLACES)
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
    eu_parameters: tuple[tuple[str, str], ...] | None = None,
    id_energy_zone: int | None = None,
) -> list[SummaryEntity]:
    out: list[SummaryEntity] = []
    for regional_district in _load_new_territories_regional_districts():
        res_id = _res_id_for_nt_rd(regional_district, south_ues_id)
        eus_param: list[EnergyUnit] | None = None
        if res_id is not None:
            res_obj = next(
                (r for r in regional_district.regional_energy_systems if r.id == res_id),
                None,
            )
            eus = _energy_units_for_federal_district_subject(
                regional_district.energy_units,
                res_id,
                res_energy_units=getattr(res_obj, "energy_units", None) if res_obj else None,
            )
            eus_param = eus or None
        out.append(
            _build_regional_district_entity(
                regional_district,
                depth=rd_depth,
                energy_units=eus_param,
                parameters=subject_parameters,
                eu_parameters=eu_parameters,
                ues_id=south_ues_id,
                res_id=res_id,
                id_federal_district=id_federal_district_for_rd,
                id_energy_zone=id_energy_zone,
            )
        )
    return out


def _south_ues_base_res_subtree_insert_index(
    summary_rows: list[dict[str, Any]],
    south_ues_id: int,
) -> int | None:
    """Индекс вставки блока «Новые территории»: сразу после последней РЭС «ОЭС Юга без НТ»."""
    insert_at: int | None = None
    in_base_south = False
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if not in_base_south:
            if (
                row.get("show_entity_cell")
                and row.get("entity_kind") == "perimeter_variant"
                and row.get("id_union_energy_system") == south_ues_id
                and legacy_nt_group_for_perimeter_code(row.get("perimeter_variant_code"))
                == CODE_WITHOUT_NT
            ):
                in_base_south = True
                block = max(int(row.get("entity_rowspan") or 1), 1)
                insert_at = i + block
                i = insert_at
                continue
            i += 1
            continue
        if row.get("show_entity_cell"):
            if row.get("id_union_energy_system") != south_ues_id:
                return insert_at
            # Следующий вариант периметра той же ОЭС (напр. «с НТ») — граница поддерева «без НТ».
            if (
                row.get("entity_kind") == "perimeter_variant"
                and legacy_nt_group_for_perimeter_code(row.get("perimeter_variant_code"))
                != CODE_WITHOUT_NT
            ):
                return insert_at
            if row.get("pd_pd_aggregation_level_row"):
                return insert_at
            block = max(int(row.get("entity_rowspan") or 1), 1)
            insert_at = i + block
            i = insert_at
            continue
        i += 1
    return insert_at


def _inject_south_ues_nt_rows_after_res(
    summary_rows: list[dict[str, Any]],
    *,
    years: list[int],
    rounding_digits: int,
    avg_temp_uses_global_rounding: bool = False,
) -> None:
    """После всех РЭС «ОЭС Юга без НТ» — блок «Новые территории» (скрыт до кнопки «+ НТ»)."""
    if not summary_rows or not years:
        return
    south = _find_union_energy_system_by_name("оэс юга")
    if south is None:
        return
    south_ues_id = int(south.id)
    if any(
        row.get("pd_pd_aggregation_level_row")
        and row.get("id_union_energy_system") == south_ues_id
        and str(row.get("entity_label") or "").strip() == _NEW_TERRITORIES_NAME
        for row in summary_rows
    ):
        return
    nt_entity = _build_nt_under_south_res_level_entity_oes(
        south_ues_id,
        _get_federal_district_by_name(_NEW_TERRITORIES_NAME),
    )
    if nt_entity is None:
        return
    nt_rows = _flatten_entity(
        nt_entity,
        years,
        rounding_digits,
        avg_temp_uses_global_rounding=avg_temp_uses_global_rounding,
    )
    if not nt_rows:
        return
    insert_at = _south_ues_base_res_subtree_insert_index(summary_rows, south_ues_id)
    if insert_at is None:
        return
    summary_rows[insert_at:insert_at] = nt_rows


def _build_nt_under_south_res_level_entity_oes(
    south_ues_id: int,
    nt_fd: FederalDistrict | None,
    *,
    ues_depth: int = 0,
) -> SummaryEntity | None:
    children = _build_nt_subject_entities_for_under_south(
        south_ues_id=south_ues_id,
        rd_depth=ues_depth + 2,
        subject_parameters=PARAMETERS_NT_SUBJECT_OES_SUMMARY,
        eu_parameters=PARAMETERS_WITH_OES_EES_AND_ES,
    )
    if not children:
        return None
    if nt_fd is None:
        nt_fd = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    return SummaryEntity(
        label=getattr(nt_fd, "name", None) or _NEW_TERRITORIES_NAME,
        depth=ues_depth + 1,
        parameters=tuple(),
        demand_rows=[],
        entity_kind="aggregation_level",
        children=children,
        demand_model_name=None,
        parent_fk_column=None,
        parent_id=None,
        id_union_energy_system=south_ues_id,
    )


def _build_south_ues_base_group_entity(
    south: UnionEnergySystem,
    *,
    ues_depth: int = 0,
) -> SummaryEntity:
    """Дерево РЭС/субъектов ОЭС Юга (без строки параметров на уровне ОЭС)."""
    child_entities = [
        _build_regional_energy_system_entity(
            res,
            ues_id=south.id,
            ues_depth=ues_depth,
        )
        for res in sorted(south.regional_energy_systems, key=_sort_by_name)
        if _is_valid_named_item(res)
    ]
    return SummaryEntity(
        label=south.name or "",
        depth=ues_depth,
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
    binding = resolve_entity_perimeter_variants(
        ENTITY_KIND_RUSSIA_FEDERATION,
        RUSSIA_FEDERATION_AGGREGATE_NAME,
    )
    model = RussiaFederationDemandParameter
    mn = model.__name__
    out: list[SummaryEntity] = []
    for code, demand_rows in _demand_row_groups_for_oes_top_aggregate(
        model,
        None,
        None,
        binding=binding,
    ):
        label = _summary_variant_entity_label(
            binding,
            RUSSIA_FEDERATION_AGGREGATE_NAME,
            code,
            ENTITY_KIND_RUSSIA_FEDERATION,
            RUSSIA_FEDERATION_AGGREGATE_NAME,
        )
        out.append(
            SummaryEntity(
                label=label,
                depth=0,
                parameters=PARAMETERS_RUSSIA_OES_SUMMARY,
                demand_rows=demand_rows,
                entity_kind="oes_top_aggregate",
                demand_model_name=mn,
                parent_fk_column=None,
                parent_id=None,
                perimeter_variant_code=code,
                summary_perimeter_variant_row=True,
            )
        )
    return out


def _build_centralized_zone_perimeter_entities(
    *,
    parameters: tuple[tuple[str, str], ...] | None = None,
) -> list[SummaryEntity]:
    """Строки «ЦЗ России» по привязке centralized_zone (с/без НТ на сводках ОЭС / ФО / ЭЗ).

    Варианты периметра — ``o1_with_nt`` / ``o1_without_nt`` (как в каталоге модуля «Спрос»).
    Подписи строк — «ЦЗ России с/без НТ» (метка О-1 только в столбце варианта периметра).
    """
    binding = resolve_entity_perimeter_binding(
        ENTITY_KIND_CENTRALIZED_ZONE,
        CENTRALIZED_ZONE_AGGREGATE_NAME,
    )
    model = CentralizedZoneDemandParameter
    mn = model.__name__
    row_parameters = (
        parameters if parameters is not None else PARAMETERS_CZ_FO_SUMMARY
    )
    out: list[SummaryEntity] = []
    groups = _demand_row_groups_for_oes_top_aggregate(
        model,
        None,
        None,
        binding=binding,
    )
    # Предпочитаем О-1 с/без НТ; иначе обычные with_nt / without_nt.
    o1_groups = [
        (code, demand_rows)
        for code, demand_rows in groups
        if code
        and is_o1_perimeter_variant_code(code)
        and _pd_nt_group_for_variant_code(code) in ("with_nt", "without_nt")
    ]
    if o1_groups:
        groups = o1_groups
    else:
        groups = [
            (code, demand_rows)
            for code, demand_rows in groups
            if code
            and not is_o1_perimeter_variant_code(code)
            and _pd_nt_group_for_variant_code(code) in ("with_nt", "without_nt")
        ]
    for code, demand_rows in groups:
        label = _summary_variant_entity_label(
            binding,
            CENTRALIZED_ZONE_AGGREGATE_NAME,
            code,
            ENTITY_KIND_CENTRALIZED_ZONE,
            CENTRALIZED_ZONE_AGGREGATE_NAME,
        )
        out.append(
            SummaryEntity(
                label=label,
                depth=0,
                parameters=row_parameters,
                demand_rows=demand_rows,
                entity_kind="centralized_zone",
                demand_model_name=mn,
                parent_fk_column=None,
                parent_id=None,
                perimeter_variant_code=code,
                summary_perimeter_variant_row=True,
            )
        )
    if out:
        return out
    return [
        _standalone_entity(
            CENTRALIZED_ZONE_AGGREGATE_NAME,
            model,
            row_parameters,
            entity_kind="centralized_zone",
        )
    ]


def _build_ees_perimeter_entities() -> list[SummaryEntity]:
    """Строки «ЭЭС России» (EesRussiaDemandParameter) по привязке entity_kind=ees_russia."""
    binding = resolve_entity_perimeter_variants(
        ENTITY_KIND_EES_RUSSIA,
        EES_RUSSIA_AGGREGATE_NAME,
    )
    model = EesRussiaDemandParameter
    mn = model.__name__

    def _entity(vcode: str | None, label: str, demand_rows: list[Any] | None = None) -> SummaryEntity:
        return SummaryEntity(
            label=label,
            depth=0,
            parameters=PARAMETERS_EES_AGGREGATE_OES_SUMMARY,
            demand_rows=(
                demand_rows
                if demand_rows is not None
                else dps.get_demand_rows(
                    model,
                    None,
                    None,
                    perimeter_variant_code=vcode,
                )
            ),
            entity_kind="oes_top_aggregate",
            demand_model_name=mn,
            parent_fk_column=None,
            parent_id=None,
            perimeter_variant_code=vcode,
            summary_perimeter_variant_row=True,
        )

    variants = _demand_row_groups_for_oes_top_aggregate(
        model,
        None,
        None,
        binding=binding,
    )
    if not variants:
        return []

    return [
        _entity(
            code,
            _summary_variant_entity_label(
                binding,
                EES_RUSSIA_AGGREGATE_NAME,
                code,
                ENTITY_KIND_EES_RUSSIA,
                EES_RUSSIA_AGGREGATE_NAME,
            ),
            demand_rows,
        )
        for code, demand_rows in variants
    ]


def _build_ees_russia_perimeter_entities(
    *,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_EES_RUSSIA_OES_SUMMARY,
) -> list[SummaryEntity]:
    """Тип энергосистемы «ЕЭС России» (EnergySystemType): строки вариантов периметра без вложенного дерева."""
    est = _get_energy_system_type_by_name(EES_UNIFIED_REF_NAME)
    model = EnergySystemTypeDemandParameter
    mn = model.__name__
    est_id = int(est.id) if est is not None else None
    fk_col = "id_energy_system_type"

    def _demand_rows(vcode: str | None) -> list[Any]:
        if est_id is None:
            return []
        return _demand_rows_for_perimeter_variant_entity(
            model,
            fk_col,
            est_id,
            vcode,
        )

    def _variant_entity(
        label: str,
        vcode: str | None,
        demand_rows: list[Any] | None = None,
    ) -> SummaryEntity:
        return SummaryEntity(
            label=label,
            depth=0,
            parameters=parameters,
            demand_rows=demand_rows if demand_rows is not None else _demand_rows(vcode),
            entity_kind="oes_top_aggregate",
            demand_model_name=mn,
            parent_fk_column=fk_col,
            parent_id=est_id,
            perimeter_variant_code=vcode,
            summary_perimeter_variant_row=True,
        )

    binding = resolve_entity_perimeter_variants(
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        EES_UNIFIED_REF_NAME,
    )
    variants = _demand_row_groups_for_oes_top_aggregate(
        model,
        fk_col,
        est_id,
        binding=binding,
    )
    if not variants:
        return []
    return [
        _variant_entity(
            _summary_variant_entity_label(
                binding,
                EES_UNIFIED_REF_NAME,
                vcode,
                ENTITY_KIND_ENERGY_SYSTEM_TYPE,
                EES_UNIFIED_REF_NAME,
            ),
            vcode,
            demand_rows,
        )
        for vcode, demand_rows in variants
    ]


def _inject_perimeter_variant_entities(
    entities: list[SummaryEntity],
    *,
    entity_kind: str,
    ues_depth: int = 0,
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
            base = _build_south_ues_base_group_entity(parent, ues_depth=ues_depth)
            res_children = list(base.children)
            territorial_children = list(res_children)
            variant_defs = _demand_row_groups_for_all_binding_variants(
                UnionEnergySystemDemandParameter,
                "id_union_energy_system",
                parent_id,
                binding=binding,
            )
            base_code = _territorial_children_base_variant_code(binding)
            if base_code is None and variant_defs:
                base_code = variant_defs[0][0]
            variant_entities: list[SummaryEntity] = []
            for vcode, demand_rows in variant_defs:
                children: list[SummaryEntity] = []
                if vcode == base_code:
                    children = list(territorial_children)
                label = _summary_variant_entity_label(
                    binding,
                    getattr(parent, "name", None) or "",
                    vcode,
                    binding.entity_kind,
                    binding.entity_name,
                )
                variant_entities.append(
                    SummaryEntity(
                        label=label,
                        depth=ues_depth,
                        parameters=PARAMETERS_UES_OES,
                        demand_rows=demand_rows,
                        entity_kind="perimeter_variant",
                        children=children,
                        demand_model_name=ues_mn,
                        parent_fk_column="id_union_energy_system",
                        parent_id=parent_id,
                        id_union_energy_system=parent_id,
                        perimeter_variant_code=vcode,
                        summary_perimeter_variant_row=True,
                    )
                )
            if not variant_entities:
                continue
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
        eu_parameters=PARAMETERS_ENERGY_UNIT_FD_SUMMARY,
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
    id_union_energy_system: int | None = None,
) -> SummaryEntity | None:
    """Ветка «Новые территории» на сводке по энергозонам: заголовок как у ТИТЭС + субъекты РФ."""
    federal_district = _get_federal_district_by_name(_NEW_TERRITORIES_NAME)
    south_ues_id = id_union_energy_system
    if south_ues_id is None:
        south = _find_south_union_energy_system()
        if south is not None and getattr(south, "id", None) is not None:
            south_ues_id = int(south.id)
    if south_ues_id is None:
        return None

    rd_depth = subject_depth if subject_depth is not None else depth + 1
    children = _build_nt_subject_entities_for_under_south(
        south_ues_id=south_ues_id,
        rd_depth=rd_depth,
        subject_parameters=PARAMETERS_RES,
        eu_parameters=PARAMETERS_RES,
        id_federal_district_for_rd=getattr(federal_district, "id", None),
        id_energy_zone=id_energy_zone,
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
        id_federal_district=getattr(federal_district, "id", None),
        id_energy_zone=id_energy_zone,
        id_union_energy_system=south_ues_id,
    )


def _build_ues_entities_filtered(
    ues_predicate: Callable[[UnionEnergySystem], bool],
    *,
    always_show_subject_row_under_res: bool = False,
    ues_depth: int = 0,
    res_parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_AND_EES,
    rd_parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_EES_AND_ES,
    eu_parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_UNIT_OES_SUMMARY,
    chukotka_territorial_in_subject: bool = False,
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
                ues_depth=ues_depth,
                res_parameters=res_parameters,
                rd_parameters=rd_parameters,
                eu_parameters=eu_parameters,
                chukotka_territorial_in_subject=chukotka_territorial_in_subject,
            )
            for res in sorted(ues.regional_energy_systems, key=_sort_by_name)
            if _is_valid_named_item(res)
        ]
        if _is_south_oes_name(getattr(ues, "name", None)):
            continue
        entities.append(
            SummaryEntity(
                label=ues.name,
                depth=ues_depth,
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
    ues_depth: int = 0,
    res_parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_AND_EES,
    rd_parameters: tuple[tuple[str, str], ...] = PARAMETERS_WITH_OES_EES_AND_ES,
    eu_parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_UNIT_OES_SUMMARY,
    chukotka_territorial_in_subject: bool = False,
) -> SummaryEntity:
    res_depth = ues_depth + 1
    rd_depth = ues_depth + 2
    eu_depth = ues_depth + 2
    regional_districts = [
        regional_district
        for regional_district in sorted(res.regional_districts, key=_sort_by_name)
        if _is_valid_named_item(regional_district)
    ]
    # Один субъект в РЭС: строки субъекта в дереве не дублируем (сразу ЭУ), но id субъекта нужен
    # для фильтров сводки ds_rd и для согласованного матчинга листьев при ds_res+ds_rd.
    single_rd_id: int | None = regional_districts[0].id if len(regional_districts) == 1 else None

    subject_children: list[SummaryEntity]
    if chukotka_territorial_in_subject and _is_chukotka_res(res) and len(regional_districts) == 1:
        rd0 = regional_districts[0]
        subject_entity = _build_regional_district_entity(
            rd0,
            depth=rd_depth,
            energy_units=_energy_units_for_federal_district_subject(
                rd0.energy_units,
                res.id,
                res_energy_units=res.energy_units,
            ),
            parameters=rd_parameters,
            ues_id=ues_id,
            res_id=res.id,
        )
        territorial_entity = replace(
            _build_chukotka_territorial_boundaries_subject_entity(subject_entity),
            depth=rd_depth,
        )
        subject_children = [territorial_entity, subject_entity]
    elif len(regional_districts) > 1:
        # Строки субъектов внутри РЭС — при двух и более субъектах (как на сводке потребления ЭЭ).
        # Сводка по ОЭС: для субъектов РФ не показываем «на ФО» и «на централизованную зону»
        subject_children = [
            _build_regional_district_entity(
                regional_district,
                depth=rd_depth,
                energy_units=_energy_units_for_federal_district_subject(
                    regional_district.energy_units,
                    res.id,
                    res_energy_units=res.energy_units,
                ),
                parameters=rd_parameters,
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
                depth=rd_depth,
                energy_units=_energy_units_for_federal_district_subject(
                    rd0.energy_units,
                    res.id,
                    res_energy_units=res.energy_units,
                ),
                parameters=rd_parameters,
                ues_id=ues_id,
                res_id=res.id,
            )
        ]
    else:
        if len(regional_districts) == 1:
            rd0 = regional_districts[0]
            energy_units = _energy_units_for_federal_district_subject(
                rd0.energy_units,
                res.id,
                res_energy_units=res.energy_units,
            )
            if not energy_units:
                energy_units = _sort_energy_units_non_dz_first(res.energy_units)
        else:
            energy_units = _sort_energy_units_non_dz_first(res.energy_units)
        subject_children = _build_energy_unit_entities(
            energy_units,
            depth=eu_depth,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res.id,
            id_regional_district=single_rd_id,
            parameters=eu_parameters,
        )

    return SummaryEntity(
        label=res.name,
        depth=res_depth,
        parameters=res_parameters,
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
    res_parameters: tuple[tuple[str, str], ...] = PARAMETERS_RES,
) -> SummaryEntity:
    """РЭС внутри энергозоны: при одном субъекте в зоне — ЭС под субъектом; при нескольких — только ЭС без строк субъектов."""
    regional_districts = sorted(
        [rd for rd in regional_districts_in_zone if _is_valid_named_item(rd)],
        key=_sort_by_name,
    )
    all_res_districts = [
        rd for rd in (res.regional_districts or []) if _is_valid_named_item(rd)
    ]
    in_zone_ids = {rd.id for rd in regional_districts}

    def _rd_outside_blocks_full_res(rd: RegionalDistrict) -> bool:
        """Субъект вне этой зоны блокирует полный показатель РЭС, кроме «не указано»."""
        if rd.id in in_zone_ids:
            return False
        ez = getattr(rd, "energy_zone", None)
        if ez is None:
            return False
        ez_name = (getattr(ez, "name", None) or "").strip().casefold()
        ez_number = str(getattr(ez, "number", None) or "").strip().casefold()
        return ez_name not in PLACEHOLDER_NAMES and ez_number not in PLACEHOLDER_NAMES

    # Полный показатель РЭС берём, если ни один субъект не привязан к *другой*
    # реальной энергозоне (привязка к «не указано» не мешает — как у НАО до исправления).
    fully_in_zone = bool(in_zone_ids) and not any(
        _rd_outside_blocks_full_res(rd) for rd in all_res_districts
    )
    subject_children: list[SummaryEntity]
    if len(regional_districts) > 1:
        # Сводка по энергозонам: при нескольких субъектах в РЭС не показываем строки по субъектам —
        # только энергоузлы РЭС в зоне (как при одном субъекте), без промежуточного уровня «субъект».
        combined_eus: list[EnergyUnit] = []
        seen_eu_ids: set[int] = set()
        for regional_district in regional_districts:
            for eu in _energy_units_for_federal_district_subject(
                regional_district.energy_units,
                res.id,
                res_energy_units=res.energy_units,
            ):
                euid = getattr(eu, "id", None)
                if euid is None or euid in seen_eu_ids:
                    continue
                seen_eu_ids.add(euid)
                combined_eus.append(eu)
        combined_eus = _sort_energy_units_non_dz_first(combined_eus)
        subject_children = _build_energy_unit_entities(
            combined_eus,
            depth=2,
            id_energy_zone=energy_zone_id,
            id_regional_energy_system=res.id,
        )
    elif len(regional_districts) == 1:
        subject_children = _build_energy_unit_entities(
            _energy_units_for_federal_district_subject(
                regional_districts[0].energy_units,
                res.id,
                res_energy_units=res.energy_units,
            ),
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
        parameters=res_parameters,
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
        ez_res_fully_in_zone=fully_in_zone,
    )


def _build_energy_zone_entities(
    *, ez_max_extended_parameters: bool = False
) -> list[SummaryEntity]:
    ez_parameters = (
        PARAMETERS_ENERGY_ZONE_MAX
        if ez_max_extended_parameters
        else PARAMETERS_ENERGY_ZONE
    )
    res_parameters = (
        PARAMETERS_RES_EZ_MAX if ez_max_extended_parameters else PARAMETERS_RES
    )
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
        selectinload(RegionalEnergySystem.regional_districts).selectinload(
            RegionalDistrict.energy_zone
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
                    res,
                    rds_in_zone,
                    energy_zone_id=ez.id,
                    res_parameters=res_parameters,
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
                parameters=ez_parameters,
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
        south = _find_south_union_energy_system()
        south_ues_id = int(south.id) if south is not None else None
        nt_entity = _build_new_territories_energy_zone_entity(
            depth=1,
            subject_depth=2,
            entity_kind="child",
            id_energy_zone=inject_zone_id,
            id_union_energy_system=south_ues_id,
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
    """Строки сводки по ОЭС: одна сущность на каждую синхронную зону.

    «Первая синхронная зона» — варианты периметра with_nt / without_nt (как у «Россия»).

    Порядок — по ``SynchronousArea.display_order`` (как в справочнике), затем имя и id.
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
            binding = resolve_entity_perimeter_variants("synchronous_area", sa.name)
            variants = _demand_row_groups_for_all_binding_variants(
                SynchronousAreaDemandParameter,
                "id_synchronous_area",
                sa.id,
                binding=binding,
            )
            if variants:
                for vcode, demand_rows in variants:
                    lbl = _summary_variant_entity_label(
                        binding,
                        base_label,
                        vcode,
                        "synchronous_area",
                        sa.name,
                    )
                    entities.append(
                        SummaryEntity(
                            label=lbl,
                            depth=depth,
                            parameters=PARAMETERS_FIRST_SYNCHRONOUS_AREA_OES_SUMMARY,
                            demand_rows=demand_rows,
                            entity_kind="synchronous_area",
                            demand_model_name=mn,
                            parent_fk_column="id_synchronous_area",
                            parent_id=sa.id,
                            id_synchronous_area=sa.id,
                            perimeter_variant_code=vcode,
                            summary_perimeter_variant_row=True,
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
                    perimeter_variant_code=None,
                ),
                entity_kind="synchronous_area",
                demand_model_name=mn,
                parent_fk_column="id_synchronous_area",
                parent_id=sa.id,
                id_synchronous_area=sa.id,
                perimeter_variant_code=None,
            )
        )
    return entities


def _energy_unit_belongs_to_placeholder_res(energy_unit: EnergyUnit) -> bool:
    """Энергорайон без привязки к ЕЭС/ТИТЭС (РЭС «не указано» в справочнике)."""
    res_obj = getattr(energy_unit, "regional_energy_system", None)
    res_name = (getattr(res_obj, "name", None) or "").strip().casefold()
    return res_name in PLACEHOLDER_NAMES


def _energy_unit_summary_perimeter_variant_code(
    energy_unit: EnergyUnit,
) -> str | None:
    """Вариант периметра для загрузки строк энергорайона на сводке.

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


def _demand_rows_for_energy_unit_summary(energy_unit: EnergyUnit) -> list[Any]:
    """Строки параметров энергорайона: сначала вариант О-1 для ДЗ, иначе базовый периметр."""
    pvc = _energy_unit_summary_perimeter_variant_code(energy_unit)
    rows = dps.get_demand_rows(
        EnergyUnitDemandParameter,
        "id_energy_unit",
        energy_unit.id,
        perimeter_variant_code=pvc,
    )
    if not rows and pvc is not None:
        rows = dps.get_demand_rows(
            EnergyUnitDemandParameter,
            "id_energy_unit",
            energy_unit.id,
            perimeter_variant_code=None,
        )
    return rows


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


def _sort_energy_units_non_dz_first(
    energy_units: list[EnergyUnit] | tuple[EnergyUnit, ...],
) -> list[EnergyUnit]:
    """Сначала энергорайоны РЭС, затем децентрализованная зона (РЭС «не указано»)."""
    regular: list[EnergyUnit] = []
    decentralized: list[EnergyUnit] = []
    seen_ids: set[int] = set()
    for energy_unit in energy_units:
        if not _is_valid_named_item(energy_unit):
            continue
        euid = getattr(energy_unit, "id", None)
        if euid is not None:
            if euid in seen_ids:
                continue
            seen_ids.add(int(euid))
        if _energy_unit_belongs_to_placeholder_res(energy_unit):
            decentralized.append(energy_unit)
        else:
            regular.append(energy_unit)
    regular.sort(key=_sort_by_name)
    decentralized.sort(key=_sort_by_name)
    return regular + decentralized


def _energy_units_for_federal_district_subject(
    energy_units: list[EnergyUnit],
    regional_energy_system_id: int,
    *,
    res_energy_units: list[EnergyUnit] | None = None,
) -> list[EnergyUnit]:
    """Энергорайоны субъекта для строки РЭС на сводках по ФО и ОЭС.

    Сначала — энергорайоны, привязанные к выбранной РЭС; в конце — энергорайоны с РЭС
    «не указано», не входящие в энергосистемы (как на /energy_consumption/summary/oes/).
    """
    pool: list[EnergyUnit] = []
    seen_pool: set[int] = set()
    for source in (energy_units, res_energy_units or ()):
        for eu in source:
            euid = getattr(eu, "id", None)
            if euid is not None:
                if int(euid) in seen_pool:
                    continue
                seen_pool.add(int(euid))
            pool.append(eu)

    res_bound = [
        eu
        for eu in pool
        if getattr(eu, "id_regional_energy_system", None) == regional_energy_system_id
        and _is_valid_named_item(eu)
    ]
    dz_extra = [
        eu
        for eu in pool
        if _energy_unit_belongs_to_placeholder_res(eu) and _is_valid_named_item(eu)
    ]
    bound_ids = {getattr(eu, "id", None) for eu in res_bound}
    dz_extra = [eu for eu in dz_extra if getattr(eu, "id", None) not in bound_ids]
    res_bound.sort(key=_sort_by_name)
    dz_extra.sort(key=_sort_by_name)
    return res_bound + dz_extra


_OES_SUMMARY_HIDDEN_TITES_UES_LABELS_CF = frozenset(
    {_TITES_EAST_UES_NAME_CF, _TITES_SIBERIA_UES_NAME_CF}
)


def _summary_row_base_label_cf(row: dict[str, Any]) -> str:
    base, _ = _pd_strip_variant_suffixes_from_label(str(row.get("entity_label") or ""))
    return base.casefold()


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
        row.get("demand_model_name") == UnionEnergySystemDemandParameter.__name__
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


def _is_hidden_tites_ues_summary_entity(entity: SummaryEntity) -> bool:
    return (
        entity.demand_model_name == UnionEnergySystemDemandParameter.__name__
        and _is_oes_summary_hidden_tites_union_energy_system_label(entity.label)
    )


def _unwrap_hidden_tites_ues_entities(
    entities: list[SummaryEntity],
) -> list[SummaryEntity]:
    """Промотирует РЭС/ниже из скрытых ОЭС «ТИТЭС Сибири» / «ТИТЭС Востока» (без строк самой ОЭС)."""
    out: list[SummaryEntity] = []
    for entity in entities:
        if _is_hidden_tites_ues_summary_entity(entity):
            for child in entity.children:
                out.append(_shift_summary_entity_depth(child, -1))
        else:
            out.append(entity)
    return out


def _iter_summary_entity_energy_unit_descendants(
    entity: SummaryEntity,
) -> list[SummaryEntity]:
    if entity.demand_model_name == EnergyUnitDemandParameter.__name__:
        return [entity]
    out: list[SummaryEntity] = []
    for child in entity.children:
        out.extend(_iter_summary_entity_energy_unit_descendants(child))
    return out


def _chukotka_territorial_boundaries_variant_enabled() -> bool:
    """Вариант «в территориальных границах» только при явной привязке в каталоге БД."""
    codes = perimeter_variant_codes_for_entity("regional_district", _CHUKOTKA_RD_LABEL)
    return CODE_TERRITORIAL_BOUNDARIES in codes


def _is_oes_summary_hidden_chukotka_rd_entity_row(row: dict[str, Any]) -> bool:
    """Субъект «Чукотский АО» (базовый вариант, не «…в территориальных границах»)."""
    if str(row.get("entity_label") or "").strip() != _CHUKOTKA_RD_LABEL:
        return False
    if str(row.get("entity_kind") or "") == "chukotka_territorial_boundaries":
        return False
    return row.get("perimeter_variant_code") is None


def _is_oes_summary_hidden_chukotka_territorial_entity_row(row: dict[str, Any]) -> bool:
    """Строка «Чукотский АО (в территориальных границах)» без привязки варианта в каталоге."""
    if _chukotka_territorial_boundaries_variant_enabled():
        return False
    if str(row.get("entity_kind") or "") == "chukotka_territorial_boundaries":
        return True
    return (
        str(row.get("entity_label") or "").strip() == _CHUKOTKA_TERRITORIAL_BOUNDARIES_LABEL
    )


def filter_oes_summary_hidden_chukotka_rd_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """На /summary/oes/ не показывать скрытые строки субъекта «Чукотский АО»."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            out.append(dict(row))
            i += 1
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        head = block[0]
        if _is_oes_summary_hidden_chukotka_rd_entity_row(
            head
        ) or _is_oes_summary_hidden_chukotka_territorial_entity_row(head):
            i += block_size
            continue
        for j, r in enumerate(block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(block)
            out.append(rc)
        i += block_size
    return out


def filter_oes_summary_hidden_tites_union_energy_system_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """На /summary/oes/ убирает строки ОЭС «ТИТЭС Сибири» / «ТИТЭС Востока» и «Проверка для …»."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("pd_pd_aggregation_level_row"):
            out.append(dict(row))
            i += 1
            continue
        if _is_oes_summary_hidden_tites_verification_row(row):
            i += max(int(row.get("entity_rowspan") or 1), 1)
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        filtered_block = [
            r
            for r in block
            if not _is_oes_summary_hidden_tites_union_energy_system_own_row(r)
        ]
        if not filtered_block:
            i += block_size
            continue
        for j, r in enumerate(filtered_block):
            rc = dict(r)
            rc["show_entity_cell"] = j == 0
            rc["entity_rowspan"] = len(filtered_block)
            out.append(rc)
        i += block_size
    return out


def _is_chukotka_res(res: RegionalEnergySystem) -> bool:
    return str(getattr(res, "name", None) or "").strip() == _CHUKOTKA_RES_LABEL


def _normalized_union_energy_system_label_cf(label: object) -> str:
    return str(label or "").strip().casefold().replace(" ", "")


def _chukotka_energy_units_max_power_sums(
    summary_rows: list[dict[str, Any]],
    years: list[int],
) -> list[float | None]:
    """Сумма «Максимальное потребление мощности, МВт» по энергорайонам ЭС Чукотского АО."""
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
        existing_calc = None
        for j in range(block_start, min(block_start + block_span, len(summary_rows))):
            if summary_rows[j].get("parameter_key") == "calculated_max_power_mw":
                existing_calc = summary_rows[j]
                break
        existing_values = list((existing_calc or {}).get("year_values") or [])
        existing_tooltips = list((existing_calc or {}).get("year_numeric_tooltips") or [])
        for ix in range(n_y):
            if not _formula_year_applies_to_row_perimeter_variant(block0, int(years[ix])):
                year_values.append(
                    existing_values[ix] if ix < len(existing_values) else "—"
                )
                year_tooltips.append(
                    existing_tooltips[ix] if ix < len(existing_tooltips) else ""
                )
                continue
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
                    "parameter_label": "Расчетное максимальное потребление мощности, МВт",
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


def _build_tites_entity() -> SummaryEntity | None:
    """Корень ТИТЭС + ДЗ — порядок веток как на /energy_consumption/summary/oes/."""
    children = _unwrap_hidden_tites_ues_entities(
        _build_ues_entities_filtered(
            _is_tites_branch,
            ues_depth=1,
            res_parameters=PARAMETERS_TITES_OES_SUMMARY,
            rd_parameters=PARAMETERS_TITES_OES_SUMMARY,
            eu_parameters=PARAMETERS_TITES_OES_SUMMARY,
            chukotka_territorial_in_subject=(
                _chukotka_territorial_boundaries_variant_enabled()
            ),
        )
    )
    seen_eu_ids: set[int] = set()
    for child in children:
        for desc in _iter_summary_entity_energy_unit_descendants(child):
            euid = getattr(desc, "id_energy_unit", None)
            if euid is not None:
                seen_eu_ids.add(int(euid))
    for extra in _build_tites_sakha_yakutia_extra_energy_unit_entities():
        euid = extra.id_energy_unit
        if euid is not None and int(euid) in seen_eu_ids:
            continue
        children.append(extra)
        if euid is not None:
            seen_eu_ids.add(int(euid))
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
    eu_parameters: tuple[tuple[str, str], ...] | None = None,
    ues_id: int | None = None,
    res_id: int | None = None,
    id_federal_district: int | None = None,
    id_energy_zone: int | None = None,
) -> SummaryEntity:
    eu_params = eu_parameters if eu_parameters is not None else parameters
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
            energy_units
            if energy_units is not None
            else (
                _energy_units_for_federal_district_subject(
                    regional_district.energy_units,
                    res_id,
                )
                if res_id is not None
                else _sort_energy_units_non_dz_first(regional_district.energy_units)
            ),
            depth=depth + 1,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res_id,
            id_regional_district=regional_district.id,
            id_federal_district=id_federal_district,
            id_energy_zone=id_energy_zone,
            parameters=eu_params,
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
    id_federal_district: int | None = None,
    id_energy_zone: int | None = None,
    is_decentralized_zone_energy_unit: bool = False,
    parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_UNIT_OES_SUMMARY,
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
        is_dz = is_decentralized_zone_energy_unit or _energy_unit_belongs_to_placeholder_res(
            energy_unit
        )
        out.append(
            SummaryEntity(
                label=energy_unit.name,
                depth=depth,
                parameters=parameters,
                demand_rows=_demand_rows_for_energy_unit_summary(energy_unit),
                entity_kind="child",
                demand_model_name=EnergyUnitDemandParameter.__name__,
                parent_fk_column="id_energy_unit",
                parent_id=energy_unit.id,
                id_union_energy_system=ues,
                id_regional_energy_system=res_id,
                id_regional_district=rd_id,
                id_federal_district=id_federal_district,
                id_energy_unit=energy_unit.id,
                id_energy_zone=id_energy_zone,
                is_decentralized_zone_energy_unit=is_dz,
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


def _build_federal_district_res_entity(
    res: RegionalEnergySystem,
    *,
    federal_district_id: int,
    fd_rd_ids: set[int] | frozenset[int],
    res_parameters: tuple[tuple[str, str], ...] = PARAMETERS_RES_FO_COEFF,
    subject_parameters: tuple[tuple[str, str], ...] = PARAMETERS_SUBJECT_FD_SUMMARY,
    eu_parameters: tuple[tuple[str, str], ...] = PARAMETERS_ENERGY_UNIT_FD_SUMMARY,
) -> SummaryEntity | None:
    """РЭС под ФО: при >1 субъекте в ФО — субъекты с энергорайонами; при одном — ЭР под РЭС."""
    rd_in_fd = [
        rd
        for rd in sorted(res.regional_districts, key=_sort_by_name)
        if rd.id in fd_rd_ids and _is_valid_named_item(rd)
    ]
    rd_ids_in_fd = frozenset(rd.id for rd in rd_in_fd)
    if not rd_ids_in_fd:
        return None

    ues_id = getattr(res, "id_union_energy_system", None)
    single_rd_id = rd_in_fd[0].id if len(rd_in_fd) == 1 else None
    subject_children: list[SummaryEntity] = []
    if len(rd_in_fd) > 1:
        subject_children = [
            _build_regional_district_entity(
                rd,
                depth=2,
                energy_units=_energy_units_for_federal_district_subject(
                    rd.energy_units,
                    res.id,
                    res_energy_units=getattr(res, "energy_units", None),
                ),
                parameters=subject_parameters,
                eu_parameters=eu_parameters,
                ues_id=ues_id,
                res_id=res.id,
                id_federal_district=federal_district_id,
            )
            for rd in rd_in_fd
        ]
    elif len(rd_in_fd) == 1:
        rd0 = rd_in_fd[0]
        eus = _energy_units_for_federal_district_subject(
            rd0.energy_units,
            res.id,
            res_energy_units=getattr(res, "energy_units", None),
        )
        if not eus:
            eus = _sort_energy_units_non_dz_first(getattr(res, "energy_units", None) or [])
        subject_children = _build_energy_unit_entities(
            eus,
            depth=2,
            id_union_energy_system=ues_id,
            id_regional_energy_system=res.id,
            id_regional_district=rd0.id,
            id_federal_district=federal_district_id,
            parameters=eu_parameters,
        )

    return SummaryEntity(
        label=res.name,
        depth=1,
        parameters=res_parameters,
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
        id_federal_district=federal_district_id,
        id_regional_energy_system=res.id,
        id_regional_district=single_rd_id,
        id_union_energy_system=ues_id,
        fo_res_linked_regional_district_ids=rd_ids_in_fd,
    )


def _build_federal_district_entities_by_res(
    *,
    fd_parameters: tuple[tuple[str, str], ...] = PARAMETERS_FEDERAL_DISTRICT,
    res_parameters: tuple[tuple[str, str], ...] = PARAMETERS_RES_FO_COEFF,
) -> list[SummaryEntity]:
    """Дерево ФО → РЭС → (субъекты при >1) → энергорайоны."""
    query = FederalDistrict.query.options(
        selectinload(FederalDistrict.regional_districts)
        .selectinload(RegionalDistrict.regional_energy_systems)
        .selectinload(RegionalEnergySystem.regional_districts)
        .selectinload(RegionalDistrict.energy_units)
        .selectinload(EnergyUnit.regional_energy_system),
        selectinload(FederalDistrict.regional_districts)
        .selectinload(RegionalDistrict.regional_energy_systems)
        .selectinload(RegionalEnergySystem.energy_units)
        .selectinload(EnergyUnit.regional_energy_system),
        selectinload(FederalDistrict.regional_districts)
        .selectinload(RegionalDistrict.energy_units)
        .selectinload(EnergyUnit.regional_energy_system),
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

        fd_rd_ids = {
            rd.id
            for rd in federal_district.regional_districts
            if _is_valid_named_item(rd)
        }
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
            res_entity = _build_federal_district_res_entity(
                res,
                federal_district_id=federal_district.id,
                fd_rd_ids=fd_rd_ids,
                res_parameters=res_parameters,
                subject_parameters=PARAMETERS_SUBJECT_FD_SUMMARY,
                eu_parameters=PARAMETERS_ENERGY_UNIT_FD_SUMMARY,
            )
            if res_entity is None:
                continue
            child_entities.append(res_entity)
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
                res_parameters=res_parameters,
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
                parameters=fd_parameters,
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
        e.entity_kind in ("group", "perimeter_variant")
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
    # Префикс «Сводной таблицы» (ЦЗ / ЭЭС / ЕЭС / СЗ) — только без территориального фильтра.
    if e.entity_kind in ("centralized_zone", "oes_top_aggregate", "synchronous_area"):
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
    if e.entity_kind in (
        "ees_russia",
        "centralized_zone",
        "oes_top_aggregate",
        "synchronous_area",
    ):
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
    # Префикс «Сводной таблицы» (ЦЗ / ЭЭС / ЕЭС / СЗ) — только без территориального фильтра.
    if e.entity_kind in (
        "ees_russia",
        "centralized_zone",
        "oes_top_aggregate",
        "synchronous_area",
    ):
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


