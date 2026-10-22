"""Названия и порядок ОЭС следуют справочнику, ключи расчёта не меняются."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, registry

from app.common.services.get_services.energy_systems import union_energy_system_get_services as reference
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full as load_reference_systems,
)
from app.ecology.services.operating_tes_constants import COEFFICIENT_TERRITORIES, TERRITORIES
from app.ecology.services.operating_tes_territory_services import get_territory_columns


@pytest.fixture
def reference_db(monkeypatch):
    table = reference.UnionEnergySystem.__table__
    engine = create_engine("sqlite://", execution_options={"schema_translate_map": {table.schema: None}})
    mapper_registry = registry()
    model = type("ReferenceSystem", (), {})
    mapper_registry.map_imperatively(model, table)
    table.create(engine)
    with Session(engine) as session:
        model.query = session.query(model)
        monkeypatch.setattr(reference, "UnionEnergySystem", model)
        monkeypatch.setattr(reference, "get_current_version", lambda: 1)
        monkeypatch.setattr(reference, "get_union_energy_system_list_full", load_reference_systems)
        session.add_all([
            model(id=1, name="ОЭС Северо-Запада", display_order=3, database_version_id=1),
            model(id=2, name="ОЭС Центра (справочник)", display_order=1, database_version_id=1),
            model(id=3, name="ОЭС Урала", display_order=2, database_version_id=1),
            model(id=4, name="ТИТЭС Сибири", display_order=0, database_version_id=1),
            model(id=5, name="ОЭС Сибири", display_order=None, database_version_id=1),
            model(id=6, name="ОЭС Северо-Запада (другая версия)", display_order=1, database_version_id=2),
            model(id=7, name="ОЭС Центра", display_order=2, database_version_id=2),
        ])
        session.commit()
        yield session, model
    mapper_registry.dispose()
    engine.dispose()


@pytest.mark.parametrize("catalog", [TERRITORIES, COEFFICIENT_TERRITORIES])
def test_reference_order_names_and_current_version(reference_db, monkeypatch, catalog):
    session, model = reference_db
    columns = get_territory_columns(catalog)
    oes = [item for item in columns if item.get("group") == "territory" and item["slug"] != "vsego"]
    assert [item["slug"] for item in oes[:4]] == ["centr", "ural", "severo-zapad", "sibir"]
    assert oes[0]["sheet_name"] == "ОЭС Центра (справочник)"
    assert {item["slug"] for item in columns} == {item["slug"] for item in catalog}
    assert next(item for item in columns if item["slug"] == "sibir")["sheet_name"] == "ОЭС Сибири"

    session.get(model, 1).display_order = 0
    session.commit()
    assert get_territory_columns(catalog)[1 if catalog is COEFFICIENT_TERRITORIES else 3]["slug"] == "severo-zapad"

    monkeypatch.setattr(reference, "get_current_version", lambda: 2)
    columns = get_territory_columns(catalog)
    northwest = next(item for item in columns if item["slug"] == "severo-zapad")
    assert northwest["sheet_name"] == "ОЭС Северо-Запада (другая версия)"
    # Подписи справочника не записываются в общий каталог и не протекают между версиями.
    assert next(item for item in catalog if item["slug"] == "centr")["sheet_name"] == "ОЭС Центра"


def test_affiliation_and_special_territory_names_keep_saved_keys():
    columns = get_territory_columns()
    assert [(item["slug"], item["sheet_name"]) for item in columns[:3]] == [
        ("vsego", "Всего"), ("minen", "Станции отрасли"), ("prompred", "Пром-предприятия"),
    ]
    assert [(item["slug"], item["sheet_name"]) for item in columns[-3:]] == [
        ("norilsk", "ТИТЭС Сибири"),
        ("isolated-dv", "ТИТЭС Востока"),
        ("nikolaevsky", "Децентрализованная зона (Николаевский энергорайон)"),
    ]
