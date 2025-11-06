import types
from unittest.mock import patch

import pytest

from app.refdata.services.fuels.fuel_services import update_fuel_service


def test_update_fuel_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_fuel_service({"a": 1}, user="tester")


def test_update_fuel_service_missing_name_raises():
    with pytest.raises(ValueError):
        update_fuel_service([{"fuel_id": 1, "name": ""}], user="tester")


def test_update_fuel_service_not_found_raises():
    # emulate db.session.get returns None
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.fuels.fuel_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_fuel_service([{"fuel_id": 1, "name": "Test"}], user="tester")


def test_update_fuel_service_unique_violation_raises():
    # emulate object exists and query.first returns truthy when name changes
    class DummyObj:
        def __init__(self):
            self.id = 1
            self.name = "Old"
            self.id_fuel_type = None

    class DummyQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return True

    class DummyFuelModel:
        def __init__(self):
            self.query = DummyQuery()

    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return DummyObj()

        def flush(self):
            pass

    with patch("app.refdata.services.fuels.fuel_services.db.session", new=DummySession()), \
         patch("app.refdata.services.fuels.fuel_services.Fuel", new=DummyFuelModel()):
        with pytest.raises(ValueError):
            update_fuel_service([{"fuel_id": 1, "name": "New"}], user="tester")


