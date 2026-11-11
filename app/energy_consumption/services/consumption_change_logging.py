"""Подробный аудит спроса и электроемкости в транзакции изменяемых данных.

Журналы сводок остаются пользовательскими отчетами об операциях; здесь хранится
история каждой строки, включая импорт, пересчет и изменения во всех версиях БД.
"""
from __future__ import annotations

import json

from flask import g, has_app_context, has_request_context, request
from sqlalchemy import event, inspect

from app.common.models.audit_mixin import AuditMixin, _get_current_username
from app.logs.models.log_model import Log
from app.logs.services.audit_helpers import (
    AUDIT_METADATA_FIELDS as _METADATA_FIELDS,
    snapshot_columns as _snapshot,
    stored_snapshot as _stored_snapshot,
)
from app.logs.services.logging_service import MAX_ACTION, MAX_USERNAME, _safe_trim

_ECONOMICS_MODELS = frozenset({
    "RussiaFederationConsumptionParameter", "FederalDistrictEATConsumptionParameter",
    "ConsumptionFormulaText",
})


def _audit_module(target):
    model_module = type(target).__module__
    if model_module.startswith("app.electrical_intensity.models."):
        return "Долгосрочный прогноз потребления"
    if model_module.startswith("app.energy_consumption.models."):
        if hasattr(target, "formula_key"):
            from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
                PAGE_ELECTRICAL_INTENSITY, get_formula_def,
            )

            definition = get_formula_def(target.formula_key)
            if definition and PAGE_ELECTRICAL_INTENSITY in definition.pages:
                return "Долгосрочный прогноз потребления"
        return "Спрос"
    if model_module.startswith("app.economics.models.") and type(target).__name__ in _ECONOMICS_MODELS:
        return "Экономика"
    if type(target).__name__ == "StationGaesChargeConsumption":
        return "Спрос"
    return None


def _write_change(mapper, connection, target, operation, before, after, module):
    fields = {
        key: {"было": before.get(key), "стало": after.get(key)}
        for key in before.keys() | after.keys()
        if before.get(key) != after.get(key)
    }
    if operation == "Изменение" and not fields:
        return
    snapshot = after or before
    version_id = snapshot.get("database_version_id")
    if "database_version_id" not in snapshot and has_app_context():
        version_id = getattr(g, "current_db_version", None)
    details = {
        "таблица": mapper.local_table.fullname,
        "контекст": snapshot,
        "изменения": fields,
    }
    if has_request_context():
        details["url"] = request.full_path
        details["endpoint"] = request.endpoint
    # Core INSERT использует то же соединение: rollback откатывает и данные, и аудит.
    # ORM add/commit внутри mapper-событий недопустимы.
    connection.execute(Log.__table__.insert().values(
        username=_safe_trim(_get_current_username(), MAX_USERNAME),
        module=module,
        action=_safe_trim(f"{operation} строки: {module} – {type(target).__name__}", MAX_ACTION),
        details=json.dumps(details, ensure_ascii=False, default=str, sort_keys=True),
        entity_type="consumption_row_change",
        entity_id=snapshot.get("id"),
        database_version_id=version_id,
    ))


def _after_insert(mapper, connection, target):
    module = _audit_module(target)
    if module:
        _write_change(mapper, connection, target, "Создание", {}, _snapshot(mapper, target), module)


def _before_update(mapper, connection, target):
    module = _audit_module(target)
    if not module:
        return
    state = inspect(target)
    changed = [
        prop.key for prop in mapper.column_attrs
        if prop.key not in _METADATA_FIELDS and state.attrs[prop.key].history.has_changes()
    ]
    if not changed:
        return
    before = _stored_snapshot(mapper, connection, target)
    after = dict(before)
    for key in changed:
        after[key] = getattr(target, key)
    _write_change(mapper, connection, target, "Изменение", before, after, module)


def _before_delete(mapper, connection, target):
    module = _audit_module(target)
    if module:
        before = _stored_snapshot(mapper, connection, target)
        _write_change(mapper, connection, target, "Удаление", before, {}, module)


def init_consumption_change_logging():
    for name, listener in (
        ("after_insert", _after_insert),
        ("before_update", _before_update),
        ("before_delete", _before_delete),
    ):
        if not event.contains(AuditMixin, name, listener):
            event.listen(AuditMixin, name, listener, propagate=True)
