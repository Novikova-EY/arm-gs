# -*- coding: utf-8 -*-
"""Загрузка/сохранение помесячного прогноза выработки ГЭС/ГАЭС (водохозяйственный год)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.extensions import db
from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
    set_db_version_on_create,
)
from app.common.services.help_services import format_decimal_for_display
from app.generation.services.machine_services.machine_services import (
    is_same_decimal,
    to_decimal,
)
from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
    HYDRO_MONTH_ORDER,
    HYDRO_MONTH_ROMAN,
    HYDRO_SCENARIOS,
    ProspectivePlaceHydroEnergyForecast,
)
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_GENERATION
from app.common.services.tranzaction_services import quick_fix_seq


def hydro_forecast_field_name(scenario: str, month: int) -> str:
    return f"hydro_gen_{scenario}_{month}"


def empty_hydro_forecast_by_scenario() -> dict[str, dict[int, Any]]:
    return {code: {m: None for m in HYDRO_MONTH_ORDER} for code, _ in HYDRO_SCENARIOS}


def load_hydro_forecast_by_scenario(
    place_kind: str,
    place_id: int,
) -> dict[str, dict[int, Any]]:
    result = empty_hydro_forecast_by_scenario()
    q = ProspectivePlaceHydroEnergyForecast.query.filter(
        ProspectivePlaceHydroEnergyForecast.place_kind == place_kind,
        ProspectivePlaceHydroEnergyForecast.place_id == place_id,
    )
    q = filter_by_db_version(q, ProspectivePlaceHydroEnergyForecast)
    for row in q.all():
        if row.scenario not in result:
            continue
        if row.month_number not in result[row.scenario]:
            continue
        result[row.scenario][row.month_number] = row.electricity_generation
    return result


def sum_months(values_by_month: dict[int, Any]) -> Decimal | None:
    total = Decimal("0")
    has_any = False
    for month in HYDRO_MONTH_ORDER:
        raw = values_by_month.get(month)
        if raw is None:
            continue
        dec = to_decimal(raw)
        if dec is None:
            continue
        total += dec
        has_any = True
    return total if has_any else None


def format_hydro_gen_display(val, digits: int = 1) -> str:
    if val is None:
        return ""
    return format_decimal_for_display(val, digits=digits)


def build_hydro_forecast_view(
    place_kind: str,
    place_id: int,
    *,
    rounding_digits: int = 1,
) -> dict[str, Any]:
    by_scenario = load_hydro_forecast_by_scenario(place_kind, place_id)
    scenarios = []
    for code, title in HYDRO_SCENARIOS:
        months = by_scenario.get(code) or {m: None for m in HYDRO_MONTH_ORDER}
        year_total = sum_months(months)
        scenarios.append(
            {
                "code": code,
                "title": title,
                "months": months,
                "year_total": year_total,
                "year_total_display": format_hydro_gen_display(year_total, rounding_digits),
            }
        )
    return {
        "month_order": HYDRO_MONTH_ORDER,
        "month_romans": HYDRO_MONTH_ROMAN,
        "scenarios": scenarios,
        "rounding_digits": rounding_digits,
        "format_value": lambda v: format_hydro_gen_display(v, rounding_digits),
    }


def save_hydro_forecast_from_form(
    user,
    *,
    place_kind: str,
    place_id: int,
    form_data,
    entity_type: str,
    commit: bool = True,
) -> list[str]:
    """
    Сохраняет помесячные значения из form_data.
    Возвращает список строк изменений (пустой, если менять нечего).

    commit=False — только staging в сессии (для общего сохранения карточки).
    """
    version_id = get_current_db_version_id()
    existing_q = ProspectivePlaceHydroEnergyForecast.query.filter(
        ProspectivePlaceHydroEnergyForecast.place_kind == place_kind,
        ProspectivePlaceHydroEnergyForecast.place_id == place_id,
    )
    existing_q = filter_by_db_version(existing_q, ProspectivePlaceHydroEnergyForecast)
    by_key = {
        (r.scenario, r.month_number): r for r in existing_q.all()
    }

    changes: list[str] = []

    def _log_num(v) -> str:
        if v is None:
            return "не указано"
        try:
            return str(v).replace(".", ",").rstrip("0").rstrip(",") or "0"
        except Exception:
            return str(v).replace(".", ",")

    def _field_changed(raw_value, orig_value) -> bool:
        if orig_value in (None, "", "—", "-"):
            return raw_value not in (None, "", "—", "-")
        return not is_same_decimal(to_decimal(raw_value), to_decimal(orig_value))

    for scenario, title in HYDRO_SCENARIOS:
        for month in HYDRO_MONTH_ORDER:
            field = hydro_forecast_field_name(scenario, month)
            raw = form_data.get(field)
            orig_raw = form_data.get(f"{field}_orig")
            if not _field_changed(raw, orig_raw):
                continue

            new_val = to_decimal(raw)
            rec = by_key.get((scenario, month))
            old_val = rec.electricity_generation if rec else None
            roman = HYDRO_MONTH_ROMAN.get(month, str(month))

            if new_val is None:
                if rec is None or old_val is None:
                    continue
                rec.electricity_generation = None
                db.session.add(rec)
                changes.append(f"{title}, {roman}: {_log_num(old_val)} → не указано")
                continue

            if rec is not None and old_val is not None and is_same_decimal(
                to_decimal(old_val), new_val
            ):
                continue

            if rec is None:
                rec = ProspectivePlaceHydroEnergyForecast(
                    place_kind=place_kind,
                    place_id=place_id,
                    scenario=scenario,
                    month_number=month,
                    electricity_generation=new_val,
                )
                set_db_version_on_create(rec)
                if version_id is not None:
                    rec.database_version_id = version_id
                db.session.add(rec)
                by_key[(scenario, month)] = rec
                changes.append(f"{title}, {roman}: не указано → {_log_num(new_val)}")
            else:
                rec.electricity_generation = new_val
                db.session.add(rec)
                changes.append(
                    f"{title}, {roman}: {_log_num(old_val)} → {_log_num(new_val)}"
                )

    if not changes:
        return []

    try:
        quick_fix_seq(
            SCHEMA_GENERATION,
            "gs_gen_prospective_place_hydro_energy_forecasts",
            "id",
        )
    except Exception:
        pass

    if commit:
        db.session.commit()
        log_to_db(
            user,
            f"Изменён прогноз выработки ({place_kind.upper()} id={place_id})",
            details="; ".join(changes),
            entity_type=entity_type,
            entity_id=place_id,
        )
    return changes
