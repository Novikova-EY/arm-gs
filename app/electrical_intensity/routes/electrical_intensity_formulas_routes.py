# -*- coding: utf-8 -*-
"""Страница текстов формул электроёмкости: /electrical_intensity/formulas/."""

from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.electrical_intensity.routes.electrical_intensity_root_bp import (
    electrical_intensity_root_bp,
)
from app.electrical_intensity.services.formula_text.long_term_consumption_formula_text_services import (
    list_formulas_for_admin,
    reset_formula_text_override,
    save_formula_text_override,
)


def _render_electrical_intensity_formulas_page():
    if not getattr(current_user, "has_admin", False):
        flash("Недостаточно прав для редактирования текстов формул.", "danger")
        return redirect(url_for("long_term_consumption_bp.electrical_intensity_start"))
    return render_template(
        "electrical_intensity/electrical_intensity_formulas.html",
        page_title="Тексты формул для модуля «Электроемкость»",
        formula_rows=list_formulas_for_admin(),
        has_active_summary_filters=False,
    )


@electrical_intensity_root_bp.route("/formulas/")
@login_required
def electrical_intensity_formulas():
    return _render_electrical_intensity_formulas_page()


@electrical_intensity_root_bp.route("/formulas/save", methods=["POST"])
@login_required
def electrical_intensity_formulas_save():
    if not getattr(current_user, "has_admin", False):
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


@electrical_intensity_root_bp.route("/formulas/reset", methods=["POST"])
@login_required
def electrical_intensity_formulas_reset():
    if not getattr(current_user, "has_admin", False):
        return jsonify(ok=False, error="Недостаточно прав"), 403
    data = request.get_json(silent=True) or {}
    key = str(data.get("formula_key") or "").strip()
    if not key:
        return jsonify(ok=False, error="Не указан ключ формулы."), 400
    reset_formula_text_override(key)
    db.session.commit()
    return jsonify(ok=True)
