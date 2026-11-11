"""Уведомления об изменении источников после commit внешней транзакции."""

from sqlalchemy import event
from sqlalchemy.orm import Session


class DataChangeTracker:
    def __init__(self, source_modules, publish, pending_key):
        self.source_modules = source_modules
        self.publish = publish
        self.pending_key = pending_key

    def _is_source(self, model):
        return model.__module__.startswith(self.source_modules)

    def _mark_transaction(self, session):
        transaction = session.get_nested_transaction() or session.get_transaction()
        session.info.setdefault(self.pending_key, set()).add(transaction)

    def _after_flush(self, session, _context):
        for obj in (*session.new, *session.deleted):
            if self._is_source(type(obj)):
                self._mark_transaction(session)
                return
        for obj in session.dirty:
            if self._is_source(type(obj)) and session.is_modified(obj, include_collections=True):
                self._mark_transaction(session)
                return

    def _orm_write(self, state):
        if (state.is_insert or state.is_update or state.is_delete) and state.bind_mapper is not None:
            if self._is_source(state.bind_mapper.class_):
                self._mark_transaction(state.session)

    def _after_commit(self, session):
        pending = session.info.get(self.pending_key, set())
        nested = session.get_nested_transaction()
        if nested is not None:
            if nested in pending:
                pending.remove(nested)
                pending.add(nested.parent)
            return
        if session.info.pop(self.pending_key, None):
            self.publish()

    def _after_soft_rollback(self, session, transaction):
        pending = session.info.get(self.pending_key)
        if pending is not None:
            pending.discard(transaction)
            if transaction.parent is None or not pending:
                session.info.pop(self.pending_key, None)

    def register(self):
        for name, handler in (
            ("after_flush", self._after_flush),
            ("do_orm_execute", self._orm_write),
            ("after_commit", self._after_commit),
            ("after_soft_rollback", self._after_soft_rollback),
        ):
            if not event.contains(Session, name, handler):
                event.listen(Session, name, handler)
