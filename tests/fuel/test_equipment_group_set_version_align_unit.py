# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.fuel.services.equipment_groups.equipment_group_set_services import (
    resolve_station_and_type_for_version,
)
from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
    ensure_equipment_group_linked_to_station,
)


def test_resolve_station_and_type_maps_clones_to_target_version():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_id_for_version",
        return_value=28505,
    ), patch(
        "app.common.services.version_entity_resolve_services.resolve_equipment_group_type_id_for_version",
        return_value=265,
    ):
        station_id, type_id = resolve_station_and_type_for_version(6323, 113, 37)

    assert station_id == 28505
    assert type_id == 265


def test_resolve_station_and_type_aborts_when_station_clone_missing():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_id_for_version",
        return_value=None,
    ):
        station_id, type_id = resolve_station_and_type_for_version(6323, 113, 37)

    assert station_id is None
    assert type_id is None


def test_resolve_station_and_type_keeps_standalone_without_station():
    with patch(
        "app.common.services.version_entity_resolve_services.resolve_equipment_group_type_id_for_version",
        return_value=265,
    ):
        station_id, type_id = resolve_station_and_type_for_version(None, 113, 37)

    assert station_id is None
    assert type_id == 265


def test_ensure_linked_creates_versioned_set_station_when_missing():
    created_set = SimpleNamespace(id=99, equipment_group_set_station_id=10)
    canonical_link = SimpleNamespace(
        id=10, station_id=28505, equipment_group_type_id=265, database_version_id=37
    )
    existing_q = MagicMock()
    existing_q.filter.return_value = existing_q
    existing_q.first.return_value = None

    join_q = MagicMock()
    join_q.filter.return_value = existing_q

    query = MagicMock()
    query.join.return_value = join_q

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.resolve_fuel_equipment_group_id_for_version",
        create=True,
    ), patch(
        "app.common.services.version_entity_resolve_services.resolve_fuel_equipment_group_id_for_version",
        return_value=31321,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_and_type_for_version",
        return_value=(28505, 265),
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.EquipmentGroupSet"
    ) as set_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.find_or_create_versioned_equipment_group_set_station",
        return_value=canonical_link,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._create_equipment_group_set_with_retry",
        return_value=created_set,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.retarget_mismatched_version_links_for_group",
    ) as retarget:
        set_cls.query = query
        result = ensure_equipment_group_linked_to_station(
            equipment_group_id=31321,
            station_id=6323,
            version_id=37,
            equipment_group_type_id=113,
        )

    assert result is created_set
    retarget.assert_called_once_with(31321, canonical_link, 37)


def test_sync_infers_missing_type_instead_of_clearing_group():
    from app.fuel.services.equipment_groups.equipment_group_set_services import (
        sync_machine_fuel_equipment_group,
    )

    machine = SimpleNamespace(
        id=62802,
        id_station=28547,
        id_equipment_group=None,
        machine_fuel_param=None,
        database_version_id=37,
    )
    mfp = SimpleNamespace(equipment_group_id=17380)
    group = SimpleNamespace(id=17380, name="TES")
    set_v2 = SimpleNamespace(equipment_group_id=17380, equipment_group=group)

    def _fill_type(machine_obj, *, version_id, equipment_group_id=None):
        machine_obj.id_equipment_group = 1060
        return 1060

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services._get_machine_fuel_param",
        return_value=mfp,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.apply_inferred_equipment_group_type_to_machine",
        side_effect=_fill_type,
    ) as infer, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._machine_requires_new_equipment_group",
        return_value=False,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.ensure_equipment_group_set_variant_for_station",
        return_value=set_v2,
    ):
        result = sync_machine_fuel_equipment_group(machine, version_id=37)

    infer.assert_called_once()
    assert machine.id_equipment_group == 1060
    assert mfp.equipment_group_id == 17380
    assert result is group


def test_ensure_reuses_shared_group_when_station_is_not_primary_owner():
    from app.fuel.services.equipment_groups.equipment_group_set_services import (
        ensure_equipment_group_set_variant_for_station,
    )

    shared_group = SimpleNamespace(
        id=17286, name="ТЭС-2 и ТЭС-3 ЭнТЭС ПЛ «Энергетика» (ТЭЦ<90 ата (Р))"
    )
    station = SimpleNamespace(
        id=28386, name="ТЭС-3 ЭнТЭС ПЛ «Энергетика»", external_code="st-3"
    )
    group_type = SimpleNamespace(id=1310, name="ТЭЦ<90 ата (Р)", ref_uuid="type-uuid")
    link = SimpleNamespace(id=20892, station_id=28386, equipment_group_type_id=1310)
    shared_set = SimpleNamespace(
        id=55, equipment_group_id=17286, equipment_group=shared_group
    )

    def _session_get(model, entity_id):
        if entity_id == 28386:
            return station
        if entity_id == 1310:
            return group_type
        return None

    query = MagicMock()
    query.filter_by.return_value = query
    query.first.return_value = shared_set

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_and_type_for_version",
        return_value=(28386, 1310),
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.db"
    ) as db_mock, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.find_or_create_versioned_equipment_group_set_station",
        return_value=link,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._get_linked_equipment_groups",
        return_value=[shared_group],
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.station_is_primary_owner_of_equipment_group",
        return_value=False,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.EquipmentGroupSet"
    ) as set_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._sync_equipment_group_context_from_source",
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._create_equipment_group_set_with_retry",
    ) as create_set:
        db_mock.session.get.side_effect = _session_get
        set_cls.query = query
        result = ensure_equipment_group_set_variant_for_station(
            station_id=28386,
            equipment_group_type_id=1310,
            version_id=37,
            is_new_group=False,
        )

    assert result is shared_set
    create_set.assert_not_called()
