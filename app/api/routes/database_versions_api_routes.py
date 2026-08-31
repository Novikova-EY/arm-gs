# -*- coding: utf-8 -*-
"""Независимый JSON-API версий БД АРМ.

GET /api/database_versions — список версий для выбора
GET /api/database_versions/<id> — сведения по одной версии

Клиент выбирает id и дальше запрашивает данные:
GET /api/datasets/<database_version>
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from app.api.services.database_versions_api_services import (
    UnknownDatabaseVersionError,
    get_database_version,
    list_database_versions,
)

database_versions_api_bp = Blueprint("database_versions_api_bp", __name__)


@database_versions_api_bp.route("/database_versions", methods=["GET"])
def api_list_database_versions():
    """
    Список версий БД АРМ.

    Пример: GET /api/database_versions
    """
    return jsonify(list_database_versions())


@database_versions_api_bp.route("/database_versions/<int:version_id>", methods=["GET"])
def api_get_database_version(version_id: int):
    """
    Сведения по одной версии БД.

    Пример: GET /api/database_versions/7
    """
    try:
        return jsonify(get_database_version(version_id))
    except UnknownDatabaseVersionError:
        return jsonify(
            {
                "error": "unknown_database_version",
                "database_version": version_id,
            }
        ), 404
