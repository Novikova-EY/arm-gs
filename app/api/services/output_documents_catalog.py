# -*- coding: utf-8 -*-
"""Каталог JSON для страницы «Передача данных для выходных документов».

Дерево соответствует наборам gs_integrations (ветка changes_july, каталог br1):
колонки common, gs_sipr, rational_struct_calc и под ним rational_struct_report.
Активность кнопки задаётся публичным /api, а не наличием чернового кода сборки.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.api.services.exchange_api_services import list_exchange_datasets

DATASET_DATABASE_VERSIONS = "database_versions"

# Имена файлов — как в репозитории интеграций; dataset = имя без .json.
OUTPUT_DOCUMENT_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "title": "common",
        "column": 1,
        "files": (
            "database_versions.json",
            "daymonth_info.json",
            "general_info.json",
            "generation_machines.json",
            "generation_stations.json",
            "gentypes_info.json",
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
        "title": "rational_struct_calc",
        "column": 3,
        "files": (
            "rational_struct_export_from_java.json",
            "rational_struct_import_to_java.json",
            "rational_struct_powers_export_from_java.json",
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
    """Группы файлов с флагом, есть ли уже публичный API."""
    enabled = _enabled_datasets(public_datasets)
    groups: list[dict[str, Any]] = []
    for group in OUTPUT_DOCUMENT_GROUPS:
        files = []
        for filename in group["files"]:
            dataset = _dataset_name(filename)
            files.append(
                {
                    "filename": filename,
                    "dataset": dataset,
                    "enabled": dataset in enabled,
                    "kind": (
                        "versions_list"
                        if dataset == DATASET_DATABASE_VERSIONS
                        else "dataset"
                    ),
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
            if item.get("enabled"):
                name = str(item.get("dataset") or "").strip()
                if name:
                    names.append(name)
    return names
