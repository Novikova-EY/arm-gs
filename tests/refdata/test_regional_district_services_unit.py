import types
import pytest
from unittest.mock import patch

from app.refdata.services.territories.regional_district_services import update_regional_district_service


def test_update_regional_district_service_raises_on_not_list():
    with pytest.raises(ValueError):
        update_regional_district_service({"a": 1}, user="tester")


def test_update_regional_district_service_missing_name_raise():
    with pytest.raises(ValueError):
        update_regional_district_service([
            {"regional_district_id": 1, "name": "", "name_full": "x"}
        ], user="tester")


def test_update_regional_district_service_not_found_raises():
    class DummySession:
        def __init__(self):
            self.no_autoflush = types.SimpleNamespace(__enter__=lambda s: None, __exit__=lambda s, *a: None)

        def get(self, model, id_):
            return None

        def flush(self):
            pass

    with patch("app.refdata.services.territories.regional_district_services.db.session", new=DummySession()):
        with pytest.raises(ValueError):
            update_regional_district_service([
                {"regional_district_id": 1, "name": "Name", "name_full": "Full"}
            ], user="tester")












