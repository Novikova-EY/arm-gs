import types
from unittest.mock import patch

from app.refdata.services.territories.regional_district_services import (
    _sync_energy_zone_aggregates_for_ids,
    update_regional_district_service,
)


def test_sync_energy_zone_aggregates_for_ids_skips_empty():
    with patch(
        "app.energy_consumption.services.energy_consumption_parameter_services"
        ".sync_energy_zone_consumption_aggregates"
    ) as sync_mock:
        _sync_energy_zone_aggregates_for_ids([])
        _sync_energy_zone_aggregates_for_ids([None])
        sync_mock.assert_not_called()


def test_sync_energy_zone_aggregates_for_ids_calls_sync_per_zone():
    class DummySession:
        def get(self, model, id_):
            return None

        def expire(self, obj, attrs):
            pass

    with patch(
        "app.refdata.services.territories.regional_district_services.db.session",
        new=DummySession(),
    ), patch(
        "app.energy_consumption.services.energy_consumption_parameter_services"
        ".sync_energy_zone_consumption_aggregates"
    ) as sync_mock:
        _sync_energy_zone_aggregates_for_ids([5, 3, 5], database_version_id=7)

    assert sync_mock.call_count == 2
    called_ids = [c.kwargs["id_energy_zone"] for c in sync_mock.call_args_list]
    assert called_ids == [3, 5]
    assert all(c.kwargs["database_version_id"] == 7 for c in sync_mock.call_args_list)


def test_update_regional_district_service_syncs_old_and_new_energy_zones():
    class DummyEZ:
        def __init__(self, ez_id, name):
            self.id = ez_id
            self.name = name

    class DummyRD:
        def __init__(self):
            self.id = 10
            self.name = "Subject"
            self.name_full = "Subject Full"
            self.name_rp = "Subject RP"
            self.name_dp = "Subject DP"
            self.region_id = 1
            self.id_federal_district = 2
            self.id_energy_zone = 14
            self.id_synchronous_area = None

    obj = DummyRD()
    zones = {14: DummyEZ(14, "Old Zone"), 20: DummyEZ(20, "New Zone")}

    class _NoAutoflush:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class DummySession:
        def __init__(self):
            self.no_autoflush = _NoAutoflush()

        def get(self, model, id_):
            model_name = getattr(model, "__name__", "")
            if model_name == "RegionalDistrict":
                return obj
            if model_name == "EnergyZone":
                return zones.get(id_)
            return None

        def flush(self):
            pass

    fake_query = types.SimpleNamespace(
        filter=lambda *a, **k: types.SimpleNamespace(first=lambda: None)
    )

    with patch(
        "app.refdata.services.territories.regional_district_services.db.session",
        new=DummySession(),
    ), patch(
        "app.refdata.services.territories.regional_district_services.apply_version_filter",
        side_effect=lambda q, model: fake_query,
    ), patch(
        "app.refdata.services.territories.regional_district_services.log_to_db",
    ), patch(
        "app.refdata.services.territories.regional_district_services._commit_with_retry",
    ), patch(
        "app.refdata.services.territories.regional_district_services"
        "._sync_energy_zone_aggregates_for_ids"
    ) as sync_helper:
        updated = update_regional_district_service(
            [
                {
                    "regional_district_id": 10,
                    "name": "Subject",
                    "name_full": "Subject Full",
                    "name_rp": "Subject RP",
                    "name_dp": "Subject DP",
                    "region_id": 1,
                    "energy_zone_id": 20,
                }
            ],
            user="tester",
        )

    assert updated == [10]
    assert obj.id_energy_zone == 20
    sync_helper.assert_called_once()
    synced_ids = sync_helper.call_args.args[0]
    assert synced_ids == {14, 20}
