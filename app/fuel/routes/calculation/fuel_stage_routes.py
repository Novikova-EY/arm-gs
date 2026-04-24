# -*- coding: utf-8 -*-
"""Этап «Топливо»: POST /fuel/calculation/run_fuel."""
from flask import flash, request
from flask_login import login_required

from app.extensions import db
from app.fuel.services.calculation.fuel.fuel_batch_stage import run_fuel_stage_batch
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import redirect_back_after_post
from app.fuel.routes import fuel_bp


@fuel_bp.route("/calculation/run_fuel", methods=["POST"])
@login_required
def run_fuel_stage():
    if not _csrf_ok():
        flash("Недействительный CSRF-токен.", "danger")
        return redirect_back_after_post()

    dp_id = request.form.get("distribution_parameter_id", type=int)
    if not dp_id:
        flash("Не указан параметр распределения (distribution_parameter_id).", "danger")
        return redirect_back_after_post()

    try:
        run = run_fuel_stage_batch(dp_id)
        br = run.batch_result
        n_ok = br.success_count if br else 0
        n_err = br.error_count if br else 0
        flash(
            f"Этап «Топливо»: групп в фильтре {len(run.selected_group_ids)}; "
            f"успешно {n_ok}, ошибок {n_err}; "
            f"ΣB={run.total_fuel_b:.1f}.",
            "success" if n_err == 0 else "warning",
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка этапа «Топливо»: {e}", "danger")

    return redirect_back_after_post()
