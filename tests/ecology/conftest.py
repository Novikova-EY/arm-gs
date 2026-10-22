"""Изолированное хранение срезов расчёта ТЭС без запуска остальных модулей."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, registry

from app.ecology.services import operating_tes_page_services as services


@pytest.fixture
def operating_tes_db(monkeypatch):
    mapper_registry = registry()
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS gs_eco")
        session = Session(connection)
        # Используем реальные таблицы, но не связи с моделями других модулей.
        for name in ("OperatingTesFuelCharacteristic", "OperatingTesCoefficient"):
            table = getattr(services, name).__table__
            model = type(name, (), {})
            mapper_registry.map_imperatively(model, table)
            table.create(connection)
            model.query = session.query(model)
            monkeypatch.setattr(services, name, model)
        monkeypatch.setattr(services, "db", SimpleNamespace(session=session))
        monkeypatch.setattr(services, "get_current_db_version_id", lambda: 1)
        yield session
        session.close()
    engine.dispose()
    mapper_registry.dispose()
