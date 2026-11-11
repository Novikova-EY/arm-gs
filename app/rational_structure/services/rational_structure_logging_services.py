from copy import deepcopy
from decimal import Decimal
import json

from app.logs.services import logging_service
from app.rational_structure.equipment_types import EQUIPMENT_TYPES
from app.rational_structure.services.technical_characteristic_columns import BASE_LABELS
from app.rational_structure.services.technical_characteristic_page_services import MATCH_STATUS_LABELS

ENTITY_TYPE = "rational_structure"
CODE_ENTITY_TYPE = "rational_structure_code"
_SYSTEM_FIELDS = {"id", "database_version_id", "created_at", "updated_at", "created_by", "modified_by"}
_FIELD_LABELS = {
    **BASE_LABELS,
    "equipment_type": "Вид оборудования",
    "machine_id": "ID агрегата",
    "pgu_machine_id": "ID составляющей ПГУ",
    "match_status": "Статус сопоставления",
    "match_details": "Подробности сопоставления",
    "extra_values": "Дополнительные характеристики",
}


def snapshot(row) -> dict:
    return {column.name: deepcopy(getattr(row, column.name))
            for column in row.__table__.columns if column.name not in _SYSTEM_FIELDS}


def _display(field, value) -> str:
    if value is None or value == "":
        return "не указано"
    if field == "match_status":
        return MATCH_STATUS_LABELS.get(value, value)
    if field == "equipment_type":
        return EQUIPMENT_TYPES.get(value, value)
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def log_record_change(row, before: dict | None, username: str, *, code: bool = False) -> None:
    after = snapshot(row)
    changes = []
    for field, value in after.items():
        old = before.get(field) if before is not None else None
        if old == value:
            continue
        if field == "extra_values":
            for label in sorted(set(old or {}) | set(value or {})):
                previous, current = (old or {}).get(label), (value or {}).get(label)
                if previous != current:
                    changes.append(f"{label}: {_display(label, previous)} → {_display(label, current)}")
        else:
            changes.append(f"{_FIELD_LABELS[field]}: {_display(field, old)} → {_display(field, value)}")
    if not changes:
        return
    title = "Связь кода Техинспекции" if code else "Технические характеристики оборудования"
    action = f"{'Добавлена' if before is None else 'Изменена'} связь кода Техинспекции" if code else (
        f"{'Добавлены' if before is None else 'Изменены'} технические характеристики оборудования"
    )
    details = [title, f"ID записи={row.id}", f"версия БД={row.database_version_id}",
               f"код Техинспекции={row.equipment_code}"]
    if not code:
        details += [f"вид={EQUIPMENT_TYPES[row.equipment_type]}", f"год={row.report_year}",
                    f"станция={row.station_name or 'не указано'}", f"номер={row.station_number or 'не указано'}"]
    details += [f"machine_id={row.machine_id}", f"pgu_machine_id={row.pgu_machine_id}", *changes]
    logging_service.log_to_db(username, action, "; ".join(details),
                              entity_type=CODE_ENTITY_TYPE if code else ENTITY_TYPE, entity_id=row.id)


def log_code_deletion(before: dict, version_id: int, record_id: int, username: str) -> None:
    logging_service.log_to_db(
        username, "Удалена связь кода Техинспекции",
        f"версия БД={version_id}; " + "; ".join(
            f"{_FIELD_LABELS[field]}: {_display(field, value)} → не указано" for field, value in before.items()
        ), entity_type=CODE_ENTITY_TYPE, entity_id=record_id,
    )
