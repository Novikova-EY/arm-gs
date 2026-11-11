"""Transactional summaries and scoped history for the three refresh controls."""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from flask import current_app, g, has_app_context, has_request_context, jsonify, request
from flask_login import current_user
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy import event, func, inspect, select, tuple_, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import MANYTOONE, Session

from app.common.models.audit_mixin import _get_current_username
from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.logs.models.data_refresh_event_model import DataRefreshEvent, DataRefreshState
from app.logs.services.audit_helpers import AUDIT_METADATA_FIELDS, snapshot_columns, stored_snapshot
from app.logs.services.field_names_ru import get_field_name_ru
from app.energy_balance.services.change_log_services import value_change

_SOURCE_LABELS = {
    "consumption": "Спрос", "demand": "Нагрузки", "balance": "Энергобалансы",
    "generation": "Генерация", "forecast": "Перспективные площадки",
    "fuel": "Топливные данные", "refdata": "Справочники",
    "territories": "Территории", "intensity": "Долгосрочный прогноз потребления",
}
_PREFIXES = (
    ("app.energy_consumption.models.", "consumption"),
    ("app.power_demand.models.", "demand"),
    ("app.energy_balance.models.", "balance"),
    ("app.generation.models.", "generation"),
    ("app.generation.prospective_places.models.", "forecast"),
    ("app.fuel.models.", "fuel"),
    ("app.refdata.models.", "refdata"),
    ("app.territories.models.", "territories"),
    ("app.electrical_intensity.models.", "intensity"),
)
_MODULE_SOURCES = {}


def _source(model):
    return next((source for prefix, source in _PREFIXES if model.__module__.startswith(prefix)), None)


def _operation_id(session):
    if has_request_context():
        if "data_refresh_operation_id" not in g:
            g.data_refresh_operation_id = str(uuid4())
        return g.data_refresh_operation_id
    return session.info.setdefault("data_refresh_operation_id", str(uuid4()))


def _kind(model, operation):
    name = model.__name__.lower()
    if "note" in name:
        return "note"
    if "formula" in name:
        return "formula"
    if has_request_context():
        endpoint = (request.endpoint or "").lower()
        if "import" in endpoint:
            return "import"
        if "recalc" in endpoint or "calculate" in endpoint or "persist_computed" in endpoint:
            return "calculation"
    return operation


def _category(model):
    name = model.__name__.lower()
    for token, label in (
        ("gaescharge", "Заряд ГАЭС"), ("ozp", "Максимумы ОЗП"),
        ("ownneeds", "Собственные нужды"), ("importexport", "Импорт и экспорт электроэнергии"),
        ("receivetransfer", "Прием и отдача электроэнергии"), ("transfer", "Перетоки"),
        ("federaldistrict", "Данные по федеральным округам"),
        ("regionaldistrict", "Данные по субъектам РФ"),
        ("unionenergysystem", "Данные по ОЭС"), ("regionalenergysystem", "Данные по энергосистемам"),
        ("energyzone", "Данные по энергозонам"), ("station", "Данные электростанций"),
        ("equipmentgroup", "Группы оборудования"), ("machine", "Генерирующее оборудование"),
    ):
        if token in name:
            return label
    return _SOURCE_LABELS[_source(model)]


def _queue_event(session, model, operation, version, scope_known, count, years=(), objects=(), details=()):
    transaction = session.get_nested_transaction() or session.get_transaction()
    pending = session.info.setdefault("data_refresh_pending", {})
    pending.setdefault(transaction, []).append((model, operation, version, scope_known, count, years, objects, details))


def _write_event(session, model, operation, version, scope_known, count, years, objects, details):
    source = _source(model)
    if source is None:
        return
    connection = session.connection()
    state = DataRefreshState.__table__
    # The singleton lock makes the cursor follow commit order, not sequence allocation order.
    revision = connection.execute(update(state).where(state.c.id == 1).values(
        revision=state.c.revision + 1,
    ).returning(state.c.revision)).scalar_one()
    username = _get_current_username() if has_request_context() else "Системный процесс"
    connection.execute(DataRefreshEvent.__table__.insert().values(
        revision=revision, operation_id=_operation_id(session),
        recorded_at=datetime.now(timezone.utc), username=username[:100], source=source,
        kind=_kind(model, operation), database_version_id=version, scope_known=scope_known,
        **{module: source in sources for module, sources in _MODULE_SOURCES.items()},
        summary={"records": count, "years": sorted(set(years)), "category": _category(model),
                 "objects": sorted(set(objects))[:5], "details": details},
    ))


def _related_names(session, mapper, snapshot):
    names = {}
    cache = session.info.setdefault("data_refresh_names", {})
    for relation in mapper.relationships:
        table = relation.mapper.local_table
        if relation.direction is not MANYTOONE or "name" not in table.c:
            continue
        pairs = relation.local_remote_pairs
        values = tuple(snapshot.get(local.key) for local, _remote in pairs)
        if any(value is None for value in values):
            continue
        key = (table.fullname, tuple(remote.key for _local, remote in pairs), values,
               snapshot.get("database_version_id"))
        if key not in cache:
            query = select(table.c.name).where(*[remote == value for (_local, remote), value in zip(pairs, values)])
            if "database_version_id" in table.c:
                query = query.where(table.c.database_version_id == snapshot.get("database_version_id"))
            cache[key] = session.connection().execute(query).scalar()
        if cache[key]:
            names.update({local.key: cache[key] for local, _remote in pairs})
    return names


def _queue_rows(session, model, rows):
    mapper = inspect(model)
    groups = defaultdict(lambda: {"years": set(), "objects": set(), "details": []})
    for before, after in rows:
        # Moving a row between versions is a removal in the old version and an addition in the new one.
        if before and after and before.get("database_version_id") != after.get("database_version_id"):
            _queue_rows(session, model, [(before, {}), ({}, after)])
            continue
        snapshot = after or before
        version = snapshot.get("database_version_id")
        if version is None:
            continue
        fields = sorted(key for key in before.keys() | after.keys()
                        if key not in AUDIT_METADATA_FIELDS | {"id", "database_version_id"}
                        and before.get(key) != after.get(key))
        if before and after and not fields:
            continue
        operation = "add" if not before else "delete" if not after else "change"
        if operation == "change" and set(fields) <= {"note", "notes", "note_text"}:
            operation = "note"
        group = groups[(operation, version)]
        old_names = _related_names(session, mapper, before) if before else {}
        new_names = _related_names(session, mapper, after) if after else {}
        names = new_names or old_names
        labels = [snapshot["name"]] if snapshot.get("name") else list(dict.fromkeys(names.values()))
        group["objects"].update(labels)
        year = snapshot.get("year_number", snapshot.get("ozp_end_year"))
        if isinstance(year, int):
            group["years"].add(year)
        context = labels or [_category(model)]
        if year is not None:
            context = [*context, str(year)]
        if snapshot.get("perimeter_variant_code"):
            context = [*context, snapshot["perimeter_variant_code"]]
        if snapshot.get("month_number") is not None:
            context = [*context, "год" if snapshot["month_number"] == 0 else f"месяц {snapshot['month_number']}"]
        context.extend(str(snapshot[key]) for key in ("sheet_slug", "row_key", "label", "source_oes_name") if snapshot.get(key))
        changes = []
        for field in fields:
            old = old_names.get(field, before.get(field))
            new = new_names.get(field, after.get(field))
            number = any(isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) for value in (old, new))
            changes.append(value_change(get_field_name_ru(field), old, new, number=number))
        group["details"].append({"object": " · ".join(context), "changes": changes})
    for (operation, version), group in groups.items():
        _queue_event(session, model, operation, version, True, len(group["details"]),
                     group["years"], group["objects"], group["details"])


def _before_flush(session, _context, _instances):
    if not _enabled():
        return
    snapshots = session.info.setdefault("data_refresh_before", {})
    for obj in session.dirty | session.deleted:
        state = inspect(obj)
        if _source(type(obj)) is None or "database_version_id" not in state.mapper.column_attrs:
            continue
        if obj in session.deleted or any(state.attrs[prop.key].history.has_changes()
                                        for prop in state.mapper.column_attrs if prop.key not in AUDIT_METADATA_FIELDS):
            snapshots[obj] = stored_snapshot(state.mapper, session.connection(), obj)


def _after_flush(session, _context):
    if not _enabled():
        return
    snapshots = session.info.pop("data_refresh_before", {})
    rows = defaultdict(list)
    for collection in (session.new, session.deleted, session.dirty):
        for obj in collection:
            state = inspect(obj)
            if _source(type(obj)) is None or "database_version_id" not in state.mapper.column_attrs:
                continue
            if obj not in session.new and obj not in snapshots:
                continue
            before = snapshots.get(obj, {})
            after = {} if obj in session.deleted else snapshot_columns(state.mapper, obj)
            rows[type(obj)].append((before, after))
    for model, changes in rows.items():
        _queue_rows(session, model, changes)


def _orm_write(state):
    if not _enabled() or not (state.is_insert or state.is_update or state.is_delete) or state.bind_mapper is None:
        return
    mapper = state.bind_mapper
    model = mapper.class_
    if _source(model) is None or "database_version_id" not in mapper.column_attrs:
        return
    session = state.session
    if session.autoflush and state.execution_options.get("autoflush", True):
        session.flush()
    table = mapper.local_table
    parameters = state.parameters
    if state.is_insert:
        result = state.invoke_statement()
        # Explicit versioned input is safe to describe; never infer a version from the open page.
        if getattr(result, "rowcount", None) != 0 and getattr(state.statement, "_post_values_clause", None) is None:
            values = parameters if isinstance(parameters, list) else [parameters or state.statement.compile().params]
            _queue_rows(session, model, [({}, dict(value)) for value in values])
        return result
    before = {}
    parameter_sets = parameters if isinstance(parameters, list) else [parameters or {}]
    for values in parameter_sets:
        query = select(table)
        if state.statement.whereclause is not None:
            query = query.where(state.statement.whereclause)
        if isinstance(parameters, list):
            if not all(column.key in values for column in mapper.primary_key):
                continue
            query = query.where(*[column == values[column.key] for column in mapper.primary_key])
        for row in session.connection().execute(query, values).mappings():
            before[tuple(row[column.key] for column in mapper.primary_key)] = dict(row)
    result = state.invoke_statement()
    after = {}
    if before:
        query = select(table).where(tuple_(*mapper.primary_key).in_(list(before)))
        after = {tuple(row[column.key] for column in mapper.primary_key): dict(row)
                 for row in session.connection().execute(query).mappings()}
    _queue_rows(session, model, [(row, after.get(identity, {})) for identity, row in before.items()])
    return result


def _before_commit(session):
    if not _enabled() or session.get_nested_transaction() is not None:
        return
    # Collect even the final implicit flush, then take the journal lock only at commit.
    session.flush()
    pending = session.info.get("data_refresh_pending", {})
    for changes in pending.values():
        for change in changes:
            _write_event(session, *change)


def _after_commit(session):
    nested = session.get_nested_transaction()
    pending = session.info.get("data_refresh_pending", {})
    if nested is not None and nested in pending:
        pending.setdefault(nested.parent, []).extend(pending.pop(nested))


def _after_rollback(session, transaction):
    session.info.get("data_refresh_pending", {}).pop(transaction, None)
    session.info.pop("data_refresh_before", None)
    session.info.pop("data_refresh_names", None)


def _transaction_end(session, transaction):
    if transaction.parent is None:
        session.info.pop("data_refresh_operation_id", None)
        session.info.pop("data_refresh_pending", None)
        session.info.pop("data_refresh_before", None)
        session.info.pop("data_refresh_names", None)


_HANDLERS = (
    ("before_flush", _before_flush), ("after_flush", _after_flush), ("do_orm_execute", _orm_write),
    ("before_commit", _before_commit), ("after_commit", _after_commit),
    ("after_soft_rollback", _after_rollback), ("after_transaction_end", _transaction_end),
)


def init_data_refresh_history(app):
    from app.energy_balance.services.energy_balance_change_events import _tracker as balance
    from app.energy_consumption.services.data_refresh_services import _tracker as consumption
    from app.power_demand.services.data_refresh_services import _tracker as demand

    for module, tracker in (("balance", balance), ("consumption", consumption), ("demand", demand)):
        _MODULE_SOURCES[module] = {
            source for prefix, source in _PREFIXES if prefix.startswith(tracker.source_modules)
        }
    for name, handler in _HANDLERS:
        if not event.contains(Session, name, handler):
            event.listen(Session, name, handler, **({"retval": True} if name == "do_orm_execute" else {}))
    app.extensions["data_refresh_history"] = True


def _serializer():
    return URLSafeSerializer(current_app.secret_key, salt="data-refresh-history")


def _enabled():
    return has_app_context() and current_app.extensions.get("data_refresh_history", False)


def capture_history(module):
    page_context = {"loadedAt": datetime.now(timezone.utc).isoformat(),
                    "historyModule": _SOURCE_LABELS[module], "historyVersion": get_current_db_version_id()}
    if not _enabled():
        return {"historyCursor": None, **page_context}
    try:
        with db.engine.connect() as connection:
            state = connection.execute(select(DataRefreshState.__table__)).mappings().one()
        cursor = _serializer().dumps({
            "epoch": state["epoch"], "after": state["revision"], "module": module,
            "version": get_current_db_version_id(),
        })
    except SQLAlchemyError:
        current_app.logger.exception("Cannot capture data refresh history")
        cursor = None
    return {"historyCursor": cursor, **page_context}


def _scope(module, version):
    table = DataRefreshEvent.__table__
    return (
        table.c[module].is_(True), table.c.scope_known.is_(True),
        table.c.database_version_id.is_not(None), table.c.database_version_id == version,
    )


def _history_query(module, cursor):
    try:
        baseline = _serializer().loads(cursor)
    except BadSignature:
        return None, "История для этой страницы недоступна. Обновите данные."
    version = get_current_db_version_id()
    if baseline.get("module") != module or baseline.get("version") != version:
        return None, "Версия базы данных изменилась. Обновите страницу."
    with db.engine.connect() as connection:
        state = connection.execute(select(DataRefreshState.__table__)).mappings().one()
    if baseline.get("epoch") != state["epoch"] or baseline.get("after", -1) > state["revision"]:
        return None, "Состояние истории изменилось. Обновите данные."
    table = DataRefreshEvent.__table__
    return select(table).where(*_scope(module, version), table.c.revision > baseline["after"]), None


def history_status(module):
    if not _enabled() or not request.args.get("history_cursor"):
        return None
    try:
        query, message = _history_query(module, request.args["history_cursor"])
        if query is None:
            return {"available": False, "message": message}
        with db.engine.connect() as connection:
            count = connection.execute(select(func.count(func.distinct(query.subquery().c.operation_id)))).scalar_one()
        return {"available": True, "count": count}
    except SQLAlchemyError:
        current_app.logger.exception("Cannot check data refresh history")
        return {"available": False, "message": "История изменений временно недоступна."}


_KIND_LABELS = {
    "add": "Добавление данных", "delete": "Удаление данных", "change": "Изменение данных",
    "import": "Импорт: сохранены изменения", "calculation": "Пересчет с сохранением",
    "formula": "Изменение формул", "note": "Изменение примечаний",
}


def history_response(module):
    if not _enabled():
        return jsonify(ok=False, message="История изменений недоступна."), 503
    try:
        query, message = _history_query(module, request.args.get("history_cursor", ""))
        if query is None:
            return jsonify(ok=True, available=False, message=message, events=[])
        before = request.args.get("before", type=int)
        table = DataRefreshEvent.__table__
        operations = query.with_only_columns(
            table.c.operation_id, func.max(table.c.revision).label("latest"),
        ).group_by(table.c.operation_id)
        if before is not None:
            operations = operations.having(func.max(table.c.revision) < before)
        operations = operations.order_by(func.max(table.c.revision).desc()).limit(21)
        with db.engine.connect() as connection:
            page = connection.execute(operations).mappings().all()
            ids = [row["operation_id"] for row in page[:20]]
            rows = connection.execute(query.where(table.c.operation_id.in_(ids)).order_by(table.c.revision.desc())).mappings().all() if ids else []
        grouped = {}
        for row in rows:
            group = grouped.setdefault(row["operation_id"], [])
            group.append(row)
        roles = getattr(current_user, "role_names", []) or []
        admin = current_user.username == "admin" or "admin" in roles
        events = []
        for operation_rows in grouped.values():
            latest = operation_rows[0]
            sources = sorted({_SOURCE_LABELS[row["source"]] for row in operation_rows})
            kinds = sorted({_KIND_LABELS[row["kind"]] for row in operation_rows})
            years = sorted({year for row in operation_rows for year in row["summary"]["years"] if row["scope_known"]})
            categories = sorted({row["summary"]["category"] for row in operation_rows})
            objects = sorted({label for row in operation_rows if row["scope_known"] and (admin or row["source"] == module)
                              for label in row["summary"]["objects"]})[:5]
            counts = [row["summary"]["records"] for row in operation_rows]
            details = [detail for row in operation_rows if admin or row["source"] == module
                       for detail in row["summary"].get("details", [])]
            own = latest["username"] == current_user.username
            timestamp = latest["recorded_at"]
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            events.append({
                "id": latest["operation_id"], "time": timestamp.isoformat(),
                "title": "; ".join(kinds), "source": ", ".join(sources),
                "actor": latest["username"] if admin or own or latest["username"] == "Системный процесс" else "Другой пользователь",
                "records": sum(counts) if all(count is not None for count in counts) else None,
                "years": years, "categories": categories, "objects": objects,
                "details": details,
            })
        response = jsonify(ok=True, available=True, events=events,
                           nextBefore=page[19]["latest"] if len(page) > 20 else None)
        response.headers["Cache-Control"] = "no-store, private"
        return response
    except SQLAlchemyError:
        current_app.logger.exception("Cannot read data refresh history")
        return jsonify(ok=False, message="Не удалось загрузить историю. Обновление данных доступно вручную."), 503
