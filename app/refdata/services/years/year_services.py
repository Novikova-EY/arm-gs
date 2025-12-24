"""Сервисный модуль: Справочник «Годы»."""

from sqlalchemy.exc import IntegrityError

from app.extensions import db

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature

# Сервисы/хелперы
from app.common.services.help_services import _to_int_or_none
from app.common.services.tranzaction_services import _commit_with_retry, no_autoflush
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change


def year_query(year_filter=None, sort_by="number", sort_dir="asc"):
    """Базовый запрос для выборки годов с фильтрацией и сортировкой (c привязкой к текущей версии БД)."""

    allowed_sort_by = {"id", "number", "year_feature"}
    sort_by = sort_by if sort_by in allowed_sort_by else "number"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = Year.query.filter(Year.id > 0)
    query = apply_version_filter(query, Year)

    yf = (year_filter or "").strip()
    need_join = False

    if yf:
        # Если похоже на число — фильтруем по году; иначе — по признаку.
        if yf.isdigit():
            query = query.filter(Year.number == int(yf))
        else:
            need_join = True
            query = query.outerjoin(YearFeature, Year.id_year_feature == YearFeature.id)
            query = query.filter(YearFeature.name.ilike(f"%{yf}%"))

    # Сортировка
    if sort_by == "year_feature":
        if not need_join:
            query = query.outerjoin(YearFeature, Year.id_year_feature == YearFeature.id)
        sort_col = YearFeature.name
    elif sort_by == "id":
        sort_col = Year.id
    else:
        sort_col = Year.number

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_year_list(page, per_page, year_filter=None, sort_by="number", sort_dir="asc"):
    """Получает список годов с пагинацией, фильтрацией и сортировкой."""
    query = year_query(
        year_filter=year_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_year_service(data, user):
    """Пакетное обновление годов."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user,
        "Получены данные для обновления списка годов",
        f"{data}",
        entity_type="year",
    )

    with db.session.no_autoflush:
        for record in data:
            year_id = _to_int_or_none(record.get("year_id"), keep_zero=False)
            number = _to_int_or_none(record.get("number"), keep_zero=False)
            feature_id = _to_int_or_none(record.get("year_feature_id"), keep_zero=False)

            if year_id is None:
                raise ValueError("Не указан ID записи года.")
            if number is None:
                raise ValueError("Поле «Год» обязательно для заполнения.")
            if number < 1900 or number > 2200:
                raise ValueError("Год должен быть в диапазоне 1900–2200.")
            if feature_id is None:
                raise ValueError("Выберите признак года.")

            obj = db.session.get(Year, year_id)
            if not obj:
                raise ValueError(f"Запись с ID «{year_id}» не найдена.")

            # Уникальность года в рамках версии БД
            if number != obj.number:
                q = (
                    apply_version_filter(Year.query, Year)
                    .filter(Year.number == number, Year.id != year_id)
                )
                if q.first():
                    raise ValueError(f"Год «{number}» уже существует в текущей версии БД.")

            # Проверяем, что признак существует в текущей версии БД
            feature = (
                apply_version_filter(YearFeature.query, YearFeature)
                .filter(YearFeature.id == feature_id)
                .first()
            )
            if not feature:
                raise ValueError("Выбранный признак года не найден для текущей версии БД.")

            changes = []

            if number != obj.number:
                changes.append(format_field_change("number", obj.number, number, "year"))
                obj.number = number

            if feature_id != obj.id_year_feature:
                old_name = obj.year_feature.name if obj.year_feature else "не указано"
                new_name = feature.name
                changes.append(format_field_change("id_year_feature", old_name, new_name, "year"))
                obj.id_year_feature = feature_id

            if changes:
                log_to_db(
                    user,
                    f"Обновлен год: {obj.number}",
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="year",
                    entity_id=year_id,
                )
                updated_ids.append(year_id)

        db.session.flush()

    try:
        _commit_with_retry()
        return updated_ids
    except IntegrityError as e:
        db.session.rollback()
        raise ValueError(
            "Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи."
        ) from e
    except Exception as e:
        db.session.rollback()
        raise


@no_autoflush
def add_year_service(payload, user):
    """Добавление нового года (в текущую активную версию БД)."""

    if not isinstance(payload, list) or not payload:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка.")

    created_ids = []

    with db.session.no_autoflush:
        for record in payload:
            number = _to_int_or_none(record.get("number"), keep_zero=False)
            feature_id = _to_int_or_none(record.get("year_feature_id"), keep_zero=False)

            if number is None:
                raise ValueError("Поле «Год» обязательно для заполнения.")
            if number < 1900 or number > 2200:
                raise ValueError("Год должен быть в диапазоне 1900–2200.")
            if feature_id is None:
                raise ValueError("Выберите признак года.")

            # Проверяем признак в текущей версии
            feature = (
                apply_version_filter(YearFeature.query, YearFeature)
                .filter(YearFeature.id == feature_id)
                .first()
            )
            if not feature:
                raise ValueError("Выбранный признак года не найден для текущей версии БД.")

            # Проверка уникальности года в текущей версии
            exists = (
                apply_version_filter(Year.query, Year)
                .filter(Year.number == number)
                .first()
            )
            if exists:
                raise ValueError(f"Год «{number}» уже существует в текущей версии БД.")

            obj = Year(number=number, id_year_feature=feature_id)
            set_db_version_on_create(obj)

            db.session.add(obj)
            db.session.flush()
            created_ids.append(obj.id)

            log_to_db(
                user,
                f"Добавлен год: {number}",
                f"Признак: {feature.name}",
                entity_type="year",
                entity_id=obj.id,
            )

        db.session.flush()

    _commit_with_retry()
    return created_ids


@no_autoflush
def delete_year_service(ids, user):
    """Удаление годов по списку ID (в текущей версии БД)."""

    if not ids:
        return 0

    id_list = []
    for x in ids:
        v = _to_int_or_none(x, keep_zero=False)
        if v is not None:
            id_list.append(v)

    if not id_list:
        return 0

    # Берем только записи текущей версии
    q = apply_version_filter(Year.query, Year).filter(Year.id.in_(id_list))
    objects = q.all()

    found_ids = {o.id for o in objects}
    missing = [i for i in id_list if i not in found_ids]
    if missing:
        raise ValueError(f"Записи годов не найдены (или не относятся к текущей версии БД): {missing}")

    for obj in objects:
        log_to_db(
            user,
            f"Удален год: {obj.number}",
            "",
            entity_type="year",
            entity_id=obj.id,
        )
        db.session.delete(obj)

    try:
        _commit_with_retry()
    except IntegrityError as e:
        db.session.rollback()
        raise ValueError("Невозможно удалить запись: есть связанные данные.") from e

    return len(objects)


