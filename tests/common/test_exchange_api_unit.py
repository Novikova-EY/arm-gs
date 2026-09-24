# -*- coding: utf-8 -*-
"""Юнит-тесты API версий БД и JSON-наборов."""
from types import SimpleNamespace

import pytest

from app.api.services import database_versions_api_services as versions_svc
from app.api.services import exchange_api_services as datasets_svc


def test_list_exchange_datasets_known_names():
    names = datasets_svc.list_exchange_datasets()["datasets"]
    assert names == [
        "general_info",
        "gentypes_info",
        "generation_stations",
        "generation_machines",
        "daymonth_info",
        "line_capital_investments",
        "month_info",
        "newlines_building",
        "power_energy_export_import_country",
        "substations_customers_info",
        "substations_load_info",
        "substations_overload_transformer",
        "substations_transformer_info",
        "load_forecast",
        "rational_struct_base",
    ]
    assert "generation_objects" not in names
    assert "equipment_group_params" not in names


def test_build_exchange_config_shape():
    from app.api.services.output_documents_catalog import (
        DATASET_DATABASE_VERSIONS,
        list_enabled_output_document_datasets,
    )

    payload = datasets_svc.build_exchange_config(
        base_url="http://msk-arm-gs01.ntcees.ru/"
    )
    names = [
        name
        for name in list_enabled_output_document_datasets()
        if name != DATASET_DATABASE_VERSIONS
    ]
    assert payload == {
        "url": (
            "http://msk-arm-gs01.ntcees.ru/api/datasets/{database_version}/{dataset}"
        ),
        "database_versions_url": (
            "http://msk-arm-gs01.ntcees.ru/api/database_versions"
        ),
        "datasets_url": "http://msk-arm-gs01.ntcees.ru/api/datasets",
        "datasets": names,
        "version": datasets_svc.EXCHANGE_CONFIG_VERSION,
        "headers": {"Accept": "application/json"},
    }
    assert "database_versions" not in payload["datasets"]
    assert "general_info" in names
    assert "rational_struct_base" in names
    assert "generation_objects" not in names
    assert "rational_struct_import_to_java" not in names


def test_config_datasets_match_page_enabled_buttons():
    from app.api.services.output_documents_catalog import (
        DATASET_DATABASE_VERSIONS,
        list_enabled_output_document_datasets,
    )

    assert [
        name
        for name in list_enabled_output_document_datasets()
        if name != DATASET_DATABASE_VERSIONS
    ] == [
        "daymonth_info",
        "general_info",
        "generation_machines",
        "generation_stations",
        "gentypes_info",
        "line_capital_investments",
        "month_info",
        "newlines_building",
        "power_energy_export_import_country",
        "load_forecast",
        "substations_customers_info",
        "substations_load_info",
        "substations_overload_transformer",
        "substations_transformer_info",
        "rational_struct_base",
    ]


def test_load_exchange_dataset_by_name(monkeypatch):
    calls = []

    def fake_gentypes(**kwargs):
        calls.append(("gentypes_info", kwargs))
        return {"dataset": "gentypes_info", "database_version": 7, "rows": [0]}

    def fake_stations(**kwargs):
        calls.append(("generation_stations", kwargs))
        return {"dataset": "generation_stations", "database_version": 7, "rows": [1]}

    def fake_machines(**kwargs):
        calls.append(("generation_machines", kwargs))
        return {"dataset": "generation_machines", "database_version": 7, "rows": [2]}

    monkeypatch.setitem(datasets_svc.DATASET_LOADERS, "gentypes_info", fake_gentypes)
    monkeypatch.setitem(
        datasets_svc.DATASET_LOADERS, "generation_stations", fake_stations
    )
    monkeypatch.setitem(
        datasets_svc.DATASET_LOADERS, "generation_machines", fake_machines
    )
    monkeypatch.setattr(
        "app.api.services.database_versions_api_services.ensure_database_version_exists",
        lambda version_id: int(version_id),
    )

    payload = datasets_svc.load_exchange_dataset(
        "generation_stations",
        version_id=7,
        year=2032,
        start_year=None,
        end_year=None,
    )
    assert payload["dataset"] == "generation_stations"
    assert payload["database_version"] == 7
    assert calls == [
        (
            "generation_stations",
            {
                "version_id": 7,
                "year": 2032,
                "start_year": None,
                "end_year": None,
            },
        )
    ]


def test_load_exchange_dataset_unknown_name(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.database_versions_api_services.ensure_database_version_exists",
        lambda version_id: int(version_id),
    )
    with pytest.raises(datasets_svc.UnknownDatasetError):
        datasets_svc.load_exchange_dataset("rational_struct_import_to_java", version_id=7)


def test_list_exchange_datasets_for_version(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.database_versions_api_services.ensure_database_version_exists",
        lambda version_id: int(version_id),
    )
    payload = datasets_svc.list_exchange_datasets_for_version(37)
    assert payload["database_version"] == 37
    assert payload["datasets"] == [
        "general_info",
        "gentypes_info",
        "generation_stations",
        "generation_machines",
        "daymonth_info",
        "line_capital_investments",
        "month_info",
        "newlines_building",
        "power_energy_export_import_country",
        "substations_customers_info",
        "substations_load_info",
        "substations_overload_transformer",
        "substations_transformer_info",
        "load_forecast",
        "rational_struct_base",
    ]
    assert payload["paths"] == [
        "/api/datasets/37/general_info",
        "/api/datasets/37/gentypes_info",
        "/api/datasets/37/generation_stations",
        "/api/datasets/37/generation_machines",
        "/api/datasets/37/daymonth_info",
        "/api/datasets/37/line_capital_investments",
        "/api/datasets/37/month_info",
        "/api/datasets/37/newlines_building",
        "/api/datasets/37/power_energy_export_import_country",
        "/api/datasets/37/substations_customers_info",
        "/api/datasets/37/substations_load_info",
        "/api/datasets/37/substations_overload_transformer",
        "/api/datasets/37/substations_transformer_info",
        "/api/datasets/37/load_forecast",
        "/api/datasets/37/rational_struct_base",
    ]


def test_list_database_versions_shape(monkeypatch):
    rows = [
        SimpleNamespace(
            id=7, version_number="ГС-2026", description="desc", is_active=True
        ),
        SimpleNamespace(
            id=3, version_number="ГС-2024", description=None, is_active=False
        ),
    ]

    class _Q:
        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return rows

    class _Session:
        def query(self, model):
            return _Q()

    monkeypatch.setattr(versions_svc.db, "session", _Session())
    monkeypatch.setattr(
        "app.api.services.general_info_exchange_services.planning_meta_for_version",
        lambda version_id, version_number: {
            "planning_scheme": "gs",
            "current_year": 2024,
            "period_start": 2024,
            "period_end": 2042,
        },
    )
    payload = versions_svc.list_database_versions()
    assert payload["rows"][0]["database_version"] == 7
    assert payload["rows"][0]["version_number"] == "ГС-2026"
    assert payload["rows"][0]["planning_scheme"] == "gs"
    assert payload["rows"][0]["period_end"] == 2042
    assert "is_active" not in payload["rows"][0]
    assert payload["rows"][1]["description"] == ""
    assert payload["rows"][1]["database_version"] == 3


def test_get_database_version_ok_and_missing(monkeypatch):
    row = SimpleNamespace(
        id=7, version_number="ГС-2026", description="x", is_active=True
    )

    class _Session:
        def get(self, model, pk):
            return row if int(pk) == 7 else None

    monkeypatch.setattr(versions_svc.db, "session", _Session())
    monkeypatch.setattr(
        "app.api.services.general_info_exchange_services.planning_meta_for_version",
        lambda version_id, version_number: {
            "planning_scheme": "gs",
            "current_year": 2024,
            "period_start": 2024,
            "period_end": 2042,
        },
    )
    assert versions_svc.get_database_version(7)["database_version"] == 7
    with pytest.raises(versions_svc.UnknownDatabaseVersionError):
        versions_svc.get_database_version(99)


def test_output_document_groups_enable_only_public_api():
    from app.api.services.output_documents_catalog import build_output_document_groups

    groups = build_output_document_groups()
    files = [item for group in groups for item in group["files"]]
    by_name = {item["dataset"]: item for item in files}

    assert [group["title"] for group in groups] == [
        "common",
        "gs_sipr",
        "rational_struct_calc",
        "rational_struct_report",
    ]
    assert [group["column"] for group in groups] == [1, 2, 3, 3]
    assert by_name["database_versions"]["enabled"] is True
    assert by_name["general_info"]["enabled"] is True
    assert by_name["gentypes_info"]["enabled"] is True
    assert by_name["generation_stations"]["enabled"] is True
    assert by_name["generation_machines"]["enabled"] is True
    assert by_name["daymonth_info"]["enabled"] is True
    assert by_name["line_capital_investments"]["enabled"] is True
    assert by_name["month_info"]["enabled"] is True
    assert by_name["newlines_building"]["enabled"] is True
    assert by_name["power_energy_export_import_country"]["enabled"] is True
    assert by_name["substations_customers_info"]["enabled"] is True
    assert by_name["substations_load_info"]["enabled"] is True
    assert by_name["substations_overload_transformer"]["enabled"] is True
    assert by_name["substations_transformer_info"]["enabled"] is True
    assert by_name["load_forecast"]["enabled"] is True
    assert by_name["rational_struct_import_to_java"]["enabled"] is False
    assert by_name["rational_struct_base"]["enabled"] is True
    assert by_name["rational_struct_base"]["filename"] == "rational_struct_base.json"
    assert by_name["database_versions"]["filename"] == "database_versions.json"
    assert by_name["month_info"]["filename"] == "month_info.json"
    assert by_name["newlines_building"]["filename"] == "newlines_building.json"
    assert by_name["power_energy_export_import_country"]["filename"] == (
        "power_energy_export_import_country.json"
    )
    assert by_name["substations_overload_transformer"]["filename"] == (
        "substations_overload_transformer.json"
    )
