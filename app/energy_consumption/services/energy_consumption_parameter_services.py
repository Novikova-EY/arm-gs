# -*- coding: utf-8 -*-
"""
CRUD и выборки для параметров потребления электроэнергии (app.energy_consumption, схема gs_ec).
"""
from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional, Type

from flask import session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.common.perimeter_variant.constants import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    legacy_nt_group_for_perimeter_code,
    perimeter_variant_codes_in_legacy_nt_group,
)
from app.common.perimeter_variant.registry import (
    filter_query_by_perimeter_variant,
    is_ees_unified_energy_system_type_entity,
    is_kaliningrad_sync_area_entity_name,
    model_supports_perimeter_variant,
    normalize_perimeter_variant_code,
    perimeter_entity_context_for_model,
    perimeter_variant_applies_to_year_code,
    perimeter_variant_display_label_for_entity,
    perimeter_variant_year_bounds_for_code,
    validate_perimeter_variant_for_entity,
)
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.database_version_services import get_current_version
from app.common.services.get_services.years.years_get_services import get_year_list_full
from app.common.services.help_services import (
    apply_thousand_grouping_to_display,
    format_decimal_trim_for_display,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.services.refdata_all_versions_common import (
    all_database_version_ids_for_refdata,
    fk_id_for_version,
)

from app.energy_consumption.models.energy_systems.energy_zone_energy_consumption_parameter_model import (
    EnergyZoneEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)

_FEDERAL_DISTRICT_SYNC_EXCLUDED_NAMES_CF = frozenset({"новые территории"})


class _UnsetType:
    pass


_UNSET = _UnsetType()

_import_actor: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ec_import_actor", default=None
)


def push_import_actor(username: str | None) -> contextvars.Token | None:
    if not username:
        return None
    return _import_actor.set(username)


def pop_import_actor(token: contextvars.Token | None) -> None:
    if token is not None:
        _import_actor.reset(token)


@contextmanager
def import_actor(username: str | None):
    token = push_import_actor(username)
    try:
        yield
    finally:
        pop_import_actor(token)


def _username() -> str:
    actor = _import_actor.get()
    if actor:
        return actor
    return session.get("username", "Неизвестный пользователь")


def _resolve_perimeter_variant_for_save(raw: object) -> str | None:
    if raw is _UNSET:
        return _UNSET  # type: ignore[return-value]
    return normalize_perimeter_variant_code(raw, known_only=True)


def _parse_reassign_variant_code_payload(raw: object) -> str | None | _UnsetType:
    """Разбор кода варианта для переноса: None — сброс (NULL в БД), _UNSET — ключ не передан."""
    if raw is _UNSET:
        return _UNSET
    if raw in (None, ""):
        return None
    return normalize_perimeter_variant_code(raw, known_only=True)


def _assert_perimeter_variant_year_allowed(
    perimeter_variant_code: str | None | _UnsetType,
    year_n: int | None,
) -> None:
    if perimeter_variant_code in (_UNSET, None) or year_n is None:
        return
    code = str(perimeter_variant_code)
    if not perimeter_variant_applies_to_year_code(code, int(year_n)):
        fy, ty = perimeter_variant_year_bounds_for_code(code)
        parts: list[str] = []
        if fy is not None:
            parts.append(f"с {fy}")
        if ty is not None:
            parts.append(f"по {ty}")
        period = " ".join(parts) if parts else "не задан"
        raise ValueError(
            f"Год {year_n} вне периода действия варианта периметра ({period})."
        )


def _resolve_perimeter_variant_for_context(
    raw: object,
    model: Type[Any],
    parent_fk_column: str | None,
    parent_id: int | None,
    *,
    validate_entity_binding: bool = True,
) -> str | None | _UnsetType:
    if raw is _UNSET:
        return _UNSET
    code = normalize_perimeter_variant_code(raw, known_only=True) if raw not in (None, "") else None
    if not model_supports_perimeter_variant(model):
        return _UNSET
    if validate_entity_binding:
        ctx = perimeter_entity_context_for_model(
            model.__name__,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
        )
        if ctx is not None:
            entity_kind, entity_name = ctx
            validate_perimeter_variant_for_entity(entity_kind, entity_name, code)
    return code


def _resolve_summary_block_perimeter_variant_code(
    raw: object,
    model: Type[Any],
    parent_fk_column: str | None,
    parent_id: int | None,
    *,
    validate_entity_binding: bool = True,
) -> str | None | _UnsetType:
    """Разбор кода варианта для блока сводки; пустое значение — сброс (NULL в БД)."""
    if raw is _UNSET:
        return _UNSET
    if raw in (None, ""):
        if not model_supports_perimeter_variant(model):
            return _UNSET
        return None
    return _resolve_perimeter_variant_for_context(
        raw,
        model,
        parent_fk_column,
        parent_id,
        validate_entity_binding=validate_entity_binding,
    )


def _perimeter_variant_codes_for_summary_block_resolve(
    model: Type[Any],
    display_perimeter_variant_code: str | None,
) -> tuple[str, ...]:
    """Коды поиска строк блока: legacy НТ-группа и O-1 той же группы для ЦЗ России."""
    base = perimeter_variant_codes_in_legacy_nt_group(display_perimeter_variant_code)
    code = str(display_perimeter_variant_code or "").strip()
    if not base and code:
        base = (code,)
    if not base:
        return ()
    model_name = getattr(model, "__name__", "")
    if model_name != "CentralizedZoneEnergyConsumptionParameter":
        return base

    def _cz_nt_group(raw: str | None) -> str | None:
        s = str(raw or "").strip()
        if not s:
            return None
        if "without_nt" in s:
            return CODE_WITHOUT_NT
        if "with_nt" in s:
            return CODE_WITH_NT
        return legacy_nt_group_for_perimeter_code(s)

    group = _cz_nt_group(code) or _cz_nt_group(base[0])
    out: list[str] = list(base)
    if group == CODE_WITH_NT:
        for extra in (CODE_WITH_NT, "o1_with_nt"):
            if extra not in out:
                out.append(extra)
    elif group == CODE_WITHOUT_NT:
        for extra in (CODE_WITHOUT_NT, "o1_without_nt"):
            if extra not in out:
                out.append(extra)
    return tuple(out)


def resolve_stored_perimeter_variant_for_summary_block(
    model: Type[Any],
    *,
    parent_fk_column: str | None,
    parent_id: int | None,
    display_perimeter_variant_code: str | None,
) -> str | None:
    """Фактический код варианта в БД для блока сводки (учитывает GAES-варианты той же НТ-группы)."""
    if not model_supports_perimeter_variant(model):
        return display_perimeter_variant_code
    for pvc in _perimeter_variant_codes_for_summary_block_resolve(
        model, display_perimeter_variant_code
    ):
        rows = get_demand_rows(
            model,
            parent_fk_column,
            parent_id,
            perimeter_variant_code=pvc,
        )
        if rows:
            stored = getattr(rows[0], "perimeter_variant_code", None)
            if stored:
                return str(stored)
            return pvc
    return display_perimeter_variant_code


def _resolve_summary_block_source_perimeter_variant_code(
    raw: object,
    model: Type[Any],
    parent_fk_column: str | None,
    parent_id: int | None,
) -> str | None | _UnsetType:
    """Исходный вариант при переносе: без проверки привязки, с подстановкой GAES-кода из БД."""
    from_pvc = _resolve_summary_block_perimeter_variant_code(
        raw,
        model,
        parent_fk_column,
        parent_id,
        validate_entity_binding=False,
    )
    if from_pvc is _UNSET or from_pvc is None:
        return from_pvc
    rows = _summary_entity_demand_rows(
        model,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        perimeter_variant_code=from_pvc,
    )
    if rows:
        return from_pvc
    resolved = resolve_stored_perimeter_variant_for_summary_block(
        model,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        display_perimeter_variant_code=str(from_pvc),
    )
    if resolved and resolved != from_pvc:
        return resolved
    return from_pvc


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
    s = str(value).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
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


def resolve_demand_load_perimeter_variant_code(
    demand_model: Type[Any],
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    *,
    display_perimeter_variant_code: str | None = None,
) -> str | None:
    """Код варианта для чтения demand_rows при «базовой» строке сводки (None).

    Сводки не подставляют вариант периметра из кода: данные читаются с тем
    значением, которое хранится в БД (конкретный код или NULL).
    """
    if display_perimeter_variant_code is not None:
        return display_perimeter_variant_code
    return None


def get_demand_rows(
    demand_model,
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    *,
    perimeter_variant_code: str | None = None,
):
    """
    Список строк параметров для родителя. fk_column_name=None — модель без FK (РФ целиком).
    """
    q = demand_model.query
    q = filter_demand_by_version(q, demand_model)
    if fk_column_name is not None and parent_id is not None:
        q = q.filter(getattr(demand_model, fk_column_name) == parent_id)
    q = filter_query_by_perimeter_variant(q, demand_model, perimeter_variant_code)
    order_parts = []
    if "is_historical_maximum" in demand_model.__table__.columns:
        order_parts.append(demand_model.is_historical_maximum.desc())
    order_parts.append(demand_model.year_number.asc().nullsfirst())
    rows = q.order_by(*order_parts).all()
    return rows


def peek_stored_perimeter_variant_code_for_parent(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
) -> str | None:
    """Сохранённый код варианта периметра у родителя (метка year IS NULL или любая строка)."""
    if not model_supports_perimeter_variant(demand_model):
        return None
    if fk_column_name is None or parent_id is None:
        return None
    q = demand_model.query
    q = filter_demand_by_version(q, demand_model)
    q = q.filter(getattr(demand_model, fk_column_name) == parent_id)
    rows = q.order_by(demand_model.year_number.asc().nullsfirst()).all()
    for row in rows:
        if getattr(row, "year_number", None) is not None:
            continue
        code = getattr(row, "perimeter_variant_code", None)
        if code:
            return str(code)
    for row in rows:
        code = getattr(row, "perimeter_variant_code", None)
        if code:
            return str(code)
    return None


def get_demand_rows_with_single_variant_fallback(
    demand_model: Type[Any],
    fk_column_name: Optional[str],
    parent_id: Optional[int],
    *,
    display_perimeter_variant_code: str | None = None,
) -> list[Any]:
    """Строки параметров без кодовой подстановки варианта периметра."""
    primary_rows = get_demand_rows(
        demand_model,
        fk_column_name,
        parent_id,
        perimeter_variant_code=display_perimeter_variant_code,
    )
    return primary_rows


def dedupe_duplicate_energy_consumption_rows_without_parent(
    model: Type[Any],
    *,
    database_version_id: int,
    year_n: int,
    perimeter_variant_code: str | None = None,
) -> None:
    """Оставляет одну строку параметра без FK-родителя на (версия, год, вариант периметра)."""
    q = model.query.filter(model.year_number == year_n)
    q = filter_by_explicit_db_version(q, model, database_version_id)
    if model_supports_perimeter_variant(model):
        q = filter_query_by_perimeter_variant(q, model, perimeter_variant_code)
    rows = q.order_by(model.id.asc()).all()
    for row in rows[1:]:
        db.session.delete(row)


def dedupe_duplicate_energy_consumption_rows_for_parent(
    model: Type[Any],
    fk_column: str,
    parent_id: int,
    *,
    database_version_id: int,
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
) -> None:
    """Оставляет одну строку на (родитель, год[, вариант]) в указанной версии БД."""
    from collections import defaultdict

    q = model.query.filter(getattr(model, fk_column) == parent_id)
    q = filter_by_explicit_db_version(q, model, database_version_id)
    if perimeter_variant_code is not _UNSET and model_supports_perimeter_variant(model):
        q = filter_query_by_perimeter_variant(q, model, perimeter_variant_code)  # type: ignore[arg-type]
    rows = q.order_by(model.year_number.asc().nullsfirst(), model.id.asc()).all()
    if len(rows) <= 1:
        return

    grouped: dict[tuple[Any, ...], list[Any]] = defaultdict(list)
    for row in rows:
        key: tuple[Any, ...] = (row.year_number,)
        if model_supports_perimeter_variant(model) and perimeter_variant_code is _UNSET:
            key = (row.year_number, getattr(row, "perimeter_variant_code", None))
        grouped[key].append(row)

    for group_rows in grouped.values():
        if len(group_rows) <= 1:
            continue
        for row in group_rows[1:]:
            db.session.delete(row)


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


def compute_energy_zone_res_aggregates(
    *,
    database_version_id: Optional[int] = None,
    id_energy_zone: Optional[int] = None,
    id_regional_energy_system: Optional[int] = None,
) -> dict[tuple[int, str | None], dict[int, tuple[Optional[Decimal], Optional[Decimal]]]]:
    """Суммы mln/sipr по (id ЭЗ, вариант периметра) → год → (mln, sipr) из РЭС, входящих в зону."""
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

    scope_rd_ids: set[int] | None = None
    if id_regional_energy_system is not None:
        res_q = RegionalEnergySystem.query.options(
            selectinload(RegionalEnergySystem.regional_districts)
        )
        res_q = _filter_version(res_q, RegionalEnergySystem)
        res_q = res_q.filter(RegionalEnergySystem.id == int(id_regional_energy_system))
        res_obj = res_q.first()
        if res_obj is None:
            return {}
        scope_rd_ids = {rd.id for rd in res_obj.regional_districts}
        zones = [
            z
            for z in zones
            if scope_rd_ids & {rd.id for rd in z.regional_districts}
        ]

    res_q = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_q = _filter_version(res_q, RegionalEnergySystem)
    all_res = list(res_q.all())

    res_supports_variant = model_supports_perimeter_variant(
        RegionalEnergySystemEnergyConsumptionParameter
    )
    out: dict[tuple[int, str | None], dict[int, tuple[Optional[Decimal], Optional[Decimal]]]] = {}

    for ez in zones:
        zone_rd_ids = {rd.id for rd in ez.regional_districts}
        res_in_zone = [
            res
            for res in all_res
            if any(rd.id in zone_rd_ids for rd in res.regional_districts)
        ]
        bucket: dict[tuple[str | None, int], tuple[list[Any], list[Any]]] = {}
        for res in res_in_zone:
            for row in _demand_rows_for_version(
                RegionalEnergySystemEnergyConsumptionParameter,
                "id_regional_energy_system",
                res.id,
                vid,
            ):
                year_n = getattr(row, "year_number", None)
                if year_n is None:
                    continue
                pvc = (
                    getattr(row, "perimeter_variant_code", None)
                    if res_supports_variant
                    else None
                )
                key = (pvc, int(year_n))
                mln_list, sipr_list = bucket.setdefault(key, ([], []))
                mln_list.append(getattr(row, "energy_consumption_mln_kvt_ch", None))
                sipr_list.append(getattr(row, "energy_consumption_sipr_mln_kvt_ch", None))

        for (pvc, year_n), (mln_vals, sipr_vals) in bucket.items():
            target = out.setdefault((ez.id, pvc), {})
            target[year_n] = (
                _sum_non_null_decimals(mln_vals),
                _sum_non_null_decimals(sipr_vals),
            )

    return out


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
    aggregates = compute_energy_zone_res_aggregates(
        database_version_id=vid,
        id_energy_zone=id_energy_zone,
        id_regional_energy_system=id_regional_energy_system,
    )
    if not aggregates:
        return

    user = _username()
    ez_supports_variant = model_supports_perimeter_variant(
        EnergyZoneEnergyConsumptionParameter
    )

    for (ez_id, pvc), by_year in aggregates.items():
        existing_ez_rows = _demand_rows_for_version(
            EnergyZoneEnergyConsumptionParameter,
            "id_energy_zone",
            ez_id,
            vid,
        )
        existing_years = {
            int(r.year_number)
            for r in existing_ez_rows
            if getattr(r, "year_number", None) is not None
        }
        all_years = existing_years | set(by_year.keys())

        for year_n in sorted(all_years):
            sum_mln, sum_sipr = by_year.get(year_n, (None, None))
            row = next(
                (
                    r
                    for r in existing_ez_rows
                    if getattr(r, "year_number", None) == year_n
                    and (
                        not ez_supports_variant
                        or getattr(r, "perimeter_variant_code", None) == pvc
                    )
                ),
                None,
            )
            if row is None:
                if sum_mln is None and sum_sipr is None:
                    continue
                row = EnergyZoneEnergyConsumptionParameter()
                row.id_energy_zone = ez_id
                if vid is not None:
                    row.database_version_id = vid
                row.year_number = year_n
                if ez_supports_variant:
                    row.perimeter_variant_code = pvc
                row.created_by = user
                db.session.add(row)
                existing_ez_rows.append(row)

            row.energy_consumption_mln_kvt_ch = sum_mln
            row.energy_consumption_sipr_mln_kvt_ch = sum_sipr
            row.modified_by = user


def _federal_district_excluded_from_sync(fd: FederalDistrict) -> bool:
    name = (getattr(fd, "name", None) or "").strip()
    cf = name.casefold()
    for prefix in ("фо - ", "фо — "):
        p = prefix.casefold()
        if cf.startswith(p):
            cf = cf[len(prefix) :].strip()
            break
    return cf in _FEDERAL_DISTRICT_SYNC_EXCLUDED_NAMES_CF


def compute_federal_district_res_aggregates(
    *,
    database_version_id: Optional[int] = None,
    id_federal_district: Optional[int] = None,
    id_regional_energy_system: Optional[int] = None,
    id_regional_district: Optional[int] = None,
) -> dict[tuple[int, str | None], dict[int, tuple[Optional[Decimal], Optional[Decimal]]]]:
    """Суммы mln/sipr по (id ФО, вариант периметра) → год → (mln, sipr) из РЭС, входящих в ФО."""
    vid = database_version_id if database_version_id is not None else get_current_version()

    def _filter_version(q, model: Type[Any]):
        if vid is not None and hasattr(model, "database_version_id"):
            q = q.filter(model.database_version_id == vid)
        return q

    fd_q = FederalDistrict.query.options(selectinload(FederalDistrict.regional_districts))
    fd_q = _filter_version(fd_q, FederalDistrict)
    if id_federal_district is not None:
        fd_q = fd_q.filter(FederalDistrict.id == int(id_federal_district))
    federal_districts = [
        fd for fd in fd_q.all() if not _federal_district_excluded_from_sync(fd)
    ]

    scope_rd_ids: set[int] | None = None
    if id_regional_district is not None:
        scope_rd_ids = {int(id_regional_district)}
    elif id_regional_energy_system is not None:
        res_q = RegionalEnergySystem.query.options(
            selectinload(RegionalEnergySystem.regional_districts)
        )
        res_q = _filter_version(res_q, RegionalEnergySystem)
        res_q = res_q.filter(RegionalEnergySystem.id == int(id_regional_energy_system))
        res_obj = res_q.first()
        scope_rd_ids = {rd.id for rd in res_obj.regional_districts} if res_obj else set()

    res_q = RegionalEnergySystem.query.options(
        selectinload(RegionalEnergySystem.regional_districts)
    )
    res_q = _filter_version(res_q, RegionalEnergySystem)
    all_res = list(res_q.all())

    res_supports_variant = model_supports_perimeter_variant(
        RegionalEnergySystemEnergyConsumptionParameter
    )
    out: dict[tuple[int, str | None], dict[int, tuple[Optional[Decimal], Optional[Decimal]]]] = {}

    for fd in federal_districts:
        fd_rd_ids = {rd.id for rd in fd.regional_districts}
        if scope_rd_ids is not None and not (fd_rd_ids & scope_rd_ids):
            continue
        res_in_fd = [
            res
            for res in all_res
            if any(rd.id in fd_rd_ids for rd in res.regional_districts)
        ]
        bucket: dict[tuple[str | None, int], tuple[list[Any], list[Any]]] = {}
        for res in res_in_fd:
            for row in _demand_rows_for_version(
                RegionalEnergySystemEnergyConsumptionParameter,
                "id_regional_energy_system",
                res.id,
                vid,
            ):
                year_n = getattr(row, "year_number", None)
                if year_n is None:
                    continue
                pvc = (
                    getattr(row, "perimeter_variant_code", None)
                    if res_supports_variant
                    else None
                )
                key = (pvc, int(year_n))
                mln_list, sipr_list = bucket.setdefault(key, ([], []))
                mln_list.append(getattr(row, "energy_consumption_mln_kvt_ch", None))
                sipr_list.append(getattr(row, "energy_consumption_sipr_mln_kvt_ch", None))

        for (pvc, year_n), (mln_vals, sipr_vals) in bucket.items():
            target = out.setdefault((fd.id, pvc), {})
            target[year_n] = (
                _sum_non_null_decimals(mln_vals),
                _sum_non_null_decimals(sipr_vals),
            )

    return out


def sync_federal_district_consumption_aggregates(
    *,
    database_version_id: Optional[int] = None,
    id_federal_district: Optional[int] = None,
    id_regional_energy_system: Optional[int] = None,
    id_regional_district: Optional[int] = None,
) -> None:
    """Пересчёт потребления по ФО как суммы показателей РЭС, входящих в округ (по субъектам ФО)."""
    vid = database_version_id if database_version_id is not None else get_current_version()
    aggregates = compute_federal_district_res_aggregates(
        database_version_id=vid,
        id_federal_district=id_federal_district,
        id_regional_energy_system=id_regional_energy_system,
        id_regional_district=id_regional_district,
    )
    if not aggregates:
        return

    user = _username()
    fd_supports_variant = model_supports_perimeter_variant(
        FederalDistrictEnergyConsumptionParameter
    )

    for (fd_id, pvc), by_year in aggregates.items():
        existing_fd_rows = _demand_rows_for_version(
            FederalDistrictEnergyConsumptionParameter,
            "id_federal_district",
            fd_id,
            vid,
        )
        existing_years = {
            int(r.year_number)
            for r in existing_fd_rows
            if getattr(r, "year_number", None) is not None
        }
        all_years = existing_years | set(by_year.keys())

        for year_n in sorted(all_years):
            sum_mln, sum_sipr = by_year.get(year_n, (None, None))
            row = next(
                (
                    r
                    for r in existing_fd_rows
                    if getattr(r, "year_number", None) == year_n
                    and (
                        not fd_supports_variant
                        or getattr(r, "perimeter_variant_code", None) == pvc
                    )
                ),
                None,
            )
            if row is None:
                if sum_mln is None and sum_sipr is None:
                    continue
                row = FederalDistrictEnergyConsumptionParameter()
                row.id_federal_district = fd_id
                if vid is not None:
                    row.database_version_id = vid
                row.year_number = year_n
                if fd_supports_variant:
                    row.perimeter_variant_code = pvc
                row.created_by = user
                db.session.add(row)
                existing_fd_rows.append(row)

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
                    f"{row_label}: некорректное число в «Потребление электрической энергии, млн кВтч»."
                )
            if _field_nonempty(ec_s) and parse_decimal(ec_s) is None:
                issues.append(
                    f"{row_label}: некорректное число в «Потребление (СиПР), млн кВтч»."
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
    *,
    perimeter_variant_code: str | None = None,
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
        if perimeter_variant_code is not None and hasattr(row, "perimeter_variant_code"):
            row.perimeter_variant_code = perimeter_variant_code

        saved += 1

    db.session.flush()
    if is_ez_tbl and parent_id is not None:
        sync_energy_zone_consumption_aggregates(id_energy_zone=int(parent_id))
    elif is_res_tbl and parent_id is not None:
        sync_energy_zone_consumption_aggregates(id_regional_energy_system=int(parent_id))
        sync_federal_district_consumption_aggregates(
            id_regional_energy_system=int(parent_id)
        )

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise
    from app.energy_consumption.services.ec_display_cache import (
        invalidate_energy_consumption_display_caches,
    )

    invalidate_energy_consumption_display_caches()
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
        perimeter_variant_code=perimeter_variant_code,
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
    mapping: dict[str, Type[Any]] = {
        "CentralizedZoneEnergyConsumptionParameter": CentralizedZoneEnergyConsumptionParameter,
        "EesEnergyConsumptionParameter": EesEnergyConsumptionParameter,
        "EesRussiaEnergyConsumptionParameter": EesRussiaEnergyConsumptionParameter,
        # Устаревшие имена классов (отдельные таблицы *_with_nt_*): одна модель + perimeter_variant_code.
        "EesRussiaWithNtEnergyConsumptionParameter": EesRussiaEnergyConsumptionParameter,
        "EnergySystemTypeEnergyConsumptionParameter": EnergySystemTypeEnergyConsumptionParameter,
        "EnergyUnitEnergyConsumptionParameter": EnergyUnitEnergyConsumptionParameter,
        "EnergyZoneEnergyConsumptionParameter": EnergyZoneEnergyConsumptionParameter,
        "RegionalEnergySystemEnergyConsumptionParameter": RegionalEnergySystemEnergyConsumptionParameter,
        "SynchronousAreaEnergyConsumptionParameter": SynchronousAreaEnergyConsumptionParameter,
        "UnionEnergySystemEnergyConsumptionParameter": UnionEnergySystemEnergyConsumptionParameter,
        "FederalDistrictEnergyConsumptionParameter": FederalDistrictEnergyConsumptionParameter,
        "RegionalDistrictEnergyConsumptionParameter": RegionalDistrictEnergyConsumptionParameter,
        "RussiaFederationEnergyConsumptionParameter": RussiaFederationEnergyConsumptionParameter,
        "RussiaFederationWithNtEnergyConsumptionParameter": RussiaFederationEnergyConsumptionParameter,
    }
    cls = mapping.get(name)
    if cls is None:
        raise ValueError(f"Неизвестная модель параметров потребления: {name}")
    return cls


def _dash_summary_display(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


_GAES_CHARGE_PARAMETER_KEY = "gaes_charge_consumption_mln_kvt_ch"
_SUMMARY_FORMULA_PROTECTED_PARAMETER_KEYS = frozenset(
    {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        "entity_note",
    }
)
_FIRST_SA_FORMULA_PERIMETER_VARIANT_CODES = frozenset(
    {
        "with_nt_with_gaes_with_kaliningrad_es",
        "with_nt_without_gaes_without_kaliningrad_es",
        "without_nt_with_gaes_without_kaliningrad_es",
        "without_nt_without_gaes_with_kaliningrad_es",
        "without_nt_without_gaes_without_kaliningrad_es",
    }
)
_EES_RUSSIA_FORMULA_PERIMETER_VARIANT_CODES = frozenset(
    {
        "with_nt_with_gaes",
        "without_nt_with_gaes",
    }
)


def _is_calculated_sync_area_base_row(parent_id: int | None) -> bool:
    if parent_id is None:
        return False

    from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

    row = SynchronousArea.query.get(parent_id)
    if row is None:
        return False
    name_cf = str(getattr(row, "name", "") or "").strip().casefold()
    return name_cf.startswith("вторая синхронная зона") or "калининград" in name_cf


def _is_summary_formula_protected_context(
    demand_model_name: str,
    parameter_key: str,
    *,
    parent_id: int | None,
    perimeter_variant_code: str | None | _UnsetType,
) -> bool:
    if parameter_key not in _SUMMARY_FORMULA_PROTECTED_PARAMETER_KEYS:
        return False

    pvc = "" if perimeter_variant_code is _UNSET else str(perimeter_variant_code or "").strip()
    if demand_model_name in (
        "EesRussiaEnergyConsumptionParameter",
        "EesRussiaWithNtEnergyConsumptionParameter",
    ):
        return pvc in _EES_RUSSIA_FORMULA_PERIMETER_VARIANT_CODES
    if demand_model_name == "SynchronousAreaEnergyConsumptionParameter":
        if pvc in _FIRST_SA_FORMULA_PERIMETER_VARIANT_CODES:
            return True
        if not pvc and _is_calculated_sync_area_base_row(parent_id):
            return True
    return False


def _assert_summary_formula_row_editable(
    demand_model_name: str,
    parameter_key: str,
    *,
    parent_id: int | None,
    perimeter_variant_code: str | None | _UnsetType,
) -> None:
    if _is_summary_formula_protected_context(
        demand_model_name,
        parameter_key,
        parent_id=parent_id,
        perimeter_variant_code=perimeter_variant_code,
    ):
        raise ValueError(
            "Эта строка рассчитывается по формуле и не редактируется вручную. "
            "Измените исходные строки, затем пересчёт обновит значение."
        )


def _summary_numeric_display(value: Any, *, digits: int) -> str:
    shown = format_decimal_trim_for_display(value, digits=digits)
    return _dash_summary_display(
        apply_thousand_grouping_to_display(shown) if shown else shown
    )


def summary_cell_display_value(row: Any, parameter_key: str, rounding_digits: int) -> str:
    """Строка для отображения ячейки сводки после сохранения."""
    display_digits = rounding_digits
    if parameter_key == "energy_consumption_mln_kvt_ch":
        v = getattr(row, "energy_consumption_mln_kvt_ch", None)
        return _summary_numeric_display(v, digits=display_digits)
    if parameter_key == "energy_consumption_sipr_mln_kvt_ch":
        v = getattr(row, "energy_consumption_sipr_mln_kvt_ch", None)
        return _summary_numeric_display(v, digits=display_digits)
    if parameter_key == _GAES_CHARGE_PARAMETER_KEY:
        v = getattr(row, "charge_consumption", None)
        return _summary_numeric_display(v, digits=display_digits)
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
    database_version_id: Optional[int] = None,
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
) -> Any:
    del is_hist
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
    if perimeter_variant_code is not _UNSET and model_supports_perimeter_variant(model):
        q = filter_query_by_perimeter_variant(q, model, perimeter_variant_code)  # type: ignore[arg-type]
    if year_n is None:
        q = q.filter(model.year_number.is_(None))
    else:
        q = q.filter(model.year_number == year_n)
    return q.first()


def create_demand_row_for_summary_slice(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    is_hist: bool,
    year_n: Optional[int],
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
    database_version_id: Optional[int] = None,
) -> Any:
    del is_hist
    row = model()
    if parent_fk_column is not None:
        setattr(row, parent_fk_column, parent_id)
    vid = database_version_id
    if vid is None:
        apply_version_to_row(row, model)
    elif hasattr(model, "database_version_id"):
        row.database_version_id = int(vid)
    row.year_number = year_n
    if perimeter_variant_code is not _UNSET and model_supports_perimeter_variant(model):
        row.perimeter_variant_code = perimeter_variant_code
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
                "Некорректное число в поле «Потребление электрической энергии, млн кВтч»."
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
            raise ValueError("Некорректное число в поле «Потребление (СиПР), млн кВтч».")
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
        "mln": "Потребление, млн кВтч",
        "sipr": "Потребление (СиПР), млн кВтч",
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


def _save_gaes_charge_summary_cell(
    raw_value: Any,
    *,
    rounding_digits: int,
    row_id: Optional[int],
    slice_key: Any,
    gaes_station_id: Optional[int],
    summary_log_scope: Optional[str] = None,
) -> str:
    """Сохранение заряда ГАЭС по станции из сводной таблицы."""
    from app.common.services.database_version_filter import set_db_version_on_create
    from app.generation.models.station.station_gaes_charge_consumption_model import (
        StationGaesChargeConsumption,
    )
    from app.generation.models.station.station_model import Station
    from app.generation.services.machine_services.machine_services import (
        is_same_decimal,
        to_decimal,
    )

    if gaes_station_id is None:
        raise ValueError("Для заряда ГАЭС укажите станцию.")

    vid = get_current_version()
    station_q = (
        Station.query.options(selectinload(Station.regional_district))
        .filter(Station.id == int(gaes_station_id))
    )
    if vid is not None:
        station_q = filter_by_explicit_db_version(station_q, Station, vid)
    station = station_q.first()
    if station is None:
        raise ValueError("Станция ГАЭС не найдена для текущей версии БД.")

    row: Any = None
    if row_id is not None and row_id > 0:
        row = StationGaesChargeConsumption.query.get(row_id)
        if row is None:
            raise ValueError("Строка не найдена.")
        if int(row.id_station or 0) != int(gaes_station_id):
            raise ValueError("Строка не соответствует выбранной станции ГАЭС.")
        if vid is not None and getattr(row, "database_version_id", None) != vid:
            raise ValueError("Данные относятся к другой версии БД. Обновите страницу.")
        year_n = getattr(row, "year_number", None)
    else:
        _, year_n = parse_summary_slice_key(slice_key)
        q = StationGaesChargeConsumption.query.filter(
            StationGaesChargeConsumption.id_station == int(gaes_station_id),
            StationGaesChargeConsumption.year_number == year_n,
        )
        q = filter_demand_by_version(q, StationGaesChargeConsumption)
        row = q.first()

    old_val = row.charge_consumption if row is not None else None

    s = str(raw_value or "").strip()
    if not s:
        new_val = None
    else:
        if parse_decimal(s) is None:
            raise ValueError(
                "Некорректное число в поле «Потребление электрической энергии ГАЭС на заряд, млн кВтч»."
            )
        old_shown = (
            format_decimal_trim_for_display(row.charge_consumption, digits=rounding_digits)
            if row is not None and row.charge_consumption is not None
            else ""
        )
        new_val = resolve_max_power_mw_for_save(raw_value, old_shown, rounding_digits)

    if row is None:
        if new_val is None:
            return "—"
        row = StationGaesChargeConsumption(
            id_station=int(gaes_station_id),
            year_number=year_n,
            charge_consumption=new_val,
        )
        set_db_version_on_create(row)
        row.created_by = _username()
        db.session.add(row)
    else:
        row.charge_consumption = new_val

    row.modified_by = _username()
    try:
        db.session.commit()
        db.session.refresh(row)
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Не удалось сохранить (конфликт данных).") from None

    from app.energy_consumption.services.ec_display_cache import (
        invalidate_energy_consumption_display_caches,
    )

    invalidate_energy_consumption_display_caches()

    year_n = getattr(row, "year_number", None)
    if (
        summary_log_scope in ("oes", "fo", "ez")
        and year_n is not None
        and not is_same_decimal(to_decimal(old_val), to_decimal(new_val))
    ):
        from app.energy_consumption.services.energy_consumption_summary_logging import (
            log_gaes_charge_from_summary_table,
        )

        rd = getattr(station, "regional_district", None)
        rd_name = rd.name if rd and getattr(rd, "name", None) else "не указано"
        log_gaes_charge_from_summary_table(
            _username(),
            summary_log_scope=summary_log_scope,
            station_id=int(gaes_station_id),
            station_name=station.name or "Без названия",
            rd_name=rd_name,
            year=int(year_n),
            old_val=old_val,
            new_val=new_val,
            database_version_id=getattr(row, "database_version_id", None) or vid,
        )

    try:
        persist_computed_energy_consumption_summary_rows_after_change(
            rounding_digits=rounding_digits,
        )
    except Exception:
        db.session.rollback()
        raise

    return summary_cell_display_value(row, _GAES_CHARGE_PARAMETER_KEY, rounding_digits)


def persist_computed_energy_consumption_summary_rows_after_change(
    *,
    rounding_digits: int = 1,
) -> int:
    """Пересчитать формулы сводки потребления и записать расчётные строки в БД."""
    from app.common.services.get_services.years.years_get_services import (
        get_year_numbers_sorted_for_current_db_version,
    )
    from app.energy_consumption.services.energy_consumption_summary_import_services import (
        persist_all_energy_consumption_summary_computed_rows,
    )

    vid = get_current_version()
    years_ok = sorted(get_year_numbers_sorted_for_current_db_version() or [])
    if vid is None or not years_ok:
        return 0
    updated = persist_all_energy_consumption_summary_computed_rows(
        database_version_id=int(vid),
        years=years_ok,
        rounding_digits=rounding_digits,
    )
    db.session.commit()
    return updated


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
    gaes_station_id: Optional[int] = None,
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
) -> str:
    """
    Создаёт или обновляет одно поле строки параметров потребления (сводная таблица).
    """
    allowed = {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
        "entity_note",
        _GAES_CHARGE_PARAMETER_KEY,
    }
    if parameter_key not in allowed:
        raise ValueError("Неизвестный параметр.")

    if parameter_key == _GAES_CHARGE_PARAMETER_KEY:
        return _save_gaes_charge_summary_cell(
            raw_value,
            rounding_digits=rounding_digits,
            row_id=row_id,
            slice_key=slice_key,
            gaes_station_id=gaes_station_id,
            summary_log_scope=summary_log_scope,
        )

    if parameter_key == "entity_note":
        model = _summary_demand_model_class(demand_model_name)
        _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)
        pvc_resolved = _resolve_perimeter_variant_for_context(
            perimeter_variant_code,
            model,
            parent_fk_column,
            parent_id,
        )
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
            _assert_summary_formula_row_editable(
                demand_model_name,
                parameter_key,
                parent_id=parent_id,
                perimeter_variant_code=getattr(erow, "perimeter_variant_code", pvc_resolved),
            )
        else:
            _, note_year = parse_summary_slice_key(slice_key)
            _assert_summary_formula_row_editable(
                demand_model_name,
                parameter_key,
                parent_id=parent_id,
                perimeter_variant_code=pvc_resolved,
            )
            erow = find_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id,
                is_hist=False,
                year_n=note_year,
                perimeter_variant_code=pvc_resolved,
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
                    perimeter_variant_code=pvc_resolved,
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
        from app.energy_consumption.services.ec_display_cache import (
            invalidate_energy_consumption_display_caches,
        )

        invalidate_energy_consumption_display_caches()
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
    pvc_resolved = _resolve_perimeter_variant_for_context(
        perimeter_variant_code,
        model,
        parent_fk_column,
        parent_id,
    )

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
        if pvc_resolved is not _UNSET and model_supports_perimeter_variant(model):
            row_pvc = getattr(row, "perimeter_variant_code", None)
            if row_pvc != pvc_resolved:
                raise ValueError("Строка не соответствует выбранному варианту периметра.")
        _assert_summary_formula_row_editable(
            demand_model_name,
            parameter_key,
            parent_id=parent_id,
            perimeter_variant_code=getattr(row, "perimeter_variant_code", pvc_resolved),
        )
        # На /summary/oes|fo|ez ввод по годам не ограничен «Год с»/«Год по» варианта.
        if summary_log_scope not in ("oes", "fo", "ez"):
            _assert_perimeter_variant_year_allowed(
                getattr(row, "perimeter_variant_code", pvc_resolved),
                getattr(row, "year_number", None),
            )
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
        _assert_summary_formula_row_editable(
            demand_model_name,
            parameter_key,
            parent_id=parent_id,
            perimeter_variant_code=pvc_resolved,
        )
        if summary_log_scope not in ("oes", "fo", "ez"):
            _assert_perimeter_variant_year_allowed(pvc_resolved, year_n)
        row = find_demand_row_for_summary_slice(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            is_hist=is_hist,
            year_n=year_n,
            perimeter_variant_code=pvc_resolved,
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
                perimeter_variant_code=pvc_resolved,
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
        sync_federal_district_consumption_aggregates(
            id_regional_energy_system=int(parent_id)
        )

    try:
        db.session.commit()
        db.session.refresh(row)
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Не удалось сохранить (конфликт данных).") from None

    from app.energy_consumption.services.ec_display_cache import (
        invalidate_energy_consumption_display_caches,
    )

    invalidate_energy_consumption_display_caches()

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


def _summary_entity_demand_rows(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
) -> list[Any]:
    if perimeter_variant_code is _UNSET:
        return _demand_rows_for_version(
            model,
            parent_fk_column,
            parent_id,
            get_current_version(),
        )
    return get_demand_rows(
        model,
        parent_fk_column,
        parent_id,
        perimeter_variant_code=perimeter_variant_code,
    )


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


def _resolve_summary_parent_id_for_all_versions(
    demand_model_name: str,
    parent_fk_column: Optional[str],
    anchor_parent_id: Optional[int],
    database_version_id: int,
) -> Optional[int]:
    if demand_model_name in _SUMMARY_STANDALONE_DEMAND_MODELS:
        return None
    if parent_fk_column is None or anchor_parent_id is None:
        return None
    return _resolve_summary_parent_id_for_version(
        parent_fk_column, anchor_parent_id, database_version_id
    )


def _list_summary_entity_demand_rows_for_version(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    database_version_id: int,
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
) -> list[Any]:
    """Строки блока сводки для одной версии БД (без фильтра текущей версии)."""
    q = model.query
    if hasattr(model, "database_version_id"):
        q = q.filter(model.database_version_id == int(database_version_id))
    if parent_fk_column is not None:
        if parent_id is None:
            return []
        q = q.filter(getattr(model, parent_fk_column) == parent_id)
    if perimeter_variant_code is not _UNSET:
        q = filter_query_by_perimeter_variant(q, model, perimeter_variant_code)
    elif model_supports_perimeter_variant(model):
        q = filter_query_by_perimeter_variant(q, model, None)
    order_parts = []
    if "is_historical_maximum" in model.__table__.columns:
        order_parts.append(model.is_historical_maximum.desc())
    order_parts.append(model.year_number.asc().nullsfirst())
    return q.order_by(*order_parts).all()


def _find_source_rows_for_reassign_in_version(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    database_version_id: int,
    from_pvc: str | None | Any,
) -> list[Any]:
    rows = _list_summary_entity_demand_rows_for_version(
        model,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        database_version_id=database_version_id,
        perimeter_variant_code=from_pvc,
    )
    if rows:
        return rows
    seed = from_pvc
    if seed in (None, "", _UNSET):
        return []
    for pvc in _perimeter_variant_codes_for_summary_block_resolve(model, str(seed)):
        if pvc == from_pvc:
            continue
        rows = _list_summary_entity_demand_rows_for_version(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            database_version_id=database_version_id,
            perimeter_variant_code=pvc,
        )
        if rows:
            return rows
    return []


def _list_summary_variant_markers_for_version(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    database_version_id: int,
) -> list[Any]:
    """Строки-метки варианта блока (year_number IS NULL) для одной версии БД."""
    q = model.query
    if hasattr(model, "database_version_id"):
        q = q.filter(model.database_version_id == int(database_version_id))
    if parent_fk_column is not None:
        if parent_id is None:
            return []
        q = q.filter(getattr(model, parent_fk_column) == parent_id)
    q = q.filter(model.year_number.is_(None))
    return q.all()


def _summary_block_pvc_can_upgrade_marker(
    from_pvc: str | None, to_pvc: str | None
) -> bool:
    """Можно ли обновить pvc единственной метки без смены НТ-группы (с/без НТ)."""
    if not from_pvc or not to_pvc:
        return False

    def _nt_group(raw: str) -> str | None:
        s = str(raw or "").strip()
        if "without_nt" in s:
            return CODE_WITHOUT_NT
        if "with_nt" in s:
            return CODE_WITH_NT
        return legacy_nt_group_for_perimeter_code(s)

    from_group = _nt_group(from_pvc)
    to_group = _nt_group(to_pvc)
    if from_group is not None and to_group is not None:
        return from_group == to_group
    return False


def _ensure_summary_block_variant_marker_row(
    model: Type[Any],
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    database_version_id: int,
    perimeter_variant_code: str | None,
) -> bool:
    """Строка-метка (year_number IS NULL) с выбранным вариантом для одной версии БД."""
    user = _username()
    row = find_demand_row_for_summary_slice(
        model,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        is_hist=True,
        year_n=None,
        database_version_id=database_version_id,
        perimeter_variant_code=perimeter_variant_code,
    )
    changed = False
    if row is None:
        markers = _list_summary_variant_markers_for_version(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id,
            database_version_id=database_version_id,
        )
        unassigned = [
            m
            for m in markers
            if getattr(m, "perimeter_variant_code", None) is None
        ]
        if len(unassigned) == 1:
            row = unassigned[0]
            if getattr(row, "perimeter_variant_code", None) != perimeter_variant_code:
                row.perimeter_variant_code = perimeter_variant_code
                changed = True
        elif (
            perimeter_variant_code
            and len(markers) == 1
            and getattr(markers[0], "perimeter_variant_code", None) is not None
        ):
            only = markers[0]
            only_pvc = getattr(only, "perimeter_variant_code", None)
            if _summary_block_pvc_can_upgrade_marker(only_pvc, perimeter_variant_code):
                row = only
                if row.perimeter_variant_code != perimeter_variant_code:
                    row.perimeter_variant_code = perimeter_variant_code
                    changed = True
        if row is None:
            row = create_demand_row_for_summary_slice(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id,
                is_hist=True,
                year_n=None,
                database_version_id=database_version_id,
                perimeter_variant_code=perimeter_variant_code,
            )
            changed = True
    elif getattr(row, "perimeter_variant_code", None) != perimeter_variant_code:
        row.perimeter_variant_code = perimeter_variant_code
        changed = True
    if changed:
        row.modified_by = user
    return changed


def _reassign_summary_entity_perimeter_variant_all_versions(
    model: Type[Any],
    demand_model_name: str,
    *,
    parent_fk_column: Optional[str],
    anchor_parent_id: Optional[int],
    from_pvc: str | None | Any,
    to_pvc: str | None,
) -> int:
    """Перенос perimeter_variant_code на все строки блока во всех версиях БД."""
    version_ids = all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — сохранение варианта периметра невозможно."
        )
    user = _username()
    updated = 0
    for vid in version_ids:
        parent_id_v = _resolve_summary_parent_id_for_all_versions(
            demand_model_name,
            parent_fk_column,
            anchor_parent_id,
            vid,
        )
        source_rows = _find_source_rows_for_reassign_in_version(
            model,
            parent_fk_column=parent_fk_column,
            parent_id=parent_id_v,
            database_version_id=vid,
            from_pvc=from_pvc,
        )
        if source_rows:
            for row in source_rows:
                if getattr(row, "perimeter_variant_code", None) == to_pvc:
                    continue
                _assert_summary_perimeter_variant_reassign_allowed(
                    model,
                    row,
                    parent_fk_column=parent_fk_column,
                    parent_id=parent_id_v,
                    to_variant_code=to_pvc,
                    database_version_id=vid,
                )
                row.perimeter_variant_code = to_pvc
                row.modified_by = user
                updated += 1
        else:
            if _ensure_summary_block_variant_marker_row(
                model,
                parent_fk_column=parent_fk_column,
                parent_id=parent_id_v,
                database_version_id=vid,
                perimeter_variant_code=to_pvc,
            ):
                updated += 1
    return updated


def _commit_summary_perimeter_variant_change() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            "Не удалось сохранить вариант периметра (конфликт данных по году)."
        ) from exc
    from app.energy_consumption.services.ec_display_cache import (
        invalidate_energy_consumption_display_caches,
    )

    invalidate_energy_consumption_display_caches()


def _maybe_log_ec_summary_perimeter_variant_change(
    summary_log_scope: Optional[str],
    *,
    demand_model_name: str,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    from_variant_code: str | None,
    to_variant_code: str | None,
) -> None:
    if not summary_log_scope or summary_log_scope not in ("oes", "fo", "ez"):
        return
    ctx = perimeter_entity_context_for_model(
        demand_model_name,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
    )
    pe_kind, pe_name = ctx if ctx is not None else (None, None)
    from_label = (
        perimeter_variant_display_label_for_entity(from_variant_code, pe_kind, pe_name)
        if from_variant_code
        else "не указано"
    )
    to_label = (
        perimeter_variant_display_label_for_entity(to_variant_code, pe_kind, pe_name)
        if to_variant_code
        else "не указано"
    )
    header_bits = [f"модель={demand_model_name}"]
    if parent_fk_column and parent_id is not None:
        pl = _parent_binding_label_for_ec_summary_log(
            parent_fk_column,
            parent_id,
            database_version_id=get_current_version(),
        )
        if pl:
            header_bits.append(pl)
    from app.energy_consumption.services.energy_consumption_summary_logging import (
        log_ec_summary_cell_change,
    )

    log_ec_summary_cell_change(
        _username(),
        summary_log_scope,
        detail_chunks=[
            ", ".join(header_bits),
            f"вариант периметра: {from_label} → {to_label}",
        ],
        database_version_id=get_current_version(),
    )


def _assert_summary_perimeter_variant_reassign_allowed(
    model: Type[Any],
    row: Any,
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    to_variant_code: str | None,
    database_version_id: Optional[int] = None,
) -> None:
    year_n = getattr(row, "year_number", None)
    if year_n is None:
        return
    vid = database_version_id
    if vid is None:
        vid = getattr(row, "database_version_id", None)
    conflict = find_demand_row_for_summary_slice(
        model,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        is_hist=False,
        year_n=int(year_n),
        database_version_id=vid,
        perimeter_variant_code=to_variant_code,
    )
    if conflict is not None and getattr(conflict, "id", None) != getattr(row, "id", None):
        raise ValueError(
            f"Для года {year_n} уже есть данные с вариантом «{to_variant_code or '—'}». "
            "Сначала удалите или перенесите их вручную."
        )


def set_summary_block_variant_code(
    demand_model_name: str,
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    block_kind: str,
    perimeter_variant_code: str | None | _UnsetType = _UNSET,
    block_scope: str | None = None,
    from_variant_code: str | None | _UnsetType = _UNSET,
    summary_log_scope: Optional[str] = None,
) -> None:
    """Назначает вариант периметра всем строкам блока сводки (без переноса между вариантами)."""
    del block_kind, block_scope
    model = _summary_demand_model_class(demand_model_name)
    _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)
    if not model_supports_perimeter_variant(model):
        raise ValueError("Эта модель не поддерживает вариант периметра.")
    new_pvc = _resolve_summary_block_perimeter_variant_code(
        perimeter_variant_code,
        model,
        parent_fk_column,
        parent_id,
    )
    if new_pvc is _UNSET:
        raise ValueError("Не указан вариант периметра.")
    from_pvc = (
        _resolve_summary_block_source_perimeter_variant_code(
            from_variant_code,
            model,
            parent_fk_column,
            parent_id,
        )
        if from_variant_code is not _UNSET
        else None
    )

    updated = _reassign_summary_entity_perimeter_variant_all_versions(
        model,
        demand_model_name,
        parent_fk_column=parent_fk_column,
        anchor_parent_id=parent_id,
        from_pvc=from_pvc,
        to_pvc=new_pvc,
    )
    if not updated:
        return
    _commit_summary_perimeter_variant_change()
    from_raw = (
        None
        if from_variant_code is _UNSET
        else (None if from_variant_code in (None, "") else str(from_variant_code))
    )
    _maybe_log_ec_summary_perimeter_variant_change(
        summary_log_scope,
        demand_model_name=demand_model_name,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        from_variant_code=from_raw,
        to_variant_code=str(new_pvc) if new_pvc else None,
    )


def reassign_summary_entity_perimeter_variant(
    demand_model_name: str,
    *,
    parent_fk_column: Optional[str],
    parent_id: Optional[int],
    from_variant_code: str | None | _UnsetType = _UNSET,
    to_variant_code: str | None | _UnsetType = _UNSET,
    summary_log_scope: Optional[str] = None,
) -> int:
    """Переносит строки параметров с одного perimeter_variant_code на другой."""
    model = _summary_demand_model_class(demand_model_name)
    _validate_summary_parent_binding(demand_model_name, parent_fk_column, parent_id)
    if not model_supports_perimeter_variant(model):
        raise ValueError("Эта модель не поддерживает вариант периметра.")

    from_pvc = (
        _resolve_summary_block_source_perimeter_variant_code(
            from_variant_code,
            model,
            parent_fk_column,
            parent_id,
        )
        if from_variant_code is not _UNSET
        else None
    )
    to_pvc = _resolve_summary_block_perimeter_variant_code(
        to_variant_code,
        model,
        parent_fk_column,
        parent_id,
    )
    if to_variant_code is _UNSET or to_pvc is _UNSET:
        raise ValueError("Не указан целевой вариант периметра.")

    ctx = perimeter_entity_context_for_model(
        demand_model_name,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
    )
    if ctx is not None and is_ees_unified_energy_system_type_entity(ctx[0], ctx[1]):
        from_group = legacy_nt_group_for_perimeter_code(
            str(from_pvc) if from_pvc not in (None, "", _UNSET) else None
        )
        to_group = legacy_nt_group_for_perimeter_code(
            str(to_pvc) if to_pvc not in (None, "", _UNSET) else None
        )
        if from_group and to_group and from_group != to_group:
            raise ValueError(
                "Нельзя перенести данные между блоками «с НТ» и «без НТ» — "
                "выберите вариант в той же НТ-группе."
            )

    from_raw = (
        None
        if from_variant_code is _UNSET
        else (None if from_variant_code in (None, "") else str(from_pvc or from_variant_code))
    )

    updated = _reassign_summary_entity_perimeter_variant_all_versions(
        model,
        demand_model_name,
        parent_fk_column=parent_fk_column,
        anchor_parent_id=parent_id,
        from_pvc=from_pvc,
        to_pvc=to_pvc,
    )
    if not updated:
        return 0
    _commit_summary_perimeter_variant_change()
    _maybe_log_ec_summary_perimeter_variant_change(
        summary_log_scope,
        demand_model_name=demand_model_name,
        parent_fk_column=parent_fk_column,
        parent_id=parent_id,
        from_variant_code=from_raw,
        to_variant_code=str(to_pvc) if to_pvc else None,
    )
    return updated
