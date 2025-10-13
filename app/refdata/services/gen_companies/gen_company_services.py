"""Сервисный модуль: Генерирующие компании."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.gen_companies.gen_company_model import GenCompany

# Сервисы
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
    _replace_quotes_sequentially,
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


def gen_company_query(
    gen_company_filter=None,
    sort_by="id",
    sort_dir="asc",):
    """ Базовый запрос для выборки списка генерирующих компаний с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    gen_company_id = _to_int_or_none(gen_company_filter)

    # Базовый запрос
    query = (
        GenCompany.query
        .filter(GenCompany.id.isnot(None), GenCompany.id > 0)
    )

    # Фильтрация
    if gen_company_filter:
        query = query.filter(
            or_(
                GenCompany.name.ilike(f"%{gen_company_filter}%"),
            )
        )

    if gen_company_id is not None:
        query = query.filter(GenCompany.id == gen_company_id)

    # Сортировка
    if sort_by == "name":
        sort_col = GenCompany.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    else:  # "id" (по умолчанию)
        sort_col = GenCompany.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(GenCompany.id.isnot(None), GenCompany.id > 0)

    return query


@no_autoflush
def get_gen_company_list(
    page, 
    per_page, 
    gen_company_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список генерирующих компаний с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = gen_company_query(
        gen_company_filter=gen_company_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_gen_company_service(data, user):
    """Обновление данных по генерирующим компаниям."""

    if not isinstance(data, list) or not data:
        raise ValueError(f"Данные должны быть предоставлены в виде непустого списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка генерирующих компаний", 
        f"{data}", 
        entity_type="gen_company")

    with db.session.no_autoflush:
        for record in data:
            gen_company_id = record.get("gen_company_id")
            name_to_clean = record.get("name", "").strip()
            name_clean = _clean_name(name_to_clean)
            name = _replace_quotes_sequentially(name_clean)

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="gen_company",
                    entity_id=gen_company_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")
            
            obj = db.session.get(GenCompany, gen_company_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{gen_company_id}» не найдена.", 
                    entity_type="gen_company", 
                    entity_id=gen_company_id)
                raise ValueError(f"Запись с ID «{gen_company_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (GenCompany.query
                     .filter(GenCompany.name == name,
                             GenCompany.id != gen_company_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")
            
            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена генерирующая компания {name}", 
                    f"Изменения = {changes}", 
                    entity_type="gen_company", 
                    entity_id=gen_company_id)
                updated_ids.append(gen_company_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()
        
        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по генерирующим компаниям", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="gen_company")
        else:
            log_to_db(
                user, 
                "Изменений по генерирующим компаниям не обнаружено", 
                "", 
                entity_type="gen_company")
        
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения генерирующей компании (уникальность/целостность)", 
            str(e), 
            entity_type="gen_company")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении генерирующих компаний", 
            str(e), 
            entity_type="gen_company")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_gen_company_service(data, user):
    """Создание новой записи: генерирующая компания"""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")
    
    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name_to_clean = (record.get("name") or "").strip()
                name_clean = _clean_name(name_to_clean)
                name = _replace_quotes_sequentially(name_clean)

                # Проверка на наличие необходимых данных
                if not name :
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="gen_company")
                    raise ValueError(f"Каждая запись должна содержать 'name''. Данные: {record}")

                # Проверяем уникальность name
                dup = (GenCompany.query
                        .filter(GenCompany.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Создаем новую запись
                obj = GenCompany(
                    name=name,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создана генерирующая компания",
                    f"Наименование: {name}.",
                    entity_type="gen_company", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "gen_companies")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения новой генерирующей компании", 
            str(e), 
            entity_type="gen_company")
        raise ValueError(f"Ошибка сохранения новой генерирующей компании: {e}")


@no_autoflush
def delete_gen_company_service(ids, user):
    """Удаляет записи генерирующих компаний по переданным ID."""
    
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление генерирующих компаний", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="gen_company")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for fd_id in ids:
        try:
            gen_company_id = int(fd_id)
        except (TypeError, ValueError):
            invalid.append(fd_id)
            log_to_db(
                user, 
                "Ошибка удаления генерирующей компании", 
                f"Некорректный ID: {fd_id}", 
                entity_type="gen_company",
                entity_id=fd_id)
            continue

        obj = _locked_get(GenCompany, gen_company_id)
        if obj:
            name = obj.name or f"ID={gen_company_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удалена генерирующая компания", 
                f"{name}", 
                entity_type="gen_company", 
                entity_id=gen_company_id)
        else:
            not_found.append(gen_company_id)
            log_to_db(
                user, 
                "Ошибка удаления генерирующей компании", 
                f"Генерирующая компания с ID={gen_company_id} не найдена.", 
                entity_type="gen_company", 
                entity_id=gen_company_id)

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
            "Ошибка удаления генерирующих компаний", 
            str(e), 
            entity_type="gen_company",
            entity_id=gen_company_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_gen_company_service(file, user):
    """Импортирует данные генерирующих компаний из Excel-файла в базу данных с проверкой отсутствия данных для обновления."""
    try:
        # Читаем данные из Excel
        data = pd.read_excel(file)

        # Проверяем наличие столбца name
        if 'name' not in data.columns:
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы.")

        # Очистка данных
        data['name'] = data['name'].apply(_clean_name)
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
        log_to_db(
            user, 
            "Импорт завершен", 
            f"Импортировано записей: {len(records)}", 
            entity_type="gen_company")
        return len(records)
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка импорта", 
            str(e), 
            entity_type="gen_company")
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_gen_company_service(
        user, 
        gen_company_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные генерирующих компаний в Excel. """

    log_to_db(
        user, 
        "Начата выгрузка таблицы генерирующих компаний. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование генерирующей компании = {gen_company_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ), 
        entity_type="gen_company")

    # Базовый запрос
    query = gen_company_query(
        gen_company_filter=gen_company_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="gen_company")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы генерирующих компаний в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="gen_company")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Генерирующие компании"
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
        "Экспорт таблицы генерирующих компаний в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="gen_company")
    return output