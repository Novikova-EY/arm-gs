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
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.organizations.department_model import Department
from app.refdata.models.organizations.business_unit_model import BusinessUnit
from app.refdata.models.gen_companies.gen_company_model import GenCompany


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
    return _build_name_map_for_rows(rows, ["name", "name_full"])


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
    by_unmatched_key: dict[tuple[str, str, str, str], UnionEnergySystemExternalMapping] = {}
    for m in existing:
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

        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}'."
            )
            continue

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
            else:
                mapping = UnionEnergySystemExternalMapping(
                    union_energy_system_ref_uuid=None,
                    external_id=external_id,
                    external_name=external_name or None,
                    external_nameoes=external_nameoes or None,
                    external_abbr=external_abbr or None,
                )
                db.session.add(mapping)
                db.session.flush()
                created += 1
                by_unmatched_key[key] = mapping

            if not local_name:
                errors.append(f"Строка {index + 1}: отсутствует name.")
            else:
                errors.append(
                    f"Строка {index + 1}: ОЭС с названием '{local_name}' не найдена."
                )
            continue

        existing_mapping = by_uuid.get(ues.ref_uuid)
        if existing_mapping:
            changed = False
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
            continue

        mapping = UnionEnergySystemExternalMapping(
            union_energy_system_ref_uuid=ues.ref_uuid,
            external_id=external_id,
            external_name=external_name or None,
            external_nameoes=external_nameoes or None,
            external_abbr=external_abbr or None,
        )
        db.session.add(mapping)
        db.session.flush()
        created += 1
        by_uuid[ues.ref_uuid] = mapping

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
                mapping = FederalDistrictExternalMapping(
                    federal_district_ref_uuid=None,
                    external_id=external_id,
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

        mapping = FederalDistrictExternalMapping(
            federal_district_ref_uuid=fd.ref_uuid,
            external_id=external_id,
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
    existing = GenCompanyExternalMapping.query.all()
    by_uuid: dict[str, GenCompanyExternalMapping] = {}
    by_unmatched_key: dict[tuple[str, str, str], GenCompanyExternalMapping] = {}
    for m in existing:
        if m.gen_company_ref_uuid and m.gen_company_ref_uuid not in by_uuid:
            by_uuid[m.gen_company_ref_uuid] = m
            continue
        if not m.gen_company_ref_uuid:
            key = (
                _clean_text(m.external_id),
                _clean_text(m.external_name),
                _clean_text(m.external_name1),
            )
            by_unmatched_key.setdefault(key, m)
    by_unmatched_key = {
        (
            _clean_text(m.external_id),
            _clean_text(m.external_name),
            _clean_text(m.external_name1),
        ): m
        for m in existing
        if not m.gen_company_ref_uuid
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
        external_name1 = _clean_text(row.get("name1_topl"))
        local_name = _clean_text(row.get("name"))
        normalized_local = _normalize_name(local_name) if local_name else ""

        if normalized_local and normalized_local in duplicates:
            errors.append(
                f"Строка {index + 1}: неоднозначное соответствие для '{local_name}'."
            )
            continue

        gen_company = name_map.get(normalized_local) if normalized_local else None
        if not gen_company:
            key = (
                _clean_text(external_id),
                _clean_text(external_name),
                _clean_text(external_name1),
            )
            if not any(key):
                errors.append(
                    f"Строка {index + 1}: пустые данные, невозможно сохранить."
                )
                continue

            existing_unmatched = by_unmatched_key.get(key)
            if existing_unmatched:
                changed = False
                if external_id and existing_unmatched.external_id != external_id:
                    existing_unmatched.external_id = external_id
                    changed = True
                if external_name and existing_unmatched.external_name != external_name:
                    existing_unmatched.external_name = external_name
                    changed = True
                if (
                    external_name1
                    and existing_unmatched.external_name1 != external_name1
                ):
                    existing_unmatched.external_name1 = external_name1
                    changed = True
                if changed:
                    updated += 1
            else:
                mapping = GenCompanyExternalMapping(
                    gen_company_ref_uuid=None,
                    external_id=external_id,
                    external_name=external_name or None,
                    external_name1=external_name1 or None,
                )
                db.session.add(mapping)
                db.session.flush()
                created += 1
                by_unmatched_key[key] = mapping

            if not local_name:
                errors.append(f"Строка {index + 1}: отсутствует name.")
            else:
                errors.append(
                    f"Строка {index + 1}: компания '{local_name}' не найдена."
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

    message = (
        "Импорт сопоставлений генерирующих компаний завершен: "
        f"обработано {processed}, создано {created}, обновлено {updated}, "
        f"ошибок {len(errors)}."
    )

    logger.info(
        "[IMPORT_GEN_COMPANY_MAPPINGS] done user=%s processed=%s created=%s updated=%s errors=%s",
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
            "name_topl": ["name_topl"],
            "ao_topl": ["ao_topl"],
            "obl_topl": ["obl_topl"],
            "alph_topl": ["alph_topl"],
            "dep_topl": ["dep_topl"],
            "oes_topl": ["oes_topl"],
            "er_topl": ["er_topl"],
            "terr_belyaev_topl": ["terr_belyaev_topl"],
            "teo90_topl": ["teo90_topl"],
            "fo_topl": ["fo_topl"],
            "abbr_topl": ["abbr_topl"],
            "reu_topl": ["reu_topl"],
            "pter_topl": ["pter_topl"],
            "keyword_topl": ["keyword_topl"],
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

    existing = TerritoriesEnergyExternalMapping.query.all()
    normalized_existing = False
    for record in existing:
        for field in integer_only_columns:
            current_value = getattr(record, field, None)
            normalized_value = _normalize_integer_like_text(current_value)
            if normalized_value == "":
                normalized_value = None
            if current_value != normalized_value:
                setattr(record, field, normalized_value)
                normalized_existing = True
    if normalized_existing:
        db.session.commit()

    existing_keys = {
        (
            _clean_text(m.regional_district_ref_uuid),
            _clean_text(m.regional_energy_system_ref_uuid),
            _clean_text(m.energy_zone_ref_uuid),
            _excel_text(m.name_topl),
            _excel_text(m.ao_topl),
            _normalize_integer_like_text(m.obl_topl),
            _normalize_integer_like_text(m.alph_topl),
            _normalize_integer_like_text(m.dep_topl),
            _normalize_integer_like_text(m.oes_topl),
            _normalize_integer_like_text(m.er_topl),
            _normalize_integer_like_text(m.terr_belyaev_topl),
            _normalize_integer_like_text(m.teo90_topl),
            _normalize_integer_like_text(m.fo_topl),
            _normalize_integer_like_text(m.abbr_topl),
            _excel_text(m.reu_topl),
            _normalize_integer_like_text(m.pter_topl),
            _normalize_integer_like_text(m.keyword_topl),
        )
        for m in existing
    }
    existing_by_obl_topl: dict[str, TerritoriesEnergyExternalMapping] = {}
    duplicate_obl_topl: set[str] = set()
    for record in existing:
        normalized_obl_topl = _normalize_integer_like_text(record.obl_topl)
        if not normalized_obl_topl:
            continue
        if normalized_obl_topl in existing_by_obl_topl:
            duplicate_obl_topl.add(normalized_obl_topl)
            continue
        existing_by_obl_topl[normalized_obl_topl] = record

    created = 0
    updated = 0
    errors: list[str] = []
    processed = 0

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
            if obl_topl_value in duplicate_obl_topl:
                errors.append(
                    "Строка "
                    f"{index + 1}: obl_topl '{obl_topl_value}' "
                    "встречается более одного раза в базе. "
                    "Обновление пропущено."
                )
                continue
            existing_record = existing_by_obl_topl.get(obl_topl_value)

        record_data = {
            "regional_district_ref_uuid": rd.ref_uuid if rd else None,
            "regional_energy_system_ref_uuid": res.ref_uuid if res else None,
            "energy_zone_ref_uuid": ez.ref_uuid if ez else None,
            "name_topl": _excel_text(row.get("name_topl")) or None,
            "ao_topl": _excel_text(row.get("ao_topl")) or None,
            "obl_topl": obl_topl_value or None,
            "alph_topl": integer_values.get("alph_topl") or None,
            "dep_topl": integer_values.get("dep_topl") or None,
            "oes_topl": integer_values.get("oes_topl") or None,
            "er_topl": integer_values.get("er_topl") or None,
            "terr_belyaev_topl": integer_values.get("terr_belyaev_topl") or None,
            "teo90_topl": integer_values.get("teo90_topl") or None,
            "fo_topl": integer_values.get("fo_topl") or None,
            "abbr_topl": _normalize_integer_like_text(row.get("abbr_topl")) or None,
            "reu_topl": _excel_text(row.get("reu_topl")) or None,
            "pter_topl": integer_values.get("pter_topl") or None,
            "keyword_topl": _normalize_integer_like_text(row.get("keyword_topl"))
            or None,
        }
        record = TerritoriesEnergyExternalMapping(**record_data)

        key = (
            _clean_text(record.regional_district_ref_uuid),
            _clean_text(record.regional_energy_system_ref_uuid),
            _clean_text(record.energy_zone_ref_uuid),
            _excel_text(record.name_topl),
            _excel_text(record.ao_topl),
            _clean_text(record.obl_topl),
            _clean_text(record.alph_topl),
            _clean_text(record.dep_topl),
            _clean_text(record.oes_topl),
            _clean_text(record.er_topl),
            _clean_text(record.terr_belyaev_topl),
            _clean_text(record.teo90_topl),
            _clean_text(record.fo_topl),
            _clean_text(record.abbr_topl),
            _clean_text(record.reu_topl),
            _clean_text(record.pter_topl),
            _clean_text(record.keyword_topl),
        )

        if existing_record:
            existing_key = (
                _clean_text(existing_record.regional_district_ref_uuid),
                _clean_text(existing_record.regional_energy_system_ref_uuid),
                _clean_text(existing_record.energy_zone_ref_uuid),
                _excel_text(existing_record.name_topl),
                _excel_text(existing_record.ao_topl),
                _clean_text(existing_record.obl_topl),
                _clean_text(existing_record.alph_topl),
                _clean_text(existing_record.dep_topl),
                _clean_text(existing_record.oes_topl),
                _clean_text(existing_record.er_topl),
                _clean_text(existing_record.terr_belyaev_topl),
                _clean_text(existing_record.teo90_topl),
                _clean_text(existing_record.fo_topl),
                _clean_text(existing_record.abbr_topl),
                _clean_text(existing_record.reu_topl),
                _clean_text(existing_record.pter_topl),
                _clean_text(existing_record.keyword_topl),
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
