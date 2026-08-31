# -*- coding: utf-8 -*-
"""Сохранение параметров распределения с формы списка (/fuel/distribution_parameters)."""

from __future__ import annotations

import re
from typing import Any

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.help_services import (
    coalesce_posted_numeric_with_stored,
    values_equal_by_display_precision,
)
from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.distribution_parameters.import_distribution_parameters_services import _parse_decimal, _parse_int
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_model import Year

_NUMERIC_ATTRS = (
    "e",
    "k",
    "bkl",
    "kn",
    "knps",
    "kngt",
    "knpg",
    "hnps",
    "hngt",
    "hnpg",
    "numb",
    "doptim",
)

_NEW_ROW_TOKEN_RE = re.compile(r"^new_[1-9][0-9]*$")


def _parse_distribution_display_rounding_digits(form) -> int:
    """Как на странице списка: -1, 0, 1, 2, 3; иначе 0 (строгое сравнение чисел)."""
    raw = form.get("distribution_save_rounding_digits")
    if raw is None or raw == "":
        return 0
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0
    if v in (-1, 0, 1, 2, 3):
        return v
    return 0


def _parse_dp_row_from_form(
    form,
    suffix: str,
    *,
    label: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Читает поля dp_<suffix>_* из формы.

    Returns:
        ({"id_ues", "id_year", "id_base", "numeric", "lim_v"}, []) при успехе,
        (None, список_ошибок) при ошибке.
    """
    errors: list[str] = []

    id_year_s = (form.get(f"dp_{suffix}_id_year") or "").strip()
    if not id_year_s:
        errors.append(f"Строка {label}: не задан расчитываемый год (year).")
        return None, errors
    try:
        id_year = int(id_year_s)
    except ValueError:
        errors.append(f"Строка {label}: некорректный расчитываемый год.")
        return None, errors
    if db.session.get(Year, id_year) is None:
        errors.append(f"Строка {label}: расчитываемый год не найден в справочнике.")
        return None, errors

    id_ues_s = (form.get(f"dp_{suffix}_id_union_energy_system") or "").strip()
    id_ues: int | None
    if not id_ues_s:
        id_ues = None
    else:
        try:
            id_ues = int(id_ues_s)
        except ValueError:
            errors.append(f"Строка {label}: некорректная ОЭС.")
            return None, errors
        if db.session.get(UnionEnergySystem, id_ues) is None:
            errors.append(f"Строка {label}: ОЭС не найдена в справочнике.")
            return None, errors

    id_base_s = (form.get(f"dp_{suffix}_id_base_year") or "").strip()
    id_base: int | None
    if not id_base_s:
        id_base = None
    else:
        try:
            id_base = int(id_base_s)
        except ValueError:
            errors.append(f"Строка {label}: некорректный расчётный год (byear).")
            return None, errors
        if db.session.get(Year, id_base) is None:
            errors.append(f"Строка {label}: расчётный год не найден в справочнике.")
            return None, errors

    numeric: dict[str, object] = {}
    for attr in _NUMERIC_ATTRS:
        raw = form.get(f"dp_{suffix}_{attr}")
        numeric[attr] = _parse_decimal(raw)

    lim_v = _parse_int(form.get(f"dp_{suffix}_lim"))

    return {
        "id_ues": id_ues,
        "id_year": id_year,
        "id_base": id_base,
        "numeric": numeric,
        "lim_v": lim_v,
    }, []


def _distribution_row_changed(
    dp: DistributionParameter,
    *,
    id_ues: int | None,
    id_year: int,
    id_base: int | None,
    numeric: dict[str, object],
    lim_v: int | None,
    display_rounding_digits: int = 0,
) -> bool:
    if dp.id_union_energy_system != id_ues:
        return True
    if dp.id_year != id_year:
        return True
    if dp.id_base_year != id_base:
        return True
    if dp.lim != lim_v:
        return True
    for attr in _NUMERIC_ATTRS:
        if not values_equal_by_display_precision(
            getattr(dp, attr),
            numeric.get(attr),
            display_rounding_digits,
        ):
            return True
    return False


def _union_energy_system_label(uid: int | None) -> str | None:
    if uid is None:
        return None
    u = db.session.get(UnionEnergySystem, uid)
    return u.name if u else f"id={uid}"


def _year_number_label(year_id: int | None):
    if year_id is None:
        return None
    y = db.session.get(Year, year_id)
    return y.number if y else f"id={year_id}"


def _distribution_parameter_change_lines(
    dp: DistributionParameter,
    *,
    id_ues: int | None,
    id_year: int,
    id_base: int | None,
    numeric: dict[str, object],
    lim_v: int | None,
    display_rounding_digits: int = 0,
) -> list[str]:
    from app.logs.services.field_names_ru import format_field_change

    et = "distribution_parameter"
    lines: list[str] = []

    if dp.id_union_energy_system != id_ues:
        lines.append(
            format_field_change(
                "id_union_energy_system",
                _union_energy_system_label(dp.id_union_energy_system),
                _union_energy_system_label(id_ues),
                et,
            )
        )
    if dp.id_year != id_year:
        lines.append(
            format_field_change(
                "id_year",
                _year_number_label(dp.id_year),
                _year_number_label(id_year),
                et,
            )
        )
    if dp.id_base_year != id_base:
        lines.append(
            format_field_change(
                "id_base_year",
                _year_number_label(dp.id_base_year),
                _year_number_label(id_base),
                et,
            )
        )
    if dp.lim != lim_v:
        lines.append(format_field_change("lim", dp.lim, lim_v, et))
    for attr in _NUMERIC_ATTRS:
        old_v = getattr(dp, attr)
        new_v = numeric.get(attr)
        if not values_equal_by_display_precision(
            old_v, new_v, display_rounding_digits
        ):
            lines.append(format_field_change(attr, old_v, new_v, et))
    return lines


def _write_distribution_parameter_delete_logs(user: Any, deleted_ids: list[int]) -> None:
    if user is None or not deleted_ids:
        return
    from app.logs.services.logging_service import log_to_db

    for did in deleted_ids:
        log_to_db(
            user,
            "Параметры распределения: удаление из таблицы",
            details=f"Удалён параметр распределения id={did}",
            entity_type="distribution_parameter",
            entity_id=did,
        )


def _write_distribution_parameter_audit_logs(user: Any, row_logs: list[tuple[int, list[str]]]) -> None:
    if user is None or not row_logs:
        return
    from app.logs.services.audit_helpers import summarize_changes
    from app.logs.services.logging_service import log_to_db

    for rid, lines in row_logs:
        if not lines:
            continue
        details = summarize_changes(f"Параметр распределения id={rid}", lines)
        log_to_db(
            user,
            "Параметры распределения: сохранение из таблицы",
            details=details,
            entity_type="distribution_parameter",
            entity_id=rid,
        )


def _validate_and_parse_bulk_apply_row(
    row: dict[str, Any],
    *,
    label: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Преобразует элемент JSON из build_distribution_parameters_bulk_copy_rows в вид как у _parse_dp_row_from_form."""
    errors: list[str] = []
    try:
        id_ues = row.get("id_union_energy_system")
        id_base = row.get("id_base_year")
        id_year = row.get("id_year")
    except (TypeError, AttributeError):
        return None, [f"{label}: некорректная структура строки."]

    if id_year is None:
        errors.append(f"{label}: не задан расчитываемый год (id_year).")
        return None, errors
    try:
        id_year = int(id_year)
    except (TypeError, ValueError):
        errors.append(f"{label}: некорректный id_year.")
        return None, errors
    if db.session.get(Year, id_year) is None:
        errors.append(f"{label}: расчитываемый год не найден в справочнике.")
        return None, errors

    if id_ues is not None:
        try:
            id_ues = int(id_ues)
        except (TypeError, ValueError):
            errors.append(f"{label}: некорректный id_union_energy_system.")
            return None, errors
        if db.session.get(UnionEnergySystem, id_ues) is None:
            errors.append(f"{label}: ОЭС не найдена в справочнике.")
            return None, errors
    else:
        id_ues = None

    if id_base is not None:
        try:
            id_base = int(id_base)
        except (TypeError, ValueError):
            errors.append(f"{label}: некорректный id_base_year.")
            return None, errors
        if db.session.get(Year, id_base) is None:
            errors.append(f"{label}: базовый год не найден в справочнике.")
            return None, errors
    else:
        id_base = None

    numeric: dict[str, object] = {}
    raw_num = row.get("numeric")
    if not isinstance(raw_num, dict):
        raw_num = {}
    for attr in _NUMERIC_ATTRS:
        raw = raw_num.get(attr)
        if raw is None or raw == "":
            numeric[attr] = None
        else:
            numeric[attr] = _parse_decimal(str(raw))

    lim_v = _parse_int(row.get("lim"))

    return {
        "id_ues": id_ues,
        "id_year": id_year,
        "id_base": id_base,
        "numeric": numeric,
        "lim_v": lim_v,
    }, []


def apply_distribution_parameters_bulk_apply_from_payload(
    rows: list[dict[str, Any]],
    *,
    user: Any | None = None,
    display_rounding_digits: int = 0,
) -> tuple[int, list[str]]:
    """
    Сохраняет строки во **все версии БД** (как импорт / сохранение формы).
    Вставка или обновление по ОЭС + базовый год + расчётный год.
    """
    from app.fuel.services.distribution_parameters.distribution_parameters_all_versions_services import (
        upsert_distribution_parameter_in_all_versions,
        ues_ref_uuid_by_id,
        year_number_by_id,
    )

    errors: list[str] = []
    if not rows:
        return 0, ["Нет строк для сохранения."]

    parsed_list: list[dict[str, Any]] = []
    seen_keys: set[tuple[int | None, int | None, int]] = set()

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"Строка {i + 1}: ожидается объект JSON.")
            continue
        label = f"Строка {i + 1}"
        parsed, row_errs = _validate_and_parse_bulk_apply_row(row, label=label)
        if row_errs:
            errors.extend(row_errs)
            continue
        assert parsed is not None
        key = (parsed["id_ues"], parsed["id_base"], parsed["id_year"])
        if key in seen_keys:
            errors.append(f"{label}: дубликат пары ОЭС/базовый год/расчётный год в запросе.")
            continue
        seen_keys.add(key)
        parsed_list.append(parsed)

    if errors:
        return 0, errors

    display_rd = display_rounding_digits if display_rounding_digits in (-1, 0, 1, 2, 3) else 0

    changed_count = 0
    row_audit_logs: list[tuple[int, list[str]]] = []

    for parsed in parsed_list:
        id_ues = parsed["id_ues"]
        id_year = parsed["id_year"]
        id_base = parsed["id_base"]
        numeric = parsed["numeric"]
        lim_v = parsed["lim_v"]

        year_num = year_number_by_id(id_year)
        byear_num = year_number_by_id(id_base)
        ues_uuid = ues_ref_uuid_by_id(id_ues)
        if year_num is None:
            errors.append("Не удалось определить номер расчётного года.")
            continue

        data = {attr: numeric.get(attr) for attr in _NUMERIC_ATTRS}
        data["lim"] = lim_v

        _blank = DistributionParameter()
        lines = _distribution_parameter_change_lines(
            _blank,
            id_ues=id_ues,
            id_year=id_year,
            id_base=id_base,
            numeric=numeric,
            lim_v=lim_v,
            display_rounding_digits=display_rd,
        )

        upsert_distribution_parameter_in_all_versions(
            ref_uuid=None,
            ues_ref_uuid=ues_uuid,
            year_number=int(year_num),
            base_year_number=int(byear_num) if byear_num is not None else None,
            data=data,
        )
        changed_count += 1
        if lines:
            row_audit_logs.append((0, lines))

    if errors:
        db.session.rollback()
        return 0, errors

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return 0, [f"Ошибка сохранения в БД: {exc}"]

    _write_distribution_parameter_audit_logs(
        user, [(rid, lines) for rid, lines in row_audit_logs if rid]
    )

    return changed_count, []


def apply_distribution_parameters_save_from_form(
    form,
    *,
    user: Any | None = None,
) -> tuple[int, list[str]]:
    """
    Обновляет/создаёт строки с формы и **синхронизирует во все версии БД**
    (общий ``ref_uuid``).

    Returns:
        (число затронутых логических строк, список ошибок).
    """
    from app.fuel.services.distribution_parameters.distribution_parameters_all_versions_services import (
        DP_SYNC_DATA_ATTRS,
        ensure_dp_ref_uuid,
        upsert_distribution_parameter_in_all_versions,
        ues_ref_uuid_by_id,
        year_number_by_id,
    )

    errors: list[str] = []

    ids_raw = (form.get("distribution_edit_row_ids") or "").strip()
    row_ids: list[int] = []
    for part in ids_raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            row_ids.append(int(part))
        except ValueError:
            errors.append(f"Некорректный идентификатор строки: {part!r}.")

    new_raw = (form.get("distribution_new_row_tokens") or "").strip()
    new_tokens: list[str] = []
    for part in new_raw.split(","):
        part = part.strip()
        if not part:
            continue
        if not _NEW_ROW_TOKEN_RE.match(part):
            errors.append(f"Некорректный маркер новой строки: {part!r}.")
            continue
        new_tokens.append(part)

    if errors:
        return 0, errors

    if not row_ids and not new_tokens:
        return 0, ["Нет строк для сохранения."]

    display_rd = _parse_distribution_display_rounding_digits(form)

    changed_count = 0
    row_audit_logs: list[tuple[int, list[str]]] = []

    def _data_from_parsed(parsed: dict[str, Any], existing: DistributionParameter | None = None) -> dict[str, Any]:
        data = {attr: parsed["numeric"].get(attr) for attr in _NUMERIC_ATTRS}
        data["lim"] = parsed["lim_v"]
        # filter_text / wname и пр. с формы сейчас не редактируются — сохраняем с якоря
        if existing is not None:
            for attr in _NUMERIC_ATTRS:
                data[attr] = coalesce_posted_numeric_with_stored(
                    getattr(existing, attr, None),
                    data[attr],
                    display_rd,
                )
            for attr in DP_SYNC_DATA_ATTRS:
                if attr in data:
                    continue
                data[attr] = getattr(existing, attr, None)
        return data

    for rid in row_ids:
        dp = db.session.get(DistributionParameter, rid)
        if dp is None:
            errors.append(f"Запись id={rid} не найдена.")
            continue

        parsed, row_errs = _parse_dp_row_from_form(form, str(rid), label=f"id={rid}")
        if row_errs:
            errors.extend(row_errs)
            continue
        assert parsed is not None

        id_ues = parsed["id_ues"]
        id_year = parsed["id_year"]
        id_base = parsed["id_base"]
        numeric = parsed["numeric"]
        lim_v = parsed["lim_v"]

        if not _distribution_row_changed(
            dp,
            id_ues=id_ues,
            id_year=id_year,
            id_base=id_base,
            numeric=numeric,
            lim_v=lim_v,
            display_rounding_digits=display_rd,
        ):
            continue

        row_audit_logs.append(
            (
                rid,
                _distribution_parameter_change_lines(
                    dp,
                    id_ues=id_ues,
                    id_year=id_year,
                    id_base=id_base,
                    numeric=numeric,
                    lim_v=lim_v,
                    display_rounding_digits=display_rd,
                ),
            )
        )

        ref = ensure_dp_ref_uuid(dp)
        ues_uuid = ues_ref_uuid_by_id(id_ues)
        year_num = year_number_by_id(id_year)
        byear_num = year_number_by_id(id_base)
        if year_num is None:
            errors.append(f"Строка id={rid}: не удалось определить номер расчётного года.")
            continue

        _ref, _a, _u, _warns = upsert_distribution_parameter_in_all_versions(
            ref_uuid=ref,
            ues_ref_uuid=ues_uuid,
            year_number=int(year_num),
            base_year_number=int(byear_num) if byear_num is not None else None,
            data=_data_from_parsed(parsed, existing=dp),
        )
        changed_count += 1

    for token in new_tokens:
        parsed, row_errs = _parse_dp_row_from_form(
            form, token, label=f"новая строка ({token})"
        )
        if row_errs:
            errors.extend(row_errs)
            continue
        assert parsed is not None

        ues_uuid = ues_ref_uuid_by_id(parsed["id_ues"])
        year_num = year_number_by_id(parsed["id_year"])
        byear_num = year_number_by_id(parsed["id_base"])
        if year_num is None:
            errors.append(f"Новая строка ({token}): не удалось определить номер расчётного года.")
            continue

        _blank = DistributionParameter()
        lines = _distribution_parameter_change_lines(
            _blank,
            id_ues=parsed["id_ues"],
            id_year=parsed["id_year"],
            id_base=parsed["id_base"],
            numeric=parsed["numeric"],
            lim_v=parsed["lim_v"],
            display_rounding_digits=display_rd,
        )

        _ref, _a, _u, _warns = upsert_distribution_parameter_in_all_versions(
            ref_uuid=None,
            ues_ref_uuid=ues_uuid,
            year_number=int(year_num),
            base_year_number=int(byear_num) if byear_num is not None else None,
            data=_data_from_parsed(parsed),
        )
        changed_count += 1
        # аудит по якорю текущей версии после flush
        if lines:
            row_audit_logs.append((0, lines))

    if errors:
        db.session.rollback()
        return 0, errors

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        return 0, [f"Ошибка сохранения в БД: {exc}"]

    _write_distribution_parameter_audit_logs(user, [(rid, lines) for rid, lines in row_audit_logs if rid])

    return changed_count, []
