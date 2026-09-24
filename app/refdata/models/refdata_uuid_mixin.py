# -*- coding: utf-8 -*-
"""
Миксин для стабильных UUID в справочниках.
"""
import uuid

from sqlalchemy import event

from app.common.services.unique_uuid_services import (
    ensure_unique_identity_uuid,
    extra_identity_uuid_sources,
)
from app.extensions import db


class RefdataUuidMixin:
    ref_uuid = db.Column(
        db.String(36),
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )


@event.listens_for(RefdataUuidMixin, "before_insert", propagate=True)
def ensure_ref_uuid_unique_before_insert(mapper, connection, target):
    """В одной версии БД ref_uuid не должен совпадать с другой записью той же таблицы."""
    table = mapper.local_table
    if "ref_uuid" not in table.c or "database_version_id" not in table.c:
        return
    schema = table.schema
    if not schema:
        return
    preferred = (getattr(target, "ref_uuid", None) or "").strip() or None
    target.ref_uuid = ensure_unique_identity_uuid(
        connection,
        schema=schema,
        table=table.name,
        column="ref_uuid",
        preferred=preferred,
        version_id=getattr(target, "database_version_id", None),
        exclude_id=getattr(target, "id", None),
        extra_sources=extra_identity_uuid_sources(schema, table.name),
    )
