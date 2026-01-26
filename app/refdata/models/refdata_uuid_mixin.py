# -*- coding: utf-8 -*-
"""
Миксин для стабильных UUID в справочниках.
"""
import uuid

from app.extensions import db


class RefdataUuidMixin:
    ref_uuid = db.Column(
        db.String(36),
        nullable=False,
        index=True,
        default=lambda: str(uuid.uuid4()),
    )
