# -*- coding: utf-8 -*-
"""Этап «Распред»: POST /fuel/calculation/run_distribution."""
from decimal import Decimal, InvalidOperation

from flask import flash, request, session
from flask_login import login_required

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
)
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import (
    FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY,
    redirect_back_after_post,
)
from app.fuel.routes import fuel_bp


def _parse_distribution_e(raw) -> Decimal | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        return Decimal(text.replace(",", "."))
    except InvalidOperation as e:
        raise ValueError("Некорректное числовое значение поля «Ераспред».") from e


@fuel_bp.route("/calculation/run_distribution", methods=["POST"])
@login_required
def run_distribution_stage():
    if not _csrf_ok():
        flash("Недействительный CSRF-токен.", "danger")
        return redirect_back_after_post()

    dp_id = request.form.get("distribution_parameter_id", type=int)
    if not dp_id:
        flash("Не указан параметр распределения (distribution_parameter_id).", "danger")
        return redirect_back_after_post()

    try:
        row = db.session.get(DistributionParameter, dp_id)
        if row is None:
            flash(f"Не найден параметр распределения id={dp_id}.", "danger")
            return redirect_back_after_post()

        if "e" in request.form:
            row.e = _parse_distribution_e(request.form.get("e"))
            db.session.add(row)
            db.session.flush()

        e_target = row.e

        run = DistributionStageService(session=db.session).run_for_distribution_parameter(
            distribution_parameter_id=dp_id,
            commit=True,
        )
        session[FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY] = {
            "distribution_parameter_id": run.distribution_parameter_id,
            "distribution_name": run.distribution_name or "",
            "year_number": run.year_number,
            "e_target": str(e_target) if e_target is not None else None,
            "selected_group_count": len(run.selected_group_ids),
            "processed_group_count": len(run.processed_group_ids),
            "skipped_group_count": len(run.skipped_group_ids),
            "updated_fuel_rows": run.updated_fuel_rows,
            "iterations": run.iterations,
            "total_distributed_e": str(run.total_distributed_e),
            "final_k": str(run.final_k) if run.final_k is not None else None,
            "final_kn": str(run.final_kn) if run.final_kn is not None else None,
        }
        session.modified = True
        flash(
            f"Этап «Распред»: групп в фильтре {len(run.selected_group_ids)}; "
            f"обновлено строк топлива {run.updated_fuel_rows}; "
            f"итераций {run.iterations}; ΣE={run.total_distributed_e:.1f}.",
            "success" if not run.skipped_group_ids else "warning",
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка этапа «Распред»: {e}", "danger")

    return redirect_back_after_post()
