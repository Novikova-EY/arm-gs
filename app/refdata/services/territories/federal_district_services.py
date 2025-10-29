"""Сервисный модуль: Федеральные округа."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.territories.federal_district_model import FederalDistrict

# Сервисы
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru

# Фильтрация по версиям
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create


def federal_district_query(
    federal_district_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки списка федеральных округов с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name","name_full","name_abr"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    federal_district_id = _to_int_or_none(federal_district_filter)

    # Базовый запрос
    query = (
        FederalDistrict.query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
    )
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, FederalDistrict)

    # Фильтрация
    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%")
            )
        )

    if federal_district_id is not None:
        query = query.filter(FederalDistrict.id == federal_district_id)

    # Сортировка
    if sort_by == "name":
        sort_col = FederalDistrict.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "name_full":
        sort_col = FederalDistrict.name_full
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "name_abr":
        sort_col = FederalDistrict.name_abr
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    else:  # "id" (по умолчанию)
        sort_col = FederalDistrict.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)

    return query


@no_autoflush
def get_federal_district_list(
    page, 
    per_page, 
    federal_district_filter=None, 
    sort_by="id", 
    sort_dir="asc"
):
    """ Получает список федеральных округов с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = federal_district_query(
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_federal_district_service(data, user):
    """Обновление данных по федеральным округам."""

    if not isinstance(data, list) or not data:
        raise ValueError(f"Данные должны быть предоставлены в виде непустого списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка федеральных округов", 
        f"{data}", 
        entity_type="federal_district")

    # Итерация по входным данным (валидация/применение)
    with db.session.no_autoflush:
        for record in data:
            federal_district_id = record.get("federal_district_id")
            name = record.get("name", "").strip()
            name_full = record.get("name_full", "").strip()
            name_abr = record.get("name_abr", "").strip()

            if not name:
                raise ValueError(f"Поле 'name' обязательно для заполнения.")
            
            obj = db.session.get(FederalDistrict, federal_district_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{federal_district_id}» не найдена.", 
                    entity_type="federal_district", 
                    entity_id=federal_district_id)
                raise ValueError(f"Запись с ID «{federal_district_id}» не найдена.")
            
            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (FederalDistrict.query
                     .filter(FederalDistrict.name == name,
                             FederalDistrict.id != federal_district_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")
            
            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "federal_district"))
                obj.name = name

            if name_full != (obj.name_full or None):
                old_val = obj.name_full or "не указано"
                new_val = name_full or "не указано"
                changes.append(f"Полное наименование: {old_val} → {new_val}")
                obj.name_full = name_full

            if name_abr != (obj.name_abr or None):
                old_val = obj.name_abr or "не указано"
                new_val = name_abr or "не указано"
                changes.append(f"Сокращенное наименование: {old_val} → {new_val}")
                obj.name_abr = name_abr

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен федеральный округ: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="federal_district", 
                    entity_id=federal_district_id)  
                updated_ids.append(federal_district_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по федеральным округам", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", entity_type="federal_district")
        else:
            log_to_db(user, "Изменений по федеральным округам не обнаружено", "", entity_type="federal_district")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения федерального округа (уникальность/целостность)", str(e, entity_type="federal_district"))
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении федеральных округов", str(e, entity_type="federal_district"))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_federal_district_service(data, user):
    """Создание новой записи: федеральный округ"""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")
    
    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                name_abr = (record.get("name_abr") or "").strip()

                # Проверка на наличие необходимых данных
                if not name or not name_full or not name_abr:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="federal_district")
                    raise ValueError(f"Каждая запись должна содержать 'name', 'name_full' и 'name_abr'. Данные: {record}")

                # Проверяем уникальность name
                dup = (FederalDistrict.query
                        .filter(FederalDistrict.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full
                dup_full = (FederalDistrict.query
                        .filter(FederalDistrict.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Проверяем уникальность name_abr
                dup_abr = (FederalDistrict.query
                        .filter(FederalDistrict.name_abr == name_abr)
                        .with_for_update().first())
                if dup_abr:
                    raise ValueError(f"Запись с сокращенным наименованием «{name_abr}» уже существует.")
                
                # Создаем новую запись
                obj = FederalDistrict(
                    name=name,
                    name_full=name_full or None,
                    name_abr=name_abr,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создан федеральный округ",
                    (
                        f"Наименование: {name};"
                        f"Полное наименование: {_dash(name_full)};"
                        f"Сокращенное наименование: {_dash(name_abr)}", 
                    ),
                    entity_type="federal_district",
                    entity_id=obj.id)

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового федерального округа. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e, entity_type="federal_district"))
        raise ValueError(f"Ошибка сохранения нового федерального округа. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового федерального округа", str(e, entity_type="federal_district"))
        raise ValueError(f"Ошибка сохранения нового федерального округа: {e}")


@no_autoflush
def delete_federal_district_service(ids, user):
    """Удаляет записи федеральных округов по переданным ID."""
    
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(user, "Удаление федеральных округов", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for fd_id in ids:
        try:
            federal_district_id = int(fd_id)
        except (TypeError, ValueError):
            invalid.append(fd_id)
            log_to_db(
                user, 
                "Ошибка удаления федерального округа", 
                f"Некорректный ID: {fd_id}",
                entity_type="federal_district",
                entity_id=fd_id)
            continue

        obj = _locked_get(FederalDistrict, federal_district_id)
        if obj:
            name = obj.name or f"ID={federal_district_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user,
                "Удален федеральный округ", 
                f"{name}",
                entity_type="federal_district",
                entity_id=federal_district_id)
        else:
            not_found.append(federal_district_id)
            log_to_db(
                user, 
                "Ошибка удаления федерального округа", 
                f"Федеральный округ с ID={federal_district_id} не найден.",
                entity_type="federal_district",
                entity_id=federal_district_id)

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
            "Ошибка удаления федеральных округов", 
            str(e, entity_type="federal_district"),
            entity_id=federal_district_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_federal_district_service(file, user):
    """Импортирует данные федеральных округов из Excel-файла в базу данных с проверкой отсутствия данных для обновления."""
    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'name_abr'}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы: 'name', 'name_full', 'name_abr'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'name_abr'])

        if data.empty:
            raise ValueError(f"Файл не содержит данных для обновления.")

        # Счетчики для статистики
        updated_count = 0
        added_count = 0
        deleted_count = 0

        # Список всех имен из загружаемой таблицы
        imported_names = set(data['name'].str.strip())

        # Получение всех текущих записей из базы данных
        existing_records = db.session.query(FederalDistrict).all()
        existing_names = {record.name for record in existing_records}

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(FederalDistrict).filter(FederalDistrict.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            federal_district = db.session.query(FederalDistrict).filter_by(name=row['name'].strip()).first()

            if federal_district:
                # Проверяем, есть ли изменения в записи
                if (
                    federal_district.name_full != row['name_full'].strip()
                    or federal_district.name_abr != row['name_abr'].strip()
                ):
                    federal_district.name_full = row['name_full'].strip()
                    federal_district.name_abr = row['name_abr'].strip()
                    updated_count += 1
            else:
                # Добавляем новую запись
                new_record = FederalDistrict(
                    name=row['name'].strip(),
                    name_full=row['name_full'].strip(),
                    name_abr=row['name_abr'].strip()
                )
                db.session.add(new_record)
                added_count += 1

        # Если нет изменений, данных для обновления нет
        if updated_count == 0 and added_count == 0 and deleted_count == 0:
            raise ValueError(f"Данные для обновления отсутствуют.")

        # Сохранение изменений в базе данных
        db.session.commit()

        # Логирование результата
        log_to_db(
            user,
            "Импорт завершен",
            f"Обновлено записей: {updated_count}, добавлено новых: {added_count}, удалено лишних: {deleted_count}"
        )
        return {
            "updated": updated_count,
            "added": added_count,
            "deleted": deleted_count
        }
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (IntegrityError)", str(e, entity_type="federal_district"))
        raise ValueError(f"Ошибка целостности данных при импорте. Проверьте уникальность записей.")
    except ValueError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (ValueError)", str(e, entity_type="federal_district"))
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных", str(e, entity_type="federal_district"))
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_federal_district_service(
        user, 
        federal_district_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные ФО в Excel. """

    log_to_db(user, "Начата выгрузка таблицы федеральных округов из базы данных", entity_type="federal_district")
    log_to_db(user, "Параметры экспорта",
        (
                f"Фильтр по столбцу: Наименование ФО = {federal_district_filter},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
    )

    # Базовый запрос
    query = federal_district_query(
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    items = query.all()

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
            "Полное наименование": _dash(o.name_full),
            "Сокращенное наименование": _dash(o.name_abr),
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы федеральных округов в Excel",
              f"Записей для экспорта: {len(data)}")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Федеральные округа"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы федеральных округов в Excel завершен", f"Экспортировано записей: {len(data)}", entity_type="federal_district")
    return output