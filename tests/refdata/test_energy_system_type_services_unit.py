import types
import pytest
from unittest.mock import patch

from app.refdata.services.energy_systems.energy_system_type_services import update_energy_system_type_service


def test_update_energy_system_type_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_energy_system_type_service({"a": 1}, user="tester")


def test_update_energy_system_type_service_missing_name_raise():
    with pytest.raises(ValueError):
        update_energy_system_type_service([
            {"energy_system_type_id": 1, "name": ""}
        ], user="tester")


def test_update_energy_system_type_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.energy_systems.energy_system_type_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_energy_system_type_service([
                {"energy_system_type_id": 1, "name": "Name"}
            ], user="tester")













