# -*- coding: utf-8 -*-
"""JSON-наборы (legacy-пути под /generation/stations/api/...).

Канон: GET /api/datasets/<database_version>/<dataset>
и GET /api/database_versions.
"""

from flask import jsonify, request

from app.api.services.database_versions_api_services import (
    UnknownDatabaseVersionError,
)
from app.api.services.exchange_api_services import (
    UnknownDatasetError,
    list_exchange_datasets,
    list_exchange_datasets_for_version,
    load_exchange_dataset,
)
from app.generation.routes.stations import station_bp


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


@station_bp.route("/api/datasets", methods=["GET"])
def list_generation_exchange_datasets():
    """Список имён наборов (legacy). Канон: GET /api/datasets."""
    return jsonify(list_exchange_datasets())


@station_bp.route("/api/datasets/<int:database_version>", methods=["GET"])
def get_generation_exchange_datasets_by_version(database_version: int):
    """
    Legacy-алиас: каталог наборов для версии БД.

    Канон: GET /api/datasets/<database_version>
    """
    try:
        return jsonify(list_exchange_datasets_for_version(database_version))
    except UnknownDatabaseVersionError:
        return jsonify(
            {
                "error": "unknown_database_version",
                "database_version": database_version,
            }
        ), 404


@station_bp.route(
    "/api/datasets/<int:database_version>/<dataset>", methods=["GET"]
)
def get_generation_exchange_dataset_by_version(database_version: int, dataset: str):
    """
    Legacy-алиас одного набора.

    Канон: GET /api/datasets/<database_version>/<dataset>
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
        return jsonify(
            {
                "error": "unknown_database_version",
                "database_version": database_version,
            }
        ), 404
    except UnknownDatasetError:
        return jsonify(
            {
                "error": "unknown_dataset",
                "database_version": database_version,
                "dataset": dataset,
                "datasets": list_exchange_datasets()["datasets"],
            }
        ), 404
