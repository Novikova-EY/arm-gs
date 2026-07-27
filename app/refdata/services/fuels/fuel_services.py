"""Сервисный модуль: Типы топлива."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload, aliased
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType

# Сервисы
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_name,
)
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

# Фильтрация по версиям
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def fuel_query(
    fuel_filter=None,
    fuel_type_filter=None,
    nazvl_filter=None,
    kmbur_filter=None,
    sort_by="id",
    sort_dir="asc"):
    """Базовый запрос для выборки топлива с фильтрацией и сортировкой."""

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "fuel_type", "nazvl", "kmbur", "parent", "kod"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    fuel_type_id = _to_int_or_none(fuel_type_filter)

    # Базовый запрос
    query = Fuel.query.filter(Fuel.id > 0)
    query = apply_version_filter(query, Fuel)

    # Фильтрация
    need_join = False
    ff = (fuel_filter or "").strip()
    if ff:
        need_join = True
        query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        query = query.filter(or_(
            Fuel.name.ilike(f"%{ff}%"),
            FuelType.name.ilike(f"%{ff}%"),
        ))
    if nazvl_filter:
        query = query.filter(Fuel.nazvl.ilike(f"%{nazvl_filter}%"))
    if kmbur_filter:
        query = query.filter(Fuel.kmbur.ilike(f"%{kmbur_filter}%"))

    # Фильтр по конкретному типу топлива (id)
    if fuel_type_id is not None:
        query = query.filter(Fuel.id_fuel_type == fuel_type_id)

    # Сортировка
    if sort_by == "name":
        sort_col = Fuel.name
    elif sort_by == "kod":
        sort_col = Fuel.kod
    elif sort_by == "nazvl":
        sort_col = Fuel.nazvl
    elif sort_by == "kmbur":
        sort_col = Fuel.kmbur
    elif sort_by == "parent":
        parent_alias = aliased(Fuel)
        query = query.outerjoin(parent_alias, Fuel.parent_id == parent_alias.id)
        sort_col = parent_alias.name
    elif sort_by == "fuel_type":
        if not ff:
            query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        sort_col = FuelType.name
    else:
        sort_col = Fuel.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


def _assert_valid_fuel_parent(fuel_id, parent_id):
    """Проверяет, что parent_id существует и не создаёт цикл."""
    if parent_id is None:
        return

    parent_obj = db.session.get(Fuel, parent_id)
    if not parent_obj:
        raise ValueError(f"Родительский вид топлива с id={parent_id} не найден.")

    if fuel_id is not None and int(parent_id) == int(fuel_id):
        raise ValueError("Вид топлива не может быть родителем самого себя.")

    seen = {int(fuel_id)} if fuel_id is not None else set()
    current_id = int(parent_id)
    while current_id is not None:
        if current_id in seen:
            raise ValueError("Обнаружена циклическая ссылка в иерархии видов топлива.")
        seen.add(current_id)
        current_obj = db.session.get(Fuel, current_id)
        if not current_obj:
            raise ValueError(f"Родительский вид топлива с id={current_id} не найден.")
        current_id = current_obj.parent_id


@no_autoflush
def get_fuel_list(
    page, 
    per_page, 
    fuel_filter=None, 
    fuel_type_filter=None, 
    nazvl_filter=None,
    kmbur_filter=None,
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список типов топлива с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = fuel_query(
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        nazvl_filter=nazvl_filter,
        kmbur_filter=kmbur_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    ).options(joinedload(Fuel.fuel_type), joinedload(Fuel.parent))

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_fuel_service(data, user):
    """ Обновление данных по типам топлива """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка типов топлива", 
        f"{data}",
        entity_type="fuel")
    
    with db.session.no_autoflush:
        for record in data:
            fuel_id = record.get("fuel_id")
            name = (record.get("name") or "").strip()
            kod = _to_int_or_none(record.get("kod"), keep_zero=True)
            nazvl = (record.get("nazvl") or "").strip() or None
            kmbur = (record.get("kmbur") or "").strip() or None

            # Проверки на валидность данных
            if not name:
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(Fuel, fuel_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="fuel", 
                    entity_id=fuel_id)
                raise ValueError(f"Запись с ID «{fuel_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(Fuel.query, Fuel)
                     .filter(Fuel.name == name,
                             Fuel.id != fuel_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "fuel"))
                obj.name = name

            if "kod" in record and kod != obj.kod:
                changes.append(
                    format_field_change(
                        "kod",
                        obj.kod if obj.kod is not None else "не указано",
                        kod if kod is not None else "не указано",
                        "fuel",
                    )
                )
                obj.kod = kod

            if nazvl != obj.nazvl:
                changes.append(
                    format_field_change(
                        "nazvl",
                        obj.nazvl or "не указано",
                        nazvl or "не указано",
                        "fuel",
                    )
                )
                obj.nazvl = nazvl

            if kmbur != obj.kmbur:
                changes.append(
                    format_field_change(
                        "kmbur",
                        obj.kmbur or "не указано",
                        kmbur or "не указано",
                        "fuel",
                    )
                )
                obj.kmbur = kmbur

            if "parent_id" in record:
                new_parent_id = _to_int_or_none(record.get("parent_id"), keep_zero=False)
                if new_parent_id != obj.parent_id:
                    _assert_valid_fuel_parent(fuel_id, new_parent_id)
                    prev_parent = (
                        db.session.get(Fuel, obj.parent_id) if obj.parent_id else None
                    )
                    new_parent = (
                        db.session.get(Fuel, new_parent_id) if new_parent_id else None
                    )
                    old_name = prev_parent.name if prev_parent else "не указано"
                    new_name = new_parent.name if new_parent else "не указано"
                    changes.append(
                        format_field_change("parent_id", old_name, new_name, "fuel")
                    )
                    obj.parent_id = new_parent_id

            # Проверка наличия вида топлива
            if "fuel_type_id" in record:
                new_val = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)
                if new_val != obj.id_fuel_type:
                    new_obj = db.session.get(FuelType, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Вид топлива с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(FuelType, obj.id_fuel_type) if obj.id_fuel_type else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(format_field_change("id_fuel_type", old_name, new_name, "fuel"))
                    obj.id_fuel_type = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлено топливо: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="fuel", 
                    entity_id=fuel_id)
                updated_ids.append(fuel_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам топлива", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="fuel")
        else:
            log_to_db(
                user, 
                "Изменений по типам топлива не обнаружено", 
                "", 
                entity_type="fuel")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения типов топлива (уникальность/целостность)", 
            str(e), 
            entity_type="fuel")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов топлива", 
            str(e), 
            entity_type="fuel")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_fuel_service(data, user):
    """Создание новой записи: тип топлива"""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                fuel_type_id = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)
                parent_id = _to_int_or_none(record.get("parent_id"), keep_zero=False)
                kod = _to_int_or_none(record.get("kod"), keep_zero=True)

                if not name and not fuel_type_id:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="fuel")
                    raise ValueError(f"Каждая запись должна содержать 'name' и 'fuel_type_id'. Данные: {record}")

                # Проверяем существование вида топлива
                obj = db.session.get(FuelType, fuel_type_id)
                if not obj:
                    raise ValueError(f"Вид топлива с id={fuel_type_id} не найден.")

                _assert_valid_fuel_parent(None, parent_id)

                # Проверяем уникальность name
                dup = (apply_version_filter(Fuel.query, Fuel)
                        .filter(Fuel.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Создаем новую запись
                obj = Fuel(
                    name=name,
                    kod=kod,
                    id_fuel_type=fuel_type_id,
                    parent_id=parent_id,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                parent_name = (
                    db.session.get(Fuel, parent_id).name if parent_id else "не указано"
                )
                log_to_db(
                    user,
                    "Создан тип топлива",
                    f"Наименование: {name};"
                    f"Код: {kod if kod is not None else 'не указано'}; "
                    f"Вид топлива: {get_fuel_type_name(fuel_type_id)}; "
                    f"Родитель: {parent_name}",
                    entity_type="fuel", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "fuels")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового вида топлива",
            str(e),
            entity_type="fuel")
        raise ValueError(f"Ошибка сохранения нового вида топлива: {e}")


@no_autoflush
def delete_fuel_service(ids, user):
    """Удаляет записи типов топлива по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов топлива", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="fuel")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for rd_id in ids:
        try:
            fuel_id = int(rd_id)
        except (TypeError, ValueError):
            invalid.append(rd_id)
            log_to_db(
                user, 
                "Ошибка удаления типов топлива", 
                f"Некорректный ID: {rd_id}", 
                entity_type="fuel",
                entity_id=rd_id)
            continue

        obj = _locked_get(Fuel, fuel_id)
        if obj:
            name = obj.name or f"ID={fuel_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален тип топлива", 
                f"{name}", 
                entity_type="fuel", 
                entity_id=fuel_id)
        else:
            not_found.append(fuel_id)
            log_to_db(
                user, 
                "Ошибка удаления типов топлива", 
                f"Тип топлива с ID={fuel_id} не найден.", 
                entity_type="fuel", 
                entity_id=fuel_id)
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
            "Ошибка удаления типов топлива", 
            str(e), 
            entity_type="fuel",
            entity_id=fuel_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_fuel_service(file, user):
    """Импортирует данные типов топлива из Excel-файла в базу данных."""

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fuel_type' not in data.columns:
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Fuel).delete()
        _commit_with_retry()

        db.session.execute(text("ALTER TABLE fuel AUTO_INCREMENT = 1"))
        _commit_with_retry()

        records = [Fuel(name=row['name'], id_fuel_type=row['id_fuel_type']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        _commit_with_retry()

        log_to_db(
            user, 
            "Импорт завершен", 
            f"Импортировано записей: {len(records)}", 
            entity_type="fuel")
        return len(records)
    except Exception as e:
        log_to_db(
            user, 
            "Ошибка импорта", 
            str(e), 
            entity_type="fuel")
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_fuel_service(
    user,
    fuel_filter=None,
    fuel_type_filter=None,
    nazvl_filter=None,
    kmbur_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Экспортирует данные типов топлива в Excel. """

    log_to_db(
        user, 
        "Начата выгрузка таблицы типов топлива. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа топлива = {fuel_filter},"
            f"Фильтр по столбцу: Вид топлива = {get_fuel_type_name(fuel_type_filter)},"
            f"Фильтр по столбцу: Наименование БД Топливо = {nazvl_filter},"
            f"Фильтр по столбцу: Тип угольного топлива = {kmbur_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ), 
        entity_type="fuel"
    )

    # Базовый запрос
    query = fuel_query(
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        nazvl_filter=nazvl_filter,
        kmbur_filter=kmbur_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="fuel")

    # Подготовка данных для Excel (названия столбцов как на экране)
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Код": o.kod if o.kod is not None else "—",
            "Вид топлива": _dash(o.name),
            "Тип топлива": getattr(o.fuel_type, "name", "Не указан") or "Не указан",
            "Родительский вид": getattr(o.parent, "name", "Не указан") or "Не указан",
            "Наименование в БД Топливо": _dash(o.nazvl),
            "Тип угольного топлива": _dash(o.kmbur),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы типов топлива в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="fuel")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    sheet_name = "Типы топлива"

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
            "Переход на openpyxl при экспорте топлива",
            f"xlsxwriter error: {e}",
            entity_type="fuel",
        )
        output = BytesIO()
        _write_excel(output, "openpyxl")

    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы типов топлива в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="fuel")
    return output

# === all_versions_fuel start ===
@no_autoflush
def add_fuel_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version
    from app.refdata.models.fuels.fuel_type_model import FuelType

    def normalize_record(record):
        name = (record.get("name") or "").strip()
        nazvl = (record.get("nazvl") or "").strip() or None
        kmbur = (record.get("kmbur") or "").strip() or None
        fuel_type_id = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)
        parent_id = _to_int_or_none(record.get("parent_id"), keep_zero=False)
        kod = _to_int_or_none(record.get("kod"), keep_zero=True)
        if not name or not fuel_type_id:
            raise ValueError("Каждая запись должна содержать 'name' и 'fuel_type_id'.")
        return {
            "name": name,
            "kod": kod,
            "nazvl": nazvl,
            "kmbur": kmbur,
            "fuel_type_id": fuel_type_id,
            "parent_id": parent_id,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "kod": clean["kod"],
            "nazvl": clean["nazvl"],
            "kmbur": clean["kmbur"],
            "id_fuel_type": fk_id_for_version(FuelType, clean["fuel_type_id"], version_id),
            "parent_id": (
                fk_id_for_version(Fuel, clean["parent_id"], version_id)
                if clean["parent_id"] is not None
                else None
            ),
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=Fuel,
        entity_type="fuel",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name']
    )


@no_autoflush
def update_fuel_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version
    from app.refdata.models.fuels.fuel_type_model import FuelType

    def normalize_record(record):
        fuel_id = record.get("fuel_id")
        name = (record.get("name") or "").strip()
        nazvl = (record.get("nazvl") or "").strip() or None
        kmbur = (record.get("kmbur") or "").strip() or None
        fuel_type_id = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)
        parent_id = _to_int_or_none(record.get("parent_id"), keep_zero=False)
        kod = _to_int_or_none(record.get("kod"), keep_zero=True)
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "fuel_id": fuel_id,
            "name": name,
            "kod": kod,
            "nazvl": nazvl,
            "kmbur": kmbur,
            "fuel_type_id": fuel_type_id,
            "parent_id": parent_id,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "kod": clean["kod"],
            "nazvl": clean["nazvl"],
            "kmbur": clean["kmbur"],
            "id_fuel_type": fk_id_for_version(FuelType, clean["fuel_type_id"], version_id),
            "parent_id": (
                fk_id_for_version(Fuel, clean["parent_id"], version_id)
                if clean["parent_id"] is not None
                else None
            ),
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=Fuel,
        entity_type="fuel",
        pk_field="fuel_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name', 'kod', 'nazvl', 'kmbur', 'id_fuel_type', 'parent_id'],
        unique_fields=['name'],
        temp_fields=['name'],
        clear_fields=[]
    )
# === all_versions_fuel end ===
