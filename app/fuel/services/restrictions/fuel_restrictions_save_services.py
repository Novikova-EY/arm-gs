# -*- coding: utf-8 -*-
"""Сохранение строк «Ограничения» с формы /fuel/restrictions (во все версии БД)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.common.services.help_services import values_equal_by_display_precision
from app.extensions import db
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.fuel.services.restrictions.fuel_restrictions_all_versions_services import (
    FR_SYNC_DATA_ATTRS,
    data_dict_from_restriction,
    delete_fuel_restriction_in_all_versions,
    upsert_fuel_restriction_in_all_versions,
)
from app.fuel.services.restrictions.fuel_restrictions_list_services import (
    resolve_obl_codes_from_regional_energy_system_ids,
    resolve_oes_codes_from_union_energy_system_ids,
)
from app.fuel.services.distribution_parameters.import_distribution_parameters_services import _parse_decimal


_NEW_ROW_TOKEN_RE = re.compile(r"^new_[1-9][0-9]*$")

# Ввод пользователя + ключи строки (как в Access-форме «Ограничения»).
_EDITABLE_NUMERIC = ("year", "oes", "obl", "emin", "emax", "kobl")
_EDITABLE_TEXT = ("restriction_name", "kcur")


def _parse_rounding_digits(form) -> int:
    raw = form.get("restrictions_save_rounding_digits")
    if raw is None or raw == "":
        return 0
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0
    if v in (-1, 0, 1, 2, 3):
        return v
    return 0


def _parse_int_id(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_row_from_form(
    form,
    suffix: str,
    *,
    label: str,
    oes_obl_are_ref_ids: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Разбор строки формы.

    Для новых строк oes/obl приходят как id UnionEnergySystem / RegionalEnergySystem
    (как в фильтрах шапки) и переводятся в Access-коды.
    """
    errors: list[str] = []
    numeric: dict[str, Decimal | None] = {}
    for attr in _EDITABLE_NUMERIC:
        if attr in ("oes", "obl") and oes_obl_are_ref_ids:
            continue
        numeric[attr] = _parse_decimal(form.get(f"fr_{suffix}_{attr}"))

    if oes_obl_are_ref_ids:
        ues_id = _parse_int_id(form.get(f"fr_{suffix}_oes"))
        res_id = _parse_int_id(form.get(f"fr_{suffix}_obl"))
        if ues_id is None:
            errors.append(f"Строка {label}: не задана ОЭС.")
            numeric["oes"] = None
        else:
            oes_codes = resolve_oes_codes_from_union_energy_system_ids([ues_id])
            if not oes_codes:
                errors.append(
                    f"Строка {label}: для выбранной ОЭС нет кода Access (oes)."
                )
                numeric["oes"] = None
            else:
                numeric["oes"] = oes_codes[0]
        if res_id is None:
            numeric["obl"] = None
        else:
            obl_codes = resolve_obl_codes_from_regional_energy_system_ids([res_id])
            if not obl_codes:
                errors.append(
                    f"Строка {label}: для выбранной РЭС нет кода Access (obl)."
                )
                numeric["obl"] = None
            else:
                numeric["obl"] = obl_codes[0]
    else:
        if numeric.get("oes") is None:
            errors.append(f"Строка {label}: не задан код ОЭС (oes).")
        if numeric.get("obl") is None:
            errors.append(f"Строка {label}: не задан код РЭС (obl).")

    name = (form.get(f"fr_{suffix}_restriction_name") or "").strip() or None
    kcur = (form.get(f"fr_{suffix}_kcur") or "").strip() or None
    if name is not None and len(name) > 50:
        errors.append(f"Строка {label}: наименование длиннее 50 символов.")
    if kcur is not None and len(kcur) > 50:
        errors.append(f"Строка {label}: kcur длиннее 50 символов.")

    if numeric.get("year") is None:
        errors.append(f"Строка {label}: не задан год (year).")

    if errors:
        return None, errors

    return {
        "numeric": numeric,
        "restriction_name": name,
        "kcur": kcur,
    }, []


def _row_changed(
    row: FuelRestriction,
    parsed: dict[str, Any],
    *,
    rounding_digits: int,
) -> bool:
    for attr in _EDITABLE_NUMERIC:
        new_v = parsed["numeric"][attr]
        old_v = getattr(row, attr)
        if not values_equal_by_display_precision(old_v, new_v, rounding_digits):
            return True
    for attr in _EDITABLE_TEXT:
        new_v = parsed[attr]
        old_v = getattr(row, attr)
        if (old_v or None) != (new_v or None):
            return True
    return False


def _sync_data_from_parsed(
    parsed: dict[str, Any],
    *,
    existing: FuelRestriction | None = None,
) -> dict[str, Any]:
    """Данные для upsert: редактируемые с формы + прочие поля с якоря (если есть)."""
    data: dict[str, Any] = {}
    if existing is not None:
        data.update(data_dict_from_restriction(existing))
    data["restriction_name"] = parsed["restriction_name"]
    data["kcur"] = parsed["kcur"]
    for attr in ("emin", "emax", "kobl"):
        data[attr] = parsed["numeric"][attr]
    # Стартовый kobl как при сбросе в Access, если не задан (новые строки).
    if data.get("kobl") is None and existing is None:
        data["kobl"] = Decimal("1")
    # Гарантируем наличие всех sync-полей.
    for attr in FR_SYNC_DATA_ATTRS:
        data.setdefault(attr, None)
    return data


def apply_fuel_restrictions_save_from_form(form, *, user=None) -> tuple[int, list[str]]:
    """
    Сохраняет существующие и новые строки ограничений **во все версии БД**.

    Returns:
        (число_изменённых_или_созданных_логических_строк, список_ошибок)
    """
    _ = user
    errors: list[str] = []
    rounding_digits = _parse_rounding_digits(form)
    updated = 0

    raw_ids = (form.get("restrictions_edit_row_ids") or "").strip()
    row_ids: list[int] = []
    for part in raw_ids.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            row_ids.append(int(part))
        except ValueError:
            errors.append(f"Некорректный id строки: {part!r}.")

    for rid in row_ids:
        row = db.session.get(FuelRestriction, rid)
        if row is None:
            errors.append(f"Строка id={rid} не найдена.")
            continue
        parsed, row_errs = _parse_row_from_form(form, str(rid), label=f"id={rid}")
        if row_errs:
            errors.extend(row_errs)
            continue
        assert parsed is not None
        if not _row_changed(row, parsed, rounding_digits=rounding_digits):
            continue
        try:
            upsert_fuel_restriction_in_all_versions(
                year=parsed["numeric"]["year"],
                oes=parsed["numeric"]["oes"],
                obl=parsed["numeric"]["obl"],
                data=_sync_data_from_parsed(parsed, existing=row),
                match_year=row.year,
                match_oes=row.oes,
                match_obl=row.obl,
            )
        except ValueError as exc:
            errors.append(f"Строка id={rid}: {exc}")
            continue
        updated += 1

    raw_tokens = (form.get("restrictions_new_row_tokens") or "").strip()
    tokens: list[str] = []
    for part in raw_tokens.split(","):
        part = part.strip()
        if not part:
            continue
        if not _NEW_ROW_TOKEN_RE.match(part):
            errors.append(f"Некорректный токен новой строки: {part!r}.")
            continue
        tokens.append(part)

    for token in tokens:
        parsed, row_errs = _parse_row_from_form(
            form,
            token,
            label=token,
            oes_obl_are_ref_ids=True,
        )
        if row_errs:
            errors.extend(row_errs)
            continue
        assert parsed is not None
        try:
            upsert_fuel_restriction_in_all_versions(
                year=parsed["numeric"]["year"],
                oes=parsed["numeric"]["oes"],
                obl=parsed["numeric"]["obl"],
                data=_sync_data_from_parsed(parsed),
            )
        except ValueError as exc:
            errors.append(f"Строка {token}: {exc}")
            continue
        updated += 1

    delete_raw = (form.get("restrictions_delete_ids") or "").strip()
    for part in delete_raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            did = int(part)
        except ValueError:
            errors.append(f"Некорректный id удаления: {part!r}.")
            continue
        deleted = delete_fuel_restriction_in_all_versions(did)
        if deleted:
            updated += 1

    if errors:
        db.session.rollback()
        return 0, errors

    if updated:
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return 0, [f"Ошибка сохранения в БД: {exc}"]
    return updated, []
