# -*- coding: utf-8 -*-
"""Сервисы JSON-API обмена: один набор — отдельный endpoint.

Первый запрос клиента (discovery): ``GET /api/config``.

Версии БД — отдельный API:
``app.api.services.database_versions_api_services``.

Выгрузка данных — по id версии и имени набора:
``GET /api/datasets/<database_version>/<dataset>``.
"""
from __future__ import annotations

from typing import Any, Callable

# Версия контракта discovery.
EXCHANGE_CONFIG_VERSION = "2026-07-01T00:00:00Z"
EXCHANGE_CONFIG_HEADERS = {"Accept": "application/json"}
# Шаблон пути к набору: подставить id версии и имя из datasets.
EXCHANGE_DATASET_PATH_TEMPLATE = "/api/datasets/{database_version}/{dataset}"
EXCHANGE_DATABASE_VERSIONS_PATH = "/api/database_versions"
EXCHANGE_DATASETS_CATALOG_PATH = "/api/datasets"

from app.api.services.daymonth_info_exchange_services import (
    DATASET_DAYMONTH_INFO,
    load_daymonth_info_dataset,
)
from app.api.services.general_info_exchange_services import (
    DATASET_GENERAL_INFO,
    load_general_info_dataset,
)
from app.api.services.generation_objects_exchange_services import (
    DATASET_GENERATION_MACHINES,
    DATASET_GENERATION_STATIONS,
    load_generation_machines_dataset,
    load_generation_stations_dataset,
)
from app.api.services.gentypes_info_exchange_services import (
    DATASET_GENTYPES_INFO,
    load_gentypes_info_dataset,
)
from app.api.services.hour_info_exchange_services import (
    DATASET_HOUR_INFO,
    load_hour_info_dataset,
)
from app.api.services.line_capital_investments_exchange_services import (
    DATASET_LINE_CAPITAL_INVESTMENTS,
    load_line_capital_investments_dataset,
)
from app.api.services.load_forecast_exchange_services import (
    DATASET_LOAD_FORECAST,
    load_load_forecast_dataset,
)
from app.api.services.month_info_exchange_services import (
    DATASET_MONTH_INFO,
    load_month_info_dataset,
)
from app.api.services.newlines_building_exchange_services import (
    DATASET_NEWLINES_BUILDING,
    load_newlines_building_dataset,
)
from app.api.services.power_energy_export_import_country_exchange_services import (
    DATASET_POWER_ENERGY_EXPORT_IMPORT_COUNTRY,
    load_power_energy_export_import_country_dataset,
)
from app.api.services.rational_struct_base_exchange_services import (
    DATASET_RATIONAL_STRUCT_BASE,
    load_rational_struct_base_dataset,
)
from app.api.services.substations_customers_info_exchange_services import (
    DATASET_SUBSTATIONS_CUSTOMERS_INFO,
    load_substations_customers_info_dataset,
)
from app.api.services.substations_load_info_exchange_services import (
    DATASET_SUBSTATIONS_LOAD_INFO,
    load_substations_load_info_dataset,
)
from app.api.services.substations_overload_transformer_exchange_services import (
    DATASET_SUBSTATIONS_OVERLOAD_TRANSFORMER,
    load_substations_overload_transformer_dataset,
)
from app.api.services.substations_transformer_info_exchange_services import (
    DATASET_SUBSTATIONS_TRANSFORMER_INFO,
    load_substations_transformer_info_dataset,
)

DatasetLoader = Callable[..., dict[str, Any]]

DATASET_LOADERS: dict[str, DatasetLoader] = {
    DATASET_GENERAL_INFO: load_general_info_dataset,
    DATASET_GENTYPES_INFO: load_gentypes_info_dataset,
    DATASET_GENERATION_STATIONS: load_generation_stations_dataset,
    DATASET_GENERATION_MACHINES: load_generation_machines_dataset,
    DATASET_DAYMONTH_INFO: load_daymonth_info_dataset,
    DATASET_HOUR_INFO: load_hour_info_dataset,
    DATASET_LINE_CAPITAL_INVESTMENTS: load_line_capital_investments_dataset,
    DATASET_MONTH_INFO: load_month_info_dataset,
    DATASET_NEWLINES_BUILDING: load_newlines_building_dataset,
    DATASET_POWER_ENERGY_EXPORT_IMPORT_COUNTRY: (
        load_power_energy_export_import_country_dataset
    ),
    DATASET_SUBSTATIONS_CUSTOMERS_INFO: load_substations_customers_info_dataset,
    DATASET_SUBSTATIONS_LOAD_INFO: load_substations_load_info_dataset,
    DATASET_SUBSTATIONS_OVERLOAD_TRANSFORMER: (
        load_substations_overload_transformer_dataset
    ),
    DATASET_SUBSTATIONS_TRANSFORMER_INFO: load_substations_transformer_info_dataset,
    DATASET_LOAD_FORECAST: load_load_forecast_dataset,
    DATASET_RATIONAL_STRUCT_BASE: load_rational_struct_base_dataset,
    # equipment_group_params временно скрыт из /api/datasets
}


class UnknownDatasetError(LookupError):
    """Имя набора не входит в публичный каталог."""


def list_exchange_datasets() -> dict[str, Any]:
    """Имена наборов, которые отдаёт АРМ (для справки)."""
    return {"datasets": list(DATASET_LOADERS.keys())}


def build_exchange_config(*, base_url: str) -> dict[str, Any]:
    """Discovery для внешнего клиента: первый запрос в сторону АРМ.

    ``datasets`` — реализованные JSON-наборы со страницы
    ``/output_documents_transfer`` (без ``database_versions``: он в
    ``database_versions_url``).
    """
    from app.api.services.output_documents_catalog import (
        DATASET_DATABASE_VERSIONS,
        list_enabled_output_document_datasets,
    )

    root = str(base_url or "").rstrip("/")
    names = [
        name
        for name in list_enabled_output_document_datasets()
        if name != DATASET_DATABASE_VERSIONS
    ]
    return {
        "url": f"{root}{EXCHANGE_DATASET_PATH_TEMPLATE}",
        "database_versions_url": f"{root}{EXCHANGE_DATABASE_VERSIONS_PATH}",
        "datasets_url": f"{root}{EXCHANGE_DATASETS_CATALOG_PATH}",
        "datasets": names,
        "version": EXCHANGE_CONFIG_VERSION,
        "headers": dict(EXCHANGE_CONFIG_HEADERS),
    }


def list_exchange_datasets_for_version(version_id: int) -> dict[str, Any]:
    """Каталог наборов для выбранной версии БД (без самих данных)."""
    from app.api.services.database_versions_api_services import (
        ensure_database_version_exists,
    )

    vid = ensure_database_version_exists(version_id)
    names = list(DATASET_LOADERS.keys())
    return {
        "database_version": vid,
        "datasets": names,
        "paths": [f"/api/datasets/{vid}/{name}" for name in names],
    }


def load_exchange_dataset(
    dataset: str,
    *,
    version_id: int,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    """Один JSON-набор для одной версии БД."""
    from app.api.services.database_versions_api_services import (
        ensure_database_version_exists,
    )

    name = str(dataset or "").strip()
    loader = DATASET_LOADERS.get(name)
    if loader is None:
        raise UnknownDatasetError(name)
    vid = ensure_database_version_exists(version_id)
    return loader(
        version_id=vid,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
