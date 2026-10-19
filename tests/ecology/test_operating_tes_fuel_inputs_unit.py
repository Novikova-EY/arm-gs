"""Покрытие топливной сводки действующими и планируемыми группами."""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.electrical_intensity.models  # noqa: F401 — связи модели Year
from app.ecology.services import operating_tes_fuel_input_services as service
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
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
        RegionalEnergySystem,
        UnionEnergySystem,
    )
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {model.__table__.schema: None for model in models}
        },
    )
    for model in models:
        model.__table__.create(engine)
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


def _insert_group(session, *, d=1, version=1, param_version=1, ved=2):
    session.execute(
        EquipmentGroup.__table__.insert(),
        {"id": 99, "external_code": "test-99", "d": d, "database_version_id": version},
    )
    session.execute(
        EquipmentGroupFuelParam.__table__.insert(),
        {
            "equipment_group_id": 99,
            "year_number": 2023,
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

