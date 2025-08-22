"""Сервисный модуль: Energy zone services.
Промышленный стиль: логирование, валидация, транзакции с ретраями, блокировки строк для 20+ пользователей."""

from app.extensions import db

# --- Инфраструктура транзакций и устойчивость к конфликтам ---
# Для работы при 20+ одновременных пользователях используем повтор коммита при
# временных ошибках БД (deadlock, lock timeout). Это снижает риск сбоев при гонках.
import time

# --- Утилиты конкурентного доступа и оптимизации сессии ---
from functools import wraps

def _locked_get(model, id_):
    """Безопасное получение записи с блокировкой строки под обновление."""
    return db.session.query(model).filter_by(id=id_).with_for_update().one_or_none()

def no_autoflush(func):
    """Декоратор: выполняет функцию в контексте no_autoflush для ускорения массовых операций."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db.session.no_autoflush:
            return func(*args, **kwargs)
    return wrapper


from sqlalchemy.exc import OperationalError


def _commit_with_retry(tries: int = 3, delay: float = 0.05) -> None:
    """Коммит с повтором при временных ошибках блокировок.
    :param tries: число попыток
    :param delay: базовая задержка между попытками (увеличивается линейно)
    """
    for attempt in range(tries):
        try:
            # --- Фиксация транзакции (устойчивый коммит) ---

            _commit_with_retry()
            return
        except OperationalError as e:
            db.session.rollback()
            if attempt >= tries - 1:
                raise
            time.sleep(delay * (attempt + 1))
        except Exception:
            db.session.rollback()
            raise

from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from app.logs.services.logging_service import log_to_db


def get_energy_zone_list(page, per_page, energy_zone_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ФО с пагинацией, фильтрацией и сортировкой."""
    # Фильтрация
    query = EnergyZone.query

    if energy_zone_filter:
        query = query.filter(
            or_(
                EnergyZone.name.ilike(f"%{energy_zone_filter}%"),
            )
        )

    # Сортировка
    if sort_by in ["name"]:
        sort_field = getattr(EnergyZone, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(EnergyZone.id.desc() if sort_dir == "desc" else EnergyZone.id.asc())

    # Пагинация
    # --- Пагинация результата запроса ---

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_total_energy_zone_records(energy_zone_filter):
    query = EnergyZone.query

    if energy_zone_filter:
        query = query.filter(EnergyZone.name.ilike(f"%{energy_zone_filter}%"))
        
    return query.count()


@no_autoflush
def update_energy_zone_service(data, user):
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
            EnergyZone.query.filter(EnergyZone.id.in_(delete_ids)).delete(synchronize_session=False)
            deleted_count = len(delete_ids)

        # 2) апдейты/добавления
        for record in (r for r in data if not r.get("_delete")):
            ez_id  = record.get("id")              # может быть 0!
            number = (record.get("number") or "").strip()
            name   = (record.get("name") or "").strip()

            if not number or not name:
                raise ValueError("Номер и наименование энергозоны обязательны.")

            # проверки уникальности (всегда исключаем текущую запись, даже если id=0)
            dup_num = EnergyZone.query.filter(EnergyZone.number == number)
            dup_name = EnergyZone.query.filter(EnergyZone.name == name)
            if ez_id is not None:
                dup_num = dup_num.filter(EnergyZone.id != ez_id)
                dup_name = dup_name.filter(EnergyZone.id != ez_id)

            if dup_num.first():
                raise ValueError(f"Энергозона с номером «{number}» уже существует.")
            if dup_name.first():
                raise ValueError(f"Энергозона с наименованием «{name}» уже существует.")

            if ez_id is not None:  # <— ключевое: 0 считается существующим id
                ez = _locked_get(EnergyZone, ez_id)
                if not ez:
                    raise ValueError(f"Запись с ID {ez_id} не найдена.")
                if ez.number == number and ez.name == name:
                    no_change_count += 1
                else:
                    ez.number = number
                    ez.name = name
                    updated_count += 1
            else:
                db.session.add(EnergyZone(number=number, name=name))
                added_count += 1

    # коммитим один раз — автоflush тут уже ок
    if updated_count == 0 and added_count == 0 and deleted_count == 0:
        raise ValueError("Данные для обновления отсутствуют.")

    try:
        # --- Фиксация транзакции (устойчивый коммит) ---

        _commit_with_retry()
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


@no_autoflush
def add_energy_zone_service(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        energy_zone_id = record.get("id")
        number = record.get("number", "").strip()
        name = record.get("name", "").strip()

        # Проверка на наличие необходимых данных
        if not number:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'number'.")

        if energy_zone_id:
            # Обновление существующей записи
            energy_zone = _locked_get(EnergyZone, energy_zone_id)
            if energy_zone:
                # Проверка на дублирование имени
                duplicate = EnergyZone.query.filter(
                    EnergyZone.number == number,
                    EnergyZone.id != energy_zone_id
                ).with_for_update().first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Энергозона номер: {number}, ID: {energy_zone_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                # Обновление полей записи
                energy_zone.number = number
                energy_zone.name = name

                try:
                    # Сохранение изменений в базе данных
                    # --- Фиксация транзакции (устойчивый коммит) ---

                    _commit_with_retry()
                    log_to_db(user, "Успешное обновление", f"Обновлена энергозона с ID: {energy_zone_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергозоны с ID: {energy_zone_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {energy_zone_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергозона с ID {energy_zone_id} не существует.")
                raise ValueError(f"Запись с ID {energy_zone_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = EnergyZone.query.filter(EnergyZone.name == name).with_for_update().first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_energy_zone = EnergyZone(
                number=number,
                name=name,
            )
            db.session.add(new_energy_zone)

            try:
                # Сохранение новой записи в базе данных
                # --- Фиксация транзакции (устойчивый коммит) ---

                _commit_with_retry()
                log_to_db(user, "Успешное добавление", f"Добавлено новая энергозона: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергозоны: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


@no_autoflush
def delete_energy_zone_service(ids, user):
    """Удаляет записи ФО по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for energy_zone_id in ids:
        try:
            energy_zone_id = int(energy_zone_id)  # Приведение к целому числу
            energy_zone = _locked_get(EnergyZone, energy_zone_id)
            if energy_zone:
                db.session.delete(energy_zone)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ФО ID: {energy_zone_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {energy_zone_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {energy_zone_id}")

    try:
        # --- Фиксация транзакции (устойчивый коммит) ---

        _commit_with_retry()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_energy_zone_from_excel_service(file, user):
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
        existing_records = db.session.query(EnergyZone).all()
        existing_names = {record.name for record in existing_records}

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(EnergyZone).filter(EnergyZone.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            energy_zone = db.session.query(EnergyZone).filter_by(name=row['name'].strip()).first()

            if energy_zone:
                # Проверяем, есть ли изменения в записи
                if (
                    energy_zone.name_full != row['name_full'].strip()
                    or energy_zone.name_abr != row['name_abr'].strip()
                ):
                    energy_zone.name_full = row['name_full'].strip()
                    energy_zone.name_abr = row['name_abr'].strip()
                    updated_count += 1
            else:
                # Добавляем новую запись
                new_record = EnergyZone(
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
        # --- Фиксация транзакции (устойчивый коммит) ---

        _commit_with_retry()

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

def export_energy_zone_to_excel_service(user, energy_zone_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ФО в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы ФО из базы данных")
    log_to_db(user, "Параметры экспорта", f"filter={energy_zone_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
   # Фильтрация
    query = EnergyZone.query

    if energy_zone_filter:
        query = query.filter(
            or_(
                EnergyZone.name.ilike(f"%{energy_zone_filter}%"),
                EnergyZone.name_full.ilike(f"%{energy_zone_filter}%"),
                EnergyZone.name_abr.ilike(f"%{energy_zone_filter}%")
            )
        )

    # Сортировка
    if sort_by in ["name", "name_full", "name_abr"]:
        sort_field = getattr(EnergyZone, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(EnergyZone.id.desc() if sort_dir == "desc" else EnergyZone.id.asc())

    energy_zone_items = query.all()
    data = [{
        "№": index + 1,
        "Наименование": o.name,
        "Наименование полное": o.name_full,
        "Наименование сокращенное": o.name_abr
    } for index, o in enumerate(energy_zone_items)]

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
