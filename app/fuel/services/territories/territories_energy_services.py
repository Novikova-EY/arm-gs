# -*- coding: utf-8 -*-
"""
Сервисы для страницы territories_energy: фильтры, выборки для выпадающих списков, сохранение.
"""
from sqlalchemy import func, distinct

from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)
from config import SCHEMA_FUE_EM


# Integer-поля (без FK после миграции)
INTEGER_COLS = ["obl", "alph", "dep", "oes", "er", "terr_belyaev", "teo90", "fo"]


def _format_choice_value(val):
    """Форматирует значение для выбора (Integer или str)."""
    if val is None:
        return "", ""
    if isinstance(val, int):
        return str(val), str(val)
    s = str(val).strip()
    return s, s


def get_filter_choices_for_territories_energy():
    """Возвращает словарь {col: [(value, label), ...]} для выпадающих фильтров."""
    choices = {}

    # Текстовые поля — distinct из таблицы
    text_cols = [
        "name_ext",
        "ao",
        "obl",
        "alph",
        "terr_belyaev",
        "teo90",
        "abbr",
        "reu",
        "pter",
        "keyword",
    ]
    for col in text_cols:
        col_attr = getattr(TerritoriesEnergyExternalMapping, col)
        if col in INTEGER_COLS:
            rows = (
                TerritoriesEnergyExternalMapping.query.with_entities(col_attr)
                .filter(col_attr.isnot(None))
                .distinct()
                .order_by(col_attr)
                .all()
            )
        else:
            rows = (
                TerritoriesEnergyExternalMapping.query.with_entities(col_attr)
                .filter(col_attr.isnot(None), col_attr != "")
                .distinct()
                .order_by(col_attr)
                .all()
            )
        choices[col] = [("", "Все")] + [
            _format_choice_value(r[0]) for r in rows if r[0] is not None
        ]

    # dep, oes, er, fo — теперь Integer, берем distinct из самой таблицы
    for col in ["dep", "oes", "er", "fo"]:
        col_attr = getattr(TerritoriesEnergyExternalMapping, col)
        rows = (
            TerritoriesEnergyExternalMapping.query.with_entities(col_attr)
            .filter(col_attr.isnot(None))
            .distinct()
            .order_by(col_attr)
            .all()
        )
        choices[col] = [("", "Все")] + [
            _format_choice_value(r[0]) for r in rows if r[0] is not None
        ]

    # Поля из Генерации — по ref_uuid
    current_version_id = get_current_db_version_id()
    rd_rows = (
        RegionalDistrict.query.with_entities(
            RegionalDistrict.ref_uuid,
            RegionalDistrict.name,
        )
        .order_by(RegionalDistrict.name)
    )
    rd_rows = filter_by_explicit_db_version(rd_rows, RegionalDistrict, current_version_id)
    rd_list = rd_rows.all()
    choices["regional_district_ref_uuid"] = [("", "Все")] + [
        (str(r[0] or "").strip(), (r[1] or r[0] or "")) for r in rd_list if (r[0] or "").strip()
    ]

    res_rows = (
        RegionalEnergySystem.query.with_entities(
            RegionalEnergySystem.ref_uuid,
            RegionalEnergySystem.name,
        )
        .order_by(RegionalEnergySystem.name)
    )
    res_rows = filter_by_explicit_db_version(res_rows, RegionalEnergySystem, current_version_id)
    res_list = res_rows.all()
    choices["regional_energy_system_ref_uuid"] = [("", "Все")] + [
        (str(r[0] or "").strip(), (r[1] or r[0] or "")) for r in res_list if (r[0] or "").strip()
    ]

    eu_rows = (
        EnergyUnit.query.with_entities(
            EnergyUnit.ref_uuid,
            EnergyUnit.name,
        )
        .order_by(EnergyUnit.name)
    )
    eu_rows = filter_by_explicit_db_version(eu_rows, EnergyUnit, current_version_id)
    eu_list = eu_rows.all()
    choices["energy_zone_ref_uuid"] = [("", "Все")] + [
        (str(r[0] or "").strip(), (r[1] or r[0] or "")) for r in eu_list if (r[0] or "").strip()
    ]

    return choices


def _normalize_uuid_for_filter(val):
    return str(val or "").strip().lower().replace("{", "").replace("}", "")


def apply_territories_energy_filters(query, filter_params):
    """Применяет фильтры к запросу TerritoriesEnergyExternalMapping."""
    for col, val in filter_params.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        val = str(val).strip()
        if col in INTEGER_COLS:
            col_attr = getattr(TerritoriesEnergyExternalMapping, col)
            try:
                query = query.filter(col_attr == int(val))
            except ValueError:
                continue
        elif col == "regional_district_ref_uuid":
            val_norm = _normalize_uuid_for_filter(val)
            rd_col = TerritoriesEnergyExternalMapping.regional_district_ref_uuid
            query = query.filter(
                func.lower(func.trim(func.replace(func.replace(rd_col, "{", ""), "}", "")))
                == val_norm
            )
        elif col == "regional_energy_system_ref_uuid":
            val_norm = _normalize_uuid_for_filter(val)
            res_col = TerritoriesEnergyExternalMapping.regional_energy_system_ref_uuid
            query = query.filter(
                func.lower(func.trim(func.replace(func.replace(res_col, "{", ""), "}", "")))
                == val_norm
            )
        elif col == "energy_zone_ref_uuid":
            val_norm = _normalize_uuid_for_filter(val)
            ez_col = TerritoriesEnergyExternalMapping.energy_zone_ref_uuid
            query = query.filter(
                func.lower(func.trim(func.replace(func.replace(ez_col, "{", ""), "}", "")))
                == val_norm
            )
        elif col in (
            "name_ext",
            "ao",
            "abbr",
            "reu",
            "pter",
            "keyword",
        ):
            col_attr = getattr(TerritoriesEnergyExternalMapping, col)
            query = query.filter(col_attr == val)
    return query


def update_territories_energy_from_form(request_form, user):
    """
    Обновляет записи TerritoriesEnergyExternalMapping из request.form.
    Ожидаются ключи вида row_{id}_{field}, например row_123_name_ext.
    Возвращает (success: bool, message: str).
    """
    from app.extensions import db
    from datetime import datetime

    editable = {
        "name_ext", "ao", "obl", "alph",
        "dep", "oes", "er", "terr_belyaev", "teo90", "fo",
        "abbr", "reu", "pter", "keyword",
        "regional_district_ref_uuid", "regional_energy_system_ref_uuid", "energy_zone_ref_uuid",
    }
    rows_data = {}
    for key in request_form:
        if not key.startswith("row_") or "_" not in key[4:]:
            continue
        parts = key.split("_", 2)
        if len(parts) != 3:
            continue
        try:
            row_id = int(parts[1])
        except ValueError:
            continue
        field = parts[2]
        if field not in editable:
            continue
        if row_id not in rows_data:
            rows_data[row_id] = {}
        rows_data[row_id][field] = request_form.get(key, "")

    updated = 0
    for row_id, row_data in rows_data.items():
        row = TerritoriesEnergyExternalMapping.query.get(row_id)
        if not row:
            continue
        for field, new_val in row_data.items():
            raw = (new_val or "").strip() or None
            if field in INTEGER_COLS and raw is not None:
                try:
                    raw = int(raw)
                except ValueError:
                    raw = None
            if hasattr(row, field):
                setattr(row, field, raw)
                updated += 1
        if hasattr(row, "modified_by"):
            row.modified_by = user
        if hasattr(row, "modified_at"):
            row.modified_at = datetime.utcnow()

    try:
        db.session.commit()
        return True, f"Сохранено изменений: {updated}"
    except Exception as e:
        db.session.rollback()
        return False, str(e)
