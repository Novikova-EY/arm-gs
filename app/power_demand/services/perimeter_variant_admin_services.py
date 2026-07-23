# -*- coding: utf-8 -*-
"""CRUD справочника вариантов периметра и привязок к сущностям."""
from __future__ import annotations

from typing import Any, Type

from sqlalchemy.exc import IntegrityError

from app.common.perimeter_variant.constants import EC_SUMMARY_BLOCK_ENTITY_KIND
from app.common.perimeter_variant.db_loader import invalidate_perimeter_catalog_cache
from app.common.perimeter_variant.registry import ENTITY_KIND_CHOICES, perimeter_catalog_source
from app.extensions import db
from app.common.models.perimeter_variant import EntityPerimeterBinding, PerimeterVariant
from app.power_demand.services.pd_summary_page_cache import clear_pd_summary_page_cache


def _username() -> str:
    from flask import session

    return session.get("username", "Неизвестный пользователь")


def _invalidate_perimeter_variant_dependent_caches() -> None:
    invalidate_perimeter_catalog_cache()
    clear_pd_summary_page_cache()


def _parameter_models_with_perimeter_variant_code() -> tuple[Type[Any], ...]:
    """Модели PD/EC с колонкой perimeter_variant_code (мягкая ссылка на код варианта)."""
    from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
        CentralizedZoneEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
        EesEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
        EesRussiaEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.energy_area_energy_consumption_parameter_model import (
        EnergyAreaEnergyConsumptionParameter,
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
    from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
        CentralizedZoneDemandParameter,
    )
    from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
        EesDemandParameter,
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
    from app.power_demand.models.territories.federal_district_demand_parameter_model import (
        FederalDistrictDemandParameter,
    )
    from app.power_demand.models.territories.regional_district_demand_parameter_model import (
        RegionalDistrictDemandParameter,
    )
    from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
        RussiaFederationDemandParameter,
    )

    return (
        CentralizedZoneDemandParameter,
        EesDemandParameter,
        EesRussiaDemandParameter,
        EnergySystemTypeDemandParameter,
        EnergyUnitDemandParameter,
        EnergyZoneDemandParameter,
        RegionalEnergySystemDemandParameter,
        SynchronousAreaDemandParameter,
        UnionEnergySystemDemandParameter,
        FederalDistrictDemandParameter,
        RegionalDistrictDemandParameter,
        RussiaFederationDemandParameter,
        CentralizedZoneEnergyConsumptionParameter,
        EesEnergyConsumptionParameter,
        EesRussiaEnergyConsumptionParameter,
        EnergyAreaEnergyConsumptionParameter,
        EnergySystemTypeEnergyConsumptionParameter,
        EnergyUnitEnergyConsumptionParameter,
        EnergyZoneEnergyConsumptionParameter,
        RegionalEnergySystemEnergyConsumptionParameter,
        SynchronousAreaEnergyConsumptionParameter,
        UnionEnergySystemEnergyConsumptionParameter,
        FederalDistrictEnergyConsumptionParameter,
        RegionalDistrictEnergyConsumptionParameter,
        RussiaFederationEnergyConsumptionParameter,
    )


def _purge_dependent_parameter_rows_for_variant_codes(codes: set[str]) -> int:
    """Удаляет строки параметров PD/EC с указанными кодами вариантов периметра."""
    if not codes:
        return 0
    removed = 0
    code_list = list(codes)
    for model in _parameter_models_with_perimeter_variant_code():
        removed += (
            model.query.filter(model.perimeter_variant_code.in_(code_list)).delete(
                synchronize_session=False
            )
        )
    return removed


def _rename_dependent_parameter_rows_for_variant_code(old_code: str, new_code: str) -> int:
    """Переименовывает perimeter_variant_code в строках параметров PD/EC."""
    if not old_code or not new_code or old_code == new_code:
        return 0
    updated = 0
    for model in _parameter_models_with_perimeter_variant_code():
        updated += (
            model.query.filter(model.perimeter_variant_code == old_code).update(
                {model.perimeter_variant_code: new_code},
                synchronize_session=False,
            )
        )
    return updated


def list_variants_for_admin() -> list[PerimeterVariant]:
    try:
        rows = PerimeterVariant.query.order_by(
            PerimeterVariant.display_order.asc().nullslast(),
            PerimeterVariant.code.asc(),
            PerimeterVariant.database_version_id.asc().nullsfirst(),
            PerimeterVariant.id.asc(),
        ).all()
        result: list[PerimeterVariant] = []
        seen_codes: set[str] = set()
        for row in rows:
            if row.code in seen_codes:
                continue
            seen_codes.add(row.code)
            result.append(row)
        return result
    except Exception:
        db.session.rollback()
        return []


def _variant_code_sort_index() -> dict[str, int]:
    """Порядок кодов вариантов как в выпадающем списке на странице админки."""
    return {v.code: idx for idx, v in enumerate(list_variants_for_admin())}


def _entity_kind_sort_index() -> dict[str, int]:
    """Порядок типов сущностей как в выпадающем списке «Тип сущности»."""
    return {ek: idx for idx, (ek, _) in enumerate(ENTITY_KIND_CHOICES)}


def list_bindings_grouped_for_admin() -> list[dict[str, Any]]:
    try:
        rows = EntityPerimeterBinding.query.order_by(
            EntityPerimeterBinding.entity_kind.asc(),
            EntityPerimeterBinding.entity_name.asc(),
            EntityPerimeterBinding.sort_order.asc(),
            EntityPerimeterBinding.database_version_id.asc().nullsfirst(),
            EntityPerimeterBinding.id.asc(),
        ).all()
    except Exception:
        db.session.rollback()
        return []
    variant_order = _variant_code_sort_index()
    entity_kind_order = _entity_kind_sort_index()
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    seen_items: set[tuple[str, str, str]] = set()
    for b in rows:
        if b.entity_kind == EC_SUMMARY_BLOCK_ENTITY_KIND:
            continue
        key = (b.entity_kind, b.entity_name)
        if key not in groups:
            groups[key] = {
                "entity_kind": b.entity_kind,
                "entity_name": b.entity_name,
                "label_prefix": b.label_prefix,
                "items": [],
            }
        if b.label_prefix and not groups[key]["label_prefix"]:
            groups[key]["label_prefix"] = b.label_prefix
        v = b.perimeter_variant
        variant_code = v.code if v else ""
        item_key = (b.entity_kind, b.entity_name, variant_code)
        if item_key in seen_items:
            continue
        seen_items.add(item_key)
        groups[key]["items"].append(
            {
                "binding_id": b.id,
                "sort_order": b.sort_order,
                "variant_code": variant_code,
                "variant_label": v.label_suffix if v else "",
                "effective_from_year": v.effective_from_year if v else None,
                "effective_to_year": v.effective_to_year if v else None,
            }
        )
    for group in groups.values():
        group["items"].sort(
            key=lambda item: (
                variant_order.get(item["variant_code"], 10**9),
                item["variant_code"],
            )
        )
    return sorted(
        groups.values(),
        key=lambda g: (
            entity_kind_order.get(g["entity_kind"], 10**9),
            (g["entity_name"] or "").casefold(),
        ),
    )


def save_variants_from_form(form_data) -> tuple[int, int]:
    """POST: variant_id[], variant_code[], variant_label[], ... Returns (saved, deleted)."""
    user = _username()
    ids = form_data.getlist("variant_id[]")
    codes = form_data.getlist("variant_code[]")
    labels = form_data.getlist("variant_label[]")
    from_years = form_data.getlist("variant_from_year[]")
    to_years = form_data.getlist("variant_to_year[]")
    orders = form_data.getlist("variant_display_order[]")
    notes = form_data.getlist("variant_note[]")
    deletes = {int(x) for x in form_data.getlist("variant_delete[]") if str(x).strip().isdigit()}

    deleted = 0
    codes_to_purge: set[str] = set()
    for did in deletes:
        row = PerimeterVariant.query.get(did)
        if row is None:
            continue
        codes_to_purge.add(row.code)
        duplicate_rows = PerimeterVariant.query.filter(PerimeterVariant.code == row.code).all()
        for duplicate in duplicate_rows:
            db.session.delete(duplicate)
            deleted += 1

    if codes_to_purge:
        _purge_dependent_parameter_rows_for_variant_codes(codes_to_purge)

    saved = 0
    n = max(len(codes), len(labels))
    for i in range(n):
        rid_s = ids[i] if i < len(ids) else ""
        rid = int(rid_s) if str(rid_s).strip().isdigit() else None
        if rid is not None and rid in deletes:
            continue
        code = (codes[i] if i < len(codes) else "").strip()
        label = (labels[i] if i < len(labels) else "").strip()
        if not code and not label:
            continue
        if not code:
            raise ValueError("Код варианта не может быть пустым.")
        if not label:
            raise ValueError(f"Подпись для кода {code!r} не может быть пустой.")

        def _parse_year(raw: str) -> int | None:
            s = str(raw or "").strip()
            if not s:
                return None
            y = int(s)
            if y < 1900 or y > 2200:
                raise ValueError(f"Некорректный год: {y}")
            return y

        fy = _parse_year(from_years[i] if i < len(from_years) else "")
        ty = _parse_year(to_years[i] if i < len(to_years) else "")
        ord_s = orders[i] if i < len(orders) else ""
        disp = int(ord_s) if str(ord_s).strip().isdigit() else None
        note = (notes[i] if i < len(notes) else "").strip() or None
        if rid:
            row = PerimeterVariant.query.get(rid)
            if row is None:
                continue
            old_code = row.code
            rows_to_update = PerimeterVariant.query.filter(PerimeterVariant.code == old_code).all()
            if old_code != code:
                _rename_dependent_parameter_rows_for_variant_code(old_code, code)
        else:
            row = PerimeterVariant()
            row.database_version_id = None
            row.created_by = user
            db.session.add(row)
            rows_to_update = [row]

        for update_row in rows_to_update:
            update_row.code = code
            update_row.label_suffix = label
            update_row.effective_from_year = fy
            update_row.effective_to_year = ty
            update_row.display_order = disp
            update_row.note = note
            update_row.database_version_id = None
            update_row.modified_by = user
        saved += 1

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("Дубликат кода варианта.") from exc
    _invalidate_perimeter_variant_dependent_caches()
    return saved, deleted


def add_binding_from_form(form_data) -> None:
    entity_kind = (form_data.get("bind_entity_kind") or "").strip()
    entity_name = (form_data.get("bind_entity_name") or "").strip()
    label_prefix = (form_data.get("bind_label_prefix") or "").strip() or None
    variant_id_raw = form_data.get("bind_variant_id")
    if not entity_kind or not entity_name or not variant_id_raw:
        raise ValueError("Укажите тип сущности, наименование и вариант периметра.")
    variant_id = int(variant_id_raw)
    v = PerimeterVariant.query.get(variant_id)
    if v is None:
        raise ValueError("Вариант периметра не найден.")
    existing = (
        EntityPerimeterBinding.query.join(PerimeterVariant)
        .filter(
            EntityPerimeterBinding.entity_kind == entity_kind,
            EntityPerimeterBinding.entity_name == entity_name,
            PerimeterVariant.code == v.code,
        )
    )
    if existing.first():
        raise ValueError("Такая привязка уже существует.")

    from sqlalchemy import func

    max_ord = (
        db.session.query(func.max(EntityPerimeterBinding.sort_order))
        .filter(
            EntityPerimeterBinding.entity_kind == entity_kind,
            EntityPerimeterBinding.entity_name == entity_name,
        )
        .scalar()
    )
    row = EntityPerimeterBinding(
        entity_kind=entity_kind,
        entity_name=entity_name,
        label_prefix=label_prefix or entity_name,
        id_perimeter_variant=variant_id,
        sort_order=int(max_ord or 0) + 1,
        database_version_id=None,
        created_by=_username(),
        modified_by=_username(),
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError("Не удалось создать привязку.") from exc
    _invalidate_perimeter_variant_dependent_caches()


def delete_bindings(binding_ids: list[int]) -> int:
    n = 0
    for bid in binding_ids:
        row = EntityPerimeterBinding.query.get(bid)
        if row is None:
            continue
        variant_code = row.perimeter_variant.code if row.perimeter_variant else None
        if variant_code:
            rows_to_delete = (
                EntityPerimeterBinding.query.join(PerimeterVariant)
                .filter(
                    EntityPerimeterBinding.entity_kind == row.entity_kind,
                    EntityPerimeterBinding.entity_name == row.entity_name,
                    PerimeterVariant.code == variant_code,
                )
                .all()
            )
        else:
            rows_to_delete = [row]
        for delete_row in rows_to_delete:
            db.session.delete(delete_row)
            n += 1
    db.session.commit()
    _invalidate_perimeter_variant_dependent_caches()
    return n


def admin_page_context() -> dict[str, Any]:
    return {
        "variants": list_variants_for_admin(),
        "binding_groups": list_bindings_grouped_for_admin(),
        "entity_kind_choices": ENTITY_KIND_CHOICES,
        "catalog_source": perimeter_catalog_source(),
    }
