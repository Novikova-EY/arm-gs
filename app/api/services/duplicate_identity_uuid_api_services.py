# -*- coding: utf-8 -*-
"""JSON-отчёт о дублирующих identity-UUID (dry-run скрипта)."""
from __future__ import annotations

from typing import Any

from app.common.services.duplicate_identity_uuid_services import (
    build_duplicate_identity_uuid_report,
)


def load_duplicate_identity_uuids_dataset(
    *,
    version_id: int | None = None,
    include_refdata: bool = False,
    **_kwargs: Any,
) -> dict[str, Any]:
    payload = build_duplicate_identity_uuid_report(
        version_id=version_id,
        include_refdata=include_refdata,
    )
    payload["dataset"] = "duplicate_identity_uuids"
    return payload
