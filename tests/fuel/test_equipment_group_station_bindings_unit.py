# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    _station_bindings_from_set_station_links,
    form_has_grouping_station_sync,
    grouping_station_ids_from_form,
    persist_equipment_group_grouping_station_if_in_form,
    sync_equipment_group_grouping_stations,
)


def test_station_bindings_lists_all_unique_stations_sorted_by_name():
    tec4 = SimpleNamespace(station_id=28489, station=SimpleNamespace(name="ТЭЦ-4 Светогорского ЦБК"))
    tec3 = SimpleNamespace(station_id=28488, station=SimpleNamespace(name="ТЭЦ-3 Светогорского ЦБК"))
    duplicate = SimpleNamespace(station_id=28488, station=SimpleNamespace(name="ТЭЦ-3 Светогорского ЦБК"))

    bindings = _station_bindings_from_set_station_links([tec4, tec3, duplicate])

    assert bindings == [
        {"id": 28488, "name": "ТЭЦ-3 Светогорского ЦБК"},
        {"id": 28489, "name": "ТЭЦ-4 Светогорского ЦБК"},
    ]


def test_station_bindings_skips_links_without_station_id():
    empty = SimpleNamespace(station_id=None, station=None)
    named = SimpleNamespace(station_id=10, station=SimpleNamespace(name="  Станция  "))

    bindings = _station_bindings_from_set_station_links([empty, named])

    assert bindings == [{"id": 10, "name": "Станция"}]


class _MultiDict(dict):
    def getlist(self, key):
        val = self.get(key)
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [val]


def test_grouping_station_ids_from_form_keeps_unique_order():
    form = _MultiDict({
        "grouping_station_ids": ["28384", "28385", "28384"],
        "grouping_station_id": "28385",
    })
    assert grouping_station_ids_from_form(form) == [28384, 28385]
    assert form_has_grouping_station_sync(form) is True


def test_form_has_grouping_station_sync_from_marker_even_if_empty():
    form = {"grouping_station_ids_present": "1"}
    assert form_has_grouping_station_sync(form) is True
    assert grouping_station_ids_from_form(form) == []


def test_sync_adds_second_station_without_unlinking_first():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "ensure_equipment_group_linked_to_station",
        return_value=SimpleNamespace(id=1),
    ) as ensure, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "linked_station_ids_for_equipment_group",
        return_value=[28384],
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_unlink_equipment_group_from_station",
    ) as unlink, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_unique_type_id_from_group_sets",
        return_value=1060,
    ):
        err = sync_equipment_group_grouping_stations(
            17286,
            [28384, 28385],
            version_id=37,
            equipment_group_type_id=1060,
        )

    assert err is None
    ensure.assert_any_call(
        equipment_group_id=17286,
        station_id=28384,
        version_id=37,
        equipment_group_type_id=1060,
    )
    ensure.assert_any_call(
        equipment_group_id=17286,
        station_id=28385,
        version_id=37,
        equipment_group_type_id=1060,
    )
    unlink.assert_not_called()


def test_sync_unlinks_station_removed_from_desired_set():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "ensure_equipment_group_linked_to_station",
        return_value=SimpleNamespace(id=1),
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "linked_station_ids_for_equipment_group",
        return_value=[28384, 28385],
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_unlink_equipment_group_from_station",
    ) as unlink:
        err = sync_equipment_group_grouping_stations(
            17286,
            [28384],
            version_id=37,
            equipment_group_type_id=1060,
        )

    assert err is None
    unlink.assert_called_once_with(17286, 28385, 37)


def test_sync_keeps_station_not_shown_on_card_when_saving_numb():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "ensure_equipment_group_linked_to_station",
        return_value=SimpleNamespace(id=1),
    ) as ensure, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "linked_station_ids_for_equipment_group",
        return_value=[28385, 28386],
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_unlink_equipment_group_from_station",
    ) as unlink:
        err = sync_equipment_group_grouping_stations(
            30400,
            [28385],
            version_id=37,
            equipment_group_type_id=1060,
            loaded_station_ids=[28385],
        )

    assert err is None
    unlink.assert_not_called()
    ensure.assert_any_call(
        equipment_group_id=30400,
        station_id=28386,
        version_id=37,
        equipment_group_type_id=1060,
    )


def test_sync_unlinks_only_station_removed_from_loaded_chips():
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "ensure_equipment_group_linked_to_station",
        return_value=SimpleNamespace(id=1),
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "linked_station_ids_for_equipment_group",
        return_value=[28385, 28386],
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_unlink_equipment_group_from_station",
    ) as unlink:
        err = sync_equipment_group_grouping_stations(
            30400,
            [28385],
            version_id=37,
            equipment_group_type_id=1060,
            loaded_station_ids=[28385, 28386],
        )

    assert err is None
    unlink.assert_called_once_with(30400, 28386, 37)


def test_display_links_keep_second_station_when_versions_differ():
    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        _display_relevant_set_station_links,
    )

    tes2 = SimpleNamespace(
        equipment_group_set_station=SimpleNamespace(
            station_id=28385, database_version_id=37, station=SimpleNamespace(name="ТЭС-2")
        )
    )
    tes3 = SimpleNamespace(
        equipment_group_set_station=SimpleNamespace(
            station_id=28386, database_version_id=None, station=SimpleNamespace(name="ТЭС-3")
        )
    )
    links = _display_relevant_set_station_links([tes2, tes3], 37)
    assert {lnk.station_id for lnk in links} == {28385, 28386}


def test_persist_syncs_station_list_from_form_marker():
    group = SimpleNamespace(id=17286, database_version_id=37)
    form = {
        "grouping_station_ids_present": "1",
        "grouping_station_ids": [28384, 28385],
        "equipment_group_type_id": "1060",
    }
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_effective_group_database_version_id",
        return_value=37,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_resolve_grouping_station_id_for_db_version",
        side_effect=lambda sid, vid: sid,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "sync_equipment_group_grouping_stations",
        return_value=None,
    ) as sync:
        err = persist_equipment_group_grouping_station_if_in_form(group, form)

    assert err is None
    sync.assert_called_once_with(
        17286,
        [28384, 28385],
        version_id=37,
        equipment_group_type_id=1060,
        loaded_station_ids=None,
    )


def test_persist_passes_loaded_station_ids_from_form():
    group = SimpleNamespace(id=30400, database_version_id=37)
    form = {
        "grouping_station_ids_present": "1",
        "grouping_station_ids_loaded_present": "1",
        "grouping_station_ids": [28385],
        "grouping_station_ids_loaded": [28385],
        "equipment_group_type_id": "1060",
    }
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_effective_group_database_version_id",
        return_value=37,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_resolve_grouping_station_id_for_db_version",
        side_effect=lambda sid, vid: sid,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "sync_equipment_group_grouping_stations",
        return_value=None,
    ) as sync:
        err = persist_equipment_group_grouping_station_if_in_form(group, form)

    assert err is None
    sync.assert_called_once_with(
        30400,
        [28385],
        version_id=37,
        equipment_group_type_id=1060,
        loaded_station_ids=[28385],
    )


def test_persist_legacy_grouping_station_id_adds_without_replacing():
    group = SimpleNamespace(id=17286, database_version_id=37)
    form = {"grouping_station_id": "28385", "equipment_group_type_id": "1060"}
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_effective_group_database_version_id",
        return_value=37,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "_resolve_grouping_station_id_for_db_version",
        return_value=28385,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services."
        "ensure_equipment_group_linked_to_station",
        return_value=SimpleNamespace(id=9),
    ) as ensure, patch(
        "app.fuel.services.equipment_groups.equipment_group_edit_services."
        "sync_equipment_group_grouping_stations",
    ) as sync:
        err = persist_equipment_group_grouping_station_if_in_form(group, form)

    assert err is None
    sync.assert_not_called()
    ensure.assert_called_once_with(
        equipment_group_id=17286,
        station_id=28385,
        version_id=37,
        equipment_group_type_id=1060,
    )
