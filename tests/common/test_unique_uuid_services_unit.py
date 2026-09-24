# -*- coding: utf-8 -*-
from app.common.services.unique_uuid_services import (
    allocate_unique_uuid,
    choose_identity_uuid,
    plan_within_version_uuid_rewrites,
)


def test_allocate_keeps_free_preferred():
    used = {"aaa"}
    assert allocate_unique_uuid(used, preferred="bbb") == "bbb"
    assert "bbb" in used


def test_allocate_skips_used_preferred():
    used = {"aaa"}
    got = allocate_unique_uuid(used, preferred="aaa", factory=lambda: "bbb")
    assert got == "bbb"
    assert "aaa" in used and "bbb" in used


def test_choose_keeps_family_uuid_used_in_other_version():
    got = choose_identity_uuid(
        "aaa",
        taken_in_version=set(),
        taken_globally={"aaa"},
    )
    assert got == "aaa"


def test_choose_replaces_uuid_taken_in_this_version():
    got = choose_identity_uuid(
        "aaa",
        taken_in_version={"aaa"},
        taken_globally={"aaa"},
        factory=lambda: "bbb",
    )
    assert got == "bbb"


def test_plan_keeps_lowest_id_and_shares_new_uuid_across_versions():
    rows = [
        {"id": 1, "database_version_id": 22, "external_code": "A"},
        {"id": 2, "database_version_id": 22, "external_code": "A"},
        {"id": 3, "database_version_id": 22, "external_code": "A"},
        {"id": 10, "database_version_id": 37, "external_code": "A"},
        {"id": 11, "database_version_id": 37, "external_code": "A"},
        {"id": 12, "database_version_id": 37, "external_code": "A"},
    ]
    codes = iter(["u1", "u2"])
    plan = plan_within_version_uuid_rewrites(rows, uuid_factory=lambda: next(codes))
    by_id = {item.row_id: item.new_uuid for item in plan}
    assert 1 not in by_id
    assert 10 not in by_id
    assert by_id[2] == by_id[11]
    assert by_id[3] == by_id[12]
    assert by_id[2] != by_id[3]
    assert len(plan) == 4


def test_plan_ignores_unique_codes_shared_across_versions():
    rows = [
        {"id": 1, "database_version_id": 1, "external_code": "A"},
        {"id": 2, "database_version_id": 2, "external_code": "A"},
    ]
    assert plan_within_version_uuid_rewrites(rows) == []


def test_duplicate_identity_report_shape():
    from app.common.services.unique_uuid_services import IdentityUuidRewrite
    from app.common.services import duplicate_identity_uuid_services as svc

    report = {
        "applied": False,
        "database_version": 37,
        "comment": "x",
        "stations": {"count": 1, "rows": []},
        "machines": {"count": 0, "rows": []},
        "refdata": {"included": False, "table_count": 0, "count": 0, "tables": []},
    }
    assert report["applied"] is False
    rewrite = IdentityUuidRewrite(
        row_id=2, version_id=37, old_uuid="A", new_uuid="u1"
    )
    filtered = svc._filter_version(
        [
            IdentityUuidRewrite(row_id=1, version_id=22, old_uuid="A", new_uuid="u1"),
            rewrite,
        ],
        37,
    )
    assert filtered == [rewrite]


def test_duplicate_identity_api_loader_sets_dataset(monkeypatch):
    from app.api.services import duplicate_identity_uuid_api_services as api_svc

    monkeypatch.setattr(
        api_svc,
        "build_duplicate_identity_uuid_report",
        lambda **kwargs: {
            "applied": False,
            "database_version": kwargs.get("version_id"),
            "stations": {"count": 0, "rows": []},
            "machines": {"count": 0, "rows": []},
            "refdata": {
                "included": kwargs.get("include_refdata"),
                "table_count": 0,
                "count": 0,
                "tables": [],
            },
        },
    )
    payload = api_svc.load_duplicate_identity_uuids_dataset(
        version_id=37, include_refdata=False
    )
    assert payload["dataset"] == "duplicate_identity_uuids"
    assert payload["database_version"] == 37
    assert payload["applied"] is False


def test_plan_does_not_reuse_existing_codes():
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return "B" if calls["n"] == 1 else "C"

    plan = plan_within_version_uuid_rewrites(
        [
            {"id": 1, "database_version_id": 1, "external_code": "A"},
            {"id": 2, "database_version_id": 1, "external_code": "A"},
            {"id": 3, "database_version_id": 1, "external_code": "B"},
        ],
        uuid_factory=factory,
    )
    assert len(plan) == 1
    assert plan[0].row_id == 2
    assert plan[0].new_uuid == "C"


def test_plan_does_not_reuse_ref_uuid_reserved_codes():
    codes = iter(["ref-uuid-taken", "free-uuid"])
    plan = plan_within_version_uuid_rewrites(
        [
            {"id": 1, "database_version_id": 1, "external_code": "A"},
            {"id": 2, "database_version_id": 1, "external_code": "A"},
        ],
        uuid_factory=lambda: next(codes),
        extra_reserved={"ref-uuid-taken"},
    )
    assert len(plan) == 1
    assert plan[0].row_id == 2
    assert plan[0].new_uuid == "free-uuid"
