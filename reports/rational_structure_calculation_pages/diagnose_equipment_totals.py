"""Read-only comparison of territory equipment and generation totals."""
import json
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from app import create_app
from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id
from app.generation.services.station_services.station_services import get_filtered_station_ids
from app.generation.services.station_services.aggregation_station_services.aggregation_rows import get_full_aggregation_rows
from app.rational_structure.services.territory_input_services import build_territory_input_context
from app.rational_structure.services.territory_input_page_services import prepare_territory_input_view
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.models.station.station_model import Station


def compare():
    app = create_app()
    with app.test_request_context('/'):
        version = get_current_db_version_id()
        print('VERSION', version)
        types = dict(db.session.execute(select(StationType.id, StationType.name)).all())
        systems = dict(db.session.execute(select(EnergySystemType.id, EnergySystemType.name)).all())
        ids = get_filtered_station_ids({})
        zone_station_ids = set(db.session.scalars(select(Station.id).join(
            RegionalDistrict, RegionalDistrict.id == Station.id_regional_district).join(
                EnergyZone, EnergyZone.id == RegionalDistrict.id_energy_zone).where(
                    Station.database_version_id == version, RegionalDistrict.database_version_id == version,
                    EnergyZone.database_version_id == version, EnergyZone.id > 0)))
        excluded_stations = list(db.session.execute(select(Station.id, Station.name).where(
            Station.id.in_(set(ids) - zone_station_ids))).all())
        ids = sorted(set(ids) & zone_station_ids)
        print(f'Stations in energy zones: {len(ids)}; excluded outside zones: {len(excluded_stations)}')
        rows = get_full_aggregation_rows.__wrapped__(2024, 2042, ids, {})
        totals = defaultdict(lambda: defaultdict(Decimal))
        for row in rows:
            totals[systems.get(row.energy_system_type_id), types.get(row.station_type_id)][row.year] += row.p_ust or Decimal(0)
        context = prepare_territory_input_view(build_territory_input_context(version, 0, sheet='equipment'),
                    MultiDict({'start_year': '2024', 'end_year': '2042', 'rounding_digits': '1'}))
        actual = [dict(label=row['label'], block=row['equipment_block'], cells=row['cells'])
                  for row in context['rows'] if row['unit'] == 'МВт' and (
                      row.get('equipment_rollup') in ('block', 'type', 'thermal')
                      or row['label'] in ('ВЭС', 'СЭС'))]
        checks = []
        labels = {'АЭС': ['АЭС'], 'ТЭС': ['ТЭС'], 'ГЭС': ['ГЭС'], 'ГАЭС': ['ГАЭС'],
                  'ВЭС': ['ВЭС'], 'СЭС': ['СЭС'], 'ВИЭ': ['ВЭС', 'СЭС'], 'СНЭЭ': ['СНЭЭ']}
        for row in actual:
            if row['block'] not in ('equipment_block_0', 'equipment_block_3'):
                continue
            kinds = labels.get(row['label'])
            if row['label'].startswith('Всего'):
                kinds = ['АЭС', 'ТЭС', 'ГЭС', 'ГАЭС', 'ВЭС', 'СЭС', 'СНЭЭ']
            if kinds is None:
                continue
            for year, value in zip(context['years'], row['cells']):
                source_year = (context['equipment_sipr_end_year'] if row['block'] == 'equipment_block_0'
                               and context['equipment_sipr_end_year'] is not None
                               and year > context['equipment_sipr_end_year']
                               and context['year_features'].get(year) == 'план' else year)
                expected = sum((totals['ЕЭС России', kind][source_year] for kind in kinds), Decimal(0))
                difference = Decimal(value or 0) - expected
                checks.append(dict(block=row['block'], label=row['label'], year=year,
                                   source_year=source_year, actual=value or '0', expected=expected,
                                   difference=difference))
        mismatches = [check for check in checks if check['difference'] != 0]
        report = dict(version=version, years=context['years'], base_year=context['equipment_base_year'],
                      sipr_end_year=context['equipment_sipr_end_year'],
                      total_source_years=context['equipment_total_source_years'],
                      reference_scope='ЕЭС России, только станции в энергозонах выбранной версии',
                      excluded_outside_zones=[dict(id=station_id, name=name) for station_id, name in excluded_stations],
                      generation={str(key): values for key, values in totals.items()}, territory=actual,
                      checks=checks, mismatches=mismatches)
        print(f'Checked {len(checks)} totals and station-type cells; mismatches: {len(mismatches)}')
        assert not mismatches, mismatches
        from pathlib import Path
        Path('reports/rational_structure_calculation_pages/equipment_totals_comparison.json').write_text(
            json.dumps(report, ensure_ascii=False, default=str, indent=2), encoding='utf-8')


if __name__ == '__main__':
    compare()
