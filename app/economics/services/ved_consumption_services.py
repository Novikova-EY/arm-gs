# -*- coding: utf-8 -*-
"""Сервисы таблицы потребления по ВЭД (долгосрочный прогноз)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from flask import session
from sqlalchemy import and_
from app.common.services.database_version_services import get_current_version
from app.common.services.help_services import (
    apply_thousand_grouping_to_display,
    format_decimal_trim_for_display,
)
from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list,
    get_federal_district_list_full,
)
from app.economics.models.federal_district_eat_consumption_parameter_model import (
    FederalDistrictEATConsumptionParameter,
)
from app.economics.models.russia_federation_consumption_parameter_model import (
    RussiaFederationConsumptionParameter,
)
from app.extensions import db
from app.economics.services.ved_consumption_constants import (
    FD_TOTAL_ROW_LABEL,
    INDUSTRIAL_COMPONENT_VED_TARGETS,
    INDUSTRIAL_GROUP_LABEL,
    TOTAL_VED_NAME,
    VED_FD_EXCLUDED_NAME_KEYS,
    VED_FD_PLACEHOLDER_NAME_KEYS,
)
from app.economics.services.formula_text.ved_consumption_formula_text_services import (
    ved_formula_text,
)
from app.economics.services.ved_consumption_logging import (
    _fmt_log_value,
    log_ved_consumption_cell_change,
)
from app.generation.services.machine_services.machine_services import (
    is_same_decimal,
    to_decimal,
)
from app.refdata.models.economic_activity.economic_activity_type_model import EconomicActivityType
from app.refdata.models.territories.federal_district_model import FederalDistrict


def _username() -> str:
    return session.get("username", "Неизвестный пользователь")


def _normalize_label(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _federal_district_name_key(name: str | None) -> str:
    cf = (name or "").strip().casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(p) :].strip()
            break
    return cf


def _is_federal_district_excluded_from_ved(fd: FederalDistrict) -> bool:
    """Скрыть служебные ФО (как на /energy_consumption/summary/federal_districts/)."""
    for attr in ("name", "name_abr", "name_full"):
        key = _federal_district_name_key(getattr(fd, attr, None))
        if not key:
            continue
        if key in VED_FD_EXCLUDED_NAME_KEYS or key in VED_FD_PLACEHOLDER_NAME_KEYS:
            return True
    return False


def _federal_districts_for_ved_page() -> list[FederalDistrict]:
    return [fd for fd in get_federal_district_list() if not _is_federal_district_excluded_from_ved(fd)]


def _format_full_numeric_tooltip(value: Any) -> str:
    """Полное значение для title/data-db-full (без округления UI)."""
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=0)
    return apply_thousand_grouping_to_display(s) if s else ""


def _cell_tooltips_for_years(
    cells: dict[int, Any], display_years: list[int]
) -> dict[int, str]:
    return {year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years}


def _format_cell_display(value: Any, rounding_digits: int) -> str:
    if value is None:
        return "—"
    shown = format_decimal_trim_for_display(value, digits=rounding_digits)
    return apply_thousand_grouping_to_display(shown) if shown else "—"


def _attach_cells_display(
    row: dict[str, Any], display_years: list[int], rounding_digits: int
) -> None:
    cells = row.get("cells") or {}
    row["cells_display"] = {
        year: _format_cell_display(cells.get(year), rounding_digits)
        for year in display_years
    }


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    if not s or s in ("—", "-", "–"):
        return None
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _ved_types_for_version(version_id: int | None) -> list[EconomicActivityType]:
    q = EconomicActivityType.query
    if version_id is not None:
        q = q.filter(EconomicActivityType.database_version_id == version_id)
    return (
        q.order_by(
            EconomicActivityType.display_order.asc().nullslast(),
            EconomicActivityType.name.asc(),
            EconomicActivityType.id.asc(),
        ).all()
    )


def _load_values_map(
    *,
    version_id: int | None,
    model: type,
    territory_filter: Any | None = None,
) -> dict[tuple[int, int], Decimal | None]:
    from app.common.services.economics_fd_data_cache import get_fd_ved_year_values

    if model is FederalDistrictEATConsumptionParameter:
        return get_fd_ved_year_values(
            "ved_consumption",
            version_id=version_id,
            model=model,
            value_attr="energy_consumption_mln_kvt_ch",
            territory_filter=territory_filter,
        )

    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    if territory_filter is not None:
        q = q.filter(territory_filter)
    result: dict[tuple[int, int], Decimal | None] = {}
    for row in q.all():
        if row.year_number is None or row.id_economic_activity_type is None:
            continue
        result[(int(row.id_economic_activity_type), int(row.year_number))] = (
            row.energy_consumption_mln_kvt_ch
        )
    return result


def build_ved_consumption_page_context(
    *,
    rounding_digits: int = 1,
    start_year: int,
    end_year: int,
    display_years: list[int],
    filter_year_list: list[int],
    coeff_base_year: int,
    summary_include_medium_years: bool,
    summary_include_long_years: bool,
    fd_filter_ids: frozenset[int],
    ved_filter_ids: frozenset[int],
    has_active_filters: bool,
) -> dict[str, Any]:
    version_id = get_current_version()
    ved_types = _ved_types_for_version(version_id)
    if ved_filter_ids:
        ved_types = [v for v in ved_types if v.id in ved_filter_ids]

    territory_blocks: list[dict[str, Any]] = []

    rf_values = _load_values_map(
        version_id=version_id,
        model=RussiaFederationConsumptionParameter,
    )
    territory_blocks.append(
        _territory_block(
            territory_kind="rf",
            territory_id=None,
            label="Российская Федерация",
            abbr="РФ",
            ved_types=ved_types,
            values_by_ved_year=rf_values,
            display_years=display_years,
            rounding_digits=rounding_digits,
        )
    )

    for fd in _federal_districts_for_ved_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        fd_values = _load_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        territory_blocks.append(
            _territory_block(
                territory_kind="fd",
                territory_id=fd.id,
                label=fd.name_full or fd.name,
                abbr=fd.name_abr or fd.name,
                ved_types=ved_types,
                values_by_ved_year=fd_values,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
        )

    federal_district_list = [
        {"id": x.id, "name": x.name}
        for x in get_federal_district_list_full()
        if not _is_federal_district_excluded_from_ved(x)
    ]
    economic_activity_type_list = [
        {"id": v.id, "name": v.name or ""}
        for v in _ved_types_for_version(version_id)
        if v.name
    ]

    return {
        "page_title": "Потребление электрической энергии по ВЭД",
        "years": display_years,
        "display_years": display_years,
        "year_features": get_year_feature_dict() or {},
        "filter_year_list": filter_year_list,
        "start_year": start_year,
        "end_year": end_year,
        "coeff_base_year": coeff_base_year,
        "summary_include_medium_years": summary_include_medium_years,
        "summary_include_long_years": summary_include_long_years,
        "lt_ved_year_segments": True,
        "territory_blocks": territory_blocks,
        "federal_district_list": federal_district_list,
        "economic_activity_type_list": economic_activity_type_list,
        "has_active_filters": has_active_filters,
        "rounding_digits": rounding_digits,
        "formula_hints": {
            "total": ved_formula_text("ved_total_row"),
            "industrial": ved_formula_text("ved_industrial_group"),
        },
        "total_ved_name": TOTAL_VED_NAME,
    }


def _is_parent_industrial_ved_name(name: str | None) -> bool:
    n = _normalize_label(name)
    if not n:
        return False
    base = _normalize_label("Промышленное производство")
    if n == base:
        return True
    return n.startswith(base) and "в том числе" in n


def _find_total_ved(
    ved_types: list[EconomicActivityType],
) -> EconomicActivityType | None:
    target_n = _normalize_label(TOTAL_VED_NAME)
    for ved in ved_types:
        if ved.name and _normalize_label(ved.name) == target_n:
            return ved
    for ved in ved_types:
        if not ved.name:
            continue
        name_n = _normalize_label(ved.name)
        if name_n == _normalize_label(FD_TOTAL_ROW_LABEL):
            return ved
        if name_n.startswith("всего") and "потребл" in name_n:
            return ved
    return _find_ved_by_target(ved_types, TOTAL_VED_NAME)


def _append_computed_total_row_at_end(
    rows: list[dict[str, Any]],
    *,
    total_ved_id: int | None,
    total_label: str,
    sum_source_rows: list[dict[str, Any]],
    display_years: list[int],
    rounding_digits: int,
    mark_as_total: bool = True,
) -> list[dict[str, Any]]:
    if total_ved_id is None:
        return rows
    without_total = [r for r in rows if r.get("ved_id") != total_ved_id]
    total_cells = _sum_industrial_group_cells(sum_source_rows, display_years)
    total_row: dict[str, Any] = {
        "ved_id": total_ved_id,
        "ved_name": total_label,
        "is_total": mark_as_total,
        "is_industrial_group": False,
        "is_industrial_component": False,
        "is_computed": True,
        "cells": total_cells,
        "cell_tooltips": _cell_tooltips_for_years(total_cells, display_years),
    }
    _attach_cells_display(total_row, display_years, rounding_digits)
    return [*without_total, total_row]


def _find_ved_by_target(
    ved_types: list[EconomicActivityType], target: str
) -> EconomicActivityType | None:
    target_n = _normalize_label(target)
    if not target_n:
        return None
    best: EconomicActivityType | None = None
    best_len = -1
    for ved in ved_types:
        if not ved.name:
            continue
        name_n = _normalize_label(ved.name)
        if name_n == target_n or name_n.startswith(target_n) or target_n.startswith(name_n):
            if len(name_n) > best_len:
                best = ved
                best_len = len(name_n)
    return best


def _ved_row(
    ved: EconomicActivityType,
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    *,
    rounding_digits: int,
) -> dict[str, Any]:
    cells: dict[int, Any] = {}
    for year in display_years:
        cells[year] = values_by_ved_year.get((ved.id, year))
    row = {
        "ved_id": ved.id,
        "ved_name": ved.name,
        "is_total": _normalize_label(ved.name) == _normalize_label(TOTAL_VED_NAME),
        "is_industrial_group": False,
        "is_industrial_component": False,
        "is_computed": False,
        "cells": cells,
        "cell_tooltips": _cell_tooltips_for_years(cells, display_years),
    }
    _attach_cells_display(row, display_years, rounding_digits)
    return row


def _sum_industrial_group_cells(
    component_rows: list[dict[str, Any]], display_years: list[int]
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        total: Decimal | None = None
        has_any = False
        for row in component_rows:
            val = row["cells"].get(year)
            if val is not None:
                has_any = True
                total = (total or Decimal(0)) + val
        cells[year] = total if has_any else None
    return cells


def _rows_in_ved_order(
    ved_types: list[EconomicActivityType], row_by_id: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        row_by_id[ved.id]
        for ved in ved_types
        if ved.name and ved.id in row_by_id
    ]


def _build_territory_rows(
    *,
    territory_kind: str,
    ved_types: list[EconomicActivityType],
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> list[dict[str, Any]]:
    row_by_id: dict[int, dict[str, Any]] = {}
    for ved in ved_types:
        if not ved.name:
            continue
        row_by_id[ved.id] = _ved_row(
            ved, values_by_ved_year, display_years, rounding_digits=rounding_digits
        )

    if territory_kind not in ("fd", "rf"):
        return _rows_in_ved_order(ved_types, row_by_id)

    total_ved = _find_total_ved(ved_types)
    total_ved_id = total_ved.id if total_ved is not None else None

    def _finish_rows(
        rows: list[dict[str, Any]], *, total_sum_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _append_computed_total_row_at_end(
            rows,
            total_ved_id=total_ved_id,
            total_label=TOTAL_VED_NAME,
            sum_source_rows=total_sum_rows,
            display_years=display_years,
            rounding_digits=rounding_digits,
            mark_as_total=True,
        )

    component_veds: list[EconomicActivityType] = []
    for target in INDUSTRIAL_COMPONENT_VED_TARGETS:
        ved = _find_ved_by_target(ved_types, target)
        if ved is None or ved.id not in row_by_id:
            ordered = _rows_in_ved_order(ved_types, row_by_id)
            without_total = [r for r in ordered if r.get("ved_id") != total_ved_id]
            return _append_computed_total_row_at_end(
                without_total,
                total_ved_id=total_ved_id,
                total_label=TOTAL_VED_NAME,
                sum_source_rows=without_total,
                display_years=display_years,
                rounding_digits=rounding_digits,
                mark_as_total=True,
            )
        component_veds.append(ved)

    component_rows: list[dict[str, Any]] = []
    component_ids: set[int] = set()
    for ved in component_veds:
        row = row_by_id[ved.id]
        row["is_industrial_component"] = True
        component_rows.append(row)
        component_ids.add(ved.id)

    industrial_cells = _sum_industrial_group_cells(component_rows, display_years)
    industrial_row: dict[str, Any] = {
        "ved_id": None,
        "ved_name": INDUSTRIAL_GROUP_LABEL,
        "is_total": False,
        "is_industrial_group": True,
        "is_industrial_component": False,
        "is_computed": True,
        "cells": industrial_cells,
        "cell_tooltips": _cell_tooltips_for_years(industrial_cells, display_years),
    }
    _attach_cells_display(industrial_row, display_years, rounding_digits)

    other_rows: list[dict[str, Any]] = []
    for ved in ved_types:
        if not ved.name or ved.id not in row_by_id:
            continue
        if ved.id in component_ids or _is_parent_industrial_ved_name(ved.name):
            continue
        if total_ved_id is not None and ved.id == total_ved_id:
            continue
        other_rows.append(row_by_id[ved.id])

    total_sum_rows: list[dict[str, Any]] = [industrial_row, *other_rows]
    return _finish_rows(
        [industrial_row, *component_rows, *other_rows],
        total_sum_rows=total_sum_rows,
    )


def _territory_block(
    *,
    territory_kind: str,
    territory_id: int | None,
    label: str,
    abbr: str,
    ved_types: list[EconomicActivityType],
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[str, Any]:
    rows = _build_territory_rows(
        territory_kind=territory_kind,
        ved_types=ved_types,
        values_by_ved_year=values_by_ved_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
    )
    return {
        "territory_kind": territory_kind,
        "territory_id": territory_id,
        "label": label,
        "abbr": abbr,
        "rows": rows,
    }


def _territory_label_for_log(kind: str, fd_id: int | None) -> str:
    if kind == "rf":
        return "Российская Федерация"
    if fd_id is None:
        return "федеральный округ"
    fd = FederalDistrict.query.get(fd_id)
    if fd is None:
        return f"федеральный округ (id={fd_id})"
    return (fd.name_abr or fd.name or fd.name_full or f"id={fd_id}").strip()


def _ved_name_for_log(ved_id: int, cache: dict[int, str]) -> str:
    if ved_id in cache:
        return cache[ved_id]
    ved = EconomicActivityType.query.get(ved_id)
    name = (ved.name or f"id={ved_id}").strip() if ved is not None else f"id={ved_id}"
    cache[ved_id] = name
    return name


def _log_ved_cell_if_changed(
    user: str,
    *,
    kind: str,
    fd_id: int | None,
    ved_id: int,
    year_n: int,
    old_val: Any,
    new_val: Decimal | None,
    version_id: int | None,
    territory_cache: dict[tuple[str, int | None], str],
    ved_cache: dict[int, str],
) -> None:
    if is_same_decimal(to_decimal(old_val), to_decimal(new_val)):
        return
    terr_key = (kind, fd_id)
    if terr_key not in territory_cache:
        territory_cache[terr_key] = _territory_label_for_log(kind, fd_id)
    chunks = [
        f"территория={territory_cache[terr_key]}",
        f"ВЭД={_ved_name_for_log(ved_id, ved_cache)}",
        f"год={year_n}",
        (
            f"Потребление, млн кВтч: {_fmt_log_value(old_val)} → "
            f"{_fmt_log_value(new_val)}"
        ),
    ]
    log_ved_consumption_cell_change(
        user,
        detail_chunks=chunks,
        database_version_id=version_id,
    )


def save_ved_consumption_from_post(form_data: Any) -> tuple[int, int]:
    version_id = get_current_version()
    user = _username()
    updated = 0
    skipped = 0
    territory_cache: dict[tuple[str, int | None], str] = {}
    ved_cache: dict[int, str] = {}

    kinds = form_data.getlist("territory_kind[]")
    territory_ids = form_data.getlist("territory_id[]")
    ved_ids = form_data.getlist("ved_id[]")
    years = form_data.getlist("cell_year[]")
    values = form_data.getlist("cell_value[]")

    n = min(len(kinds), len(territory_ids), len(ved_ids), len(years), len(values))
    for i in range(n):
        kind = str(kinds[i] or "").strip()
        terr_raw = str(territory_ids[i] or "").strip()
        ved_raw = str(ved_ids[i] or "").strip()
        year_raw = str(years[i] or "").strip()
        val_raw = values[i]

        if not ved_raw or not year_raw:
            skipped += 1
            continue
        try:
            ved_id = int(ved_raw)
            year_n = int(year_raw)
        except ValueError:
            skipped += 1
            continue

        dec = _parse_decimal(val_raw)
        fd_id: int | None = None
        if kind == "rf":
            row = _get_or_create_rf_row(version_id, ved_id, year_n, user)
        elif kind == "fd" and terr_raw:
            try:
                fd_id = int(terr_raw)
            except ValueError:
                skipped += 1
                continue
            row = _get_or_create_fd_row(version_id, fd_id, ved_id, year_n, user)
        else:
            skipped += 1
            continue

        old_val = row.energy_consumption_mln_kvt_ch
        if is_same_decimal(to_decimal(old_val), to_decimal(dec)):
            skipped += 1
            continue

        row.energy_consumption_mln_kvt_ch = dec
        row.modified_by = user
        _log_ved_cell_if_changed(
            user,
            kind=kind,
            fd_id=fd_id,
            ved_id=ved_id,
            year_n=year_n,
            old_val=old_val,
            new_val=dec,
            version_id=version_id,
            territory_cache=territory_cache,
            ved_cache=ved_cache,
        )
        updated += 1

    if updated:
        from app.common.services.economics_fd_data_cache import (
            invalidate_economics_fd_data_cache,
        )

        invalidate_economics_fd_data_cache(version_id, "ved_consumption")

    return updated, skipped


def _get_or_create_fd_row(
    version_id: int | None,
    fd_id: int,
    ved_id: int,
    year_n: int,
    user: str,
) -> FederalDistrictEATConsumptionParameter:
    filters = [
        FederalDistrictEATConsumptionParameter.id_federal_district == fd_id,
        FederalDistrictEATConsumptionParameter.id_economic_activity_type == ved_id,
        FederalDistrictEATConsumptionParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            FederalDistrictEATConsumptionParameter.database_version_id == version_id
        )
    row = FederalDistrictEATConsumptionParameter.query.filter(and_(*filters)).first()
    if row is None:
        row = FederalDistrictEATConsumptionParameter(
            id_federal_district=fd_id,
            id_economic_activity_type=ved_id,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _get_or_create_rf_row(
    version_id: int | None,
    ved_id: int,
    year_n: int,
    user: str,
) -> RussiaFederationConsumptionParameter:
    filters = [
        RussiaFederationConsumptionParameter.id_economic_activity_type == ved_id,
        RussiaFederationConsumptionParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            RussiaFederationConsumptionParameter.database_version_id == version_id
        )
    row = RussiaFederationConsumptionParameter.query.filter(and_(*filters)).first()
    if row is None:
        row = RussiaFederationConsumptionParameter(
            id_economic_activity_type=ved_id,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row
