import types
from unittest.mock import patch

from app.refdata.services.refdata_all_versions_common import (
    _fk_id_cache,
    _select_version_targets_for_update,
    fk_id_for_version,
    fk_id_resolution_cache,
    update_all_versions_records,
)


def test_fk_id_for_version_rejects_null_target_version():
    try:
        fk_id_for_version(types.SimpleNamespace(__name__="EnergyZone"), 10, None)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "id=None" in str(exc)


def test_fk_id_for_version_cache_batches_all_versions_on_first_miss():
    src = types.SimpleNamespace(id=10, ref_uuid="ru-fd", database_version_id=1)
    copy_v1 = types.SimpleNamespace(id=10, ref_uuid="ru-fd", database_version_id=1)
    copy_v2 = types.SimpleNamespace(id=20, ref_uuid="ru-fd", database_version_id=2)
    copy_v3 = types.SimpleNamespace(id=30, ref_uuid="ru-fd", database_version_id=3)
    query_calls = {"n": 0}

    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            query_calls["n"] += 1
            return [copy_v1, copy_v2, copy_v3]

    class DummySession:
        def get(self, model, id_):
            assert id_ == 10
            return src

    fake_model = types.SimpleNamespace(
        __name__="FederalDistrict",
        query=DummyQuery(),
        ref_uuid=object(),
        database_version_id=object(),
    )

    with patch(
        "app.refdata.services.refdata_all_versions_common.db.session",
        new=DummySession(),
    ):
        with fk_id_resolution_cache():
            assert fk_id_for_version(fake_model, 10, 1) == 10
            assert fk_id_for_version(fake_model, 10, 2) == 20
            assert fk_id_for_version(fake_model, 10, 3) == 30
            # Один SELECT по ref_uuid на все версии, не по одному на каждую.
            assert query_calls["n"] == 1
            cache = _fk_id_cache.get()
            assert cache[("FederalDistrict", 10, 2)] == 20

    assert _fk_id_cache.get() is None


def test_update_all_versions_records_logs_once_not_per_row():
    shared_ref = "shared-ref"
    anchor = types.SimpleNamespace(
        id=1,
        ref_uuid=shared_ref,
        database_version_id=1,
        name="A",
        id_energy_zone=100,
    )
    sibling = types.SimpleNamespace(
        id=3,
        ref_uuid=shared_ref,
        database_version_id=2,
        name="A",
        id_energy_zone=101,
    )

    class DummyColumn:
        def __eq__(self, other):
            return self

        def __ne__(self, other):
            return self

        def __invert__(self):
            return self

        def in_(self, values):
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

        def first(self):
            return None

    class _NoAutoflush:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class DummySession:
        def __init__(self, rows):
            self.no_autoflush = _NoAutoflush()
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
        name=DummyColumn(),
        __name__="RegionalDistrict",
        __tablename__="gs_sys_regional_districts",
    )
    log_calls = []

    with patch(
        "app.refdata.services.refdata_all_versions_common.db.session",
        new=DummySession([anchor, sibling]),
    ), patch(
        "app.refdata.services.refdata_all_versions_common.filter_by_explicit_db_version",
        side_effect=lambda query, model, version_id: query,
    ), patch(
        "app.refdata.services.refdata_all_versions_common._commit_with_retry",
    ), patch(
        "app.refdata.services.refdata_all_versions_common.log_to_db",
        side_effect=lambda *a, **k: log_calls.append((a, k)),
    ):
        update_all_versions_records(
            data=[{"regional_district_id": 1, "name": "B"}],
            user="tester",
            model_cls=fake_model,
            entity_type="regional_district",
            pk_field="regional_district_id",
            normalize_record=lambda record: {
                "regional_district_id": record["regional_district_id"],
                "name": record["name"],
            },
            resolve_for_version=lambda clean, version_id: {
                "name": clean["name"],
                "id_energy_zone": 200 + int(version_id),
            },
            tracked_fields=["name", "id_energy_zone"],
            unique_fields=["name"],
        )

    assert len(log_calls) == 1
    assert log_calls[0][0][1] == "Обновлены записи во всех версиях БД"
    assert "обновлено строк: 2" in log_calls[0][0][2]


def test_select_version_targets_prefers_matching_name_when_ref_uuid_duplicated():
    shared_ref = "broken-shared-ref"
    anchor = types.SimpleNamespace(
        id=652,
        ref_uuid=shared_ref,
        database_version_id=20,
        name="Калининградская область",
    )
    v7_other = types.SimpleNamespace(
        id=13,
        ref_uuid=shared_ref,
        database_version_id=7,
        name="Ленинградская область",
    )
    v7_same = types.SimpleNamespace(
        id=18,
        ref_uuid=shared_ref,
        database_version_id=7,
        name="Калининградская область",
    )
    orphan = types.SimpleNamespace(
        id=562,
        ref_uuid=shared_ref,
        database_version_id=None,
        name="Калининградская область",
    )
    v20_other = types.SimpleNamespace(
        id=648,
        ref_uuid=shared_ref,
        database_version_id=20,
        name="Ленинградская область",
    )

    selected = _select_version_targets_for_update(
        anchor,
        [v7_other, v7_same, orphan, v20_other, anchor],
    )
    assert [(obj.database_version_id, obj.id) for obj in selected] == [(7, 18), (20, 652)]


def test_update_all_versions_records_skips_null_database_version_copies():
    shared_ref = "shared-ref"
    anchor = types.SimpleNamespace(
        id=1,
        ref_uuid=shared_ref,
        database_version_id=1,
        name="Kaliningrad",
        id_energy_zone=100,
    )
    orphan = types.SimpleNamespace(
        id=2,
        ref_uuid=shared_ref,
        database_version_id=None,
        name="Kaliningrad",
        id_energy_zone=99,
    )
    sibling = types.SimpleNamespace(
        id=3,
        ref_uuid=shared_ref,
        database_version_id=2,
        name="Kaliningrad",
        id_energy_zone=101,
    )

    class DummyColumn:
        def __eq__(self, other):
            return self

        def __ne__(self, other):
            return self

        def __invert__(self):
            return self

        def in_(self, values):
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

        def first(self):
            return None

    class _NoAutoflush:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class DummySession:
        def __init__(self, rows):
            self.no_autoflush = _NoAutoflush()
            self._rows = {row.id: row for row in rows}

        def get(self, model, id_):
            return self._rows.get(id_)

        def flush(self):
            pass

        def rollback(self):
            pass

    fake_model = types.SimpleNamespace(
        query=DummyQuery([anchor, orphan, sibling]),
        ref_uuid=DummyColumn(),
        id=DummyColumn(),
        name=DummyColumn(),
        __name__="RegionalDistrict",
        __tablename__="gs_sys_regional_districts",
    )

    resolve_calls = []

    def resolve_for_version(clean, version_id):
        resolve_calls.append(version_id)
        return {
            "name": clean["name"],
            "id_energy_zone": 200 + int(version_id),
        }

    session = DummySession([anchor, orphan, sibling])

    with patch(
        "app.refdata.services.refdata_all_versions_common.db.session",
        new=session,
    ), patch(
        "app.refdata.services.refdata_all_versions_common.filter_by_explicit_db_version",
        side_effect=lambda query, model, version_id: query,
    ), patch(
        "app.refdata.services.refdata_all_versions_common._commit_with_retry",
    ), patch(
        "app.refdata.services.refdata_all_versions_common.log_to_db",
    ):
        updated_ids = update_all_versions_records(
            data=[{"regional_district_id": 1, "name": "Kaliningrad"}],
            user="tester",
            model_cls=fake_model,
            entity_type="regional_district",
            pk_field="regional_district_id",
            normalize_record=lambda record: {
                "regional_district_id": record["regional_district_id"],
                "name": record["name"],
            },
            resolve_for_version=resolve_for_version,
            tracked_fields=["name", "id_energy_zone"],
            unique_fields=["name"],
        )

    assert None not in resolve_calls
    assert resolve_calls == [1, 2]
    assert orphan.id_energy_zone == 99
    assert anchor.id_energy_zone == 201
    assert sibling.id_energy_zone == 202
    assert updated_ids == [1, 3]


def test_update_all_versions_records_handles_shared_ref_uuid_pair_on_same_page():
    shared_ref = "broken-shared-ref"
    kalin_v20 = types.SimpleNamespace(
        id=652,
        ref_uuid=shared_ref,
        database_version_id=20,
        name="Калининградская область",
        id_energy_zone=10,
    )
    lenin_v20 = types.SimpleNamespace(
        id=648,
        ref_uuid=shared_ref,
        database_version_id=20,
        name="Ленинградская область",
        id_energy_zone=11,
    )
    kalin_v7 = types.SimpleNamespace(
        id=18,
        ref_uuid=shared_ref,
        database_version_id=7,
        name="Калининградская область",
        id_energy_zone=20,
    )
    lenin_v7 = types.SimpleNamespace(
        id=13,
        ref_uuid=shared_ref,
        database_version_id=7,
        name="Ленинградская область",
        id_energy_zone=21,
    )
    all_rows = [kalin_v20, lenin_v20, kalin_v7, lenin_v7]

    class DummyColumn:
        def __eq__(self, other):
            return self

        def __ne__(self, other):
            return self

        def __invert__(self):
            return self

        def in_(self, values):
            return self

    class DummyQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def with_for_update(self):
            return self

        def all(self):
            return list(all_rows)

        def first(self):
            return None

    class _NoAutoflush:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class DummySession:
        def __init__(self):
            self.no_autoflush = _NoAutoflush()
            self._rows = {row.id: row for row in all_rows}

        def get(self, model, id_):
            return self._rows.get(id_)

        def flush(self):
            pass

        def rollback(self):
            pass

    fake_model = types.SimpleNamespace(
        query=DummyQuery(),
        ref_uuid=DummyColumn(),
        id=DummyColumn(),
        name=DummyColumn(),
        __name__="RegionalDistrict",
        __tablename__="gs_sys_regional_districts",
    )

    with patch(
        "app.refdata.services.refdata_all_versions_common.db.session",
        new=DummySession(),
    ), patch(
        "app.refdata.services.refdata_all_versions_common.filter_by_explicit_db_version",
        side_effect=lambda query, model, version_id: query,
    ), patch(
        "app.refdata.services.refdata_all_versions_common._commit_with_retry",
    ), patch(
        "app.refdata.services.refdata_all_versions_common.log_to_db",
    ):
        updated_ids = update_all_versions_records(
            data=[
                {
                    "regional_district_id": 652,
                    "name": "Калининградская область",
                    "energy_zone_id": 99,
                },
                {
                    "regional_district_id": 648,
                    "name": "Ленинградская область",
                    "energy_zone_id": 88,
                },
            ],
            user="tester",
            model_cls=fake_model,
            entity_type="regional_district",
            pk_field="regional_district_id",
            normalize_record=lambda record: {
                "regional_district_id": record["regional_district_id"],
                "name": record["name"],
                "energy_zone_id": record["energy_zone_id"],
            },
            resolve_for_version=lambda clean, version_id: {
                "name": clean["name"],
                "id_energy_zone": clean["energy_zone_id"] + int(version_id),
            },
            tracked_fields=["name", "id_energy_zone"],
            unique_fields=["name"],
        )

    assert kalin_v7.id_energy_zone == 99 + 7
    assert lenin_v7.id_energy_zone == 88 + 7
    assert kalin_v20.id_energy_zone == 99 + 20
    assert lenin_v20.id_energy_zone == 88 + 20
    assert set(updated_ids) == {652, 648, 18, 13}
