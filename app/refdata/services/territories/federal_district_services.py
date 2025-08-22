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
from app.refdata.services.common_services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.refdata.services.common_services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@no_autoflush
def get_federal_district_list(
    page, 
    per_page, 
    federal_district_filter=None, 
    sort_by="id", 
    sort_dir="asc"
):
    """Получает список федеральных округов с пагинацией, фильтрацией и сортировкой."""

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

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_federal_district_service(data, user):
    """Обновление данных по федеральным округам."""

    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    updated_ids = []

    # Итерация по входным данным (валидация/применение)
    with db.session.no_autoflush:
        for record in data:
            federal_district_id = record.get("id")
            name = record.get("name", "").strip()
            name_full = record.get("name_full", "").strip()
            name_abr = record.get("name_abr", "").strip()

            if not name:
                raise ValueError("Поле 'name' обязательно для заполнения.")
            
            obj = db.session.get(FederalDistrict, federal_district_id)
            if not obj:
                raise ValueError(f"Запись с ID «{federal_district_id}» не найдена.")
            
            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (FederalDistrict.query
                     .filter(FederalDistrict.name == name,
                             FederalDistrict.id != federal_district_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")
            
            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            if name_full != (obj.name_full or None):
                changes["Полное наименование"] = f"{_dash(obj.name_full)} → {_dash(name_full)}"
                obj.name_full = name_full

            if name_abr != (obj.name_abr or None):
                changes["Сокращенное наименование"] = f"{_dash(obj.name_abr)} → {_dash(name_abr)}"
                obj.name_abr = name_abr

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен федеральный округ: {name}", f"Изменения = {changes}")
                updated_ids.append(federal_district_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по федеральным округам", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по федеральным округам не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения федерального округа (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении федеральных округов", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_federal_district_service(data, user):
    """Создание/обновление федерального округа"""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")
    
    log_to_db(user, "Получены данные для добавления/обновления федеральных округов", f"Кол-во записей: {len(data)}")

    created_ids = []
    updated_count = 0

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                federal_district_id = record.get("id")
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                name_abr = (record.get("name_abr") or "").strip()

                if not name or not name_full or name_abr is None:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'name_abr'.")

                #----- ОБНОВЛЕНИЕ-----
                if federal_district_id:
                    obj = _locked_get(FederalDistrict, federal_district_id)
                    if not obj:
                        log_to_db(user, "Ошибка обновления федерального округа", f"Запись с ID={federal_district_id} не найдена")
                        raise ValueError(f"Запись с ID {federal_district_id} не найдена.")

                    # Уникальность name — только если меняется
                    if (obj.name or "") != name:
                        dup = (FederalDistrict.query
                               .filter(FederalDistrict.name == name,
                                       FederalDistrict.id != federal_district_id)
                               .with_for_update().first())
                        if dup:
                            raise ValueError(f"Запись с именем «{name}» уже существует.")

                    изменения = {}

                    if (obj.name or "") != name:
                        изменения["Наименование"] = f"{_dash(obj.name)} → {name}"
                        obj.name = name

                    if (obj.name_full or "") != name_full:
                        изменения["Полное наименование"] = f"{_dash(obj.name_full)} → {_dash(name_full)}"
                        obj.name_full = name_full or None

                    if (obj.name_abr or "") != name_abr:
                        изменения["Сокращенное наименование"] = f"{_dash(obj.name_abr)} → {_dash(name_abr)}"
                        obj.name_funame_abrll = name_abr or None

                    if изменения:
                        updated_count += 1
                        log_to_db(user, "Обновлен федеральный округ", f"Наименование = {name}. Изменения = {изменения}")

                #----- СОЗДАНИЕ-----
                else:
                    # Уникальность name при создании
                    dup = (FederalDistrict.query
                           .filter(FederalDistrict.name == name)
                           .with_for_update().first())
                    if dup:
                        raise ValueError(f"Запись с именем «{name}» уже существует.")

                    obj = FederalDistrict(
                        name=name,
                        name_full=name_full or None,
                        name_abr=name_abr or None,
                    )
                    db.session.add(obj)
                    db.session.flush()  # получить id без полного коммита
                    created_ids.append(obj.id)

                    log_to_db(
                        user,
                        "Создан федеральный округ",
                        f"Наименование: {name}; Полное наименование: {_dash(name_full)}; Сокращенное наименование: {name_abr}"
                    )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        # Итоговый лог
        tail = []
        if created_ids:
            tail.append(f"создано: {len(created_ids)} (id: {created_ids})")
        if updated_count:
            tail.append(f"обновлено: {updated_count}")
        log_to_db(user, "Сохранение федерального округа завершено", "; ".join(tail) or "Изменений нет")

        if len(created_ids) == 1:
            return created_ids[0]
        if created_ids:
            return created_ids
        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения федерального округа (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения федерального округа", str(e))
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {e}")


@no_autoflush
def delete_federal_district_service(ids, user):
    """Удаляет записи федеральных округов по переданным ID."""
    
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление федеральных округов", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for fd_id in ids:
        try:
            federal_district_id = int(fd_id)
        except (TypeError, ValueError):
            invalid.append(fd_id)
            log_to_db(user, "Ошибка удаления федерального округа", f"Некорректный ID: {fd_id}")
            continue

        obj = _locked_get(FederalDistrict, federal_district_id)
        if obj:
            name = obj.name or f"ID={federal_district_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(user, "Удален федеральный округ", f"{name}")
        else:
            not_found.append(federal_district_id)
            log_to_db(user, "Ошибка удаления федерального округа", f"Федеральный округ с ID={federal_district_id} не найден.")

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

        log_to_db(user, "Результат удаления федеральных округов", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления федеральных округов", str(e))
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_federal_district_service(file, user):
    """Импортирует данные федеральных округов из Excel-файла в базу данных с проверкой отсутствия данных для обновления."""
    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'name_abr'}
        if not required_columns.issubset(data.columns):
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы: 'name', 'name_full', 'name_abr'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'name_abr'])

        if data.empty:
            raise ValueError("Файл не содержит данных для обновления.")

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
            raise ValueError("Данные для обновления отсутствуют.")

        # Сохранение изменений в базе данных
        db.session.commit()

        # Логирование результата
        log_to_db(
            user,
            "Импорт завершён",
            f"Обновлено записей: {updated_count}, добавлено новых: {added_count}, удалено лишних: {deleted_count}"
        )
        return {
            "updated": updated_count,
            "added": added_count,
            "deleted": deleted_count
        }
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (IntegrityError)", str(e))
        raise ValueError("Ошибка целостности данных при импорте. Проверьте уникальность записей.")
    except ValueError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (ValueError)", str(e))
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_federal_district_service(
        user, 
        federal_district_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """Экспортирует данные ФО в Excel и возвращает бинарный поток."""

    # Нормализация входов
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    sort_by = (sort_by or "id").lower()
    allowed_sort = {"id", "name", "name_full", "name_abr"}
    if sort_by not in allowed_sort:
        sort_by = "id"

    fdf = (federal_district_filter or "").strip()

    log_to_db(user, "Начата выгрузка таблицы федеральных округов из базы данных")
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"federal_district_filter={fdf!r}, "
            f"sort_by={sort_by}, sort_dir={sort_dir}"
        ),
    )

    # Базовый запрос
    query = (
        FederalDistrict.query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
    )

    # Фильтрация по названию/полю name_full
    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%")
            )
        )

    # Фильтрация
    if fdf:
        like = f"%{fdf}%"
        query = query.filter(or_(FederalDistrict.name.ilike(like),
                         FederalDistrict.name_full.ilike(like),
                         FederalDistrict.name_abr.ilike(like)))

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

    items = query.all()

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": o.name or "",
            "Полное наименование": o.name_full or "",
            "Сокращенное наименование": o.name_abr or "",
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
    log_to_db(user, "Экспорт таблицы федеральных округов в Excel завершен", f"Экспортировано записей: {len(data)}")
    return output
