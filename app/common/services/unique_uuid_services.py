# -*- coding: utf-8 -*-
"""Уникальные identity-UUID в пределах версии БД.

Один и тот же UUID у копий одной сущности в разных версиях — нормально.
В одной версии (database_version_id, uuid) должен быть один.
Записи не удаляются: лишним копиям выдаётся новый UUID.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
import uuid
from typing import Callable, Iterable

from sqlalchemy import text as sql_text

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ALL_VERSIONS = object()


def norm_uuid(value) -> str:
    return str(value or "").strip().lower().strip("{}")


def new_uuid4() -> str:
    return str(uuid.uuid4())


def allocate_unique_uuid(
    used: set[str],
    preferred: str | None = None,
    factory: Callable[[], str] | None = None,
) -> str:
    """Возвращает preferred, если он свободен, иначе новый UUID. Добавляет результат в used."""
    factory = factory or new_uuid4
    preferred_raw = (preferred or "").strip()
    preferred_key = norm_uuid(preferred_raw)
    if preferred_key and preferred_key not in used:
        used.add(preferred_key)
        return preferred_raw
    for _ in range(32):
        candidate = factory()
        key = norm_uuid(candidate)
        if key and key not in used:
            used.add(key)
            return candidate
    raise RuntimeError("Не удалось выделить уникальный UUID")


def choose_identity_uuid(
    preferred: str | None,
    *,
    taken_in_version: set[str],
    taken_globally: set[str],
    factory: Callable[[], str] | None = None,
) -> str:
    """
    Копии одной сущности в других версиях могут делить UUID.
    Если preferred уже занят в этой версии — выдаём новый, не занятый ни в одной версии.
    """
    preferred_raw = (preferred or "").strip()
    preferred_key = norm_uuid(preferred_raw)
    taken_version = {norm_uuid(item) for item in taken_in_version if norm_uuid(item)}
    taken_all = {norm_uuid(item) for item in taken_globally if norm_uuid(item)}
    if preferred_key and preferred_key not in taken_version:
        return preferred_raw
    return allocate_unique_uuid(taken_all, factory=factory)


def _assert_ident(value: str, label: str) -> str:
    if not _IDENT.match(value or ""):
        raise ValueError(f"Некорректный {label}: {value!r}")
    return value


def identity_uuid_taken(
    connection,
    *,
    schema: str,
    table: str,
    column: str,
    code: str,
    version_id=_ALL_VERSIONS,
    exclude_id: int | None = None,
) -> bool:
    """Есть ли уже строка с этим UUID. version_id=_ALL_VERSIONS — любая версия."""
    schema = _assert_ident(schema, "schema")
    table = _assert_ident(table, "table")
    column = _assert_ident(column, "column")
    code_key = norm_uuid(code)
    if not code_key:
        return False

    params = {"code": code_key}
    version_clause = ""
    if version_id is not _ALL_VERSIONS:
        if version_id is None:
            version_clause = "AND database_version_id IS NULL"
        else:
            version_clause = "AND database_version_id = :vid"
            params["vid"] = version_id
    exclude_clause = ""
    if exclude_id is not None:
        exclude_clause = "AND id <> :exclude_id"
        params["exclude_id"] = exclude_id
    sql = f"""
        SELECT 1
        FROM {schema}.{table}
        WHERE lower(trim(COALESCE({column}, ''))) = :code
          {version_clause}
          {exclude_clause}
        LIMIT 1
    """
    row = connection.execute(sql_text(sql), params).first()
    return row is not None


def identity_uuid_taken_in_sources(
    connection,
    code: str,
    sources: Iterable[tuple[str, str, str]],
    *,
    exclude_id: int | None = None,
    current_schema: str | None = None,
    current_table: str | None = None,
) -> bool:
    """Есть ли UUID в любой из таблиц identity (ref_uuid / external_code)."""
    for schema, table, column in sources:
        extra_exclude = (
            exclude_id
            if schema == current_schema and table == current_table
            else None
        )
        if identity_uuid_taken(
            connection,
            schema=schema,
            table=table,
            column=column,
            code=code,
            version_id=_ALL_VERSIONS,
            exclude_id=extra_exclude,
        ):
            return True
    return False


def extra_identity_uuid_sources(schema: str, table: str) -> list[tuple[str, str, str]]:
    """Остальные identity-колонки (станции, агрегаты, ref_uuid справочников)."""
    from app.common.services.duplicate_identity_uuid_services import other_identity_uuid_sources

    return other_identity_uuid_sources(schema, table)


def ensure_unique_identity_uuid(
    connection,
    *,
    schema: str,
    table: str,
    column: str,
    preferred: str | None,
    version_id: int | None,
    exclude_id: int | None = None,
    factory: Callable[[], str] | None = None,
    extra_sources: Iterable[tuple[str, str, str]] | None = None,
) -> str:
    """Для INSERT: оставить preferred, если он свободен в версии, иначе новый глобально свободный UUID."""
    factory = factory or new_uuid4
    extra_sources = list(extra_sources or ())
    preferred_raw = (preferred or "").strip()
    if preferred_raw and not identity_uuid_taken(
        connection,
        schema=schema,
        table=table,
        column=column,
        code=preferred_raw,
        version_id=version_id,
        exclude_id=exclude_id,
    ):
        return preferred_raw
    for _ in range(32):
        candidate = factory()
        if identity_uuid_taken(
            connection,
            schema=schema,
            table=table,
            column=column,
            code=candidate,
            version_id=_ALL_VERSIONS,
            exclude_id=exclude_id,
        ):
            continue
        if extra_sources and identity_uuid_taken_in_sources(
            connection,
            candidate,
            extra_sources,
            exclude_id=exclude_id,
            current_schema=schema,
            current_table=table,
        ):
            continue
        return candidate
    raise RuntimeError(
        f"Не удалось выделить уникальный UUID для {schema}.{table}.{column}"
    )


@dataclass(frozen=True)
class IdentityUuidRewrite:
    row_id: int
    version_id: int | None
    old_uuid: str
    new_uuid: str


def plan_within_version_uuid_rewrites(
    rows: Iterable[dict],
    *,
    uuid_field: str = "external_code",
    uuid_factory: Callable[[], str] | None = None,
    extra_reserved: Iterable[str] | None = None,
) -> list[IdentityUuidRewrite]:
    """
    Для групп (version, uuid) с несколькими строками:
    запись с минимальным id сохраняет UUID,
    остальные получают новый (один и тот же новый UUID у одного ранга во всех версиях).
    Ничего не удаляет.
    """
    items = []
    for row in rows:
        raw = str(row.get(uuid_field) or "").strip()
        code = norm_uuid(raw)
        if not code:
            continue
        items.append(
            {
                "id": int(row["id"]),
                "version_id": row.get("database_version_id"),
                "code": code,
                "original": raw,
            }
        )

    used = {item["code"] for item in items}
    if extra_reserved:
        used.update(norm_uuid(item) for item in extra_reserved if norm_uuid(item))
    by_code: dict[str, dict] = defaultdict(lambda: defaultdict(list))
    for item in items:
        by_code[item["code"]][item["version_id"]].append(item)
    for versions in by_code.values():
        for members in versions.values():
            members.sort(key=lambda item: item["id"])

    factory = uuid_factory or new_uuid4
    rewrites: list[IdentityUuidRewrite] = []
    for orig_code, by_version in by_code.items():
        del orig_code
        if all(len(members) <= 1 for members in by_version.values()):
            continue
        max_rank = max(len(members) for members in by_version.values())
        for rank in range(1, max_rank):
            new_code = allocate_unique_uuid(used, factory=factory)
            for members in by_version.values():
                if rank >= len(members):
                    continue
                member = members[rank]
                rewrites.append(
                    IdentityUuidRewrite(
                        row_id=member["id"],
                        version_id=member["version_id"],
                        old_uuid=member["original"],
                        new_uuid=new_code,
                    )
                )
    rewrites.sort(
        key=lambda item: (
            item.version_id is None,
            item.version_id or 0,
            item.row_id,
        )
    )
    return rewrites
