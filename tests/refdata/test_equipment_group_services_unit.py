import types
import pytest
from unittest.mock import patch

from app.refdata.services.refdata_for_stations.technologies.equipment_group_services import (
    update_equipment_group_all_versions_service,
    update_equipment_group_service,
)


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

        def rollback(self):
            pass

    with patch("app.refdata.services.refdata_for_stations.technologies.equipment_group_services.db.session", new=DummySession()), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services.log_to_db"
    ):
        with pytest.raises(ValueError):
            update_equipment_group_service([
                {"equipment_group_id": 1, "name": "Group"}
            ], user="tester")


def test_update_equipment_group_all_versions_service_propagates_display_order():
    anchor = types.SimpleNamespace(
        id=1,
        ref_uuid="shared-ref",
        database_version_id=1,
        name="Group",
        display_order=15,
        id_technology_type=None,
        id_technology_availability=None,
    )
    sibling = types.SimpleNamespace(
        id=2,
        ref_uuid="shared-ref",
        database_version_id=2,
        name="Group",
        display_order=10,
        id_technology_type=None,
        id_technology_availability=None,
    )

    class DummyColumn:
        def __eq__(self, other):
            return self

        def __ne__(self, other):
            return self

        def asc(self):
            return self

    class DummyQuery:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def with_for_update(self):
            return self

        def all(self):
            return list(self._rows)

    class DummyDupQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def with_for_update(self):
            return self

        def first(self):
            return None

    class DummySession:
        def __init__(self, rows):
            self.no_autoflush = types.SimpleNamespace(
                __enter__=lambda s: None,
                __exit__=lambda s, *a: None,
            )
            self._rows = {row.id: row for row in rows}

        def get(self, model, id_):
            return self._rows.get(id_)

        def flush(self):
            pass

        def rollback(self):
            pass

    fake_model = types.SimpleNamespace(
        query=DummyQuery([anchor, sibling]),
        ref_uuid=DummyColumn(),
        id=DummyColumn(),
        display_order=DummyColumn(),
    )

    session = DummySession([anchor, sibling])

    with patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services.db.session",
        new=session,
    ), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services.EquipmentGroupType",
        new=fake_model,
    ), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services._equipment_group_dup_query_for_version",
        side_effect=lambda *args, **kwargs: DummyDupQuery(),
    ), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services.filter_by_explicit_db_version",
        side_effect=lambda *args, **kwargs: DummyDupQuery(),
    ), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services._commit_with_retry"
    ), patch(
        "app.refdata.services.refdata_for_stations.technologies.equipment_group_services.log_to_db"
    ):
        updated_ids = update_equipment_group_all_versions_service(
            [
                {
                    "equipment_group_id": 1,
                    "name": "Group",
                    "display_order": 15,
                    "technology_type_id": None,
                    "technology_availability_id": None,
                }
            ],
            user="tester",
        )

    assert sibling.display_order == 15
    assert updated_ids == [2]














