"""Покрытие топливной сводки действующими и планируемыми группами."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.electrical_intensity.models  # noqa: F401 – связи модели Year
from app.ecology.services import operating_tes_fuel_input_services as service
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.ecology.services import fuel_summary_services as summary
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem


@pytest.fixture
def fuel_session(monkeypatch):
    models = (
        EquipmentGroup,
        EquipmentGroupFuelParam,
        EquipmentGroupExtraFuelParam,
        Machine,
        MachinePower,
        MachineFuelParam,
        RegionalEnergySystem,
        UnionEnergySystem,
        service.EquipmentGroupSet,
        service.EquipmentGroupSetStation,
        service.Station,
        service.EnergyUnit,
        service.UnionEnergySystemExternalMapping,
        service.TerritoriesEnergyExternalMapping,
    )
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {model.__table__.schema: None for model in models}
        },
    )
    for model in models:
        model.__table__.create(engine)
    service.regional_district_regional_energy_system.create(engine)
    with Session(engine) as session:
        monkeypatch.setattr(service.db, "session", session)
        monkeypatch.setattr(service, "get_current_db_version_id", lambda: 1)
        session.execute(
            UnionEnergySystem.__table__.insert(),
            [{"id": 1, "name": "ОЭС Центра"}, {"id": 2, "name": "ТИТЭС"}],
        )
        session.execute(
            RegionalEnergySystem.__table__.insert(),
            [
                {"id": 1, "name": "Центр", "name_full": "Центр", "name_rp": "Центра", "id_union_energy_system": 1},
                {"id": 2, "name": "Норильский район", "name_full": "Норильский район", "name_rp": "Норильского района", "id_union_energy_system": 2},
            ],
        )
        session.execute(
            EquipmentGroup.__table__.insert(),
            [
                {"id": 1, "external_code": "test-1", "d": 1, "database_version_id": 1, "regional_energy_system_id": None},
                {"id": 2, "external_code": "test-2", "d": 0, "database_version_id": 1, "regional_energy_system_id": 1},
                {"id": 3, "external_code": "test-3", "d": None, "database_version_id": 1, "regional_energy_system_id": 2},
                {"id": 4, "external_code": "test-4", "d": 2, "database_version_id": 1, "regional_energy_system_id": None},
            ],
        )
        # Ни одна группа не имеет связи со станцией: это не должно терять её
        # из итогов, в том числе для котельных и неизвестной территории.
        for year in (2023, 2024):
            session.execute(
                EquipmentGroupFuelParam.__table__.insert(),
                [
                    {
                        "equipment_group_id": group_id,
                        "database_version_id": 1,
                        "year_number": year,
                        "ved": ved,
                        "nust": capacity,
                        "q": group_id * 10,
                        "e": group_id * 100,
                        "b": group_id,
                    }
                    for group_id, ved, capacity in (
                        (1, 2, 150), (2, 3, 100), (3, 99, None), (4, 1, Decimal("100.1"))
                    )
                ],
            )
        yield session
    engine.dispose()


def _insert_group(session, *, d=1, version=1, param_version=1, ved=2, year=2023):
    session.execute(
        EquipmentGroup.__table__.insert(),
        {"id": 99, "external_code": "test-99", "d": d, "database_version_id": version},
    )
    session.execute(
        EquipmentGroupFuelParam.__table__.insert(),
        {
            "equipment_group_id": 99,
            "year_number": year,
            "database_version_id": param_version,
            "ved": ved,
            "q": 999,
        },
    )


def test_operating_and_planned_cover_russia_without_station_links(fuel_session):
    operating = service.load_operating_tes_fuel_inputs([2023, 2024])
    planned = service.load_operating_tes_fuel_inputs([2023, 2024], operating=False)

    for year in (2023, 2024):
        assert operating[year]["vsego"]["q"] == Decimal("10")
        assert planned[year]["vsego"]["q"] == Decimal("90")
        for field, total in (("q", 100), ("e", 1000), ("b", 10)):
            assert operating[year]["vsego"][field] + planned[year]["vsego"][field] == total
        assert planned[year]["centr"]["q"] == Decimal("20")
        assert planned[year]["norilsk"]["q"] == Decimal("30")


def test_planned_capacity_classes_do_not_lose_or_duplicate_groups(fuel_session):
    planned = service.load_operating_tes_fuel_inputs(
        [2023], operating=False, by_capacity=True
    )
    classes = planned[2023]["vsego"]

    assert classes["le100"]["q"] == Decimal("50")
    assert classes["gt100"]["q"] == Decimal("40")
    assert service.combine_capacity_buckets(classes)["q"] == Decimal("90")


@pytest.mark.parametrize("ved", [None, 0, -1])
@pytest.mark.parametrize("d", [0, 1])
def test_nonparticipating_rows_are_excluded(fuel_session, ved, d):
    _insert_group(fuel_session, ved=ved, d=d)

    inputs = service.load_operating_tes_fuel_inputs([2023], operating=d == 1)

    assert inputs[2023]["vsego"]["q"] == (10 if d == 1 else 90)


@pytest.mark.parametrize("version,param_version", [(1, None), (1, 2), (2, 2), (None, None)])
def test_other_and_unversioned_data_do_not_leak_into_current_version(
    fuel_session, version, param_version
):
    _insert_group(fuel_session, version=version, param_version=param_version)

    inputs = service.load_operating_tes_fuel_inputs([2023])

    assert inputs[2023]["vsego"]["q"] == Decimal("10")


def test_no_selected_version_uses_only_matching_legacy_data(fuel_session, monkeypatch):
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: None)
    _insert_group(fuel_session, version=None, param_version=None)

    inputs = service.load_operating_tes_fuel_inputs([2023])

    assert inputs[2023]["vsego"]["q"] == Decimal("999")
    assert service.load_operating_tes_fuel_inputs([2023], operating=False)[2023] == {}


def test_extra_fuel_from_another_version_does_not_affect_inputs(fuel_session):
    fuel_session.execute(
        EquipmentGroupExtraFuelParam.__table__.insert(),
        [
            {"equipment_group_id": 1, "year_number": 2023, "database_version_id": 2, "gaz_prir": 999},
            {"equipment_group_id": 2, "year_number": 2023, "database_version_id": 1, "gaz_prir": 12},
        ],
    )

    operating = service.load_operating_tes_fuel_inputs([2023])
    planned = service.load_operating_tes_fuel_inputs([2023], operating=False)

    assert operating[2023]["vsego"]["q"] == Decimal("10")
    assert operating[2023]["vsego"]["gaz_prir"] == 0
    assert planned[2023]["vsego"]["gaz_prir"] == Decimal("12")


@pytest.mark.parametrize("name,slug", [
    ("ТИТЭС Востока", "isolated-dv"),
    ("ТИТЭС Сибири", "norilsk"),
])
def test_tites_reference_names_are_special_not_oes(fuel_session, name, slug):
    fuel_session.execute(
        UnionEnergySystem.__table__.update().where(UnionEnergySystem.id == 1).values(name=name)
    )
    fuel_session.execute(
        EquipmentGroup.__table__.update().where(EquipmentGroup.id == 1)
        .values(regional_energy_system_id=1)
    )
    inputs = service.load_operating_tes_fuel_inputs([2023])[2023]
    assert inputs[slug]["q"] == 10
    assert "vostok" not in inputs
    assert "sibir" not in inputs


@pytest.mark.parametrize("code,name,slug", [
    ("9", "Из.узлы Дальнего Востока", "isolated-dv"),
    ("10", "Норильск.эн.р-н", "norilsk"),
])
@pytest.mark.parametrize("by_capacity", [False, True])
@pytest.mark.parametrize("d", [0, 1])
def test_external_energy_district_code_works_without_station(
    fuel_session, by_capacity, d, code, name, slug,
):
    # Энергорайон задан кодом Топлива, РЭС и станция отсутствуют.
    _insert_group(fuel_session, d=d, year=2025)
    fuel_session.execute(
        service.UnionEnergySystemExternalMapping.__table__.insert(),
        {"external_id": code, "external_nameoes": name},
    )
    fuel_session.execute(
        EquipmentGroup.__table__.update().where(EquipmentGroup.id == 99).values(oes=int(code))
    )
    inputs = service.load_operating_tes_fuel_inputs(
        [2025], operating=d == 1, by_capacity=by_capacity,
    )[2025]
    bucket = inputs[slug]
    if by_capacity:
        bucket = service.combine_capacity_buckets(bucket)
    assert bucket["q"] == 999


def _link_station(session, *, station_id=1, res_id=None, unit_id=None, subject_id=None, version=1):
    session.execute(service.Station.__table__.insert(), {
        "id": station_id, "name": f"Станция {station_id}", "external_code": f"station-{station_id}",
        "database_version_id": version, "id_regional_energy_system": res_id,
        "id_energy_unit": unit_id, "id_regional_district": subject_id,
    })
    session.execute(service.EquipmentGroupSetStation.__table__.insert(), {
        "id": station_id, "station_id": station_id, "database_version_id": version,
    })
    session.execute(service.EquipmentGroupSet.__table__.insert(), {
        "equipment_group_id": 99, "equipment_group_set_station_id": station_id,
    })


@pytest.mark.parametrize("by_capacity", [False, True])
def test_station_energy_district_does_not_multiply_fuel_totals(fuel_session, by_capacity):
    _insert_group(fuel_session)
    fuel_session.execute(service.EnergyUnit.__table__.insert(), {
        "id": 1, "name": "Норильский энергорайон",
        "name_rp": "Норильского энергорайона", "name_dp": "Норильском энергорайоне",
        "id_regional_district": 1, "id_regional_energy_system": 1, "database_version_id": 1,
    })
    # Несколько станций/типов ГО одной территории не должны умножать расход.
    _link_station(fuel_session, station_id=1, unit_id=1)
    _link_station(fuel_session, station_id=2, unit_id=1)
    fuel_session.execute(EquipmentGroupExtraFuelParam.__table__.insert(), {
        "equipment_group_id": 99, "year_number": 2023,
        "database_version_id": 1, "gaz_prir": 15,
    })
    inputs = service.load_operating_tes_fuel_inputs([2023], by_capacity=by_capacity)[2023]
    if by_capacity:
        inputs = {slug: service.combine_capacity_buckets(bucket) for slug, bucket in inputs.items()}
    assert inputs["norilsk"]["q"] == 999
    assert inputs["norilsk"]["gaz_prir"] == 15
    assert inputs["vsego"]["q"] == 1009
    assert "centr" not in inputs


@pytest.mark.parametrize("group_unit_id", [None, 1, 2])
@pytest.mark.parametrize("station_unit_id", [None, 1, 2])
@pytest.mark.parametrize("by_capacity", [False, True])
def test_nikolaevsky_column_uses_only_equipment_group_energy_unit(
    fuel_session, group_unit_id, station_unit_id, by_capacity,
):
    _insert_group(fuel_session)
    fuel_session.execute(service.EnergyUnit.__table__.insert(), [
        {
            "id": unit_id, "name": name, "name_rp": name, "name_dp": name,
            "id_regional_district": 1, "id_regional_energy_system": 1,
            "database_version_id": 1,
        }
        for unit_id, name in (
            (1, "Николаевский энергорайон"), (2, "Другой энергорайон"),
        )
    ])
    fuel_session.execute(EquipmentGroup.__table__.update().where(
        EquipmentGroup.id == 99,
    ).values(energy_unit_id=group_unit_id, regional_energy_system_id=1, oes=12, r=1))
    fuel_session.execute(service.UnionEnergySystemExternalMapping.__table__.insert(), {
        "external_id": "12", "external_nameoes": "Николаевский э.р.",
    })
    fuel_session.execute(EquipmentGroupFuelParam.__table__.update().where(
        EquipmentGroupFuelParam.equipment_group_id == 99,
    ).values(nust=150))
    fuel_session.execute(EquipmentGroupExtraFuelParam.__table__.insert(), {
        "equipment_group_id": 99, "year_number": 2023,
        "database_version_id": 1, "gaz_prir": 15,
    })
    if station_unit_id is not None:
        _link_station(fuel_session, station_id=1, unit_id=station_unit_id)
        _link_station(fuel_session, station_id=2, unit_id=station_unit_id)

    inputs = service.load_operating_tes_fuel_inputs([2023], by_capacity=by_capacity)[2023]
    if by_capacity:
        inputs = {slug: service.combine_capacity_buckets(bucket) for slug, bucket in inputs.items()}
    # Та же территориальная принадлежность должна попасть в пакет для экологии.
    summary_inputs = summary.load_fuel_summary([2023])[2023]
    for buckets, total in ((inputs, 1009), (summary_inputs, 999)):
        assert buckets["vsego"]["q"] == total
        if group_unit_id == 1:
            assert buckets["nikolaevsky"]["q"] == 999
            assert buckets["nikolaevsky"]["gaz_prir"] == 15
            assert "centr" not in buckets
        else:
            assert "nikolaevsky" not in buckets
            assert buckets["centr"]["q"] == 999


@pytest.mark.parametrize("station_version,group_res,expected", [
    (1, None, "centr"),
    (1, 2, "norilsk"),
    (2, None, None),
])
def test_station_res_fallback_preserves_group_priority_and_version(
    fuel_session, station_version, group_res, expected,
):
    _insert_group(fuel_session)
    if group_res:
        fuel_session.execute(
            EquipmentGroup.__table__.update().where(EquipmentGroup.id == 99)
            .values(regional_energy_system_id=group_res)
        )
    _link_station(fuel_session, res_id=1, version=station_version)
    inputs = service.load_operating_tes_fuel_inputs([2023])[2023]
    assert inputs["vsego"]["q"] == 1009
    if expected:
        assert inputs[expected]["q"] == 999
    else:
        assert "centr" not in inputs


@pytest.mark.parametrize("ambiguous", [False, True])
def test_subject_res_fallback_requires_unambiguous_membership(fuel_session, ambiguous):
    _insert_group(fuel_session)
    fuel_session.execute(
        EquipmentGroup.__table__.update().where(EquipmentGroup.id == 99)
        .values(regional_district_id=10)
    )
    memberships = [{"regional_district_id": 10, "regional_energy_system_id": 1}]
    if ambiguous:
        memberships.append({"regional_district_id": 10, "regional_energy_system_id": 2})
    fuel_session.execute(service.regional_district_regional_energy_system.insert(), memberships)
    inputs = service.load_operating_tes_fuel_inputs([2023])[2023]
    assert inputs["vsego"]["q"] == 1009
    if ambiguous:
        assert "centr" not in inputs
        assert "norilsk" not in inputs
    else:
        assert inputs["centr"]["q"] == 999


def test_unspecified_res_does_not_inherit_whole_subject_membership(fuel_session):
    _insert_group(fuel_session)
    fuel_session.execute(RegionalEnergySystem.__table__.update().where(
        RegionalEnergySystem.id == 1
    ).values(name="не указано"))
    fuel_session.execute(EquipmentGroup.__table__.update().where(
        EquipmentGroup.id == 99
    ).values(regional_energy_system_id=1, regional_district_id=10))
    fuel_session.execute(service.regional_district_regional_energy_system.insert(), {
        "regional_district_id": 10, "regional_energy_system_id": 2,
    })
    inputs = service.load_operating_tes_fuel_inputs([2023])[2023]
    assert "norilsk" not in inputs
    assert "nikolaevsky" not in inputs



def _summary_machine(session, machine_id, group_id, power, *, expected=2023, version=1):
    session.execute(Machine.__table__.insert(), {
        "id": machine_id, "external_code": f"summary-{machine_id}",
        "machine_number": str(machine_id), "machine_name": f"Агрегат {machine_id}",
        "database_version_id": version, "date_exploitation_expected": expected,
        "is_archived": False,
    })
    session.execute(MachineFuelParam.__table__.insert(), {
        "machine_id": machine_id, "equipment_group_id": group_id, "database_version_id": version,
    })
    for year in (2023, 2024):
        session.execute(MachinePower.__table__.insert(), {
            "id_machine": machine_id, "year_number": year, "p_ust": power, "database_version_id": version,
        })


@pytest.mark.parametrize("d", [None, 0, 1, 2, 9])
@pytest.mark.parametrize("r", [None, 0, 1, 2, 9])
@pytest.mark.parametrize("capacity", [None, 0, Decimal("99.9"), 100, Decimal("100.1")])
def test_summary_selects_groups_by_flags_and_yearly_nust(fuel_session, d, r, capacity):
    fuel_session.execute(EquipmentGroup.__table__.update().values(d=9))
    _insert_group(fuel_session, d=d)
    fuel_session.execute(EquipmentGroup.__table__.update().where(
        EquipmentGroup.id == 99,
    ).values(r=r))
    fuel_session.execute(EquipmentGroupFuelParam.__table__.update().where(
        EquipmentGroupFuelParam.equipment_group_id == 99,
    ).values(nust=capacity))

    inputs, errors = summary.build_fuel_summary([2023])

    expected_scope = None
    if (d, r) == (1, 1) and capacity is not None:
        expected_scope = "operating"
    elif (d, r) in ((1, 2), (None, None)) and capacity is not None:
        expected_scope = "new_lt100" if capacity < 100 else "new_ge100"
    assert not any(errors.values())
    for scope in inputs:
        assert inputs[scope][2023].get("vsego", {}).get("q", 0) == (
            999 if scope == expected_scope else 0
        )


def test_summary_uses_group_nust_each_year_and_preserves_territories_and_totals(fuel_session):
    for group_id, d, r in ((1, 1, 1), (2, 1, 2), (3, None, None), (4, 1, 2)):
        fuel_session.execute(EquipmentGroup.__table__.update().where(
            EquipmentGroup.id == group_id,
        ).values(d=d, r=r))
    fuel_session.execute(EquipmentGroupFuelParam.__table__.update().where(
        EquipmentGroupFuelParam.equipment_group_id == 2,
        EquipmentGroupFuelParam.year_number == 2023,
    ).values(nust=60))
    fuel_session.execute(EquipmentGroupFuelParam.__table__.update().where(
        EquipmentGroupFuelParam.equipment_group_id == 3,
    ).values(nust=150))
    # Сведения агрегатов, даже противоречивые, больше не влияют на отбор ГО.
    _summary_machine(fuel_session, 10, 2, 200, expected=2030)
    _summary_machine(fuel_session, 11, 2, 50, expected=None)
    _summary_machine(fuel_session, 12, None, 100)

    inputs, errors = summary.build_fuel_summary([2023, 2024])

    assert not any(errors.values())
    assert inputs["new_lt100"][2023]["vsego"]["b"] == 2
    assert inputs["new_lt100"][2023]["centr"]["b"] == 2
    assert not inputs["new_lt100"][2024]
    assert inputs["new_ge100"][2023]["norilsk"]["b"] == 3
    assert inputs["new_ge100"][2024]["vsego"]["b"] == 9
    for year in (2023, 2024):
        assert inputs["operating"][year]["vsego"]["b"] == 1
        for field, total in (("b", 10), ("e", 1000), ("q", 100)):
            assert sum(inputs[scope][year].get("vsego", {}).get(field, 0) for scope in inputs) == total
    assert summary.load_fuel_summary([2023], "new_lt100")[2023]["vsego"]["b"] == 2


@pytest.mark.parametrize("version,param_version", [(1, None), (1, 2), (2, 2), (None, None)])
@pytest.mark.parametrize("scope,r", [("operating", 1), ("new_lt100", 2), ("new_ge100", 2)])
def test_summary_excludes_other_versions(fuel_session, version, param_version, scope, r):
    fuel_session.execute(EquipmentGroup.__table__.update().values(d=9))
    _insert_group(fuel_session, version=version, param_version=param_version)
    fuel_session.execute(EquipmentGroup.__table__.update().where(
        EquipmentGroup.id == 99,
    ).values(r=r))
    fuel_session.execute(EquipmentGroupFuelParam.__table__.update().where(
        EquipmentGroupFuelParam.equipment_group_id == 99,
    ).values(nust=50 if scope == "new_lt100" else 100))
    assert not summary.load_fuel_summary([2023], scope)[2023]
