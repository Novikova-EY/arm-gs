# -*- coding: utf-8 -*-
"""Инвариант ref_uuid: уникален в версии, один на название во всех версиях."""

from app.refdata.services.repair_ref_uuid_services import (
    mapping_uuid_rewrites,
    plan_ref_uuid_repairs,
)


def _row(rid, name, ref_uuid, version_id):
    return {
        "id": rid,
        "name": name,
        "ref_uuid": ref_uuid,
        "database_version_id": version_id,
    }


SHARED = "11111111-1111-1111-1111-111111111111"
ZAB_UUID = "22222222-2222-2222-2222-222222222222"
KAL_UUID = "33333333-3333-3333-3333-333333333333"
ZAB = "Забайкальский край"
KAL = "Калининградская область"


def test_collision_keeps_exclusive_uuid_per_name():
    """Общий uuid в одной версии не должен переехать обоим субъектам."""
    rows = [
        _row(50, ZAB, ZAB_UUID, 5),
        _row(51, KAL, KAL_UUID, 5),
        _row(2268, ZAB, SHARED, 20),
        _row(2272, KAL, SHARED, 20),
    ]
    plan = plan_ref_uuid_repairs(rows)
    by_id = {item.row_id: item for item in plan.updates}

    assert by_id[2268].new_uuid == ZAB_UUID
    assert by_id[2272].new_uuid == KAL_UUID
    assert 50 not in by_id
    assert 51 not in by_id
    assert len(plan.within_version_collisions) == 1
    assert set(plan.within_version_collisions[0]["names"]) == {ZAB, KAL}


def test_selecting_both_subjects_stays_two_uuids():
    rows = [
        _row(2268, ZAB, SHARED, 20),
        _row(2272, KAL, SHARED, 20),
        _row(50, ZAB, ZAB_UUID, 5),
        _row(51, KAL, KAL_UUID, 5),
    ]
    plan = plan_ref_uuid_repairs(rows)
    after = {row["id"]: row["ref_uuid"] for row in rows}
    for update in plan.updates:
        after[update.row_id] = update.new_uuid
    assert after[2268] != after[2272]
    assert after[2268] == after[50] == ZAB_UUID
    assert after[2272] == after[51] == KAL_UUID


def test_shared_only_uuid_assigns_new_to_second_name():
    rows = [
        _row(1, ZAB, SHARED, 1),
        _row(2, KAL, SHARED, 1),
        _row(3, ZAB, SHARED, 2),
        _row(4, KAL, SHARED, 2),
    ]
    generated = iter(["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"])
    plan = plan_ref_uuid_repairs(rows, uuid_factory=lambda: next(generated))
    after = {}
    for row in rows:
        after[(row["id"], row["name"])] = row["ref_uuid"]
    for update in plan.updates:
        after[(update.row_id, update.name)] = update.new_uuid
    zab_uuids = {after[(1, ZAB)], after[(3, ZAB)]}
    kal_uuids = {after[(2, KAL)], after[(4, KAL)]}
    assert len(zab_uuids) == 1
    assert len(kal_uuids) == 1
    assert zab_uuids != kal_uuids


def test_same_name_across_versions_unified():
    rows = [
        _row(1, ZAB, ZAB_UUID, 1),
        _row(2, ZAB, "44444444-4444-4444-4444-444444444444", 2),
    ]
    plan = plan_ref_uuid_repairs(rows)
    assert len(plan.split_names) == 1
    assert {item.new_uuid for item in plan.updates} == {ZAB_UUID}
    assert plan.updates[0].row_id == 2


def test_mapping_rewrite_skips_ambiguous_shared_uuid():
    rows = [
        _row(50, ZAB, ZAB_UUID, 5),
        _row(2268, ZAB, SHARED, 20),
        _row(2272, KAL, SHARED, 20),
        _row(51, KAL, KAL_UUID, 5),
    ]
    plan = plan_ref_uuid_repairs(rows)
    assert mapping_uuid_rewrites(plan) == []


def test_unspecified_duplicate_rows_same_uuid_are_ok():
    rows = [
        _row(545, "Не указано", SHARED, None),
        _row(2705, "Не указано", SHARED, None),
    ]
    plan = plan_ref_uuid_repairs(rows)
    assert plan.updates == []
    assert plan.within_version_collisions == []


def test_mapping_rewrite_when_uuid_fully_replaced():
    leftover = "44444444-4444-4444-4444-444444444444"
    rows = [
        _row(1, ZAB, ZAB_UUID, 1),
        _row(2, ZAB, leftover, 2),
    ]
    plan = plan_ref_uuid_repairs(rows)
    assert mapping_uuid_rewrites(plan) == [(leftover, ZAB_UUID, ZAB)]
