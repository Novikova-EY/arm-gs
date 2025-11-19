import types
import pytest
from unittest.mock import patch

from app.refdata.services.refdata_for_stations.technologies.equipment_group_services import update_equipment_group_service


def test_update_equipment_group_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_equipment_group_service({"a": 1}, user="tester")


def test_update_equipment_group_service_missing_name_raise():
    with pytest.raises(ValueError):
        update_equipment_group_service([
            {"equipment_group_id": 1, "name": ""}
        ], user="tester")


def test_update_equipment_group_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.refdata_for_stations.technologies.equipment_group_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_equipment_group_service([
                {"equipment_group_id": 1, "name": "Group"}
            ], user="tester")













