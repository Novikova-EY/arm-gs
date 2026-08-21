# -*- coding: utf-8 -*-
"""
Импорт сопоставлений ОЭС с внешними идентификаторами из Excel.
Ожидаемые колонки: id_topl, name_topl, name.
"""
from __future__ import annotations

import re
import pandas as pd
from flask import current_app

from app.extensions import db
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_federal_district_model import (
    FederalDistrictExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_branch_model import (
    GenCompanyBranchExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.organizations.department_model import Department
from app.refdata.models.organizations.business_unit_model import BusinessUnit
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)


def _clean_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _excel_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _normalize_integer_like_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value).strip()
    raw = re.sub(r"\s+", "", str(value).strip())
    if not raw:
        return ""
    match = re.match(r"^([+-]?\d+)[.,]0+$", raw)
    if match:
        return match.group(1)
    return raw


def _normalize_integer_only(value: object) -> tuple[str, bool]:
    """
    Возвращает нормализованное целое (без .0) и флаг валидности.
    Пустые значения возвращаются как "" и считаются валидными.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "", True
    if isinstance(value, int):
        return str(value), True
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value)), True
        return "", False
    raw = re.sub(r"\s+", "", str(value).strip())
    if raw == "":
        return "", True
    if re.fullmatch(r"[+-]?\d+", raw):
        return raw, True
    if re.fullmatch(r"[+-]?\d+[.,]\d+", raw):
        int_part, frac = re.split(r"[.,]", raw, 1)
        if frac and set(frac) == {"0"}:
            return int_part, True
        return "", False
    return "", False

def _normalize_column_name(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def _normalize_decimal(value: object) -> tuple[object | None, bool]:
    """
    Нормализует числовое значение (поддерживает +/-, запятую как десятичный разделитель).
    Возвращает (Decimal|None, валидно ли значение). Пустые значения считаются валидными.
    """
    from decimal import Decimal, InvalidOperation

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, True
    if isinstance(value, (int, float)):
        # float -> Decimal через строку, чтобы сохранить формат 1.0 -> 1.0
        return Decimal(str(value)), True

    raw = str(value).strip().replace("\u00a0", " ").replace("\xa0", " ")
    if raw == "":
        return None, True
    raw = raw.replace(" ", "")
    raw = raw.replace(",", ".")
    try:
        return Decimal(raw), True
    except (InvalidOperation, ValueError):
        return None, False


def _apply_column_aliases(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    normalized_map = {_normalize_column_name(col): col for col in df.columns}
    rename_map: dict[str, str] = {}
    for canonical, alias_list in aliases.items():
        candidates = [canonical, *alias_list]
        for alias in candidates:
            normalized = _normalize_column_name(alias)
            if normalized in normalized_map:
                rename_map[normalized_map[normalized]] = canonical
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _normalize_name(value: object) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    return (
        raw.replace("\u00a0", " ")
        .replace("\xa0", " ")
        .replace("-", " ")
        .replace("–", " ")
        .replace("—", " ")
        .replace(".", " ")
        .replace(",", " ")
        .lower()
        .strip()
        .replace(" ", "")
    )


# Access (БД Топливо) → нормализованное UnionEnergySystem.name в АРМ.
_UES_ACCESS_NAME_ALIASES: dict[str, str] = {
    "норильск": "титэссибири",
    "норильскэнрн": "титэссибири",
}


def _apply_ues_access_name_aliases(name_map: dict[str, object]) -> None:
    """«Норильск» / «Норильск.эн.р-н» в Excel Топливо → ОЭС «ТИТЭС Сибири»."""
    for alias, canonical in _UES_ACCESS_NAME_ALIASES.items():
        target = name_map.get(canonical)
        if target is not None and alias not in name_map:
            name_map[alias] = target


def _build_name_map_for_rows(rows, fields: list[str]):
    name_map: dict[str, object] = {}
    duplicates: set[str] = set()
    for row in rows:
        for field in fields:
            candidate = getattr(row, field, None)
            normalized = _normalize_name(candidate)
            if not normalized:
                continue
            if normalized in name_map and getattr(name_map[normalized], "id", None) != row.id:
                duplicates.add(normalized)
            else:
                name_map[normalized] = row
    return name_map, duplicates


def _normalize_external_id(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()
    raw = str(value).strip()
    try:
        as_float = float(raw.replace(",", "."))
        if as_float.is_integer():
            return str(int(as_float))
    except ValueError:
        pass
    return raw


def _build_ues_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        UnionEnergySystem.query, UnionEnergySystem, current_version_id
    )
    rows = query.all()
    name_map, duplicates = _build_name_map_for_rows(rows, ["name", "name_full"])
    _apply_ues_access_name_aliases(name_map)
    return name_map, duplicates


def import_union_energy_system_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_UES_MAPPINGS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "id_topl": ["idtopl", "id", "ид", "id_топливо", "ид_топливо"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
            "name": ["name", "наименование", "название", "name_oes"],
            "nameoes_topl": ["nameoes", "nameoes_topl", "name_oes_topl"],
            "abbr_topl": ["abbr", "abbr_topl", "аббр", "сокр", "abbr_топливо"],
        },
    )

    required_columns = {"id_topl", "name_topl", "name", "nameoes_topl", "abbr_topl"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: id_topl, name_topl, name, nameoes_topl, abbr_topl."
        )

    current_version_id = get_current_db_version_id()
    name_map, duplicates = _build_ues_name_map(current_version_id)
    existing = UnionEnergySystemExternalMapping.query.all()
    by_uuid: dict[str, UnionEnergySystemExternalMapping] = {}
    by_external_id: dict[str, UnionEnergySystemExternalMapping] = {}
    by_unmatched_key: dict[tuple[str, str, str, str], UnionEnergySystemExternalMapping] = {}
    for m in existing:
        if m.external_id:
            by_external_id[_clean_text(m.external_id)] = m
        if m.union_energy_system_ref_uuid and m.union_energy_system_ref_uuid not in by_uuid:
            by_uuid[m.union_energy_system_ref_uuid] = m
            continue
        if not m.union_energy_system_ref_uuid:
            key = (
                _clean_text(m.external_id),
                _clean_text(m.external_name),
                _clean_text(m.external_nameoes),
                _clean_text(m.external_abbr),
            )
            by_unmatched_key.setdefault(key, m)
    by_unmatched_key = {
        (
            _clean_text(m.external_id),
            _clean_text(m.external_name),
            _clean_text(m.external_nameoes),
            _clean_text(m.external_abbr),
        ): m
        for m in existing
        if not m.union_energy_system_ref_uuid
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("id_topl"))
        external_name = _clean_text(row.get("name_topl"))
        external_nameoes = _clean_text(row.get("nameoes_topl"))
        external_abbr = _clean_text(row.get("abbr_topl"))
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        # Ранее при неоднозначном соответствии по name строка полностью пропускалась.
        # Теперь разрешаем такие случаи: берем первое найденное совпадение из name_map,
        # а пользователю лишь отображаем предупреждение.
        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}', использовано первое совпадение."
            )

        ues = name_map.get(normalized_local) if normalized_local else None
        if not ues:
            key = (
                _clean_text(external_id),
                _clean_text(external_name),
                _clean_text(external_nameoes),
                _clean_text(external_abbr),
            )
            if not any(key):
                errors.append(
                    f"Строка {index + 1}: пустые данные, невозможно сохранить."
                )
                continue

            existing_unmatched = by_unmatched_key.get(key)
            if not existing_unmatched and external_id:
                existing_unmatched = by_external_id.get(_clean_text(external_id))
            if existing_unmatched:
                changed = False
                if external_id and existing_unmatched.external_id != external_id:
                    existing_unmatched.external_id = external_id
                    changed = True
                if external_name and existing_unmatched.external_name != external_name:
                    existing_unmatched.external_name = external_name
                    changed = True
                if external_nameoes and existing_unmatched.external_nameoes != external_nameoes:
                    existing_unmatched.external_nameoes = external_nameoes
                    changed = True
                if external_abbr and existing_unmatched.external_abbr != external_abbr:
                    existing_unmatched.external_abbr = external_abbr
                    changed = True
                if changed:
                    updated += 1
                by_unmatched_key[key] = existing_unmatched
                if external_id:
                    by_external_id[_clean_text(external_id)] = existing_unmatched
            else:
                # external_id: use None instead of '' to avoid UniqueViolation
                # (unique constraint allows multiple NULLs, but only one empty string)
                mapping = UnionEnergySystemExternalMapping(
                    union_energy_system_ref_uuid=None,
                    external_id=external_id or None,
                    external_name=external_name or None,
                    external_nameoes=external_nameoes or None,
                    external_abbr=external_abbr or None,
                )
                db.session.add(mapping)
                db.session.flush()
                created += 1
                by_unmatched_key[key] = mapping
                if external_id:
                    by_external_id[_clean_text(external_id)] = mapping

            if not local_name:
                errors.append(f"Строка {index + 1}: отсутствует name.")
            else:
                errors.append(
                    f"Строка {index + 1}: ОЭС с названием '{local_name}' не найдена."
                )
            continue

        existing_mapping = by_uuid.get(ues.ref_uuid)
        if not existing_mapping and external_id:
            existing_mapping = by_external_id.get(_clean_text(external_id))
            if existing_mapping:
                if existing_mapping.union_energy_system_ref_uuid != ues.ref_uuid:
                    by_uuid.pop(existing_mapping.union_energy_system_ref_uuid, None)
        if existing_mapping:
            changed = False
            if existing_mapping.union_energy_system_ref_uuid != ues.ref_uuid:
                existing_mapping.union_energy_system_ref_uuid = ues.ref_uuid
                changed = True
            if external_id and existing_mapping.external_id != external_id:
                existing_mapping.external_id = external_id
                changed = True
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                changed = True
            if external_nameoes and existing_mapping.external_nameoes != external_nameoes:
                existing_mapping.external_nameoes = external_nameoes
                changed = True
            if external_abbr and existing_mapping.external_abbr != external_abbr:
                existing_mapping.external_abbr = external_abbr
                changed = True
            if changed:
                updated += 1
            by_uuid[ues.ref_uuid] = existing_mapping
            if external_id:
                by_external_id[_clean_text(external_id)] = existing_mapping
            continue

        # external_id: use None instead of '' to avoid UniqueViolation
        mapping = UnionEnergySystemExternalMapping(
            union_energy_system_ref_uuid=ues.ref_uuid,
            external_id=external_id or None,
            external_name=external_name or None,
            external_nameoes=external_nameoes or None,
            external_abbr=external_abbr or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_uuid[ues.ref_uuid] = mapping
        if external_id:
            by_external_id[_clean_text(external_id)] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений ОЭС завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_UES_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def _build_federal_district_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        FederalDistrict.query, FederalDistrict, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name", "name_full", "name_abr"])


def _build_department_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        Department.query, Department, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name", "name_full", "name_abr"])


def _build_business_unit_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        BusinessUnit.query, BusinessUnit, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name", "name_full", "name_abr"])


def _build_regional_district_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        RegionalDistrict.query, RegionalDistrict, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name", "name_full", "name_rp", "name_dp"])


def _build_regional_energy_system_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        RegionalEnergySystem.query, RegionalEnergySystem, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name", "name_full", "name_rp"])


def _build_energy_unit_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        EnergyUnit.query, EnergyUnit, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name"])


def _build_gen_company_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        GenCompany.query, GenCompany, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name"])


def _build_equipment_group_name_map(current_version_id: int | None):
    query = filter_by_explicit_db_version(
        EquipmentGroupType.query, EquipmentGroupType, current_version_id
    )
    rows = query.all()
    return _build_name_map_for_rows(rows, ["name"])


def import_federal_district_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_FD_MAPPINGS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "id_topl": ["idtopl", "id", "ид", "id_топливо", "ид_топливо"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
            "name": ["name", "наименование", "название", "name_fo"],
        },
    )

    required_columns = {"id_topl", "name_topl", "name"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: id_topl, name_topl, name."
        )

    current_version_id = get_current_db_version_id()
    name_map, duplicates = _build_federal_district_name_map(current_version_id)
    existing = FederalDistrictExternalMapping.query.all()
    by_uuid = {
        m.federal_district_ref_uuid: m
        for m in existing
        if m.federal_district_ref_uuid
    }
    by_unmatched_key = {
        (_clean_text(m.external_id), _clean_text(m.external_name)): m
        for m in existing
        if not m.federal_district_ref_uuid
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("id_topl"))
        external_name = _clean_text(row.get("name_topl"))
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}'."
            )
            continue

        fd = name_map.get(normalized_local) if normalized_local else None
        if not fd:
            key = (_clean_text(external_id), _clean_text(external_name))
            if key not in by_unmatched_key:
                # external_id: use None instead of '' to avoid UniqueViolation
                # (unique constraint allows multiple NULLs, but only one empty string)
                mapping = FederalDistrictExternalMapping(
                    federal_district_ref_uuid=None,
                    external_id=external_id or None,
                    external_name=external_name or None,
                )
                db.session.add(mapping)
                db.session.flush()
                created += 1
                by_unmatched_key[key] = mapping
            if not local_name:
                errors.append(f"Строка {index + 1}: отсутствует name.")
            else:
                errors.append(
                    f"Строка {index + 1}: ФО с названием '{local_name}' не найден."
                )
            continue

        existing_mapping = by_uuid.get(fd.ref_uuid)
        if existing_mapping:
            changed = False
            if external_id and existing_mapping.external_id != external_id:
                existing_mapping.external_id = external_id
                changed = True
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                changed = True
            if changed:
                updated += 1
            continue

        # external_id: use None instead of '' to avoid UniqueViolation
        mapping = FederalDistrictExternalMapping(
            federal_district_ref_uuid=fd.ref_uuid,
            external_id=external_id or None,
            external_name=external_name or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_uuid[fd.ref_uuid] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений ФО завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_FD_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_gen_company_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_GEN_COMPANY_MAPPINGS] start user=%s filename=%s", user, filename
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "code_topl": ["code_topl", "code", "код", "id_topl", "id"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
            "name1_topl": [
                "name1_topl",
                "name1",
                "name_1",
                "name1topl",
                "название1_топливо",
            ],
            "name": ["name", "наименование", "название", "name_gen_company"],
        },
    )

    required_columns = {"code_topl", "name_topl", "name1_topl", "name"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: code_topl, name_topl, name1_topl, name."
        )

    current_version_id = get_current_db_version_id()
    name_map, duplicates = _build_gen_company_name_map(current_version_id)
    logger.info(
        "[IMPORT_GEN_COMPANY_MAPPINGS] Версия БД=%s, доступно генерирующих компаний для сопоставления=%s, дубликатов=%s",
        current_version_id, len(name_map), len(duplicates),
    )
    existing = GenCompanyExternalMapping.query.all()
    by_uuid: dict[str, GenCompanyExternalMapping] = {
        m.gen_company_ref_uuid: m
        for m in existing
        if m.gen_company_ref_uuid
    }
    by_unmatched_key = {
        (
            _clean_text(m.external_id),
            _clean_text(m.external_name),
            _clean_text(m.external_name1),
        ): m
        for m in existing
        if not m.gen_company_ref_uuid
    }
    by_external_id: dict[str, GenCompanyExternalMapping] = {
        m.external_id: m for m in existing if m.external_id
    }

    created = 0
    updated = 0
    errors: list[str] = []
    saved_unmatched: list[str] = []  # сохранено без сопоставления
    processed = 0

    def _save_or_update_unmatched(
        external_id: str,
        external_name: str | None,
        external_name1: str | None,
        by_unmatched_key: dict,
        by_external_id: dict,
    ) -> tuple[GenCompanyExternalMapping | None, bool, bool]:
        """Сохраняет или обновляет запись без сопоставления с GenCompany. Возвращает (mapping, created, updated)."""
        key = (_clean_text(external_id), _clean_text(external_name or ""), _clean_text(external_name1 or ""))
        if not any(key):
            return None, False, False
        existing_by_id = by_external_id.get(external_id) if external_id else None
        existing_by_key = by_unmatched_key.get(key)
        target = existing_by_id or existing_by_key
        if target:
            changed = False
            if external_id and target.external_id != external_id:
                target.external_id = external_id
                changed = True
            if external_name is not None and target.external_name != external_name:
                target.external_name = external_name or None
                changed = True
            if external_name1 is not None and target.external_name1 != external_name1:
                target.external_name1 = external_name1 or None
                changed = True
            if external_id:
                by_external_id[external_id] = target
            by_unmatched_key[key] = target
            return target, False, changed
        mapping = GenCompanyExternalMapping(
            gen_company_ref_uuid=None,
            external_id=external_id or None,
            external_name=external_name or None,
            external_name1=external_name1 or None,
        )
        db.session.add(mapping)
        db.session.flush()
        if external_id:
            by_external_id[external_id] = mapping
        by_unmatched_key[key] = mapping
        return mapping, True, False

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("code_topl"))
        external_name = _clean_text(row.get("name_topl")) or None
        external_name1 = _clean_text(row.get("name1_topl")) or None
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        if normalized_local and normalized_local in duplicates:
            mapping, was_created, was_updated = _save_or_update_unmatched(
                external_id, external_name, external_name1,
                by_unmatched_key, by_external_id,
            )
            if mapping:
                if was_created:
                    created += 1
                if was_updated:
                    updated += 1
                saved_unmatched.append(
                    f"Строка {index + 1}: сохранено без сопоставления (неоднозначное имя '{local_name}')."
                )
            else:
                errors.append(
                    f"Строка {index + 1}: пустые code_topl/name_topl/name1_topl, неоднозначное имя '{local_name}'."
                )
            continue

        gen_company = name_map.get(normalized_local) if normalized_local else None
        if not gen_company:
            mapping, was_created, was_updated = _save_or_update_unmatched(
                external_id, external_name, external_name1,
                by_unmatched_key, by_external_id,
            )
            if mapping:
                if was_created:
                    created += 1
                if was_updated:
                    updated += 1
                if not local_name:
                    saved_unmatched.append(f"Строка {index + 1}: сохранено без сопоставления (name отсутствует).")
                else:
                    saved_unmatched.append(
                        f"Строка {index + 1}: сохранено без сопоставления (компания '{local_name}' не найдена)."
                    )
                    logger.warning(
                        "[IMPORT_GEN_COMPANY_MAPPINGS] Компания не найдена: '%s' "
                        "(строка %s, normalized=%r)",
                        local_name, index + 1, normalized_local,
                    )
            else:
                errors.append(
                    f"Строка {index + 1}: пустые данные code_topl/name_topl/name1_topl, невозможно сохранить."
                )
            continue

        existing_mapping = by_uuid.get(gen_company.ref_uuid)
        if existing_mapping:
            changed = False
            if external_id and existing_mapping.external_id != external_id:
                existing_mapping.external_id = external_id
                changed = True
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                changed = True
            if external_name1 and existing_mapping.external_name1 != external_name1:
                existing_mapping.external_name1 = external_name1
                changed = True
            if changed:
                updated += 1
            continue

        mapping = GenCompanyExternalMapping(
            gen_company_ref_uuid=gen_company.ref_uuid,
            external_id=external_id,
            external_name=external_name or None,
            external_name1=external_name1 or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_uuid[gen_company.ref_uuid] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    parts = [
        f"обработано {processed}",
        f"создано {created}",
        f"обновлено {updated}",
    ]
    if saved_unmatched:
        parts.append(f"без сопоставления {len(saved_unmatched)}")
    if errors:
        parts.append(f"ошибок {len(errors)}")
    message = "Импорт сопоставлений генерирующих компаний завершен: " + ", ".join(parts) + "."

    logger.info(
        "[IMPORT_GEN_COMPANY_MAPPINGS] done user=%s processed=%s created=%s updated=%s "
        "saved_unmatched=%s errors=%s",
        user, processed, created, updated, len(saved_unmatched), len(errors),
    )

    all_messages = errors + saved_unmatched
    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "saved_unmatched": saved_unmatched,
        "all_messages": all_messages,
        "message": message,
    }


def import_equipment_group_mappings_from_excel(file, user: str):
    """
    Импорт сопоставлений типов групп оборудования из Excel (по принципу gen_company).
    Ожидаемые колонки:
    - code         — код из БД Топливо (целое), аналог external_id
    - name_topl    — наименование из БД Топливо (текст)
    - gruppa_oborud — группа оборудования (текст)
    - name         — наименование типа группы в АРМ (для поиска EquipmentGroupType.name)
    - type, tm, n1, n2, p1, p2 — дополнительные поля
    """
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] start user=%s filename=%s", user, filename
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "name": ["name", "наименование", "название", "name_equipment_group"],
            "name_topl": [
                "nametopl",
                "name_t",
                "name_topl",
                "название_топливо",
                "наименование_топливо",
                "name_топливо",
                "name_ext",
                "external_name",
            ],
            "code": ["code_topl", "code", "код", "id_topl", "id"],
            "type": ["type_topl", "type", "тип"],
            "tm": ["tm_topl", "tm", "тм"],
            "n1": ["n1_topl", "n1"],
            "n2": ["n2_topl", "n2"],
            "p1": ["p1_topl", "p1"],
            "p2": ["p2_topl", "p2"],
            "gruppa_oborud": [
                "gruppa_oborud_topl",
                "gr_oborud",
                "group_equipment",
                "группа_оборудования",
            ],
        },
    )

    required_columns = {"code", "name_topl", "gruppa_oborud", "name"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: code, name_topl, gruppa_oborud, name. "
            "Опционально: type, tm, n1, n2, p1, p2."
        )

    current_version_id = get_current_db_version_id()
    name_map, duplicates = _build_equipment_group_name_map(current_version_id)

    existing = EquipmentGroupExternalMapping.query.all()
    # Маппинги без привязки к EquipmentGroupType (equipment_group_ref_uuid is None) —
    # ключ: (code, name_topl, gruppa_oborud)
    by_unmatched_key: dict[tuple[str, str, str], EquipmentGroupExternalMapping] = {
        (
            _clean_text(m.code),
            _clean_text(m.name_topl),
            _clean_text(m.gruppa_oborud),
        ): m
        for m in existing
        if not m.equipment_group_ref_uuid
    }
    # Быстрый поиск по code (в БД есть уникальный индекс по code).
    by_code: dict[int, EquipmentGroupExternalMapping] = {
        m.code: m for m in existing if m.code is not None
    }
    # Маппинги с привязкой к EquipmentGroupType — допускаем несколько строк на один ref_uuid,
    # но для каждой пары (code, equipment_group_ref_uuid) должна быть не более одной записи.
    # Ключ: (code, equipment_group_ref_uuid)
    by_key_with_ref: dict[tuple[str, str], EquipmentGroupExternalMapping] = {
        (
            _clean_text(m.code),
            m.equipment_group_ref_uuid,
        ): m
        for m in existing
        if m.equipment_group_ref_uuid
    }

    created = 0
    updated = 0
    unchanged = 0
    skipped_empty = 0
    errors: list[str] = []
    processed = 0

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] rows_in_sheet=%s", len(df.index)
    )

    for index, row in df.iterrows():
        if row.isnull().all():
            logger.debug(
                "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: skip (all values NaN)",
                index + 1,
            )
            continue

        processed += 1

        # Для сопоставления с EquipmentGroupType используем колонку name (АРМ),
        # а name_topl — это внешнее наименование из БД Топливо.
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        name_topl = _clean_text(row.get("name_topl")) or local_name
        code_raw = row.get("code")
        type_raw = row.get("type")
        n1_raw = row.get("n1")
        n2_raw = row.get("n2")
        p1_raw = row.get("p1")
        p2_raw = row.get("p2")
        tm_val = _clean_text(row.get("tm"))
        gruppa_oborud_val = _clean_text(row.get("gruppa_oborud"))

        code_text, code_ok = _normalize_integer_only(code_raw)
        type_text, type_ok = _normalize_integer_only(type_raw)
        n1_text, n1_ok = _normalize_integer_only(n1_raw)
        n2_text, n2_ok = _normalize_integer_only(n2_raw)
        p1_text, p1_ok = _normalize_integer_only(p1_raw)
        p2_text, p2_ok = _normalize_integer_only(p2_raw)

        if not code_ok:
            errors.append(
                f"Строка {index + 1}: code должно быть целым числом. Значение очищено."
            )
            code_text = ""
        if not type_ok:
            errors.append(
                f"Строка {index + 1}: type должно быть целым числом. Значение очищено."
            )
            type_text = ""
        if not n1_ok:
            errors.append(
                f"Строка {index + 1}: n1 должно быть целым числом. Значение очищено."
            )
            n1_text = ""
        if not n2_ok:
            errors.append(
                f"Строка {index + 1}: n2 должно быть целым числом. Значение очищено."
            )
            n2_text = ""
        if not p1_ok:
            errors.append(
                f"Строка {index + 1}: p1 должно быть целым числом. Значение очищено."
            )
            p1_text = ""
        if not p2_ok:
            errors.append(
                f"Строка {index + 1}: p2 должно быть целым числом. Значение очищено."
            )
            p2_text = ""

        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}', использовано первое совпадение."
            )

        equipment_group = name_map.get(normalized_local) if normalized_local else None

        logger.debug(
            "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: name=%r normalized=%r "
            "name_topl=%r code=%r gruppa_oborud=%r equipment_group_id=%s",
            index + 1,
            local_name,
            normalized_local,
            name_topl,
            code_text,
            gruppa_oborud_val,
            getattr(equipment_group, 'id', None) if equipment_group else None,
        )

        code_value = int(code_text) if code_text else None
        type_value = int(type_text) if type_text else None
        n1_value = int(n1_text) if n1_text else None
        n2_value = int(n2_text) if n2_text else None
        p1_value = int(p1_text) if p1_text else None
        p2_value = int(p2_text) if p2_text else None

        code_str = _clean_text(code_value) if code_value is not None else ""
        key = (code_str, _clean_text(name_topl), _clean_text(gruppa_oborud_val))

        if not equipment_group:
            if not any(key):
                errors.append(
                    f"Строка {index + 1}: пустые данные, невозможно сохранить."
                )
                skipped_empty += 1
                logger.info(
                    "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: skip (no equipment_group and empty key)",
                    index + 1,
                )
                continue

            existing_unmatched = by_unmatched_key.get(key)
            if existing_unmatched:
                changed = False
                if existing_unmatched.equipment_group_ref_uuid is not None:
                    existing_unmatched.equipment_group_ref_uuid = None
                    changed = True
                if name_topl and existing_unmatched.name_topl != name_topl:
                    existing_unmatched.name_topl = name_topl
                    changed = True
                if code_value is not None and existing_unmatched.code != code_value:
                    existing_unmatched.code = code_value
                    changed = True
                if type_value is not None and existing_unmatched.type_ != type_value:
                    existing_unmatched.type_ = type_value
                    changed = True
                if tm_val and existing_unmatched.tm != tm_val:
                    existing_unmatched.tm = tm_val
                    changed = True
                if (
                    gruppa_oborud_val
                    and existing_unmatched.gruppa_oborud != gruppa_oborud_val
                ):
                    existing_unmatched.gruppa_oborud = gruppa_oborud_val
                    changed = True
                if n1_value is not None and existing_unmatched.n1 != n1_value:
                    existing_unmatched.n1 = n1_value
                    changed = True
                if n2_value is not None and existing_unmatched.n2 != n2_value:
                    existing_unmatched.n2 = n2_value
                    changed = True
                if p1_value is not None and existing_unmatched.p1 != p1_value:
                    existing_unmatched.p1 = p1_value
                    changed = True
                if p2_value is not None and existing_unmatched.p2 != p2_value:
                    existing_unmatched.p2 = p2_value
                    changed = True
                if changed:
                    updated += 1
                    logger.info(
                        "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: updated unmatched mapping id=%s (no equipment_group)",
                        index + 1,
                        existing_unmatched.id,
                    )
                by_unmatched_key[key] = existing_unmatched
            else:
                mapping = EquipmentGroupExternalMapping(
                    equipment_group_ref_uuid=None,
                    name_topl=name_topl or None,
                    code=code_value,
                    type_=type_value,
                    tm=tm_val or None,
                    n1=n1_value,
                    n2=n2_value,
                    p1=p1_value,
                    p2=p2_value,
                    gruppa_oborud=gruppa_oborud_val or None,
                )
                db.session.add(mapping)
                db.session.flush()
                created += 1
                logger.info(
                    "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: created unmatched mapping id=%s (no equipment_group)",
                    index + 1,
                    mapping.id,
                )
                by_unmatched_key[key] = mapping
                if code_value is not None:
                    by_code[code_value] = mapping

            if not local_name:
                errors.append(f"Строка {index + 1}: отсутствует name.")
            else:
                errors.append(
                    f"Строка {index + 1}: тип группы оборудования '{local_name}' не найден."
                )
            logger.info(
                "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: no EquipmentGroupType found for name=%r (mapping saved without ref_uuid)",
                index + 1,
                local_name,
            )
            continue

        # Ищем существующий mapping по ключу (code, equipment_group_ref_uuid),
        # чтобы не перетирать другие строки той же группы с другими code.
        existing_mapping = None
        ref_uuid = equipment_group.ref_uuid
        if ref_uuid and code_str:
            full_key = (code_str, ref_uuid)
            existing_mapping = by_key_with_ref.get(full_key)

        # Если по полному ключу не нашли, но такой code уже есть в БД,
        # переиспользуем существующую запись вместо INSERT, чтобы не нарушить
        # уникальность uq_gs_fue_em_equipment_group_code.
        if not existing_mapping and code_value is not None:
            existing_by_code = by_code.get(code_value)
            if existing_by_code:
                existing_mapping = existing_by_code

        if existing_mapping:
            changed = False
            if name_topl and existing_mapping.name_topl != name_topl:
                existing_mapping.name_topl = name_topl
                changed = True
            if code_value is not None and existing_mapping.code != code_value:
                existing_mapping.code = code_value
                changed = True
            if type_value is not None and existing_mapping.type_ != type_value:
                existing_mapping.type_ = type_value
                changed = True
            if tm_val and existing_mapping.tm != tm_val:
                existing_mapping.tm = tm_val
                changed = True
            if (
                gruppa_oborud_val
                and existing_mapping.gruppa_oborud != gruppa_oborud_val
            ):
                existing_mapping.gruppa_oborud = gruppa_oborud_val
                changed = True
            if n1_value is not None and existing_mapping.n1 != n1_value:
                existing_mapping.n1 = n1_value
                changed = True
            if n2_value is not None and existing_mapping.n2 != n2_value:
                existing_mapping.n2 = n2_value
                changed = True
            if p1_value is not None and existing_mapping.p1 != p1_value:
                existing_mapping.p1 = p1_value
                changed = True
            if p2_value is not None and existing_mapping.p2 != p2_value:
                existing_mapping.p2 = p2_value
                changed = True
            if changed:
                updated += 1
                logger.info(
                    "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: updated mapping id=%s for equipment_group_ref_uuid=%s",
                    index + 1,
                    existing_mapping.id,
                    equipment_group.ref_uuid,
                )
            else:
                unchanged += 1
                logger.debug(
                    "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: no changes for mapping id=%s (data identical)",
                    index + 1,
                    existing_mapping.id,
                )
            continue

        # Создаем новый mapping, если ни по ключу (code, ref_uuid), ни по code ничего не нашли.
        mapping = EquipmentGroupExternalMapping(
            equipment_group_ref_uuid=equipment_group.ref_uuid,
            name_topl=name_topl or None,
            code=code_value,
            type_=type_value,
            tm=tm_val or None,
            n1=n1_value,
            n2=n2_value,
            p1=p1_value,
            p2=p2_value,
            gruppa_oborud=gruppa_oborud_val or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        # Регистрируем новый mapping в кэшах
        if code_value is not None:
            by_code[code_value] = mapping
        if ref_uuid and code_str:
            full_key = (code_str, ref_uuid)
            by_key_with_ref[full_key] = mapping
        logger.info(
            "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] row=%s: created mapping id=%s for equipment_group_ref_uuid=%s",
            index + 1,
            mapping.id,
            equipment_group.ref_uuid,
        )

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений типов групп оборудования завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"без изменений {unchanged}, пропущено пустых {skipped_empty}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_EQUIPMENT_GROUP_MAPPINGS] done user=%s processed=%s "
        "created=%s updated=%s unchanged=%s skipped_empty=%s errors=%s",
        user,
        processed,
        created,
        updated,
        unchanged,
        skipped_empty,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_gen_company_branch_mappings_from_excel(file, user: str):
    """
    Импорт сопоставлений филиалов генерирующих компаний из Excel.
    Обязательные колонки: code_topl, name_topl.
    Необязательная колонка name — для сопоставления с GenCompany.name.
    Все строки с code_topl и name_topl сохраняются в БД, даже без сопоставления с GenCompany.
    """
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_GEN_COMPANY_BRANCH_MAPPINGS] start user=%s filename=%s", user, filename
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "code_topl": ["code_topl", "code", "код", "id_topl", "id"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
            "name": ["name", "наименование", "название", "name_gen_company"],
        },
    )

    required_columns = {"code_topl", "name_topl"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: code_topl, name_topl. Колонка name (для сопоставления с GenCompany) необязательна."
        )

    current_version_id = get_current_db_version_id()
    name_map, duplicates = _build_gen_company_name_map(current_version_id)

    existing = GenCompanyBranchExternalMapping.query.all()
    # Ключ для поиска существующей строки: (external_id, external_name) — филиал идентифицируется по данным из БД Топливо
    by_key: dict[tuple[str, str], GenCompanyBranchExternalMapping] = {
        (
            _clean_text(m.external_id),
            _clean_text(m.external_name),
        ): m
        for m in existing
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("code_topl"))
        external_name = _clean_text(row.get("name_topl"))
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        if not any([external_id, external_name, local_name]):
            errors.append(
                f"Строка {index + 1}: пустые данные, невозможно сохранить."
            )
            continue

        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}'."
            )
            gen_company = None
        else:
            gen_company = name_map.get(normalized_local) if normalized_local else None

        key = (_clean_text(external_id), _clean_text(external_name))
        record = by_key.get(key)

        if record:
            changed = False
            target_uuid = gen_company.ref_uuid if gen_company else None
            if record.gen_company_ref_uuid != target_uuid:
                record.gen_company_ref_uuid = target_uuid
                changed = True
            # Нормализуем сохранение строковых полей (если поменялись)
            if external_id and record.external_id != external_id:
                record.external_id = external_id
                changed = True
            if external_name and record.external_name != external_name:
                record.external_name = external_name
                changed = True
            if local_name and record.local_name != local_name:
                record.local_name = local_name
                changed = True
            if changed:
                updated += 1
        else:
            mapping = GenCompanyBranchExternalMapping(
                gen_company_ref_uuid=gen_company.ref_uuid if gen_company else None,
                external_id=external_id or None,
                external_name=external_name or None,
                local_name=local_name or None,
            )
            db.session.add(mapping)
            db.session.flush()
            created += 1
            by_key[key] = mapping

        if local_name and not gen_company and normalized_local and normalized_local not in duplicates:
            errors.append(f"Строка {index + 1}: компания '{local_name}' не найдена (сопоставление сохранено без связи с GenCompany).")

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений генерирующих компаний (филиалы) завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_GEN_COMPANY_BRANCH_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_department_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_DEPARTMENT_MAPPINGS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "dep_topl": ["dep_topl", "deptopl", "dep", "деп", "деп_топливо"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
        },
    )

    required_columns = {"dep_topl", "name_topl"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: dep_topl, name_topl."
        )

    existing = DepartmentExternalMapping.query.all()
    by_external_id = {
        _clean_text(m.external_id): m for m in existing if m.external_id
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("dep_topl"))
        external_name = _clean_text(row.get("name_topl"))

        if not external_id:
            errors.append(f"Строка {index + 1}: отсутствует dep_topl.")
            continue

        existing_mapping = by_external_id.get(_clean_text(external_id))
        if existing_mapping:
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                updated += 1
            continue

        mapping = DepartmentExternalMapping(
            external_id=external_id,
            external_name=external_name or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_external_id[_clean_text(external_id)] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений департаментов завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_DEPARTMENT_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_business_unit_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info("[IMPORT_BUSINESS_UNIT_MAPPINGS] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "code_topl": ["code_topl", "code", "код", "код_топливо"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
        },
    )

    required_columns = {"code_topl", "name_topl"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: code_topl, name_topl."
        )

    existing = BusinessUnitExternalMapping.query.all()
    by_external_id = {
        _clean_text(m.external_id): m for m in existing if m.external_id
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("code_topl"))
        external_name = _clean_text(row.get("name_topl"))

        if not external_id:
            errors.append(f"Строка {index + 1}: отсутствует code_topl.")
            continue

        existing_mapping = by_external_id.get(_clean_text(external_id))
        if existing_mapping:
            changed = False
            if external_id and existing_mapping.external_id != external_id:
                existing_mapping.external_id = external_id
                changed = True
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                changed = True
            if changed:
                updated += 1
            continue

        mapping = BusinessUnitExternalMapping(
            external_id=external_id,
            external_name=external_name or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_external_id[_clean_text(external_id)] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений бизнес единиц завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_BUSINESS_UNIT_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_economic_region_mappings_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)

    logger.info(
        "[IMPORT_ECONOMIC_REGION_MAPPINGS] start user=%s filename=%s",
        user,
        filename,
    )

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")
    df = _apply_column_aliases(
        df,
        {
            "er_topl": ["er_topl", "er", "код_эр", "код_энергораяона", "код_энергорайона"],
            "name_topl": ["nametopl", "name_t", "name_topl", "название_топливо"],
        },
    )

    required_columns = {"er_topl", "name_topl"}
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Ожидаются: er_topl, name_topl."
        )

    existing = EconomicRegionExternalMapping.query.all()
    by_external_id = {
        _clean_text(m.external_id): m for m in existing if m.external_id
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue

        processed += 1
        external_id = _normalize_external_id(row.get("er_topl"))
        external_name = _clean_text(row.get("name_topl"))

        if not external_id:
            errors.append(f"Строка {index + 1}: отсутствует er_topl.")
            continue

        existing_mapping = by_external_id.get(_clean_text(external_id))
        if existing_mapping:
            changed = False
            if external_id and existing_mapping.external_id != external_id:
                existing_mapping.external_id = external_id
                changed = True
            if external_name and existing_mapping.external_name != external_name:
                existing_mapping.external_name = external_name
                changed = True
            if changed:
                updated += 1
            continue

        mapping = EconomicRegionExternalMapping(
            external_id=external_id,
            external_name=external_name or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_external_id[_clean_text(external_id)] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт сопоставлений экономических районов завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_ECONOMIC_REGION_MAPPINGS] done user=%s processed=%s created=%s "
        "updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_territories_energy_from_excel(file, user: str):
    logger = current_app.logger
    filename = getattr(file, "filename", None)
    logger.info("[IMPORT_TERR_ENERGY] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")

    df = _apply_column_aliases(
        df,
        {
            "regional_district_name": ["regional_district_name", "subject_name", "rd_name", "субъект"],
            "regional_energy_system_name": [
                "regional_energy_system_name",
                "res_name",
                "regional_energy_system",
                "рэс",
            ],
            "energy_unit_name": ["energy_unit_name", "energy_zone_name", "ez_name", "энергорайон"],
            "name_topl": ["name_topl", "name_ext"],
            "ao_topl": ["ao_topl", "ao"],
            "obl_topl": ["obl_topl", "obl"],
            "alph_topl": ["alph_topl", "alph"],
            "dep_topl": ["dep_topl", "dep"],
            "oes_topl": ["oes_topl", "oes"],
            "er_topl": ["er_topl", "er"],
            "terr_belyaev_topl": ["terr_belyaev_topl", "terr_belyaev"],
            "teo90_topl": ["teo90_topl", "teo90"],
            "fo_topl": ["fo_topl", "fo"],
            "abbr_topl": ["abbr_topl", "abbr"],
            "reu_topl": ["reu_topl", "reu"],
            "pter_topl": ["pter_topl", "pter"],
            "keyword_topl": ["keyword_topl", "keyword"],
        },
    )

    required_columns = {
        "name_topl",
        "ao_topl",
        "obl_topl",
        "alph_topl",
        "dep_topl",
        "oes_topl",
        "er_topl",
        "terr_belyaev_topl",
        "teo90_topl",
        "fo_topl",
        "abbr_topl",
        "reu_topl",
        "pter_topl",
        "keyword_topl",
    }
    # Excel column names for validation; model fields for setattr
    integer_only_columns = {
        "obl_topl",
        "alph_topl",
        "dep_topl",
        "oes_topl",
        "er_topl",
        "terr_belyaev_topl",
        "teo90_topl",
        "fo_topl",
        "pter_topl",
    }
    EXCEL_TO_MODEL = {
        "name_topl": "name_ext",
        "ao_topl": "ao",
        "obl_topl": "obl",
        "alph_topl": "alph",
        "dep_topl": "dep",
        "oes_topl": "oes",
        "er_topl": "er",
        "terr_belyaev_topl": "terr_belyaev",
        "teo90_topl": "teo90",
        "fo_topl": "fo",
        "abbr_topl": "abbr",
        "reu_topl": "reu",
        "pter_topl": "pter",
        "keyword_topl": "keyword",
    }
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        found_columns = [str(col) for col in df.columns]
        found_preview = ", ".join(found_columns[:25])
        if len(found_columns) > 25:
            found_preview += ", ..."
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Найдены колонки: {found_preview}"
        )

    current_version_id = get_current_db_version_id()
    rd_map, rd_dups = _build_regional_district_name_map(current_version_id)
    res_map, res_dups = _build_regional_energy_system_name_map(current_version_id)
    ez_map, ez_dups = _build_energy_unit_name_map(current_version_id)

    # Валидные external_id для FK: dep, oes, er, fo — должны существовать в соответствующих таблицах сопоставлений
    valid_dep_ids = {
        _clean_text(m.external_id)
        for m in DepartmentExternalMapping.query.all()
        if m.external_id
    }
    valid_oes_ids = {
        _clean_text(m.external_id)
        for m in UnionEnergySystemExternalMapping.query.all()
        if m.external_id
    }
    valid_er_ids = {
        _clean_text(m.external_id)
        for m in EconomicRegionExternalMapping.query.all()
        if m.external_id
    }
    valid_fo_ids = {
        _clean_text(m.external_id)
        for m in FederalDistrictExternalMapping.query.all()
        if m.external_id
    }

    existing = TerritoriesEnergyExternalMapping.query.all()
    normalized_existing = False
    for record in existing:
        for excel_col, model_field in EXCEL_TO_MODEL.items():
            if excel_col not in integer_only_columns:
                continue
            current_value = getattr(record, model_field, None)
            normalized_value = _normalize_integer_like_text(current_value)
            if normalized_value == "":
                normalized_value = None
            if current_value != normalized_value:
                setattr(record, model_field, normalized_value)
                normalized_existing = True
    if normalized_existing:
        db.session.commit()

    existing_keys = {
        (
            _clean_text(m.regional_district_ref_uuid),
            _clean_text(m.regional_energy_system_ref_uuid),
            _clean_text(m.energy_zone_ref_uuid),
            _excel_text(m.name_ext),
            _excel_text(m.ao),
            _normalize_integer_like_text(m.obl),
            _normalize_integer_like_text(m.alph),
            _normalize_integer_like_text(m.dep),
            _normalize_integer_like_text(m.oes),
            _normalize_integer_like_text(m.er),
            _normalize_integer_like_text(m.terr_belyaev),
            _normalize_integer_like_text(m.teo90),
            _normalize_integer_like_text(m.fo),
            _normalize_integer_like_text(m.abbr),
            _excel_text(m.reu),
            _normalize_integer_like_text(m.pter),
            _normalize_integer_like_text(m.keyword),
        )
        for m in existing
    }
    existing_by_obl: dict[str, TerritoriesEnergyExternalMapping] = {}
    duplicate_obl: set[str] = set()
    for record in existing:
        normalized_obl = _normalize_integer_like_text(record.obl)
        if not normalized_obl:
            continue
        if normalized_obl in existing_by_obl:
            duplicate_obl.add(normalized_obl)
            continue
        existing_by_obl[normalized_obl] = record

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0
    warned_missing: set[tuple[str, str]] = set()  # (field, value) — чтобы не дублировать предупреждения

    for index, row in df.iterrows():
        if row.isnull().all():
            continue
        processed += 1

        rd_name = _clean_text(row.get("regional_district_name"))
        res_name = _clean_text(row.get("regional_energy_system_name"))
        ez_name = _clean_text(row.get("energy_unit_name"))
        integer_values: dict[str, str] = {}
        for field in integer_only_columns:
            normalized_value, is_valid = _normalize_integer_only(row.get(field))
            if not is_valid:
                errors.append(
                    f"Строка {index + 1}: поле {field} должно быть целым. "
                    "Значение очищено."
                )
                normalized_value = ""
            integer_values[field] = normalized_value

        obl_topl_value = integer_values.get("obl_topl", "")

        normalized_rd = _normalize_name(rd_name) if rd_name else ""
        normalized_res = _normalize_name(res_name) if res_name else ""
        normalized_ez = _normalize_name(ez_name) if ez_name else ""

        rd = None
        res = None
        ez = None

        if normalized_rd and normalized_rd in rd_dups:
            errors.append(
                f"Строка {index + 1}: неоднозначный субъект РФ '{rd_name}'."
            )
        elif normalized_rd:
            rd = rd_map.get(normalized_rd)

        if normalized_res and normalized_res in res_dups:
            errors.append(
                f"Строка {index + 1}: неоднозначная РЭС '{res_name}'."
            )
        elif normalized_res:
            res = res_map.get(normalized_res)

        if normalized_ez and normalized_ez in ez_dups:
            errors.append(
                f"Строка {index + 1}: неоднозначный энергорайон '{ez_name}'."
            )
        elif normalized_ez:
            ez = ez_map.get(normalized_ez)

        existing_record = None
        if obl_topl_value:
            if obl_topl_value in duplicate_obl:
                errors.append(
                    "Строка "
                    f"{index + 1}: obl_topl '{obl_topl_value}' "
                    "встречается более одного раза в базе. "
                    "Обновление пропущено."
                )
                continue
            existing_record = existing_by_obl.get(obl_topl_value)

        dep_val = integer_values.get("dep_topl") or None
        oes_val = integer_values.get("oes_topl") or None
        er_val = integer_values.get("er_topl") or None
        fo_val = integer_values.get("fo_topl") or None

        # dep, oes, er, fo — FK на таблицы сопоставлений; если external_id отсутствует — ставим None
        if dep_val and _clean_text(dep_val) not in valid_dep_ids:
            if ("dep", _clean_text(dep_val)) not in warned_missing:
                warned_missing.add(("dep", _clean_text(dep_val)))
                errors.append(
                    f"dep_topl={dep_val} отсутствует в справочнике департаментов. "
                    "Сначала выполните импорт сопоставлений департаментов."
                )
            dep_val = None
        if oes_val and _clean_text(oes_val) not in valid_oes_ids:
            if ("oes", _clean_text(oes_val)) not in warned_missing:
                warned_missing.add(("oes", _clean_text(oes_val)))
                errors.append(
                    f"oes_topl={oes_val} отсутствует в справочнике ОЭС. "
                    "Сначала выполните импорт сопоставлений ОЭС."
                )
            oes_val = None
        if er_val and _clean_text(er_val) not in valid_er_ids:
            if ("er", _clean_text(er_val)) not in warned_missing:
                warned_missing.add(("er", _clean_text(er_val)))
                errors.append(
                    f"er_topl={er_val} отсутствует в справочнике экономических районов. "
                    "Сначала выполните импорт сопоставлений экономических районов."
                )
            er_val = None
        if fo_val and _clean_text(fo_val) not in valid_fo_ids:
            if ("fo", _clean_text(fo_val)) not in warned_missing:
                warned_missing.add(("fo", _clean_text(fo_val)))
                errors.append(
                    f"fo_topl={fo_val} отсутствует в справочнике ФО. "
                    "Сначала выполните импорт сопоставлений федеральных округов."
                )
            fo_val = None

        record_data = {
            "regional_district_ref_uuid": rd.ref_uuid if rd else None,
            "regional_energy_system_ref_uuid": res.ref_uuid if res else None,
            "energy_zone_ref_uuid": ez.ref_uuid if ez else None,
            "external_id": obl_topl_value or None,
            "external_name": _excel_text(row.get("name_topl")) or None,
            "name_ext": _excel_text(row.get("name_topl")) or None,
            "ao": _excel_text(row.get("ao_topl")) or None,
            "obl": obl_topl_value or None,
            "alph": integer_values.get("alph_topl") or None,
            "dep": dep_val,
            "oes": oes_val,
            "er": er_val,
            "terr_belyaev": integer_values.get("terr_belyaev_topl") or None,
            "teo90": integer_values.get("teo90_topl") or None,
            "fo": fo_val,
            "abbr": _normalize_integer_like_text(row.get("abbr_topl")) or None,
            "reu": _excel_text(row.get("reu_topl")) or None,
            "pter": integer_values.get("pter_topl") or None,
            "keyword": _normalize_integer_like_text(row.get("keyword_topl")) or None,
        }
        record = TerritoriesEnergyExternalMapping(**record_data)

        key = (
            _clean_text(record.regional_district_ref_uuid),
            _clean_text(record.regional_energy_system_ref_uuid),
            _clean_text(record.energy_zone_ref_uuid),
            _excel_text(record.name_ext),
            _excel_text(record.ao),
            _clean_text(record.obl),
            _clean_text(record.alph),
            _clean_text(record.dep),
            _clean_text(record.oes),
            _clean_text(record.er),
            _clean_text(record.terr_belyaev),
            _clean_text(record.teo90),
            _clean_text(record.fo),
            _clean_text(record.abbr),
            _clean_text(record.reu),
            _clean_text(record.pter),
            _clean_text(record.keyword),
        )

        if existing_record:
            existing_key = (
                _clean_text(existing_record.regional_district_ref_uuid),
                _clean_text(existing_record.regional_energy_system_ref_uuid),
                _clean_text(existing_record.energy_zone_ref_uuid),
                _excel_text(existing_record.name_ext),
                _excel_text(existing_record.ao),
                _clean_text(existing_record.obl),
                _clean_text(existing_record.alph),
                _clean_text(existing_record.dep),
                _clean_text(existing_record.oes),
                _clean_text(existing_record.er),
                _clean_text(existing_record.terr_belyaev),
                _clean_text(existing_record.teo90),
                _clean_text(existing_record.fo),
                _clean_text(existing_record.abbr),
                _clean_text(existing_record.reu),
                _clean_text(existing_record.pter),
                _clean_text(existing_record.keyword),
            )
            if key in existing_keys and key != existing_key:
                errors.append(
                    "Строка "
                    f"{index + 1}: запись с такими значениями уже существует. "
                    "Обновление пропущено."
                )
                continue
            if existing_key in existing_keys:
                existing_keys.remove(existing_key)
            existing_keys.add(key)
            for field, value in record_data.items():
                setattr(existing_record, field, value)
            updated += 1
            continue

        if key in existing_keys:
            continue

        existing_keys.add(key)
        db.session.add(record)
        created += 1

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    if processed > 0 and created == 0 and not errors:
        errors.append(
            "Не создано ни одной записи: строки совпадают с существующими "
            "или не содержат данных для сохранения."
        )

    message = (
        "Импорт сопоставлений территорий/энергосистем завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_TERR_ENERGY] done user=%s processed=%s created=%s "
        "updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }


def import_cities_from_excel(file, user: str):
    """
    Импорт справочника "Города" из Excel.
    Ожидаемые колонки: code_topl, name_topl, naselenie, gilfond, obesp_cts, dprom_ao, dgkh_ao, obl.

    Форматы:
    - code_topl, obl, dprom_ao, dgkh_ao: целое число
    - naselenie, gilfond: числовой (+/- допускается)
    - name_topl, obesp_cts: текст
    """
    logger = current_app.logger
    filename = getattr(file, "filename", None)
    logger.info("[IMPORT_CITIES] start user=%s filename=%s", user, filename)

    xls = pd.ExcelFile(file)
    sheet_name = xls.sheet_names[0]
    df = xls.parse(sheet_name, header=0)
    df = df.dropna(how="all")

    df = _apply_column_aliases(
        df,
        {
            "code_topl": ["code", "код", "id_topl", "id"],
            "name_topl": ["name_t", "nametopl", "название_топливо", "наименование"],
            "naselenie": ["население", "population"],
            "gilfond": ["жилфонд", "housing"],
            "obesp_cts": ["obespcts", "обесп_цтс", "обеспеченность_цтс"],
            "dprom_ao": ["dpromao", "дпром_ао"],
            "dgkh_ao": ["dgkhao", "дгкх_ао"],
            "obl": ["обл", "region", "obl_topl"],
        },
    )

    required_columns = {
        "code_topl",
        "name_topl",
        "naselenie",
        "gilfond",
        "obesp_cts",
        "dprom_ao",
        "dgkh_ao",
        "obl",
    }
    missing = sorted([c for c in required_columns if c not in df.columns])
    if missing:
        found_columns = [str(col) for col in df.columns]
        found_preview = ", ".join(found_columns[:25])
        if len(found_columns) > 25:
            found_preview += ", ..."
        raise ValueError(
            "Неверный шаблон файла: отсутствуют обязательные колонки "
            f"{missing}. Найдены колонки: {found_preview}"
        )

    existing = CitiesExternalMapping.query.all()
    by_code: dict[int, CitiesExternalMapping] = {
        int(m.code): m for m in existing if m.code is not None
    }

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

    for index, row in df.iterrows():
        if row.isnull().all():
            continue
        processed += 1

        code_raw = row.get("code_topl")
        code_text, code_ok = _normalize_integer_only(code_raw)
        if not code_ok or not code_text:
            errors.append(f"Строка {index + 1}: code_topl должен быть целым числом.")
            continue
        code_topl = int(code_text)

        obl_raw = row.get("obl")
        obl_text, obl_ok = _normalize_integer_only(obl_raw)
        if not obl_ok:
            errors.append(f"Строка {index + 1}: obl должен быть целым числом. Значение очищено.")
            obl_text = ""
        obl_value = int(obl_text) if obl_text else None

        nas_value, nas_ok = _normalize_decimal(row.get("naselenie"))
        if not nas_ok:
            errors.append(
                f"Строка {index + 1}: naselenie должно быть числом (+/- допускается). Значение очищено."
            )
            nas_value = None

        gil_value, gil_ok = _normalize_decimal(row.get("gilfond"))
        if not gil_ok:
            errors.append(
                f"Строка {index + 1}: gilfond должно быть числом (+/- допускается). Значение очищено."
            )
            gil_value = None

        name_topl = _clean_text(row.get("name_topl")) or None
        obesp_cts = _clean_text(row.get("obesp_cts")) or None

        dprom_raw = row.get("dprom_ao")
        dprom_text, dprom_ok = _normalize_integer_only(dprom_raw)
        if not dprom_ok:
            errors.append(
                f"Строка {index + 1}: dprom_ao должен быть целым числом. Значение очищено."
            )
            dprom_text = ""
        dprom_ao = int(dprom_text) if dprom_text else None

        dgkh_raw = row.get("dgkh_ao")
        dgkh_text, dgkh_ok = _normalize_integer_only(dgkh_raw)
        if not dgkh_ok:
            errors.append(
                f"Строка {index + 1}: dgkh_ao должен быть целым числом. Значение очищено."
            )
            dgkh_text = ""
        dgkh_ao = int(dgkh_text) if dgkh_text else None

        record = by_code.get(code_topl)
        if record:
            changed = False
            if record.name != name_topl:
                record.name = name_topl
                changed = True
            if record.naselenie != nas_value:
                record.naselenie = nas_value
                changed = True
            if record.gilfond != gil_value:
                record.gilfond = gil_value
                changed = True
            if record.obesp_cts != obesp_cts:
                record.obesp_cts = obesp_cts
                changed = True
            if record.dprom_ao != dprom_ao:
                record.dprom_ao = dprom_ao
                changed = True
            if record.dgkh_ao != dgkh_ao:
                record.dgkh_ao = dgkh_ao
                changed = True
            if record.obl != obl_value:
                record.obl = obl_value
                changed = True
            if changed:
                updated += 1
            continue

        mapping = CitiesExternalMapping(
            code=code_topl,
            name=name_topl,
            naselenie=nas_value,
            gilfond=gil_value,
            obesp_cts=obesp_cts,
            dprom_ao=dprom_ao,
            dgkh_ao=dgkh_ao,
            obl=obl_value,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_code[code_topl] = mapping

    if created or updated:
        db.session.commit()

    if processed == 0:
        raise ValueError("Файл не содержит данных для загрузки.")

    message = (
        "Импорт справочника 'Города' завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )
    logger.info(
        "[IMPORT_CITIES] done user=%s processed=%s created=%s updated=%s errors=%s",
        user,
        processed,
        created,
        updated,
        len(errors),
    )

    return {
        "processed_rows": processed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "errors_count": len(errors),
        "message": message,
    }
