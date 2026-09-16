# -*- coding: utf-8 -*-
"""Выработка ЭЭ по типам станций для листов баланса электрической энергии.

Источники по признаку года (YearFeature):
- факт / текущий — суммы со страницы ee_generation (станция × год × тип × зона);
- план — для ТЭС суммы столбца «Выработка ЭЭ» (E) со страницы
  stations_equipment_group_fuel_params (группа × год × зона);
  для остальных типов (АЭС, ГЭС, ГАЭС, СНЭЭ) — те же суммы
  со страницы ee_generation, что и для факт/текущий;
  для СЭС/ВЭС в плановых (и при необходимости текущем) годах, если в
  ``StationEnergyGeneration`` нет значения, подставляется тот же расчёт, что
  на карточке станции / странице «Выработка ВИЭ»
  (``compute_ves_ses_plan_generation``).

Для ГЭС и ГАЭС дополнительно суммируется годовой итог таблицы
«Прогноз выработки электрической энергии электростанцией» с карточек
перспективных площадок: средневодный год (сценарий medium_50 / 50%) —
только ОЭС Северо-Запада, Центра, Волги, Урала и Юга; у остальных
листов — маловодный год (low_95 / 95%). Суммы ЕЭС и 1-й СЗ складывают
листы с этой же водностью.
"""

from __future__ import annotations

import logging
from decimal import Decimal

_logger = logging.getLogger(__name__)
from typing import Any

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.energy_balance.services.power_balance_installed_capacity_services import (
    get_power_balance_station_type_groups,
    iter_station_type_groups,
    resolve_sheet_territory,
    resolve_station_balance_territory,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    load_annual_generation_by_station,
)
from app.generation.models.station.station_model import Station

GENERATION_TES_KEY = "generation_tes"
GENERATION_AES_KEY = "generation_aes"
GENERATION_GES_KEY = "generation_ges"
GENERATION_GAES_KEY = "generation_gaes"

HYDRO_YEAR_AVERAGE = "average"
HYDRO_YEAR_LOW = "low"
_HYDRO_YEAR_LOW_ALIASES = {"low", "malovodnyy", "маловодный"}
# Средневодный год — только эти ОЭС; у остальных (Сибирь, Восток, ТИТЭС, …) маловодный.
AVERAGE_HYDRO_YEAR_SLUGS = frozenset(
    {"severo-zapad", "centr", "srednyaya-volga", "ural", "yug"}
)
# ЕЭС и 1-я СЗ складывают ОЭС с разной водностью — отдельного варианта нет.
MIXED_HYDRO_YEAR_LAYOUTS = frozenset({"ees_rossii", "sz1"})


def _generation_group_from_installed(group: dict[str, Any]) -> dict[str, Any]:
    key = str(group.get("key") or "")
    if key.startswith("installed_"):
        key = "generation_" + key[len("installed_") :]
    children = [
        _generation_group_from_installed(child) for child in (group.get("children") or [])
    ]
    return {**group, "key": key, "children": children}


def generation_type_groups() -> list[dict[str, Any]]:
    return [
        _generation_group_from_installed(group)
        for group in get_power_balance_station_type_groups()
    ]


def generation_type_keys(groups: list[dict[str, Any]] | None = None) -> tuple[str, ...]:
    items = groups if groups is not None else generation_type_groups()
    return tuple(group["key"] for group in items)


def _decimal_or_zero(raw: Any) -> Decimal:
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


def _norm_year_feature(name: Any) -> str:
    return " ".join(str(name or "").split()).casefold().replace("ё", "е")


def classify_ee_balance_generation_years(
    years: list[int],
    year_features: dict[Any, Any] | None = None,
) -> tuple[list[int], list[int]]:
    """Делит годы на (факт/текущий, план) по признаку YearFeature."""
    if year_features is None:
        from app.common.services.get_services.years.year_feature_services import (
            get_year_feature_dict,
        )

        year_features = get_year_feature_dict() or {}
    fact_current: list[int] = []
    plan: list[int] = []
    for year in years:
        year_int = int(year)
        raw = year_features.get(year_int)
        if raw is None:
            raw = year_features.get(year)
        feature = _norm_year_feature(raw)
        if feature.startswith("факт") or feature.startswith("текущий"):
            fact_current.append(year_int)
        elif feature == "план" or feature.startswith("план"):
            plan.append(year_int)
    return fact_current, plan


def _tes_generation_key(groups: list[dict[str, Any]]) -> str:
    for group in groups:
        key = str(group.get("key") or "")
        if key == GENERATION_TES_KEY:
            return key
        label = _norm_year_feature(group.get("label"))
        if "тэс" in label:
            return key
    return GENERATION_TES_KEY


def _plan_generation_keys_from_ee(groups: list[dict[str, Any]], tes_key: str) -> set[str]:
    """Плановые годы: все типы кроме ТЭС берутся со страницы ee_generation."""
    return {
        str(group["key"])
        for group in iter_station_type_groups(groups)
        if str(group.get("key") or "") and str(group["key"]) != tes_key
    }


def forecast_scenario_for_hydro_year(hydro_year: Any) -> str:
    """Вкладка баланса → сценарий прогноза на карточке ГЭС/ГАЭС."""
    from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
        SCENARIO_LOW_95,
        SCENARIO_MEDIUM_50,
    )

    raw = str(hydro_year or "").strip().casefold().replace("ё", "е")
    if raw in _HYDRO_YEAR_LOW_ALIASES:
        return SCENARIO_LOW_95
    return SCENARIO_MEDIUM_50


def _norm_hydro_sheet_name(name: Any) -> str:
    return (
        str(name or "")
        .casefold()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )


def _is_average_hydro_oes_sheet(sheet: dict[str, Any] | None) -> bool:
    if not sheet:
        return False
    slug = str(sheet.get("slug") or "").strip()
    if slug in AVERAGE_HYDRO_YEAR_SLUGS:
        return True
    if str(sheet.get("layout") or "") == "oes_yug":
        return True
    if str(sheet.get("group") or "") != "oes":
        return False
    name = _norm_hydro_sheet_name(sheet.get("sheet_name"))
    if not name:
        name = _norm_hydro_sheet_name((sheet.get("territory") or {}).get("name"))
    if "северо" in name and "запад" in name:
        return True
    if "центр" in name and "северо" not in name:
        return True
    if "волг" in name:
        return True
    if "урал" in name:
        return True
    if "юг" in name and "восток" not in name and "сибир" not in name:
        return True
    return False


def _ues_id_from_oes_parent_slug(slug: str) -> int | None:
    text = str(slug or "").strip()
    if not text.startswith("oes-"):
        return None
    try:
        value = int(text.split("-", 1)[1])
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def hydro_year_for_balance_sheet(
    sheet: dict[str, Any] | None,
    sheets: list[dict[str, Any]] | None = None,
) -> str | None:
    """Водность листа: средневодный / маловодный / None (смешанный ЕЭС и 1-я СЗ)."""
    if not sheet:
        return HYDRO_YEAR_LOW
    if str(sheet.get("layout") or "") in MIXED_HYDRO_YEAR_LAYOUTS:
        return None
    by_slug: dict[str, dict[str, Any]] = {}
    by_ues_id: dict[int, dict[str, Any]] = {}
    for item in sheets or []:
        slug = str(item.get("slug") or "").strip()
        if slug:
            by_slug[slug] = item
        territory = item.get("territory") or {}
        if str(territory.get("kind") or "") != "ues":
            continue
        try:
            by_ues_id[int(territory["id"])] = item
        except (TypeError, ValueError, KeyError):
            continue
    current: dict[str, Any] | None = sheet
    seen: set[str] = set()
    while current:
        slug = str(current.get("slug") or "").strip()
        if slug:
            if slug in seen:
                break
            seen.add(slug)
        if _is_average_hydro_oes_sheet(current):
            return HYDRO_YEAR_AVERAGE
        parent_slug = str(current.get("parent_slug") or "").strip()
        if not parent_slug:
            break
        if parent_slug in AVERAGE_HYDRO_YEAR_SLUGS:
            return HYDRO_YEAR_AVERAGE
        nxt = by_slug.get(parent_slug)
        if nxt is None:
            ues_id = _ues_id_from_oes_parent_slug(parent_slug)
            if ues_id is not None:
                nxt = by_ues_id.get(ues_id)
        if nxt is None:
            break
        current = nxt
    return HYDRO_YEAR_LOW


def _hydro_map_for_territory(
    hydro_pack: tuple[Any, ...] | None,
    kind: str,
    entity_id: int,
) -> dict[str, dict[int, Decimal]] | None:
    if not hydro_pack:
        return None
    ues_by_key, sa_by_key, res_by_key, eu_by_key = hydro_pack
    if kind == "ues":
        return ues_by_key.get(entity_id)
    if kind == "sa":
        return sa_by_key.get(entity_id)
    if kind == "res":
        return res_by_key.get(entity_id)
    if kind == "eu":
        return eu_by_key.get(entity_id)
    return None


def _int_id_or_none(raw: Any) -> int | None:
    try:
        if raw is None or raw == "":
            return None
        value = int(raw)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _generation_key_for_place_kind(
    place_kind: str,
    groups: list[dict[str, Any]],
) -> str | None:
    kind = str(place_kind or "").strip().casefold()
    if kind == "ges":
        wanted = GENERATION_GES_KEY
    elif kind == "gaes":
        wanted = GENERATION_GAES_KEY
    else:
        return None
    keys = {str(group.get("key") or "") for group in groups}
    if wanted in keys:
        return wanted
    return None


def _merge_generation_by_territory(
    target: dict[int, dict[str, dict[int, Decimal]]],
    extra: dict[int, dict[str, dict[int, Decimal]]] | None,
) -> None:
    for entity_id, by_key in (extra or {}).items():
        dest = target.setdefault(entity_id, {})
        for group_key, year_map in (by_key or {}).items():
            bucket = dest.setdefault(group_key, {})
            for year, amount in (year_map or {}).items():
                bucket[year] = bucket.get(year, Decimal("0")) + _decimal_or_zero(amount)


def accumulate_hydro_forecast_generation(
    items: list[dict[str, Any]],
    years: list[int],
    res_to_ues: dict[int, int],
    district_to_ues: dict[int, int],
    district_to_sa: dict[int, int],
) -> tuple[
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
]:
    """Раскладывает годовой прогноз площадок по ОЭС / СЗ / РЭС / энергорайонам."""
    ues_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    sa_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    res_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    eu_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    year_list = [int(year) for year in years]

    def _add(
        buckets: dict[int, dict[str, dict[int, Decimal]]],
        entity_id: int | None,
        group_key: str,
        amount: Decimal,
    ) -> None:
        if entity_id is None:
            return
        bucket = buckets.setdefault(int(entity_id), {}).setdefault(group_key, {})
        for year in year_list:
            bucket[year] = bucket.get(year, Decimal("0")) + amount

    for item in items:
        group_key = str(item.get("group_key") or "")
        if not group_key:
            continue
        amount = _decimal_or_zero(item.get("amount"))
        if amount == 0 and item.get("amount") is None:
            continue
        res_id = _int_id_or_none(item.get("res_id"))
        district_id = _int_id_or_none(item.get("district_id"))
        eu_id = _int_id_or_none(item.get("eu_id"))
        ues_id, sa_id = resolve_station_balance_territory(
            id_regional_energy_system=res_id,
            id_regional_district=district_id,
            res_to_ues=res_to_ues,
            district_to_ues=district_to_ues,
            district_to_sa=district_to_sa,
        )
        _add(ues_by_key, ues_id, group_key, amount)
        _add(sa_by_key, sa_id, group_key, amount)
        _add(res_by_key, res_id, group_key, amount)
        _add(eu_by_key, eu_id, group_key, amount)
    return ues_by_key, sa_by_key, res_by_key, eu_by_key


def _load_forecast_year_totals_by_place(scenario: str) -> dict[tuple[str, int], Decimal]:
    from app.generation.prospective_places.models.prospective_place_hydro_energy_forecast_model import (
        HYDRO_MONTH_ORDER,
        ProspectivePlaceHydroEnergyForecast,
    )
    from app.generation.prospective_places.services.hydro_energy_forecast_services import (
        sum_months,
    )

    query = ProspectivePlaceHydroEnergyForecast.query.filter(
        ProspectivePlaceHydroEnergyForecast.scenario == scenario,
    )
    query = filter_by_db_version(query, ProspectivePlaceHydroEnergyForecast)
    by_place: dict[tuple[str, int], dict[int, Any]] = {}
    for row in query.all():
        kind = str(getattr(row, "place_kind", None) or "").strip().casefold()
        place_id = _int_id_or_none(getattr(row, "place_id", None))
        month = _int_id_or_none(getattr(row, "month_number", None))
        if not kind or place_id is None or month not in HYDRO_MONTH_ORDER:
            continue
        by_place.setdefault((kind, place_id), {})[month] = row.electricity_generation
    totals: dict[tuple[str, int], Decimal] = {}
    for key, months in by_place.items():
        total = sum_months(months)
        if total is not None:
            totals[key] = total
    return totals


def _load_ges_gaes_places_by_ids(
    ges_ids: set[int],
    gaes_ids: set[int],
) -> tuple[list[Any], list[Any]]:
    from sqlalchemy.orm import joinedload

    from app.generation.prospective_places.models.gaes.station_prospective_place_gaes_model import (
        StationProspectivePlaceGAES,
    )
    from app.generation.prospective_places.models.ges.station_prospective_place_ges_model import (
        StationProspectivePlaceGES,
    )

    ges_places: list[Any] = []
    gaes_places: list[Any] = []
    if ges_ids:
        ges_places = list(
            StationProspectivePlaceGES.query.filter(
                StationProspectivePlaceGES.id.in_(ges_ids)
            )
            .options(joinedload(StationProspectivePlaceGES.station))
            .all()
        )
    if gaes_ids:
        gaes_places = list(
            StationProspectivePlaceGAES.query.filter(
                StationProspectivePlaceGAES.id.in_(gaes_ids)
            )
            .options(joinedload(StationProspectivePlaceGAES.station))
            .all()
        )
    return ges_places, gaes_places


def _place_territory_ids(
    place: Any,
    single_eu_by_res: dict[int, int],
) -> tuple[int | None, int | None, int | None]:
    station = getattr(place, "station", None)
    res_id = _int_id_or_none(
        getattr(station, "id_regional_energy_system", None) if station is not None else None
    )
    district_id = _int_id_or_none(
        getattr(station, "id_regional_district", None) if station is not None else None
    )
    eu_id = _int_id_or_none(
        getattr(station, "id_energy_unit", None) if station is not None else None
    )
    if res_id is None:
        res_id = _int_id_or_none(getattr(place, "id_regional_energy_system", None))
    if district_id is None:
        district_id = _int_id_or_none(getattr(place, "id_regional_district", None))
    if eu_id is None and res_id is not None:
        eu_id = single_eu_by_res.get(res_id)
    return res_id, district_id, eu_id


def _hydro_forecast_items_from_places(
    *,
    groups: list[dict[str, Any]],
    totals: dict[tuple[str, int], Decimal],
    ges_places: list[Any],
    gaes_places: list[Any],
    single_eu_by_res: dict[int, int],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kind, places in (("ges", ges_places), ("gaes", gaes_places)):
        group_key = _generation_key_for_place_kind(kind, groups)
        if not group_key:
            continue
        for place in places:
            place_id = _int_id_or_none(getattr(place, "id", None))
            if place_id is None:
                continue
            amount = totals.get((kind, place_id))
            if amount is None:
                continue
            res_id, district_id, eu_id = _place_territory_ids(place, single_eu_by_res)
            items.append(
                {
                    "group_key": group_key,
                    "amount": amount,
                    "res_id": res_id,
                    "district_id": district_id,
                    "eu_id": eu_id,
                }
            )
    return items


def _load_hydro_forecast_generation_by_territory(
    years: list[int],
    groups: list[dict[str, Any]],
    hydro_year: Any,
) -> tuple[
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
]:
    if not years:
        return {}, {}, {}, {}
    scenario = forecast_scenario_for_hydro_year(hydro_year)
    totals = _load_forecast_year_totals_by_place(scenario)
    if not totals:
        return {}, {}, {}, {}
    ges_ids = {place_id for kind, place_id in totals if kind == "ges"}
    gaes_ids = {place_id for kind, place_id in totals if kind == "gaes"}
    ges_places, gaes_places = _load_ges_gaes_places_by_ids(ges_ids, gaes_ids)
    single_eu_by_res = _single_energy_unit_id_by_res()
    items = _hydro_forecast_items_from_places(
        groups=groups,
        totals=totals,
        ges_places=ges_places,
        gaes_places=gaes_places,
        single_eu_by_res=single_eu_by_res,
    )
    if not items:
        return {}, {}, {}, {}
    res_ids: set[int] = set()
    district_ids: set[int] = set()
    for item in items:
        res_id = _int_id_or_none(item.get("res_id"))
        district_id = _int_id_or_none(item.get("district_id"))
        if res_id:
            res_ids.add(res_id)
        if district_id:
            district_ids.add(district_id)
    try:
        res_to_ues, district_to_ues, district_to_sa = _territory_lookups(
            res_ids, district_ids
        )
    except Exception:
        _logger.exception("ee balance generation: hydro territory lookups failed")
        res_to_ues, district_to_ues, district_to_sa = {}, {}, {}
    return accumulate_hydro_forecast_generation(
        items,
        years,
        res_to_ues,
        district_to_ues,
        district_to_sa,
    )


def _territory_lookups(
    res_ids: set[int],
    district_ids: set[int],
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    res_to_ues: dict[int, int] = {}
    if res_ids:
        for res in RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(res_ids)):
            ues_id = getattr(res, "id_union_energy_system", None)
            if ues_id:
                res_to_ues[int(res.id)] = int(ues_id)
    district_to_ues: dict[int, int] = {}
    district_to_sa: dict[int, int] = {}
    if district_ids:
        for district in RegionalDistrict.query.filter(RegionalDistrict.id.in_(district_ids)):
            sa_id = getattr(district, "id_synchronous_area", None)
            if sa_id:
                district_to_sa[int(district.id)] = int(sa_id)
            for res in district.regional_energy_systems or []:
                ues_id = getattr(res, "id_union_energy_system", None)
                if ues_id:
                    district_to_ues[int(district.id)] = int(ues_id)
                    break
    return res_to_ues, district_to_ues, district_to_sa


def _type_id_to_group_key(groups: list[dict[str, Any]]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for group in iter_station_type_groups(groups):
        for type_id in group.get("type_ids") or ():
            try:
                mapping[int(type_id)] = str(group["key"])
            except (TypeError, ValueError, KeyError):
                continue
    return mapping


def _ves_ses_type_key_from_group(group_key: str | None) -> str | None:
    """Ключ типа для расчёта плана ВИЭ; None — станция не СЭС/ВЭС."""
    key = str(group_key or "")
    if key == "generation_ses":
        return "ses"
    if key == "generation_ves":
        return "ves"
    if key == "generation_ses_ves":
        return "other"
    return None


def _load_owner_generation_by_station(
    station_ids: list[int],
    start_year: int,
    end_year: int,
) -> dict[int, dict[int, Any]]:
    """station_id -> {year: electricity_generation} от собственника (ВЭС/СЭС)."""
    if not station_ids or start_year > end_year:
        return {}
    from collections import defaultdict

    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_owner_energy_generation_model import (
        StationOwnerEnergyGeneration,
    )

    version_id = get_current_db_version_id()
    query = StationOwnerEnergyGeneration.query.filter(
        StationOwnerEnergyGeneration.id_station.in_(station_ids),
        StationOwnerEnergyGeneration.year_number >= int(start_year),
        StationOwnerEnergyGeneration.year_number <= int(end_year),
    )
    query = filter_by_explicit_db_version(query, StationOwnerEnergyGeneration, version_id)
    result: dict[int, dict[int, Any]] = defaultdict(dict)
    for row in query.all():
        if row.id_station is None or row.year_number is None:
            continue
        result[int(row.id_station)][int(row.year_number)] = row.electricity_generation
    return dict(result)


def apply_ves_ses_plan_generation_to_station_map(
    stations: list[Any],
    generation_by_station: dict[int, dict[int, Any]],
    type_to_key: dict[int, str],
    *,
    years: list[int],
    year_features: dict[Any, Any] | None = None,
) -> dict[int, dict[int, Any]]:
    """В пустые годы СЭС/ВЭС подставляет расчёт с карточки станции (без записи в БД).

    Для каждого года из ``years``: если в ``generation_by_station`` нет значения
    (``None`` / ключ отсутствует), берётся ``compute_ves_ses_plan_generation``.
    Явно сохранённый ноль оставляем.
    """
    if not stations or not years or not type_to_key:
        return generation_by_station

    ves_ses_stations: list[tuple[Any, str]] = []
    for station in stations:
        type_id = getattr(station, "id_station_type", None)
        if type_id is None:
            continue
        try:
            group_key = type_to_key.get(int(type_id))
        except (TypeError, ValueError):
            continue
        type_key = _ves_ses_type_key_from_group(group_key)
        if type_key is None:
            continue
        if getattr(station, "id", None) is None:
            continue
        ves_ses_stations.append((station, type_key))
    if not ves_ses_stations:
        return generation_by_station

    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict,
    )
    from app.generation.services.station_services.ves_ses_plan_generation_services import (
        classify_ves_ses_generation_years,
        compute_ves_ses_plan_generation,
        load_station_commission_years,
        load_station_exploitation_dates,
        seven_year_sample_window,
    )

    features = year_features if year_features is not None else (get_year_feature_dict() or {})
    current_year, plan_years = classify_ves_ses_generation_years(features)
    year_set = {int(year) for year in years}
    plan_in_scope = [year for year in plan_years if year in year_set]
    if current_year is None and not plan_in_scope:
        return generation_by_station

    station_ids = [int(station.id) for station, _type_key in ves_ses_stations]
    load_start = min(year_set)
    load_end = max(year_set)
    if current_year is not None:
        load_start = min(load_start, seven_year_sample_window(int(current_year))[0])
        load_end = max(load_end, int(current_year))

    # Догружаем факт для окна «7 лет», если карту строили только по плановым годам.
    try:
        extended = load_annual_generation_by_station(station_ids, load_start, load_end)
    except Exception:
        _logger.exception("ee balance generation: ves/ses extended generation load failed")
        extended = {}
    for sid, year_map in extended.items():
        bucket = generation_by_station.setdefault(int(sid), {})
        for year, value in year_map.items():
            if year not in bucket or bucket.get(year) is None:
                bucket[int(year)] = value

    try:
        owner_by_station = _load_owner_generation_by_station(station_ids, load_start, load_end)
    except Exception:
        _logger.exception("ee balance generation: owner generation load failed")
        owner_by_station = {}
    version_id = get_current_db_version_id()
    try:
        commission_by_station = load_station_commission_years(station_ids, version_id)
        exploitation_by_station = load_station_exploitation_dates(station_ids, version_id)
    except Exception:
        _logger.exception("ee balance generation: station commission/exploitation load failed")
        commission_by_station, exploitation_by_station = {}, {}
    try:
        from app.energy_balance.services.ee_balance_ves_ses_page_services import (
            _load_stations_p_ust,
        )

        # Как на странице ВИЭ: Руст за окно 7 лет факта + текущий + годы листа.
        # Иначе «первое появление Руст» попадает в текущий/план, и план
        # ошибочно считается как Руст×коэффициент вместо min за 7 лет.
        capacity_years = set(year_set)
        if current_year is not None:
            capacity_years.add(int(current_year))
            window_start, window_end = seven_year_sample_window(int(current_year))
            capacity_years.update(range(int(window_start), int(window_end) + 1))
        p_ust_by_station = _load_stations_p_ust(
            station_ids, sorted(capacity_years), version_id
        )
    except Exception:
        _logger.exception("ee balance generation: ves/ses p_ust load failed")
        p_ust_by_station = {}

    for station, type_key in ves_ses_stations:
        station_id = int(station.id)
        energy_full = dict(generation_by_station.get(station_id) or {})
        _min_sample, plan_calc, _rules = compute_ves_ses_plan_generation(
            energy_full,
            owner_by_station.get(station_id) or {},
            current_year=current_year,
            plan_years=plan_years,
            commission_year=commission_by_station.get(station_id),
            capacity_by_year=p_ust_by_station.get(station_id) or {},
            type_key=type_key,
            exploitation_date_expected=exploitation_by_station.get(station_id) or "",
        )
        if not plan_calc:
            continue
        bucket = generation_by_station.setdefault(station_id, {})
        for year, value in plan_calc.items():
            year_int = int(year)
            if year_int not in year_set:
                continue
            if bucket.get(year_int) is not None:
                continue
            bucket[year_int] = value
    return generation_by_station


def _fuel_param_e_participates(ved: Any) -> bool:
    """Как на fuel_params: ved>0 в сумме; ved=0 — оболочка; ved NULL — legacy, тоже в сумме."""
    if ved is None:
        return True
    try:
        return int(ved) > 0
    except (TypeError, ValueError):
        return False


def _sheet_specs(sheets: list[dict[str, Any]] | None) -> list[tuple[str, dict[str, Any] | None]]:
    if not sheets:
        return []
    specs: list[tuple[str, dict[str, Any] | None]] = []
    for sheet in sheets:
        if (
            sheet.get("skip_table")
            or sheet.get("skip_direct_capacity")
            or sheet.get("layout") in {"ees_rossii", "sz1"}
        ):
            continue
        specs.append((sheet["slug"], sheet.get("territory")))
    return specs


def _empty_sheet_inputs(
    groups: list[dict[str, Any]],
    years: list[int],
) -> dict[str, dict[int, Decimal]]:
    return {
        group["key"]: {year: Decimal("0") for year in years}
        for group in iter_station_type_groups(groups)
        if group.get("key")
    }


def _accumulate_station_generation_by_territory(
    stations: list[Any],
    generation_by_station: dict[int, dict[int, Any]],
    type_to_key: dict[int, str],
    years: list[int],
    res_to_ues: dict[int, int],
    district_to_ues: dict[int, int],
    district_to_sa: dict[int, int],
    *,
    plan_years: set[int] | None = None,
    plan_group_keys: set[str] | None = None,
) -> tuple[
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
    dict[int, dict[str, dict[int, Decimal]]],
]:
    ues_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    sa_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    res_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    eu_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    plan_year_set = plan_years or set()
    plan_keys = plan_group_keys or set()
    for station in stations:
        type_id = getattr(station, "id_station_type", None)
        group_key = type_to_key.get(int(type_id)) if type_id is not None else None
        if not group_key:
            continue
        station_id = int(station.id)
        year_map = generation_by_station.get(station_id) or {}
        res_id = getattr(station, "id_regional_energy_system", None)
        district_id = getattr(station, "id_regional_district", None)
        ues_id, sa_id = resolve_station_balance_territory(
            id_regional_energy_system=int(res_id) if res_id else None,
            id_regional_district=int(district_id) if district_id else None,
            res_to_ues=res_to_ues,
            district_to_ues=district_to_ues,
            district_to_sa=district_to_sa,
        )
        try:
            res_int = int(res_id) if res_id else None
        except (TypeError, ValueError):
            res_int = None
        try:
            eu_raw = getattr(station, "id_energy_unit", None)
            eu_int = int(eu_raw) if eu_raw else None
        except (TypeError, ValueError):
            eu_int = None
        for year in years:
            if year in plan_year_set and group_key not in plan_keys:
                continue
            value = year_map.get(year)
            if value is None:
                continue
            amount = _decimal_or_zero(value)
            if ues_id is not None:
                ues_by_key.setdefault(ues_id, {}).setdefault(group_key, {})
                bucket = ues_by_key[ues_id][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount
            if sa_id is not None:
                sa_by_key.setdefault(sa_id, {}).setdefault(group_key, {})
                bucket = sa_by_key[sa_id][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount
            if res_int:
                res_by_key.setdefault(res_int, {}).setdefault(group_key, {})
                bucket = res_by_key[res_int][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount
            if eu_int:
                eu_by_key.setdefault(eu_int, {}).setdefault(group_key, {})
                bucket = eu_by_key[eu_int][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount
    return ues_by_key, sa_by_key, res_by_key, eu_by_key


def _load_stations_for_generation() -> list[Any]:
    from app.generation.services.station_services.station_services import get_filtered_station_ids

    try:
        station_ids = get_filtered_station_ids({})
    except Exception:
        _logger.exception("ee balance generation: filtered station ids load failed")
        station_ids = []
    if not station_ids:
        return []
    try:
        query = Station.query.filter(Station.id.in_(station_ids))
        query = filter_by_db_version(query, Station)
        return list(
            query.with_entities(
                Station.id,
                Station.id_station_type,
                Station.id_regional_energy_system,
                Station.id_regional_district,
                Station.id_energy_unit,
            ).all()
        )
    except Exception:
        _logger.exception("ee balance generation: stations for generation load failed")
        return []


def _single_energy_unit_id_by_res() -> dict[int, int]:
    """РЭС → энергорайон, только если у РЭС ровно один энергорайон."""
    from app.common.services.get_services.energy_systems.energy_unit_get_services import (
        get_energy_unit_list_full,
    )

    by_res: dict[int, set[int]] = {}
    try:
        units = list(get_energy_unit_list_full() or [])
    except Exception:
        _logger.exception("ee balance generation: energy unit list load failed")
        return {}
    for unit in units:
        res_id = getattr(unit, "id_regional_energy_system", None)
        eu_id = getattr(unit, "id", None)
        try:
            if not res_id or not eu_id or int(eu_id) <= 0:
                continue
            by_res.setdefault(int(res_id), set()).add(int(eu_id))
        except (TypeError, ValueError):
            continue
    return {res_id: next(iter(eu_ids)) for res_id, eu_ids in by_res.items() if len(eu_ids) == 1}


def _energy_unit_id_by_equipment_group(
    equipment_group_ids: set[int],
) -> dict[int, int]:
    if not equipment_group_ids:
        return {}
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
    from app.generation.models.station.station_model import Station

    try:
        rows = (
            db.session.query(EquipmentGroupSet.equipment_group_id, Station.id_energy_unit)
            .join(
                EquipmentGroupSetStation,
                EquipmentGroupSetStation.id
                == EquipmentGroupSet.equipment_group_set_station_id,
            )
            .join(Station, Station.id == EquipmentGroupSetStation.station_id)
            .filter(EquipmentGroupSet.equipment_group_id.in_(equipment_group_ids))
            .filter(Station.id_energy_unit.isnot(None))
            .all()
        )
    except Exception:
        _logger.exception("ee balance generation: equipment group energy unit lookup failed")
        return {}
    result: dict[int, int] = {}
    for eg_id, eu_id in rows:
        try:
            if eg_id and eu_id and int(eu_id) > 0:
                result[int(eg_id)] = int(eu_id)
        except (TypeError, ValueError):
            continue
    return result


def _load_tes_e_from_fuel_params(
    years: list[int],
) -> tuple[
    dict[int, dict[int, Decimal]],
    dict[int, dict[int, Decimal]],
    dict[int, dict[int, Decimal]],
    dict[int, dict[int, Decimal]],
]:
    """Суммы E (млн кВтч) по ОЭС, СЗ, РЭС и энергорайонам для плановых годов."""
    if not years:
        return {}, {}, {}, {}

    from sqlalchemy import and_, or_
    from sqlalchemy.orm import selectinload

    from app.extensions import db
    from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
        resolve_composite_parents_by_numb,
        territorial_ids_for_equipment_group,
    )
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    version_id = get_current_db_version_id()
    version_match = or_(
        and_(
            EquipmentGroupFuelParam.database_version_id == EquipmentGroup.database_version_id,
            EquipmentGroup.database_version_id.isnot(None),
        ),
        and_(
            EquipmentGroupFuelParam.database_version_id.is_(None),
            EquipmentGroup.database_version_id.is_(None),
        ),
    )
    join_cond = and_(
        EquipmentGroupFuelParam.equipment_group_id == EquipmentGroup.id,
        EquipmentGroupFuelParam.year_number.in_([int(year) for year in years]),
        version_match,
    )
    query = (
        db.session.query(EquipmentGroup, EquipmentGroupFuelParam)
        .join(EquipmentGroupFuelParam, join_cond)
        .filter(EquipmentGroupFuelParam.e.isnot(None))
    )
    if version_id is None:
        query = query.filter(EquipmentGroup.database_version_id.is_(None))
    else:
        query = query.filter(EquipmentGroup.database_version_id == version_id)
    try:
        query = query.options(
            selectinload(EquipmentGroup.regional_energy_system).selectinload(
                RegionalEnergySystem.union_energy_system
            ),
            selectinload(EquipmentGroup.territories_energy_external_mapping),
            selectinload(EquipmentGroup.regional_district).selectinload(
                RegionalDistrict.regional_energy_systems
            ),
        )
        rows = list(query.all())
    except Exception:
        _logger.exception("ee balance generation: tes fuel params query failed")
        return {}, {}, {}, {}
    if not rows:
        return {}, {}, {}, {}

    try:
        parent_by_numb = resolve_composite_parents_by_numb(
            rows, database_version_id=version_id
        )
    except Exception:
        _logger.exception("ee balance generation: composite parent resolution failed")
        parent_by_numb = {}

    district_ids: set[int] = set()
    for eg, _param in rows:
        district_id = getattr(eg, "regional_district_id", None)
        if district_id:
            district_ids.add(int(district_id))
        if parent_by_numb:
            from app.fuel.services.equipment_groups.composite_station_semantics import (
                is_composite_child_group,
            )

            if is_composite_child_group(eg) and not district_id:
                main = getattr(eg, "main", None)
                try:
                    main_int = int(main) if main is not None else None
                except (TypeError, ValueError):
                    main_int = None
                parent = parent_by_numb.get(main_int) if main_int is not None else None
                parent_district = getattr(parent, "regional_district_id", None) if parent else None
                if parent_district:
                    district_ids.add(int(parent_district))
    try:
        _res_to_ues, _district_to_ues, district_to_sa = _territory_lookups(set(), district_ids)
    except Exception:
        _logger.exception("ee balance generation: tes district territory lookups failed")
        district_to_sa = {}

    ues_by_year: dict[int, dict[int, Decimal]] = {}
    sa_by_year: dict[int, dict[int, Decimal]] = {}
    res_by_year: dict[int, dict[int, Decimal]] = {}
    eu_by_year: dict[int, dict[int, Decimal]] = {}
    single_eu_by_res = _single_energy_unit_id_by_res()
    eg_ids = {int(eg.id) for eg, _param in rows if getattr(eg, "id", None)}
    eg_to_eu = _energy_unit_id_by_equipment_group(eg_ids)
    wanted = {int(year) for year in years}
    for eg, param in rows:
        if param is None or not _fuel_param_e_participates(getattr(param, "ved", None)):
            continue
        year = getattr(param, "year_number", None)
        if year is None or int(year) not in wanted:
            continue
        amount = _decimal_or_zero(getattr(param, "e", None))
        if amount == 0 and getattr(param, "e", None) is None:
            continue
        year_int = int(year)
        try:
            _est_id, ues_id, res_id = territorial_ids_for_equipment_group(
                eg, parent_by_numb=parent_by_numb
            )
        except Exception:
            _logger.exception("ee balance generation: equipment group territorial ids failed")
            ues_id = -1
            res_id = -1
        if ues_id is not None and int(ues_id) > 0:
            ues_bucket = ues_by_year.setdefault(int(ues_id), {})
            ues_bucket[year_int] = ues_bucket.get(year_int, Decimal("0")) + amount
        if res_id is not None and int(res_id) > 0:
            res_bucket = res_by_year.setdefault(int(res_id), {})
            res_bucket[year_int] = res_bucket.get(year_int, Decimal("0")) + amount
        eu_id = None
        if res_id is not None and int(res_id) > 0:
            eu_id = single_eu_by_res.get(int(res_id))
        if eu_id is None:
            try:
                eu_id = eg_to_eu.get(int(eg.id)) if getattr(eg, "id", None) else None
            except (TypeError, ValueError):
                eu_id = None
        if eu_id:
            eu_bucket = eu_by_year.setdefault(int(eu_id), {})
            eu_bucket[year_int] = eu_bucket.get(year_int, Decimal("0")) + amount

        district_id = getattr(eg, "regional_district_id", None)
        if not district_id and parent_by_numb:
            from app.fuel.services.equipment_groups.composite_station_semantics import (
                is_composite_child_group,
            )

            if is_composite_child_group(eg):
                main = getattr(eg, "main", None)
                try:
                    main_int = int(main) if main is not None else None
                except (TypeError, ValueError):
                    main_int = None
                parent = parent_by_numb.get(main_int) if main_int is not None else None
                district_id = getattr(parent, "regional_district_id", None) if parent else None
        if district_id:
            sa_id = district_to_sa.get(int(district_id))
            if sa_id is not None:
                sa_bucket = sa_by_year.setdefault(int(sa_id), {})
                sa_bucket[year_int] = sa_bucket.get(year_int, Decimal("0")) + amount
    return ues_by_year, sa_by_year, res_by_year, eu_by_year


def load_ee_balance_generation_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
    hydro_year: Any = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """Выработка ЭЭ по типам станций для листов с прямой территорией (не ЕЭС / 1-я СЗ).

    Прогноз ГЭС/ГАЭС: средневодный год только у ОЭС СЗ, Центра, Волги, Урала и Юга;
    у остальных листов — маловодный. ``hydro_year`` оставлен для совместимости и не
    переключает сценарий.
    """
    del hydro_year
    if not years:
        return {}
    groups = generation_type_groups()
    type_to_key = _type_id_to_group_key(groups)
    if not type_to_key and not groups:
        return {}

    wanted_years = [int(year) for year in years]
    fact_current_years, plan_years = classify_ee_balance_generation_years(wanted_years)
    tes_key = _tes_generation_key(groups)
    plan_from_ee_keys = _plan_generation_keys_from_ee(groups, tes_key)
    ee_generation_years = list(fact_current_years)
    if plan_years and plan_from_ee_keys:
        ee_generation_years = sorted(set(fact_current_years) | set(plan_years))

    ues_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    sa_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    res_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    eu_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}

    if ee_generation_years and type_to_key:
        stations = _load_stations_for_generation()
        if stations:
            res_ids: set[int] = set()
            district_ids: set[int] = set()
            for station in stations:
                res_id = getattr(station, "id_regional_energy_system", None)
                district_id = getattr(station, "id_regional_district", None)
                if res_id:
                    res_ids.add(int(res_id))
                if district_id:
                    district_ids.add(int(district_id))
            try:
                res_to_ues, district_to_ues, district_to_sa = _territory_lookups(
                    res_ids, district_ids
                )
            except Exception:
                _logger.exception("ee balance generation: generation territory lookups failed")
                res_to_ues, district_to_ues, district_to_sa = {}, {}, {}
            try:
                generation_by_station = load_annual_generation_by_station(
                    [int(station.id) for station in stations if getattr(station, "id", None)],
                    min(ee_generation_years),
                    max(ee_generation_years),
                )
            except Exception:
                _logger.exception("ee balance generation: annual generation by station load failed")
                generation_by_station = {}
            try:
                generation_by_station = apply_ves_ses_plan_generation_to_station_map(
                    stations,
                    generation_by_station,
                    type_to_key,
                    years=ee_generation_years,
                )
            except Exception:
                _logger.exception("ee balance generation: ves/ses plan generation overlay failed")
                pass
            accumulated = _accumulate_station_generation_by_territory(
                stations,
                generation_by_station,
                type_to_key,
                ee_generation_years,
                res_to_ues,
                district_to_ues,
                district_to_sa,
                plan_years=set(plan_years),
                plan_group_keys=plan_from_ee_keys,
            )
            ues_by_key = accumulated[0]
            sa_by_key = accumulated[1]
            res_by_key = accumulated[2] if len(accumulated) > 2 else {}
            eu_by_key = accumulated[3] if len(accumulated) > 3 else {}

    if plan_years:
        tes_ues: dict[int, dict[int, Decimal]] = {}
        tes_sa: dict[int, dict[int, Decimal]] = {}
        tes_res: dict[int, dict[int, Decimal]] = {}
        tes_eu: dict[int, dict[int, Decimal]] = {}
        try:
            tes_loaded = _load_tes_e_from_fuel_params(plan_years)
            tes_ues = tes_loaded[0] if tes_loaded else {}
            tes_sa = tes_loaded[1] if len(tes_loaded) > 1 else {}
            tes_res = tes_loaded[2] if len(tes_loaded) > 2 else {}
            tes_eu = tes_loaded[3] if len(tes_loaded) > 3 else {}
        except Exception:
            _logger.exception("ee balance generation: tes e from fuel params load failed")
            tes_ues, tes_sa, tes_res, tes_eu = {}, {}, {}, {}
        for ues_id, year_map in tes_ues.items():
            bucket = ues_by_key.setdefault(ues_id, {}).setdefault(tes_key, {})
            for year, amount in year_map.items():
                bucket[year] = bucket.get(year, Decimal("0")) + amount
        for sa_id, year_map in tes_sa.items():
            bucket = sa_by_key.setdefault(sa_id, {}).setdefault(tes_key, {})
            for year, amount in year_map.items():
                bucket[year] = bucket.get(year, Decimal("0")) + amount
        for res_id, year_map in tes_res.items():
            bucket = res_by_key.setdefault(res_id, {}).setdefault(tes_key, {})
            for year, amount in year_map.items():
                bucket[year] = bucket.get(year, Decimal("0")) + amount
        for eu_id, year_map in tes_eu.items():
            bucket = eu_by_key.setdefault(eu_id, {}).setdefault(tes_key, {})
            for year, amount in year_map.items():
                bucket[year] = bucket.get(year, Decimal("0")) + amount

    hydro_by_year: dict[str, tuple] = {}
    for hydro_key in (HYDRO_YEAR_AVERAGE, HYDRO_YEAR_LOW):
        try:
            hydro_by_year[hydro_key] = _load_hydro_forecast_generation_by_territory(
                wanted_years, groups, hydro_key
            )
        except Exception:
            _logger.exception("ee balance generation: hydro forecast generation load failed")
            hydro_by_year[hydro_key] = ({}, {}, {}, {})

    sheet_specs = _sheet_specs(sheets)
    sheets_by_slug = {
        str(item.get("slug") or ""): item for item in (sheets or []) if item.get("slug")
    }
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    plan_filled_keys = {tes_key} | plan_from_ee_keys
    for slug, territory in sheet_specs:
        resolved = (
            territory if territory and territory.get("id") is not None else resolve_sheet_territory(slug)
        )
        if resolved is None:
            continue
        try:
            entity_id = int(resolved["id"])
        except (TypeError, ValueError, KeyError):
            continue
        kind = str(resolved.get("kind") or "")
        if kind == "ues":
            by_key = ues_by_key.get(entity_id)
        elif kind == "sa":
            by_key = sa_by_key.get(entity_id)
        elif kind == "res":
            by_key = res_by_key.get(entity_id)
        elif kind == "eu":
            by_key = eu_by_key.get(entity_id)
        else:
            continue
        sheet = sheets_by_slug.get(slug) or {"slug": slug, "territory": territory}
        sheet_hydro_year = hydro_year_for_balance_sheet(sheet, sheets) or HYDRO_YEAR_LOW
        hydro_by_key = _hydro_map_for_territory(
            hydro_by_year.get(sheet_hydro_year), kind, entity_id
        )
        sheet_inputs = _empty_sheet_inputs(groups, wanted_years)
        for group in iter_station_type_groups(groups):
            group_key = group["key"]
            year_map = (by_key or {}).get(group_key) or {}
            hydro_year_map = (hydro_by_key or {}).get(group_key) or {}
            for year in wanted_years:
                if year in fact_current_years or (
                    year in plan_years and group_key in plan_filled_keys
                ):
                    sheet_inputs[group_key][year] = _decimal_or_zero(
                        year_map.get(year)
                    ) + _decimal_or_zero(hydro_year_map.get(year))
        inputs[slug] = sheet_inputs
    return inputs
