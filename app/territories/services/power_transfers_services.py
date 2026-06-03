# -*- coding: utf-8 -*-
"""Сервисы перетоков мощности энергоузлов."""

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.territories.models.energy_unit_power_transfer_model import EnergyUnitPowerTransfer
from app.territories.models.energy_unit_power_transfer_value_model import (
    EnergyUnitPowerTransferValue,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_ges_tep_current_price_year_number,
    get_year_numbers_sorted_for_current_db_version,
)
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_list_full,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
)
from app.common.services.help_services import _to_int_or_none
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)
from app.logs.services.logging_service import log_to_db
from config import SCHEMA_TERRITORIES

ENTITY_TYPE = "energy_unit_power_transfer"


def _power_transfer_period_base_year_n() -> int:
    """N для окна N−9…N (как на сводке потребления)."""
    n = get_ges_tep_current_price_year_number()
    if n is not None:
        return int(n)
    return int(get_filter_end_year())


def get_power_transfer_filter_year_list() -> list[int]:
    """Годы для выпадающих списков фильтра."""
    nums = get_year_numbers_sorted_for_current_db_version()
    if nums:
        return nums
    n = _power_transfer_period_base_year_n()
    return list(range(n - 20, n + 21))


def get_power_transfer_default_year_range() -> tuple[int, int]:
    """Период по умолчанию: отчётное окно N−9…N."""
    bounds = get_power_transfer_filter_year_list()
    n = _power_transfer_period_base_year_n()
    default_sy = n - 9
    default_ey = n
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        default_sy = max(lo, min(default_sy, hi))
        default_ey = max(lo, min(default_ey, hi))
        if default_sy > default_ey:
            default_sy, default_ey = default_ey, default_sy
    return default_sy, default_ey


def parse_power_transfer_year_range(
    request_args,
    *,
    form_start_year: Any = None,
    form_end_year: Any = None,
) -> tuple[int, int]:
    """Разбор start_year / end_year из запроса или формы."""
    default_sy, default_ey = get_power_transfer_default_year_range()
    bounds = get_power_transfer_filter_year_list()
    lo = bounds[0] if bounds else default_sy
    hi = bounds[-1] if bounds else default_ey

    def _read(raw: Any, default: int) -> int:
        if raw in (None, ""):
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    if form_start_year is not None or form_end_year is not None:
        sy = _read(form_start_year, default_sy)
        ey = _read(form_end_year, default_ey)
    else:
        sy = _read(request_args.get("start_year"), default_sy)
        ey = _read(request_args.get("end_year"), default_ey)

    sy = max(lo, min(sy, hi))
    ey = max(lo, min(ey, hi))
    if sy > ey:
        sy, ey = ey, sy
    return sy, ey


def power_transfer_display_years(start_year: int, end_year: int) -> list[int]:
    return list(range(start_year, end_year + 1))


def power_transfer_year_field_name(transfer_id: int, year: int) -> str:
    """Имя поля формы для transfer_mln_kvt_ch (EnergyUnitPowerTransferValue)."""
    return f"transfer_mln_{transfer_id}_{year}"


def parse_decimal_field(value: Any, *, strict: bool = False) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        if strict:
            raise ValueError(f"Некорректное числовое значение: «{value}»") from None
        return None


def load_power_transfer_year_values_map(
    transfer_ids: list[int],
    years: list[int],
) -> dict[int, dict[int, Decimal | None]]:
    """{transfer_id: {year: value}} для отображения в таблице."""
    if not transfer_ids or not years:
        return {}

    rows = (
        EnergyUnitPowerTransferValue.query.filter(
            EnergyUnitPowerTransferValue.id_energy_unit_power_transfer.in_(
                transfer_ids
            ),
            EnergyUnitPowerTransferValue.year_number.in_(years),
        )
    )
    rows = apply_version_filter(rows, EnergyUnitPowerTransferValue).all()

    result: dict[int, dict[int, Decimal | None]] = {
        tid: {y: None for y in years} for tid in transfer_ids
    }
    for row in rows:
        tid = row.id_energy_unit_power_transfer
        if tid in result:
            result[tid][row.year_number] = row.transfer_mln_kvt_ch
    return result


def extract_power_transfer_year_values_from_form(
    form_data,
    transfer_ids: list[int],
    years: list[int],
) -> dict[int, dict[int, Decimal | None]]:
    """
    Собирает значения для EnergyUnitPowerTransferValue.transfer_mln_kvt_ch
    из полей transfer_mln_{id перетока}_{год}.
    """
    result: dict[int, dict[int, Decimal | None]] = {}
    for tid in transfer_ids:
        for year in years:
            field = power_transfer_year_field_name(tid, year)
            raw = form_data.get(field)
            if raw in (None, ""):
                parsed = None
            else:
                parsed = parse_decimal_field(raw, strict=True)
            result.setdefault(tid, {})[year] = parsed
    return result


# обратная совместимость
_extract_year_values_from_form = extract_power_transfer_year_values_from_form


@no_autoflush
def update_power_transfer_year_values_service(
    transfer_ids: list[int],
    years: list[int],
    values_by_transfer: dict[int, dict[int, Decimal | None]],
    user: str,
) -> None:
    """Создание/обновление/удаление значений перетока по годам."""
    if not transfer_ids or not years:
        return

    existing_rows = (
        EnergyUnitPowerTransferValue.query.filter(
            EnergyUnitPowerTransferValue.id_energy_unit_power_transfer.in_(
                transfer_ids
            ),
            EnergyUnitPowerTransferValue.year_number.in_(years),
        )
    )
    existing_rows = apply_version_filter(
        existing_rows, EnergyUnitPowerTransferValue
    ).all()

    by_key: dict[tuple[int, int], EnergyUnitPowerTransferValue] = {
        (r.id_energy_unit_power_transfer, r.year_number): r for r in existing_rows
    }

    with db.session.no_autoflush:
        for tid in transfer_ids:
            year_map = values_by_transfer.get(tid, {})
            for year in years:
                new_val = year_map.get(year)
                key = (tid, year)
                obj = by_key.get(key)
                if new_val is None:
                    if obj is not None:
                        db.session.delete(obj)
                        log_to_db(
                            user,
                            f"Удалено значение перетока id={tid} за {year} г.",
                            entity_type=ENTITY_TYPE,
                            entity_id=tid,
                        )
                    continue
                if obj is None:
                    obj = EnergyUnitPowerTransferValue(
                        id_energy_unit_power_transfer=tid,
                        year_number=year,
                        transfer_mln_kvt_ch=new_val,
                    )
                    set_db_version_on_create(obj)
                    db.session.add(obj)
                    log_to_db(
                        user,
                        f"Добавлено значение перетока id={tid} за {year} г.",
                        f"{new_val}",
                        entity_type=ENTITY_TYPE,
                        entity_id=tid,
                    )
                elif obj.transfer_mln_kvt_ch != new_val:
                    old = obj.transfer_mln_kvt_ch
                    obj.transfer_mln_kvt_ch = new_val
                    log_to_db(
                        user,
                        f"Обновлено значение перетока id={tid} за {year} г.",
                        f"{old} → {new_val}",
                        entity_type=ENTITY_TYPE,
                        entity_id=tid,
                    )


def get_power_transfer_choice_lists() -> dict[str, list]:
    """Списки для выпадающих списков (энергоузел, субъект РФ)."""
    energy_units = get_energy_unit_list_full()
    energy_unit_list = [(eu.id, eu.name) for eu in energy_units if eu.id and eu.id > 0]
    regional_district_list = get_regional_district_list_full()
    return {
        "energy_unit_list": energy_unit_list,
        "regional_district_list": regional_district_list,
    }


def power_transfer_query(
    power_transfer_filter: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
):
    """Базовый запрос списка перетоков с фильтрацией и сортировкой."""
    allowed_sort_by = {"id", "energy_unit", "regional_district", "direction"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"
    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = EnergyUnitPowerTransfer.query.options(
        joinedload(EnergyUnitPowerTransfer.energy_unit),
        joinedload(EnergyUnitPowerTransfer.regional_district),
    )
    query = apply_version_filter(query, EnergyUnitPowerTransfer)

    eu_joined = False
    rd_joined = False

    def _join_energy_unit(q):
        nonlocal eu_joined
        if not eu_joined:
            q = q.join(
                EnergyUnit,
                EnergyUnitPowerTransfer.id_energy_unit == EnergyUnit.id,
            )
            eu_joined = True
        return q

    def _join_regional_district(q):
        nonlocal rd_joined
        if not rd_joined:
            q = q.join(
                RegionalDistrict,
                EnergyUnitPowerTransfer.id_regional_district == RegionalDistrict.id,
            )
            rd_joined = True
        return q

    if power_transfer_filter:
        pattern = f"%{power_transfer_filter.strip()}%"
        query = _join_energy_unit(query)
        query = _join_regional_district(query)
        query = query.filter(
            or_(
                EnergyUnit.name.ilike(pattern),
                RegionalDistrict.name.ilike(pattern),
                EnergyUnitPowerTransfer.direction.ilike(pattern),
            )
        )

    if sort_by == "energy_unit":
        query = _join_energy_unit(query)
        sort_field = EnergyUnit.name
    elif sort_by == "regional_district":
        query = _join_regional_district(query)
        sort_field = RegionalDistrict.name
    elif sort_by == "direction":
        sort_field = EnergyUnitPowerTransfer.direction
    else:
        sort_field = EnergyUnitPowerTransfer.id

    query = query.order_by(
        sort_field.desc() if sort_dir == "desc" else sort_field.asc()
    )
    return query


@no_autoflush
def get_power_transfer_list(
    page: int,
    per_page: int,
    power_transfer_filter: str | None = None,
    sort_by: str = "id",
    sort_dir: str = "asc",
):
    """Список перетоков с пагинацией."""
    query = power_transfer_query(
        power_transfer_filter=power_transfer_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def _validate_fk_ids(id_energy_unit: int | None, id_regional_district: int | None) -> None:
    if not id_energy_unit or id_energy_unit <= 0:
        raise ValueError("Укажите энергоузел.")
    if not id_regional_district or id_regional_district <= 0:
        raise ValueError("Укажите субъект РФ.")

    eu = db.session.get(EnergyUnit, id_energy_unit)
    if not eu:
        raise ValueError(f"Энергоузел с ID={id_energy_unit} не найден.")

    rd = db.session.get(RegionalDistrict, id_regional_district)
    if not rd:
        raise ValueError(f"Субъект РФ с ID={id_regional_district} не найден.")


@no_autoflush
def update_power_transfer_service(
    data: list[dict[str, Any]],
    user: str,
    *,
    year_values_by_transfer: dict[int, dict[int, Decimal | None]] | None = None,
    display_years: list[int] | None = None,
) -> list[int]:
    """Обновление записей перетоков."""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids: list[int] = []
    log_to_db(
        user,
        "Получены данные для обновления перетоков мощности",
        f"{data}",
        entity_type=ENTITY_TYPE,
    )

    with db.session.no_autoflush:
        for record in data:
            record_id = record.get("power_transfer_id")
            id_energy_unit = _to_int_or_none(record.get("id_energy_unit"), keep_zero=False)
            id_regional_district = _to_int_or_none(
                record.get("id_regional_district"), keep_zero=False
            )
            direction = (record.get("direction") or "").strip() or None

            _validate_fk_ids(id_energy_unit, id_regional_district)

            obj = db.session.get(EnergyUnitPowerTransfer, record_id)
            if not obj:
                raise ValueError(f"Запись с ID «{record_id}» не найдена.")

            changes = []
            if obj.id_energy_unit != id_energy_unit:
                changes.append(
                    f"Энергоузел: {obj.id_energy_unit} → {id_energy_unit}"
                )
                obj.id_energy_unit = id_energy_unit

            if obj.id_regional_district != id_regional_district:
                changes.append(
                    f"Субъект РФ: {obj.id_regional_district} → {id_regional_district}"
                )
                obj.id_regional_district = id_regional_district

            old_direction = (obj.direction or "").strip()
            new_direction = direction or ""
            if old_direction != new_direction:
                changes.append(f"Направление: {old_direction or '—'} → {new_direction or '—'}")
                obj.direction = direction

            if changes:
                log_to_db(
                    user,
                    f"Обновлён переток мощности id={record_id}",
                    "; ".join(changes),
                    entity_type=ENTITY_TYPE,
                    entity_id=record_id,
                )
                updated_ids.append(record_id)

        if year_values_by_transfer is not None and display_years:
            active_ids = [
                int(r["power_transfer_id"])
                for r in data
                if r.get("power_transfer_id") is not None
            ]
            update_power_transfer_year_values_service(
                active_ids,
                display_years,
                year_values_by_transfer,
                user,
            )

        db.session.flush()

    try:
        _commit_with_retry()
        return updated_ids
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения перетоков (целостность)",
            str(e),
            entity_type=ENTITY_TYPE,
        )
        raise ValueError(
            "Ошибка сохранения данных. Проверьте выбранные энергоузел и субъект РФ."
        ) from e
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения перетоков",
            str(e),
            entity_type=ENTITY_TYPE,
        )
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}") from e


@no_autoflush
def add_power_transfer_service(data: list[dict[str, Any]], user: str) -> None:
    """Создание записей перетоков."""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert() -> None:
        with db.session.no_autoflush:
            for record in data:
                id_energy_unit = _to_int_or_none(
                    record.get("id_energy_unit"), keep_zero=False
                )
                id_regional_district = _to_int_or_none(
                    record.get("id_regional_district"), keep_zero=False
                )
                direction = (record.get("direction") or "").strip() or None

                _validate_fk_ids(id_energy_unit, id_regional_district)

                obj = EnergyUnitPowerTransfer(
                    id_energy_unit=id_energy_unit,
                    id_regional_district=id_regional_district,
                    direction=direction,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user,
                    "Создан переток мощности энергоузла",
                    (
                        f"Энергоузел ID={id_energy_unit}; "
                        f"Субъект РФ ID={id_regional_district}; "
                        f"Направление: {direction or '—'}"
                    ),
                    entity_type=ENTITY_TYPE,
                    entity_id=obj.id,
                )

    try:
        _do_insert()
        _commit_with_retry()
    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_TERRITORIES, "energy_unit_power_transfers")
        _do_insert()
        _commit_with_retry()
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка создания перетока мощности",
            str(e),
            entity_type=ENTITY_TYPE,
        )
        raise ValueError(f"Ошибка сохранения новой записи: {e}") from e


@no_autoflush
def delete_power_transfer_service(ids: list, user: str) -> dict[str, Any]:
    """Удаление записей перетоков по ID."""
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(
        user,
        "Удаление перетоков мощности",
        f"ID: {ids}",
        entity_type=ENTITY_TYPE,
    )

    successful_deletes = 0
    not_found: list[int] = []
    invalid: list[Any] = []

    for raw_id in ids:
        try:
            record_id = _to_int_or_none(raw_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(raw_id)
            continue

        obj = _locked_get(EnergyUnitPowerTransfer, record_id)
        if obj:
            db.session.delete(obj)
            successful_deletes += 1
            log_to_db(
                user,
                "Удалён переток мощности",
                f"ID={record_id}",
                entity_type=ENTITY_TYPE,
                entity_id=record_id,
            )
        else:
            not_found.append(record_id)

    try:
        _commit_with_retry()
        return {
            "deleted": successful_deletes,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка удаления перетоков",
            str(e),
            entity_type=ENTITY_TYPE,
        )
        raise ValueError("Ошибка при удалении данных.") from e
