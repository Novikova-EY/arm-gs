"""Сервисный модуль: Типы агрегатов."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq, 
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru

# Фильтрация по версиям
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create


def station_type_query(
        station_type_filter=None, 
        sort_by="display_order", 
        sort_dir="asc"):
    """ Базовый запрос для выборки типов электростанций с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = StationType.query.filter(StationType.id.isnot(None), StationType.id > 0)
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, StationType)

    # Фильтрация
    if station_type_filter:
        query = query.filter(StationType.name.ilike(f"%{station_type_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = StationType.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "display_order":
        # Сортировка по порядку отображения, значения NULL в конце
        if sort_dir == "desc":
            query = query.order_by(
                (StationType.display_order.is_(None)),
                StationType.display_order.desc(),
            )
        else:
            query = query.order_by(
                (StationType.display_order.is_(None)),
                StationType.display_order.asc(),
            )
    else:
        # sort_by == "id" или "number"
        sort_col = StationType.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_station_type_list(
    page, 
    per_page, 
    station_type_filter=None, 
    sort_by="display_order", 
    sort_dir="asc"):
    """ Получает список типов электростанций с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = station_type_query(
        station_type_filter=station_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_station_type_service(data, user):
    """ Обновление данных по типам электростанций """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка типов электростанций", 
        f"{data}", 
        entity_type="station_type")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            station_type_id = record.get("station_type_id")
            name = (record.get("name") or "").strip()
            display_order = record.get("display_order")

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="station_type",
                    entity_id=station_type_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(StationType, station_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{station_type_id}» не найдена.", 
                    entity_type="station_type", 
                    entity_id=station_type_id)
                raise ValueError(f"Запись с ID «{station_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(StationType.query, StationType)
                     .filter(StationType.name == name,
                             StationType.id != station_type_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            # Проверка уникальности display_order
            if display_order is not None and display_order != obj.display_order:
                q_display = (
                    apply_version_filter(StationType.query, StationType)
                    .filter(
                        StationType.display_order == display_order,
                        StationType.id != station_type_id,
                    )
                )
                if q_display.first():
                    raise ValueError(
                        f"Запись с порядком отображения «{display_order}» уже существует."
                    )

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "station_type"))
                obj.name = name

            if display_order != obj.display_order:
                old_val = obj.display_order if obj.display_order is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(f"Порядок отображения: {old_val} → {new_val}")
                obj.display_order = display_order

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен тип электростанции: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="station_type", 
                    entity_id=station_type_id)
                updated_ids.append(station_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам электростанций", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="station_type",
                entity_id=station_type_id)
        else:
            log_to_db(user, "Изменений по типам электростанций не обнаружено", "", entity_type="station_type")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения типов электростанций (уникальность/целостность)", 
            str(e), 
            entity_type="station_type",
            entity_id=station_type_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов электростанций", 
            str(e), 
            entity_type="station_type",
            entity_id=station_type_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_station_type_service(data, user):
    """Создание новой записи: тип электростанции"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()
                display_order = record.get("display_order")
                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="station_type")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (apply_version_filter(StationType.query, StationType)
                       .filter(StationType.name == name)
                       .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Проверка уникальности display_order при создании
                if display_order is not None:
                    dup_display = (
                        apply_version_filter(StationType.query, StationType)
                        .filter(StationType.display_order == display_order)
                        .with_for_update()
                        .first()
                    )
                    if dup_display:
                        raise ValueError(
                            f"Запись с порядком отображения «{display_order}» уже существует."
                        )

                obj = StationType(name=name, display_order=display_order)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан тип электростанции", 
                    f"Наименование: {name}",
                    entity_type="station_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "station_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового типа электростанции", 
            str(e), 
            entity_type="station_type")
        raise ValueError(f"Ошибка сохранения нового типа электростанции: {e}") from e


@no_autoflush
def delete_station_type_service(ids, user):
    """Удаляет записи типов электростанций по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов электростанций", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="station_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            station_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления типов электростанций", 
                f"Некорректный ID: {ft_id}", 
                entity_type="station_type",
                entity_id=ft_id)
            continue

        obj = _locked_get(StationType, station_type_id)
        if obj:
            name = obj.name or f"ID={station_type_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален тип электростанции", 
                f"{name}", 
                entity_type="station_type", 
                entity_id=station_type_id)
        else:
            not_found.append(station_type_id)
            log_to_db(
                user, 
                "Ошибка удаления типов электростанций", 
                f"Тип агрегата с ID={station_type_id} не найден.", 
                entity_type="station_type", 
                entity_id=station_type_id)

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено: {successful_deletes}"]
        if deleted_names:
            parts.append(f"Наименование: {deleted_names}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления типов электростанций", 
            str(e), 
            entity_type="station_type",
            entity_id=station_type_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_station_type_service(
    user,
    station_type_filter=None,
    sort_by="display_order",
    sort_dir="asc",):
    """ Экспортирует данные типов агрегатов в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы типов электростанций. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа электростанции = {station_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="station_type"
    )

    # Базовый запрос
    query = station_type_query(
        station_type_filter=station_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="station_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы типов электростанций в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="station_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы электростанций"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы типов агрегатов в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="station_type")
    return output


def repair_station_types_sequence_hard(user: str) -> None:
    """
    Выравнивает sequence для refdata.station_types.id под MAX(id)
    в ОТДЕЛЬНОЙ транзакции (engine.begin), чтобы ее не откатил внешний rollback().
    Работает и для SERIAL, и для IDENTITY, т.к. имя берем через pg_get_serial_sequence.
    """
    try:
        with db.engine.begin() as conn:  # <— отдельная транзакция, гарантированный commit
            seq_name = conn.execute(
                text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                {"tbl": f"{SCHEMA_REFDATA}.station_types", "col": "id"}
            ).scalar()
            if not seq_name:
                raise RuntimeError("pg_get_serial_sequence вернул NULL для refdata.station_types(id)")

            max_id = conn.execute(
                text(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA_REFDATA}.station_types")
            ).scalar()

            # true => следующий nextval будет max_id + 1
            conn.execute(
                text("SELECT setval(:seq::regclass, :new_val, true)"),
                {"seq": seq_name, "new_val": int(max_id)}
            )

        log_to_db(user,
                  "Ремонт последовательности station_types (HARD) выполнен",
                  f"seq={seq_name}, max_id={max_id}",
                  entity_type="station_type")

    except Exception as e:
        log_to_db(user,
                  "Не удалось выполнить ремонт последовательности station_types (HARD)",
                  str(e),
                  entity_type="station_type")
