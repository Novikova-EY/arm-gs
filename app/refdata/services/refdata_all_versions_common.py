# -*- coding: utf-8 -*-
"""Общие утилиты для синхронизации справочников по всем версиям БД (ref_uuid)."""

import uuid as uuid_lib
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_REFDATA

# Кэш (model_name, source_pk, target_version_id) -> target_pk в рамках одной
# операции «во всех версиях». Без него каждая строка формы × каждая версия × каждый FK
# даёт отдельный SELECT (и log_to_db — отдельный commit).
_fk_id_cache: ContextVar[dict | None] = ContextVar("refdata_fk_id_cache", default=None)


@contextmanager
def fk_id_resolution_cache():
    """Включает кэш/батч-прогрев для fk_id_for_version на время операции."""
    token = _fk_id_cache.set({})
    try:
        yield
    finally:
        _fk_id_cache.reset(token)


def all_database_version_ids_for_refdata() -> list[int]:
    """Все зарегистрированные id версий БД."""
    return [
        v.id
        for v in DatabaseVersion.query.order_by(DatabaseVersion.version_number).all()
        if v.id is not None
    ]


def fk_id_for_version(model_cls, source_pk_id: int | None, target_version_id: int | None) -> int | None:
    """
    Находит id строки с тем же ref_uuid в указанной версии БД,
    по исходному pk записи из текущей (или любой) версии.

    При активном fk_id_resolution_cache() один раз подгружает все версии
    по ref_uuid и дальше отвечает из памяти.
    """
    if source_pk_id is None:
        return None
    if target_version_id is None:
        raise ValueError(
            f"Нельзя сопоставить {model_cls.__name__} с версией БД id=None: "
            "записи без версии не участвуют в синхронизации «во всех версиях»."
        )

    source_pk = int(source_pk_id)
    target_vid = int(target_version_id)
    cache = _fk_id_cache.get()
    cache_key = (model_cls.__name__, source_pk, target_vid)
    if cache is not None and cache_key in cache:
        return cache[cache_key]

    src = db.session.get(model_cls, source_pk)
    if not src:
        raise ValueError(f"Связанная запись {model_cls.__name__} id={source_pk_id} не найдена.")
    ru = getattr(src, "ref_uuid", None)
    if not ru:
        if cache is not None:
            cache[cache_key] = source_pk
        return source_pk

    if cache is not None:
        # Один SELECT по ref_uuid вместо отдельного запроса на каждую версию.
        copies = model_cls.query.filter(model_cls.ref_uuid == ru).all()
        for copy in copies:
            copy_vid = getattr(copy, "database_version_id", None)
            if copy_vid is None:
                continue
            cache[(model_cls.__name__, source_pk, int(copy_vid))] = int(copy.id)
        if cache_key not in cache:
            raise ValueError(
                f"В версии БД id={target_version_id} нет записи {model_cls.__name__} с ref_uuid={ru}."
            )
        return cache[cache_key]

    tgt = (
        filter_by_explicit_db_version(model_cls.query, model_cls, target_vid)
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


def _select_version_targets_for_update(anchor, targets: list) -> list:
    """
    Отбирает по одной копии на database_version_id для обновления «во всех версиях».

    Пропускает записи без версии. Если в одной версии несколько строк с одним
    ref_uuid (битые данные), выбирает копию по совпадению с якорем:
    сам якорь → то же name → новое name из формы → минимальный id.
    """
    by_version: dict[int, list] = defaultdict(list)
    for obj in targets:
        vid = getattr(obj, "database_version_id", None)
        if vid is None:
            continue
        by_version[vid].append(obj)

    selected = []
    anchor_name = getattr(anchor, "name", None)
    for vid in sorted(by_version.keys()):
        candidates = by_version[vid]
        if len(candidates) == 1:
            selected.append(candidates[0])
            continue

        chosen = None
        for obj in candidates:
            if obj.id == getattr(anchor, "id", None):
                chosen = obj
                break
        if chosen is None and anchor_name not in (None, ""):
            named = [obj for obj in candidates if getattr(obj, "name", None) == anchor_name]
            if named:
                chosen = min(named, key=lambda obj: obj.id)
        if chosen is None:
            chosen = min(candidates, key=lambda obj: obj.id)
        selected.append(chosen)
    return selected


# === all_versions_common_helpers start ===


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
    created_ids: list[int] = []
    created_refs: list[str] = []

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

            created_ids.clear()
            created_refs.clear()
            for vid, final, shared_ref in planned:
                obj = create_instance(final) if create_instance else model_cls(**final)
                obj.ref_uuid = shared_ref
                obj.database_version_id = vid
                db.session.add(obj)
                db.session.flush()
                created_ids.append(obj.id)
                if shared_ref not in created_refs:
                    created_refs.append(shared_ref)

    try:
        with fk_id_resolution_cache():
            integrity_retry_commit(_do_writes, model_cls.__tablename__)
        if created_ids:
            log_to_db(
                user,
                "Созданы записи во всех версиях БД",
                (
                    f"Сущность: {entity_type}; версий: {len(version_ids)}; "
                    f"создано строк: {len(created_ids)}; ref_uuid={', '.join(created_refs)}"
                ),
                entity_type=entity_type,
                entity_id=created_ids[0],
            )
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
    before_commit=None,
    after_commit=None,
):
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    normalized = [normalize_record(record) for record in data]
    version_batches: dict[int, list[dict]] = defaultdict(list)
    updated_ids: list[int] = []
    scheduled_obj_ids: set[int] = set()

    try:
        with fk_id_resolution_cache():
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
                    targets = _select_version_targets_for_update(anchor, targets)
                    if not targets:
                        raise ValueError(
                            f"Для записи id={pk_value} не найдены копии с заполненной "
                            f"версией БД по ref_uuid={anchor.ref_uuid}."
                        )

                    for obj in targets:
                        if obj.id in scheduled_obj_ids:
                            continue
                        scheduled_obj_ids.add(obj.id)
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
                                    f"В версии БД id={version_id} значение поля «{field}» "
                                    f"повторяется в текущем пакете сохранения: «{value}»."
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

                db.session.flush()

            if before_commit:
                before_commit()
            _commit_with_retry()

        if updated_ids:
            sample = ", ".join(str(i) for i in updated_ids[:20])
            more = "" if len(updated_ids) <= 20 else f" и ещё {len(updated_ids) - 20}"
            log_to_db(
                user,
                "Обновлены записи во всех версиях БД",
                (
                    f"Сущность: {entity_type}; обновлено строк: {len(updated_ids)}; "
                    f"ids=[{sample}{more}]"
                ),
                entity_type=entity_type,
                entity_id=updated_ids[0],
            )
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
