from decimal import Decimal

from sqlalchemy import select

from app.common.perimeter_variant.constants import EES_UNIFIED_REF_NAME
from app.extensions import db
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.common.services.database_version_services import get_current_version
from app.common.services.help_services import parse_decimal_from_display
from app.energy_consumption.pages.summary_ez_page_services import build_summary_ez_page_context
from app.energy_consumption.services.energy_consumption_summary_services import (
    _gaes_charge_cache_generation,
    _gaes_charge_raw_station_values_for_entity,
)
from app.power_demand.services.demand_summary_services import build_energy_zones_summary_context


CONSUMPTION_MODEL = "EnergyZoneEnergyConsumptionParameter"
DEMAND_MODEL = "EnergyZoneDemandParameter"


def _source_row(context, model, zone_id, parameter, *, without_gaes=False, without_nt=False):
    rows = [row for row in context["summary_rows"]
            if row.get("demand_model_name") == model and row.get("parent_id") == zone_id
            and row.get("parameter_key") == parameter
            and (not without_nt or not (row.get("perimeter_variant_code") or "").startswith("with_nt"))
            and ("without_gaes" in (row.get("perimeter_variant_code") or "")) == without_gaes]
    # Как в исходных сводках по умолчанию: без НТ, основной периметр.
    rows.sort(key=lambda row: (
        (row.get("perimeter_variant_code") or "").startswith("with_nt"),
        bool(row.get("perimeter_variant_code")),
    ))
    return rows[0] if rows else None


def _series(context, row, years):
    if row is None:
        return [None] * len(years)
    values = row["year_values"]
    tooltips = row.get("year_numeric_tooltips", [])
    by_year = {}
    for index, year in enumerate(context["years"]):
        raw = tooltips[index] if index < len(tooltips) and tooltips[index] else values[index]
        by_year[year] = parse_decimal_from_display(str(raw))
    return [by_year.get(year) for year in years]


def load_territory_summary_values(version_id, zone_id, years):
    if version_id != get_current_version():
        raise ValueError("Версия исходных сводок не совпадает с выбранной версией БД.")
    is_ees = zone_id is None
    consumption_model, demand_model = CONSUMPTION_MODEL, DEMAND_MODEL
    parent_id = zone_id
    if is_ees:
        consumption_model = "EnergySystemTypeEnergyConsumptionParameter"
        demand_model = "EnergySystemTypeDemandParameter"
        parent_id = db.session.scalar(select(EnergySystemType.id).where(
            EnergySystemType.database_version_id == version_id,
            EnergySystemType.name == EES_UNIFIED_REF_NAME,
        ))
        if parent_id is None:
            return dict(has_gaes=True, **{key: [None] * len(years) for key in (
                "consumption", "consumption_with_gaes", "max_power", "combined", "hours")})
    common = dict(start_year=min(years), end_year=max(years),
                  data_start_year=min(years), data_end_year=max(years),
                  filter_year_list=years, ez_territory_ordered=([] if is_ees else [zone_id], []))
    consumption = build_summary_ez_page_context(
        0, **common, coeff_base_year=min(years) - 1,
        include_medium_years=True, can_edit_summary_cells=False,
    )
    demand = build_energy_zones_summary_context(
        0, **common, ez_max_extended_parameters=True,
        data_segments=frozenset({"core", "chi"}),
    )
    stations = () if is_ees else _gaes_charge_raw_station_values_for_entity(
        version_id, CONSUMPTION_MODEL, "id_energy_zone", zone_id, tuple(years),
        _gaes_charge_cache_generation(),
    )
    with_gaes = _series(consumption, _source_row(
        consumption, consumption_model, parent_id, "energy_consumption_mln_kvt_ch", without_nt=is_ees), years)
    without_row = _source_row(consumption, consumption_model, parent_id,
                              "energy_consumption_mln_kvt_ch", without_gaes=True, without_nt=is_ees)
    if without_row is not None or is_ees:
        without_gaes = _series(consumption, without_row, years)
    elif stations:
        charge = {}
        for _, _, station_values in stations:
            for year, value in station_values:
                charge[year] = charge.get(year, Decimal(0)) + Decimal(str(value))
        without_gaes = [value - charge[year] if value is not None and year in charge else None
                        for year, value in zip(years, with_gaes)]
    else:
        without_gaes = with_gaes
    result = {"has_gaes": is_ees or bool(stations), "consumption": without_gaes,
              "consumption_with_gaes": with_gaes}
    for name, parameter in (("max_power", "max_power"), ("combined", "combined_on_ees"),
                            ("hours", "peak_max_power_usage_hours")):
        result[name] = _series(demand, _source_row(
            demand, demand_model, parent_id, parameter, without_nt=is_ees), years)
    return result


def populate_territory_summary_rows(context):
    is_ees = context.get("is_ees", False)
    if (context["sheet"] != "years" or not context["years"]
            or (context["selected_zone"] is None and not is_ees) or context["version_id"] is None
            or not context["rows"]):
        return
    zone_id = None if is_ees else context["selected_zone"].id
    data = load_territory_summary_values(context["version_id"], zone_id, context["years"])
    mean = [value / Decimal(8760) * Decimal(1000) if value is not None else None
            for value in data["consumption"]]
    ratio = [combined / average if combined is not None and average not in (None, 0) else None
             for combined, average in zip(data["combined"], mean)]
    series = {"0": data["consumption"], "1": data["max_power"], "2": data["combined"],
              "3": data["hours"], "4": mean, "5": ratio}
    labels = {"1": "Максимальное потребление мощности",
              "2": "Совмещенное потребление мощности на час прохождения максимума ЕЭС"}
    formulas = {
        "4": "Среднегодовое потребление мощности, МВт = Годовое потребление электрической энергии без ГАЭС, млн кВт·ч / 8760 × 1000. Используется 8760 часов для каждого года.",
        "5": "Соотношение п. 2а к Рсреднегодовой = Совмещенное потребление мощности на час прохождения максимума ЕЭС, МВт / Среднегодовое потребление мощности, МВт. При нулевом знаменателе результат отсутствует.",
    }
    rows = []
    for original in context["rows"]:
        row = dict(original)
        key = row["key"]
        if key in series:
            row.update(cells=[str(value) if value is not None else "" for value in series[key]],
                       readonly=True, formula=formulas.get(key, ""))
            if key in labels:
                row["label"] = labels[key]
        if key == "0" and data["has_gaes"]:
            row.update(number="1.1", label="Годовое потребление электрической энергии без ГАЭС")
            rows.append(row)
            rows.append(dict(row, key="0_with_gaes", number="1.2", virtual=True,
                             label="Годовое потребление электрической энергии с ГАЭС",
                             cells=[str(value) if value is not None else "" for value in data["consumption_with_gaes"]]))
        else:
            rows.append(row)
    context["rows"] = rows
