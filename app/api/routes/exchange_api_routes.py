# -*- coding: utf-8 -*-
"""Единый JSON-API наборов datasets (без версий БД).

GET /api/datasets — список имён наборов (справка)
GET /api/datasets/<database_version> — все наборы для версии (только id)

Версии БД: GET /api/database_versions (отдельный blueprint).
"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.api.services.database_versions_api_services import (
    UnknownDatabaseVersionError,
)
from app.api.services.exchange_api_services import (
    list_exchange_datasets,
    load_all_exchange_datasets,
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


@exchange_api_bp.route("/datasets", methods=["GET"])
def get_datasets_catalog():
    """
    Справка: какие наборы входят в выгрузку по id версии.
    Лёгкий ответ — открывается в браузере.

    GET /api/datasets
    """
    return jsonify(list_exchange_datasets())


@exchange_api_bp.route("/datasets/<int:database_version>", methods=["GET"])
def get_datasets_by_version(database_version: int):
    """
    Единый API: все JSON-наборы для выбранной версии БД.

    GET /api/datasets/46
    Query (опционально): year, start_year, end_year.

    Полная выгрузка (без фильтра лет) — файл на скачивание.
    С фильтром year/start_year/end_year — JSON в браузере.
    """
    years = _year_kwargs()
    try:
        payload = load_all_exchange_datasets(
            version_id=database_version,
            **years,
        )
    except UnknownDatabaseVersionError:
        return jsonify(
            {
                "error": "unknown_database_version",
                "database_version": database_version,
            }
        ), 404
    response = jsonify(payload)
    # Тяжёлый полный срез — скачивание; узкий по годам — смотреть в браузере.
    is_full_dump = (
        years["year"] is None
        and years["start_year"] is None
        and years["end_year"] is None
    )
    if is_full_dump:
        response.headers["Content-Disposition"] = (
            f'attachment; filename="arm_gs_datasets_{database_version}.json"'
        )
    return response
