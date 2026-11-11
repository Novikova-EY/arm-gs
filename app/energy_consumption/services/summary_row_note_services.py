import hashlib
import json
import re

from app.energy_consumption.models.summary_row_note_model import EnergyConsumptionSummaryRowNote
from app.extensions import db

NOTE_MAX_LENGTH = 4000


def summary_row_note_key(row):
    identity = {key: row.get(key) for key in (
        "demand_model_name", "parent_fk_column", "parent_id", "entity_kind",
        "parameter_key", "perimeter_variant_code", "gaes_station_id",
    )}
    if not row.get("demand_model_name"):
        identity["entity_label"] = row.get("entity_label")
    encoded = json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def attach_summary_row_notes(context):
    from app.common.services.database_version_services import get_current_version

    rows = context.get("summary_rows") or []
    if not rows:
        return
    version_id = get_current_version()
    for row in rows:
        row["pd_ec_note_key"] = summary_row_note_key(row)
        row["pd_ec_note_version_id"] = version_id
        row["show_entity_note_cell"] = True
    if version_id is None:
        return
    keys = {row["pd_ec_note_key"] for row in rows}
    notes = {note.row_key: note.note for note in EnergyConsumptionSummaryRowNote.query.filter(
        EnergyConsumptionSummaryRowNote.database_version_id == version_id,
        EnergyConsumptionSummaryRowNote.row_key.in_(keys),
    ).all()}
    for row in rows:
        if row["pd_ec_note_key"] in notes:
            row["entity_note_text"] = notes[row["pd_ec_note_key"]]


def save_summary_row_note(row_key, value, *, version_id, user):
    if version_id is None:
        raise ValueError("Выберите версию базы данных.")
    if not isinstance(row_key, str) or not re.fullmatch(r"[0-9a-f]{64}", row_key):
        raise ValueError("Некорректный ключ строки.")
    if not isinstance(value, str):
        raise ValueError("Примечание должно быть текстом.")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if len(value) > NOTE_MAX_LENGTH:
        raise ValueError(f"Примечание не должно превышать {NOTE_MAX_LENGTH} символов.")
    note = EnergyConsumptionSummaryRowNote.query.filter_by(
        database_version_id=version_id, row_key=row_key,
    ).first()
    if note is None:
        note = EnergyConsumptionSummaryRowNote(
            database_version_id=version_id, row_key=row_key, created_by=user,
        )
        db.session.add(note)
    note.note = value
    note.modified_by = user
    db.session.commit()
    from app.energy_consumption.services.ec_display_cache import invalidate_energy_consumption_display_caches

    invalidate_energy_consumption_display_caches(version_id=version_id)
    return value
