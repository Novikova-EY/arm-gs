# -*- coding: utf-8 -*-
"""Встроенный fallback-каталог (если в БД ещё нет записей)."""
from __future__ import annotations

from app.common.perimeter_variant.registry_types import (
    EntityPerimeterBinding,
    PerimeterVariantDefinition,
)

CODE_WITH_NT = "with_nt"
CODE_WITHOUT_NT = "without_nt"
CODE_WITHOUT_CRIMEA_SEV = "without_crimea_sev"
CODE_WITHOUT_NT_WITH_KALININGRAD_ES = "without_nt_with_kaliningrad_es"
CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES = "without_nt_without_kaliningrad_es"
CODE_WITH_NT_WITH_GAES = "with_nt_with_gaes"
CODE_WITH_NT_WITHOUT_GAES = "with_nt_without_gaes"
CODE_WITHOUT_NT_WITH_GAES = "without_nt_with_gaes"
CODE_WITHOUT_NT_WITHOUT_GAES = "without_nt_without_gaes"
CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES = "without_nt_with_gaes_with_kaliningrad_es"
CODE_O1 = "o1"
CODE_TERRITORIAL_BOUNDARIES = "territorial_boundaries"

# Варианты блоков «с/без заряда ГАЭС» на сводке — не строки дерева ОЭС/ЕЭС.
TREE_EXCLUDED_VARIANT_CODES: frozenset[str] = frozenset(
    {
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    }
)

# Устаревшие коды with_nt / without_nt на сводке → варианты с зарядом ГАЭС в той же НТ-группе.
LEGACY_NT_GROUP_GAES_VARIANT_CANDIDATES: dict[str, tuple[str, ...]] = {
    CODE_WITH_NT: (CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES),
    CODE_WITHOUT_NT: (CODE_WITHOUT_NT_WITH_GAES, CODE_WITHOUT_NT_WITHOUT_GAES),
}


def perimeter_variant_codes_in_legacy_nt_group(code: str | None) -> tuple[str, ...]:
    """Код и связанные GAES-варианты той же группы (с НТ / без НТ) для поиска строк в БД."""
    if not code:
        return ()
    s = str(code).strip()
    if s in LEGACY_NT_GROUP_GAES_VARIANT_CANDIDATES:
        return (s,) + LEGACY_NT_GROUP_GAES_VARIANT_CANDIDATES[s]
    for legacy, gaes_codes in LEGACY_NT_GROUP_GAES_VARIANT_CANDIDATES.items():
        if s in gaes_codes:
            return (legacy,) + gaes_codes
    return (s,)


def is_tree_display_variant_code(code: str | None) -> bool:
    """Исключает варианты блоков «с/без заряда ГАЭС» — они не строки дерева сводки."""
    if not code:
        return False
    return str(code).strip() not in TREE_EXCLUDED_VARIANT_CODES
# В справочнике БД код часто хранится кириллической «о» (U+043E), не латинской «o».
CYRILLIC_O1_VARIANT_CODE = "\u043e1"

# Служебные привязки: какой вариант периметра у блока строк на сводке потребления (не для дерева ОЭС).
EC_SUMMARY_BLOCK_ENTITY_KIND = "ec_summary_block"

# --- entity_kind для привязок периметра (страница /perimeter_variants/) ---
# Агрегаты без строки в refdata (префиксы моделей/таблиц gs_*_russia_federation_*, gs_*_ees_russia_*, gs_*_centralized_zone_*).
ENTITY_KIND_EES_RUSSIA = "ees_russia"
ENTITY_KIND_RUSSIA_FEDERATION = "russia_federation"
ENTITY_KIND_CENTRALIZED_ZONE = "centralized_zone"
# Строка справочника EnergySystemType (Единая энергосистема России — «ЕЭС», не «ЭЭС»).
ENTITY_KIND_ENERGY_SYSTEM_TYPE = "energy_system_type"

# ЭЭС России — электроэнергетические системы России (агрегат, модели EesRussia*, Ees*, …).
EES_RUSSIA_AGGREGATE_NAME = "ЭЭС России"
EES_RUSSIA_AGGREGATE_NAME_CF = "ээс россии"
# ЕЭС России — единая энергосистема (справочник EnergySystemType, имя как в refdata).
EES_UNIFIED_REF_NAME = "ЕЭС России"
EES_UNIFIED_REF_NAME_CF = "еэс россии"

RUSSIA_FEDERATION_AGGREGATE_NAME = "Россия"
RUSSIA_FEDERATION_AGGREGATE_NAME_CF = "россия"
CENTRALIZED_ZONE_AGGREGATE_NAME = "ЦЗ России"
CENTRALIZED_ZONE_AGGREGATE_NAME_CF = "цз россии"

FALLBACK_PERIMETER_VARIANT_BY_CODE: dict[str, PerimeterVariantDefinition] = {
    CODE_WITH_NT: PerimeterVariantDefinition(
        CODE_WITH_NT, "с НТ", effective_from_year=2024
    ),
    CODE_WITHOUT_NT: PerimeterVariantDefinition(
        CODE_WITHOUT_NT, "без НТ"
    ),
    CODE_WITHOUT_CRIMEA_SEV: PerimeterVariantDefinition(
        CODE_WITHOUT_CRIMEA_SEV, "без ЭС РК и г.С"
    ),
    CODE_WITHOUT_NT_WITH_KALININGRAD_ES: PerimeterVariantDefinition(
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        "без НТ (с ЭС Калининградской области)",
        effective_to_year=2024,
    ),
    CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES: PerimeterVariantDefinition(
        CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
        "без НТ (без ЭС Калининградской области)",
        effective_from_year=2025,
    ),
    CODE_O1: PerimeterVariantDefinition(CODE_O1, "О-1"),
    CODE_TERRITORIAL_BOUNDARIES: PerimeterVariantDefinition(
        CODE_TERRITORIAL_BOUNDARIES, "(в территориальных границах)"
    ),
}

FALLBACK_ENTITY_PERIMETER_BINDINGS: tuple[EntityPerimeterBinding, ...] = (
    EntityPerimeterBinding(
        entity_kind="union_energy_system",
        entity_name_cf="оэс юга",
        entity_name="ОЭС Юга",
        label_prefix="ОЭС Юга",
        variants=(
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITH_NT],
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT],
        ),
    ),
    EntityPerimeterBinding(
        entity_kind="federal_district",
        entity_name_cf="южный фо",
        entity_name="Южный ФО",
        label_prefix="Южный ФО",
        variants=(
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITH_NT],
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT],
        ),
    ),
    EntityPerimeterBinding(
        entity_kind="synchronous_area",
        entity_name_cf="первая синхронная зона",
        entity_name="Первая синхронная зона",
        label_prefix="Первая синхронная зона",
        variants=(
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT_WITH_KALININGRAD_ES],
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES],
        ),
    ),
    EntityPerimeterBinding(
        entity_kind=ENTITY_KIND_RUSSIA_FEDERATION,
        entity_name_cf=RUSSIA_FEDERATION_AGGREGATE_NAME_CF,
        entity_name=RUSSIA_FEDERATION_AGGREGATE_NAME,
        label_prefix=RUSSIA_FEDERATION_AGGREGATE_NAME,
        variants=(
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITH_NT],
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT],
        ),
    ),
    EntityPerimeterBinding(
        entity_kind=ENTITY_KIND_EES_RUSSIA,
        entity_name_cf=EES_RUSSIA_AGGREGATE_NAME_CF,
        entity_name=EES_RUSSIA_AGGREGATE_NAME,
        label_prefix=EES_RUSSIA_AGGREGATE_NAME,
        variants=(
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITH_NT],
            FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_WITHOUT_NT],
        ),
    ),
    EntityPerimeterBinding(
        entity_kind="regional_district",
        entity_name_cf="чукотский ао",
        entity_name="Чукотский АО",
        label_prefix="Чукотский АО",
        variants=(FALLBACK_PERIMETER_VARIANT_BY_CODE[CODE_TERRITORIAL_BOUNDARIES],),
    ),
)
