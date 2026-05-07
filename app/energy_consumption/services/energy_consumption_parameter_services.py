# -*- coding: utf-8 -*-
"""
CRUD и выборки для параметров потребления электроэнергии (app.energy_consumption, схема gs_ec).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional, Type

from flask import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.database_version_services import get_current_version
from app.common.services.get_services.years.years_get_services import get_year_list_full
from app.common.services.help_services import format_decimal_trim_for_display
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict

from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)


def _username() -> str:
    return session.get("username", "Неизвестный пользователь")


def parse_slice_year(raw: Any) -> tuple[bool, Optional[int]]:
    """
    Устаревший разбор для совместимости: для потребления год календарный; «hist» не используется.
    """
    s = str(raw or "").strip()
    if s == "hist":
        return True, None
    if not s:
        return False, None
    if s.isdigit():
        return False, int(s)
    return False, None


def _decimal_round_half_up_to_int(val: Any) -> Optional[Decimal]:
    """Целое значение (до ближайшего целого, от половины вверх). Для None → None."""
    if val is None:
        return None
    try:
        d = val if isinstance(val, Decimal) else Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _is_energy_consumption_parameter_model(model: Type[Any]) -> bool:
    tbl = getattr(model, "__table__", None)
    if tbl is None:
        return False
    return "energy_consumption_mln_kvt_ch" in tbl.columns


def _parse_calendar_year_slice(raw: Any) -> Optional[int]:
    s = str(raw or "").strip()
    if not s or s == "hist" or not s.isdigit():
        return None
    return int(s)


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_peak_datetime(value: Any):
    """«ДД.ММ.ГГГГ ЧЧ:ММ» (мск) или одна строка «ГГГГ» → aware datetime. Несуществующие даты → None."""
    if value is None:
        return None
    s = None
    for line in str(value).splitlines():
        t = line.strip()
        if t:
            s = t
            break
    if not s:
        s = str(value).strip()
    if not s:
        return None
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    if re.fullmatch(r"\d{4}", s):
        y = int(s)
        if 1000 <= y <= 9999:
            return datetime(y, 1, 1, 0, 0, 0, tzinfo=msk)
        return None
    try:
        naive = datetime.strptime(s, "%d.%m.%Y %H:%M")
        return naive.replace(tzinfo=msk)
    except ValueError:
        return None


def _peak_datetime_as_msk(dt):
    if dt is None:
        return None
    from zoneinfo import ZoneInfo

    msk = ZoneInfo("Europe/Moscow")
    if dt.tzinfo is not None:
        return dt.astimezone(msk)
    return dt.replace(tzinfo=msk)


def _peak_datetime_is_year_only_msk(dt) -> bool:
    """Ввод «только год» сохраняется как 1 января 00:00 МСК — в столбце «исторический максимум» показываем год."""
    d = _peak_datetime_as_msk(dt)
    if d is None:
        return False
    return (
        d.month == 1
        and d.day == 1
        and d.hour == 0
        and d.minute == 0
        and d.second == 0
        and d.microsecond == 0
    )


def format_peak_datetime(dt) -> str:
    if dt is None:
        return ""
    try:
        dt = _peak_datetime_as_msk(dt)
        if dt is None:
            return ""
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(dt)


def format_peak_datetime_for_slice(dt, hist_slice: bool) -> str:
    """Сводка: в столбце «исторический максимум» для ввода только года — строка «ГГГГ», иначе как format_peak_datetime."""
    if dt is None:
        return ""
    if hist_slice and _peak_datetime_is_year_only_msk(dt):
        d = _peak_datetime_as_msk(dt)
        return str(d.year) if d is not None else ""
    return format_peak_datetime(dt)


def filter_parents_by_version(query, model):
    vid = get_current_version()
    if vid is not None and hasattr(model, "database_version_id"):
        query = query.filter(model.database_version_id == vid)
    return query


def year_dropdown_numbers(rows) -> list[int]:
    """
    Номера годов из справочника Years (текущая версия БД),
    плюс значения year_number из строк, которых нет в справочнике (устаревшие данные).
    """
    ref_years = get_year_list_full()
    ref_nums = {y.number for y in ref_years}
    extra: set[int] = set()
    for r in rows:
        yn = getattr(r, "year_number", None)
        if yn is not None and yn not in ref_nums:
            extra.add(int(yn))
    return sorted(ref_nums | extra)


def filter_demand_by_version(query, demand_model):
    vid = get_current_version()
    if vid is not None and hasattr(demand_model, "database_version_id"):
        query = query.filter(demand_model.database_version_id == vid)
    return query


def get_demand_rows(demand_model, fk_column_name: Optional[str], parent_id: Optional[int]):
    """
    Список строк параметров для родителя. fk_column_name=None — модель без FK (РФ целиком).
    """
    q = demand_model.query
    q = filter_demand_by_version(q, demand_model)
    if fk_column_name is not None and parent_id is not None:
        q = q.filter(getattr(demand_model, fk_column_name) == parent_id)
    order_parts = []
    if "is_historical_maximum" in demand_model.__table__.columns:
        order_parts.append(demand_model.is_historical_maximum.desc())
    order_parts.append(demand_model.year_number.asc().nullsfirst())
    rows = q.order_by(*order_parts).all()
    return rows


def _demand_rows_for_version(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    database_version_id: Optional[int],
) -> list[Any]:
    q = demand_model.query
    if database_version_id is not None and hasattr(demand_model, "database_version_id"):
        q = q.filter(demand_model.database_version_id == database_version_id)
    if fk_column_name is not None and parent_id is not None:
        q = q.filter(getattr(demand_model, fk_column_name) == parent_id)
    order_parts = []
    if "is_historical_maximum" in demand_model.__table__.columns:
        order_parts.append(demand_model.is_historical_maximum.desc())
    order_parts.append(demand_model.year_number.asc().nullsfirst())
    return q.order_by(*order_parts).all()


def _sum_non_null_decimals(values: list[Any]) -> Optional[Decimal]:
    acc: Optional[Decimal] = None
    for v in values:
        if v is None:
            continue
        try:
            d = v if isinstance(v, Decimal) else Decimal(str(v))
        except (InvalidOperation, TypeError, ValueError):
            continue
        acc = d if acc is None else acc + d
    return acc


def sync_energy_zone_consumption_aggregates(
    *,
    database_version_id: Optional[int] = None,
    id_energy_zone: Optional[int] = None,
    id_regional_energy_system: Optional[int] = None,
) -> None:
    """Пересчёт потребления по энергозоне как суммы показателей РЭС, входящих в зону (по субъектам зоны).

    Обновляет ``energy_consumption_mln_kvt_ch`` и ``energy_consumption_sipr_mln_kvt_ch`` в
    :class:`EnergyZoneEnergyConsumptionParameter`. Примечания к строкам не меняет.
    """
    vid = database_version_id if database_version_id is not None else get_current_version()

    def _filter_version(q, model: Type[Any]):
        if vid is not None and hasattr(model, "database_version_id"):
            q = q.filter(model.database_version_id == vid)
        return q

    ez_q = EnergyZone.query.options(selectinload(EnergyZone.regional_districts))
    ez_q = _filter_version(ez_q, EnergyZone)
    if id_energy_zone is not None:
        ez_q = ez_q.filter(EnergyZone.id == int(id_energy_zone))
    zones = list(ez_q.all())

    if id_regional_energy_system is not None:
        res_q = RegionalEnergySystem.query.filter(
            RegionalEnergySystem.id == int(id_regional_energy_system)
        )
        res_q = _filter_version(res_q, RegionalEnergySystem)
        res_obj = res_q.first()
        if res_obj is None:
            zones = []
        else:
            rd_ids_res = {rd.id for rd in res_obj.regional_districts}
            zones = [
                z
                for z in zones
                if rd_ids_res & {rd.id for rd in z.regional_districts}
            ]

    res_q = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_q = _filter_version(res_q, RegionalEnergySystem)
    all_res = list(res_q.all())

    user = _username()

    for ez in zones:
        zone_rd_ids = {rd.id for rd in ez.regional_districts}
        res_in_zone: list[RegionalEnergySystem] = []
        for res in all_res:
            if any(rd.id in zone_rd_ids for rd in res.regional_districts):
                res_in_zone.append(res)

        mln_by_year: dict[int, list[Any]] = {}
        sipr_by_year: dict[int, list[Any]] = {}
        for res in res_in_zone:
            for r in _demand_rows_for_version(
                RegionalEnergySystemEnergyConsumptionParameter,
                "id_regional_energy_system",
                res.id,
                vid,
            ):
                y = getattr(r, "year_number", None)
                if y is None:
                    continue
                yi = int(y)
                mln_by_year.setdefault(yi, []).append(
                    getattr(r, "energy_consumption_mln_kvt_ch", None)
                )
                sipr_by_year.setdefault(yi, []).append(
                    getattr(r, "energy_consumption_sipr_mln_kvt_ch", None)
                )

        existing_ez_rows = _demand_rows_for_version(
            EnergyZoneEnergyConsumptionParameter,
            "id_energy_zone",
            ez.id,
            vid,
        )
        existing_years = {
            int(r.year_number)
            for r in existing_ez_rows
            if getattr(r, "year_number", None) is not None
        }
        all_years = existing_years | set(mln_by_year.keys()) | set(sipr_by_year.keys())

        for y in sorted(all_years):
            sum_mln = _sum_non_null_decimals(mln_by_year.get(y, []))
            sum_sipr = _sum_non_null_decimals(sipr_by_year.get(y, []))
            row = next(
                (r for r in existing_ez_rows if getattr(r, "year_number", None) == y),
                None,
            )
            if row is None:
                if sum_mln is None and sum_sipr is None:
                    continue
                row = EnergyZoneEnergyConsumptionParameter()
                row.id_energy_zone = ez.id
                if vid is not None:
                    row.database_version_id = vid
                row.year_number = y
                row.created_by = user
                db.session.add(row)
                existing_ez_rows.append(row)

            row.energy_consumption_mln_kvt_ch = sum_mln
            row.energy_consumption_sipr_mln_kvt_ch = sum_sipr
            row.modified_by = user


def apply_version_to_row(row, demand_model):
    vid = get_current_version()
    if vid is not None and hasattr(demand_model, "database_version_id"):
        row.database_version_id = vid


def _field_nonempty(val: Any) -> bool:
    return bool(str(val or "").strip())


def _norm_num_str_for_compare(s: str) -> str:
    return (
        (s or "")
        .strip()
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
    )


def rounding_digits_from_form(form_data) -> int:
    """Как _parse_energy_consumption_rounding_digits в маршрутах: режим округления из POST/формы."""
    raw = form_data.get("rounding_digits")
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return 1
    if v == -1:
        return -1
    if v in (0, 1, 2, 3):
        return v
    return 1


def resolve_max_power_mw_for_save(
    visible_raw: Any,
    db_snapshot_raw: Any,
    rounding_digits: int,
) -> Optional[Decimal]:
    """
    Видимое поле может быть округлено относительно БД. Если текст совпадает с отображением
    снимка БД при текущем rounding_digits, сохраняем полное значение из снимка; иначе — то, что ввёл пользователь.
    """
    vis = parse_decimal(visible_raw if visible_raw is not None else "")
    if not str(db_snapshot_raw or "").strip():
        return vis
    db_dec = parse_decimal(db_snapshot_raw)
    if db_dec is None:
        return vis
    if vis is None:
        return None
    shown = format_decimal_trim_for_display(db_dec, digits=rounding_digits)
    if _norm_num_str_for_compare(str(visible_raw or "")) == _norm_num_str_for_compare(shown):
        return db_dec
    return vis


def validate_energy_consumption_post_complete(
    form_data, *, skip_mln_sipr_validation: bool = False
) -> None:
    """Поля формы: row_id[], slice_year[], ec_mln[], ec_sipr[], ec_mln_db[], ec_sipr_db[], note[], del[]."""
    ids = form_data.getlist("row_id[]")
    slice_years = form_data.getlist("slice_year[]")
    ec_mlns = form_data.getlist("ec_mln[]")
    ec_siprs = form_data.getlist("ec_sipr[]")
    notes = form_data.getlist("note[]")
    dels = form_data.getlist("del[]")
    deleted = {int(x) for x in dels if str(x).strip().isdigit()}

    n = max(len(ids), len(slice_years), len(ec_mlns), len(ec_siprs), len(notes))
    issues: list[str] = []

    for i in range(n):
        rid_s = ids[i] if i < len(ids) else ""
        rid = int(rid_s) if str(rid_s).strip().isdigit() else None
        if rid and rid in deleted:
            continue

        sl_st = (slice_years[i] if i < len(slice_years) else "").strip()
        ec_m = ec_mlns[i] if i < len(ec_mlns) else ""
        ec_s = ec_siprs[i] if i < len(ec_siprs) else ""
        note_v = notes[i] if i < len(notes) else ""

        row_label = f"строка таблицы №{i + 1}"

        if not rid:
            all_empty = (
                not sl_st
                and not _field_nonempty(ec_m)
                and not _field_nonempty(ec_s)
                and not _field_nonempty(note_v)
            )
            if all_empty:
                continue
            row_label = "новая строка"

        if sl_st == "hist":
            issues.append(
                f"{row_label}: выберите календарный год (исторический максимум не используется)."
            )
            continue

        year_n = _parse_calendar_year_slice(sl_st)
        if year_n is None:
            issues.append(f"{row_label}: не выбран год.")
            continue

        if not skip_mln_sipr_validation:
            if _field_nonempty(ec_m) and parse_decimal(ec_m) is None:
                issues.append(
                    f"{row_label}: некорректное число в «Потребление электрической энергии, млн кВт·ч»."
                )
            if _field_nonempty(ec_s) and parse_decimal(ec_s) is None:
                issues.append(
                    f"{row_label}: некорректное число в «Потребление (СиПР), млн кВт·ч»."
                )

    if issues:
        msg = "Нельзя сохранить: не все обязательные поля заполнены или формат неверный. " + " ".join(
            issues[:15]
        )
        if len(issues) > 15:
            msg += " …"
        raise ValueError(msg)


def validate_demand_post_complete(
    form_data,
    demand_model: Type[Any],
    require_combined_oe_ees: bool,
    *,
    require_combined_on_ez: bool = False,
) -> None:
    """
    Для маршрутов потребления — только модели gs_ec.
    Аргументы combined_* оставлены для совместимости вызовов из маршрутов.
    """
    del require_combined_oe_ees, require_combined_on_ez
    if not _is_energy_consumption_parameter_model(demand_model):
        raise ValueError("Ожидается модель параметров потребления (gs_ec).")
    skip_nums = (
        getattr(demand_model, "__tablename__", None) == "gs_ec_energy_zone_consumption_params"
    )
    validate_energy_consumption_post_complete(
        form_data, skip_mln_sipr_validation=skip_nums
    )


def save_energy_consumption_rows_from_post(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    form_data,
) -> tuple[int, int]:
    validate_demand_post_complete(
        form_data,
        demand_model,
        False,
        require_combined_on_ez=False,
    )

    rd_save = rounding_digits_from_form(form_data)

    ids = form_data.getlist("row_id[]")
    slice_years = form_data.getlist("slice_year[]")
    ec_mlns = form_data.getlist("ec_mln[]")
    ec_sipr_raw = form_data.getlist("ec_sipr[]")
    ec_mln_dbs = form_data.getlist("ec_mln_db[]")
    ec_sipr_dbs = form_data.getlist("ec_sipr_db[]")
    notes = form_data.getlist("note[]")
    dels = form_data.getlist("del[]")
    deleted = set(int(x) for x in dels if str(x).strip().isdigit())

    saved = 0
    deleted_n = 0
    user = _username()
    is_ez_tbl = (
        getattr(demand_model, "__tablename__", None) == "gs_ec_energy_zone_consumption_params"
    )
    is_res_tbl = (
        getattr(demand_model, "__tablename__", None)
        == "gs_ec_regional_energy_system_consumption_params"
    )

    for rid in deleted:
        row = demand_model.query.get(rid)
        if row is not None:
            if fk_column_name is not None and parent_id is not None:
                if getattr(row, fk_column_name) != parent_id:
                    continue
            elif fk_column_name is not None:
                continue
            db.session.delete(row)
            deleted_n += 1

    n = max(len(ids), len(slice_years), len(ec_mlns), len(ec_sipr_raw), len(notes))
    for i in range(n):
        rid_s = ids[i] if i < len(ids) else ""
        rid = int(rid_s) if str(rid_s).strip().isdigit() else None
        raw_sl = slice_years[i] if i < len(slice_years) else ""
        year_n = _parse_calendar_year_slice(raw_sl)

        db_mln = ec_mln_dbs[i] if i < len(ec_mln_dbs) else ""
        db_sipr = ec_sipr_dbs[i] if i < len(ec_sipr_dbs) else ""
        ec_mln = resolve_max_power_mw_for_save(
            ec_mlns[i] if i < len(ec_mlns) else "",
            db_mln,
            rd_save,
        )
        ec_sipr = resolve_max_power_mw_for_save(
            ec_sipr_raw[i] if i < len(ec_sipr_raw) else "",
            db_sipr,
            rd_save,
        )
        note_v = str(notes[i] if i < len(notes) else "").strip()
        note_val = note_v if note_v else None

        if year_n is None and not rid:
            continue

        if rid:
            row = demand_model.query.get(rid)
            if row is None:
                continue
            if fk_column_name is not None and parent_id is not None:
                if getattr(row, fk_column_name) != parent_id:
                    continue
        else:
            row = demand_model()
            if fk_column_name is not None and parent_id is not None:
                setattr(row, fk_column_name, parent_id)
            apply_version_to_row(row, demand_model)
            row.created_by = user
            db.session.add(row)

        row.year_number = year_n
        if is_ez_tbl:
            pass
        else:
            row.energy_consumption_mln_kvt_ch = ec_mln
            row.energy_consumption_sipr_mln_kvt_ch = ec_sipr
        row.note = note_val
        row.modified_by = user

        saved += 1

    db.session.flush()
    if is_ez_tbl and parent_id is not None:
        sync_energy_zone_consumption_aggregates(id_energy_zone=int(parent_id))
    elif is_res_tbl and parent_id is not None:
        sync_energy_zone_consumption_aggregates(id_regional_energy_system=int(parent_id))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise
    return saved, deleted_n


def save_demand_rows_from_post(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    form_data,
    *,
    require_combined_oe_ees: bool = True,
    require_combined_on_ez: bool = False,
) -> tuple[int, int]:
    """
    POST: row_id[], slice_year[], ec_mln[], ec_sipr[], ec_mln_db[], ec_sipr_db[], note[], del[].
    Год — только календарный номер (целое).
    """
    del require_combined_oe_ees, require_combined_on_ez
    if not _is_energy_consumption_parameter_model(demand_model):
        raise ValueError("Ожидается модель параметров потребления (gs_ec).")
    return save_energy_consumption_rows_from_post(
        demand_model,
        fk_column_name,
        parent_id,
        form_data,
    )


def _summary_demand_model_class(name: str) -> Type[Any]:
    from app.energy_consumption.models.energy_systems.centralized_zone_energy_consumption_parameter_model import (
        CentralizedZoneEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.ees_energy_consumption_parameter_model import (
        EesEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
        EesRussiaEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.ees_russia_with_nt_energy_consumption_parameter_model import (
        EesRussiaWithNtEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
        EnergySystemTypeEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.energy_unit_energy_consumption_parameter_model import (
        EnergyUnitEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
        EnergyZoneEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
        RegionalEnergySystemEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.synchronous_area_energy_consumption_parameter_model import (
        SynchronousAreaEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
        UnionEnergySystemEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
        FederalDistrictEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
        RegionalDistrictEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.territories.russia_federation_energy_consumption_parameter_model import (
        RussiaFederationEnergyConsumptionParameter,
    )
    from app.energy_consumption.models.territories.russia_federation_with_nt_energy_consumption_parameter_model import (
        RussiaFederationWithNtEnergyConsumptionParameter,
    )

    mapping: dict[str, Type[Any]] = {
        "CentralizedZoneEnergyConsumptionParameter": CentralizedZoneEnergyConsumptionParameter,
        "EesEnergyConsumptionParameter": EesEnergyConsumptionParameter,
        "EesRussiaEnergyConsumptionParameter": EesRussiaEnergyConsumptionParameter,
        "EesRussiaWithNtEnergyConsumptionParameter": EesRussiaWithNtEnergyConsumptionParameter,
        "EnergySystemTypeEnergyConsumptionParameter": EnergySystemTypeEnergyConsumptionParameter,
        "EnergyUnitEnergyConsumptionParameter": EnergyUnitEnergyConsumptionParameter,
        "EnergyZoneEnergyConsumptionParameter": EnergyZoneEnergyConsumptionParameter,
        "RegionalEnergySystemEnergyConsumptionParameter": RegionalEnergySystemEnergyConsumptionParameter,
        "SynchronousAreaEnergyConsumptionParameter": SynchronousAreaEnergyConsumptionParameter,
        "UnionEnergySystemEnergyConsumptionParameter": UnionEnergySystemEnergyConsumptionParameter,
        "FederalDistrictEnergyConsumptionParameter": FederalDistrictEnergyConsumptionParameter,
        "RegionalDistrictEnergyConsumptionParameter": RegionalDistrictEnergyConsumptionParameter,
        "RussiaFederationEnergyConsumptionParameter": RussiaFederationEnergyConsumptionParameter,
        "RussiaFederationWithNtEnergyConsumptionParameter": RussiaFederationWithNtEnergyConsumptionParameter,
    }
    cls = mapping.get(name)
    if cls is None:
        raise ValueError(f"Неизвестная модель параметров потребления: {name}")
    return cls


def _dash_summary_display(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def summary_cell_display_value(row: Any, parameter_key: str, rounding_digits: int) -> str:
    """Строка для отображения ячейки сводки после сохранения."""
    if parameter_key == "energy_consumption_mln_kvt_ch":
        v = getattr(row, "energy_consumption_mln_kvt_ch", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "energy_consumption_sipr_mln_kvt_ch":
        v = getattr(row, "energy_consumption_sipr_mln_kvt_ch", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key in ("note", "entity_note"):
        return _dash_summary_display(getattr(row, "note", None))
    return "—"


_SUMMARY_STANDALONE_DEMAND_MODELS = frozenset(
    {
        "CentralizedZoneEnergyConsumptionParameter",
        "EesEnergyConsumptionParameter",
        "EesRussiaEnergyConsumptionParameter",
        "EesRussiaWithNtEnergyConsumptionParameter",
        "RussiaFederationEnergyConsumptionParameter",
        "RussiaFederationWithNtEnergyConsumptionParameter",
    }
)


def _validate_summary_parent_binding(
    model_name: str,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
) -> None:
    if model_name in _SUMMARY_STANDALONE_DEMAND_MODELS:
        if parent_fk_column or parent_id is not None:
            raise ValueError("Некорректные параметры привязки.")
        return
    if not parent_fk_column or parent_id is None:
        raise ValueError("Для этой строки нужен объект привязки. Обновите страницу.")


def parse_summary_slice_key(slice_key: Any) -> tuple[bool, Optional[int]]:
    """Календарный год; «hist» не допускается."""
    if slice_key is None or slice_key == "":
        raise ValueError("Не указан год среза.")
    if slice_key == "hist":
        raise ValueError(
            "Срез «исторический максимум» для показателей потребления не поддерживается."
        )
    try:
        y = int(slice_key)
    except (TypeError, ValueError) as exc:
        raise ValueError("Некорректный год среза.") from exc
    return False, y


def find_demand_row_for_summary_slice(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    is_hist: bool,
    year_n: Optional[int],
) -> Any:
    del is_hist
    if year_n is None:
        return None
    q = model.query
    q = filter_demand_by_version(q, model)
    if parent_fk_column is not None:
        if parent_id is None:
            return None
        q = q.filter(getattr(model, parent_fk_column) == parent_id)
    q = q.filter(model.year_number == year_n)
    return q.first()


def create_demand_row_for_summary_slice(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    is_hist: bool,
    year_n: Optional[int],
) -> Any:
    del is_hist
    row = model()
    if parent_fk_column is not None:
        setattr(row, parent_fk_column, parent_id)
    apply_version_to_row(row, model)
    row.year_number = year_n
    row.created_by = _username()
    db.session.add(row)
    return row


def _apply_summary_field_to_row(
    row: Any,
    parameter_key: str,
    raw_value: Any,
    *,
    rounding_digits: int,
    sipr_summary_mode: bool = False,
) -> None:
    if parameter_key == "energy_consumption_mln_kvt_ch":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError(
                "Некорректное число в поле «Потребление электрической энергии, млн кВт·ч»."
            )
        old_shown = (
            format_decimal_trim_for_display(row.energy_consumption_mln_kvt_ch, digits=rounding_digits)
            if row.energy_consumption_mln_kvt_ch is not None
            else ""
        )
        row.energy_consumption_mln_kvt_ch = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
        if (
            not sipr_summary_mode
            and "energy_consumption_sipr_mln_kvt_ch" in row.__table__.columns
        ):
            row.energy_consumption_sipr_mln_kvt_ch = _decimal_round_half_up_to_int(
                row.energy_consumption_mln_kvt_ch
            )
    elif parameter_key == "energy_consumption_sipr_mln_kvt_ch":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Потребление (СиПР), млн кВт·ч».")
        old_shown = (
            format_decimal_trim_for_display(row.energy_consumption_sipr_mln_kvt_ch, digits=rounding_digits)
            if row.energy_consumption_sipr_mln_kvt_ch is not None
            else ""
        )
        row.energy_consumption_sipr_mln_kvt_ch = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "note":
        if "note" not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        row.note = s if s else None
    else:
        raise ValueError("Неизвестный параметр для сохранения.")


def _assert_plan_year_only_max_power_editable(
    year_number: Optional[int],
    is_hist: bool,
    parameter_key: str,
    *,
    demand_model_name: str,
) -> None:
    del demand_model_name
    if parameter_key == "entity_note":
        return
    if is_hist or year_number is None:
        return


def _summary_row_tri_snapshot(row: Any) -> dict[str, Any]:
    if row is None:
        return {"mln": None, "sipr": None, "note": None}
    mln = getattr(row, "energy_consumption_mln_kvt_ch", None)
    sipr = getattr(row, "energy_consumption_sipr_mln_kvt_ch", None)
    note = getattr(row, "note", None) if hasattr(row, "note") else None
    return {"mln": mln, "sipr": sipr, "note": note}


def _fmt_tri_snap_val(val: Any, key: str, rounding_digits: int) -> str:
    if val is None:
        return "—"
    if key in ("mln", "sipr"):
        return format_decimal_trim_for_display(val, digits=rounding_digits) or "—"
    s = str(val).strip()
    return s if s else "—"


def _tri_snap_numeric_equal(a: Any, b: Any) -> bool:
    """Сравнение значений показателей млн/СиПР для журнала (учёт Decimal/чисел из БД)."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError, TypeError):
        return False


def _diff_tri_snap_for_log(
    before: dict,
    after: dict,
    rounding_digits: int,
    *,
    parameter_key: str,
) -> list[str]:
    """Только поля, которые пользователь менял по запросу (без автосинхронизации СиПР с млн)."""
    labels = {
        "mln": "Потребление, млн кВт·ч",
        "sipr": "Потребление (СиПР), млн кВт·ч",
        "note": "Примечание",
    }
    pk = (parameter_key or "").strip()
    if pk == "entity_note":
        keys_order = ["note"]
    elif pk == "energy_consumption_mln_kvt_ch":
        keys_order = ["mln"]
    elif pk == "energy_consumption_sipr_mln_kvt_ch":
        keys_order = ["sipr"]
    else:
        keys_order = list(labels.keys())

    parts: list[str] = []
    for k in keys_order:
        label = labels[k]
        vb, va = before.get(k), after.get(k)
        if k in ("mln", "sipr"):
            if _tri_snap_numeric_equal(vb, va):
                continue
        else:
            fb_check = _fmt_tri_snap_val(vb, k, rounding_digits)
            fa_check = _fmt_tri_snap_val(va, k, rounding_digits)
            if fb_check == fa_check:
                continue
        fb = _fmt_tri_snap_val(vb, k, rounding_digits)
        fa = _fmt_tri_snap_val(va, k, rounding_digits)
        if k in ("mln", "sipr") and fb == fa:
            fb = format_decimal_trim_for_display(vb, digits=0) or "—"
            fa = format_decimal_trim_for_display(va, digits=0) or "—"
        parts.append(f"{label}: {fb} → {fa}")
    return parts


_EC_SUMMARY_PARENT_FK_LABELS: dict[str, tuple[Type[Any], str]] = {
    "id_regional_district": (RegionalDistrict, "субъект РФ"),
    "id_regional_energy_system": (RegionalEnergySystem, "РЭС"),
    "id_union_energy_system": (UnionEnergySystem, "ОЭС"),
    "id_federal_district": (FederalDistrict, "федеральный округ"),
    "id_energy_zone": (EnergyZone, "энергозона"),
}


def _parent_binding_label_for_ec_summary_log(
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    *,
    database_version_id: Optional[int],
) -> Optional[str]:
    """Подпись родительского объекта для журнала: id + наименование из справочника."""
    if not parent_fk_column or parent_id is None:
        return None
    spec = _EC_SUMMARY_PARENT_FK_LABELS.get(parent_fk_column)
    if not spec:
        return f"{parent_fk_column}={parent_id}"
    model_cls, ru_short = spec
    q = model_cls.query.filter(model_cls.id == int(parent_id))
    if database_version_id is not None:
        q = filter_by_explicit_db_version(q, model_cls, int(database_version_id))
    ent = q.first()
    pid = int(parent_id)
    if ent is None:
        return f"{parent_fk_column}={pid}; {ru_short}=— (нет в справочнике для версии БД)"
    nm = getattr(ent, "name", None)
    name_s = str(nm).strip() if nm is not None else ""
    if name_s:
        return f"{parent_fk_column}={pid}; {ru_short}={name_s}"
    return f"{parent_fk_column}={pid}"


def _maybe_log_ec_summary_cell(
    summary_log_scope: Optional[str],
    *,
    demand_model_name: str,
    parameter_key: str,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    row: Any,
    snap_before: dict[str, Any],
    rounding_digits: int,
) -> None:
    if not summary_log_scope or summary_log_scope not in ("oes", "fo", "ez") or row is None:
        return
    rid_log = getattr(row, "id", None)
    if rid_log is not None:
        model_cls = type(row)
        fresh = model_cls.query.get(int(rid_log))
        if fresh is not None:
            row = fresh
    snap_after = _summary_row_tri_snapshot(row)
    diff_lines = _diff_tri_snap_for_log(
        snap_before, snap_after, rounding_digits, parameter_key=parameter_key
    )
    if not diff_lines:
        return
    header_bits = [f"модель={demand_model_name}"]
    if parent_fk_column and parent_id is not None:
        pl = _parent_binding_label_for_ec_summary_log(
            parent_fk_column,
            parent_id,
            database_version_id=getattr(row, "database_version_id", None),
        )
        if pl:
            header_bits.append(pl)
    yn = getattr(row, "year_number", None)
    if yn is not None:
        header_bits.append(f"год={yn}")
    rid = getattr(row, "id", None)
    if rid is not None:
        header_bits.append(f"id_записи={rid}")
    chunks: list[str] = [", ".join(header_bits)] + diff_lines
    from app.energy_consumption.services.energy_consumption_summary_logging import (
        log_ec_summary_cell_change,
    )

    log_ec_summary_cell_change(
        _username(),
        summary_log_scope,
        detail_chunks=chunks,
        database_version_id=getattr(row, "database_version_id", None),
    )


def save_demand_summary_cell(
    demand_model_name: str,
    parameter_key: str,
    raw_value: Any,
    *,
    rounding_digits: int,
    sipr_summary_mode: bool = False,
    row_id: Optional[int] = None,
    slice_key: Any = None,
    parent_fk_column: Optional[str] = None,
    parent_id: Optional[int] = None,
    summary_log_scope: Optional[str] = None,
) -> str:
    """
    Создаёт или обновляет одно поле строки параметров потребления (сводная таблица).
    """
    allowed = {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        "entity_note",
    }
    if parameter_key not in allowed:
        raise ValueError("Неизвестный параметр.")

    if parameter_key == "entity_note":
        model = _summary_demand_model_class(demand_model_name)
        _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)
        vid = get_current_version()
        user = _username()
        if parent_fk_column and not hasattr(model, parent_fk_column):
            raise ValueError("Некорректная привязка к объекту.")
        erow: Any = None
        if row_id is not None and row_id > 0:
            erow = model.query.get(row_id)
            if erow is None:
                raise ValueError("Строка не найдена.")
            if vid is not None and getattr(erow, "database_version_id", None) != vid:
                raise ValueError("Данные относятся к другой версии БД. Обновите страницу.")
            if parent_fk_column is not None and parent_id is not None:
                if getattr(erow, parent_fk_column, None) != parent_id:
                    raise ValueError("Строка не соответствует выбранному объекту.")
        else:
            _, note_year = parse_summary_slice_key(slice_key)
            erow = find_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id,
                is_hist=False,
                year_n=note_year,
            )
            if erow is None:
                if not str(raw_value or "").strip():
                    return ""
                erow = create_demand_row_for_summary_slice(
                    model,
                    parent_fk_column=parent_fk_column,
                    parent_id=parent_id,
                    is_hist=False,
                    year_n=note_year,
                )
        snap_before = _summary_row_tri_snapshot(erow)
        _apply_summary_field_to_row(
            erow,
            "note",
            raw_value,
            rounding_digits=rounding_digits,
            sipr_summary_mode=sipr_summary_mode,
        )
        erow.modified_by = user
        try:
            db.session.commit()
            db.session.refresh(erow)
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Не удалось сохранить (конфликт данных).") from None
        _maybe_log_ec_summary_cell(
            summary_log_scope,
            demand_model_name=demand_model_name,
            parameter_key="entity_note",
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            row=erow,
            snap_before=snap_before,
            rounding_digits=rounding_digits,
        )
        return summary_cell_display_value(erow, "entity_note", rounding_digits)

    model = _summary_demand_model_class(demand_model_name)
    _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)

    if (
        model.__tablename__ == "gs_ec_energy_zone_consumption_params"
        and parameter_key
        in (
            "energy_consumption_mln_kvt_ch",
            "energy_consumption_sipr_mln_kvt_ch",
        )
    ):
        raise ValueError(
            "Показатели по энергозоне считаются автоматически как сумма по РЭС; "
            "измените данные на уровне региональных энергосистем."
        )

    vid = get_current_version()
    user = _username()

    if parent_fk_column and not hasattr(model, parent_fk_column):
        raise ValueError("Некорректная привязка к объекту.")

    row: Any = None

    if row_id is not None and row_id > 0:
        row = model.query.get(row_id)
        if row is None:
            raise ValueError("Строка не найдена.")
        if vid is not None and getattr(row, "database_version_id", None) != vid:
            raise ValueError("Данные относятся к другой версии БД. Обновите страницу.")
        if parent_fk_column is not None and parent_id is not None:
            if getattr(row, parent_fk_column, None) != parent_id:
                raise ValueError("Строка не соответствует выбранному объекту.")
        _assert_plan_year_only_max_power_editable(
            getattr(row, "year_number", None),
            bool(getattr(row, "is_historical_maximum", False)),
            parameter_key,
            demand_model_name=demand_model_name,
        )
    else:
        is_hist, year_n = parse_summary_slice_key(slice_key)
        _assert_plan_year_only_max_power_editable(
            year_n, is_hist, parameter_key, demand_model_name=demand_model_name
        )
        row = find_demand_row_for_summary_slice(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            is_hist=is_hist,
            year_n=year_n,
        )
        if row is None:
            if not str(raw_value or "").strip():
                return "—"
            row = create_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id,
                is_hist=is_hist,
                year_n=year_n,
            )

    snap_before = _summary_row_tri_snapshot(row)
    _apply_summary_field_to_row(
        row,
        parameter_key,
        raw_value,
        rounding_digits=rounding_digits,
        sipr_summary_mode=sipr_summary_mode,
    )
    row.modified_by = user

    if (
        model.__tablename__ == "gs_ec_regional_energy_system_consumption_params"
        and parent_fk_column == "id_regional_energy_system"
        and parent_id is not None
    ):
        db.session.flush()
        sync_energy_zone_consumption_aggregates(id_regional_energy_system=int(parent_id))

    try:
        db.session.commit()
        db.session.refresh(row)
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Не удалось сохранить (конфликт данных).") from None

    _maybe_log_ec_summary_cell(
        summary_log_scope,
        demand_model_name=demand_model_name,
        parameter_key=parameter_key,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        row=row,
        snap_before=snap_before,
        rounding_digits=rounding_digits,
    )

    return summary_cell_display_value(row, parameter_key, rounding_digits)
