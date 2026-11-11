from sqlalchemy import select

from app.extensions import db
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.rational_structure.services.territory_discount_rate_services import populate_territory_discount_rate
from app.rational_structure.services.territory_equipment_services import populate_territory_equipment_rows
from app.rational_structure.services.territory_input_services import sum_territory_rows
from app.rational_structure.services.territory_summary_services import populate_territory_summary_rows
from app.rational_structure.services.territory_transfer_services import populate_territory_transfer_rows


def territory_reference_years(version_id):
    if version_id is None:
        return [], {}
    rows = db.session.execute(select(Year.number, YearFeature.name).outerjoin(
        YearFeature, (Year.id_year_feature == YearFeature.id) & (
            (YearFeature.database_version_id == version_id) | YearFeature.database_version_id.is_(None))
    ).where(Year.database_version_id == version_id).order_by(Year.number)).all()
    return [number for number, _ in rows], {number: name for number, name in rows if name}


def prepare_territory_input_view(context, args):
    reference_years, features = territory_reference_years(context["version_id"])
    all_years = context["years"]
    choices = sorted(set(reference_years) | set(all_years))
    default_start, default_end = min(all_years), max(all_years)
    if context["sheet"] == "years":
        fact_years = [year for year in choices if features.get(year) == "факт" and year < default_start]
        if fact_years:
            default_start = max(fact_years)
    start = args.get("start_year", default_start, type=int)
    end = args.get("end_year", default_end, type=int)
    if start not in choices:
        start = default_start
    if end not in choices:
        end = default_end
    start, end = sorted((start, end))
    range_years = [year for year in choices if start <= year <= end]
    view_year = args.get("view_year", type=int)
    if view_year not in range_years:
        view_year = None
    years = [view_year] if view_year else range_years
    rounding = args.get("rounding_digits", 1, type=int)
    if rounding not in (-1, 0, 1, 2, 3, 6):
        rounding = 1
    for row in context["rows"]:
        values_by_year = dict(zip(all_years, row["cells"]))
        row["cells"] = [values_by_year.get(year, "") for year in years]
    context.update(years=years, editable_years=all_years, reference_years=choices, year_features=features,
                   start_year=start, end_year=end, range_years=range_years, view_year=view_year,
                   rounding_digits=rounding, export_equipment_check=args.get('equipment_check') == '1')
    if context.get('is_ees'):
        zone_contexts = context.pop('zone_contexts')
        for zone_context in zone_contexts:
            for row in zone_context['rows']:
                by_year = dict(zip(zone_context['years'], row['cells']))
                row['cells'] = [by_year.get(year, '') for year in years]
            zone_context['years'] = years
            populate_territory_transfer_rows(zone_context)
        context['rows'] = sum_territory_rows(zone_contexts, years)
        context['transfer_source_empty'] = bool(zone_contexts) and all(
            zone.get('transfer_source_empty', False) for zone in zone_contexts)
    else:
        populate_territory_transfer_rows(context)
    populate_territory_equipment_rows(context)
    populate_territory_summary_rows(context)
    populate_territory_discount_rate(context)
    return context
