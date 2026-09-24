# -*- coding: utf-8 -*-
"""План разведения дублирующих identity-UUID. Записи не удаляет и сам ничего не пишет."""
from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text

from app.common.services.unique_uuid_services import (
    IdentityUuidRewrite,
    plan_within_version_uuid_rewrites,
)
from app.extensions import db
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin
from config import SCHEMA_GENERATION


def load_identity_code_rows(
    schema: str,
    table: str,
    column: str,
    *,
    require_version: bool = False,
) -> list[dict]:
    version_filter = "AND database_version_id IS NOT NULL" if require_version else ""
    rows = db.session.execute(
        text(
            f"""
            SELECT id, database_version_id, {column} AS code
            FROM {schema}.{table}
            WHERE trim(COALESCE({column}, '')) <> ''
              {version_filter}
            """
        )
    ).fetchall()
    return [
        {
            "id": row.id,
            "database_version_id": row.database_version_id,
            column: row.code,
        }
        for row in rows
    ]


def iter_identity_uuid_sources() -> list[tuple[str, str, str]]:
    sources = [
        (SCHEMA_GENERATION, "gs_gen_stations", "external_code"),
        (SCHEMA_GENERATION, "gs_gen_machines", "external_code"),
    ]
    for _cls, schema, table in iter_refdata_uuid_models():
        sources.append((schema, table, "ref_uuid"))
    return sources


def other_identity_uuid_sources(schema: str, table: str) -> list[tuple[str, str, str]]:
    return [
        item
        for item in iter_identity_uuid_sources()
        if item[0] != schema or item[1] != table
    ]


def load_reserved_identity_uuids(
    *,
    exclude_schema: str | None = None,
    exclude_table: str | None = None,
) -> set[str]:
    from app.common.services.unique_uuid_services import norm_uuid

    used: set[str] = set()
    for schema, table, column in iter_identity_uuid_sources():
        if schema == exclude_schema and table == exclude_table:
            continue
        for row in load_identity_code_rows(schema, table, column):
            key = norm_uuid(row[column])
            if key:
                used.add(key)
    return used


def plan_identity_table(
    schema: str,
    table: str,
    column: str,
    *,
    require_version: bool = False,
    extra_reserved: set[str] | None = None,
) -> list[IdentityUuidRewrite]:
    return plan_within_version_uuid_rewrites(
        load_identity_code_rows(
            schema, table, column, require_version=require_version
        ),
        uuid_field=column,
        extra_reserved=extra_reserved,
    )


def iter_refdata_uuid_models():
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        try:
            if not issubclass(cls, RefdataUuidMixin):
                continue
        except TypeError:
            continue
        table = mapper.local_table
        if "ref_uuid" not in table.c or "database_version_id" not in table.c:
            continue
        if not table.schema:
            continue
        yield cls, table.schema, table.name


def _filter_version(
    rewrites: list[IdentityUuidRewrite],
    version_id: int | None,
) -> list[IdentityUuidRewrite]:
    if version_id is None:
        return rewrites
    return [item for item in rewrites if item.version_id == version_id]


def _rewrite_payload(item: IdentityUuidRewrite, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "id": item.row_id,
        "database_version_id": item.version_id,
        "old_uuid": item.old_uuid,
        "new_uuid": item.new_uuid,
    }
    if extra:
        payload.update(extra)
    return payload


def _station_labels(ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = db.session.execute(
        text(
            f"""
            SELECT id, name, name_combined, name_so
            FROM {SCHEMA_GENERATION}.gs_gen_stations
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).fetchall()
    labels = {}
    for row in rows:
        name = (row.name or row.name_combined or row.name_so or "").strip()
        labels[int(row.id)] = {"name": name}
    return labels


def _machine_labels(ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    rows = db.session.execute(
        text(
            f"""
            SELECT id, id_station, machine_number, machine_name
            FROM {SCHEMA_GENERATION}.gs_gen_machines
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids},
    ).fetchall()
    return {
        int(row.id): {
            "id_station": row.id_station,
            "machine_number": (row.machine_number or "").strip(),
            "machine_name": (row.machine_name or "").strip(),
        }
        for row in rows
    }


def _section_rows(
    rewrites: list[IdentityUuidRewrite],
    labels: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [_rewrite_payload(item, labels.get(item.row_id)) for item in rewrites]


def build_duplicate_identity_uuid_report(
    *,
    version_id: int | None = None,
    include_refdata: bool = False,
) -> dict[str, Any]:
    """Тот же план, что у scripts/fix_duplicate_identity_uuids.py --dry-run. Без записи в БД."""
    station_rewrites = _filter_version(
        plan_identity_table(
            SCHEMA_GENERATION,
            "gs_gen_stations",
            "external_code",
            extra_reserved=load_reserved_identity_uuids(
                exclude_schema=SCHEMA_GENERATION,
                exclude_table="gs_gen_stations",
            ),
        ),
        version_id,
    )
    machine_rewrites = _filter_version(
        plan_identity_table(
            SCHEMA_GENERATION,
            "gs_gen_machines",
            "external_code",
            extra_reserved=load_reserved_identity_uuids(
                exclude_schema=SCHEMA_GENERATION,
                exclude_table="gs_gen_machines",
            ),
        ),
        version_id,
    )

    refdata_tables: list[dict[str, Any]] = []
    if include_refdata:
        for _cls, schema, table in sorted(
            iter_refdata_uuid_models(),
            key=lambda item: (item[1], item[2]),
        ):
            rewrites = _filter_version(
                plan_identity_table(
                    schema,
                    table,
                    "ref_uuid",
                    require_version=True,
                    extra_reserved=load_reserved_identity_uuids(
                        exclude_schema=schema,
                        exclude_table=table,
                    ),
                ),
                version_id,
            )
            if not rewrites:
                continue
            refdata_tables.append(
                {
                    "schema": schema,
                    "table": table,
                    "count": len(rewrites),
                    "rows": [_rewrite_payload(item) for item in rewrites],
                }
            )

    station_ids = [item.row_id for item in station_rewrites]
    machine_ids = [item.row_id for item in machine_rewrites]
    refdata_total = sum(item["count"] for item in refdata_tables)
    return {
        "applied": False,
        "database_version": version_id,
        "comment": (
            "План разведения дублирующих UUID. Записи не удаляются и этим запросом не обновляются."
        ),
        "stations": {
            "count": len(station_rewrites),
            "rows": _section_rows(station_rewrites, _station_labels(station_ids)),
        },
        "machines": {
            "count": len(machine_rewrites),
            "rows": _section_rows(machine_rewrites, _machine_labels(machine_ids)),
        },
        "refdata": {
            "included": include_refdata,
            "table_count": len(refdata_tables),
            "count": refdata_total,
            "tables": refdata_tables,
        },
    }
