# -*- coding: utf-8 -*-
"""Пагинация сводок потребления по территориальным секциям (ОЭС / ФО / энергозоны)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import request

UES_MODEL_NAME = "UnionEnergySystemEnergyConsumptionParameter"
FD_MODEL_NAME = "FederalDistrictEnergyConsumptionParameter"
EZ_MODEL_NAME = "EnergyZoneEnergyConsumptionParameter"

TITES_SUFFIX_LABEL_FRAGMENT = "ТИТЭС"
_NEW_TERRITORIES_LABEL_FRAGMENT = "новые территории"

PAGINATION_SCOPES: frozenset[str] = frozenset({"oes", "fo", "ez"})

DEFAULT_ENTITY_PAGE_SIZE = 2
MAX_ENTITY_PAGE_SIZE = 8
ALL_ENTITY_PAGE_SIZE = 0

PAGINATION_ALL_LABELS: dict[str, str] = {
    "oes": "Все ОЭС",
    "fo": "Все ФО",
    "ez": "Все энергозоны",
}


@dataclass(frozen=True, slots=True)
class _PaginationScopeSpec:
    demand_model_name: str
    id_field: str
    parent_fk_column: str
    section_entity_kinds: frozenset[str]
    require_depth_zero: bool = False
    suffix_block: Callable[[list[dict[str, Any]]], bool] | None = None


def _oes_suffix_block(block: list[dict[str, Any]]) -> bool:
    if not block:
        return False
    label = str(block[0].get("entity_label") or "")
    return TITES_SUFFIX_LABEL_FRAGMENT in label


def _ez_suffix_block(block: list[dict[str, Any]]) -> bool:
    """После энергозон — блок «Новые территории»."""
    if not block:
        return False
    label = str(block[0].get("entity_label") or "").casefold()
    return _NEW_TERRITORIES_LABEL_FRAGMENT in label


_SCOPE_SPECS: dict[str, _PaginationScopeSpec] = {
    "oes": _PaginationScopeSpec(
        demand_model_name=UES_MODEL_NAME,
        id_field="id_union_energy_system",
        parent_fk_column="id_union_energy_system",
        section_entity_kinds=frozenset({"group", "perimeter_variant"}),
        require_depth_zero=False,
        suffix_block=_oes_suffix_block,
    ),
    "fo": _PaginationScopeSpec(
        demand_model_name=FD_MODEL_NAME,
        id_field="id_federal_district",
        parent_fk_column="id_federal_district",
        section_entity_kinds=frozenset({"group", "perimeter_variant"}),
        require_depth_zero=True,
        suffix_block=None,
    ),
    "ez": _PaginationScopeSpec(
        demand_model_name=EZ_MODEL_NAME,
        id_field="id_energy_zone",
        parent_fk_column="id_energy_zone",
        section_entity_kinds=frozenset({"group", "perimeter_variant"}),
        require_depth_zero=True,
        suffix_block=_ez_suffix_block,
    ),
}


def parse_ec_entity_pagination(scope: str) -> tuple[int, int] | None:
    """GET pd_page, pd_page_size. pd_page_size=0 — все секции на одной странице."""
    if scope not in PAGINATION_SCOPES:
        return None
    raw_size = request.args.get("pd_page_size")
    if raw_size is None or str(raw_size).strip() == "":
        page_size = DEFAULT_ENTITY_PAGE_SIZE
    else:
        try:
            page_size = int(raw_size)
        except (TypeError, ValueError):
            page_size = DEFAULT_ENTITY_PAGE_SIZE
    if page_size < 0:
        page_size = DEFAULT_ENTITY_PAGE_SIZE
    if page_size > MAX_ENTITY_PAGE_SIZE:
        page_size = MAX_ENTITY_PAGE_SIZE
    try:
        page = int(request.args.get("pd_page", 1) or 1)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    return page, page_size


def client_entity_pagination_config(scope: str) -> dict[str, Any]:
    return {
        "default_page_size": DEFAULT_ENTITY_PAGE_SIZE,
        "max_page_size": MAX_ENTITY_PAGE_SIZE,
        "all_page_size": ALL_ENTITY_PAGE_SIZE,
        "all_label": PAGINATION_ALL_LABELS.get(scope, "Показать всё"),
    }


def _iter_entity_blocks(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    blocks: list[list[dict[str, Any]]] = []
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        if row.get("pd_ec_aggregation_level_row") or row.get("pd_pd_aggregation_level_row"):
            blocks.append([row])
            i += 1
            continue
        if not row.get("show_entity_cell"):
            i += 1
            continue
        block_size = int(row.get("entity_rowspan") or 1)
        if block_size < 1:
            block_size = 1
        blocks.append(rows[i : i + block_size])
        i += block_size
    return blocks


def _section_id_from_row(row: dict[str, Any], spec: _PaginationScopeSpec) -> int | None:
    raw = row.get(spec.id_field)
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    if (
        row.get("parent_fk_column") == spec.parent_fk_column
        and row.get("parent_id") is not None
    ):
        try:
            return int(row["parent_id"])
        except (TypeError, ValueError):
            return None
    return None


def _is_gaes_charge_skip_row(row: dict[str, Any]) -> bool:
    if row.get("parameter_key") == "gaes_charge_consumption_mln_kvt_ch":
        return True
    if row.get("pd_ec_gaes_injected_row"):
        return True
    return "(заряд гаэс)" in str(row.get("entity_label") or "").casefold()


def _is_top_level_section_block_head(
    row: dict[str, Any],
    spec: _PaginationScopeSpec,
) -> bool:
    if not row.get("show_entity_cell"):
        return False
    if _is_gaes_charge_skip_row(row):
        return False
    if spec.require_depth_zero:
        depth = row.get("entity_depth")
        if depth is not None and int(depth) != 0:
            return False
    if str(row.get("demand_model_name") or "") != spec.demand_model_name:
        return False
    if row.get("parent_fk_column") != spec.parent_fk_column:
        return False
    kind = str(row.get("entity_kind") or "")
    return kind in spec.section_entity_kinds


def _is_section_start(block: list[dict[str, Any]], spec: _PaginationScopeSpec) -> bool:
    if not block:
        return False
    return _is_top_level_section_block_head(block[0], spec)


def _section_title(section: list[dict[str, Any]]) -> str:
    for row in section:
        if row.get("show_entity_cell"):
            return str(row.get("entity_label") or "").strip()
    return ""


def split_summary_rows_for_pagination(
    rows: list[dict[str, Any]] | None,
    scope: str,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[dict[str, Any]]]:
    """prefix → paginable sections → suffix (ТИТЭС / НТ)."""
    if not rows:
        return [], [], []
    spec = _SCOPE_SPECS.get(scope)
    if spec is None:
        return list(rows), [], []

    prefix: list[dict[str, Any]] = []
    sections: list[list[dict[str, Any]]] = []
    suffix: list[dict[str, Any]] = []
    current_section: list[dict[str, Any]] | None = None
    current_section_id: int | None = None
    in_suffix = False

    for block in _iter_entity_blocks(rows):
        if in_suffix:
            suffix.extend(block)
            continue
        if spec.suffix_block and spec.suffix_block(block):
            if current_section is not None:
                sections.append(current_section)
                current_section = None
                current_section_id = None
            in_suffix = True
            suffix.extend(block)
            continue
        if _is_section_start(block, spec):
            section_id = _section_id_from_row(block[0], spec)
            if (
                current_section is not None
                and section_id is not None
                and current_section_id == section_id
            ):
                current_section.extend(block)
                continue
            if current_section is not None:
                sections.append(current_section)
            current_section = list(block)
            current_section_id = section_id
            continue
        if current_section is not None:
            current_section.extend(block)
        else:
            prefix.extend(block)

    if current_section is not None:
        sections.append(current_section)

    return prefix, sections, suffix


def paginate_summary_rows_for_scope(
    rows: list[dict[str, Any]] | None,
    scope: str,
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    empty_meta = {
        "enabled": False,
        "scope": scope,
        "page": 1,
        "page_size": page_size,
        "total_pages": 1,
        "total_sections": 0,
        "has_prev": False,
        "has_next": False,
        "section_titles": [],
        "all_label": PAGINATION_ALL_LABELS.get(scope, "Показать всё"),
    }
    if not rows:
        return [], empty_meta
    if page_size <= 0:
        return list(rows), {
            **empty_meta,
            "page_size": 0,
            "total_sections": len(split_summary_rows_for_pagination(rows, scope)[1]),
        }

    prefix, sections, suffix = split_summary_rows_for_pagination(rows, scope)
    total_sections = len(sections)
    if total_sections == 0:
        return list(rows), {**empty_meta, "page_size": page_size}

    total_pages = max(1, (total_sections + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    page_sections = sections[start : start + page_size]

    out: list[dict[str, Any]] = []
    if page == 1:
        out.extend(prefix)
    for section in page_sections:
        out.extend(section)
    if page == total_pages:
        out.extend(suffix)

    titles = [_section_title(sec) for sec in page_sections if _section_title(sec)]
    return out, {
        "enabled": True,
        "scope": scope,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_sections": total_sections,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "section_titles": titles,
        "all_label": PAGINATION_ALL_LABELS.get(scope, "Показать всё"),
    }


def paginate_oes_summary_rows(
    rows: list[dict[str, Any]] | None,
    *,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return paginate_summary_rows_for_scope(
        rows, "oes", page=page, page_size=page_size
    )


def split_oes_summary_rows_for_pagination(
    rows: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]], list[dict[str, Any]]]:
    return split_summary_rows_for_pagination(rows, "oes")
