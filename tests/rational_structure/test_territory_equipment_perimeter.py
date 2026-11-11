from decimal import Decimal

import pytest
from sqlalchemy import select

from test_territory_data import database
from test_calculation_pages import calculation_database
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.services import territory_equipment_services as services
from app.rational_structure.services.territory_input_services import build_territory_input_context
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


@pytest.fixture
def ees_reference(calculation_database):
    for model in (EnergySystemType, UnionEnergySystem, RegionalEnergySystem):
        model.__table__.create(db.engine)
    regional_district_regional_energy_system.create(db.engine)
    for index, name in enumerate(('ЕЭС России', 'ТИТЭС', 'не указано', 'Новые территории'), 1):
        db.session.execute(EnergySystemType.__table__.insert(), dict(
            id=index, name=name, database_version_id=1))
        db.session.execute(UnionEnergySystem.__table__.insert(), dict(
            id=index, name=name, id_energy_system_type=index, database_version_id=1))
        db.session.execute(RegionalEnergySystem.__table__.insert(), dict(
            id=index, name=name, name_full=name, name_rp=name,
            id_union_energy_system=index, database_version_id=1))
    db.session.execute(regional_district_regional_energy_system.insert(), [
        dict(regional_district_id=index, regional_energy_system_id=1) for index in (1, 2)])
    db.session.commit()


def test_ees_placement_prioritizes_direct_res_and_excludes_archived_and_other_versions(ees_reference):
    # Оба субъекта входят в ЕЭС, но прямая РЭС второй станции указывает на ТИТЭС.
    db.session.get(Station, 2).id_regional_energy_system = 2
    db.session.get(Machine, 1).is_archived = True
    db.session.execute(Machine.__table__.insert(), [
        dict(id=index, id_station=station, machine_number=str(index), machine_name=f'Агрегат {index}',
             external_code=f'test-{index}',
             database_version_id=version)
        for index, station, version in ((3, 1, 1), (4, 1, 2), (5, 2, 1))])
    db.session.commit()
    assert services._territory_machine_ids(1, ees_only=True) == {3}
    assert services._territory_machine_ids(1) == {2, 3, 5}
    TechnologyType.__table__.create(db.engine)
    rows, _, _, powers, _ = services.load_territory_equipment_sources(1)
    assert {row['machine_id'] for row in rows} == {2, 3, 5}
    assert all(machine != 1 for machine, _, _, _ in powers)


def test_ees_totals_match_card_powers_by_station_type_in_both_blocks(ees_reference):
    from app.rational_structure.models import TerritoryInput

    TerritoryInput.__table__.create(db.engine)
    TechnologyType.__table__.create(db.engine)
    types = ('АЭС', 'ГЭС', 'ВЭС', 'СЭС', 'ГАЭС', 'СНЭЭ')
    db.session.execute(StationType.__table__.insert(), [
        dict(id=index, name=name, database_version_id=1) for index, name in enumerate(types, 2)])
    db.session.get(Station, 2).id_regional_energy_system = 2
    db.session.scalar(select(MachinePower).where(MachinePower.id_machine == 1)).p_ust = 10
    for type_id, name in enumerate(('ТЭС', *types), 1):
        for system in (1, 2, 3, 4):
            station_id = type_id * 10 + system
            db.session.execute(Station.__table__.insert(), dict(
                id=station_id, name=f'{name} {system}', external_code=f'station-{station_id}',
                id_station_type=type_id, id_regional_district=1, id_regional_energy_system=system,
                database_version_id=1))
            db.session.execute(Machine.__table__.insert(), dict(
                id=station_id, id_station=station_id, machine_number='1', external_code=f'machine-{station_id}',
                machine_name=f'{name} агрегат', database_version_id=1))
            for year in (2024, 2025, 2031, 2042):
                db.session.add(MachinePower(id_machine=station_id, year_number=year,
                    p_ust=Decimal(type_id * 10 + year - 2024) if system == 1 else 999,
                    database_version_id=1))
    db.session.execute(EnergyZone.__table__.insert(), [
        dict(id=0, number='0', name='Не указано', database_version_id=1),
        dict(id=3, number='3', name='Зона другой версии', database_version_id=2)])
    db.session.execute(RegionalDistrict.__table__.insert(), [
        dict(id=index, name=f'Регион {index}', name_full=f'Регион {index}', name_rp=f'Региона {index}',
             name_dp=f'Региону {index}', id_energy_zone=zone, database_version_id=version)
        for index, zone, version in ((3, None, 1), (4, 3, 1), (5, 1, 2), (6, 0, 1))])
    excluded_machines = set()
    for type_id in range(1, 8):
        for region in (None, 3, 4, 5, 6):
            station_id = 1000 + type_id * 10 + (region or 0)
            excluded_machines.add(station_id)
            db.session.execute(Station.__table__.insert(), dict(
                id=station_id, name=f'Вне энергозон {station_id}', external_code=f'station-{station_id}',
                id_station_type=type_id, id_regional_district=region, id_regional_energy_system=1,
                database_version_id=1))
            db.session.execute(Machine.__table__.insert(), dict(
                id=station_id, id_station=station_id, machine_number='1', external_code=f'machine-{station_id}',
                machine_name=f'Вне энергозон {station_id}', database_version_id=1))
            for year in (2024, 2025, 2031, 2042):
                db.session.add(MachinePower(id_machine=station_id, year_number=year, p_ust=9999,
                                           database_version_id=1))
    db.session.commit()
    assert not (services._territory_machine_ids(1, ees_only=True) & excluded_machines)
    context = build_territory_input_context(1, 0, sheet='equipment')
    context['years'] = [2024, 2025, 2031, 2042]
    services.populate_territory_equipment_rows(context)
    assert context['equipment_base_year'] == 2024
    for block in (0, 3):
        rows = {row['label']: row for row in context['rows']
                if row['equipment_block'] == f'equipment_block_{block}' and row['unit'] == 'МВт'
                and row.get('equipment_rollup') in ('block', 'type', 'thermal')}
        for index, year in enumerate(context['years']):
            offset = year - 2024
            expected = {'ТЭС': 10 + offset + (10 if year == 2024 else 0),
                        'АЭС': 20 + offset, 'ГЭС': 30 + offset, 'ГАЭС': 60 + offset,
                        'ВИЭ': 90 + 2 * offset, 'СНЭЭ': 70 + offset}
            for name, value in expected.items():
                assert Decimal(rows[name]['cells'][index]) == value
            title = services.BLOCKS[block][1]
            assert Decimal(rows[title]['cells'][index]) == sum(expected.values())
    station_totals = services.load_territory_station_power_totals(1, 1, [2024])
    # В отдельной энергозоне сохраняется ее территориальный состав, включая ТИТЭС.
    assert station_totals['ВЭС'] == [40 + 3 * 999]
