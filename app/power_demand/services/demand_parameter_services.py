# -*- coding: utf-8 -*-
"""
CRUD и выборки для таблиц параметров нагрузки (power_demand, схема gs_pd).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Type

from flask import session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.database_version_services import get_current_version
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.services.refdata_all_versions_common import (
    all_database_version_ids_for_refdata,
    fk_id_for_version,
)
from app.common.services.get_services.years.year_feature_services import (
    get_year_feature_dict,
)
from app.common.services.get_services.years.years_get_services import get_year_list_full
from app.common.services.help_services import format_decimal_trim_for_display
from app.common.perimeter_variant.registry import (
    filter_query_by_perimeter_variant,
    model_supports_perimeter_variant,
    normalize_perimeter_variant_code,
)

_UNSET = object()


def _username() -> str:
    return session.get("username", "Неизвестный пользователь")


def parse_slice_year(raw: Any) -> tuple[bool, Optional[int]]:
    """
    Одно поле формы: «Исторический максимум» (hist) или номер года.
    Пустое значение — срез «год» без выбранного года (новая незаполненная строка).
    """
    s = str(raw or "").strip()
    if s == "hist":
        return True, None
    if not s:
        return False, None
    if s.isdigit():
        return False, int(s)
    return False, None


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


_REFDATA_MODEL_BY_PARENT_FK: dict[str, Type[Any]] = {
    "id_union_energy_system": UnionEnergySystem,
    "id_regional_energy_system": RegionalEnergySystem,
    "id_regional_district": RegionalDistrict,
    "id_federal_district": FederalDistrict,
    "id_energy_zone": EnergyZone,
    "id_synchronous_area": SynchronousArea,
    "id_energy_system_type": EnergySystemType,
    "id_energy_unit": EnergyUnit,
}


def _resolve_summary_parent_id_for_version(
    parent_fk_column: Optional[str],
    anchor_parent_id: Optional[int],
    target_version_id: int,
) -> Optional[int]:
    if parent_fk_column is None or anchor_parent_id is None:
        return None
    ref_cls = _REFDATA_MODEL_BY_PARENT_FK.get(parent_fk_column)
    if ref_cls is None:
        raise ValueError(f"Неизвестная колонка привязки сводки: {parent_fk_column}")
    return fk_id_for_version(ref_cls, int(anchor_parent_id), int(target_version_id))


def _single_regional_district_id_for_res(
    regional_energy_system_id: int,
    *,
    database_version_id: int,
) -> Optional[int]:
    """Один субъект РФ у РЭС — id субъекта в указанной версии справочника, иначе None."""
    stmt = select(regional_district_regional_energy_system.c.regional_district_id).where(
        regional_district_regional_energy_system.c.regional_energy_system_id
        == regional_energy_system_id
    )
    rows = db.session.execute(stmt).all()
    rd_ids = {int(r[0]) for r in rows if r[0] is not None}
    if len(rd_ids) != 1:
        return None
    rd_id = next(iter(rd_ids))
    rq = RegionalDistrict.query.filter(RegionalDistrict.id == rd_id)
    rq = filter_by_explicit_db_version(rq, RegionalDistrict, database_version_id)
    return rd_id if rq.first() is not None else None


def _map_res_parameter_key_for_single_rd_mirror(parameter_key: str) -> Optional[str]:
    """Поле RegionalEnergySystemDemandParameter → колонка RegionalDistrictDemandParameter."""
    pk = str(parameter_key or "")
    if pk.startswith("coeff_k_"):
        return None
    if pk == "entity_note":
        return "note"
    if pk == "combined_on_ez":
        return "combined_on_es"
    if pk in (
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_oes",
        "combined_on_ees",
    ):
        return pk
    return None


def _mirror_res_demand_to_single_rd(
    *,
    res_parent_id_v: int,
    parameter_key: str,
    raw_value: Any,
    rounding_digits: int,
    is_hist: bool,
    year_n: Optional[int],
    database_version_id: int,
) -> None:
    from app.power_demand.models.territories.regional_district_demand_parameter_model import (
        RegionalDistrictDemandParameter,
    )

    rd_field = _map_res_parameter_key_for_single_rd_mirror(parameter_key)
    if rd_field is None:
        return
    rd_id = _single_regional_district_id_for_res(
        int(res_parent_id_v),
        database_version_id=int(database_version_id),
    )
    if rd_id is None:
        return
    rd_model = RegionalDistrictDemandParameter
    rd_row = find_demand_row_for_summary_slice(
        rd_model,
        parent_fk_column="id_regional_district",
        parent_id=int(rd_id),
        is_hist=is_hist,
        year_n=year_n,
        database_version_id=database_version_id,
    )
    if rd_row is None:
        if not str(raw_value or "").strip():
            return
        rd_row = create_demand_row_for_summary_slice(
            rd_model,
            parent_fk_column="id_regional_district",
            parent_id=int(rd_id),
            is_hist=is_hist,
            year_n=year_n,
            database_version_id=database_version_id,
        )
    _apply_summary_field_to_row(
        rd_row, rd_field, raw_value, rounding_digits=rounding_digits
    )
    rd_row.modified_by = _username()


def get_demand_rows(
    demand_model,
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    *,
    perimeter_variant_code: Any = _UNSET,
):
    """
    Список строк параметров для родителя. fk_column_name=None — модель без FK (РФ целиком).

    perimeter_variant_code: для моделей с PerimeterVariantColumnMixin — None (базовый периметр)
    или код из app.common.perimeter_variant.registry.
    """
    q = demand_model.query
    q = filter_demand_by_version(q, demand_model)
    if fk_column_name is not None and parent_id is not None:
        q = q.filter(getattr(demand_model, fk_column_name) == parent_id)
    if perimeter_variant_code is not _UNSET:
        q = filter_query_by_perimeter_variant(q, demand_model, perimeter_variant_code)
    rows = q.order_by(
        demand_model.is_historical_maximum.desc(),
        demand_model.year_number.asc().nullsfirst(),
    ).all()
    return rows


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
    """Как _parse_power_demand_rounding_digits в маршрутах: режим округления из POST/формы."""
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


def validate_demand_post_complete(
    form_data,
    require_combined_oe_ees: bool,
    *,
    require_combined_on_ez: bool = False,
) -> None:
    """
    Проверяет, что все строки, которые должны сохраниться, заполнены.
    Строки, отмеченные на удаление, не проверяются.
    Полностью пустая новая строка (без id) допустима — пропускается.
    """
    ids = form_data.getlist("row_id[]")
    slice_years = form_data.getlist("slice_year[]")
    p_maxs = form_data.getlist("p_max[]")
    dts = form_data.getlist("dt[]")
    tnvs = form_data.getlist("tnv[]")
    oess = form_data.getlist("oes[]")
    eess = form_data.getlist("ees[]")
    ess = form_data.getlist("es[]")
    ezss = form_data.getlist("ez[]")
    dels = form_data.getlist("del[]")
    deleted = {int(x) for x in dels if str(x).strip().isdigit()}

    n = max(len(ids), len(slice_years), len(ess), len(ezss) if require_combined_on_ez else 0)
    issues: list[str] = []

    for i in range(n):
        rid_s = ids[i] if i < len(ids) else ""
        rid = int(rid_s) if str(rid_s).strip().isdigit() else None
        if rid and rid in deleted:
            continue

        sl_st = (slice_years[i] if i < len(slice_years) else "").strip()
        p_max = p_maxs[i] if i < len(p_maxs) else ""
        dt = dts[i] if i < len(dts) else ""
        tnv = tnvs[i] if i < len(tnvs) else ""
        oes = oess[i] if i < len(oess) else ""
        ees = eess[i] if i < len(eess) else ""
        es_s = ess[i] if i < len(ess) else ""
        ez_s = ezss[i] if i < len(ezss) else ""

        row_label = f"строка таблицы №{i + 1}"

        if not rid:
            core_empty = (
                not sl_st
                and not _field_nonempty(p_max)
                and not _field_nonempty(dt)
                and not _field_nonempty(tnv)
            )
            oe_empty = not _field_nonempty(oes)
            ee_empty = not _field_nonempty(ees)
            ez_empty = not _field_nonempty(ez_s)
            if (
                core_empty
                and not _field_nonempty(es_s)
                and (not require_combined_oe_ees or (oe_empty and ee_empty))
                and (not require_combined_on_ez or ez_empty)
            ):
                continue
            row_label = "новая строка"

        is_hist, year_n = parse_slice_year(sl_st)
        if not sl_st or (not is_hist and year_n is None):
            issues.append(f"{row_label}: не выбран срез или год.")
            continue

        if not _field_nonempty(p_max):
            issues.append(f"{row_label}: не заполнено «Максимальное потребление, МВт».")
        elif parse_decimal(p_max) is None:
            issues.append(f"{row_label}: некорректное число в «Максимальное потребление, МВт».")

        if not _field_nonempty(dt):
            issues.append(f"{row_label}: не заполнено «Дата и время».")
        else:
            dt_parsed = parse_peak_datetime(dt)
            if dt_parsed is None:
                issues.append(
                    f"{row_label}: «Дата и время»: несуществующая дата или неверный формат "
                    f"(ДД.ММ.ГГГГ ЧЧ:ММ или только год ГГГГ)."
                )
            elif not is_hist and year_n is not None and dt_parsed.year != year_n:
                issues.append(
                    f"{row_label}: год в «Дата и время» ({dt_parsed.year}) должен совпадать "
                    f"с годом в столбце «Срез / год» ({year_n})."
                )

        if not _field_nonempty(tnv):
            issues.append(f"{row_label}: не заполнено «Среднесуточная ТНВ».")
        elif parse_decimal(tnv) is None:
            issues.append(f"{row_label}: некорректное число в «Среднесуточная ТНВ».")

        if _field_nonempty(es_s) and parse_decimal(es_s) is None:
            issues.append(f"{row_label}: некорректное число в «Совмещенный на ЭС, МВт».")

        if require_combined_oe_ees:
            if not _field_nonempty(oes):
                issues.append(f"{row_label}: не заполнено «Совмещённый на ОЭС».")
            elif parse_decimal(oes) is None:
                issues.append(f"{row_label}: некорректное число в «Совмещённый на ОЭС».")
            if not _field_nonempty(ees):
                issues.append(f"{row_label}: не заполнено «Совмещённый на ЕЭС».")
            elif parse_decimal(ees) is None:
                issues.append(f"{row_label}: некорректное число в «Совмещённый на ЕЭС».")

        if require_combined_on_ez:
            if not _field_nonempty(ez_s):
                issues.append(f"{row_label}: не заполнено «Совмещённый на энергозону, МВт».")
            elif parse_decimal(ez_s) is None:
                issues.append(
                    f"{row_label}: некорректное число в «Совмещённый на энергозону, МВт»."
                )

    if issues:
        msg = "Нельзя сохранить: не все обязательные поля заполнены или формат неверный. " + " ".join(
            issues[:15]
        )
        if len(issues) > 15:
            msg += " …"
        raise ValueError(msg)


def save_demand_rows_from_post(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    form_data,
    *,
    require_combined_oe_ees: bool = True,
    require_combined_on_ez: bool = False,
    perimeter_variant_code: Any = _UNSET,
) -> tuple[int, int]:
    """
    Обрабатывает POST с полями row_id[], slice_year[], p_max[], dt[], tnv[], oes[], ees[], es[], ez[], del[].
    slice_year[]: «hist» — исторический максимум; иначе — номер года (строка цифр).
    Возвращает (saved_count, deleted_count).
    """
    validate_demand_post_complete(
        form_data,
        require_combined_oe_ees,
        require_combined_on_ez=require_combined_on_ez,
    )

    rd_save = rounding_digits_from_form(form_data)
    pvc = perimeter_variant_code
    if pvc is not _UNSET:
        pvc = normalize_perimeter_variant_code(pvc) if pvc not in (None, "") else None
    else:
        pvc = _UNSET

    ids = form_data.getlist("row_id[]")
    slice_years = form_data.getlist("slice_year[]")
    p_maxs = form_data.getlist("p_max[]")
    p_max_dbs = form_data.getlist("p_max_db[]")
    dts = form_data.getlist("dt[]")
    tnvs = form_data.getlist("tnv[]")
    oess = form_data.getlist("oes[]")
    eess = form_data.getlist("ees[]")
    ess = form_data.getlist("es[]")
    ezss = form_data.getlist("ez[]")
    ez_mode = (
        require_combined_on_ez
        and "combined_on_ez" in demand_model.__table__.columns
        and form_data.get("demand_form_ez_mode") == "1"
    )
    dels = form_data.getlist("del[]")
    deleted = set(int(x) for x in dels if str(x).strip().isdigit())

    saved = 0
    deleted_n = 0
    user = _username()

    # Удаление
    for rid in deleted:
        row = demand_model.query.get(rid)
        if row is not None:
            if fk_column_name is not None and parent_id is not None:
                if getattr(row, fk_column_name) != parent_id:
                    continue
            elif fk_column_name is not None:
                continue
            if pvc is not _UNSET and model_supports_perimeter_variant(demand_model):
                if getattr(row, "perimeter_variant_code", None) != pvc:
                    continue
            db.session.delete(row)
            deleted_n += 1

    n = max(len(ids), len(slice_years), len(ess), len(ezss) if ez_mode else 0)
    for i in range(n):
        rid_s = ids[i] if i < len(ids) else ""
        rid = int(rid_s) if str(rid_s).strip().isdigit() else None
        raw_sl = slice_years[i] if i < len(slice_years) else ""
        is_hist, year_n = parse_slice_year(raw_sl)

        db_snap = p_max_dbs[i] if i < len(p_max_dbs) else ""
        p_max = resolve_max_power_mw_for_save(
            p_maxs[i] if i < len(p_maxs) else "",
            db_snap,
            rd_save,
        )
        dt_val = parse_peak_datetime(dts[i] if i < len(dts) else None)
        tnv = parse_decimal(tnvs[i] if i < len(tnvs) else None)
        if ez_mode:
            oes = None
            ees = None
        else:
            oes = parse_decimal(oess[i] if i < len(oess) else None)
            ees = parse_decimal(eess[i] if i < len(eess) else None)
        es_raw = ess[i] if i < len(ess) else ""
        combined_es = parse_decimal(es_raw) if str(es_raw or "").strip() else None
        ez_val = (
            parse_decimal(ezss[i] if i < len(ezss) else None)
            if ez_mode
            else None
        )

        if is_hist:
            year_n = None
        elif year_n is None and not rid:
            continue
        elif not is_hist and year_n is None:
            continue

        if rid:
            row = demand_model.query.get(rid)
            if row is None:
                continue
            if fk_column_name is not None and parent_id is not None:
                if getattr(row, fk_column_name) != parent_id:
                    continue
            if pvc is not _UNSET and model_supports_perimeter_variant(demand_model):
                if getattr(row, "perimeter_variant_code", None) != pvc:
                    continue
        else:
            row = demand_model()
            if fk_column_name is not None and parent_id is not None:
                setattr(row, fk_column_name, parent_id)
            if pvc is not _UNSET and model_supports_perimeter_variant(demand_model):
                row.perimeter_variant_code = pvc
            apply_version_to_row(row, demand_model)
            row.created_by = user
            db.session.add(row)

        row.is_historical_maximum = is_hist
        row.year_number = year_n
        row.max_power_consumption_mw = p_max
        row.peak_datetime_msk = dt_val
        row.avg_daily_air_temp_c = tnv
        row.combined_on_oes = oes
        row.combined_on_ees = ees
        if "combined_on_es" in demand_model.__table__.columns:
            row.combined_on_es = combined_es
        if "combined_on_ez" in demand_model.__table__.columns and ez_mode:
            row.combined_on_ez = ez_val
        row.modified_by = user

        saved += 1

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise
    return saved, deleted_n


def _summary_demand_model_class(name: str) -> Type[Any]:
    from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
        CentralizedZoneDemandParameter,
    )
    from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
        EesDemandParameter,
    )
    from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
        EesRussiaDemandParameter,
    )
    from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
        EnergySystemTypeDemandParameter,
    )
    from app.power_demand.models.energy_systems.energy_unit_demand_parameter_model import (
        EnergyUnitDemandParameter,
    )
    from app.power_demand.models.energy_systems.energy_zone_demand_parameter_model import (
        EnergyZoneDemandParameter,
    )
    from app.power_demand.models.energy_systems.regional_energy_system_demand_parameter_model import (
        RegionalEnergySystemDemandParameter,
    )
    from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
        SynchronousAreaDemandParameter,
    )
    from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
        UnionEnergySystemDemandParameter,
    )
    from app.power_demand.models.territories.federal_district_demand_parameter_model import (
        FederalDistrictDemandParameter,
    )
    from app.power_demand.models.territories.regional_district_demand_parameter_model import (
        RegionalDistrictDemandParameter,
    )
    from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
        RussiaFederationDemandParameter,
    )
    mapping: dict[str, Type[Any]] = {
        "CentralizedZoneDemandParameter": CentralizedZoneDemandParameter,
        "EesDemandParameter": EesDemandParameter,
        "EesRussiaDemandParameter": EesRussiaDemandParameter,
        "EnergySystemTypeDemandParameter": EnergySystemTypeDemandParameter,
        "EnergyUnitDemandParameter": EnergyUnitDemandParameter,
        "EnergyZoneDemandParameter": EnergyZoneDemandParameter,
        "RegionalEnergySystemDemandParameter": RegionalEnergySystemDemandParameter,
        "SynchronousAreaDemandParameter": SynchronousAreaDemandParameter,
        "UnionEnergySystemDemandParameter": UnionEnergySystemDemandParameter,
        "FederalDistrictDemandParameter": FederalDistrictDemandParameter,
        "RegionalDistrictDemandParameter": RegionalDistrictDemandParameter,
        "RussiaFederationDemandParameter": RussiaFederationDemandParameter,
    }
    cls = mapping.get(name)
    if cls is None:
        raise ValueError(f"Неизвестная модель параметров нагрузки: {name}")
    return cls


def _dash_summary_display(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def summary_cell_display_value(row: Any, parameter_key: str, rounding_digits: int) -> str:
    """Строка для отображения ячейки сводки после сохранения (как в demand_summary_services)."""
    if str(parameter_key or "").startswith("coeff_k_"):
        if hasattr(row, "__table__") and parameter_key in row.__table__.columns:
            v = getattr(row, parameter_key, None)
            return _dash_summary_display(
                format_decimal_trim_for_display(v, digits=rounding_digits)
            )
        return "—"
    if parameter_key == "max_power":
        v = getattr(row, "max_power_consumption_mw", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "peak_datetime":
        s = format_peak_datetime_for_slice(
            getattr(row, "peak_datetime_msk", None),
            bool(getattr(row, "is_historical_maximum", False)),
        )
        return _dash_summary_display(s)
    if parameter_key == "avg_temp":
        v = getattr(row, "avg_daily_air_temp_c", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=0))
    if parameter_key == "combined_on_oes":
        v = getattr(row, "combined_on_oes", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "combined_on_ees":
        v = getattr(row, "combined_on_ees", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "combined_on_es":
        v = getattr(row, "combined_on_es", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "combined_on_ez":
        v = getattr(row, "combined_on_ez", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "combined_on_fo":
        v = getattr(row, "combined_on_fo", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key == "combined_on_cz":
        v = getattr(row, "combined_on_cz", None)
        return _dash_summary_display(format_decimal_trim_for_display(v, digits=rounding_digits))
    if parameter_key in ("note", "entity_note"):
        return _dash_summary_display(getattr(row, "note", None))
    return "—"


_SUMMARY_STANDALONE_DEMAND_MODELS = frozenset(
    {
        "CentralizedZoneDemandParameter",
        "EesDemandParameter",
        "EesRussiaDemandParameter",
        "RussiaFederationDemandParameter",
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
    """«hist» → исторический максимум; иначе — номер года."""
    if slice_key is None or slice_key == "":
        raise ValueError("Не указан срез (год или исторический максимум).")
    if slice_key == "hist":
        return True, None
    try:
        y = int(slice_key)
    except (TypeError, ValueError) as exc:
        raise ValueError("Некорректный срез.") from exc
    return False, y


def find_demand_row_for_summary_slice(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    is_hist: bool,
    year_n: Optional[int],
    database_version_id: Optional[int] = None,
    perimeter_variant_code: Any = _UNSET,
) -> Any:
    q = model.query
    vid = database_version_id
    if vid is None and hasattr(model, "database_version_id"):
        vid = get_current_version()
    if vid is not None and hasattr(model, "database_version_id"):
        q = q.filter(model.database_version_id == vid)
    if parent_fk_column is not None:
        if parent_id is None:
            return None
        q = q.filter(getattr(model, parent_fk_column) == parent_id)
    if perimeter_variant_code is not _UNSET:
        q = filter_query_by_perimeter_variant(q, model, perimeter_variant_code)
    q = q.filter(model.is_historical_maximum == is_hist)
    if is_hist:
        q = q.filter(model.year_number.is_(None))
    else:
        if year_n is None:
            return None
        q = q.filter(model.year_number == year_n)
    return q.first()


def create_demand_row_for_summary_slice(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    is_hist: bool,
    year_n: Optional[int],
    database_version_id: Optional[int] = None,
    perimeter_variant_code: Any = _UNSET,
) -> Any:
    row = model()
    if parent_fk_column is not None:
        setattr(row, parent_fk_column, parent_id)
    if perimeter_variant_code is not _UNSET and model_supports_perimeter_variant(model):
        row.perimeter_variant_code = perimeter_variant_code
    vid = database_version_id
    if vid is None:
        vid = get_current_version()
    if hasattr(model, "database_version_id"):
        row.database_version_id = vid
    row.is_historical_maximum = is_hist
    row.year_number = None if is_hist else year_n
    row.created_by = _username()
    db.session.add(row)
    return row


def _apply_summary_field_to_row(
    row: Any,
    parameter_key: str,
    raw_value: Any,
    *,
    rounding_digits: int,
) -> None:
    if parameter_key == "max_power":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Максимальное потребление, МВт».")
        old_shown = (
            format_decimal_trim_for_display(row.max_power_consumption_mw, digits=rounding_digits)
            if row.max_power_consumption_mw is not None
            else ""
        )
        row.max_power_consumption_mw = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "peak_datetime":
        s = str(raw_value or "").strip()
        if not s:
            row.peak_datetime_msk = None
        else:
            dt_val = parse_peak_datetime(raw_value)
            if dt_val is None:
                raise ValueError(
                    "Дата и время: несуществующая дата или неверный формат "
                    "(ДД.ММ.ГГГГ ЧЧ:ММ или только год ГГГГ)."
                )
            if (
                not row.is_historical_maximum
                and row.year_number is not None
                and dt_val.year != row.year_number
            ):
                raise ValueError(
                    f"Год в дате ({dt_val.year}) должен совпадать с годом среза ({row.year_number})."
                )
            row.peak_datetime_msk = dt_val
    elif parameter_key == "avg_temp":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Среднесуточная ТНВ».")
        old_shown = (
            format_decimal_trim_for_display(row.avg_daily_air_temp_c, digits=0)
            if row.avg_daily_air_temp_c is not None
            else ""
        )
        row.avg_daily_air_temp_c = resolve_max_power_mw_for_save(
            raw_value, old_shown, 0
        )
    elif parameter_key == "combined_on_oes":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на ОЭС».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_oes, digits=rounding_digits)
            if row.combined_on_oes is not None
            else ""
        )
        row.combined_on_oes = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "combined_on_ees":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на ЕЭС».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_ees, digits=rounding_digits)
            if row.combined_on_ees is not None
            else ""
        )
        row.combined_on_ees = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "combined_on_es":
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на ЭС, МВт».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_es, digits=rounding_digits)
            if row.combined_on_es is not None
            else ""
        )
        row.combined_on_es = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "combined_on_ez":
        if "combined_on_ez" not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на энергозону».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_ez, digits=rounding_digits)
            if row.combined_on_ez is not None
            else ""
        )
        row.combined_on_ez = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "combined_on_fo":
        if "combined_on_fo" not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на ФО».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_fo, digits=rounding_digits)
            if row.combined_on_fo is not None
            else ""
        )
        row.combined_on_fo = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "combined_on_cz":
        if "combined_on_cz" not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле «Совмещенный на централизованную зону».")
        old_shown = (
            format_decimal_trim_for_display(row.combined_on_cz, digits=rounding_digits)
            if row.combined_on_cz is not None
            else ""
        )
        row.combined_on_cz = resolve_max_power_mw_for_save(
            raw_value, old_shown, rounding_digits
        )
    elif parameter_key == "note":
        if "note" not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        row.note = s if s else None
    elif str(parameter_key or "").startswith("coeff_k_"):
        if parameter_key not in row.__table__.columns:
            raise ValueError("Это поле не относится к данной строке параметров.")
        s = str(raw_value or "").strip()
        if s and parse_decimal(s) is None:
            raise ValueError("Некорректное число в поле коэффициента k.")
        prev = getattr(row, parameter_key, None)
        old_shown = (
            format_decimal_trim_for_display(prev, digits=rounding_digits)
            if prev is not None
            else ""
        )
        setattr(
            row,
            parameter_key,
            resolve_max_power_mw_for_save(raw_value, old_shown, rounding_digits),
        )


def _year_number_has_plan_feature(year_number: int) -> bool:
    yf = get_year_feature_dict() or {}
    nm = yf.get(year_number)
    if nm is None:
        return False
    return str(nm).strip().lower().replace(" ", "") == "план"


def _plan_year_extra_editable(demand_model_name: str, parameter_key: str) -> bool:
    """Поля, которые сводка «коэффициентов» может менять для годов с признаком «План» помимо max_power."""
    pk = parameter_key or ""
    if pk.startswith("coeff_k_"):
        return True
    dm = demand_model_name or ""
    # РЭС на странице ОЭС: совмещённые строки и сохранённые k.
    if dm == "RegionalEnergySystemDemandParameter":
        return pk in ("combined_on_oes", "combined_on_ees")
    # Строка объекта объединённой энергосистемы на странице ОЭС.
    if dm == "UnionEnergySystemDemandParameter":
        return pk in (
            "combined_on_ees",
            "calculated_max_power_mw",
            "calculated_combined_on_ees_mw",
        )
    return False


def _assert_plan_year_only_max_power_editable(
    year_number: Optional[int],
    is_hist: bool,
    parameter_key: str,
    *,
    demand_model_name: str,
) -> None:
    """Для годов с признаком «План» в сводке по умолчанию можно менять только max_power и см. extra."""
    if parameter_key == "entity_note":
        return
    if is_hist or year_number is None:
        return
    if _year_number_has_plan_feature(int(year_number)) and parameter_key != "max_power":
        if _plan_year_extra_editable(demand_model_name, parameter_key):
            return
        raise ValueError(
            "Для годов с признаком «План» редактируется только показатель "
            "«Максимальное потребление мощности, МВт»."
        )


def _resolve_perimeter_variant_for_save(raw: Any) -> Any:
    if raw in (None, "", _UNSET):
        return _UNSET
    return normalize_perimeter_variant_code(raw)


def save_demand_summary_cell(
    demand_model_name: str,
    parameter_key: str,
    raw_value: Any,
    *,
    rounding_digits: int,
    row_id: Optional[int] = None,
    slice_key: Any = None,
    parent_fk_column: Optional[str] = None,
    parent_id: Optional[int] = None,
    perimeter_variant_code: Any = _UNSET,
) -> str:
    """
    Создаёт или обновляет одно поле строки параметров нагрузки (сводная таблица).
    Запись выполняется во всех версиях БД (по ref_uuid справочников).
    Для РЭС с одним субъектом РФ дублирует показатель в параметры этого субъекта.
    """
    allowed = {
        "max_power",
        "peak_datetime",
        "avg_temp",
        "combined_on_oes",
        "combined_on_ees",
        "combined_on_es",
        "combined_on_ez",
        "combined_on_fo",
        "combined_on_cz",
        "coeff_k_combined_on_oes",
        "coeff_k_combined_on_ees",
        "coeff_k_calculated_max_power_mw",
        "coeff_k_calculated_combined_on_ees_mw",
        "entity_note",
    }
    if parameter_key not in allowed:
        raise ValueError("Неизвестный параметр.")

    pvc = _resolve_perimeter_variant_for_save(perimeter_variant_code)

    version_ids = all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — сохранение сводки невозможно."
        )
    anchor_vid = get_current_version()
    display_vid = anchor_vid if anchor_vid in version_ids else version_ids[0]
    user = _username()

    if parameter_key == "entity_note":
        model = _summary_demand_model_class(demand_model_name)
        _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)
        if parent_fk_column and not hasattr(model, parent_fk_column):
            raise ValueError("Некорректная привязка к объекту.")
        anchor_parent_id = parent_id
        if row_id is not None and row_id > 0:
            erow0 = model.query.get(row_id)
            if erow0 is None:
                raise ValueError("Строка не найдена.")
            if anchor_vid is not None and getattr(erow0, "database_version_id", None) != anchor_vid:
                raise ValueError("Данные относятся к другой версии БД. Обновите страницу.")
            if parent_fk_column is not None and parent_id is not None:
                if getattr(erow0, parent_fk_column, None) != parent_id:
                    raise ValueError("Строка не соответствует выбранному объекту.")
            if pvc is not _UNSET and hasattr(erow0, "perimeter_variant_code"):
                row_pvc = getattr(erow0, "perimeter_variant_code", None)
                if row_pvc != pvc:
                    raise ValueError("Строка не соответствует выбранному варианту периметра.")
            if not getattr(erow0, "is_historical_maximum", False):
                raise ValueError("Примечание сводки привязано к строке исторического максимума.")
            if parent_fk_column is not None:
                anchor_parent_id = getattr(erow0, parent_fk_column, None)
            if pvc is _UNSET and hasattr(erow0, "perimeter_variant_code"):
                pvc = getattr(erow0, "perimeter_variant_code", None)
        display_row: Any = None
        for vid in version_ids:
            parent_id_v: Optional[int] = None
            if demand_model_name not in _SUMMARY_STANDALONE_DEMAND_MODELS:
                parent_id_v = _resolve_summary_parent_id_for_version(
                    parent_fk_column, anchor_parent_id, vid
                )
            erow = find_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id_v,
                is_hist=True,
                year_n=None,
                database_version_id=vid,
                perimeter_variant_code=pvc,
            )
            if erow is None:
                if not str(raw_value or "").strip():
                    continue
                erow = create_demand_row_for_summary_slice(
                    model,
                    parent_fk_column=parent_fk_column,
                    parent_id=parent_id_v,
                    is_hist=True,
                    year_n=None,
                    database_version_id=vid,
                    perimeter_variant_code=pvc,
                )
            _apply_summary_field_to_row(erow, "note", raw_value, rounding_digits=rounding_digits)
            erow.modified_by = user
            if (
                demand_model_name == "RegionalEnergySystemDemandParameter"
                and parent_fk_column == "id_regional_energy_system"
                and parent_id_v is not None
            ):
                _mirror_res_demand_to_single_rd(
                    res_parent_id_v=int(parent_id_v),
                    parameter_key="entity_note",
                    raw_value=raw_value,
                    rounding_digits=rounding_digits,
                    is_hist=True,
                    year_n=None,
                    database_version_id=int(vid),
                )
            if vid == display_vid:
                display_row = erow
        try:
            db.session.commit()
            if display_row is not None:
                db.session.refresh(display_row)
        except IntegrityError:
            db.session.rollback()
            raise ValueError("Не удалось сохранить (конфликт данных).") from None
        if display_row is None:
            return ""
        return summary_cell_display_value(display_row, "entity_note", rounding_digits)

    model = _summary_demand_model_class(demand_model_name)
    _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)

    if parent_fk_column and not hasattr(model, parent_fk_column):
        raise ValueError("Некорректная привязка к объекту.")

    anchor_parent_id = parent_id
    is_hist: bool
    year_n: Optional[int]

    if row_id is not None and row_id > 0:
        row0 = model.query.get(row_id)
        if row0 is None:
            raise ValueError("Строка не найдена.")
        if anchor_vid is not None and getattr(row0, "database_version_id", None) != anchor_vid:
            raise ValueError("Данные относятся к другой версии БД. Обновите страницу.")
        if parent_fk_column is not None and parent_id is not None:
            if getattr(row0, parent_fk_column, None) != parent_id:
                raise ValueError("Строка не соответствует выбранному объекту.")
        if pvc is not _UNSET and hasattr(row0, "perimeter_variant_code"):
            row_pvc = getattr(row0, "perimeter_variant_code", None)
            if row_pvc != pvc:
                raise ValueError("Строка не соответствует выбранному варианту периметра ОЭС Юга.")
        if parent_fk_column is not None:
            anchor_parent_id = getattr(row0, parent_fk_column, None)
        is_hist = bool(row0.is_historical_maximum)
        year_n = row0.year_number if not is_hist else None
        if pvc is _UNSET and hasattr(row0, "perimeter_variant_code"):
            pvc = getattr(row0, "perimeter_variant_code", None)
        _assert_plan_year_only_max_power_editable(
            getattr(row0, "year_number", None),
            is_hist,
            parameter_key,
            demand_model_name=demand_model_name,
        )
    else:
        is_hist, year_n = parse_summary_slice_key(slice_key)
        _assert_plan_year_only_max_power_editable(
            year_n, is_hist, parameter_key, demand_model_name=demand_model_name
        )
        if (
            pvc is _UNSET
            and demand_model_name == "UnionEnergySystemDemandParameter"
            and parent_fk_column == "id_union_energy_system"
        ):
            pvc = None

    display_row_main: Any = None
    for vid in version_ids:
        parent_id_v: Optional[int] = None
        if demand_model_name not in _SUMMARY_STANDALONE_DEMAND_MODELS:
            parent_id_v = _resolve_summary_parent_id_for_version(
                parent_fk_column, anchor_parent_id, vid
            )
        row = find_demand_row_for_summary_slice(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id_v,
            is_hist=is_hist,
            year_n=year_n,
            database_version_id=vid,
            perimeter_variant_code=pvc,
        )
        if row is None:
            if not str(raw_value or "").strip():
                continue
            row = create_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id_v,
                is_hist=is_hist,
                year_n=year_n,
                database_version_id=vid,
                perimeter_variant_code=pvc,
            )
        _apply_summary_field_to_row(row, parameter_key, raw_value, rounding_digits=rounding_digits)
        row.modified_by = user
        if (
            demand_model_name == "RegionalEnergySystemDemandParameter"
            and parent_fk_column == "id_regional_energy_system"
            and parent_id_v is not None
        ):
            _mirror_res_demand_to_single_rd(
                res_parent_id_v=int(parent_id_v),
                parameter_key=parameter_key,
                raw_value=raw_value,
                rounding_digits=rounding_digits,
                is_hist=is_hist,
                year_n=year_n,
                database_version_id=int(vid),
            )
        if vid == display_vid:
            display_row_main = row

    try:
        db.session.commit()
        if display_row_main is not None:
            db.session.refresh(display_row_main)
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Не удалось сохранить (конфликт данных).") from None

    if display_row_main is None:
        return "—"

    return summary_cell_display_value(display_row_main, parameter_key, rounding_digits)
