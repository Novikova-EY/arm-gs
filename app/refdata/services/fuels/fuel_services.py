"""Сервисный модуль: Типы топлива."""

import re
from difflib import SequenceMatcher
from io import BytesIO

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload, aliased

from app.extensions import db
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
    parent_filter=None,
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
    parent_id = _to_int_or_none(parent_filter, keep_zero=True)

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

    # Фильтр по родительскому виду (0 / «корень» → без родителя)
    if parent_id is not None:
        if parent_id == 0:
            query = query.filter(Fuel.parent_id.is_(None))
        else:
            query = query.filter(Fuel.parent_id == parent_id)

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
    sort_dir="asc",
    parent_filter=None):
    """ Получает список типов топлива с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = fuel_query(
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        nazvl_filter=nazvl_filter,
        kmbur_filter=kmbur_filter,
        parent_filter=parent_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    ).options(joinedload(Fuel.fuel_type), joinedload(Fuel.parent))

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


def get_fuel_hierarchy_tree():
    """
    Дерево видов топлива текущей версии БД:
    верхний уровень — тип топлива, далее иерархия по parent_id.
    """
    fuels = (
        apply_version_filter(Fuel.query, Fuel)
        .filter(Fuel.id > 0)
        .options(joinedload(Fuel.fuel_type))
        .order_by(Fuel.name.asc())
        .all()
    )
    nodes = {
        f.id: {
            "id": f.id,
            "kod": f.kod,
            "name": f.name,
            "nazvl": f.nazvl,
            "parent_id": f.parent_id,
            "fuel_type_id": f.id_fuel_type,
            "fuel_type": (getattr(f.fuel_type, "name", None) if f.fuel_type else None) or "не указано",
            "children": [],
            "node_kind": "fuel",
        }
        for f in fuels
    }
    roots = []
    for node in nodes.values():
        parent_id = node["parent_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    def _sort_nodes(items):
        # Агрегации и дочерние узлы — по названию (без учёта регистра)
        items.sort(key=lambda n: (n.get("name") or "").casefold())
        for child in items:
            _sort_nodes(child.get("children") or [])

    _sort_nodes(roots)

    # Группировка корней по типу топлива (верхний уровень иерархии)
    groups_map: dict[str, dict] = {}
    for root in roots:
        type_name = root.get("fuel_type") or "не указано"
        type_id = root.get("fuel_type_id")
        group_key = f"{type_id if type_id is not None else 'none'}::{type_name}"
        if group_key not in groups_map:
            groups_map[group_key] = {
                "id": f"type-{type_id if type_id is not None else 'none'}",
                "kod": None,
                "name": type_name,
                "nazvl": None,
                "parent_id": None,
                "fuel_type_id": type_id,
                "fuel_type": type_name,
                "children": [],
                "node_kind": "fuel_type",
            }
        groups_map[group_key]["children"].append(root)

    grouped_roots = list(groups_map.values())
    grouped_roots.sort(key=lambda g: (g["name"] or "").casefold())
    for group in grouped_roots:
        _sort_nodes(group["children"])

    return {
        "roots": grouped_roots,
        "total": len(fuels),
        "roots_count": len(roots),
        "fuel_types_count": len(grouped_roots),
    }


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
            nazvl = _normalize_fuel_nazvl(record.get("nazvl"))
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
                    nazvl=_normalize_fuel_nazvl(record.get("nazvl")),
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


def _normalize_fuel_match_text(value) -> str:
    """Нормализация строки для сопоставления Excel ↔ Вид топлива."""
    text = str(value or "").strip().casefold().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" ,", ",").replace(", ", ",")
    return text.strip(" ,")


def _normalize_fuel_nazvl(value) -> str | None:
    """Наименование в БД Топливо — только строчными буквами."""
    text = str(value or "").strip()
    if not text:
        return None
    return text.lower()


def _fuel_name_without_ugol_prefix(name: str) -> str:
    text = _normalize_fuel_match_text(name)
    for prefix in ("уголь ", "угли "):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _parse_fuel_composition_excel(file) -> list[dict]:
    """
    Читает шаблон «Состав видов топлива.xlsx» (Kod, NazvR, NazvL, Pred).
    """
    data = pd.read_excel(file)
    columns = {str(c).strip(): c for c in data.columns}
    required = ("Kod", "NazvR", "NazvL", "Pred")
    missing = [name for name in required if name not in columns]
    if missing:
        raise ValueError(
            "Неверный формат файла. Ожидаются столбцы Kod, NazvR, NazvL, Pred. "
            f"Отсутствуют: {', '.join(missing)}."
        )

    rows: list[dict] = []
    for _, row in data.iterrows():
        nazvr = row[columns["NazvR"]]
        if pd.isna(nazvr) or not str(nazvr).strip():
            continue
        kod = _to_int_or_none(row[columns["Kod"]], keep_zero=True)
        if kod is None:
            raise ValueError(f"В строке с NazvR={nazvr!r} отсутствует Kod.")
        nazvl_raw = row[columns["NazvL"]]
        nazvl = None if pd.isna(nazvl_raw) else _normalize_fuel_nazvl(nazvl_raw)
        pred = _to_int_or_none(row[columns["Pred"]], keep_zero=True)
        rows.append(
            {
                "kod": kod,
                "nazvr": str(nazvr).strip(),
                "nazvl": nazvl,
                "pred": pred,
            }
        )
    if not rows:
        raise ValueError("В файле нет строк для импорта.")
    return rows


def _match_excel_row_to_fuel(excel_row: dict, fuels: list, used_ids: set[int]):
    """
    Ищет похожее соответствие NazvR → Fuel.name (Вид топлива не меняем).
    Дополнительно использует NazvL ↔ nazvl как точный ключ.
    """
    nazvr_n = _normalize_fuel_match_text(excel_row["nazvr"])
    nazvl_n = _normalize_fuel_match_text(excel_row["nazvl"])
    candidates: list[tuple[float, object]] = []

    for fuel in fuels:
        if fuel.id in used_ids:
            continue
        name_n = _normalize_fuel_match_text(fuel.name)
        name_core = _fuel_name_without_ugol_prefix(fuel.name)
        fuel_nazvl_n = _normalize_fuel_match_text(fuel.nazvl)

        score = None
        if nazvl_n and fuel_nazvl_n and nazvl_n == fuel_nazvl_n:
            score = 100.0
        elif name_n == nazvr_n:
            score = 95.0
        elif name_core == nazvr_n:
            score = 92.0
        else:
            ratio = SequenceMatcher(None, nazvr_n, name_core).ratio()
            if ratio >= 0.88:
                score = 70.0 + ratio * 20.0
            elif nazvr_n and (
                name_n.startswith(nazvr_n + " ")
                or name_core.startswith(nazvr_n + " ")
                or (len(nazvr_n) >= 6 and nazvr_n in name_core)
            ):
                # Предпочитаем более короткое имя (избегаем «амурский» → «...средне-амурский»)
                score = 80.0 - abs(len(name_core) - len(nazvr_n)) * 0.5

        if score is not None:
            candidates.append((score, fuel))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], len(item[1].name or "")))
    best_score, best_fuel = candidates[0]
    if best_score < 70.0:
        return None
    return best_fuel


def _default_fuel_type_id_for_version(version_id: int) -> int:
    """Тип топлива по умолчанию для новых записей импорта («не указано»)."""
    from app.common.services.database_version_filter import filter_by_explicit_db_version

    q = filter_by_explicit_db_version(FuelType.query, FuelType, version_id)
    ft = q.filter(FuelType.name == "не указано").first()
    if not ft:
        ft = q.order_by(FuelType.id.asc()).first()
    if not ft:
        raise ValueError(
            f"В версии БД id={version_id} нет типов топлива — нельзя создать новые виды."
        )
    return int(ft.id)


def import_fuel_service(file, user):
    """
    Импорт из Excel «Состав видов топлива» во все версии БД.

    Сопоставление по похожему NazvR ↔ поле «Вид топлива» (name) — name не меняется.
    Kod → kod, NazvL → nazvl, Pred → parent_id (через Kod родителя; Pred=-1 → корень).
    Несопоставленные строки добавляются как новые записи (name = NazvR).
    """
    from app.refdata.services.refdata_all_versions_common import (
        all_database_version_ids_for_refdata,
        new_shared_ref_uuid,
    )
    from app.common.services.choices_cache_service import choices_cache

    try:
        excel_rows = _parse_fuel_composition_excel(file)
        version_ids = all_database_version_ids_for_refdata()
        if not version_ids:
            raise ValueError(
                "В системе нет зарегистрированных версий БД — импорт во все версии невозможен."
            )

        total_updated = 0
        total_created = 0
        created_rows: list[dict] = []
        versions_touched = 0
        # общий ref_uuid для одной и той же новой строки Excel во всех версиях
        ref_uuid_by_nazvr: dict[str, str] = {}

        with db.session.no_autoflush:
            for version_id in version_ids:
                fuels = (
                    Fuel.query.filter(Fuel.database_version_id == version_id)
                    .order_by(Fuel.id)
                    .all()
                )

                used_ids: set[int] = set()
                matched: list[tuple[dict, object]] = []
                to_create: list[dict] = []

                fuzzy_pending: list[dict] = []
                for excel_row in excel_rows:
                    nazvr_n = _normalize_fuel_match_text(excel_row["nazvr"])
                    nazvl_n = _normalize_fuel_match_text(excel_row["nazvl"])
                    exact = None
                    for fuel in fuels:
                        if fuel.id in used_ids:
                            continue
                        if nazvl_n and _normalize_fuel_match_text(fuel.nazvl) == nazvl_n:
                            exact = fuel
                            break
                        if _normalize_fuel_match_text(fuel.name) == nazvr_n:
                            exact = fuel
                            break
                        if _fuel_name_without_ugol_prefix(fuel.name) == nazvr_n:
                            exact = fuel
                            break
                    if exact is not None:
                        used_ids.add(exact.id)
                        matched.append((excel_row, exact))
                    else:
                        fuzzy_pending.append(excel_row)

                for excel_row in fuzzy_pending:
                    fuel = _match_excel_row_to_fuel(excel_row, fuels, used_ids)
                    if fuel is None:
                        to_create.append(excel_row)
                        continue
                    used_ids.add(fuel.id)
                    matched.append((excel_row, fuel))

                if not matched and not to_create:
                    continue

                versions_touched += 1
                created_in_version: list[tuple[dict, object]] = []

                if to_create:
                    default_type_id = _default_fuel_type_id_for_version(version_id)
                    existing_names = {
                        _normalize_fuel_match_text(f.name) for f in fuels
                    }
                    for excel_row in to_create:
                        name = (excel_row["nazvr"] or "").strip()
                        if not name:
                            continue
                        name_key = _normalize_fuel_match_text(name)
                        if name_key in existing_names:
                            # имя уже есть в версии, но не сопоставилось эвристикой — пропускаем создание
                            continue
                        if name not in ref_uuid_by_nazvr:
                            other = (
                                Fuel.query.filter(
                                    Fuel.name == name,
                                    Fuel.ref_uuid.isnot(None),
                                )
                                .order_by(Fuel.id.asc())
                                .first()
                            )
                            ref_uuid_by_nazvr[name] = (
                                other.ref_uuid if other and other.ref_uuid else new_shared_ref_uuid()
                            )
                        obj = Fuel(
                            name=name,
                            kod=excel_row["kod"],
                            nazvl=_normalize_fuel_nazvl(excel_row["nazvl"]),
                            id_fuel_type=default_type_id,
                            parent_id=None,
                            database_version_id=version_id,
                            ref_uuid=ref_uuid_by_nazvr[name],
                        )
                        db.session.add(obj)
                        db.session.flush()
                        fuels.append(obj)
                        existing_names.add(name_key)
                        created_in_version.append((excel_row, obj))
                        total_created += 1
                        log_to_db(
                            user,
                            f"Импорт Excel: создано топливо «{name}» (версия {version_id})",
                            (
                                f"Код: {excel_row['kod'] if excel_row['kod'] is not None else 'не указано'}; "
                                f"NazvL: {excel_row['nazvl'] or 'не указано'}; "
                                f"Тип топлива: не указано"
                            ),
                            entity_type="fuel",
                            entity_id=obj.id,
                        )
                    if created_in_version and not created_rows:
                        created_rows = [
                            {
                                "kod": er["kod"],
                                "nazvr": er["nazvr"],
                                "nazvl": er["nazvl"],
                            }
                            for er, _ in created_in_version
                        ]

                # Сброс родителей у обновляемых/созданных — безопасная перестройка иерархии
                for _, fuel in matched + created_in_version:
                    fuel.parent_id = None
                db.session.flush()

                # 1) kod + nazvl для сопоставленных (поле name не меняем)
                for excel_row, fuel in matched:
                    new_kod = excel_row["kod"]
                    new_nazvl = _normalize_fuel_nazvl(excel_row["nazvl"])
                    changes = []
                    if new_kod != fuel.kod:
                        changes.append(
                            format_field_change(
                                "kod",
                                fuel.kod if fuel.kod is not None else "не указано",
                                new_kod if new_kod is not None else "не указано",
                                "fuel",
                            )
                        )
                        fuel.kod = new_kod
                    if new_nazvl != fuel.nazvl:
                        changes.append(
                            format_field_change(
                                "nazvl",
                                fuel.nazvl or "не указано",
                                new_nazvl or "не указано",
                                "fuel",
                            )
                        )
                        fuel.nazvl = new_nazvl
                    if changes:
                        log_to_db(
                            user,
                            f"Импорт Excel: обновлено топливо «{fuel.name}» (версия {version_id})",
                            f"Изменения: {'; '.join(changes)}",
                            entity_type="fuel",
                            entity_id=fuel.id,
                        )
                    total_updated += 1

                db.session.flush()

                kod_to_id = {f.kod: f.id for f in fuels if f.kod is not None}

                # 2) Pred → parent_id по Kod родителя (-1 / отсутствует → корень)
                for excel_row, fuel in matched + created_in_version:
                    pred = excel_row["pred"]
                    if pred is None or pred < 0:
                        continue
                    new_parent_id = kod_to_id.get(pred)
                    if new_parent_id is None:
                        continue
                    _assert_valid_fuel_parent(fuel.id, new_parent_id)
                    new_parent = db.session.get(Fuel, new_parent_id)
                    log_to_db(
                        user,
                        f"Импорт Excel: родитель для «{fuel.name}» (версия {version_id})",
                        format_field_change(
                            "parent_id",
                            "не указано",
                            new_parent.name if new_parent else "не указано",
                            "fuel",
                        ),
                        entity_type="fuel",
                        entity_id=fuel.id,
                    )
                    fuel.parent_id = new_parent_id

        _commit_with_retry()
        try:
            choices_cache.invalidate_cache(Fuel.__name__.lower())
        except Exception:
            pass

        created_labels = [
            (
                f"Kod={row['kod']}: {row['nazvr']}"
                + (f" ({row['nazvl']})" if row.get("nazvl") else "")
            )
            for row in created_rows
        ]
        created_kinds = len(created_rows)
        msg = (
            f"Импорт завершён: обновлено записей {total_updated}, "
            f"добавлено новых видов {created_kinds} "
            f"в {versions_touched} версиях БД."
        )
        hints = []
        if created_labels:
            hints.append(
                "Добавлены как новые (NazvR → Вид топлива):\n"
                + "\n".join(f"• {label}" for label in created_labels)
            )
        log_to_db(
            user,
            "Импорт состава видов топлива из Excel завершен",
            (
                f"Обновлено: {total_updated}; создано видов: {created_kinds} "
                f"({total_created} строк по версиям); версий: {versions_touched}"
                + (f"; новые: {'; '.join(created_labels[:10])}" if created_labels else "")
            ),
            entity_type="fuel",
        )
        return {
            "ok": True,
            "updated": total_updated,
            "created": created_kinds,
            "created_rows_total": total_created,
            "versions": versions_touched,
            "skipped": 0,
            "unmatched_rows": [],
            "unmatched_names": [],
            "created_rows": created_rows,
            "created_names": created_labels,
            "message": msg,
            "hints": hints,
        }
    except ValueError:
        db.session.rollback()
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта", str(e), entity_type="fuel")
        raise ValueError(f"Ошибка при импорте данных: {e}") from e


def build_fuel_import_payload(result) -> dict:
    """Единый ответ импорта для JSON/flash (как на сводке ОЭС)."""
    if not isinstance(result, dict):
        result = {"updated": result or 0, "versions": 0, "skipped": 0, "unmatched_names": []}
    updated = result.get("updated", 0)
    created = result.get("created", 0)
    versions = result.get("versions", 0)
    skipped = result.get("skipped", 0)
    unmatched = result.get("unmatched_names") or []
    created_names = result.get("created_names") or []
    message = result.get("message") or (
        f"Импорт завершён: обновлено записей {updated}"
        + (f", добавлено новых {created}" if created else "")
        + f" в {versions} версиях БД."
    )
    hints = list(result.get("hints") or [])
    if not hints and created_names:
        hints.append(
            "Добавлены как новые (NazvR → Вид топлива):\n"
            + "\n".join(f"• {label}" for label in created_names)
        )
    if not hints and unmatched:
        hints.append(
            "Не сопоставлены строки Excel (NazvR ↔ Вид топлива):\n"
            + "\n".join(f"• {label}" for label in unmatched)
        )
    elif skipped and not unmatched and not created_names and "Не сопоставлено" not in message:
        message += f" Не сопоставлено строк Excel: {skipped}."
    return {
        "ok": True,
        "message": message,
        "hints": hints,
        "updated": updated,
        "created": created,
        "versions": versions,
        "skipped": skipped,
        "unmatched_names": unmatched,
        "created_names": created_names,
    }


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
        nazvl = _normalize_fuel_nazvl(record.get("nazvl"))
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
        nazvl = _normalize_fuel_nazvl(record.get("nazvl"))
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
