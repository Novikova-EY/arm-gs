"""Сервисный модуль: Виды топлива."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.fuels.fuel_type_model import FuelType

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


def _invalidate_fuel_type_caches() -> None:
    """
    Инвалидирует кэши, используемые для выпадающих списков и get-сервисов FuelType.
    Важно: без этого новые/изменённые виды топлива могут не появляться на страницах,
    которые используют in-memory кэш (например, refdata/fuel).
    """
    # Локальные импорты, чтобы избежать возможных циклических зависимостей при старте приложения
    try:
        from app.common.services.choices_cache_service import choices_cache

        # По умолчанию ключ = model_class.__name__.lower() => "fueltype"
        choices_cache.invalidate_cache(FuelType.__name__.lower())
    except Exception:
        # Кэш — оптимизация; если не получилось очистить, не роняем бизнес-операцию.
        pass

    try:
        from app.common.services.get_services.fuels import fuel_type_get_services

        fuel_type_get_services.get_fuel_type_list_full.cache_clear()
        fuel_type_get_services.get_fuel_type_list.cache_clear()
    except Exception:
        pass


def fuel_type_query(
        fuel_type_filter=None, 
        topl_nazvl_filter=None,
        sort_by="display_order", 
        sort_dir="asc"):
    """ Базовый запрос для выборки видов топлива с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "topl_nazvl", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = FuelType.query.filter(FuelType.id.isnot(None), FuelType.id > 0)
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, FuelType)

    # Фильтрация
    if fuel_type_filter:
        query = query.filter(FuelType.name.ilike(f"%{fuel_type_filter}%"))
    if topl_nazvl_filter:
        query = query.filter(FuelType.topl_nazvl.ilike(f"%{topl_nazvl_filter}%"))
    # Сортировка
    if sort_by == "name":
        sort_col = FuelType.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "topl_nazvl":
        sort_col = FuelType.topl_nazvl
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "display_order":
        # Сортируем по порядку отображения, значения NULL в конце
        if sort_dir == "desc":
            query = query.order_by(
                (FuelType.display_order.is_(None)),
                FuelType.display_order.desc(),
            )
        else:
            query = query.order_by(
                (FuelType.display_order.is_(None)),
                FuelType.display_order.asc(),
            )
    else:
        # sort_by == "id" или "number"
        sort_col = FuelType.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query

@no_autoflush
def get_fuel_type_list(
    page, 
    per_page, 
    fuel_type_filter=None, 
    topl_nazvl_filter=None,
    sort_by="display_order", 
    sort_dir="asc"):
    """ Получает список видов топлива с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = fuel_type_query(
        fuel_type_filter=fuel_type_filter,
        topl_nazvl_filter=topl_nazvl_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_fuel_type_service(data, user):
    """ Обновление данных по видам топлива """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка видов топлива", 
        f"{data}",
        entity_type="fuel_type")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            fuel_type_id = record.get("fuel_type_id")
            name = (record.get("name") or "").strip()
            topl_nazvl = (record.get("topl_nazvl") or "").strip() or None
            display_order = record.get("display_order")

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="fuel_type",
                    entity_id=fuel_type_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(FuelType, fuel_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{fuel_type_id}» не найдена.", 
                    entity_type="fuel_type", 
                    entity_id=fuel_type_id)
                raise ValueError(f"Запись с ID «{fuel_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or "").strip():
                q = (apply_version_filter(FuelType.query, FuelType)
                     .filter(FuelType.name == name,
                             FuelType.id != fuel_type_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            # Проверка уникальности display_order
            if display_order is not None and display_order != obj.display_order:
                q_display = (
                    apply_version_filter(FuelType.query, FuelType)
                    .filter(
                        FuelType.display_order == display_order,
                        FuelType.id != fuel_type_id,
                    )
                )
                if q_display.first():
                    raise ValueError(
                        f"Запись с порядком отображения «{display_order}» уже существует."
                    )

            changes = []

            if name != (obj.name or "").strip():
                changes.append(format_field_change("name", obj.name or "не указано", name, "fuel_type"))
                obj.name = name

            if topl_nazvl != obj.topl_nazvl:
                changes.append(
                    format_field_change(
                        "topl_nazvl",
                        obj.topl_nazvl or "не указано",
                        topl_nazvl or "не указано",
                        "fuel_type",
                )
                )
                obj.topl_nazvl = topl_nazvl

            if display_order != obj.display_order:
                old_val = obj.display_order if obj.display_order is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(
                    f"Порядок отображения: {old_val} → {new_val}"
                )
                obj.display_order = display_order

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен вид топлива: {name}",
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="fuel_type", 
                    entity_id=fuel_type_id)
                updated_ids.append(fuel_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()
        _invalidate_fuel_type_caches()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по видам топлива", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="fuel_type")
        else:
            log_to_db(
                user, 
                "Изменений по видам топлива не обнаружено", 
                "", 
                entity_type="fuel_type")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения видов топлива (уникальность/целостность)", 
            str(e), 
            entity_type="fuel_type")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении видов топлива", 
            str(e), 
            entity_type="fuel_type")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_fuel_type_service(data, user):
    """Создание новой записи: вид топлива"""
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
                        entity_type="fuel_type")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (apply_version_filter(FuelType.query, FuelType)
                       .filter(FuelType.name == name)
                       .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Проверка уникальности display_order при создании
                if display_order is not None:
                    dup_display = (
                        apply_version_filter(FuelType.query, FuelType)
                        .filter(FuelType.display_order == display_order)
                        .with_for_update()
                        .first()
                    )
                    if dup_display:
                        raise ValueError(
                            f"Запись с порядком отображения «{display_order}» уже существует."
                        )

                obj = FuelType(name=name, display_order=display_order)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан вид топлива", 
                    f"Наименование: {name}",
                    entity_type="fuel_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        _invalidate_fuel_type_caches()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "fuel_types")
        _do_insert()
        _commit_with_retry()
        _invalidate_fuel_type_caches()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового вида топлива", 
            str(e), 
            entity_type="fuel_type")
        raise ValueError(f"Ошибка сохранения нового вида топлива: {e}") from e


@no_autoflush
def delete_fuel_type_service(ids, user):
    """Удаляет записи видов топлива по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление видов топлива", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="fuel_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            fuel_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления видов топлива", 
                f"Некорректный ID: {ft_id}", 
                entity_type="fuel_type",
                entity_id=ft_id)
            continue

        obj = _locked_get(FuelType, fuel_type_id)
        if obj:
            name = obj.name or f"ID={fuel_type_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален вид топлива", 
                f"{name}", 
                entity_type="fuel_type", 
                entity_id=fuel_type_id)
        else:
            not_found.append(fuel_type_id)
            log_to_db(
                user, 
                "Ошибка удаления видов топлива", 
                f"Вид топлива с ID={fuel_type_id} не найден.", 
                entity_type="fuel_type", 
                entity_id=fuel_type_id)

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()
        _invalidate_fuel_type_caches()

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
            "Ошибка удаления видов топлива", 
            str(e), 
            entity_type="fuel_type",
            entity_id=fuel_type_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_fuel_type_service(file, user):
    """Импортирует данные видов топлива из Excel-файла в базу данных."""

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fuel_type' not in data.columns:
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(FuelType).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fuel_types AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [FuelType(name=row['name']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        _invalidate_fuel_type_caches()
        log_to_db(user, "Импорт завершен", f"Импортировано записей: {len(records)}", entity_type="fuel_type")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e), entity_type="fuel_type")
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_fuel_type_service(
    user,
    fuel_type_filter=None,
    topl_nazvl_filter=None,
    sort_by="display_order",
    sort_dir="asc",):
    """ Экспортирует данные видов топлива в Excel. """

    log_to_db(user, "Начата выгрузка таблицы видов топлива из базы данных", entity_type="fuel_type")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование вида топлива = {fuel_type_filter},"
            f"Фильтр по столбцу: Наименование БД Топливо = {topl_nazvl_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ), entity_type="fuel_type"
    )

    # Базовый запрос
    query = fuel_type_query(
        fuel_type_filter=fuel_type_filter,
        topl_nazvl_filter=topl_nazvl_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}", entity_type="fuel_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
            "Наименование БД Топливо": _dash(o.topl_nazvl),
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы видов топлива в Excel",
              f"Записей для экспорта: {len(data)}", entity_type="fuel_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    sheet_name = "Виды топлива"

    def _write_excel(buffer, engine_name):
        with pd.ExcelWriter(buffer, engine=engine_name) as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            ws = writer.sheets[sheet_name]

            # Автоподбор ширины с аккуратным лимитом
            for i, col in enumerate(df.columns):
                max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
                ws.set_column(i, i, min(max_len + 2, 60))

    output = BytesIO()
    try:
        _write_excel(output, "xlsxwriter")
    except Exception as e:
        # Резервный engine на случай проблем с xlsxwriter
        log_to_db(
            user,
            "Переход на openpyxl при экспорте видов топлива",
            f"xlsxwriter error: {e}",
            entity_type="fuel_type",
        )
        output = BytesIO()
        _write_excel(output, "openpyxl")

    output.seek(0)
    log_to_db(user, "Экспорт таблицы видов топлива в Excel завершен", f"Экспортировано записей: {len(data)}", entity_type="fuel_type")
    return output


def repair_fuel_types_sequence_hard(user: str) -> None:
    """
    Выравнивает sequence для refdata.fuel_types.id под MAX(id)
    в ОТДЕЛЬНОЙ транзакции (engine.begin), чтобы её не откатил внешний rollback().
    Работает и для SERIAL, и для IDENTITY, т.к. имя берём через pg_get_serial_sequence.
    """
    try:
        with db.engine.begin() as conn:  # <— отдельная транзакция, гарантированный commit
            seq_name = conn.execute(
                text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                {"tbl": f"{SCHEMA_REFDATA}.fuel_types", "col": "id"}
            ).scalar()
            if not seq_name:
                raise RuntimeError("pg_get_serial_sequence вернул NULL для refdata.fuel_types(id)")

            max_id = conn.execute(
                text(f"SELECT COALESCE(MAX(id), 0) FROM {SCHEMA_REFDATA}.fuel_types")
            ).scalar()

            # true => следующий nextval будет max_id + 1
            conn.execute(
                text("SELECT setval(:seq::regclass, :new_val, true)"),
                {"seq": seq_name, "new_val": int(max_id)}
            )

        log_to_db(user,
                  "Ремонт последовательности fuel_types (HARD) выполнен",
                  f"seq={seq_name}, max_id={max_id}",
                  entity_type="fuel_type")

    except Exception as e:
        log_to_db(user,
                  "Не удалось выполнить ремонт последовательности fuel_types (HARD)",
                  str(e),
                  entity_type="fuel_type")
