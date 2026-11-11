# -*- coding: utf-8 -*-
"""Поиск групп по имени, без совпадений в дополнительном названии."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401 – связи модели Year
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups import equipment_group_fuel_params_services as fuel_params
from app.fuel.services.stations.stations_equipment_groups_services import (
    get_filtered_equipment_group_ids_all,
)


@pytest.fixture
def name_filter_session(monkeypatch):
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {EquipmentGroup.__table__.schema: None},
    })

    @event.listens_for(engine, "connect")
    def unicode_lower(connection, _):
        # SQLite lower() не поддерживает кириллицу, в отличие от PostgreSQL.
        connection.create_function("lower", 1, lambda value: value.lower() if value else value)

    EquipmentGroup.__table__.create(engine)
    sessions = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", sessions)
    monkeypatch.setattr(fuel_params, "get_current_db_version_id", lambda: 20)
    with sessions() as session:
        session.execute(EquipmentGroup.__table__.insert(), [
            {"id": 1, "external_code": "eg-1", "database_version_id": 20,
             "name": "Гусевская ТЭЦ", "name_ext": "Гусевская ТЭЦ"},
            {"id": 2, "external_code": "eg-2", "database_version_id": 20,
             "name": "Маяковская ТЭС", "name_ext": "Гусевская ТЭС"},
            {"id": 3, "external_code": "eg-3", "database_version_id": 19,
             "name": "Гусевская ТЭЦ", "name_ext": None},
            {"id": 4, "external_code": "eg-4", "database_version_id": 20,
             "name": None, "name_ext": "Гусевская ТЭЦ"},
        ])
        session.commit()
        yield session
    sessions.remove()
    engine.dispose()


@pytest.mark.parametrize("search, expected", [
    ("  гУсЕв  ", {1}),
    ("Маяков", {2}),
    ("Несуществующая", set()),
    ("", {1, 2, 4}),
])
def test_equipment_group_search_uses_only_name(name_filter_session, search, expected):
    filters = {"equipment_group_name_filter": search}

    assert get_filtered_equipment_group_ids_all(
        filters, version_id=20, strict_version=True,
    ) == expected
    # Этот список используется экспортом и операциями страницы «Сведения о работе ТЭС».
    assert set(fuel_params.get_equipment_group_ids_for_fuel_params_filters(filters)) == expected
