from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption as Consumption,
)
from app.fuel.services.fuel_imports import import_equipment_group_specific_fuel_consumption_services as importer


@pytest.fixture
def fuel_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {
                EquipmentGroup.__table__.schema: None,
                Consumption.__table__.schema: None,
            }
        },
    )
    EquipmentGroup.__table__.create(engine)
    Consumption.__table__.create(engine)
    sessions = scoped_session(sessionmaker(bind=engine))
    with sessions() as session:
        monkeypatch.setattr(db, "session", sessions)
        monkeypatch.setattr(
            "app.common.services.database_version_filter.get_current_db_version_id",
            lambda: 20,
        )
        monkeypatch.setattr(importer, "log_to_db", lambda *args, **kwargs: None)
        yield session
    sessions.remove()
    engine.dispose()


def add_group(session, group_id, numb, version):
    session.execute(
        EquipmentGroup.__table__.insert().values(
            id=group_id,
            numb=numb,
            external_code=f"group-{group_id}",
            database_version_id=version,
        )
    )


def add_consumption(session, group_id, numb, year, version, **values):
    session.execute(
        Consumption.__table__.insert().values(
            equipment_group_id=group_id,
            numb1120=numb,
            year_number=year,
            database_version_id=version,
            **values,
        )
    )


def import_frame(monkeypatch, frame, year=2024):
    class ExcelFile:
        sheet_names = ["data"]

        def parse(self, _sheet, header=0):
            assert header == 0
            return frame

    monkeypatch.setattr(importer.pd, "ExcelFile", lambda _file: ExcelFile())
    monkeypatch.setattr(
        "app.common.services.database_version_filter.get_current_db_version_id",
        lambda: 20,
    )
    return importer.import_equipment_group_specific_fuel_consumption_calculated_from_excel(
        SimpleNamespace(filename="snapshot.xlsx"), "tester", year=year
    )


def test_import_replaces_year_snapshot_and_preserves_other_years_and_versions(
    fuel_session, monkeypatch,
):
    session = fuel_session
    add_group(session, 1, 100, 20)
    add_group(session, 2, 200, 20)
    add_group(session, 3, 300, 20)
    add_group(session, 4, 300, 22)
    add_group(session, 5, 100, 22)
    add_consumption(
        session,
        1,
        100,
        2024,
        20,
        name="old",
        k=7,
        y=8,
        btp=9,
        sntp=10,
        bk=11,
        snk=12,
        snbas=13,
        ksn=14,
        bbas=15,
        kh=16,
    )
    add_consumption(session, 2, 200, 2024, 20, y=55, k=3)
    add_consumption(session, 3, 300, 2024, 20, y=77, k=4)
    add_consumption(session, 3, 300, 2023, 20, y=88, k=5)
    add_consumption(session, 4, 300, 2024, 22, y=99, k=6)
    add_consumption(session, 5, 100, 2024, 22, y=111, k=7)
    session.commit()

    frame = pd.DataFrame(
        [
            {"NUMB1120": 100, "NAME": "new", "Year": 2030, "K": 0, "Y": 0},
            {"NUMB1120": 200, "NAME": None, "Year": 2023},
        ]
    )
    result = import_frame(monkeypatch, frame)

    assert result["created"] == 0
    assert result["updated"] == 2
    assert result["deleted"] == 1
    assert result["skipped"] == 0

    current_100 = session.query(Consumption).filter_by(
        equipment_group_id=1, year_number=2024, database_version_id=20
    ).one()
    assert current_100.name == "new"
    assert current_100.k == Decimal(0)
    assert current_100.y == Decimal(0)
    assert current_100.btp is None
    assert current_100.sntp is None
    assert current_100.bk is None
    assert current_100.snk is None

    current_200 = session.query(Consumption).filter_by(
        equipment_group_id=2, year_number=2024, database_version_id=20
    ).one()
    assert current_200.k is None
    assert current_200.y is None
    assert current_200.name is None

    assert session.query(Consumption).filter_by(
        equipment_group_id=3, year_number=2024, database_version_id=20
    ).count() == 0
    assert session.query(Consumption).filter_by(
        equipment_group_id=3, year_number=2023, database_version_id=20
    ).one().y == Decimal(88)
    assert session.query(Consumption).filter_by(
        equipment_group_id=4, year_number=2024, database_version_id=22
    ).one().y == Decimal(99)
    assert session.query(Consumption).filter_by(
        equipment_group_id=5, year_number=2024, database_version_id=22
    ).one().y == Decimal(111)


def test_import_creates_rows_for_all_empty_values_and_empty_file_clears_selected_year(
    fuel_session, monkeypatch,
):
    session = fuel_session
    add_group(session, 1, 100, 20)
    add_group(session, 2, 200, 20)
    add_consumption(session, 2, 200, 2024, 20, y=25)
    add_consumption(session, 2, 200, 2023, 20, y=35)
    session.commit()

    frame = pd.DataFrame([{"NUMB1120": 100}])
    result = import_frame(monkeypatch, frame)
    created = session.query(Consumption).filter_by(
        equipment_group_id=1, year_number=2024, database_version_id=20
    ).one()
    assert result["created"] == 1
    assert created.y is None
    assert created.k is None

    empty_result = import_frame(monkeypatch, pd.DataFrame(columns=["NUMB1120", "Y"]))
    assert empty_result["deleted"] == 1
    assert session.query(Consumption).filter_by(year_number=2024, database_version_id=20).count() == 0
    assert session.query(Consumption).filter_by(year_number=2023, database_version_id=20).count() == 1
