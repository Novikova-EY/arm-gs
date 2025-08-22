# -*- coding: utf-8 -*-
"""
Сервисный слой для справочника «Типы энергосистем».
Содержит операции выборки, добавления, обновления, удаления и экспорта.
Все операции логируются через log_to_db.
"""
from io import BytesIO
from typing import List, Tuple, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy import asc, desc
import pandas as pd

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

def _apply_sort(query, sort_by: str, sort_dir: str):
    """Применяет сортировку с whitelisting допустимых полей."""
    sort_by = (sort_by or "id").lower()
    sort_dir = (sort_dir or "asc").lower()

    allowed = {
        "id": EnergySystemType.id,
        "name": EnergySystemType.name,
    }
    column = allowed.get(sort_by, EnergySystemType.id)
    order = asc if sort_dir != "desc" else desc
    return query.order_by(order(column))

def get_energy_system_types(
    energy_system_type_filter: Optional[str],
    sort_by: str,
    sort_dir: str,
    page: int,
    per_page: int,
) -> Tuple[List[EnergySystemType], int]:
    """Возвращает список типов энергосистем и общее количество записей с учётом фильтра."""
    query = EnergySystemType.query
    if energy_system_type_filter:
        like = f"%{energy_system_type_filter.strip()}%"
        query = query.filter(EnergySystemType.name.ilike(like))

    total = query.count()
    query = _apply_sort(query, sort_by, sort_dir)
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total

def get_total_energy_system_type_records(energy_system_type_filter: Optional[str]) -> int:
    query = EnergySystemType.query
    if energy_system_type_filter:
        like = f"%{energy_system_type_filter.strip()}%"
        query = query.filter(EnergySystemType.name.ilike(like))
    return query.count()

def add_energy_system_type_service(data: List[dict], user) -> int:
    """Добавляет одну запись. Ожидается список с одним словарём: {'name': '...'}.
    Возвращает id созданной записи.
    """
    if not isinstance(data, list) or not data:
        raise ValueError("Ожидается непустой список записей для добавления.")
    record = data[0]
    name = (record.get("name") or "").strip()
    if not name:
        log_to_db(user, "Ошибка валидации", "Пустое наименование типа энергосистемы")
        raise ValueError("Наименование обязательно.")

    exists = EnergySystemType.query.filter_by(name=name).first()
    if exists:
        log_to_db(user, "Ошибка дублирования", f"Тип энергосистемы с именем '{name}' уже существует (id={exists.id}).")
        raise ValueError(f"Тип энергосистемы с именем '{name}' уже существует.")

    obj = EnergySystemType(name=name)
    db.session.add(obj)
    db.session.commit()
    log_to_db(user, "Добавление типа энергосистемы", f"id={obj.id}, name={obj.name}")
    return obj.id

def update_energy_system_types(ids: List[int], names: List[str], user) -> int:
    """Массовое обновление имён.
    Возвращает количество обновлённых записей.
    """
    if not ids or not names or len(ids) != len(names):
        raise ValueError("Списки ids и names должны быть одинаковой длины и не пустыми.")

    updated = 0
    for _id, _name in zip(ids, names):
        _name = (_name or "").strip()
        if not _name:
            log_to_db(user, "Ошибка валидации", f"id={_id}: пустое имя")
            raise ValueError("Наименование обязательно.")

        # Проверка на дубликат имени у других записей
        dup = EnergySystemType.query.filter(
            EnergySystemType.name == _name,
            EnergySystemType.id != _id
        ).first()
        if dup:
            log_to_db(user, "Ошибка дублирования", f"id={_id}: имя '{_name}' уже занято (id={dup.id})")
            raise ValueError(f"Имя '{_name}' уже существует.")

        obj = EnergySystemType.query.get(_id)
        if not obj:
            log_to_db(user, "Не найдено", f"id={_id}")
            continue
        if obj.name != _name:
            obj.name = _name
            updated += 1

    if updated:
        db.session.commit()
    return updated

def delete_energy_system_types(ids: List[int], user) -> Tuple[int, int]:
    """Удаление по списку id.
    Возвращает кортеж (успешно_удалено, не_удалено_из-за_ссылочной_целостности).
    """
    ok, failed = 0, 0
    for _id in ids or []:
        obj = EnergySystemType.query.get(_id)
        if not obj:
            continue
        try:
            db.session.delete(obj)
            db.session.commit()
            ok += 1
            log_to_db(user, "Удаление типа энергосистемы", f"id={_id}, name={obj.name}")
        except IntegrityError:
            db.session.rollback()
            failed += 1
            log_to_db(user, "Удаление невозможно (FK)", f"id={_id}, name={obj.name}")
    return ok, failed

def export_energy_system_types(energy_system_type_filter: Optional[str], sort_by: str, sort_dir: str) -> BytesIO:
    """Генерация Excel с учётом фильтров/сортировки."""
    query = EnergySystemType.query
    if energy_system_type_filter:
        like = f"%{energy_system_type_filter.strip()}%"
        query = query.filter(EnergySystemType.name.ilike(like))

    query = _apply_sort(query, sort_by, sort_dir)
    rows = query.all()

    data = [ {"ID": r.id, "Наименование типа энергосистемы": r.name} for r in rows ]
    df = pd.DataFrame(data, columns=["ID", "Наименование типа энергосистемы"])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Типы энергосистем", index=False)
    output.seek(0)
    return output



# --- Адаптеры имен для совместимости с роутами ---
try:
    # Локальный импорт класса пагинации, чтобы вернуть именно тот объект, который ожидают роуты/шаблоны
    from app.common.models.pagination import Pagination  # type: ignore
except Exception:
    Pagination = None  # на случай изоляции тестов

def get_energy_system_type_list(page, per_page, energy_system_type_filter=None, sort_by="id", sort_dir="asc"):
    """Обёртка: вернуть Pagination, как ожидает роут."""
    items, total = get_energy_system_types(
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by, sort_dir=sort_dir,
        page=page, per_page=per_page
    )
    if Pagination is not None:
        pagination = Pagination(page=page, per_page=per_page, total=total)
        # большинство реализаций Pagination позволяют класть items вручную
        setattr(pagination, "items", items)
        return pagination
    # запасной путь: вернуть кортеж (items, total)
    return type("SimplePagination", (), {"items": items, "page": page, "per_page": per_page, "total": total})()

def update_energy_system_type_service(energy_system_type_data, user):
    """Обёртка: преобразует список словарей в ids/names для массового обновления."""
    ids, names = [], []
    for rec in energy_system_type_data or []:
        ids.append(rec.get("id"))
        names.append((rec.get("name") or "").strip())
    return update_energy_system_types(ids, names, user)

def delete_energy_system_type_service(ids, user):
    """Обёртка под delete_*_list сигнатуру."""
    return delete_energy_system_types(ids, user)

def export_energy_system_type_to_excel_service(user=None, energy_system_type_filter=None, sort_by="id", sort_dir="asc"):
    """Обёртка экспорта; user не используется, оставлен для унификации сигнатуры с роутами."""
    return export_energy_system_types(
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by, sort_dir=sort_dir
    )

# Совместимое имя с другими сервисами (если роут ожидает get_total_with_filter)
def get_total_with_filter(filter_value=None):
    return get_total_energy_system_type_records(filter_value)


__all__ = [
    "_apply_sort",
    "get_energy_system_types",
    "get_total_energy_system_type_records",
    "add_energy_system_type",
    "update_energy_system_types",
    "delete_energy_system_types",
    "export_energy_system_types",
    # адаптеры для роутов
    "get_energy_system_type_list",
    "update_energy_system_type",
    "delete_energy_system_type_list",
    "export_energy_system_type_to_excel",
    "get_total_with_filter",
]
