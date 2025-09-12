"""Сервисный модуль: Объединенные энергосистемы."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_name,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_name,
)
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


def regional_energy_system_query(
    regional_energy_system_filter=None,
    union_energy_system_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки региональных энергосистем с фильтрацией и сортировкой. """

    # Нормализация входов
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    sort_by = (sort_by or "id").lower()
    allowed_sort = {"id", "name", "name_full", "federal_district", "energy_zone", "synchronous_area"}
    if sort_by not in allowed_sort:
        sort_by = "id"

    # Безопасная конвертация ID-фильтров
    union_energy_system_id = _to_int_or_none(union_energy_system_filter)

    # Базовый запрос
    query = (
        RegionalEnergySystem.query
        .options(
            joinedload(RegionalEnergySystem.regional_districts),
            joinedload(RegionalEnergySystem.union_energy_system)
        )
    )

    # Фильтрация по названию региональной энергосистемы
    if regional_energy_system_filter:
        query = query.filter(RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%"))

    # Фильтрация по ОЭС (строго по ID)
    if union_energy_system_filter:
        query = query.filter(RegionalEnergySystem.id_union_energy_system == union_energy_system_id)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())
    
    elif sort_by == "name_full":
        query = query.order_by(RegionalEnergySystem.name_full.desc() if sort_dir == "desc" else RegionalEnergySystem.name_full.asc())
    
    elif sort_by == "union_energy_system":
        query = query.join(UnionEnergySystem).order_by(
            UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc()
        )
    
    else:
        query = query.order_by(RegionalEnergySystem.id.desc() if sort_dir == "desc" else RegionalEnergySystem.id.asc())


    # Исключаем запись "Не указано" (id=0)
    query = query.filter(RegionalEnergySystem.id.isnot(None), RegionalEnergySystem.id > 0)

    return query


@no_autoflush
def get_regional_energy_system_list(
    page, 
    per_page, 
    regional_energy_system_filter=None, 
    union_energy_system_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список региональных энергосистем с пагинацией, фильтрацией и сортировкой, загружая связи с субъектами РФ. """

    # Базовый запрос
    query = regional_energy_system_query(
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_regional_energy_system_service(data, user):
    """Обновление данных по региональным энергосистемам."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(user, "Получены данные для обновления списка региональных энергосистем", 
              f"{data}")

    with db.session.no_autoflush:
        for record in data:
            regional_energy_system_id = record.get("regional_energy_system_id")
            name = record.get("name")
            name_full = record.get("name_full")
            union_energy_system_id = _to_int_or_none(record.get("union_energy_system_id"), keep_zero=False)
            regional_district_ids = _to_int_or_none(record.get("regional_district_ids", []), keep_zero=False)

            # Проверки на валидность данных
            if not name or union_energy_system_id is None:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError(f"Каждая запись должна содержать 'name' и 'union_energy_system_id'. Данные: {record}")

            obj = db.session.get(RegionalEnergySystem, regional_energy_system_id)
            if not obj:
                log_to_db(user, "Ошибка валидации", 
                    f"Запись с ID «{regional_energy_system_id}» не найдена.")
                raise ValueError(f"Запись с ID «{regional_energy_system_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (RegionalEnergySystem.query
                     .filter(RegionalEnergySystem.name == name,
                             RegionalEnergySystem.id != regional_energy_system_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

            # Проверка уникальности name_full
            if name_full != (obj.name_full or ""):
                q_full = (RegionalEnergySystem.query
                     .filter(RegionalEnergySystem.name_full == name_full,
                             RegionalEnergySystem.id != regional_energy_system_id))
                if q_full.first():
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")
                
            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            if name_full != (obj.name_full or None):
                changes["Полное наименование"] = f"{_dash(obj.name_full)} → {_dash(name_full)}"
                obj.name_full = name_full

            # Опциональные FK (если ключ присутствует в record)
            if "union_energy_system_id" in record:
                ues = _to_int_or_none(record.get("union_energy_system_id"), keep_zero=False)
                if ues != obj.id_union_energy_system:
                    new_ues = db.session.get(UnionEnergySystem, ues) if ues is not None else None
                    if ues is not None and not new_ues:
                        raise ValueError(f"ОЭС с id={ues} не найдена.")
                    
                    prev_fd = db.session.get(UnionEnergySystem, obj.id_union_energy_system) if obj.id_union_energy_system else None
                    changes["ОЭС"] = f"{_dash(prev_fd.name if prev_fd else None)} → {_dash(new_ues.name if new_ues else None)}"
                    obj.id_union_energy_system = ues

            # Обновление связей «многие ко многим»
            # Выполняем обновление только если ключ присутствует в record
            if "regional_district_ids" in record:
                # Нормализация входа в множество целых id
                raw_ids = regional_district_ids
                normalized_ids = []

                if isinstance(raw_ids, (list, tuple, set)):
                    for v in raw_ids:
                        iv = _to_int_or_none(v, keep_zero=False)
                        if iv is not None:
                            normalized_ids.append(iv)
                elif isinstance(raw_ids, str):
                    # поддержка "1,2,3"
                    for part in raw_ids.split(","):
                        iv = _to_int_or_none(part.strip(), keep_zero=False)
                        if iv is not None:
                            normalized_ids.append(iv)
                else:
                    # Неподдерживаемый формат — считаем, что список пуст
                    normalized_ids = []

                new_district_ids = set(normalized_ids)
                existing_district_ids = {d.id for d in obj.regional_districts}

                to_add_ids = new_district_ids - existing_district_ids
                to_remove_ids = existing_district_ids - new_district_ids

                # Добавить новые связи пакетно, с проверкой, что все есть в БД
                if to_add_ids:
                    districts_to_add = (RegionalDistrict.query
                                        .filter(RegionalDistrict.id.in_(to_add_ids))
                                        .all())
                    found_ids = {d.id for d in districts_to_add}
                    missing_ids = to_add_ids - found_ids
                    if missing_ids:
                        raise ValueError(f"Субъекты РФ не найдены: {sorted(missing_ids)}")

                    for d in districts_to_add:
                        obj.regional_districts.append(d)

                # Удалить устаревшие связи (без лишних запросов)
                if to_remove_ids:
                    for d in list(obj.regional_districts):
                        if d.id in to_remove_ids:
                            obj.regional_districts.remove(d)

                # Логируем изменения, если были
                if to_add_ids or to_remove_ids:
                    changes["Субъекты РФ (regional_districts)"] = (
                        f"{sorted(existing_district_ids)} → {sorted(new_district_ids)}"
                    )

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлена региональная энергосистема: {name}", 
                          f"Изменения = {changes}")
                updated_ids.append(regional_energy_system_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по региональной энергосистеме", 
                      f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по региональным энергосистемам не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения региональной энергосистемы (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении региональной энергосистемы", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_regional_energy_system_service(data, user):
    """Создание новой записи: региональная энергосистема"""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                union_energy_system_id = _to_int_or_none(record.get("union_energy_system_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not name or not name_full or not union_energy_system_id:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'union_energy_system_id'. Данные: {record}")

                # Проверяем существование ОЭС
                obj = db.session.get(UnionEnergySystem, union_energy_system_id)
                if not obj:
                    raise ValueError(f"ОЭС с id={union_energy_system_id} не найдена.")

                # Проверяем уникальность name
                dup = (RegionalEnergySystem.query
                        .filter(RegionalEnergySystem.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full
                dup_full = (RegionalEnergySystem.query
                        .filter(RegionalEnergySystem.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Создаем новую запись
                obj = RegionalEnergySystem(
                    name=name,
                    name_full=name_full or None,
                    id_union_energy_system=union_energy_system_id,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(user, "Создана региональная энергосистема",
                    (
                        f"Наименование: {name}; "
                        f"Полное наименование: {_dash(name_full)}; "
                        f"Часть энергосистемы России: {get_union_energy_system_name(union_energy_system_id)} "
                    )
                )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения новой региональной энергосистемы Возможно, нарушены уникальные ограничения или внешние ключи.", str(e))
        raise ValueError("Ошибка сохранения новой региональной энергосистемы. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения новой региональной энергосистемы", str(e))
        raise ValueError(f"Ошибка сохранения новой региональной энергосистемы: {e}")


@no_autoflush
def delete_regional_energy_system_service(ids, user):
    """Удаляет записи региональных энергосистем по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")
    
    log_to_db(user, "Удаление записей", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for res_id in ids:
        try:
            regional_energy_system_id = int(res_id)
        except (TypeError, ValueError):
            invalid.append(res_id)
            log_to_db(user, "Ошибка удаления региональной энергосистемы", 
                      f"Некорректный ID: {res_id}")
            continue

        obj = _locked_get(RegionalEnergySystem, regional_energy_system_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_regional_energy_system_name(regional_energy_system_id))
            successful_deletes += 1
            log_to_db(user, "Удалена региональная энергосистема" 
                      f"{get_regional_energy_system_name(regional_energy_system_id)}")
        else:
            not_found.append(regional_energy_system_id)
            log_to_db(user, "Ошибка удаления региональной энергосистемы", 
                      f"Региональная энергосистема с ID={regional_energy_system_id} не найдена.")

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

        log_to_db(user, "Результат удаления региональных энергосистем", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления региональных энергосистем", str(e))
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_regional_energy_system_service(file, user):
    """Импортирует данные региональных энергосистем из Excel с текстовым названием ОЭС и обновляет существующие записи."""

    try:
        # Читаем данные из файла
        data = pd.read_excel(file)

        # Проверяем наличие необходимых столбцов
        required_columns = {'id', 'name', 'union_energy_system'}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы: {required_columns - set(data.columns)}")

        # Удаляем пробелы в названиях столбцов (если есть)
        data.columns = data.columns.str.strip()

        imported_count = 0  # Количество успешно импортированных записей
        updated_count = 0  # Количество обновленных записей

        # Создаем словарь соответствий названия ОЭС → ID (кэш для ускорения запросов)
        oes_mapping = {oes.name: oes.id for oes in db.session.query(UnionEnergySystem).all()}

        # Обрабатываем каждую запись
        for _, row in data.iterrows():
            oes_name = row['union_energy_system'].strip()  # Название ОЭС
            oes_id = oes_mapping.get(oes_name)

            if not oes_id:
                log_to_db(user, "Предупреждение", f"ОЭС '{oes_name}' не найден в базе. Запись '{row['name']}' пропущена.")
                continue  # Пропускаем запись, если ОЭС не найден

            # Проверяем, существует ли уже такая энергосистема в БД
            record = db.session.query(RegionalEnergySystem).filter_by(id=row['id']).first()

            if record:
                # Логирование изменений перед обновлением
                old_data = f"Старая ОЭС: {record.id_union_energy_system}, Старое имя: {record.name}"
                new_data = f"Новая ОЭС: {oes_id}, Новое имя: {row['name']}"

                # Обновляем существующую запись
                record.name = row['name']
                record.id_union_energy_system = oes_id

                log_to_db(user, "Обновление записи", f"Обновлена энергосистема ID {row['id']}. {old_data} → {new_data}")
                updated_count += 1
            else:
                # Создаем новую запись
                new_record = RegionalEnergySystem(
                    id=row['id'],
                    name=row['name'],
                    id_union_energy_system=oes_id
                )
                db.session.add(new_record)
                log_to_db(user, "Добавление новой записи", f"Добавлена новая энергосистема: {row['name']} (ОЭС: {oes_name})")
                imported_count += 1  # Увеличиваем счетчик новых записей

        # Сохраняем изменения
        db.session.commit()
        log_to_db(user, "Импорт завершён", f"Добавлено записей: {imported_count}, Обновлено: {updated_count}")

        return {"imported": imported_count, "updated": updated_count}

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта (IntegrityError)", str(e))
        raise ValueError("Ошибка целостности данных. Возможно, дублируются ID или имена.")

    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_regional_energy_system_service(
        user, 
        regional_energy_system_filter=None, 
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка региональных энергосистем в Excel. """
        
    log_to_db(user, "Начата выгрузка таблицы региональных энергосистем из базы данных")
    log_to_db(user, "Параметры экспорта", 
            (
                f"Фильтр по столбцу: Наименование региональной энергосистемы = {regional_energy_system_filter}," 
                f"Фильтр по столбцу: ОЭС = {get_union_energy_system_name(union_energy_system_filter)},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            )
    )

    # Базовый запрос
    query = regional_energy_system_query(
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
        "№": idx + 1,
        "Региональная энергосистема": _dash(o.name),
        "Региональная энергосистема (полное название)": _dash(o.name_full),
        "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указана",
        "Субъекты РФ": ", ".join([district.name_full for district in o.regional_districts]) if o.regional_districts else "Не указаны"
        })

    if not data:
        log_to_db(user, "Экспорт завершён", "Нет данных для экспорта.")
        return None

    log_to_db(user, "Подготовка данных для экспорта таблицы региональных энергосистем в Excel", 
              f"Записей для экспорта: {len(data)}")
    
    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)

    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Региональные энергосистемы"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы региональных энергосистем в Excel завершён", 
              f"Экспортировано записей: {len(data)}")
    
    return output
