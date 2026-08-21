# -*- coding: utf-8 -*-
"""Перенос id субъекта между версиями БД не должен подменять Забайкалье на Калининград."""

from app.generation.services.station_services.filters_services import (
    _choose_current_version_id,
    _expand_ids_across_versions_from_rows,
    _remap_ids_for_current_version_from_rows,
)


def _row(rid, ref_uuid, name, version_id):
    return {
        "id": rid,
        "ref_uuid": ref_uuid,
        "name": name,
        "database_version_id": version_id,
    }


ZAB_NAME = "забайкальский край"
KAL_NAME = "калининградская область"
SHARED_UUID = "shared-uuid-zab-kal"


def test_remap_keeps_current_version_id_when_ref_uuid_collides():
    """Выбор «Забайкальский край» в текущей версии не схлопывается в Калининград."""
    zab = _row(2268, SHARED_UUID, ZAB_NAME, 20)
    kal = _row(2272, SHARED_UUID, KAL_NAME, 20)
    current_rows = [zab, kal]

    assert _choose_current_version_id(zab, current_rows, 20) == 2268
    assert _remap_ids_for_current_version_from_rows(
        [2268], [zab, kal], current_rows, 20
    ) == [2268]


def test_remap_keeps_both_subjects_when_selected_together():
    zab = _row(2268, SHARED_UUID, ZAB_NAME, 20)
    kal = _row(2272, SHARED_UUID, KAL_NAME, 20)
    current_rows = [zab, kal]

    assert _remap_ids_for_current_version_from_rows(
        [2268, 2272], [zab, kal], current_rows, 20
    ) == [2268, 2272]


def test_remap_from_other_version_uses_name_when_uuid_collides():
    """Старый id Забайкалья при общем uuid попадает в Забайкалье текущей версии."""
    old_zab = _row(648, SHARED_UUID, ZAB_NAME, 5)
    zab = _row(2268, SHARED_UUID, ZAB_NAME, 20)
    kal = _row(2272, SHARED_UUID, KAL_NAME, 20)

    assert _choose_current_version_id(old_zab, [zab, kal], 20) == 2268
    assert _remap_ids_for_current_version_from_rows(
        [648], [old_zab], [zab, kal], 20
    ) == [2268]


def test_remap_unique_uuid_maps_to_current_version():
    old_kal = _row(100, "uuid-kaliningrad", KAL_NAME, 5)
    cur_kal = _row(2272, "uuid-kaliningrad", KAL_NAME, 20)

    assert _choose_current_version_id(old_kal, [cur_kal], 20) == 2272


def test_expand_across_versions_excludes_colliding_other_name():
    zab_v5 = _row(50, SHARED_UUID, ZAB_NAME, 5)
    zab_v20 = _row(2268, SHARED_UUID, ZAB_NAME, 20)
    kal_v20 = _row(2272, SHARED_UUID, KAL_NAME, 20)
    all_rows = [zab_v5, zab_v20, kal_v20]

    assert _expand_ids_across_versions_from_rows(
        [2268], [zab_v20], all_rows
    ) == [50, 2268]


def test_expand_includes_rename_when_uuid_unique_in_version():
    """Переименование субъекта (тот же uuid, другое имя) в версии без коллизии сохраняется."""
    old = _row(50, "uuid-zab", "читинская область", 5)
    new = _row(2268, "uuid-zab", ZAB_NAME, 20)

    assert _expand_ids_across_versions_from_rows(
        [2268], [new], [old, new]
    ) == [50, 2268]
