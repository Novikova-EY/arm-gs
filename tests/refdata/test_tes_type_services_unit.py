import types
import pytest
from unittest.mock import patch

from app.refdata.services.refdata_for_stations.machines.tes_type_services import update_tes_type_service


def test_update_tes_type_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_tes_type_service({"a": 1}, user="tester")


def test_update_tes_type_service_missing_name_raise():
    with pytest.raises(ValueError):
        update_tes_type_service([
            {"tes_type_id": 1, "name": ""}
        ], user="tester")


def test_update_tes_type_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.refdata_for_stations.machines.tes_type_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_tes_type_service([
                {"tes_type_id": 1, "name": "TES"}
            ], user="tester")












