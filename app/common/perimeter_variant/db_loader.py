# -*- coding: utf-8 -*-
"""Загрузка каталога и привязок из gs_sys (с fallback)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.common.perimeter_variant.constants import (
    EC_SUMMARY_BLOCK_ENTITY_KIND,
    FALLBACK_ENTITY_PERIMETER_BINDINGS,
    FALLBACK_PERIMETER_VARIANT_BY_CODE,
    is_tree_display_variant_code,
)
from app.common.perimeter_variant.registry_types import (
    EntityPerimeterBinding,
    PerimeterVariantDefinition,
)
from app.extensions import db


@dataclass(frozen=True, slots=True)
class LoadedPerimeterCatalog:
    variants_by_code: dict[str, PerimeterVariantDefinition]
    bindings: tuple[EntityPerimeterBinding, ...]
    source: str


_cache: LoadedPerimeterCatalog | None = None


def invalidate_perimeter_catalog_cache() -> None:
    global _cache
    _cache = None


def ensure_tree_perimeter_variants_in_db(*, username: str = "system") -> int:
    """Добавляет в справочник отсутствующие базовые коды дерева (with_nt, without_nt, …)."""
    from app.common.models.perimeter_variant import PerimeterVariant

    existing_codes = {v.code for v in PerimeterVariant.query.all()}
    added = 0
    for code, vdef in FALLBACK_PERIMETER_VARIANT_BY_CODE.items():
        if not is_tree_display_variant_code(code) or code in existing_codes:
            continue
        db.session.add(
            PerimeterVariant(
                code=code,
                label_suffix=vdef.label_suffix,
                effective_from_year=vdef.effective_from_year,
                effective_to_year=vdef.effective_to_year,
                database_version_id=None,
                created_by=username,
                modified_by=username,
            )
        )
        added += 1
    if not added:
        return 0
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return 0
    invalidate_perimeter_catalog_cache()
    return added


def _load_variants_from_db() -> dict[str, PerimeterVariantDefinition]:
    from app.common.models.perimeter_variant import PerimeterVariant

    variants_orm = PerimeterVariant.query.order_by(
        PerimeterVariant.display_order.asc().nullslast(),
        PerimeterVariant.code.asc(),
        PerimeterVariant.database_version_id.asc().nullsfirst(),
        PerimeterVariant.id.asc(),
    ).all()
    by_code: dict[str, PerimeterVariantDefinition] = {}
    for v in variants_orm:
        if v.code in by_code:
            continue
        by_code[v.code] = PerimeterVariantDefinition(
            code=v.code,
            label_suffix=v.label_suffix,
            effective_from_year=v.effective_from_year,
            effective_to_year=v.effective_to_year,
        )
    return by_code


def _load_bindings_from_db(
    by_code: dict[str, PerimeterVariantDefinition],
) -> tuple[EntityPerimeterBinding, ...]:
    from app.common.models.perimeter_variant import (
        EntityPerimeterBinding as EntityPerimeterBindingModel,
        PerimeterVariant,
    )

    id_to_code = {int(v.id): v.code for v in PerimeterVariant.query.all()}

    bindings_orm = EntityPerimeterBindingModel.query.order_by(
        EntityPerimeterBindingModel.entity_kind.asc(),
        EntityPerimeterBindingModel.entity_name.asc(),
        EntityPerimeterBindingModel.sort_order.asc(),
        EntityPerimeterBindingModel.database_version_id.asc().nullsfirst(),
        EntityPerimeterBindingModel.id.asc(),
    ).all()

    groups: dict[tuple[str, str], list[PerimeterVariantDefinition]] = {}
    prefixes: dict[tuple[str, str], str | None] = {}
    entity_names: dict[tuple[str, str], str] = {}
    for b in bindings_orm:
        if b.entity_kind == EC_SUMMARY_BLOCK_ENTITY_KIND:
            continue
        code = id_to_code.get(int(b.id_perimeter_variant))
        if not code or code not in by_code:
            continue
        key = (b.entity_kind, b.entity_name.strip())
        entity_names[key] = b.entity_name.strip()
        groups.setdefault(key, []).append(by_code[code])
        if b.label_prefix and key not in prefixes:
            prefixes[key] = b.label_prefix

    binding_list: list[EntityPerimeterBinding] = []
    for (ek, en), vlist in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        seen_codes: set[str] = set()
        unique_variants: list[PerimeterVariantDefinition] = []
        for vdef in vlist:
            if vdef.code in seen_codes:
                continue
            seen_codes.add(vdef.code)
            unique_variants.append(vdef)
        binding_list.append(
            EntityPerimeterBinding(
                entity_kind=ek,
                entity_name_cf=en.casefold(),
                label_prefix=prefixes.get((ek, en)) or en,
                entity_name=entity_names.get((ek, en), en),
                variants=tuple(unique_variants),
            )
        )
    return tuple(binding_list)


def list_perimeter_variant_ui_options() -> list[dict[str, str]]:
    """Опции для select: все коды справочника (та же выборка, что на /perimeter-variants/)."""
    opts: list[dict[str, str]] = []
    try:
        from app.common.models.perimeter_variant import PerimeterVariant

        rows = PerimeterVariant.query.order_by(
            PerimeterVariant.display_order.asc().nullslast(),
            PerimeterVariant.code.asc(),
            PerimeterVariant.database_version_id.asc().nullsfirst(),
            PerimeterVariant.id.asc(),
        ).all()
        if rows:
            seen_codes: set[str] = set()
            for v in rows:
                if v.code in seen_codes:
                    continue
                seen_codes.add(v.code)
                opts.append({"code": v.code, "label": v.label_suffix})
            return opts
    except Exception:
        db.session.rollback()

    catalog = load_perimeter_catalog()
    for code, vdef in sorted(
        catalog.variants_by_code.items(),
        key=lambda item: (item[1].label_suffix.casefold(), item[0]),
    ):
        opts.append({"code": code, "label": vdef.label_suffix})
    return opts


def load_perimeter_catalog(*, force: bool = False) -> LoadedPerimeterCatalog:
    global _cache
    if not force and _cache is not None:
        return _cache

    try:
        by_code = _load_variants_from_db()
        if by_code:
            try:
                binding_list = _load_bindings_from_db(by_code)
            except Exception:
                db.session.rollback()
                binding_list = ()
            catalog = LoadedPerimeterCatalog(by_code, binding_list, "database")
            _cache = catalog
            return catalog
    except Exception:
        db.session.rollback()

    catalog = LoadedPerimeterCatalog(
        dict(FALLBACK_PERIMETER_VARIANT_BY_CODE),
        FALLBACK_ENTITY_PERIMETER_BINDINGS,
        "fallback",
    )
    _cache = catalog
    return catalog
