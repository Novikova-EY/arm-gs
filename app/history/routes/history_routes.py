# -*- coding: utf-8 -*-
"""
Маршруты визуализации исторических данных.
"""
from flask import Blueprint, render_template, request, abort
from flask_login import login_required

from app.history.services.history_services import (
    build_history_context,
    build_refdata_history_context,
    get_refdata_sections,
    REFDATA_LABELS,
)

history_bp = Blueprint("history_bp", __name__)


@history_bp.route("/", methods=["GET"])
@login_required
def history_index():
    context = build_history_context(request.args)
    return render_template("history/history.html", **context)


@history_bp.route("/refdata", methods=["GET"])
@login_required
def history_refdata_index():
    return render_template(
        "history/refdata/index.html",
        sections=get_refdata_sections(),
    )


@history_bp.route("/refdata/<entity_type>", methods=["GET"])
@login_required
def history_refdata_entity(entity_type: str):
    if entity_type not in REFDATA_LABELS:
        abort(404)
    context = build_refdata_history_context(entity_type, request.args)
    return render_template("history/refdata/entity_history.html", **context)
