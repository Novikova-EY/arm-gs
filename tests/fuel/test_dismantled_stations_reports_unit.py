"""Демонтированные станции не участвуют в отчетных витринах и экспорте."""

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401 – связи модели Year
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import EquipmentGroupSpecificFuelCost
from app.fuel.models.fue_equipment_group_natural_fuel_model import EquipmentGroupNaturalFuel
from app.fuel.models.external_mapping.fue_em_territories_energy_model import TerritoriesEnergyExternalMapping
from app.fuel.models.external_mapping.fue_em_gen_company_model import GenCompanyExternalMapping
from app.fuel.services.equipment_groups import equipment_group_fuel_params_services as params
from app.fuel.services.equipment_groups import equipment_group_specific_fuel_cost_services as costs
from app.fuel.services.equipment_groups import equipment_group_natural_fuel_services as natural
from app.fuel.services.fuel_exports.export_stations_equipment_group_fuel_params_services import (
    export_stations_equipment_group_fuel_params_to_excel,
)
from app.fuel.services.fuel_exports.export_stations_equipment_group_specific_fuel_cost_services import (
    export_stations_equipment_group_specific_fuel_cost_to_excel,
)


from app.fuel.services.fuel_exports.export_stations_equipment_group_natural_fuel_services import (
    export_stations_equipment_group_natural_fuel_to_excel,
)


REPORTS = [
    (params.get_equipment_groups_with_fuel_params_data,
     params.build_equipment_group_fuel_params_hierarchy,
     export_stations_equipment_group_fuel_params_to_excel),
    (costs.get_equipment_groups_with_specific_fuel_cost_data,
     costs.build_equipment_group_specific_fuel_cost_hierarchy,
     export_stations_equipment_group_specific_fuel_cost_to_excel),
    (natural.get_equipment_groups_with_natural_fuel_data,
     natural.build_equipment_group_natural_fuel_hierarchy,
     export_stations_equipment_group_natural_fuel_to_excel),
]


@pytest.fixture
def report_session(monkeypatch):
    models = (EquipmentGroup, EquipmentGroupFuelParam, EquipmentGroupSpecificFuelCost,
              EquipmentGroupNaturalFuel,
              TerritoriesEnergyExternalMapping, GenCompanyExternalMapping)
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {model.__table__.schema: None for model in models},
    })
    for model in models:
        model.__table__.create(engine)
    sessions = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", sessions)
    for service in (params, costs, natural):
        monkeypatch.setattr(service, "get_current_db_version_id", lambda: 20)
    monkeypatch.setattr(params, "_get_equipment_group_station_mapping_with_display_order",
                        lambda *a, **k: {})
    monkeypatch.setattr(
        "app.fuel.services.stations.stations_equipment_groups_services."
        "get_standalone_equipment_group_ids", lambda **k: set(),
    )
    for module, func in [
        ("energy_system_type", "get_energy_system_type_map"),
        ("regional_energy_system", "get_regional_energy_systems_name_map"),
        ("union_energy_system", "get_union_energy_systems_map"),
        ("union_energy_system", "get_union_energy_system_display_order_map"),
    ]:
        monkeypatch.setattr(
            f"app.common.services.get_services.energy_systems.{module}_get_services.{func}",
            lambda: {},
        )
    with sessions() as session:
        yield session
    sessions.remove()
    engine.dispose()


def add_group(session, gid, d, version=20, **values):
    session.execute(EquipmentGroup.__table__.insert().values(
        id=gid, external_code=f"eg-{gid}", numb=100 + gid,
        name=f"Станция {gid}", d=d, database_version_id=version, **values,
    ))


def add_year_data(session, gid, year=2024, version=20):
    for model in (EquipmentGroupFuelParam, EquipmentGroupSpecificFuelCost, EquipmentGroupNaturalFuel):
        session.execute(model.__table__.insert().values(
            equipment_group_id=gid, numb1120=100 + gid,
            year_number=year, database_version_id=version, gaz=gid,
        ))


@pytest.mark.parametrize("read,build,export", REPORTS)
@pytest.mark.parametrize("version", [20, None])
def test_reports_hide_dismantled_with_or_without_year_data(
    report_session, monkeypatch, read, build, export, version,
):
    for service in (params, costs, natural):
        monkeypatch.setattr(service, "get_current_db_version_id", lambda: version)
    for gid, d in [(1, 1), (2, None), (3, 0), (4, 9), (5, 9), (6, 1)]:
        add_group(report_session, gid, d, version=version)
    for gid in (1, 2, 3, 4):
        add_year_data(report_session, gid, version=version)
    add_year_data(report_session, 5, year=2023, version=version)

    data = read(start_year=2024, end_year=2024, per_page=1)

    assert {eg.id for eg, _ in data["rows"]} == {1, 2, 3, 6}
    assert data["total_count"] == 4
    assert set(data["numb1120_filter_choices"]) == {101, 102, 103, 106}
    assert next(param for eg, param in data["rows"] if eg.id == 6) is None
    # Только отображение: ни справочник, ни загруженные показатели не удаляются.
    assert report_session.query(EquipmentGroup).count() == 6
    assert report_session.query(EquipmentGroupFuelParam).count() == 5
    assert report_session.query(EquipmentGroupSpecificFuelCost).count() == 5
    assert report_session.query(EquipmentGroupNaturalFuel).count() == 5


@pytest.mark.parametrize("read,build,export", REPORTS)
def test_code_filter_cannot_show_dismantled_station(report_session, read, build, export):
    add_group(report_session, 1, 9)
    add_year_data(report_session, 1)
    data = read(filters={"numb1120_filter": [101]}, start_year=2024, end_year=2024)
    assert data["rows"] == []
    assert data["total_count"] == 0
    assert export({"numb1120_filter": [101]}, 2024, 2024) is None


@pytest.mark.parametrize("read,version", [
    (params.get_equipment_groups_with_fuel_params_data, None),
    (natural.get_equipment_groups_with_natural_fuel_data, 20),
])
def test_explicit_id_cannot_show_dismantled_station(report_session, read, version):
    add_group(report_session, 1, 9, version=version)
    data = read(
        filters={"equipment_group_ids": [1]}, start_year=2024, end_year=2024,
    )
    assert data["rows"] == []


@pytest.mark.parametrize("read,build,export", REPORTS)
def test_hierarchy_totals_and_excel_exclude_dismantled_station(
    report_session, read, build, export,
):
    add_group(report_session, 1, 1)
    add_group(report_session, 2, 9)
    add_year_data(report_session, 1)
    add_year_data(report_session, 2)
    data = read(start_year=2024, end_year=2024)
    hierarchy = build(data["rows"])
    res = hierarchy[0]["ues_list"][0]["res_list"][0]
    assert {gb["equipment_group"].id for gb in res["group_blocks"]} == {1}
    assert res["res_summary"]["gaz"] == 1
    workbook = load_workbook(export({}, 2024, 2024))
    names = [str(row[1]).replace("\xa0", " ")
             for row in workbook.active.iter_rows(values_only=True)]
    assert "Станция 1" in names
    assert "Станция 2" not in names


@pytest.mark.parametrize("read,build,export", REPORTS)
def test_dismantled_composite_parent_is_not_recreated_as_total(
    report_session, read, build, export,
):
    add_group(report_session, 1, 9, comp=1)
    for gid in (2, 3):
        add_group(report_session, gid, 1, main=101, niv=1)
        add_year_data(report_session, gid)
    data = read(start_year=2024, end_year=2024)
    hierarchy = build(data["rows"])
    blocks = hierarchy[0]["ues_list"][0]["res_list"][0]["group_blocks"]
    assert {gb["equipment_group"].id for gb in blocks} == {2, 3}
    workbook = load_workbook(export({}, 2024, 2024))
    names = [str(row[1]).replace("\xa0", " ")
             for row in workbook.active.iter_rows(values_only=True)]
    assert "Станция 1, всего" not in names
    assert "Станция 2" in names
    assert "Станция 3" in names
