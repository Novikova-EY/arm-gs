"""Сервисный модуль: Типы агрегатов ТЭС."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def tes_machine_type_query(
        tes_machine_type_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки типов агрегатов ТЭС с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = TesMachineType.query.filter(TesMachineType.id.isnot(None), TesMachineType.id > 0)

    # Фильтрация
    if tes_machine_type_filter:
        query = query.filter(TesMachineType.name.ilike(f"%{tes_machine_type_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = TesMachineType.name
    else:
        sort_col = TesMachineType.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_tes_machine_type_list(
    page, 
    per_page, 
    tes_machine_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список типов агрегатов ТЭС с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = tes_machine_type_query(
        tes_machine_type_filter=tes_machine_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_tes_machine_type_service(data, user):
    """ Обновление данных по типам агрегатов ТЭС """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка типов агрегатов ТЭС", 
        f"{data}", 
        entity_type="tes_machine_type")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            tes_machine_type_id = record.get("tes_machine_type_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="tes_machine_type",
                    entity_id=tes_machine_type_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(TesMachineType, tes_machine_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{tes_machine_type_id}» не найдена.", 
                    entity_type="tes_machine_type", 
                    entity_id=tes_machine_type_id)
                raise ValueError(f"Запись с ID «{tes_machine_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (TesMachineType.query
                     .filter(TesMachineType.name == name,
                             TesMachineType.id != tes_machine_type_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "tes_machine_type"))
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен тип агрегата ТЭС: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="tes_machine_type", 
                    entity_id=tes_machine_type_id)
                updated_ids.append(tes_machine_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам агрегатов ТЭС", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="tes_machine_type",
                entity_id=tes_machine_type_id)
        else:
            log_to_db(user, "Изменений по типам агрегатов ТЭС не обнаружено", "", entity_type="tes_machine_type")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения типов агрегатов ТЭС (уникальность/целостность)", 
            str(e), 
            entity_type="tes_machine_type",
            entity_id=tes_machine_type_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов агрегатов ТЭС", 
            str(e), 
            entity_type="tes_machine_type",
            entity_id=tes_machine_type_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_tes_machine_type_service(data, user):
    """Создание новой записи: тип агрегата ТЭС"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="tes_machine_type")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                # Проверяем уникальность name
                dup = (TesMachineType.query
                       .filter(TesMachineType.name == name)
                       .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Создаем новую запись
                obj = TesMachineType(name=name)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан тип агрегата ТЭС", 
                    f"Наименование: {name}",
                    entity_type="tes_machine_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "tes_machine_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового типа агрегата ТЭС", 
            str(e), 
            entity_type="tes_machine_type")
        raise ValueError(f"Ошибка сохранения нового типа агрегата ТЭС: {e}") from e


@no_autoflush
def delete_tes_machine_type_service(ids, user):
    """Удаляет записи типов агрегатов ТЭС по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов агрегатов ТЭС", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="tes_machine_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            tes_machine_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления типов агрегатов ТЭС", 
                f"Некорректный ID: {ft_id}", 
                entity_type="tes_machine_type",
                entity_id=ft_id)
            continue

        obj = _locked_get(TesMachineType, tes_machine_type_id)
        if obj:
            name = obj.name or f"ID={tes_machine_type_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален тип агрегата ТЭС", 
                f"{name}", 
                entity_type="tes_machine_type", 
                entity_id=tes_machine_type_id)
        else:
            not_found.append(tes_machine_type_id)
            log_to_db(
                user, 
                "Ошибка удаления типов агрегатов ТЭС", 
                f"Тип агрегата с ID={tes_machine_type_id} не найден.", 
                entity_type="tes_machine_type", 
                entity_id=tes_machine_type_id)

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
            "Ошибка удаления типов агрегатов ТЭС", 
            str(e), 
            entity_type="tes_machine_type",
            entity_id=tes_machine_type_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_tes_machine_type_service(
    user,
    tes_machine_type_filter=None,
    sort_by="id",
    sort_dir="asc",):
    """ Экспортирует данные типов агрегатов ТЭС в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы типов агрегатов ТЭС. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа агрегата = {tes_machine_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="tes_machine_type"
    )

    # Базовый запрос
    query = tes_machine_type_query(
        tes_machine_type_filter=tes_machine_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="tes_machine_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы типов агрегатов ТЭС в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="tes_machine_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы агрегатов ТЭС"
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
        "Экспорт таблицы типов агрегатов ТЭС в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="tes_machine_type")
    return output


from sqlalchemy import text

def quick_fix_seq(schema: str, table: str, col: str = "id"):
    """
    Быстро выравнивает sequence под MAX(id) для указанной таблицы.
    """
    with db.engine.begin() as conn:
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": f"{schema}.{table}", "col": col}
        ).scalar()
        if not seq:
            return
        max_id = conn.execute(
            text(f"SELECT COALESCE(MAX({col}), 0) FROM {schema}.{table}")
        ).scalar()

        conn.execute(
            text(f"SELECT setval('{seq}', {int(max_id)}, true)")
        )

