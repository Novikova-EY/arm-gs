# -*- coding: utf-8 -*-
"""
Сервисы для визуализации исторических данных.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import cast, tuple_
from sqlalchemy.types import Text

from app.refdata.models.history.refdata_entity_model import RefdataEntity, RefdataEntityYear
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year

MAX_ROWS = 200
MAX_YEARS = 20

REFDATA_SECTIONS = [
    {
        "title": "Справочники территорий РФ",
        "items": [
            ("federal_district", "Федеральные округа"),
            ("regional_district", "Субъекты РФ"),
        ],
    },
    {
        "title": "Справочники энергосистем",
        "items": [
            ("union_energy_system", "Объединенные энергосистемы"),
            ("regional_energy_system", "Региональные энергосистемы"),
        ],
    },
    {
        "title": "Справочники энергоузлов/энергорайонов",
        "items": [
            ("energy_unit", "Энергоузлы"),
            ("energy_area", "Энергорайоны"),
        ],
    },
    {
        "title": "Справочники типов энергосистем/энергозон",
        "items": [
            ("energy_system_type", "Типы энергосистем"),
            ("synchronous_area", "Синхронные зоны"),
            ("energy_zone", "Энергозоны"),
        ],
    },
    {
        "title": "Справочник генерирующих компаний",
        "items": [
            ("gen_company", "Генерирующие компании"),
        ],
    },
    {
        "title": "Справочники топлива",
        "items": [
            ("fuel_type", "Типы топлива"),
            ("fuel", "Виды топлива"),
        ],
    },
    {
        "title": "Справочники для станций",
        "items": [
            ("station_type", "Типы электростанций"),
            ("condition_type", "Типы состояния оборудования"),
            ("machine_type", "Типы агрегатов"),
        ],
    },
    {
        "title": "Справочники ТЭС",
        "items": [
            ("tes_type", "Типы ТЭС"),
            ("tes_machine_type", "Типы агрегатов ТЭС"),
            ("pgu_tes_machine_type", "Типы агрегатов ПГУ"),
        ],
    },
    {
        "title": "Справочники технологий",
        "items": [
            ("equipment_group", "Группы оборудования"),
            ("technology_type", "Типы технологий"),
            ("technology_availability", "Доступность технологии"),
        ],
    },
]

REFDATA_LABELS = {item[0]: item[1] for section in REFDATA_SECTIONS for item in section["items"]}


def _get_current_year_number(database_version_id: int | None) -> int | None:
    if not database_version_id:
        return None
    year_feature = YearFeature.query.filter_by(
        database_version_id=database_version_id,
        name="Текущий",
    ).first()
    if not year_feature:
        year_feature = (
            YearFeature.query.filter_by(database_version_id=database_version_id)
            .filter(YearFeature.name.ilike("%текущ%"))
            .order_by(YearFeature.id.asc())
            .first()
        )
    if not year_feature:
        return None
    current_year = Year.query.filter_by(
        database_version_id=database_version_id,
        id_year_feature=year_feature.id,
    ).first()
    if not current_year:
        return None
    return current_year.number


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def get_refdata_sections() -> list[dict[str, Any]]:
    return REFDATA_SECTIONS


def _apply_payload_search(query, payload_col, name_search: str | None):
    if not name_search:
        return query
    return query.filter(cast(payload_col, Text).ilike(f"%{name_search}%"))


def _apply_version_year(query, model, database_version_id: int | None, year: int | None, year_field: str):
    if database_version_id is not None:
        query = query.filter(model.database_version_id == database_version_id)
    if year is not None:
        query = query.filter(getattr(model, year_field) == year)
    return query


def _get_years_for_query(query, model, year_field: str, year: int | None) -> list[int]:
    if year is not None:
        return [year]
    year_col = getattr(model, year_field)
    years = [row[0] for row in query.with_entities(year_col).distinct().order_by(year_col.asc()).all()]
    years = [value for value in years if value is not None]
    if len(years) > MAX_YEARS:
        years = years[-MAX_YEARS:]
    return years


def _build_pivot(
    base_query,
    model,
    year_field: str,
    key_fields: list[str],
    years: list[int],
) -> list[dict[str, Any]]:
    key_columns = [getattr(model, field) for field in key_fields]
    keys = (
        base_query.with_entities(*key_columns)
        .distinct()
        .order_by(*key_columns)
        .limit(MAX_ROWS)
        .all()
    )
    if not keys:
        return []

    query = base_query
    if years:
        query = query.filter(getattr(model, year_field).in_(years))
    if len(key_fields) == 1:
        query = query.filter(key_columns[0].in_([key[0] for key in keys]))
    else:
        query = query.filter(tuple_(*key_columns).in_(keys))

    records = query.all()
    rows_map = {tuple(key): {"fields": dict(zip(key_fields, key)), "cells": {}} for key in keys}

    for record in records:
        key = tuple(getattr(record, field) for field in key_fields)
        rows_map[key]["cells"][getattr(record, year_field)] = record

    return [rows_map[tuple(key)] for key in keys]


def build_history_context(args) -> dict[str, Any]:
    database_version_id = _parse_int(args.get("database_version_id"))
    year = _parse_int(args.get("year"))
    name_search = (args.get("name_search") or "").strip() or None

    if year is None:
        year = _get_current_year_number(database_version_id)

    refdata_query = RefdataEntityYear.query.join(
        RefdataEntity, RefdataEntity.id == RefdataEntityYear.refdata_entity_id
    )
    refdata_query = _apply_version_year(refdata_query, RefdataEntityYear, database_version_id, None, "year")
    if name_search:
        refdata_query = _apply_payload_search(refdata_query, RefdataEntityYear.payload, name_search)
    refdata_years = _get_years_for_query(refdata_query, RefdataEntityYear, "year", year)
    refdata_rows = _build_pivot(
        refdata_query,
        RefdataEntityYear,
        "year",
        ["refdata_entity_id", "database_version_id"],
        refdata_years,
    )
    if refdata_rows:
        ref_ids = [row["fields"]["refdata_entity_id"] for row in refdata_rows]
        entities = (
            RefdataEntity.query.filter(RefdataEntity.id.in_(ref_ids))
            .with_entities(RefdataEntity.id, RefdataEntity.entity_type, RefdataEntity.entity_id)
            .all()
        )
        entity_map = {entity_id: (entity_type, entity_key) for entity_id, entity_type, entity_key in entities}
        for row in refdata_rows:
            ref_id = row["fields"]["refdata_entity_id"]
            entity_type, entity_key = entity_map.get(ref_id, ("", None))
            row["fields"]["entity_type"] = entity_type
            row["fields"]["entity_id"] = entity_key

    return {
        "filters": {
            "database_version_id": database_version_id or "",
            "year": year or "",
            "name_search": name_search or "",
        },
        "refdata_years": refdata_years,
        "refdata_rows": refdata_rows,
        "max_rows": MAX_ROWS,
        "max_years": MAX_YEARS,
    }


def build_refdata_history_context(entity_type: str, args) -> dict[str, Any]:
    database_version_id = _parse_int(args.get("database_version_id"))
    year = _parse_int(args.get("year"))
    name_search = (args.get("name_search") or "").strip() or None

    if year is None:
        year = _get_current_year_number(database_version_id)

    refdata_query = (
        RefdataEntityYear.query.join(
            RefdataEntity, RefdataEntity.id == RefdataEntityYear.refdata_entity_id
        )
        .filter(RefdataEntity.entity_type == entity_type)
    )

    refdata_query = _apply_version_year(refdata_query, RefdataEntityYear, database_version_id, None, "year")

    if name_search:
        refdata_query = _apply_payload_search(refdata_query, RefdataEntityYear.payload, name_search)

    refdata_years = _get_years_for_query(refdata_query, RefdataEntityYear, "year", year)

    key_rows = (
        refdata_query.with_entities(RefdataEntity.ref_uuid)
        .distinct()
        .order_by(RefdataEntity.ref_uuid.asc())
        .limit(MAX_ROWS)
        .all()
    )
    refdata_rows = []
    if key_rows:
        ref_uuids = [row[0] for row in key_rows]
        records = refdata_query
        if refdata_years:
            records = records.filter(RefdataEntityYear.year.in_(refdata_years))
        records = records.filter(RefdataEntity.ref_uuid.in_(ref_uuids)).all()

        rows_map = {
            ref_uuid: {
                "fields": {"ref_uuid": ref_uuid},
                "cells": {},
            }
            for (ref_uuid,) in key_rows
        }

        for record in records:
            row = rows_map.get(record.refdata_entity.ref_uuid)
            if not row:
                continue
            year_key = record.year
            row["cells"].setdefault(year_key, []).append(
                {
                    "database_version_id": record.database_version_id,
                    "payload": record.payload,
                }
            )
        refdata_rows = list(rows_map.values())

    return {
        "filters": {
            "database_version_id": database_version_id or "",
            "year": year or "",
            "name_search": name_search or "",
        },
        "entity_type": entity_type,
        "entity_label": REFDATA_LABELS.get(entity_type, entity_type),
        "refdata_years": refdata_years,
        "refdata_rows": refdata_rows,
        "max_rows": MAX_ROWS,
        "max_years": MAX_YEARS,
    }
