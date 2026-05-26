# -*- coding: utf-8 -*-
"""
Синхронизация данных station_details во все версии БД:
- агрегаты (Machine) по external_code;
- выработка (StationEnergyGeneration) и заряд ГАЭС (StationGaesChargeConsumption) по external_code станции.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from flask import current_app
from sqlalchemy.orm.attributes import flag_modified

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import (
    build_database_version_numbers_by_id,
    database_version_log_prefix,
)
from app.common.services.database_version_filter import (
    filter_by_explicit_db_version,
    set_db_version_on_create,
)
from app.common.services.version_entity_resolve_services import (
    resolve_gen_company_id_for_version,
    resolve_refdata_fk_id_for_version,
    resolve_station_group_id_for_version,
)
from app.common.services.tranzaction_services import _commit_with_retry, quick_fix_seq
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.generation.models.station.station_energy_generation_model import (
    StationEnergyGeneration,
)
from app.generation.models.station.station_model import Station
from app.generation.services.machine_services.machine_services import (
    is_same_decimal,
    to_decimal,
)
from app.generation.services.station_services.station_services import clear_station_aggregation_cache
from app.logs.services.logging_service import log_to_db
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.services.station_services.station_services import _is_excluded_district
from config import SCHEMA_GENERATION

logger = logging.getLogger(__name__)

_MACHINE_STATION_DETAILS_FIELDS = ("fuel_so", "note", "id_gen_company")


def _norm_text(v) -> str:
    if v is None:
        return ""
    try:
        return str(v).strip()
    except Exception:
        return ""


def _parse_int_form_val(val) -> Optional[int]:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


def _format_val_for_log(val) -> str:
    if val is None or val == "":
        return "—"
    return str(val)


def _format_gen_company_for_log(pk_id: Optional[int]) -> str:
    if not pk_id:
        return "—"
    gc = GenCompany.query.get(pk_id)
    if gc and gc.name:
        return f"{gc.name} (id={pk_id})"
    return str(pk_id)


# Обратная совместимость для импортов из других модулей
_resolve_fk_id_for_version = resolve_refdata_fk_id_for_version
_resolve_gen_company_id_for_version = resolve_gen_company_id_for_version
_resolve_station_group_id_for_version = resolve_station_group_id_for_version


def _machine_ids_from_form(form_data) -> list[int]:
    ids: set[int] = set()
    keys = form_data.keys() if hasattr(form_data, "keys") else ()
    for key in keys:
        for prefix in ("fuel_so_", "note_", "id_gen_company_"):
            if isinstance(key, str) and key.startswith(prefix):
                suffix = key[len(prefix) :]
                if suffix.isdigit():
                    ids.add(int(suffix))
    return sorted(ids)


def _read_machine_form_values(form_data, machine_id: int) -> dict[str, Any]:
    fuel_so = (form_data.get(f"fuel_so_{machine_id}", "") or "").strip()
    note = (form_data.get(f"note_{machine_id}", "") or "").strip()
    gen_company_key = f"id_gen_company_{machine_id}"
    gen_company_id = None
    if hasattr(form_data, "get"):
        gen_company_id = form_data.get(gen_company_key, type=int)
    if gen_company_id is None:
        gen_company_id = _parse_int_form_val(form_data.get(gen_company_key))
    return {
        "fuel_so": fuel_so,
        "note": note,
        "id_gen_company": gen_company_id,
    }


def _all_database_version_ids() -> list[Optional[int]]:
    version_ids: list[Optional[int]] = [None]
    for dv in DatabaseVersion.query.filter(DatabaseVersion.id.isnot(None)).all():
        if dv.id:
            version_ids.append(dv.id)
    return version_ids


def _stations_by_external_code(
    external_code: str, version_id: Optional[int]
) -> list[Station]:
    q = Station.query.filter(Station.external_code == external_code)
    q = filter_by_explicit_db_version(q, Station, version_id)
    return q.all()


def _year_values_from_form(
    form_data, field_prefix: str, start_year: int, end_year: int
) -> dict[int, Decimal | None]:
    """Значения по годам из полей формы {prefix}_{year}."""
    out: dict[int, Decimal | None] = {}
    for year in range(start_year, end_year + 1):
        raw = form_data.get(f"{field_prefix}_{year}")
        if raw is None or str(raw).strip() in ("", "—", "-"):
            out[year] = None
        else:
            out[year] = to_decimal(raw)
    return out


def _form_has_field_prefix(form_data, field_prefix: str, start_year: int, end_year: int) -> bool:
    keys = form_data.keys() if hasattr(form_data, "keys") else ()
    for year in range(start_year, end_year + 1):
        if f"{field_prefix}_{year}" in keys:
            return True
    return False


def _log_num(v) -> str:
    if v is None:
        return "не указано"
    try:
        return str(v).replace(".", ",").rstrip("0").rstrip(",") or "0"
    except Exception:
        return str(v).replace(".", ",")


def _zero_int_to_none(val: Optional[int]) -> Optional[int]:
    if val in (None, 0):
        return None
    return val


def _read_station_general_info_from_form(form_data) -> dict[str, Any]:
    st_type = _parse_int_form_val(form_data.get("id_station_type"))
    res_id = _parse_int_form_val(form_data.get("id_regional_energy_system"))
    eu_id = _parse_int_form_val(form_data.get("id_energy_unit"))
    return {
        "name": (form_data.get("name") or "").strip(),
        "id_condition_type": _parse_int_form_val(form_data.get("id_condition_type")),
        "id_station_type": _zero_int_to_none(st_type),
        "id_station_group": _parse_int_form_val(form_data.get("id_station_group")),
        "note": (form_data.get("note") or "").strip() or None,
        "id_regional_district": _parse_int_form_val(form_data.get("id_regional_district")),
        "id_regional_energy_system": _zero_int_to_none(res_id),
        "location": _norm_text(form_data.get("location")) or None,
        "id_energy_unit": _zero_int_to_none(eu_id),
    }


def _form_has_station_general_info(form_data) -> bool:
    keys = set(form_data.keys()) if hasattr(form_data, "keys") else set()
    meta_keys = {
        "name",
        "id_condition_type",
        "id_station_type",
        "id_station_group",
        "id_energy_unit",
        "id_regional_energy_system",
        "id_regional_district",
        "location",
        "note",
    }
    return bool(meta_keys & keys)


def _sync_station_general_info_all_versions(
    *,
    station_external_code: str,
    version_ids: list[Optional[int]],
    version_numbers: dict[int, str],
    meta_values: dict[str, Any],
    versions_touched_set: set[Optional[int]],
    change_log: list[str],
    warnings: list[str],
) -> int:
    """Общая информация и местоположение станции во всех версиях."""
    anchor_condition = meta_values.get("id_condition_type")
    anchor_station_type = meta_values.get("id_station_type")
    anchor_group = meta_values.get("id_station_group")
    anchor_district = meta_values.get("id_regional_district")
    anchor_res = meta_values.get("id_regional_energy_system")
    anchor_energy_unit = meta_values.get("id_energy_unit")

    updated_stations = 0
    new_name = meta_values.get("name") or ""

    for version_id in version_ids:
        targets = _stations_by_external_code(station_external_code, version_id)
        if not targets:
            continue
        version_changed = False
        for target in targets:
            resolved = {
                "id_condition_type": _resolve_fk_id_for_version(
                    ConditionType, anchor_condition, version_id
                ),
                "id_station_type": _resolve_fk_id_for_version(
                    StationType, anchor_station_type, version_id
                )
                if anchor_station_type
                else None,
                "id_station_group": _resolve_station_group_id_for_version(
                    anchor_group, version_id
                ),
                "id_regional_district": _resolve_fk_id_for_version(
                    RegionalDistrict, anchor_district, version_id
                ),
                "id_regional_energy_system": _resolve_fk_id_for_version(
                    RegionalEnergySystem, anchor_res, version_id
                )
                if anchor_res
                else None,
                "id_energy_unit": _resolve_fk_id_for_version(
                    EnergyUnit, anchor_energy_unit, version_id
                )
                if anchor_energy_unit
                else None,
            }

            if anchor_condition and resolved["id_condition_type"] is None:
                warnings.append(
                    f"Станция id={target.id}, "
                    f"{database_version_log_prefix(version_id, version_numbers)}: "
                    "состояние не сопоставлено."
                )
            if anchor_district and resolved["id_regional_district"] is None:
                warnings.append(
                    f"Станция id={target.id}, "
                    f"{database_version_log_prefix(version_id, version_numbers)}: "
                    "субъект РФ не сопоставлен."
                )

            station_changed = False

            if new_name and target.name != new_name:
                rd_for_check = resolved["id_regional_district"] or target.id_regional_district
                skip_name = False
                if not _is_excluded_district(rd_for_check, version_id):
                    conflict = (
                        Station.query.filter(
                            Station.name == new_name,
                            Station.id_regional_district == rd_for_check,
                            Station.database_version_id == version_id,
                            Station.id != target.id,
                        ).first()
                    )
                    if conflict:
                        warnings.append(
                            f"Станция id={target.id}, "
                            f"{database_version_log_prefix(version_id, version_numbers)}: "
                            f"название «{new_name}» уже занято в этом субъекте РФ, название не изменено."
                        )
                        skip_name = True
                if not skip_name:
                    change_log.append(
                        f"Общая информация, {database_version_log_prefix(version_id, version_numbers)}, "
                        f"id={target.id}: название {_format_val_for_log(target.name)} → "
                        f"{_format_val_for_log(new_name)}"
                    )
                    target.name = new_name
                    station_changed = True

            if resolved["id_condition_type"] is not None and (
                target.id_condition_type != resolved["id_condition_type"]
            ):
                target.id_condition_type = resolved["id_condition_type"]
                station_changed = True

            if target.id_station_type != resolved["id_station_type"]:
                target.id_station_type = resolved["id_station_type"]
                station_changed = True

            new_group = resolved["id_station_group"]
            if new_group and target.id_station_group != new_group:
                target.id_station_group = new_group
                station_changed = True

            new_note = meta_values.get("note")
            if _norm_text(target.note) != _norm_text(new_note):
                target.note = new_note
                station_changed = True

            if (
                resolved["id_regional_district"]
                and target.id_regional_district != resolved["id_regional_district"]
            ):
                target.id_regional_district = resolved["id_regional_district"]
                station_changed = True

            if target.id_regional_energy_system != resolved["id_regional_energy_system"]:
                target.id_regional_energy_system = resolved["id_regional_energy_system"]
                station_changed = True

            new_location = meta_values.get("location")
            if _norm_text(target.location) != _norm_text(new_location):
                target.location = new_location
                station_changed = True

            if target.id_energy_unit != resolved["id_energy_unit"]:
                target.id_energy_unit = resolved["id_energy_unit"]
                station_changed = True

            if station_changed:
                from sqlalchemy.sql import func

                target.updated_at = func.now()
                flag_modified(target, "updated_at")
                updated_stations += 1
                version_changed = True
                logger.info(
                    "[station_all_versions] general info station id=%s version_id=%s",
                    target.id,
                    version_id,
                )

        if version_changed:
            versions_touched_set.add(version_id)

    return updated_stations


def _sync_station_year_table_all_versions(
    *,
    station_external_code: str,
    version_ids: list[Optional[int]],
    version_numbers: dict[int, str],
    year_values: dict[int, Decimal | None],
    model_cls,
    value_attr: str,
    table_label: str,
    versions_touched_set: set[Optional[int]],
    change_log: list[str],
) -> int:
    """
    Копирует помесячные/погодовые значения на все станции с тем же external_code.
    Возвращает число обновлённых строк (записей по год×станция).
    """
    updated_rows = 0
    for version_id in version_ids:
        targets = _stations_by_external_code(station_external_code, version_id)
        if not targets:
            continue
        version_changed = False
        for target_station in targets:
            q = model_cls.query.filter(
                model_cls.id_station == target_station.id,
                model_cls.year_number.in_(list(year_values.keys())),
            )
            q = filter_by_explicit_db_version(q, model_cls, version_id)
            by_year = {r.year_number: r for r in q.all()}
            for year, new_val in year_values.items():
                rec = by_year.get(year)
                old_val = getattr(rec, value_attr, None) if rec else None
                if is_same_decimal(to_decimal(old_val), to_decimal(new_val)):
                    continue
                if rec is None:
                    rec = model_cls(
                        id_station=target_station.id,
                        year_number=year,
                    )
                    setattr(rec, value_attr, new_val)
                    set_db_version_on_create(rec)
                    if version_id is not None:
                        rec.database_version_id = version_id
                    db.session.add(rec)
                    by_year[year] = rec
                else:
                    setattr(rec, value_attr, new_val)
                    db.session.add(rec)
                updated_rows += 1
                version_changed = True
                change_log.append(
                    f"{table_label}, {database_version_log_prefix(version_id, version_numbers)}, "
                    f"станция id={target_station.id}, {year} г.: "
                    f"{_log_num(old_val)} → {_log_num(new_val)}"
                )
                logger.info(
                    "[station_all_versions] %s station_id=%s version_id=%s year=%s",
                    table_label,
                    target_station.id,
                    version_id,
                    year,
                )
        if version_changed:
            versions_touched_set.add(version_id)
    return updated_rows


def _apply_values_to_machine(
    machine: Machine, values: dict[str, Any]
) -> tuple[bool, list[tuple[str, str, str]]]:
    changes: list[tuple[str, str, str]] = []
    labels = {
        "fuel_so": "Топливо",
        "note": "Примечание",
        "id_gen_company": "Собственник",
    }
    for field in _MACHINE_STATION_DETAILS_FIELDS:
        if field not in values:
            continue
        new_val = values[field]
        old_val = getattr(machine, field, None)
        if field == "fuel_so":
            old_cmp, new_cmp = _norm_text(old_val), _norm_text(new_val)
        elif field == "note":
            old_cmp, new_cmp = _norm_text(old_val), _norm_text(new_val)
        else:
            old_cmp, new_cmp = old_val, new_val
        if old_cmp != new_cmp:
            setattr(machine, field, new_val)
            if field == "id_gen_company":
                old_str = _format_gen_company_for_log(old_val)
                new_str = _format_gen_company_for_log(new_val)
            else:
                old_str = _format_val_for_log(old_cmp)
                new_str = _format_val_for_log(new_cmp)
            changes.append((labels[field], old_str, new_str))
    return bool(changes), changes


def update_station_machines_all_versions_from_form(
    *,
    user,
    station: Station,
    form_data,
    start_year: int,
    end_year: int,
    sync_station_energy: bool = False,
    sync_station_gaes_charge: bool = False,
    sync_station_general_info: bool = False,
    request_meta: Optional[dict] = None,
) -> dict:
    """
    Применяет данные формы station_details во всех версиях БД.

    Агрегаты — по external_code машины (fuel_so, note, id_gen_company).
    Общая информация / местоположение — по external_code станции.
    Выработка и заряд ГАЭС — по external_code станции (st_gen_*, st_gaes_charge_*).
    """
    request_meta = request_meta or {}
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    anchor_machine_ids = _machine_ids_from_form(form_data)
    has_machine_form = bool(anchor_machine_ids)
    has_energy_form = bool(sync_station_energy)
    has_gaes_form = bool(sync_station_gaes_charge)
    has_general_info_form = sync_station_general_info and _form_has_station_general_info(
        form_data
    )

    if not has_machine_form and not has_energy_form and not has_gaes_form and not has_general_info_form:
        return {
            "versions_touched": 0,
            "updated_machines": 0,
            "updated_stations": 0,
            "updated_energy_rows": 0,
            "updated_gaes_rows": 0,
            "no_changes": True,
            "warnings": ["В форме нет данных для синхронизации во всех версиях."],
        }

    anchors_by_id = {}
    if has_machine_form:
        anchors_by_id = {
            m.id: m
            for m in Machine.query.filter(
                Machine.id.in_(anchor_machine_ids), Machine.id_station == station.id
            ).all()
        }

    version_ids = _all_database_version_ids()
    version_numbers = build_database_version_numbers_by_id()

    versions_touched_set: set[Optional[int]] = set()
    updated_machine_ids: set[int] = set()
    per_machine_log: list[str] = []
    station_table_log: list[str] = []
    warnings: list[str] = []
    aggregate_field_changes: list[tuple[str, str, str]] = []
    updated_energy_rows = 0
    updated_gaes_rows = 0
    updated_stations = 0

    station_external_code = (getattr(station, "external_code", None) or "").strip()

    logger.info(
        "[station_all_versions] START station_id=%s station_name=%r user=%r "
        "machines=%s general=%s energy=%s gaes=%s years=%s..%s meta=%s",
        station.id,
        station.name,
        user,
        has_machine_form,
        has_general_info_form,
        has_energy_form,
        has_gaes_form,
        start_year,
        end_year,
        request_meta,
    )

    needs_station_code = has_energy_form or has_gaes_form or has_general_info_form
    if needs_station_code and not station_external_code:
        warnings.append(
            "У электростанции отсутствует external_code — общая информация, выработка "
            "и заряд ГАЭС не синхронизированы во всех версиях."
        )
        has_energy_form = False
        has_gaes_form = False
        has_general_info_form = False

    if has_energy_form or has_gaes_form:
        for seq_table in (
            "gs_gen_station_energy_generations",
            "gs_gen_station_gaes_charge_consumptions",
        ):
            try:
                quick_fix_seq(SCHEMA_GENERATION, seq_table, "id")
            except Exception:
                pass

    with db.session.no_autoflush:
        if has_general_info_form and station_external_code:
            meta_values = _read_station_general_info_from_form(form_data)
            updated_stations = _sync_station_general_info_all_versions(
                station_external_code=station_external_code,
                version_ids=version_ids,
                version_numbers=version_numbers,
                meta_values=meta_values,
                versions_touched_set=versions_touched_set,
                change_log=station_table_log,
                warnings=warnings,
            )

        if has_energy_form and station_external_code:
            year_values = _year_values_from_form(form_data, "st_gen", start_year, end_year)
            updated_energy_rows = _sync_station_year_table_all_versions(
                station_external_code=station_external_code,
                version_ids=version_ids,
                version_numbers=version_numbers,
                year_values=year_values,
                model_cls=StationEnergyGeneration,
                value_attr="electricity_generation",
                table_label="Выработка электроэнергии",
                versions_touched_set=versions_touched_set,
                change_log=station_table_log,
            )

        if has_gaes_form and station_external_code:
            year_values = _year_values_from_form(
                form_data, "st_gaes_charge", start_year, end_year
            )
            updated_gaes_rows = _sync_station_year_table_all_versions(
                station_external_code=station_external_code,
                version_ids=version_ids,
                version_numbers=version_numbers,
                year_values=year_values,
                model_cls=StationGaesChargeConsumption,
                value_attr="charge_consumption",
                table_label="Потребление ГАЭС на заряд",
                versions_touched_set=versions_touched_set,
                change_log=station_table_log,
            )

        for anchor_id in (anchor_machine_ids if has_machine_form else []):
            anchor = anchors_by_id.get(anchor_id)
            if not anchor:
                warnings.append(f"Агрегат id={anchor_id} не найден на электростанции, пропуск.")
                continue

            external_code = (getattr(anchor, "external_code", None) or "").strip()
            if not external_code:
                msg = (
                    f"Агрегат №{anchor.machine_number} (id={anchor_id}): отсутствует external_code, "
                    "синхронизация во всех версиях невозможна."
                )
                warnings.append(msg)
                logger.warning("[machine_all_versions] %s", msg)
                continue

            form_values = _read_machine_form_values(form_data, anchor_id)
            anchor_gen_company_id = form_values.get("id_gen_company")
            gc_ref_uuid = None
            if anchor_gen_company_id:
                gc_anchor = GenCompany.query.get(anchor_gen_company_id)
                if gc_anchor:
                    gc_ref_uuid = (getattr(gc_anchor, "ref_uuid", None) or "").strip() or None

            machine_log_header = (
                f"external_code={external_code}, агрегат №{anchor.machine_number} "
                f"(anchor id={anchor_id}): топливо={form_values.get('fuel_so')!r}, "
                f"примечание={_norm_text(form_values.get('note'))!r}, "
                f"id_gen_company={anchor_gen_company_id}"
            )
            per_machine_log.append(machine_log_header)
            logger.info("[machine_all_versions] %s", machine_log_header)

            for version_id in version_ids:
                version_filter = (
                    Machine.database_version_id.is_(None)
                    if version_id is None
                    else (Machine.database_version_id == version_id)
                )
                targets = (
                    Machine.query.filter(Machine.external_code == external_code)
                    .filter(version_filter)
                    .all()
                )
                if not targets:
                    continue

                resolved_gen_company_id = _resolve_gen_company_id_for_version(
                    anchor_gen_company_id, version_id
                )
                if anchor_gen_company_id and resolved_gen_company_id is None:
                    warnings.append(
                        f"Агрегат external_code={external_code}, "
                        f"{database_version_log_prefix(version_id, version_numbers)}: "
                        f"собственник id={anchor_gen_company_id} не сопоставлен, поле не обновлено."
                    )

                values_to_apply = {
                    "fuel_so": form_values["fuel_so"],
                    "note": form_values["note"],
                }
                if resolved_gen_company_id is not None or anchor_gen_company_id is None:
                    values_to_apply["id_gen_company"] = resolved_gen_company_id

                version_changed = False
                for target in targets:
                    changed, field_changes = _apply_values_to_machine(target, values_to_apply)
                    if changed:
                        from sqlalchemy.sql import func

                        target.updated_at = func.now()
                        flag_modified(target, "updated_at")
                        updated_machine_ids.add(target.id)
                        version_changed = True
                        if not aggregate_field_changes and field_changes:
                            aggregate_field_changes = field_changes
                        logger.info(
                            "[machine_all_versions] updated machine id=%s version_id=%s "
                            "station_id=%s number=%s changes=%s",
                            target.id,
                            version_id,
                            target.id_station,
                            target.machine_number,
                            field_changes,
                        )
                if version_changed:
                    versions_touched_set.add(version_id)

    any_changes = (
        bool(updated_machine_ids)
        or updated_stations > 0
        or updated_energy_rows > 0
        or updated_gaes_rows > 0
    )
    if not any_changes:
        logger.info(
            "[station_all_versions] DONE no changes station_id=%s warnings=%s",
            station.id,
            warnings,
        )
        return {
            "versions_touched": 0,
            "updated_machines": 0,
            "updated_stations": 0,
            "updated_energy_rows": 0,
            "updated_gaes_rows": 0,
            "no_changes": True,
            "warnings": warnings,
            "per_machine_log": per_machine_log,
            "station_table_log": station_table_log,
        }

    try:
        for seq_table in (
            "gs_gen_station_energy_generations",
            "gs_gen_station_gaes_charge_consumptions",
        ):
            try:
                quick_fix_seq(SCHEMA_GENERATION, seq_table, "id")
            except Exception:
                pass
        _commit_with_retry()
        clear_station_aggregation_cache(
            "после синхронизации station_details во всех версиях БД"
        )
    except Exception:
        db.session.rollback()
        logger.exception(
            "[station_all_versions] COMMIT FAILED station_id=%s", station.id
        )
        raise

    versions_touched = len(versions_touched_set)
    updated_count = len(updated_machine_ids)

    log_lines = [
        "Синхронизация station_details во всех версиях БД.",
        f"Электростанция: {station.name} (id={station.id}, external_code={station_external_code or '—'})",
        f"Пользователь: {user}",
        f"Годы: {start_year}–{end_year}",
        f"Затронуто версий БД: {versions_touched}",
        f"Обновлено записей Machine: {updated_count}",
        f"Обновлено станций (общая информация): {updated_stations}",
        f"Обновлено строк выработки: {updated_energy_rows}",
        f"Обновлено строк заряда ГАЭС: {updated_gaes_rows}",
        f"Мета запроса: {request_meta}",
    ]
    if per_machine_log:
        log_lines.append("Агрегаты-источники:")
        log_lines.extend(f"  - {line}" for line in per_machine_log)
    if station_table_log:
        log_lines.append("Таблицы станции (первые 50 строк):")
        log_lines.extend(f"  - {line}" for line in station_table_log[:50])
        if len(station_table_log) > 50:
            log_lines.append(f"  ... ещё {len(station_table_log) - 50} строк")
    for label, old_val, new_val in aggregate_field_changes:
        log_lines.append(f"  {label}: было {old_val} → стало {new_val}")
    if warnings:
        log_lines.append("Предупреждения:")
        log_lines.extend(f"  ! {w}" for w in warnings)

    details_text = "\n".join(log_lines)
    log_to_db(
        user,
        "Синхронизация данных электростанции во всех версиях БД (station_details)",
        details=details_text,
        entity_type="station",
        entity_id=station.id,
    )
    if current_app:
        current_app.logger.info(
            "[station_all_versions] SUCCESS station_id=%s versions=%s machines=%s "
            "stations=%s energy_rows=%s gaes_rows=%s",
            station.id,
            versions_touched,
            updated_count,
            updated_stations,
            updated_energy_rows,
            updated_gaes_rows,
        )

    return {
        "versions_touched": versions_touched,
        "updated_machines": updated_count,
        "updated_stations": updated_stations,
        "updated_energy_rows": updated_energy_rows,
        "updated_gaes_rows": updated_gaes_rows,
        "warnings": warnings,
        "per_machine_log": per_machine_log,
        "station_table_log": station_table_log,
        "change_details": aggregate_field_changes,
    }


def update_machine_all_versions_from_machine_details_form(
    *,
    user,
    station: Station,
    machine_id: int,
    form_data,
    request_meta: Optional[dict] = None,
) -> dict:
    """
    Синхронизация полей агрегата (топливо СО, примечание, собственник) во всех версиях БД
    со страницы machine_details (поля формы с префиксом main_).
    """
    from werkzeug.datastructures import MultiDict

    def _get(key: str):
        if hasattr(form_data, "get"):
            return form_data.get(key)
        return form_data.get(key) if isinstance(form_data, dict) else None

    fuel_so = (_get("main-fuel_so") or _get("main_fuel_so") or _get("fuel_so") or "").strip()
    note = (_get("main-note") or _get("main_note") or _get("note") or "").strip()
    gen_company_id = _parse_int_form_val(
        _get("main-id_gen_company") or _get("main_id_gen_company") or _get("id_gen_company")
    )

    augmented = MultiDict(form_data)
    augmented[f"fuel_so_{machine_id}"] = fuel_so
    augmented[f"note_{machine_id}"] = note
    if gen_company_id is not None:
        augmented[f"id_gen_company_{machine_id}"] = str(gen_company_id)
    else:
        augmented[f"id_gen_company_{machine_id}"] = ""

    return update_station_machines_all_versions_from_form(
        user=user,
        station=station,
        form_data=augmented,
        start_year=0,
        end_year=0,
        sync_station_energy=False,
        sync_station_gaes_charge=False,
        sync_station_general_info=False,
        request_meta=request_meta,
    )
