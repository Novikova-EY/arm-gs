from app.extensions import db
from app.logs.models.log_model import Log
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from app.logs.services.logging_service import log_to_db


def get_synchronous_area_list(page, per_page, synchronous_area_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ФО с пагинацией, фильтрацией и сортировкой."""
    # Фильтрация
    query = SynchronousArea.query

    if synchronous_area_filter:
        query = query.filter(
            or_(
                SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"),
            )
        )

    # Сортировка
    if sort_by in ["name"]:
        sort_field = getattr(SynchronousArea, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(SynchronousArea.id.desc() if sort_dir == "desc" else SynchronousArea.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


from sqlalchemy.exc import IntegrityError

def update_synchronous_area_service(data, user):
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    updated_count = added_count = no_change_count = deleted_count = 0

    # не даём автосбросу сработать на запросах/логах пока не закончим правки
    with db.session.no_autoflush:
        # лог можно оставить тут
        log_to_db(user, "Получены данные для обновления энергозон", f"{data}")

        # 1) удаление
        delete_ids = [r["id"] for r in data if r.get("_delete") and r.get("id") is not None]
        # (id=0 сюда не попадёт — и правильно)
        if delete_ids:
            SynchronousArea.query.filter(SynchronousArea.id.in_(delete_ids)).delete(synchronize_session=False)
            deleted_count = len(delete_ids)

        # 2) апдейты/добавления
        for record in (r for r in data if not r.get("_delete")):
            ez_id  = record.get("id")              # может быть 0!
            number = (record.get("number") or "").strip()
            name   = (record.get("name") or "").strip()

            if not number or not name:
                raise ValueError("Номер и наименование энергозоны обязательны.")

            # проверки уникальности (всегда исключаем текущую запись, даже если id=0)
            dup_num = SynchronousArea.query.filter(SynchronousArea.number == number)
            dup_name = SynchronousArea.query.filter(SynchronousArea.name == name)
            if ez_id is not None:
                dup_num = dup_num.filter(SynchronousArea.id != ez_id)
                dup_name = dup_name.filter(SynchronousArea.id != ez_id)

            if dup_num.first():
                raise ValueError(f"Энергозона с номером «{number}» уже существует.")
            if dup_name.first():
                raise ValueError(f"Энергозона с наименованием «{name}» уже существует.")

            if ez_id is not None:  # <— ключевое: 0 считается существующим id
                ez = db.session.get(SynchronousArea, ez_id)
                if not ez:
                    raise ValueError(f"Запись с ID {ez_id} не найдена.")
                if ez.number == number and ez.name == name:
                    no_change_count += 1
                else:
                    ez.number = number
                    ez.name = name
                    updated_count += 1
            else:
                db.session.add(SynchronousArea(number=number, name=name))
                added_count += 1

    # коммитим один раз — автоflush тут уже ок
    if updated_count == 0 and added_count == 0 and deleted_count == 0:
        raise ValueError("Данные для обновления отсутствуют.")

    try:
        db.session.commit()
        log_to_db(
            user, "Обновление энергозон",
            f"Обновлено: {updated_count}, добавлено: {added_count}, удалено: {deleted_count}, без изменений: {no_change_count}"
        )
    except IntegrityError:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления энергозон", "Нарушена уникальность (номер/наименование).")
        raise ValueError("Ошибка сохранения данных. Возможно, нарушена уникальность (номер/наименование).")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления энергозон", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")



def add_synchronous_area_service(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        synchronous_area_id = record.get("id")
        number = record.get("number", "").strip()
        name = record.get("name", "").strip()

        # Проверка на наличие необходимых данных
        if not number:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'number'.")

        if synchronous_area_id:
            # Обновление существующей записи
            synchronous_area = SynchronousArea.query.get(synchronous_area_id)
            if synchronous_area:
                # Проверка на дублирование имени
                duplicate = SynchronousArea.query.filter(
                    SynchronousArea.number == number,
                    SynchronousArea.id != synchronous_area_id
                ).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Энергозона номер: {number}, ID: {synchronous_area_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                # Обновление полей записи
                synchronous_area.number = number
                synchronous_area.name = name

                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлена энергозона с ID: {synchronous_area_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергозоны с ID: {synchronous_area_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {synchronous_area_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергозона с ID {synchronous_area_id} не существует.")
                raise ValueError(f"Запись с ID {synchronous_area_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = SynchronousArea.query.filter(SynchronousArea.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_synchronous_area = SynchronousArea(
                number=number,
                name=name,
            )
            db.session.add(new_synchronous_area)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлено новая энергозона: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергозоны: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def get_total_synchronous_area_records(synchronous_area_filter):
    query = SynchronousArea.query

    if synchronous_area_filter:
        query = query.filter(SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"))
        
    return query.count()

def delete_synchronous_area_service(ids, user):
    """Удаляет записи ФО по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for synchronous_area_id in ids:
        try:
            synchronous_area_id = int(synchronous_area_id)  # Приведение к целому числу
            synchronous_area = SynchronousArea.query.get(synchronous_area_id)
            if synchronous_area:
                db.session.delete(synchronous_area)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ФО ID: {synchronous_area_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {synchronous_area_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {synchronous_area_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_synchronous_area_from_excel_service(file, user):
    """Импортирует данные ФО из Excel-файла в базу данных с проверкой отсутствия данных для обновления."""
    import pandas as pd
    from sqlalchemy.exc import IntegrityError

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
        existing_records = db.session.query(SynchronousArea).all()
        existing_names = {record.name for record in existing_records}

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(SynchronousArea).filter(SynchronousArea.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            synchronous_area = db.session.query(SynchronousArea).filter_by(name=row['name'].strip()).first()

            if synchronous_area:
                # Проверяем, есть ли изменения в записи
                if (
                    synchronous_area.name_full != row['name_full'].strip()
                    or synchronous_area.name_abr != row['name_abr'].strip()
                ):
                    synchronous_area.name_full = row['name_full'].strip()
                    synchronous_area.name_abr = row['name_abr'].strip()
                    updated_count += 1
            else:
                # Добавляем новую запись
                new_record = SynchronousArea(
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


import pandas as pd
from io import BytesIO

def export_synchronous_area_to_excel_service(user, synchronous_area_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ФО в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы ФО из базы данных")
    log_to_db(user, "Параметры экспорта", f"filter={synchronous_area_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
   # Фильтрация
    query = SynchronousArea.query

    if synchronous_area_filter:
        query = query.filter(
            or_(
                SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"),
                SynchronousArea.name_full.ilike(f"%{synchronous_area_filter}%"),
                SynchronousArea.name_abr.ilike(f"%{synchronous_area_filter}%")
            )
        )

    # Сортировка
    if sort_by in ["name", "name_full", "name_abr"]:
        sort_field = getattr(SynchronousArea, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(SynchronousArea.id.desc() if sort_dir == "desc" else SynchronousArea.id.asc())

    synchronous_area_items = query.all()
    data = [{
        "№": index + 1,
        "Наименование": o.name,
        "Наименование полное": o.name_full,
        "Наименование сокращенное": o.name_abr
    } for index, o in enumerate(synchronous_area_items)]

    log_to_db(user, "Подготовка данных для экспорта таблицы ФО в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ФО")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы ФО в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
