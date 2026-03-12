# -*- coding: utf-8 -*-
"""
Сервисы для страницы fuel/refdata/equipment_group: фильтры, выборки для выпадающих списков, сохранение.
"""
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)


def get_filter_choices_for_equipment_group():
    """Возвращает словарь {col: [(value, label), ...]} для выпадающих фильтров."""
    choices = {}

    # Поля из EquipmentGroupExternalMapping (code, type_, n1, n2, p1, p2 — Integer; остальные — String)
    int_cols = {"code", "type_", "n1", "n2", "p1", "p2"}
    mapping_cols = [
        "code", "name_topl", "type_", "tm", "n1", "n2", "p1", "p2", "gruppa_oborud",
    ]
    for col in mapping_cols:
        col_attr = getattr(EquipmentGroupExternalMapping, col)
        q = EquipmentGroupExternalMapping.query.with_entities(col_attr).filter(col_attr.isnot(None))
        if col not in int_cols:
            q = q.filter(col_attr != "")
        rows = q.distinct().order_by(col_attr).all()
        vals = []
        for r in rows:
            v = r[0]
            if v is not None and str(v).strip() != "":
                vals.append((str(v).strip(), str(v).strip()))
        choices[col] = [("", "Все")] + vals

    # equipment_group_ref_uuid — типы групп оборудования из Генерации
    current_version_id = get_current_db_version_id()
    eg_rows = (
        EquipmentGroupType.query.with_entities(
            EquipmentGroupType.ref_uuid,
            EquipmentGroupType.name,
        )
        .order_by(EquipmentGroupType.name)
    )
    eg_rows = filter_by_explicit_db_version(eg_rows, EquipmentGroupType, current_version_id)
    eg_list = eg_rows.all()
    choices["equipment_group_ref_uuid"] = [("", "Все")] + [
        (str(r[0] or "").strip(), (r[1] or r[0] or "")) for r in eg_list if (r[0] or "").strip()
    ]

    return choices


def _normalize_uuid_for_filter(val):
    return str(val or "").strip().lower().replace("{", "").replace("}", "")


def apply_equipment_group_row_filters(rows, filter_params):
    """
    Фильтрует список rows (SimpleNamespace(eg=..., mapping=...)) по filter_params.
    Возвращает отфильтрованный список.
    """
    if not filter_params:
        return rows

    result = []
    for row in rows:
        mapping = row.mapping
        eg = row.eg

        match = True
        for col, filter_val in filter_params.items():
            if filter_val is None or (isinstance(filter_val, str) and not filter_val.strip()):
                continue
            filter_val = str(filter_val).strip()

            if col == "equipment_group_ref_uuid":
                ref_uuid = eg.ref_uuid if eg else (mapping.equipment_group_ref_uuid if mapping else None)
                val_norm = _normalize_uuid_for_filter(ref_uuid)
                filter_norm = _normalize_uuid_for_filter(filter_val)
                if val_norm != filter_norm:
                    match = False
                    break
            elif col in ("code", "name_topl", "type_", "tm", "n1", "n2", "p1", "p2", "gruppa_oborud"):
                val = getattr(mapping, col, None) if mapping else None
                val_str = str(val) if val is not None else ""
                if val_str.strip() != filter_val:
                    match = False
                    break

        if match:
            result.append(row)

    return result


def update_equipment_group_mappings_from_form(request_form, user):
    """
    Обновляет записи EquipmentGroupExternalMapping из request.form.
    Ожидаются ключи вида row_{mapping_id}_{field}, например row_123_code.
    Для перепривязки: row_{mapping_id}_equipment_group_ref_uuid.
    Возвращает (success: bool, message: str).
    """
    from app.extensions import db
    from app.logs.services.logging_service import log_to_db

    editable = {
        "code", "name_topl", "type_", "tm", "n1", "n2", "p1", "p2", "gruppa_oborud",
        "equipment_group_ref_uuid",
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
    for mapping_id, row_data in rows_data.items():
        mapping = EquipmentGroupExternalMapping.query.get(mapping_id)
        if not mapping:
            continue
        for field, new_val in row_data.items():
            if field == "equipment_group_ref_uuid":
                new_val = (new_val or "").strip() or None
            elif field in ("code", "n1", "n2", "p1", "p2", "type_"):
                s = (new_val or "").strip()
                if s == "":
                    new_val = None
                else:
                    try:
                        new_val = int(s)
                    except ValueError:
                        continue  # skip invalid integer
            else:
                new_val = (new_val or "").strip() or None

            if hasattr(mapping, field):
                old_val = getattr(mapping, field)
                if old_val != new_val:
                    setattr(mapping, field, new_val)
                    updated += 1

    try:
        db.session.commit()
        log_to_db(
            user,
            "Обновлены сопоставления типов групп оборудования (Топливо)",
            f"Изменено полей: {updated}",
            entity_type="equipment_group",
        )
        return True, f"Сохранено: изменено полей {updated}"
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения сопоставлений типов групп оборудования",
            str(e),
            entity_type="equipment_group",
        )
        return False, str(e)
