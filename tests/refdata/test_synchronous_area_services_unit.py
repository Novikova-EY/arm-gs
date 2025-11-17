import types
import pytest
from unittest.mock import patch

from app.refdata.services.energy_systems.synchronous_area_services import update_synchronous_area_service


def test_update_synchronous_area_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_synchronous_area_service({"a": 1}, user="tester")


def test_update_synchronous_area_service_missing_name_raise():
    with pytest.raises(ValueError):
        update_synchronous_area_service([
            {"synchronous_area_id": 1, "name": "", "number": "1"}
        ], user="tester")


def test_update_synchronous_area_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.energy_systems.synchronous_area_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_synchronous_area_service([
                {"synchronous_area_id": 1, "name": "SA", "number": "1"}
            ], user="tester")












