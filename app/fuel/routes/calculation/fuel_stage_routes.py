# -*- coding: utf-8 -*-
"""Этап «Топливо»: POST /fuel/calculation/run_fuel."""
from flask import flash, request, session
from flask_login import login_required

from app.extensions import db
from app.fuel.services.calculation.fuel.fuel_batch_stage import run_fuel_stage_batch
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import (
    FUEL_STAGE_LAST_RUN_SESSION_KEY,
    redirect_back_after_post,
)
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
        n_calculated = 0
        if br:
            n_calculated = sum(1 for item in br.items if item.success and item.calculated)
        readiness = run.readiness
        session[FUEL_STAGE_LAST_RUN_SESSION_KEY] = {
            "distribution_parameter_id": run.distribution_parameter_id,
            "distribution_name": run.distribution_name or "",
            "year_number": run.year_number,
            "selected_group_count": len(run.selected_group_ids),
            "success_count": n_ok,
            "error_count": n_err,
            "calculated_count": n_calculated,
            "total_fuel_b": str(run.total_fuel_b) if run.total_fuel_b is not None else None,
            "e_target": str(readiness.e_target) if readiness and readiness.e_target is not None else None,
            "sum_e_cyear": (
                str(readiness.sum_e_cyear) if readiness and readiness.sum_e_cyear is not None else None
            ),
            "delta_e": str(readiness.delta_e) if readiness and readiness.delta_e is not None else None,
        }
        session.modified = True
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
