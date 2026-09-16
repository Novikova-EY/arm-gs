# -*- coding: utf-8 -*-
"""JSON-набор gentypes_info: зона × год.

Источники (страницы АРМ → поля mock):
- /generation/stations/station_list?show_totals=1 —
  «Максимальная мощность, МВт» = строка «…, всего» Руст агрегации
  своего уровня (ОЭС / РЭС / энергорайон / СЗ);
- /energy_balance/power_balance/ —
  максимум потребления, экспорт мощности, ограничения, вводы после максимума, перетоки;
- баланс ЭЭ /energy_balance/ee_balance/ —
  потребление (все зоны — /1000 → млрд по ключу mock; в БД млн),
  экспорт ЭЭ; ГАЭС — gs_gen_station_gaes_charge_consumptions;
- /power_demand/summary/oes/ — строки «… без НТ»:
  ЧЧИУМ, дата/время максимума, ТНВ;
  для ЕЭС «Потребление мощности на час прохождения максимума ЕЭС» =
  «Максимальное потребление мощности»; для СЗ — combined_on_ees той же строки;
- /power_demand/ozp_maxima/ — максимум ОЗП и дата/время максимума ОЗП
  (только строки ЕЭС; у остальных зон 0).

Зоны: ЕЭС + все СЗ + все ОЭС версии (без «не указано» / «Новые территории»),
энергорайоны ТИТЭС Востока и РЭС ТИТЭС (Востока и Сибири).
Годы: [current_year − 5 … period_end] той же версии, что в /api/database_versions.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.api.services.exchange_common_services import (
    clip_years,
    dataset_envelope,
    load_exchange_years,
    resolve_database_version,
    version_filter as _version_filter,
)
from app.api.services.generation_objects_exchange_services import (
    json_number,
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
    installed_type_keys,
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
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
    EnergyUnitDemandParameter,
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
from app.power_demand.services.ozp_max_power_services import (
    load_ozp_rows_by_end_year,
    normalize_ozp_peak_datetime,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict

DATASET_GENTYPES_INFO = "gentypes_info"

# Ключи — как в mock коллег (единицы в имени могут отличаться от БД: см. комментарий модуля).
KEY_YEAR = "Год"
KEY_ZONE = "Название зоны"
KEY_CONSUMPTION = "Потребление, млрд. кВт•ч"
KEY_INSTALLED = "Максимальная мощность, МВт"
KEY_DEMAND_MAX = "Максимум потребления мощности, МВт"
KEY_POWER_EXPORT = "Экспорт мощности, МВт"
KEY_CONSTRAINTS = "Ограничения, МВт"
KEY_Q4 = "Вводы мощности после прохождения максимума, МВт"
KEY_FLOW = "Переток мощности в смежные энергосистемы (выдача (-), прием (+))"
KEY_GAES = (
    "Потребление электрической энергии на производственные нужды ГАЭС "
    "в насосном режиме, млн. кВт•ч"
)
KEY_EE_EXPORT = "Экспорт электрической энергии, млрд. кВт•ч"
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
KEY_OZP_MAX = "Максимум потребления мощности ОЗП, МВт"
KEY_OZP_PEAK_DT = (
    "ОЗП. Дата и время прохождения максимума потребления мощности, дд.мм чч:мм"
)
KEY_ZONE_CODE = "external_code"
GENTYPES_INFO_COMMENT = (
    "ЧЧИУМ, дата/время максимума, ТНВ и потребление на час максимума ЕЭС "
    "берутся со сводки /power_demand/summary/oes/ из строк «… без НТ» "
    "(ЕЭС России без НТ, Первая синхронная зона без НТ и т.д.). "
    "Для ЕЭС потребление на час максимума ЕЭС = «Максимальное потребление мощности, МВт» "
    "той же строки; для синхронных зон — «Совмещенное потребление… на час максимума ЕЭС».\n\n"
    "Максимум потребления мощности ОЗП и дата/время максимума ОЗП — "
    "/power_demand/ozp_maxima/ (одно значение на период ОЗП, не в разрезе зоны) "
    "и пишутся только в строки ЕЭС России; у остальных зон — 0. "
    "Если на странице ОЗП пусто — 0.\n\n"
    "Для ТИТЭС Востока своей строки на сводках ОЭС нет "
    "(/power_demand/summary/oes/?ds_ues=317, "
    "/energy_consumption/summary/oes/?ds_ues=317): в JSON пишется сумма "
    "по РЭС этой ТИТЭС — «Максимальное потребление мощности, МВт» "
    "и потребление ЭЭ (млн кВт·ч → млрд в JSON). "
    "Потребление ЭЭ для ТИТЭС (Восток и Сибирь, РЭС и энергорайоны) — "
    "со сводки /energy_consumption/summary/oes/ из строки с вариантом периметра "
    "«не указано» (не «без НТ» и не О-1). "
    "ЧЧИУМ для ТИТЭС Востока и её РЭС/энергорайонов — как на той же сводке "
    "при кнопке «ЧЧИ»: (потребление, млн кВт·ч) / (максимум, МВт) × 1000, целое. "
    "Дата/время максимума и ТНВ у ТИТЭС Востока — с РЭС этой ТИТЭС "
    "с наибольшим «Максимальное потребление мощности» "
    "(на сводке у самой ОЭС этих полей нет). "
    "«Потребление мощности на час прохождения максимума ЕЭС России» "
    "для ТИТЭС Востока и её РЭС/энергорайонов — "
    "«Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт» "
    "со сводки /power_demand/summary/oes/?ds_ues=317; "
    "у самой ТИТЭС Востока — сумма этого показателя по РЭС.\n\n"
    "«Максимальная мощность, МВт» — Руст агрегационной строки своего уровня "
    "на /generation/stations/station_list?show_totals=1 "
    "(для ТИТЭС Востока — «ТИТЭС Востока, всего», для РЭС — «ЭС …, всего», "
    "для энергорайона — строка энергорайона; не сумма Руст+Ррасп).\n\n"
    "Поле «Прогнозируемые объемы капитальных вложений, млрд руб.» в набор не входит: "
    "такого показателя в разрезе зоны в АРМ нет.\n\n"
    "Поле external_code — это ref_uuid зоны из справочника "
    "(тип энергосистемы, синхронная зона, ОЭС, РЭС или энергорайон)."
)

_KIND_DEMAND = {
    "est": (EnergySystemTypeDemandParameter, "id_energy_system_type"),
    "ues": (UnionEnergySystemDemandParameter, "id_union_energy_system"),
    "sa": (SynchronousAreaDemandParameter, "id_synchronous_area"),
    "res": (RegionalEnergySystemDemandParameter, "id_regional_energy_system"),
    "eu": (EnergyUnitDemandParameter, "id_energy_unit"),
}


def _norm(text: str | None) -> str:
    return (text or "").casefold().replace("ё", "е").replace(" ", "").strip()


def select_gentypes_sheets(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ЕЭС + все СЗ + все ОЭС + энергорайоны ТИТЭС (без «не указано» / «Новые территории»)."""
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


def append_tites_res_sheets(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """После каждой ТИТЭС вставляет её РЭС (на балансе их нет, там энергорайоны)."""
    from app.energy_balance.services.power_balance_page_services import (
        GROUP_OES,
        _is_tites_east_name,
        _is_tites_sibir_name,
        _res_sheets_for_ues,
    )

    seen = {str(sheet.get("slug") or "") for sheet in sheets if sheet.get("slug")}
    result: list[dict[str, Any]] = []
    for sheet in sheets:
        result.append(sheet)
        if sheet.get("group") != GROUP_OES:
            continue
        name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
        if not (_is_tites_east_name(name) or _is_tites_sibir_name(name)):
            continue
        terr = sheet.get("territory") or {}
        try:
            ues_id = int(terr.get("id"))
        except (TypeError, ValueError):
            continue
        parent_slug = str(sheet.get("slug") or "")
        for res_sheet in _res_sheets_for_ues(ues_id, parent_slug):
            res_slug = str(res_sheet.get("slug") or "")
            if not res_slug or res_slug in seen:
                continue
            name_n = _norm(res_sheet.get("sheet_name"))
            if "неуказан" in name_n:
                continue
            seen.add(res_slug)
            result.append(res_sheet)
    return result


def load_gentypes_years(version_id: int | None) -> list[int]:
    """Годы: current_year − 5 … period_end, как у generation_stations / database_versions."""
    return load_exchange_years(version_id)


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


def _consumption_mlrd(value: Any) -> int:
    """Потребление в JSON: млн → млрд (/1000), целое."""
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


def _format_ozp_peak_dt(value: Any) -> str | int:
    """Дата/время максимума ОЗП со страницы ozp_maxima; пусто — 0."""
    try:
        text = normalize_ozp_peak_datetime(value)
    except ValueError:
        text = None
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


def _chi_as_on_oes_summary(consumption: Any, gaes: Any, demand_max: Any) -> int:
    """ЧЧИ как на /power_demand/summary/oes/ при кнопке «ЧЧИ»: целое."""
    try:
        cons = Decimal(str(consumption or 0))
        gaes_v = Decimal(str(gaes or 0))
        dem = Decimal(str(demand_max or 0))
    except Exception:
        return 0
    if dem == 0:
        return 0
    return _as_int((cons - gaes_v) / dem * 1000)


def _tites_east_branch_slugs(sheets: list[dict[str, Any]]) -> set[str]:
    """ТИТЭС Востока и её листы РЭС/энергорайонов (как ?ds_ues=317)."""
    from app.energy_balance.services.power_balance_page_services import (
        GROUP_EU,
        GROUP_OES,
        GROUP_RES,
        _is_tites_east_name,
    )

    east_slugs: set[str] = set()
    for sheet in sheets:
        name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
        slug = str(sheet.get("slug") or "")
        if slug and sheet.get("group") == GROUP_OES and _is_tites_east_name(name):
            east_slugs.add(slug)
    if not east_slugs:
        return set()
    branch = set(east_slugs)
    for sheet in sheets:
        slug = str(sheet.get("slug") or "")
        if (
            slug
            and sheet.get("group") in {GROUP_RES, GROUP_EU}
            and str(sheet.get("parent_slug") or "") in east_slugs
        ):
            branch.add(slug)
    return branch


def _sum_installed_for_year(cap_inputs: dict[str, Any], year: int) -> Decimal:
    """Руст агрегационной строки своего уровня (station_list «…, всего»)."""
    cap_inputs = cap_inputs or {}
    total_map = cap_inputs.get("installed_total")
    if isinstance(total_map, dict) and total_map.get(year) is not None:
        return Decimal(str(total_map[year]))
    allowed = set(installed_type_keys())
    total = Decimal(0)
    for key, year_map in cap_inputs.items():
        if key not in allowed or not isinstance(year_map, dict):
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
            joinedload(Station.energy_unit),
        )
        .filter(_version_filter(Station, version_id))
        .all()
    )
    # station_id → {sa_id, ues_id, est_id, res_id, eu_id}
    station_terr: dict[int, dict[str, int | None]] = {}
    for st in stations:
        district = getattr(st, "regional_district", None)
        sa = getattr(district, "synchronous_area", None) if district else None
        res = getattr(st, "regional_energy_system_obj", None)
        eu = getattr(st, "energy_unit", None)
        ues = getattr(res, "union_energy_system", None) if res else None
        ues_id = getattr(ues, "id", None) if ues else getattr(res, "id_union_energy_system", None)
        est_id = getattr(ues, "id_energy_system_type", None) if ues else None
        res_id = getattr(res, "id", None) if res else getattr(st, "id_regional_energy_system", None)
        if res_id is None and eu is not None:
            res_id = getattr(eu, "id_regional_energy_system", None)
        eu_id = getattr(eu, "id", None) if eu else getattr(st, "id_energy_unit", None)
        station_terr[int(st.id)] = {
            "sa": int(sa.id) if sa and getattr(sa, "id", None) else None,
            "ues": int(ues_id) if ues_id else None,
            "est": int(est_id) if est_id else None,
            "res": int(res_id) if res_id else None,
            "eu": int(eu_id) if eu_id else None,
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
                or (kind == "res" and terr.get("res") == parent_id)
                or (kind == "eu" and terr.get("eu") == parent_id)
            )
            if match:
                year_sum[year] = year_sum.get(year, Decimal(0)) + val
        result[slug] = year_sum
    return result


def _fill_tites_ues_metric_from_res(
    sheets: list[dict[str, Any]],
    maps: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
    *,
    key: str,
    extras: dict[str, dict[str, dict[int, Any]]] | None = None,
    extras_key: str | None = None,
) -> None:
    """ТИТЭС Востока на сводке ОЭС без своей строки: показатель = сумма РЭС.

    На /power_demand/summary/oes/?ds_ues=317 и
    /energy_consumption/summary/oes/?ds_ues=317 строка самой ОЭС пустая/скрыта;
    максимум мощности и потребление ЭЭ берутся из РЭС этой ТИТЭС (без О-1).
    """
    from app.energy_balance.services.power_balance_page_services import (
        GROUP_OES,
        GROUP_RES,
        _is_tites_east_name,
        _is_tites_sibir_name,
    )

    extra_maps = extras or {}
    extra_key = extras_key or key
    wanted = {int(y) for y in years}
    for sheet in sheets:
        if sheet.get("group") != GROUP_OES:
            continue
        name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
        if not (_is_tites_east_name(name) or _is_tites_sibir_name(name)):
            continue
        slug = str(sheet.get("slug") or "")
        if not slug:
            continue
        child_slugs = [
            str(child.get("slug") or "")
            for child in sheets
            if child.get("group") == GROUP_RES
            and str(child.get("parent_slug") or "") == slug
            and child.get("slug")
        ]
        if not child_slugs:
            continue
        year_map = (maps.get(slug) or {}).get(key) or {}
        extra_map = (extra_maps.get(slug) or {}).get(extra_key) or {}
        filled: dict[int, Decimal] = {}
        for year in wanted:
            if year_map.get(year) is not None or extra_map.get(year) is not None:
                continue
            total = Decimal(0)
            seen = False
            for child_slug in child_slugs:
                raw = _map_get(maps, child_slug, key, year)
                if raw is None:
                    raw = (extra_maps.get(child_slug) or {}).get(extra_key, {}).get(year)
                if raw is None:
                    continue
                seen = True
                total += Decimal(str(raw))
            if seen:
                filled[year] = total
        if not filled:
            continue
        maps.setdefault(slug, {}).setdefault(key, {}).update(filled)


def _fill_tites_ues_demand_max_from_res(
    sheets: list[dict[str, Any]],
    demand_max: dict[str, dict[str, dict[int, Any]]],
    extras: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
) -> None:
    _fill_tites_ues_metric_from_res(
        sheets,
        demand_max,
        years,
        key="demand_max",
        extras=extras,
        extras_key="demand_max",
    )


def _fill_tites_ues_consumption_from_res(
    sheets: list[dict[str, Any]],
    consumption: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
) -> None:
    _fill_tites_ues_metric_from_res(sheets, consumption, years, key="consumption")


def _fill_tites_ues_combined_from_res(
    sheets: list[dict[str, Any]],
    extras: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
) -> None:
    """ТИТЭС Востока: совмещённое на час ЕЭС = сумма РЭС со сводки ОЭС."""
    maps: dict[str, dict[str, dict[int, Any]]] = {}
    for slug, payload in extras.items():
        comb = (payload or {}).get("combined_on_ees") or {}
        maps[str(slug)] = {"combined_on_ees": dict(comb)}
    _fill_tites_ues_metric_from_res(sheets, maps, years, key="combined_on_ees")
    for slug, payload in maps.items():
        filled = payload.get("combined_on_ees") or {}
        if not filled:
            continue
        extras.setdefault(slug, {}).setdefault("combined_on_ees", {}).update(filled)


def _extra_has_value(value: Any) -> bool:
    if value is None or value == "" or value == 0:
        return False
    return True


def _pick_child_slug_with_peak(
    child_slugs: list[str],
    extras: dict[str, dict[str, dict[int, Any]]],
    demand_max: dict[str, dict[str, dict[int, Any]]],
    year: int,
) -> str | None:
    best_slug: str | None = None
    best_dem = Decimal("-1")
    for child_slug in child_slugs:
        peak = (extras.get(child_slug) or {}).get("peak_datetime", {}).get(year)
        if not _extra_has_value(peak):
            continue
        raw = _map_get(demand_max, child_slug, "demand_max", year)
        if raw is None:
            raw = (extras.get(child_slug) or {}).get("demand_max", {}).get(year)
        try:
            dem = Decimal(str(raw or 0))
        except Exception:
            dem = Decimal(0)
        if best_slug is None or dem > best_dem:
            best_dem = dem
            best_slug = child_slug
    return best_slug


def _fill_tites_east_peak_temp_from_res(
    sheets: list[dict[str, Any]],
    extras: dict[str, dict[str, dict[int, Any]]],
    demand_max: dict[str, dict[str, dict[int, Any]]],
    years: list[int],
) -> None:
    """ТИТЭС Востока: дата максимума и ТНВ со сводки ОЭС — с РЭС с наибольшим максимумом.

    На /power_demand/summary/oes/?ds_ues=317 у самой ОЭС этих строк нет;
    берём РЭС (иначе энергорайон) с датой максимума и наибольшим max_power.
    """
    from app.energy_balance.services.power_balance_page_services import (
        GROUP_EU,
        GROUP_OES,
        GROUP_RES,
        _is_tites_east_name,
    )

    wanted = {int(y) for y in years}
    for sheet in sheets:
        if sheet.get("group") != GROUP_OES:
            continue
        name = sheet.get("sheet_name") or (sheet.get("territory") or {}).get("name")
        if not _is_tites_east_name(name):
            continue
        slug = str(sheet.get("slug") or "")
        if not slug:
            continue
        res_slugs = [
            str(child.get("slug") or "")
            for child in sheets
            if child.get("group") == GROUP_RES
            and str(child.get("parent_slug") or "") == slug
            and child.get("slug")
        ]
        eu_slugs = [
            str(child.get("slug") or "")
            for child in sheets
            if child.get("group") == GROUP_EU
            and str(child.get("parent_slug") or "") == slug
            and child.get("slug")
        ]
        peak_map = (extras.get(slug) or {}).get("peak_datetime") or {}
        temp_map = (extras.get(slug) or {}).get("avg_daily_air_temp_c") or {}
        for year in wanted:
            if _extra_has_value(peak_map.get(year)) and _extra_has_value(temp_map.get(year)):
                continue
            source = _pick_child_slug_with_peak(
                res_slugs, extras, demand_max, year
            ) or _pick_child_slug_with_peak(eu_slugs, extras, demand_max, year)
            if not source:
                continue
            src = extras.get(source) or {}
            bucket = extras.setdefault(slug, {})
            if not _extra_has_value(peak_map.get(year)):
                peak_val = (src.get("peak_datetime") or {}).get(year)
                if _extra_has_value(peak_val):
                    bucket.setdefault("peak_datetime", {})[year] = peak_val
            if not _extra_has_value(temp_map.get(year)):
                temp_val = (src.get("avg_daily_air_temp_c") or {}).get(year)
                if _extra_has_value(temp_val):
                    bucket.setdefault("avg_daily_air_temp_c", {})[year] = temp_val
            peak_map = (extras.get(slug) or {}).get("peak_datetime") or {}
            temp_map = (extras.get(slug) or {}).get("avg_daily_air_temp_c") or {}


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


def _sheet_external_code(
    sheet: dict[str, Any],
    codes: dict[tuple[str, int], str],
) -> str:
    terr = sheet.get("territory") or {}
    kind = terr.get("kind")
    tid = terr.get("id")
    if kind and tid is not None:
        try:
            return codes.get((str(kind), int(tid)), "") or ""
        except (TypeError, ValueError):
            return ""
    resolved = resolve_demand_max_territory(sheet)
    if not resolved:
        return ""
    try:
        return codes.get((str(resolved["kind"]), int(resolved["id"])), "") or ""
    except (TypeError, ValueError, KeyError):
        return ""


def _load_territory_external_codes(
    version_id: int | None,
) -> dict[tuple[str, int], str]:
    result: dict[tuple[str, int], str] = {}
    for kind, model in (
        ("est", EnergySystemType),
        ("sa", SynchronousArea),
        ("ues", UnionEnergySystem),
        ("res", RegionalEnergySystem),
        ("eu", EnergyUnit),
    ):
        rows = (
            db.session.query(model.id, model.ref_uuid)
            .filter(_version_filter(model, version_id))
            .all()
        )
        for oid, code in rows:
            if oid is None:
                continue
            result[(kind, int(oid))] = (code or "").strip()
    return result


def _load_ozp_rows_for_years(
    version_id: int | None,
    years: list[int],
) -> dict[int, Any]:
    """ОЗП year-1–year: ozp_end_year = календарный год строки."""
    wanted = {int(y) for y in years}
    by_end = load_ozp_rows_by_end_year(version_id=version_id)
    return {year: by_end.get(year) for year in wanted}


def build_gentypes_year_row(
    *,
    year: int,
    zone: str | None,
    consumption: Any,
    installed: Any,
    demand_max: Any,
    power_export: Any,
    constraints: Any,
    q4: Any,
    flow: Any,
    gaes: Any,
    ee_export: Any,
    chi: Any,
    peak_dt: Any,
    temp: Any,
    combined: Any,
    ozp_max: Any,
    ozp_peak_dt: Any,
    external_code: str | None,
) -> dict[str, Any]:
    return {
        KEY_YEAR: int(year),
        KEY_ZONE: zone,
        KEY_CONSUMPTION: consumption,
        KEY_INSTALLED: installed,
        KEY_DEMAND_MAX: demand_max,
        KEY_POWER_EXPORT: power_export,
        KEY_CONSTRAINTS: constraints,
        KEY_Q4: q4,
        KEY_FLOW: flow,
        KEY_GAES: gaes,
        KEY_EE_EXPORT: ee_export,
        KEY_CHI: chi,
        KEY_PEAK_DT: peak_dt,
        KEY_TEMP: temp,
        KEY_COMBINED: combined,
        KEY_OZP_MAX: ozp_max,
        KEY_OZP_PEAK_DT: ozp_peak_dt,
        KEY_ZONE_CODE: external_code or "",
    }


def build_gentypes_info_rows(
    *,
    years: list[int],
    sheets: list[dict[str, Any]],
    version_id: int | None,
) -> list[dict[str, Any]]:
    if not years or not sheets:
        return []

    consumption = load_ee_balance_consumption_inputs(years, sheets)
    _fill_tites_ues_consumption_from_res(sheets, consumption, years)
    demand_max = load_power_balance_demand_max_inputs(years, sheets)
    power_export = load_power_balance_export_inputs(years, sheets)
    ee_export = load_ee_balance_export_inputs(years, sheets)
    capacity = load_power_balance_installed_capacity_inputs(years, sheets)
    extras = _load_demand_extras(sheets, years)
    _fill_tites_ues_demand_max_from_res(sheets, demand_max, extras, years)
    _fill_tites_ues_combined_from_res(sheets, extras, years)
    _fill_tites_east_peak_temp_from_res(sheets, extras, demand_max, years)
    flows = _custom_flow_net_by_slug(sheets, years)
    gaes_map = _load_gaes_by_sheet(sheets, years, version_id)
    ozp_by_year = _load_ozp_rows_for_years(version_id, years)
    zone_codes = _load_territory_external_codes(version_id)
    tites_east_chi_slugs = _tites_east_branch_slugs(sheets)

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
            is_sz = sheet.get("group") == GROUP_SZ
            if is_ees:
                # Сводка ОЭС: у «ЕЭС России без НТ» совмещённое на час ЕЭС =
                # «Максимальное потребление мощности, МВт».
                combined = dem
            elif not is_sz and combined is None:
                combined = 0

            ozp_row = ozp_by_year.get(int(year)) if is_ees else None
            ozp_max = (
                getattr(ozp_row, "max_power_mw", None) if ozp_row is not None else None
            )
            ozp_peak = (
                getattr(ozp_row, "peak_datetime", None) if ozp_row is not None else None
            )
            rows.append(
                build_gentypes_year_row(
                    year=year,
                    zone=zone,
                    consumption=_consumption_mlrd(cons),
                    installed=_as_int(installed),
                    demand_max=_as_int(dem),
                    power_export=_as_int(p_exp),
                    constraints=_as_int(constraints),
                    q4=_as_int(q4),
                    flow=_as_int(flow),
                    gaes=_as_int(gaes),
                    ee_export=_as_fixed(ee_exp, 2),
                    chi=(
                        _chi_as_on_oes_summary(cons, gaes, dem)
                        if slug in tites_east_chi_slugs
                        else _chi(cons, gaes, dem)
                    ),
                    peak_dt=_format_peak_dt(peak),
                    temp=_num(_as_fixed(temp, 1)) if temp is not None else 0,
                    combined=_as_int(combined),
                    ozp_max=_as_int(ozp_max),
                    ozp_peak_dt=_format_ozp_peak_dt(ozp_peak),
                    external_code=_sheet_external_code(sheet, zone_codes),
                )
            )
    return rows


_VERSION_CONTEXT_UNSET = object()


def load_gentypes_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    from flask import g

    prev_version = getattr(g, "current_db_version", _VERSION_CONTEXT_UNSET)
    if resolved_id is not None:
        g.current_db_version = resolved_id
    try:
        years = clip_years(
            load_gentypes_years(resolved_id),
            year=year,
            start_year=start_year,
            end_year=end_year,
        )
        sheets = append_tites_res_sheets(
            select_gentypes_sheets(get_power_balance_sheets())
        )
        rows = build_gentypes_info_rows(
            years=years,
            sheets=sheets,
            version_id=resolved_id,
        )
        return dataset_envelope(
            DATASET_GENTYPES_INFO,
            database_version=resolved_id,
            version_number=version_number,
            comment=GENTYPES_INFO_COMMENT,
            rows=rows,
        )
    finally:
        if prev_version is _VERSION_CONTEXT_UNSET:
            if hasattr(g, "current_db_version"):
                delattr(g, "current_db_version")
        else:
            g.current_db_version = prev_version
