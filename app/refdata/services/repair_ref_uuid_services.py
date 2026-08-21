# -*- coding: utf-8 -*-
"""Восстановление инварианта ref_uuid в версионированных справочниках.

В одной версии БД ref_uuid уникален. У одного названия во всех версиях —
один и тот же ref_uuid.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import uuid as uuid_lib
from typing import Callable, Iterable


def norm_name(value) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def norm_uuid(value) -> str:
    return str(value or "").strip().lower().strip("{}")


@dataclass(frozen=True)
class RefUuidUpdate:
    row_id: int
    name: str
    version_id: int | None
    old_uuid: str
    new_uuid: str


@dataclass
class RefUuidRepairPlan:
    updates: list[RefUuidUpdate] = field(default_factory=list)
    within_version_collisions: list[dict] = field(default_factory=list)
    split_names: list[dict] = field(default_factory=list)
    canonical_by_name: dict[str, str] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return bool(self.within_version_collisions or self.split_names or self.updates)


def _original_uuid_form(rows: Iterable[dict]) -> dict[str, str]:
    forms: dict[str, str] = {}
    for row in rows:
        raw = str(row.get("ref_uuid") or "").strip()
        key = norm_uuid(raw)
        if key and key not in forms:
            forms[key] = raw
    return forms


def _choose_canonical_uuids(
    by_name: dict[str, list[dict]],
    uuid_to_names: dict[str, set[str]],
    uuid_factory: Callable[[], str] | None = None,
) -> dict[str, str]:
    canonical: dict[str, str] = {}
    used: set[str] = set()

    for name, name_rows in by_name.items():
        counts = Counter(row["ref_uuid"] for row in name_rows if row["ref_uuid"])
        exclusive = [
            uuid_key
            for uuid_key, _count in counts.most_common()
            if uuid_to_names.get(uuid_key) == {name} and uuid_key not in used
        ]
        if exclusive:
            canonical[name] = exclusive[0]
            used.add(exclusive[0])

    for name, name_rows in sorted(by_name.items()):
        if name in canonical:
            continue
        counts = Counter(row["ref_uuid"] for row in name_rows if row["ref_uuid"])
        available = [
            uuid_key
            for uuid_key, _count in counts.most_common()
            if uuid_key and uuid_key not in used
        ]
        if available:
            canonical[name] = available[0]
            used.add(available[0])
            continue
        if uuid_factory is not None:
            generated = norm_uuid(uuid_factory())
            while not generated or generated in used:
                generated = norm_uuid(uuid_factory())
        else:
            n = 0
            while True:
                seed = f"refdata|{name}" if n == 0 else f"refdata|{name}|{n}"
                generated = norm_uuid(str(uuid_lib.uuid5(uuid_lib.NAMESPACE_URL, seed)))
                if generated not in used:
                    break
                n += 1
        canonical[name] = generated
        used.add(generated)

    return canonical


def plan_ref_uuid_repairs(
    rows: Iterable[dict],
    *,
    uuid_factory: Callable[[], str] | None = None,
) -> RefUuidRepairPlan:
    """Строит план: уникальный ref_uuid в версии, один uuid на название во всех версиях."""
    source_rows = list(rows)
    original_form = _original_uuid_form(source_rows)

    normalized: list[dict] = []
    for row in source_rows:
        name = norm_name(row.get("name"))
        normalized.append(
            {
                "id": int(row["id"]),
                "name": name,
                "name_display": str(row.get("name") or "").strip() or name,
                "ref_uuid": norm_uuid(row.get("ref_uuid")),
                "database_version_id": row.get("database_version_id"),
            }
        )

    by_name: dict[str, list[dict]] = defaultdict(list)
    uuid_to_names: dict[str, set[str]] = defaultdict(set)
    for row in normalized:
        if not row["name"]:
            continue
        by_name[row["name"]].append(row)
        if row["ref_uuid"]:
            uuid_to_names[row["ref_uuid"]].add(row["name"])

    canonical_norm = _choose_canonical_uuids(by_name, uuid_to_names, uuid_factory)
    within_version_collisions = []
    by_version_uuid: dict[tuple, list[dict]] = defaultdict(list)
    for row in normalized:
        if not row["ref_uuid"]:
            continue
        by_version_uuid[(row["database_version_id"], row["ref_uuid"])].append(row)
    for (version_id, uuid_key), group in sorted(
        by_version_uuid.items(),
        key=lambda item: (item[0][0] is None, item[0][0] or 0, item[0][1]),
    ):
        names = sorted({item["name_display"] for item in group})
        if len(names) > 1:
            within_version_collisions.append(
                {
                    "database_version_id": version_id,
                    "ref_uuid": original_form.get(uuid_key, uuid_key),
                    "names": names,
                    "ids": [item["id"] for item in group],
                }
            )

    split_names = []
    for name, name_rows in sorted(by_name.items()):
        uuids = sorted({item["ref_uuid"] for item in name_rows if item["ref_uuid"]})
        if len(uuids) > 1:
            split_names.append(
                {
                    "name": name_rows[0]["name_display"],
                    "ref_uuids": [original_form.get(item, item) for item in uuids],
                    "ids": [item["id"] for item in name_rows],
                }
            )

    canonical_by_name = {
        name_rows[0]["name_display"]: original_form.get(uuid_key, uuid_key)
        for name, uuid_key in canonical_norm.items()
        for name_rows in [by_name[name]]
    }

    updates: list[RefUuidUpdate] = []
    for row in normalized:
        if not row["name"]:
            continue
        target_norm = canonical_norm[row["name"]]
        target = original_form.get(target_norm, target_norm)
        current = original_form.get(row["ref_uuid"], row["ref_uuid"])
        if norm_uuid(current) == target_norm:
            continue
        updates.append(
            RefUuidUpdate(
                row_id=row["id"],
                name=row["name_display"],
                version_id=row["database_version_id"],
                old_uuid=current,
                new_uuid=target,
            )
        )

    _assert_plan_unique_in_version(normalized, updates)
    return RefUuidRepairPlan(
        updates=updates,
        within_version_collisions=within_version_collisions,
        split_names=split_names,
        canonical_by_name=canonical_by_name,
    )


def _assert_plan_unique_in_version(rows: list[dict], updates: list[RefUuidUpdate]) -> None:
    by_id = {row["id"]: dict(row) for row in rows}
    for update in updates:
        by_id[update.row_id]["ref_uuid"] = norm_uuid(update.new_uuid)
    seen: dict[tuple, str] = {}
    for row in by_id.values():
        uuid_key = row["ref_uuid"]
        if not uuid_key:
            continue
        key = (row["database_version_id"], uuid_key)
        prev_name = seen.get(key)
        if prev_name is not None and prev_name != row["name"]:
            raise ValueError(
                f"После правки ref_uuid={uuid_key} всё ещё общий у разных названий "
                f"в версии {row['database_version_id']}: {prev_name!r} и {row['name']!r}."
            )
        seen[key] = row["name"]


def mapping_uuid_rewrites(plan: RefUuidRepairPlan) -> list[tuple[str, str, str]]:
    """Переносы uuid во внешних таблицах, только если старый uuid однозначно заменён."""
    old_to_new: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, RefUuidUpdate] = {}
    for update in plan.updates:
        old_key = norm_uuid(update.old_uuid)
        new_key = norm_uuid(update.new_uuid)
        if not old_key or old_key == new_key:
            continue
        old_to_new[old_key].add(new_key)
        samples.setdefault(old_key, update)

    canonical = {norm_uuid(value) for value in plan.canonical_by_name.values()}
    rewrites = []
    for old_key, new_keys in old_to_new.items():
        if old_key in canonical:
            continue
        if len(new_keys) != 1:
            continue
        sample = samples[old_key]
        rewrites.append((sample.old_uuid, sample.new_uuid, sample.name))
    return rewrites
