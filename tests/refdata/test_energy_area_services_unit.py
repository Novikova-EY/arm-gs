import types
import pytest
from unittest.mock import patch

from app.refdata.services.energy_systems.energy_area_services import update_energy_area_service


def test_update_energy_area_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_energy_area_service({"a": 1}, user="tester")


def test_update_energy_area_service_missing_fields_raise():
    # name и regional_district_id обязательны
    with pytest.raises(ValueError):
        update_energy_area_service([{"energy_area_id": 1, "name": ""}], user="tester")


def test_update_energy_area_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.energy_systems.energy_area_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_energy_area_service([
                {"energy_area_id": 1, "name": "EA", "regional_district_id": 2}
            ], user="tester")


def test_update_energy_area_service_unique_violation_raises():
    class DummyObj:
        def __init__(self):
            self.id = 1
            self.name = "Old"
            self.id_regional_district = 2

    class DummyQuery:
        def filter(self, *a, **k):
            return self

        def first(self):
            return True

    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return DummyObj()

        def flush(self):
            pass

    class DummyEnergyArea:
        def __init__(self):
            self.query = DummyQuery()

    with patch("app.refdata.services.energy_systems.energy_area_services.db.session", new=DummySession()), \
         patch("app.refdata.services.energy_systems.energy_area_services.EnergyArea", new=DummyEnergyArea()):
        with pytest.raises(ValueError):
            update_energy_area_service([
                {"energy_area_id": 1, "name": "New", "regional_district_id": 2}
            ], user="tester")


