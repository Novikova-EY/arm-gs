# -*- coding: utf-8 -*-
"""Максимум потребления мощности для балансов — со сводки /power_demand/summary/oes/.

Берём строку «Максимальное потребление мощности, МВт» варианта «без НТ»
(ЕЭС, СЗ, ОЭС). Калининградская СЗ — как на сводке: сохранённый вариант, без пары с/без НТ.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
from app.common.perimeter_variant.registry import is_kaliningrad_sync_area_entity_name
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
)
from app.energy_balance.services.power_balance_installed_capacity_services import (
    _match_named_object,
    resolve_sheet_territory,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
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
from app.power_demand.services.demand_parameter_services import (
    get_demand_rows,
    get_demand_rows_for_summary_block,
    peek_stored_perimeter_variant_code_for_parent,
)

_KIND_DEMAND = {
    "est": (EnergySystemTypeDemandParameter, "id_energy_system_type"),
    "ues": (UnionEnergySystemDemandParameter, "id_union_energy_system"),
    "sa": (SynchronousAreaDemandParameter, "id_synchronous_area"),
    "res": (RegionalEnergySystemDemandParameter, "id_regional_energy_system"),
    "eu": (EnergyUnitDemandParameter, "id_energy_unit"),
}

_FIRST_SA_EXTRA_CODES = (
    "without_nt_without_gaes_kaliningrad",
    "without_nt_with_gaes_kaliningrad",
    "without_nt_without_gaes_with_kaliningrad_es",
    "without_nt_with_gaes_with_kaliningrad_es",
    "without_nt_without_gaes_without_kaliningrad",
    "without_nt_with_gaes_without_kaliningrad",
    "without_nt_without_gaes_without_kaliningrad_es",
    "without_nt_with_gaes_without_kaliningrad_es",
)


def _norm_label(text: str | None) -> str:
    return (
        (text or "")
        .casefold()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )


def _is_first_sz_name(name: str | None) -> bool:
    n = _norm_label(name)
    if "калининг" in n:
        return False
    return ("1" in n or "перв" in n) and "сз" in n


def _rows_have_max_power(rows: list[Any]) -> bool:
    for row in rows or []:
        if getattr(row, "is_historical_maximum", False):
            continue
        if getattr(row, "max_power_consumption_mw", None) is not None:
            return True
    return False


def _is_unspecified(name: str | None) -> bool:
    n = _norm_label(name)
    return (not n) or ("не указано" in n)


def year_values_from_max_power_rows(
    rows: list[Any],
    years: list[int],
) -> dict[int, Decimal]:
    """max_power_consumption_mw по календарным годам (без исторического максимума)."""
    wanted = {int(year) for year in years}
    result: dict[int, Decimal] = {}
    for row in rows or []:
        if getattr(row, "is_historical_maximum", False):
            continue
        year = getattr(row, "year_number", None)
        if year is None:
            continue
        year_int = int(year)
        if year_int not in wanted:
            continue
        value = getattr(row, "max_power_consumption_mw", None)
        if value is None:
            continue
        result[year_int] = Decimal(str(value))
    return result


def _named_id(objects: list[Any], *, needles: tuple[str, ...], exclude: tuple[str, ...] = ()) -> dict[str, Any] | None:
    matched = _match_named_object(objects, needles=needles, exclude=exclude)
    if matched is None:
        return None
    return {"id": int(matched.id), "name": getattr(matched, "name", None)}


def _sa_by_slug(wanted_slug: str) -> dict[str, Any] | None:
    from app.energy_balance.services.power_balance_page_services import _sz_layout_and_slug

    try:
        objects = list(get_synchronous_area_list_full() or [])
    except Exception:
        objects = []
    for obj in objects:
        obj_id = getattr(obj, "id", None)
        name = getattr(obj, "name", None)
        if obj_id is None or int(obj_id) <= 0 or _is_unspecified(name):
            continue
        _layout, slug = _sz_layout_and_slug(
            str(name or ""),
            int(obj_id),
            name_full=getattr(obj, "name_full", None),
            number=getattr(obj, "number", None),
        )
        if slug == wanted_slug:
            full = str(getattr(obj, "name_full", None) or "").strip()
            return {"kind": "sa", "id": int(obj_id), "name": full or name}
    return None


def _resolve_ees_est() -> dict[str, Any] | None:
    try:
        objects = list(get_energy_system_type_list_full() or [])
    except Exception:
        objects = []
    matched = _named_id(objects, needles=("еэс",), exclude=("титес", "децентрализ"))
    if matched is None:
        return None
    return {"kind": "est", **matched}


def resolve_demand_max_territory(sheet: dict[str, Any]) -> dict[str, Any] | None:
    """Территория листа для чтения max_power: id и kind из версии БД."""
    territory = sheet.get("territory") or {}
    entity_id = territory.get("id")
    kind = territory.get("kind")
    if entity_id is not None and kind:
        try:
            return {
                "kind": str(kind),
                "id": int(entity_id),
                "name": territory.get("name") or sheet.get("sheet_name"),
            }
        except (TypeError, ValueError):
            pass

    slug = str(sheet.get("slug") or "")
    layout = str(sheet.get("layout") or "")
    group = str(sheet.get("group") or "")

    if group == "ees" or layout == "ees_rossii" or slug == "ees-rossii":
        return _resolve_ees_est()
    if layout == "sz1" or slug == "1-sz-ees":
        return _sa_by_slug("1-sz-ees")
    if layout == "kaliningrad" or "kaliningrad" in slug:
        return _sa_by_slug("kaliningradskaya-sz-ees") or resolve_sheet_territory(
            "kaliningradskaya-sz-ees"
        )
    if slug == "2-sz-ees-vostok" or (group == "sz" and layout == "oes_vostok"):
        return _sa_by_slug("2-sz-ees-vostok") or resolve_sheet_territory("2-sz-ees-vostok")
    if slug:
        return resolve_sheet_territory(slug)
    return None


def _demand_rows_without_nt(
    model: Any,
    fk_column: str,
    parent_id: int,
    *,
    kind: str,
    name: str | None,
) -> list[Any]:
    if kind == "sa" and is_kaliningrad_sync_area_entity_name(name):
        stored = peek_stored_perimeter_variant_code_for_parent(model, fk_column, parent_id)
        return get_demand_rows(
            model,
            fk_column,
            parent_id,
            perimeter_variant_code=stored,
        )
    rows = get_demand_rows_for_summary_block(
        model,
        fk_column,
        parent_id,
        display_perimeter_variant_code=CODE_WITHOUT_NT,
    )
    if _rows_have_max_power(rows):
        return rows
    if kind == "sa" and _is_first_sz_name(name):
        by_year: dict[int, Any] = {}
        codes: list[str | None] = list(_FIRST_SA_EXTRA_CODES)
        stored = peek_stored_perimeter_variant_code_for_parent(model, fk_column, parent_id)
        if stored:
            codes.insert(0, stored)
        for code in codes:
            for row in get_demand_rows(
                model,
                fk_column,
                parent_id,
                perimeter_variant_code=code,
            ):
                if getattr(row, "is_historical_maximum", False):
                    continue
                year = getattr(row, "year_number", None)
                if year is None:
                    continue
                y = int(year)
                if y not in by_year or (
                    getattr(by_year[y], "max_power_consumption_mw", None) is None
                    and getattr(row, "max_power_consumption_mw", None) is not None
                ):
                    by_year[y] = row
        if by_year:
            return list(by_year.values())
    return rows


def load_power_balance_demand_max_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """demand_max по листам БМ из max_power сводки ОЭС (вариант без НТ)."""
    if not years or not sheets:
        return {}
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug or sheet.get("skip_table"):
            continue
        territory = resolve_demand_max_territory(sheet)
        if territory is None:
            continue
        kind = str(territory.get("kind") or "")
        spec = _KIND_DEMAND.get(kind)
        if spec is None:
            continue
        model, fk_column = spec
        try:
            parent_id = int(territory["id"])
        except (TypeError, ValueError, KeyError):
            continue
        rows = _demand_rows_without_nt(
            model,
            fk_column,
            parent_id,
            kind=kind,
            name=territory.get("name") or sheet.get("sheet_name"),
        )
        year_map = year_values_from_max_power_rows(rows, years)
        if year_map:
            inputs[slug] = {"demand_max": year_map}
    return inputs
