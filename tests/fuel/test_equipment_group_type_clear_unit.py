# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    _apply_equipment_group_type_change_from_form,
)
from app.fuel.services.equipment_groups.equipment_group_set_services import (
    find_or_create_versioned_equipment_group_set_station,
    resolve_station_and_type_for_version,
)


def test_resolve_station_and_type_keeps_none_type():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_id_for_version",
        return_value=28505,
    ):
        station_id, type_id = resolve_station_and_type_for_version(6323, None, 37)

    assert station_id == 28505
    assert type_id is None


def test_find_or_create_allows_null_equipment_group_type():
    existing = SimpleNamespace(id=1, station_id=100, equipment_group_type_id=None)
    query = MagicMock()
    query.filter.return_value = query
    query.first.return_value = existing

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.EquipmentGroupSetStation"
    ) as cls:
        cls.query = query
        result = find_or_create_versioned_equipment_group_set_station(100, None, 20)

    assert result is existing
    assert query.filter.called


def test_apply_type_change_clears_type_without_refdata_lookup():
    set_row = SimpleNamespace(id=1, equipment_group_set_station_id=10)
    old_link = SimpleNamespace(
        id=10, station_id=100, equipment_group_type_id=1055, database_version_id=20
    )
    target = SimpleNamespace(
        id=11, station_id=100, equipment_group_type_id=None, database_version_id=20
    )
    set_query = MagicMock()
    set_query.filter_by.return_value = set_query
    set_query.order_by.return_value = set_query
    set_query.all.return_value = [set_row]
    link_query = MagicMock()
    link_query.get.return_value = old_link

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services.filter_by_explicit_db_version"
    ) as version_filter, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services.EquipmentGroupSet"
    ) as set_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services.EquipmentGroupSetStation"
    ) as link_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.resolve_station_and_type_for_version",
        return_value=(100, None),
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services.find_or_create_versioned_equipment_group_set_station",
        return_value=target,
    ) as find_or_create, patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services._point_group_set_at_link",
    ) as point_at, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services._update_machines_id_equipment_group_for_fuel_group",
    ), patch(
        "app.extensions.db"
    ):
        set_cls.query = set_query
        link_cls.query = link_query
        err = _apply_equipment_group_type_change_from_form(28257, None, 20)

    assert err is None
    version_filter.assert_not_called()
    find_or_create.assert_called_once_with(100, None, 20)
    point_at.assert_called_once_with(set_row, target)


def test_apply_egt_anchor_clears_type_without_resolving_refdata():
    from app.fuel.services.equipment_groups.equipment_group_merge_services import (
        _apply_egt_anchor_to_groups,
    )

    group = SimpleNamespace(id=28257)
    warnings: list[str] = []
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_merge_services._resolve_equipment_group_type_id_for_version"
    ) as resolve_type, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services._apply_equipment_group_type_change_from_form",
        return_value=None,
    ) as apply_change:
        err, applied = _apply_egt_anchor_to_groups([group], None, 20, warnings)

    assert err is None
    assert applied is True
    assert warnings == []
    resolve_type.assert_not_called()
    apply_change.assert_called_once_with(28257, None, 20)
