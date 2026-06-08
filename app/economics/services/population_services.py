# -*- coding: utf-8 -*-
"""Сервисы таблицы численности населения (долгосрочный прогноз)."""

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
from app.economics.models.federal_district_population_parameter_model import (
    FederalDistrictPopulationParameter,
)
from app.extensions import db
from app.economics.services.population_constants import (
    POP_FD_EXCLUDED_NAME_KEYS,
    POP_FD_PLACEHOLDER_NAME_KEYS,
)
from app.economics.services.population_logging import (
    _fmt_log_value,
    log_population_cell_change,
)
from app.generation.services.machine_services.machine_services import (
    is_same_decimal,
    to_decimal,
)
from app.refdata.models.territories.federal_district_model import FederalDistrict


def _username() -> str:
    return session.get("username", "Неизвестный пользователь")


def _federal_district_name_key(name: str | None) -> str:
    cf = (name or "").strip().casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(p) :].strip()
            break
    return cf


def _is_federal_district_excluded(fd: FederalDistrict) -> bool:
    for attr in ("name", "name_abr", "name_full"):
        key = _federal_district_name_key(getattr(fd, attr, None))
        if not key:
            continue
        if key in POP_FD_EXCLUDED_NAME_KEYS or key in POP_FD_PLACEHOLDER_NAME_KEYS:
            return True
    return False


def federal_districts_for_population_page() -> list[FederalDistrict]:
    return [fd for fd in get_federal_district_list() if not _is_federal_district_excluded(fd)]


def _format_full_numeric_tooltip(value: Any) -> str:
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=0)
    return apply_thousand_grouping_to_display(s) if s else ""


def _format_cell_display(value: Any, rounding_digits: int) -> str:
    if value is None:
        return "—"
    shown = format_decimal_trim_for_display(value, digits=rounding_digits)
    return apply_thousand_grouping_to_display(shown) if shown else "—"


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


def _load_values_by_fd_year(
    *,
    version_id: int | None,
    fd_id: int,
) -> dict[int, Decimal | None]:
    q = FederalDistrictPopulationParameter.query.filter(
        FederalDistrictPopulationParameter.id_federal_district == fd_id,
    )
    if version_id is not None:
        q = q.filter(FederalDistrictPopulationParameter.database_version_id == version_id)
    result: dict[int, Decimal | None] = {}
    for row in q.all():
        if row.year_number is None:
            continue
        result[int(row.year_number)] = row.population_thousand_persons
    return result


def build_population_page_context(
    *,
    rounding_digits: int = 1,
    start_year: int,
    end_year: int,
    display_years: list[int],
    filter_year_list: list[int],
    coeff_base_year: int,
    summary_include_medium_years: bool,
    fd_filter_ids: frozenset[int],
    has_active_filters: bool,
) -> dict[str, Any]:
    version_id = get_current_version()
    rows: list[dict[str, Any]] = []

    for fd in federal_districts_for_population_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        values = _load_values_by_fd_year(version_id=version_id, fd_id=fd.id)
        cells: dict[int, Any] = {year: values.get(year) for year in display_years}
        row = {
            "fd_id": fd.id,
            "label": fd.name_full or fd.name,
            "abbr": fd.name_abr or fd.name,
            "cells": cells,
            "cell_tooltips": {
                year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
            },
            "cells_display": {
                year: _format_cell_display(cells.get(year), rounding_digits)
                for year in display_years
            },
        }
        rows.append(row)

    federal_district_list = [
        {"id": x.id, "name": x.name}
        for x in get_federal_district_list_full()
        if not _is_federal_district_excluded(x)
    ]

    return {
        "page_title": "Численность населения",
        "years": display_years,
        "display_years": display_years,
        "year_features": get_year_feature_dict() or {},
        "filter_year_list": filter_year_list,
        "start_year": start_year,
        "end_year": end_year,
        "coeff_base_year": coeff_base_year,
        "summary_include_medium_years": summary_include_medium_years,
        "lt_ved_year_segments": True,
        "population_rows": rows,
        "federal_district_list": federal_district_list,
        "has_active_filters": has_active_filters,
        "rounding_digits": rounding_digits,
    }


def _territory_label_for_log(fd_id: int) -> str:
    fd = FederalDistrict.query.get(fd_id)
    if fd is None:
        return f"федеральный округ (id={fd_id})"
    return (fd.name_abr or fd.name or fd.name_full or f"id={fd_id}").strip()


def save_population_from_post(form_data: Any) -> tuple[int, int]:
    version_id = get_current_version()
    user = _username()
    updated = 0
    skipped = 0
    territory_cache: dict[int, str] = {}

    fd_ids = form_data.getlist("fd_id[]")
    years = form_data.getlist("cell_year[]")
    values = form_data.getlist("cell_value[]")

    n = min(len(fd_ids), len(years), len(values))
    for i in range(n):
        fd_raw = str(fd_ids[i] or "").strip()
        year_raw = str(years[i] or "").strip()
        val_raw = values[i]

        if not fd_raw or not year_raw:
            skipped += 1
            continue
        try:
            fd_id = int(fd_raw)
            year_n = int(year_raw)
        except ValueError:
            skipped += 1
            continue

        dec = _parse_decimal(val_raw)
        row = _get_or_create_fd_row(version_id, fd_id, year_n, user)
        old_val = row.population_thousand_persons
        if is_same_decimal(to_decimal(old_val), to_decimal(dec)):
            skipped += 1
            continue

        row.population_thousand_persons = dec
        row.modified_by = user
        if fd_id not in territory_cache:
            territory_cache[fd_id] = _territory_label_for_log(fd_id)
        log_population_cell_change(
            user,
            detail_chunks=[
                f"территория={territory_cache[fd_id]}",
                f"год={year_n}",
                (
                    f"Численность населения, тыс. чел.: {_fmt_log_value(old_val)} → "
                    f"{_fmt_log_value(dec)}"
                ),
            ],
            database_version_id=version_id,
        )
        updated += 1

    return updated, skipped


def _get_or_create_fd_row(
    version_id: int | None,
    fd_id: int,
    year_n: int,
    user: str,
) -> FederalDistrictPopulationParameter:
    filters = [
        FederalDistrictPopulationParameter.id_federal_district == fd_id,
        FederalDistrictPopulationParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            FederalDistrictPopulationParameter.database_version_id == version_id
        )
    row = FederalDistrictPopulationParameter.query.filter(and_(*filters)).first()
    if row is None:
        row = FederalDistrictPopulationParameter(
            id_federal_district=fd_id,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row
