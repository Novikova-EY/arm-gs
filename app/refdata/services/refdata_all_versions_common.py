# -*- coding: utf-8 -*-
"""Общие утилиты для синхронизации справочников по всем версиям БД (ref_uuid)."""

import uuid as uuid_lib

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_REFDATA


def all_database_version_ids_for_refdata() -> list[int]:
    """Все зарегистрированные id версий БД."""
    return [
        v.id
        for v in DatabaseVersion.query.order_by(DatabaseVersion.version_number).all()
        if v.id is not None
    ]


def fk_id_for_version(model_cls, source_pk_id: int | None, target_version_id: int) -> int | None:
    """
    Находит id строки с тем же ref_uuid в указанной версии БД,
    по исходному pk записи из текущей (или любой) версии.
    """
    if source_pk_id is None:
        return None
    src = db.session.get(model_cls, int(source_pk_id))
    if not src:
        raise ValueError(f"Связанная запись {model_cls.__name__} id={source_pk_id} не найдена.")
    ru = getattr(src, "ref_uuid", None)
    if not ru:
        return int(source_pk_id)
    tgt = (
        filter_by_explicit_db_version(model_cls.query, model_cls, target_version_id)
        .filter(model_cls.ref_uuid == ru)
        .first()
    )
    if not tgt:
        raise ValueError(
            f"В версии БД id={target_version_id} нет записи {model_cls.__name__} с ref_uuid={ru}."
        )
    return int(tgt.id)


def tmp_placeholders(prefix: str, sid: str, obj_id: int) -> str:
    """Временное значение для обхода уникальных ограничений при массовом переименовании."""
    return f"__{prefix}_{sid}_{obj_id}__"


def integrity_retry_commit(do_writes, seq_table: str):
    """Коммит с одним повтором после IntegrityError и выравниванием sequence."""
    try:
        do_writes()
        _commit_with_retry()
    except IntegrityError:
        db.session.rollback()
        if seq_table:
            quick_fix_seq(SCHEMA_REFDATA, seq_table)
        do_writes()
        _commit_with_retry()


def new_shared_ref_uuid() -> str:
    return str(uuid_lib.uuid4())

# === all_versions_common_helpers start ===
from collections import defaultdict


def _all_versions_has_value(value) -> bool:
    return value not in (None, "")


def add_all_versions_records(
    *,
    data,
    user,
    model_cls,
    entity_type: str,
    normalize_record,
    resolve_for_version,
    unique_fields: list[str] | tuple[str, ...],
    create_instance=None,
    after_commit=None,
):
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    version_ids = all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — нельзя выполнить операцию «во всех версиях»."
        )

    normalized = [normalize_record(record) for record in data]

    def _do_writes():
        planned = []
        seen: dict[int, dict[str, set]] = {
            vid: {field: set() for field in unique_fields}
            for vid in version_ids
        }
        with db.session.no_autoflush:
            for clean in normalized:
                shared_ref = new_shared_ref_uuid()
                for vid in version_ids:
                    final = resolve_for_version(clean, vid)
                    for field in unique_fields:
                        value = final.get(field)
                        if not _all_versions_has_value(value):
                            continue
                        if value in seen[vid][field]:
                            raise ValueError(
                                f"В версии БД id={vid} значение поля «{field}» уже присутствует в текущем пакете сохранения."
                            )
                        seen[vid][field].add(value)
                        dup = (
                            filter_by_explicit_db_version(model_cls.query, model_cls, vid)
                            .filter(getattr(model_cls, field) == value)
                            .with_for_update()
                            .first()
                        )
                        if dup:
                            raise ValueError(
                                f"В версии БД id={vid} значение поля «{field}» уже занято."
                            )
                    planned.append((vid, final, shared_ref))

            for vid, final, shared_ref in planned:
                obj = create_instance(final) if create_instance else model_cls(**final)
                obj.ref_uuid = shared_ref
                obj.database_version_id = vid
                db.session.add(obj)
                db.session.flush()
                log_to_db(
                    user,
                    "Создана запись во всех версиях БД",
                    f"Сущность: {entity_type}; версия БД id={vid}; ref_uuid={shared_ref}",
                    entity_type=entity_type,
                    entity_id=obj.id,
                )

    try:
        integrity_retry_commit(_do_writes, model_cls.__tablename__)
        if after_commit:
            after_commit()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка операции добавления во всех версиях БД",
            str(e),
            entity_type=entity_type,
        )
        raise ValueError(f"Ошибка сохранения записи во всех версиях: {e}") from e


def update_all_versions_records(
    *,
    data,
    user,
    model_cls,
    entity_type: str,
    pk_field: str,
    normalize_record,
    resolve_for_version,
    tracked_fields: list[str] | tuple[str, ...],
    unique_fields: list[str] | tuple[str, ...],
    temp_fields: list[str] | tuple[str, ...] = (),
    clear_fields: list[str] | tuple[str, ...] = (),
    apply_changes=None,
    after_commit=None,
):
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    normalized = [normalize_record(record) for record in data]
    version_batches: dict[int, list[dict]] = defaultdict(list)
    updated_ids: list[int] = []

    try:
        with db.session.no_autoflush:
            for clean in normalized:
                pk_value = clean.get(pk_field)
                anchor = db.session.get(model_cls, pk_value)
                if not anchor:
                    raise ValueError(f"Запись с ID «{pk_value}» не найдена.")
                if not getattr(anchor, "ref_uuid", None):
                    raise ValueError(
                        f"У записи id={pk_value} отсутствует ref_uuid: синхронизация между версиями невозможна."
                    )

                targets = (
                    model_cls.query
                    .filter(model_cls.ref_uuid == anchor.ref_uuid)
                    .order_by(model_cls.id)
                    .with_for_update()
                    .all()
                )
                if not targets:
                    raise ValueError(
                        f"Для записи id={pk_value} не найдены копии по ref_uuid={anchor.ref_uuid}."
                    )

                for obj in targets:
                    final = resolve_for_version(clean, obj.database_version_id)
                    version_batches[obj.database_version_id].append(
                        {
                            "obj": obj,
                            "final": final,
                            "before": {
                                field: getattr(obj, field, None)
                                for field in tracked_fields
                            },
                        }
                    )

            for version_id, items in version_batches.items():
                target_ids = [item["obj"].id for item in items]
                seen: dict[str, dict] = {field: {} for field in unique_fields}

                for item in items:
                    final = item["final"]
                    for field in unique_fields:
                        value = final.get(field)
                        if not _all_versions_has_value(value):
                            continue
                        if value in seen[field]:
                            raise ValueError(
                                f"В версии БД id={version_id} значение поля «{field}» повторяется в текущем пакете сохранения."
                            )
                        seen[field][value] = item["obj"].id

                for field in unique_fields:
                    values = [
                        item["final"].get(field)
                        for item in items
                        if _all_versions_has_value(item["final"].get(field))
                    ]
                    if not values:
                        continue
                    dup = (
                        filter_by_explicit_db_version(model_cls.query, model_cls, version_id)
                        .filter(
                            getattr(model_cls, field).in_(values),
                            ~model_cls.id.in_(target_ids),
                        )
                        .with_for_update()
                        .first()
                    )
                    if dup:
                        raise ValueError(
                            f"В версии БД id={version_id} значение поля «{field}» уже занято."
                        )

                if clear_fields:
                    for item in items:
                        for field in clear_fields:
                            if item["final"].get(field) != getattr(item["obj"], field, None):
                                setattr(item["obj"], field, None)
                    db.session.flush()

                if temp_fields:
                    for item in items:
                        obj = item["obj"]
                        for field in temp_fields:
                            if (
                                item["final"].get(field) != item["before"].get(field)
                                and _all_versions_has_value(item["final"].get(field))
                            ):
                                setattr(
                                    obj,
                                    field,
                                    tmp_placeholders(field, str(version_id), obj.id),
                                )
                    db.session.flush()

                for item in items:
                    obj = item["obj"]
                    final = item["final"]
                    before = item["before"]

                    if apply_changes:
                        apply_changes(obj, final)
                    else:
                        for field in tracked_fields:
                            setattr(obj, field, final.get(field))

                    changed = any(
                        before.get(field) != getattr(obj, field, None)
                        for field in tracked_fields
                    )
                    if changed:
                        updated_ids.append(obj.id)
                        log_to_db(
                            user,
                            "Обновлена запись во всех версиях БД",
                            f"Сущность: {entity_type}; версия БД id={version_id}; запись id={obj.id}",
                            entity_type=entity_type,
                            entity_id=obj.id,
                        )

            db.session.flush()

        _commit_with_retry()
        if after_commit:
            after_commit()
        return updated_ids
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка операции обновления во всех версиях БД",
            str(e),
            entity_type=entity_type,
        )
        raise ValueError(f"Ошибка сохранения записи во всех версиях: {e}") from e
# === all_versions_common_helpers end ===
