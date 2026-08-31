# -*- coding: utf-8 -*-
"""Сервисы единого JSON-API обмена: наборы datasets.

Версии БД — отдельный API:
``app.api.services.database_versions_api_services``.

Выгрузка данных — только по id версии:
``GET /api/datasets/<database_version>``.
"""
from __future__ import annotations

from typing import Any, Callable

from app.api.services.general_info_exchange_services import (
    DATASET_GENERAL_INFO,
    load_general_info_dataset,
)
from app.api.services.generation_objects_exchange_services import (
    DATASET_GENERATION_MACHINES,
    DATASET_GENERATION_OBJECTS,
    load_generation_machines_dataset,
    load_generation_objects_dataset,
)
from app.api.services.gentypes_info_exchange_services import (
    DATASET_GENTYPES_INFO,
    load_gentypes_info_dataset,
)

DatasetLoader = Callable[..., dict[str, Any]]

DATASET_LOADERS: dict[str, DatasetLoader] = {
    DATASET_GENERAL_INFO: load_general_info_dataset,
    DATASET_GENTYPES_INFO: load_gentypes_info_dataset,
    DATASET_GENERATION_OBJECTS: load_generation_objects_dataset,
    DATASET_GENERATION_MACHINES: load_generation_machines_dataset,
    # equipment_group_params временно скрыт из /api/datasets
}


def list_exchange_datasets() -> dict[str, Any]:
    """Имена наборов, которые отдаёт АРМ (для справки)."""
    return {"datasets": list(DATASET_LOADERS.keys())}


def load_all_exchange_datasets(
    *,
    version_id: int,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    """Все доступные наборы для одной версии БД (id в URL, без имени набора)."""
    from app.api.services.database_versions_api_services import (
        ensure_database_version_exists,
    )

    vid = ensure_database_version_exists(version_id)
    items: list[dict[str, Any]] = []
    for loader in DATASET_LOADERS.values():
        items.append(
            loader(
                version_id=vid,
                year=year,
                start_year=start_year,
                end_year=end_year,
            )
        )
    return {
        "database_version": vid,
        "version": vid,
        "datasets": items,
    }
