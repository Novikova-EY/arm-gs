# -*- coding: utf-8 -*-
"""JSON-наборы (legacy-пути под /generation/stations/api/...).

Канон: GET /api/datasets/<database_version>
и GET /api/database_versions.
"""

from flask import jsonify, request

from app.api.services.exchange_api_services import (
    list_exchange_datasets,
    load_all_exchange_datasets,
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
    Legacy-алиас: все наборы для версии БД.

    Канон: GET /api/datasets/<database_version>
    """
    return jsonify(
        load_all_exchange_datasets(
            version_id=database_version,
            **_year_kwargs(),
        )
    )
