# -*- coding: utf-8 -*-
"""
Автоматическая синхронизация исторических справочников при изменениях.
"""
from sqlalchemy import event

from app.extensions import db
from app.refdata.models.history.refdata_entity_model import RefdataEntity, RefdataEntityYear
from app.refdata.services.history.refdata_history_services import (
    REFDATA_HISTORY_MAPPINGS,
    sync_refdata_history_for_instance,
)


def _is_refdata_instance(obj) -> bool:
    return obj.__class__ in REFDATA_HISTORY_MAPPINGS


@event.listens_for(db.session, "after_flush")
def _collect_refdata_history_targets(session, flush_context):
    if session.info.get("refdata_history_in_progress"):
        return
    targets = []
    deleted_targets = []
    for obj in session.new.union(session.dirty):
        if obj in session.deleted:
            continue
        if isinstance(obj, (RefdataEntity, RefdataEntityYear)):
            continue
        if _is_refdata_instance(obj):
            targets.append(obj)
    for obj in session.deleted:
        if isinstance(obj, (RefdataEntity, RefdataEntityYear)):
            continue
        if _is_refdata_instance(obj):
            deleted_targets.append(obj)
    if targets:
        session.info["refdata_history_targets"] = targets
    if deleted_targets:
        session.info["refdata_history_deleted_targets"] = deleted_targets


@event.listens_for(db.session, "after_flush_postexec")
def _apply_refdata_history_targets(session, flush_context):
    targets = session.info.pop("refdata_history_targets", [])
    deleted_targets = session.info.pop("refdata_history_deleted_targets", [])
    if not targets:
        if not deleted_targets:
            return
    session.info["refdata_history_in_progress"] = True
    try:
        for obj in deleted_targets:
            sync_refdata_history_for_instance(obj, session, is_deleted=True)
        for obj in targets:
            sync_refdata_history_for_instance(obj, session)
    finally:
        session.info["refdata_history_in_progress"] = False
