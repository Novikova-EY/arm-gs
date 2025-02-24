from app import db
from app.models.logs_models import Log
from app.models.gen_companies_models import GenCompany
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def get_gen_company_list(page, per_page, gen_company_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список генерирующих компаний с пагинацией, фильтрацией и сортировкой."""
    # Фильтрация
    query = GenCompany.query

    if gen_company_filter:
        query = query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(GenCompany.name.desc() if sort_dir == "desc" else GenCompany.name.asc())
    else:
        query = query.order_by(GenCompany.id.desc() if sort_dir == "desc" else GenCompany.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def update_gen_company(data, user):
    """
    Обновляет записи генерирующей компании в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "АО "Генерирующая компания""}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        gen_company_id = record.get("id")
        name = record.get("name")

        # Проверки на валидность данных
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")

        if gen_company_id:
            fo = GenCompany.query.get(gen_company_id)

            duplicate = GenCompany.query.filter(GenCompany.name == name, GenCompany.id != gen_company_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            fo.name = name
        else:
            duplicate = GenCompany.query.filter(GenCompany.name == name, GenCompany.id != gen_company_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_gen_company = GenCompany(name=name)
            db.session.add(new_gen_company)

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(user, "Обновление записей генерирующей компании", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления генерирующей компании", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления генерирующей компании", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")

def gen_company_name_clear(name_to_change):
    """
    Приводит наименование в правильный вид
    """
    import re

    name = name_to_change.strip() # Удаление пробелов в начале и конце строки
    name = name.replace('\xa0', ' ') # Замена неразрывных пробелов на обычные
    name = re.sub(r'\s+', ' ', name) # Замена множественных пробелов одним пробелом
    name = re.sub(r'"\s*(\w)', r'«\1', name) # Замена " перед словом на «
    name = re.sub(r'(\w)\s*"', r'\1»', name) # Замена " после слова на »

    return name


def add_gen_company(data, user):
    """
    Добавляет или обновляет записи генерирующей компании в базе данных.
    :param data: Список словарей с данными генерирующей компании. Пример:
                 [{"id": 1, "name": "АО "Генерирующая компания""}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        gen_company_id = record.get("id")
        name = record.get("name")
         
        # Очистка и обработка имени
        name = gen_company_name_clear(name)

        # Проверка на наличие необходимых данных
        if not name:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name'.")

        if gen_company_id:
            # Обновление существующей записи
            gen_company = GenCompany.query.get(gen_company_id)
            if gen_company:
                # Проверка на дублирование имени
                duplicate = GenCompany.query.filter(GenCompany.name == name, GenCompany.id != gen_company_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {gen_company_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                gen_company.name = name
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено генерирующей компании с ID: {gen_company_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении генерирующей компании с ID: {gen_company_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {gen_company_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"генерирующей компании с ID {gen_company_id} не существует.")
                raise ValueError(f"Запись с ID {gen_company_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = GenCompany.query.filter(GenCompany.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_gen_company = GenCompany(name=name)
            db.session.add(new_gen_company)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлено новое генерирующей компании: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении генерирующей компании: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def get_total_gen_company_records(gen_company_filter):
    """
    Возвращает общее количество записей генерирующей компании, соответствующих фильтру.
    :param gen_company_filter: Фильтр по имени генерирующей компании.
    :return: Количество записей.
    """
    query = GenCompany.query
    
    if gen_company_filter:
        query = query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%"))
    return query.count()

def delete_gen_company_list(ids, user):
    """Удаляет записи генерирующей компании по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for gen_company_id in ids:
        try:
            gen_company_id = int(gen_company_id)  # Приведение к целому числу
            fo = GenCompany.query.get(gen_company_id)
            if fo:
                db.session.delete(fo)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален генерирующей компании ID: {gen_company_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {gen_company_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {gen_company_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_gen_company_from_excel(file, user):
    """Импортирует данные генерирующей компании из Excel-файла в базу данных."""
    import pandas as pd
    from sqlalchemy import text

    try:
        # Читаем данные из Excel
        data = pd.read_excel(file)

        # Проверяем наличие столбца name
        if 'name' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        # Очистка данных
        data['name'] = data['name'].apply(gen_company_name_clear)
        data = data.drop_duplicates(subset=['name']).dropna(subset=['name'])

        # Разрываем связь с gen_companies в machines
        db.session.execute(text("UPDATE machines SET id_gen_company = NULL WHERE id_gen_company IS NOT NULL"))
        db.session.commit()

        # Удаляем все записи из gen_companies
        db.session.query(GenCompany).delete()
        db.session.commit()

        # Сбрасываем автоинкремент
        db.session.execute(text("ALTER TABLE gen_companies AUTO_INCREMENT = 1"))
        db.session.commit()

        # Вставка новых записей
        records = [GenCompany(name=row['name']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        # Лог успешного импорта
        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")



import pandas as pd
from io import BytesIO

def export_gen_company_to_excel(user, gen_company_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные генерирующей компании в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы генерирующей компании из базы данных")
    log_to_db(user, "Параметры экспорта", f"gen_company_filter={gen_company_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = GenCompany.query
    if gen_company_filter:
        query = query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%"))

    # Сортировка
    if sort_by == "id":
        query = query.order_by(GenCompany.id.desc() if sort_dir == "desc" else GenCompany.id.asc())
    elif sort_by == "name":
        query = query.order_by(GenCompany.name.desc() if sort_dir == "desc" else GenCompany.name.asc())

    gen_company_items = query.all()
    data = [{
        "№": index + 1,
        "Наименование": o.name
    } for index, o in enumerate(gen_company_items)]

    log_to_db(user, "Подготовка данных для экспорта таблицы генерирующих компаний в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="генерирующей компании")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы генерирующих компаний в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
