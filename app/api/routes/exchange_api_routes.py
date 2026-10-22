# -*- coding: utf-8 -*-
"""JSON-API наборов datasets: отдельный набор – отдельный URL.

GET /api/config – discovery (первый запрос внешнего клиента)
GET /api/datasets – список имён наборов (справка)
GET /api/datasets/<database_version> – каталог наборов выбранной версии
GET /api/datasets/<database_version>/<dataset> – один JSON-набор
GET /api/duplicate_identity_uuids – план разведения дублирующих UUID
GET /api/duplicate_identity_uuids/<database_version> – тот же план по версии

Версии БД: GET /api/database_versions (отдельный blueprint).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.services.database_versions_api_services import (
    UnknownDatabaseVersionError,
    ensure_database_version_exists,
)
from app.api.services.duplicate_identity_uuid_api_services import (
    load_duplicate_identity_uuids_dataset,
)
from app.api.services.exchange_api_services import (
    UnknownDatasetError,
    build_exchange_config,
    list_exchange_datasets,
    list_exchange_datasets_for_version,
    load_exchange_dataset,
)

exchange_api_bp = Blueprint("exchange_api_bp", __name__)


def _int_arg(*names: str) -> int | None:
    for name in names:
        raw = request.args.get(name)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    return None


def _year_kwargs() -> dict:
    return {
        "year": _int_arg("year"),
        "start_year": _int_arg("start_year"),
        "end_year": _int_arg("end_year"),
    }


def _unknown_version_response(database_version: int):
    return jsonify(
        {
            "error": "unknown_database_version",
            "database_version": database_version,
        }
    ), 404


def _unknown_dataset_response(database_version: int, dataset: str):
    return jsonify(
        {
            "error": "unknown_dataset",
            "database_version": database_version,
            "dataset": dataset,
            "datasets": list_exchange_datasets()["datasets"],
        }
    ), 404


@exchange_api_bp.route("/config", methods=["GET"])
def get_exchange_config():
    """
    Discovery для внешнего клиента (первый запрос в сторону АРМ).

    GET /api/config
    """
    base_url = request.url_root.rstrip("/")
    return jsonify(build_exchange_config(base_url=base_url))


@exchange_api_bp.route("/datasets", methods=["GET"])
def get_datasets_catalog():
    """
    Справка: какие наборы можно запросить по id версии.
    Лёгкий ответ – открывается в браузере.

    GET /api/datasets
    """
    return jsonify(list_exchange_datasets())


@exchange_api_bp.route("/datasets/<int:database_version>", methods=["GET"])
def get_datasets_by_version(database_version: int):
    """
    Каталог наборов выбранной версии (без данных).

    GET /api/datasets/37
    """
    try:
        return jsonify(list_exchange_datasets_for_version(database_version))
    except UnknownDatabaseVersionError:
        return _unknown_version_response(database_version)


@exchange_api_bp.route(
    "/datasets/<int:database_version>/<dataset>", methods=["GET"]
)
def get_dataset_by_version(database_version: int, dataset: str):
    """
    Один JSON-набор для выбранной версии БД.

    GET /api/datasets/37/gentypes_info
    Query (опционально): year, start_year, end_year.
    """
    try:
        return jsonify(
            load_exchange_dataset(
                dataset,
                version_id=database_version,
                **_year_kwargs(),
            )
        )
    except UnknownDatabaseVersionError:
        return _unknown_version_response(database_version)
    except UnknownDatasetError:
        return _unknown_dataset_response(database_version, dataset)


def _want_refdata() -> bool:
    raw = (request.args.get("refdata") or "").strip().lower()
    return raw in {"1", "true", "yes"}


@exchange_api_bp.route("/duplicate_identity_uuids", methods=["GET"])
def get_duplicate_identity_uuids():
    """
    План скрипта fix_duplicate_identity_uuids.py (dry-run, без записи).

    GET /api/duplicate_identity_uuids
    GET /api/duplicate_identity_uuids?refdata=1
    """
    return jsonify(
        load_duplicate_identity_uuids_dataset(include_refdata=_want_refdata())
    )


@exchange_api_bp.route(
    "/duplicate_identity_uuids/<int:database_version>", methods=["GET"]
)
def get_duplicate_identity_uuids_by_version(database_version: int):
    """
    Тот же план, только строки выбранной версии БД.

    GET /api/duplicate_identity_uuids/37
    """
    try:
        vid = ensure_database_version_exists(database_version)
    except UnknownDatabaseVersionError:
        return _unknown_version_response(database_version)
    return jsonify(
        load_duplicate_identity_uuids_dataset(
            version_id=vid,
            include_refdata=_want_refdata(),
        )
    )
