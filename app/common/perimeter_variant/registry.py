# -*- coding: utf-8 -*-
"""Публичный API каталога вариантов периметра (БД + fallback)."""
from __future__ import annotations

from app.common.perimeter_variant.constants import (
    CENTRALIZED_ZONE_AGGREGATE_NAME,
    CODE_O1,
    CODE_WITHOUT_CRIMEA_SEV,
    CODE_WITHOUT_NT,
    CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    CODE_WITH_NT,
    CODE_WITH_NT_WITH_GAES,
    CYRILLIC_O1_VARIANT_CODE,
    ENTITY_KIND_CENTRALIZED_ZONE,
    ENTITY_KIND_EES_RUSSIA,
    ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    ENTITY_KIND_RUSSIA_FEDERATION,
    EES_RUSSIA_AGGREGATE_NAME,
    FALLBACK_ENTITY_PERIMETER_BINDINGS,
    FALLBACK_PERIMETER_VARIANT_BY_CODE,
    RUSSIA_FEDERATION_AGGREGATE_NAME,
    is_tree_display_variant_code,
)
from app.common.perimeter_variant.db_loader import load_perimeter_catalog
from app.common.perimeter_variant.registry_types import (
    EntityPerimeterBinding,
    PerimeterVariantDefinition,
)

__all__ = [
    "CODE_WITH_NT",
    "CODE_WITHOUT_NT",
    "CODE_WITH_NT_WITH_GAES",
    "CODE_WITHOUT_NT_WITH_GAES",
    "CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES",
    "CODE_O1",
    "CODE_WITHOUT_CRIMEA_SEV",
    "CODE_WITHOUT_NT_WITH_KALININGRAD_ES",
    "CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES",
    "EntityPerimeterBinding",
    "PerimeterVariantDefinition",
    "ENTITY_KIND_CHOICES",
    "perimeter_entity_context_for_model",
    "entity_perimeter_bindings",
    "filter_query_by_perimeter_variant",
    "model_supports_perimeter_variant",
    "is_o1_perimeter_variant_code",
    "normalize_perimeter_variant_code",
    "perimeter_variant_applies_to_year",
    "perimeter_variant_applies_to_year_code",
    "perimeter_variant_year_bounds_for_code",
    "resolve_catalog_o1_perimeter_variant_code",
    "perimeter_variant_definitions",
    "resolve_entity_perimeter_variants",
    "resolve_entity_perimeter_binding",
    "perimeter_variant_codes_for_entity",
    "perimeter_variant_options_for_entity",
    "perimeter_variant_display_label",
    "perimeter_variant_display_label_for_entity",
    "validate_perimeter_variant_for_entity",
    "is_tree_display_variant_code",
    "ordered_tree_variants_for_display",
    "variant_label_for_entity",
    "perimeter_catalog_source",
]


def _catalog():
    return load_perimeter_catalog()


def perimeter_catalog_source() -> str:
    return _catalog().source


def entity_perimeter_bindings() -> tuple[EntityPerimeterBinding, ...]:
    return _catalog().bindings


def perimeter_variant_definitions() -> dict[str, PerimeterVariantDefinition]:
    return dict(_catalog().variants_by_code)


def PERIMETER_VARIANT_BY_CODE() -> dict[str, PerimeterVariantDefinition]:
    return _catalog().variants_by_code


# Для `from registry import PERIMETER_VARIANT_BY_CODE` как dict — ленивый прокси через __getattr__ в loader consumers
# Проще: в demand_summary импортировать perimeter_variant_definitions()


def resolve_entity_perimeter_variants(
    entity_kind: str,
    entity_name: str | None,
) -> EntityPerimeterBinding | None:
    cf = (entity_name or "").strip().casefold()
    if not cf:
        return None
    for b in entity_perimeter_bindings():
        if b.entity_kind == entity_kind and b.entity_name_cf == cf:
            return b
    return None


def resolve_entity_perimeter_binding(
    entity_kind: str | None,
    entity_name: str | None,
) -> EntityPerimeterBinding | None:
    """Привязка вариантов периметра: каталог БД, затем по ``entity_kind``, затем fallback."""
    if not entity_kind:
        return None
    name = (entity_name or "").strip()
    if name:
        binding = resolve_entity_perimeter_variants(entity_kind, name)
        if binding is not None:
            return binding
    for b in entity_perimeter_bindings():
        if b.entity_kind == entity_kind and (not name or b.matches_name(name)):
            return b
    for b in FALLBACK_ENTITY_PERIMETER_BINDINGS:
        if b.entity_kind == entity_kind and (not name or b.matches_name(name)):
            return b
    return None


def perimeter_variant_codes_for_entity(
    entity_kind: str | None,
    entity_name: str | None,
) -> tuple[str, ...]:
    """Разрешённые коды для сущности: только явно заведённые привязки в БД."""
    if not entity_kind or not (entity_name or "").strip():
        return ()
    binding = resolve_entity_perimeter_variants(str(entity_kind), entity_name)
    if binding is None:
        return ()
    return tuple(v.code for v in binding.variants)


def perimeter_variant_options_for_entity(
    entity_kind: str | None,
    entity_name: str | None,
) -> list[dict[str, str]]:
    codes = perimeter_variant_codes_for_entity(entity_kind, entity_name)
    defs = _catalog().variants_by_code
    opts: list[dict[str, str]] = []
    for code in codes:
        vdef = defs.get(code)
        opts.append({"code": code, "label": vdef.label_suffix if vdef else code})
    return opts


def validate_perimeter_variant_for_entity(
    entity_kind: str | None,
    entity_name: str | None,
    raw: object,
) -> str | None:
    pvc = normalize_perimeter_variant_code(raw)
    allowed = perimeter_variant_codes_for_entity(entity_kind, entity_name)
    if pvc is None:
        if not allowed:
            return None
        label = entity_name or "выбранной сущности"
        raise ValueError(f"Для «{label}» нужно выбрать один из привязанных вариантов периметра.")
    if pvc in allowed:
        return pvc
    if not allowed:
        label = entity_name or "выбранной сущности"
        raise ValueError(
            f"Для «{label}» варианты периметра не привязаны. "
            "Сначала настройте привязку на странице вариантов периметра."
        )
    labels = ", ".join(str(code) for code in allowed)
    label = entity_name or "выбранной сущности"
    raise ValueError(
        f"Вариант периметра {pvc} не разрешён для «{label}». "
        f"Разрешены только: {labels}."
    )


def variant_label_for_entity(binding: EntityPerimeterBinding, variant: PerimeterVariantDefinition) -> str:
    prefix = binding.display_label_prefix
    if variant.label_suffix.startswith(prefix) or (
        prefix and variant.label_suffix.lower().startswith(prefix.lower())
    ):
        return variant.label_suffix
    if prefix:
        return f"{prefix} {variant.label_suffix}"
    return variant.label_suffix


def ordered_tree_variants_for_display(binding: EntityPerimeterBinding) -> tuple[PerimeterVariantDefinition, ...]:
    """Порядок вариантов периметра для дерева сводки задаётся порядком привязок."""
    return tuple(v for v in binding.variants if is_tree_display_variant_code(v.code))


def perimeter_variant_display_label(code: str | None) -> str:
    """Человекочитаемая подпись варианта периметра по коду (для таблиц и форм)."""
    if code is None:
        return ""
    s = str(code).strip()
    if not s:
        return ""
    vdef = _catalog().variants_by_code.get(s)
    if vdef is not None:
        return vdef.label_suffix
    if is_o1_perimeter_variant_code(s):
        resolved = resolve_catalog_o1_perimeter_variant_code()
        o1_def = _catalog().variants_by_code.get(resolved)
        if o1_def is not None:
            return o1_def.label_suffix
    return s


def perimeter_variant_display_label_for_entity(
    code: str | None,
    entity_kind: str | None,
    entity_name: str | None,
) -> str:
    """Подпись варианта периметра с учётом привязки сущности (``entity_kind`` + имя)."""
    if code is None:
        return ""
    s = str(code).strip()
    if not s:
        return ""
    if entity_kind:
        binding = resolve_entity_perimeter_binding(str(entity_kind), entity_name)
        if binding is not None:
            for vdef in binding.variants:
                if vdef.code == s:
                    suffix = (vdef.label_suffix or "").strip()
                    if suffix and suffix.casefold() != s.casefold():
                        return suffix
                    fb = FALLBACK_PERIMETER_VARIANT_BY_CODE.get(s)
                    if fb is not None:
                        return fb.label_suffix
                    return suffix or s
    return perimeter_variant_display_label(s)


def perimeter_variant_year_bounds_for_code(
    code: str | None,
) -> tuple[int | None, int | None]:
    """Год с / год по варианта периметра (из справочника, с fallback из constants)."""
    if code is None:
        return None, None
    s = str(code).strip()
    if not s:
        return None, None
    vdef = _catalog().variants_by_code.get(s)
    fb = FALLBACK_PERIMETER_VARIANT_BY_CODE.get(s)
    if vdef is None:
        if fb is None:
            return None, None
        return fb.effective_from_year, fb.effective_to_year
    from_year = vdef.effective_from_year
    to_year = vdef.effective_to_year
    if from_year is None and to_year is None and fb is not None:
        from_year = fb.effective_from_year
        to_year = fb.effective_to_year
    return from_year, to_year


def perimeter_variant_applies_to_year(variant: PerimeterVariantDefinition, year: int) -> bool:
    if variant.effective_from_year is not None and year < variant.effective_from_year:
        return False
    if variant.effective_to_year is not None and year > variant.effective_to_year:
        return False
    return True


def perimeter_variant_applies_to_year_code(code: str | None, year: int) -> bool:
    """True, если год попадает в период действия варианта (или границы не заданы)."""
    if code is None:
        return True
    s = str(code).strip()
    if not s:
        return True
    vdef = _catalog().variants_by_code.get(s)
    if vdef is None:
        return True
    return perimeter_variant_applies_to_year(vdef, int(year))


def model_supports_perimeter_variant(model: type) -> bool:
    return hasattr(model, "perimeter_variant_code")


def is_o1_perimeter_variant_code(code: object) -> bool:
    """True для вариантов, код которых содержит ``o1`` (включая кириллическую ``о1``)."""
    if code is None:
        return False
    s = str(code).strip().casefold().replace(CYRILLIC_O1_VARIANT_CODE[0], "o")
    return CODE_O1 in s


def resolve_catalog_o1_perimeter_variant_code() -> str:
    """Код варианта О-1, как он заведён в текущем справочнике."""
    defs = _catalog().variants_by_code
    if CODE_O1 in defs:
        return CODE_O1
    if CYRILLIC_O1_VARIANT_CODE in defs:
        return CYRILLIC_O1_VARIANT_CODE
    for code in defs:
        if is_o1_perimeter_variant_code(code):
            return code
    return CODE_O1


def normalize_perimeter_variant_code(raw: object, *, known_only: bool = True) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if known_only and s not in _catalog().variants_by_code:
        if is_o1_perimeter_variant_code(s):
            resolved = resolve_catalog_o1_perimeter_variant_code()
            if resolved in _catalog().variants_by_code:
                return resolved
        raise ValueError(f"Неизвестный вариант периметра: {s!r}")
    return s


_AGGREGATE_MODEL_PERIMETER_ENTITY: dict[str, tuple[str, str]] = {
    "RussiaFederationDemandParameter": (
        ENTITY_KIND_RUSSIA_FEDERATION,
        RUSSIA_FEDERATION_AGGREGATE_NAME,
    ),
    "RussiaFederationEnergyConsumptionParameter": (
        ENTITY_KIND_RUSSIA_FEDERATION,
        RUSSIA_FEDERATION_AGGREGATE_NAME,
    ),
    "EesRussiaDemandParameter": (ENTITY_KIND_EES_RUSSIA, EES_RUSSIA_AGGREGATE_NAME),
    "EesRussiaEnergyConsumptionParameter": (
        ENTITY_KIND_EES_RUSSIA,
        EES_RUSSIA_AGGREGATE_NAME,
    ),
    "EesDemandParameter": (ENTITY_KIND_EES_RUSSIA, EES_RUSSIA_AGGREGATE_NAME),
    "EesEnergyConsumptionParameter": (ENTITY_KIND_EES_RUSSIA, EES_RUSSIA_AGGREGATE_NAME),
    "CentralizedZoneDemandParameter": (
        ENTITY_KIND_CENTRALIZED_ZONE,
        CENTRALIZED_ZONE_AGGREGATE_NAME,
    ),
    "CentralizedZoneEnergyConsumptionParameter": (
        ENTITY_KIND_CENTRALIZED_ZONE,
        CENTRALIZED_ZONE_AGGREGATE_NAME,
    ),
}


def perimeter_entity_context_for_model(
    model_name: str,
    *,
    parent_fk_column: str | None = None,
    parent_id: int | None = None,
) -> tuple[str, str] | None:
    """
    (entity_kind, entity_name) для привязок периметра по классу модели параметров.

    Агрегаты «Россия», «ЭЭС России», «ЦЗ России» — без FK на refdata.
    ОЭС и прочие территориальные сущности — по parent_id (см. вызывающий код).
    """
    key = (model_name or "").strip()
    if not key:
        return None
    mapped = _AGGREGATE_MODEL_PERIMETER_ENTITY.get(key)
    if mapped is not None:
        return mapped
    parent_lookup: dict[tuple[str, str], tuple[str, str]] = {
        ("EnergySystemTypeDemandParameter", "id_energy_system_type"): (
            ENTITY_KIND_ENERGY_SYSTEM_TYPE,
            "app.refdata.models.energy_systems.energy_system_type_model:EnergySystemType",
        ),
        ("EnergySystemTypeEnergyConsumptionParameter", "id_energy_system_type"): (
            ENTITY_KIND_ENERGY_SYSTEM_TYPE,
            "app.refdata.models.energy_systems.energy_system_type_model:EnergySystemType",
        ),
        ("SynchronousAreaEnergyConsumptionParameter", "id_synchronous_area"): (
            "synchronous_area",
            "app.refdata.models.energy_systems.synchronous_area_model:SynchronousArea",
        ),
        ("UnionEnergySystemDemandParameter", "id_union_energy_system"): (
            "union_energy_system",
            "app.refdata.models.energy_systems.union_energy_system_model:UnionEnergySystem",
        ),
        ("UnionEnergySystemEnergyConsumptionParameter", "id_union_energy_system"): (
            "union_energy_system",
            "app.refdata.models.energy_systems.union_energy_system_model:UnionEnergySystem",
        ),
        ("RegionalEnergySystemEnergyConsumptionParameter", "id_regional_energy_system"): (
            "regional_energy_system",
            "app.refdata.models.energy_systems.regional_energy_system_model:RegionalEnergySystem",
        ),
        ("EnergyZoneEnergyConsumptionParameter", "id_energy_zone"): (
            "energy_zone",
            "app.refdata.models.energy_systems.energy_zone_model:EnergyZone",
        ),
    }
    if parent_fk_column and parent_id is not None:
        lookup = parent_lookup.get((key, parent_fk_column))
        if lookup is not None:
            entity_kind, import_spec = lookup
            module_name, class_name = import_spec.split(":", 1)
            from importlib import import_module

            model = getattr(import_module(module_name), class_name)
            parent = model.query.get(parent_id)
            name = (getattr(parent, "name", None) or "").strip() if parent is not None else ""
            if name:
                return entity_kind, name
    return None


def filter_query_by_perimeter_variant(q, model: type, variant_code: str | None):
    if not model_supports_perimeter_variant(model):
        return q
    if variant_code is None:
        return q.filter(model.perimeter_variant_code.is_(None))
    return q.filter(model.perimeter_variant_code == variant_code)


ENTITY_KIND_CHOICES: tuple[tuple[str, str], ...] = (
    (ENTITY_KIND_CENTRALIZED_ZONE, "ЦЗ России"),
    (ENTITY_KIND_RUSSIA_FEDERATION, "Россия"),
    (ENTITY_KIND_EES_RUSSIA, "ЭЭС России"),
    (
        "energy_system_type",
        "Часть энергосистемы России (ЕЭС России, ТИТЭС, …)",
    ),
    ("synchronous_area", "Синхронная зона"),
    ("union_energy_system", "ОЭС (объединённая энергосистема)"),
    ("federal_district", "Федеральный округ"),
    ("regional_energy_system", "Региональная энергосистема"),
    ("energy_zone", "Энергозона"),
)
