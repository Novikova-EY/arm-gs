# -*- coding: utf-8 -*-
"""Администрирование вариантов периметра и привязок к сущностям."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.power_demand.forms.demand_parameter_forms import EmptyCSRFForm
from app.power_demand.services import perimeter_variant_admin_services as pvas

perimeter_variant_bp = Blueprint("perimeter_variant_bp", __name__)


def _require_admin():
    if not getattr(current_user, "is_admin", False):
        flash("Доступ только для администратора.", "danger")
        return False
    return True


@perimeter_variant_bp.route("/perimeter_variants/", methods=["GET", "POST"])
@login_required
def perimeter_variants_admin():
    if not _require_admin():
        return redirect(url_for("start.index"))

    form = EmptyCSRFForm()
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Ошибка CSRF.", "danger")
            return redirect(url_for("perimeter_variant_bp.perimeter_variants_admin"))

        action = (request.form.get("action") or "").strip()
        try:
            if action == "save_variants":
                saved, deleted = pvas.save_variants_from_form(request.form)
                flash(f"Варианты: сохранено {saved}, удалено {deleted}.", "success")
            elif action == "add_binding":
                pvas.add_binding_from_form(request.form)
                flash("Привязка добавлена.", "success")
            elif action == "delete_bindings":
                ids = [int(x) for x in request.form.getlist("binding_delete[]") if str(x).strip().isdigit()]
                n = pvas.delete_bindings(ids)
                flash(f"Удалено привязок: {n}.", "success")
            else:
                flash("Неизвестное действие.", "warning")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash(f"Ошибка: {e}", "danger")
        return redirect(url_for("perimeter_variant_bp.perimeter_variants_admin"))

    ctx = pvas.admin_page_context()
    ctx["form"] = form
    return render_template("perimeter_variants/perimeter_variants_admin.html", **ctx)
