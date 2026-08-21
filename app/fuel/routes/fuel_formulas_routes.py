# -*- coding: utf-8 -*-
"""Страница текстов формул модуля «Топливо»: /fuel/formulas/."""

from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.fuel.routes import fuel_bp
from app.fuel.services.formula_text.fuel_formula_text_services import (
    list_formulas_for_admin,
    reset_formula_text_override,
    save_formula_text_override,
)


def _require_fuel_formula_admin():
    if not getattr(current_user, "is_admin", False):
        return False
    return True


@fuel_bp.route("/formulas/")
@login_required
def fuel_formulas():
    if not _require_fuel_formula_admin():
        flash("Недостаточно прав для редактирования текстов формул.", "danger")
        return redirect(url_for("fuel_bp.fuel_start"))
    return render_template(
        "fuel/fuel_formulas.html",
        page_title="Тексты формул для модуля «Топливо»",
        formula_rows=list_formulas_for_admin(),
    )


@fuel_bp.route("/formulas/save", methods=["POST"])
@login_required
def fuel_formulas_save():
    if not _require_fuel_formula_admin():
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    try:
        save_formula_text_override(
            formula_key=str(data.get("formula_key") or ""),
            formula_text=str(data.get("formula_text") or ""),
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True)


@fuel_bp.route("/formulas/reset", methods=["POST"])
@login_required
def fuel_formulas_reset():
    if not _require_fuel_formula_admin():
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    key = str(data.get("formula_key") or "").strip()
    if not key:
        return jsonify(ok=False, error="Не указан ключ формулы."), 400
    reset_formula_text_override(key)
    db.session.commit()
    return jsonify(ok=True)
