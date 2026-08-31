# -*- coding: utf-8 -*-
"""JSON-набор gentypes_info: зона × год.

Источники (страницы АРМ → поля mock):
- /energy_balance/power_balance/ —
  «Максимальная мощность» (=установленная), максимум потребления, экспорт мощности,
  ограничения, вводы после максимума, перетоки;
- баланс ЭЭ /energy_balance/ee_balance/ —
  потребление (все зоны — /1000 → млрд по ключу mock; в БД млн),
  экспорт ЭЭ; ГАЭС — gs_gen_station_gaes_charge_consumptions;
- /power_demand/summary/oes/ —
  ЧЧИУМ (формула как на сводке), дата/время максимума;
- параметры нагрузки (ТНВ, combined_on_ees) — те же gs_pd_*_demand_params, что на сводке;
  страница /power_demand/ozp_maxima/ в АРМ — только максимум ОЗП, в mock-ключе нет → не отдаём.

Капвложения — 0 (модуль Экономика).
Зоны: ЕЭС + все СЗ + все ОЭС версии (без «не указано» / «Новые территории»).
Годы: [текущий − 5 … конец расчётного периода СиПР/ГС] по /refdata/.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.common.services.get_services.years.years_get_services import (
    _get_planning_period_years_for_version,
)
from app.energy_balance.services.ee_balance_consumption_services import (
    load_ee_balance_consumption_inputs,
)
from app.energy_balance.services.ee_balance_export_services import (
    load_ee_balance_export_inputs,
)
from app.energy_balance.services.power_balance_custom_flow_services import (
    load_power_balance_custom_flows,
)
from app.energy_balance.services.power_balance_demand_max_services import (
    load_power_balance_demand_max_inputs,
    resolve_demand_max_territory,
    year_values_from_max_power_rows,
    _demand_rows_without_nt,
)
from app.energy_balance.services.power_balance_export_services import (
    load_power_balance_export_inputs,
)
from app.energy_balance.services.power_balance_installed_capacity_services import (
    load_power_balance_installed_capacity_inputs,
)
from app.energy_balance.services.power_balance_page_services import (
    GROUP_EES,
    GROUP_SZ,
    get_power_balance_sheets,
)
from app.extensions import db
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.generation.models.station.station_model import Station
from app.api.services.generation_objects_exchange_services import (
    clip_years,
    dataset_envelope,
    json_number,
    resolve_database_version,
    _version_filter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.years.year_model import Year
from app.refdata.services.year_management_services import get_current_year_info

DATASET_GENTYPES_INFO = "gentypes_info"

# Ключи — как в mock коллег (единицы в имени могут отличаться от БД: см. комментарий модуля).
KEY_YEAR = "Год"
KEY_ZONE = "Зона"
KEY_CONSUMPTION = "Потребление, млрд. кВт•ч"
KEY_INSTALLED = "Максимальная мощность, МВт"
KEY_DEMAND_MAX = "Максимум потребления мощности, МВт"
KEY_POWER_EXPORT = "Экспорт мощности, МВт"
KEY_CONSTRAINTS = "Ограничения, МВт"
KEY_Q4 = "Вводы мощности после прохождения максимума, МВт"
KEY_FLOW = "Переток мощности в смежные энергосистемы (выдача (-), прием (+))"
KEY_GAES = (
    "Потребление электрической энергии на производственные нужды ГАЭС "
    "в насосном режиме, МВт"
)
KEY_EE_EXPORT = "Экспорт электрической энергии, млрд. кВт•ч"
KEY_CAPEX = "Прогнозируемые объемы капитальных вложений, млрд руб."
KEY_CHI = (
    "Число часов использования максимума потребления мощности "
    "(без учета потребления электрической энергии на производственные нужды "
    "ГАЭС в насосном режиме), ч/год"
)
KEY_PEAK_DT = "Дата и время прохождения максимума потребления мощности, дд.мм чч:мм"
KEY_TEMP = "Среднесуточная ТНВ, °С"
KEY_COMBINED = (
    "Потребление мощности на час прохождения максимума потребления мощности "
    "ЕЭС России, МВт"
)

_KIND_DEMAND = {
    "est": (EnergySystemTypeDemandParameter, "id_energy_system_type"),
    "ues": (UnionEnergySystemDemandParameter, "id_union_energy_system"),
    "sa": (SynchronousAreaDemandParameter, "id_synchronous_area"),
}


def _norm(text: str | None) -> str:
    return (text or "").casefold().replace("ё", "е").replace(" ", "").strip()


def select_gentypes_sheets(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ЕЭС + все СЗ + все ОЭС (листы баланса уже без «не указано» / «Новые территории»)."""
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug or slug in seen:
            continue
        name_n = _norm(sheet.get("sheet_name"))
        if "неуказан" in name_n or "новыхтерритор" in name_n or "новыетерритор" in name_n:
            continue
        seen.add(slug)
        selected.append(sheet)
    return selected


def load_gentypes_years(version_id: int | None) -> list[int]:
    """
    Годы: от (текущий − 5) включительно до конца расчётного периода СиПР/ГС.
    Текущий год и границы — как на /refdata/ (YearFeature «текущий (оценка)», YearService).
    """
    if version_id is None:
        return []
    info = get_current_year_info(version_id) or {}
    current = info.get("current_year") or 0
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = 0
    if current <= 0:
        return []
    _plan_start, plan_end = _get_planning_period_years_for_version(int(version_id))
    try:
        plan_end = int(plan_end)
    except (TypeError, ValueError):
        plan_end = current
    start = current - 5
    end = max(plan_end, current)
    catalog = {
        int(n)
        for (n,) in db.session.query(Year.number)
        .filter(Year.database_version_id == int(version_id))
        .all()
        if n is not None
    }
    if not catalog:
        return list(range(start, end + 1))
    return [y for y in range(start, end + 1) if y in catalog]


def _map_get(maps: dict, slug: str, key: str, year: int) -> Any:
    return ((maps.get(slug) or {}).get(key) or {}).get(year)


def _cap_metric(capacity_by_slug: dict, slug: str, key: str, year: int) -> Decimal:
    raw = ((capacity_by_slug.get(slug) or {}).get(key) or {}).get(year)
    if raw is None:
        return Decimal(0)
    return Decimal(str(raw))


def _num(value: Any) -> int | float:
    return json_number(value) or 0


def _as_int(value: Any) -> int:
    """Округление до целого (half-up)."""
    if value is None or value == "":
        return 0
    try:
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0


def _as_fixed(value: Any, places: int) -> float:
    """Округление до ``places`` знаков после запятой (half-up)."""
    if value is None or value == "":
        return 0.0
    try:
        quant = Decimal(1).scaleb(-int(places))
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def _consumption_mlrd(value: Any, *, is_ees: bool = False) -> int:
    """Потребление в JSON: млн → млрд (/1000), целое."""
    del is_ees
    raw = _num(value)
    if raw == 0:
        return 0
    return _as_int(Decimal(str(raw)) / Decimal(1000))


def _format_peak_dt(value: Any) -> str | int:
    if value is None:
        return 0
    if isinstance(value, datetime):
        return value.strftime("%d.%m %H:%M")
    text = str(value).strip()
    return text or 0


def _chi(consumption: Any, gaes: Any, demand_max: Any) -> float:
    """ЧЧИУМ, 1 знак после запятой."""
    try:
        cons = Decimal(str(consumption or 0))
        gaes_v = Decimal(str(gaes or 0))
        dem = Decimal(str(demand_max or 0))
    except Exception:
        return 0.0
    if dem == 0:
        return 0.0
    return _as_fixed((cons - gaes_v) / dem * 1000, 1)


def _sum_installed_for_year(cap_inputs: dict[str, Any], year: int) -> Decimal:
    total = Decimal(0)
    for key, year_map in (cap_inputs or {}).items():
        if key in {"constraints", "commissioning_after_max"}:
            continue
        if not isinstance(year_map, dict):
            continue
        val = year_map.get(year)
        if val is not None:
            total += Decimal(str(val))
    return total


def _sum_metric_over_slugs(
    capacity_by_slug: dict,
    slugs: list[str],
    key: str,
    year: int,
    *,
    subtract_slugs: list[str] | None = None,
) -> Decimal:
    total = Decimal(0)
    for slug in slugs:
        if key == "__installed__":
            total += _sum_installed_for_year(capacity_by_slug.get(slug) or {}, year)
        else:
            total += _cap_metric(capacity_by_slug, slug, key, year)
    for slug in subtract_slugs or []:
        if key == "__installed__":
            total -= _sum_installed_for_year(capacity_by_slug.get(slug) or {}, year)
        else:
            total -= _cap_metric(capacity_by_slug, slug, key, year)
    return total


def _load_demand_extras(
    sheets: list[dict[str, Any]],
    years: list[int],
) -> dict[str, dict[str, dict[int, Any]]]:
    wanted = {int(y) for y in years}
    result: dict[str, dict[str, dict[int, Any]]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        territory = resolve_demand_max_territory(sheet)
        if not slug or territory is None:
            continue
        kind = str(territory.get("kind") or "")
        spec = _KIND_DEMAND.get(kind)
        if spec is None:
            continue
        model, fk = spec
        try:
            parent_id = int(territory["id"])
        except (TypeError, ValueError, KeyError):
            continue
        rows = _demand_rows_without_nt(
            model,
            fk,
            parent_id,
            kind=kind,
            name=territory.get("name") or sheet.get("sheet_name"),
        )
        peak: dict[int, Any] = {}
        temp: dict[int, Any] = {}
        combined: dict[int, Any] = {}
        for row in rows or []:
            if getattr(row, "is_historical_maximum", False):
                continue
            year = getattr(row, "year_number", None)
            if year is None or int(year) not in wanted:
                continue
            y = int(year)
            peak[y] = getattr(row, "peak_datetime", None)
            temp[y] = getattr(row, "avg_daily_air_temp_c", None)
            if hasattr(row, "combined_on_ees"):
                combined[y] = getattr(row, "combined_on_ees", None)
        result[slug] = {
            "peak_datetime": peak,
            "avg_daily_air_temp_c": temp,
            "combined_on_ees": combined,
            "demand_max": year_values_from_max_power_rows(rows, years),
        }
    return result


def _custom_flow_net_by_slug(
    sheets: list[dict[str, Any]],
    years: list[int],
) -> dict[str, dict[int, Decimal]]:
    flows = load_power_balance_custom_flows(sheets=sheets) or {}
    wanted = {int(y) for y in years}
    result: dict[str, dict[int, Decimal]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if not slug:
            continue
        year_net: dict[int, Decimal] = {y: Decimal(0) for y in wanted}
        for item in flows.get(slug) or []:
            direction = str(item.get("direction") or "")
            values = item.get("values") or {}
            if direction == "flow_in":
                sign = Decimal(1)
            elif direction == "flow_out":
                sign = Decimal(-1)
            else:
                continue
            for year, raw in values.items():
                try:
                    y = int(year)
                except (TypeError, ValueError):
                    continue
                if y not in wanted or raw is None:
                    continue
                year_net[y] = year_net.get(y, Decimal(0)) + sign * Decimal(str(raw))
        result[slug] = year_net
    return result


def _load_gaes_by_sheet(
    sheets: list[dict[str, Any]],
    years: list[int],
    version_id: int | None,
) -> dict[str, dict[int, Decimal]]:
    """Сумма charge_consumption станций по территории листа (млн кВт·ч в БД)."""
    if not sheets or not years:
        return {}
    wanted = {int(y) for y in years}
    stations = (
        db.session.query(Station)
        .options(
            joinedload(Station.regional_district).joinedload(RegionalDistrict.synchronous_area),
            joinedload(Station.regional_energy_system_obj).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
        )
        .filter(_version_filter(Station, version_id))
        .all()
    )
    # station_id → {sa_id, ues_id, est_id}
    station_terr: dict[int, dict[str, int | None]] = {}
    for st in stations:
        district = getattr(st, "regional_district", None)
        sa = getattr(district, "synchronous_area", None) if district else None
        res = getattr(st, "regional_energy_system_obj", None)
        ues = getattr(res, "union_energy_system", None) if res else None
        ues_id = getattr(ues, "id", None) if ues else getattr(res, "id_union_energy_system", None)
        est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        station_terr[int(st.id)] = {
            "sa": int(sa.id) if sa and getattr(sa, "id", None) else None,
            "ues": int(ues_id) if ues_id else None,
            "est": int(est_id) if est_id else None,
        }

    q = (
        db.session.query(
            StationGaesChargeConsumption.id_station,
            StationGaesChargeConsumption.year_number,
            func.coalesce(func.sum(StationGaesChargeConsumption.charge_consumption), 0),
        )
        .filter(StationGaesChargeConsumption.year_number.in_(list(wanted)))
        .filter(_version_filter(StationGaesChargeConsumption, version_id))
        .group_by(
            StationGaesChargeConsumption.id_station,
            StationGaesChargeConsumption.year_number,
        )
    )
    by_station_year: dict[tuple[int, int], Decimal] = {}
    for sid, year, val in q.all():
        if sid is None or year is None:
            continue
        by_station_year[(int(sid), int(year))] = Decimal(str(val or 0))

    result: dict[str, dict[int, Decimal]] = {}
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        territory = resolve_demand_max_territory(sheet)
        if not slug or territory is None:
            continue
        kind = str(territory.get("kind") or "")
        try:
            parent_id = int(territory["id"])
        except (TypeError, ValueError, KeyError):
            continue
        year_sum: dict[int, Decimal] = {y: Decimal(0) for y in wanted}
        for (sid, year), val in by_station_year.items():
            terr = station_terr.get(sid) or {}
            match = (
                (kind == "sa" and terr.get("sa") == parent_id)
                or (kind == "ues" and terr.get("ues") == parent_id)
                or (kind == "est" and terr.get("est") == parent_id)
            )
            if match:
                year_sum[year] = year_sum.get(year, Decimal(0)) + val
        result[slug] = year_sum
    return result


def _sum_sheet_metric(
    maps: dict,
    slugs: list[str] | tuple[str, ...],
    key: str,
    year: int,
    *,
    subtract_slugs: list[str] | tuple[str, ...] | None = None,
) -> Decimal | None:
    total = Decimal(0)
    seen = False
    for slug in slugs:
        raw = _map_get(maps, str(slug), key, year)
        if raw is None:
            continue
        seen = True
        total += Decimal(str(raw))
    for slug in subtract_slugs or []:
        raw = _map_get(maps, str(slug), key, year)
        if raw is None:
            continue
        seen = True
        total -= Decimal(str(raw))
    return total if seen else None


def build_gentypes_info_rows(
    *,
    years: list[int],
    sheets: list[dict[str, Any]],
    version_id: int | None,
) -> list[dict[str, Any]]:
    if not years or not sheets:
        return []

    consumption = load_ee_balance_consumption_inputs(years, sheets)
    demand_max = load_power_balance_demand_max_inputs(years, sheets)
    power_export = load_power_balance_export_inputs(years, sheets)
    ee_export = load_ee_balance_export_inputs(years, sheets)
    capacity = load_power_balance_installed_capacity_inputs(years, sheets)
    extras = _load_demand_extras(sheets, years)
    flows = _custom_flow_net_by_slug(sheets, years)
    gaes_map = _load_gaes_by_sheet(sheets, years, version_id)

    all_sheets = get_power_balance_sheets()
    capacity_all = load_power_balance_installed_capacity_inputs(years, all_sheets)

    rows: list[dict[str, Any]] = []
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        zone = str(sheet.get("sheet_name") or slug).strip()
        is_ees = slug == "ees-rossii" or sheet.get("group") == GROUP_EES
        for year in years:
            cons = _map_get(consumption, slug, "consumption", year)
            # ЕЭС / 1-я СЗ на странице БЭ — сумма по ОЭС (как formula), не прямая строка EST/SA.
            source_slugs = tuple(sheet.get("source_slugs") or ())
            subtract_slugs = tuple(sheet.get("subtract_slugs") or ())
            if source_slugs:
                aggregated = _sum_sheet_metric(
                    consumption,
                    source_slugs,
                    "consumption",
                    year,
                    subtract_slugs=subtract_slugs,
                )
                if aggregated is not None:
                    cons = aggregated
            dem = _map_get(demand_max, slug, "demand_max", year)
            if dem is None:
                dem = (extras.get(slug) or {}).get("demand_max", {}).get(year)
            p_exp = _map_get(power_export, slug, "export", year)
            ee_exp = _map_get(ee_export, slug, "export", year)
            gaes = (gaes_map.get(slug) or {}).get(year)

            # ЕЭС / 1-я СЗ: Руст, ограничения, вводы Q4 — как formula на БМ
            # (source_slugs / subtract_slugs листа, не «все is_ees_member»).
            if source_slugs:
                installed = _sum_metric_over_slugs(
                    capacity_all,
                    list(source_slugs),
                    "__installed__",
                    year,
                    subtract_slugs=list(subtract_slugs) or None,
                )
                constraints = _sum_metric_over_slugs(
                    capacity_all,
                    list(source_slugs),
                    "constraints",
                    year,
                    subtract_slugs=list(subtract_slugs) or None,
                )
                q4 = _sum_metric_over_slugs(
                    capacity_all,
                    list(source_slugs),
                    "commissioning_after_max",
                    year,
                    subtract_slugs=list(subtract_slugs) or None,
                )
            else:
                cap_sheet = capacity.get(slug) or {}
                installed = _sum_installed_for_year(cap_sheet, year)
                constraints = (cap_sheet.get("constraints") or {}).get(year)
                q4 = (cap_sheet.get("commissioning_after_max") or {}).get(year)

            flow = (flows.get(slug) or {}).get(year)
            peak = ((extras.get(slug) or {}).get("peak_datetime") or {}).get(year)
            temp = ((extras.get(slug) or {}).get("avg_daily_air_temp_c") or {}).get(year)
            combined = ((extras.get(slug) or {}).get("combined_on_ees") or {}).get(year)
            if sheet.get("group") != GROUP_SZ:
                # для ОЭС/ЕЭС — 0, кроме случаев когда поле есть в PD
                if combined is None:
                    combined = 0

            rows.append(
                {
                    KEY_YEAR: int(year),
                    KEY_ZONE: zone,
                    KEY_CONSUMPTION: _consumption_mlrd(cons, is_ees=is_ees),
                    KEY_INSTALLED: _as_int(installed),
                    KEY_DEMAND_MAX: _as_int(dem),
                    KEY_POWER_EXPORT: _as_int(p_exp),
                    KEY_CONSTRAINTS: _as_int(constraints),
                    KEY_Q4: _as_int(q4),
                    KEY_FLOW: _as_int(flow),
                    KEY_GAES: _as_int(gaes),
                    KEY_EE_EXPORT: _as_fixed(ee_exp, 2),
                    KEY_CAPEX: 0,
                    KEY_CHI: _chi(cons, gaes, dem),
                    KEY_PEAK_DT: _format_peak_dt(peak),
                    KEY_TEMP: _as_fixed(temp, 1) if temp is not None else 0.0,
                    KEY_COMBINED: _as_int(combined),
                }
            )
    return rows


def load_gentypes_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    years = clip_years(
        load_gentypes_years(resolved_id),
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    sheets = select_gentypes_sheets(get_power_balance_sheets())
    rows = build_gentypes_info_rows(
        years=years,
        sheets=sheets,
        version_id=resolved_id,
    )
    return dataset_envelope(
        DATASET_GENTYPES_INFO,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )
