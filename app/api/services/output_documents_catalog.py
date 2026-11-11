# -*- coding: utf-8 -*-
"""Каталог JSON для страницы «Передача данных для выходных документов».

Дерево соответствует наборам gs_integrations (ветка changes_july, каталог br1):
колонки common, gs_sipr, rational_struct_calc и под ним rational_struct_report.
Публичные API, локальные JSON-заглушки и внешние ссылки отображаются отдельно.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.api.services.exchange_api_services import list_exchange_datasets

DATASET_DATABASE_VERSIONS = "database_versions"
MOCK_DATASETS = {
    "rational_struct_functionals",
    "rational_struct_k0",
    "rational_struct_load_graf_import_to_java",
    "rational_struct_zones",
}
RESULT_INTERFACES = {
    "rational_struct_export_from_java_powers": "powers",
    "rational_struct_export_from_java_technologies": "technologies",
}

# Имена файлов – как в репозитории интеграций; dataset = имя без .json.
OUTPUT_DOCUMENT_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "title": "common",
        "column": 1,
        "files": (
            "database_versions.json",
            "daymonth_info.json",
            "general_info.json",
            "generation_machines.json",
            "generation_machines_changes.json",
            "generation_stations.json",
            "generation_stations_changes.json",
            "gentypes_info.json",
            "hour_info.json",
            "line_capital_investments.json",
            "month_info.json",
            "newlines_building.json",
            "power_energy_export_import_country.json",
        ),
    },
    {
        "title": "gs_sipr",
        "column": 2,
        "files": (
            "load_forecast.json",
            "substations_customers_info.json",
            "substations_load_info.json",
            "substations_overload_transformer.json",
            "substations_transformer_info.json",
        ),
    },
    {
        "title": "IMPORT_GS_TO_EE",
        "column": 2,
        "files": (
            "import_gs_to_ee_zam_cena.json",
        ),
    },
    {
        "title": "rational_struct_calc",
        "column": 3,
        "files": (
            "rational_struct_export_from_java_powers.json",
            "rational_struct_export_from_java_technologies.json",
            "rational_struct_functionals.json",
            "rational_struct_import_to_java.json",
            "rational_struct_k0.json",
            "rational_struct_load_graf_import_to_java.json",
            "rational_struct_zones.json",
        ),
    },
    {
        "title": "rational_struct_report",
        "column": 3,
        "files": (
            "rational_struct_base.json",
        ),
    },
)


def _dataset_name(filename: str) -> str:
    name = str(filename or "").strip()
    if name.lower().endswith(".json"):
        return name[:-5]
    return name


def _enabled_datasets(public_datasets: Iterable[str] | None = None) -> set[str]:
    if public_datasets is None:
        public_datasets = list_exchange_datasets().get("datasets") or []
    enabled = {str(name).strip() for name in public_datasets if str(name).strip()}
    enabled.add(DATASET_DATABASE_VERSIONS)
    return enabled


def build_output_document_groups(
    public_datasets: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Группы файлов с типом источника и доступностью ссылки."""
    enabled = _enabled_datasets(public_datasets)
    groups: list[dict[str, Any]] = []
    for group in OUTPUT_DOCUMENT_GROUPS:
        files = []
        for filename in group["files"]:
            dataset = _dataset_name(filename)
            if dataset in MOCK_DATASETS:
                kind = "mock"
            elif dataset in RESULT_INTERFACES:
                kind = "external"
            elif dataset == DATASET_DATABASE_VERSIONS:
                kind = "versions_list"
            else:
                kind = "dataset"
            files.append(
                {
                    "filename": filename,
                    "dataset": dataset,
                    "enabled": dataset in enabled or kind in {"mock", "external"},
                    "kind": kind,
                    "interface": RESULT_INTERFACES.get(dataset),
                }
            )
        groups.append({
            "title": group["title"],
            "column": int(group.get("column") or 1),
            "files": files,
        })
    return groups


def list_enabled_output_document_datasets(
    public_datasets: Iterable[str] | None = None,
) -> list[str]:
    """Имена реализованных API в порядке страницы /output_documents_transfer."""
    names: list[str] = []
    for group in build_output_document_groups(public_datasets):
        for item in group["files"]:
            if item.get("enabled") and item["kind"] in {"dataset", "versions_list"}:
                name = str(item.get("dataset") or "").strip()
                if name:
                    names.append(name)
    return names
