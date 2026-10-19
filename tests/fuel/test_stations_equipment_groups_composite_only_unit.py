# -*- coding: utf-8 -*-
"""Фильтр «Составные станции» (composite_only) на странице групп оборудования."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.electrical_intensity.models  # noqa: F401 — связи модели Year
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.stations import stations_equipment_groups_services as service


@pytest.fixture
def fuel_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        execution_options={
            "schema_translate_map": {EquipmentGroup.__table__.schema: None}
        },
    )
    EquipmentGroup.__table__.create(engine)
    with Session(engine) as session:
        monkeypatch.setattr(db, "session", session)
        session.execute(
            EquipmentGroup.__table__.insert(),
            [
                # Составная станция: родитель comp=1, main пуст
                {"id": 1, "external_code": "parent", "numb": 100, "comp": 1, "main": None, "database_version_id": 1},
                # Её группы
                {"id": 2, "external_code": "child-1", "numb": 101, "comp": None, "main": 100, "database_version_id": 1},
                {"id": 3, "external_code": "child-2", "numb": 102, "comp": 0, "main": 100, "database_version_id": 1},
                # Обычная ТЭС: comp пуст, main пуст
                {"id": 4, "external_code": "plain-tes", "numb": 200, "comp": None, "main": None, "database_version_id": 1},
                # Группа обычной ТЭС: main указывает на «не составной» numb
                {"id": 5, "external_code": "plain-group", "numb": 201, "comp": None, "main": 200, "database_version_id": 1},
                # Родитель с main=0 (как в Access) — тоже составная станция
                {"id": 6, "external_code": "parent-zero-main", "numb": 300, "comp": 1, "main": 0, "database_version_id": 1},
                {"id": 7, "external_code": "child-of-zero", "numb": 301, "comp": None, "main": 300, "database_version_id": 1},
                # Другая версия БД — не должна попадать в текущую
                {"id": 8, "external_code": "other-version-parent", "numb": 400, "comp": 1, "main": None, "database_version_id": 2},
                {"id": 9, "external_code": "other-version-child", "numb": 401, "comp": None, "main": 400, "database_version_id": 2},
            ],
        )
        yield session
    engine.dispose()


def test_composite_only_returns_parents_with_their_groups(fuel_session):
    ids = service.get_composite_station_equipment_group_ids(version_id=1)

    assert ids == {1, 2, 3, 6, 7}


def test_composite_only_excludes_plain_station_groups(fuel_session):
    ids = service.get_composite_station_equipment_group_ids(version_id=1)

    assert 4 not in ids  # обычная ТЭС
    assert 5 not in ids  # её группа: main указывает на несоставной numb


def test_composite_only_ignores_other_versions(fuel_session):
    ids = service.get_composite_station_equipment_group_ids(version_id=1)

    assert 8 not in ids
    assert 9 not in ids


def test_composite_only_strict_version_keeps_only_current(fuel_session):
    ids = service.get_composite_station_equipment_group_ids(
        version_id=1, strict_version=True
    )

    assert ids == {1, 2, 3, 6, 7}


def test_composite_only_uses_parents_of_selected_version(fuel_session):
    ids = service.get_composite_station_equipment_group_ids(version_id=2)

    assert ids == {8, 9}