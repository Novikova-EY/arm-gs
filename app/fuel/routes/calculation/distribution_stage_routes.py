# -*- coding: utf-8 -*-
"""Этап «Распред»: POST /fuel/calculation/run_distribution."""
from decimal import Decimal, InvalidOperation

from flask import flash, request, session
from flask_login import login_required
from sqlalchemy.orm import joinedload

from app.common.services.help_services import parse_decimal_from_display
from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    DistributionStageService,
    d0,
)
from app.fuel.routes.coefficient_stage_routes import _store_coeff_last_run_in_session
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import (
    FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY,
    redirect_back_after_post,
)
from app.fuel.routes import fuel_bp


def _parse_distribution_e(raw) -> Decimal | None:
    try:
        return parse_decimal_from_display(raw)
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
        row = db.session.get(
            DistributionParameter,
            dp_id,
            options=[
                joinedload(DistributionParameter.union_energy_system),
                joinedload(DistributionParameter.year),
                joinedload(DistributionParameter.base_year),
            ],
        )
        if row is None:
            flash(f"Не найден параметр распределения id={dp_id}.", "danger")
            return redirect_back_after_post()

        if "e" in request.form:
            row.e = _parse_distribution_e(request.form.get("e"))
            db.session.add(row)
            db.session.flush()

        e_target = row.e

        apply_restrictions = str(request.form.get("apply_restrictions") or "").strip() in (
            "1",
            "true",
            "on",
            "yes",
        )

        run = DistributionStageService(session=db.session).run_for_distribution_parameter(
            distribution_parameter_id=dp_id,
            apply_restrictions=apply_restrictions,
            commit=True,
        )
        if run.coeff_run is not None:
            # «Распред» всегда пересчитывает «Коэфф» — показываем тот же блок результата.
            _store_coeff_last_run_in_session(
                row, run.coeff_run, trigger="run_distribution"
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
            "restriction_outer_iterations": run.restriction_outer_iterations,
            "apply_restrictions": apply_restrictions,
            "total_distributed_e": str(run.total_distributed_e),
            "final_k": str(run.final_k) if run.final_k is not None else None,
            "final_kn": str(run.final_kn) if run.final_kn is not None else None,
        }
        session.modified = True
        restr_note = (
            f"; ограничения учтены (внешних итераций kobl: {run.restriction_outer_iterations})"
            if apply_restrictions
            else "; ограничения не учитывались"
        )
        e_tgt = d0(e_target) if e_target is not None else Decimal("0")
        delta_e = abs(e_tgt - d0(run.total_distributed_e))
        converged = e_tgt > 0 and delta_e < Decimal("0.3")
        flash_level = "success"
        if run.skipped_group_ids or not converged:
            flash_level = "warning"
        converge_note = ""
        if e_tgt > 0 and not converged:
            converge_note = (
                f"; не сошлось с Ераспред={e_tgt:.1f} "
                f"(Δ={delta_e:.1f}, допуск 0.3) — «Топливо» будет недоступно"
            )
        flash(
            f"Этап «Распред»: групп в фильтре {len(run.selected_group_ids)}; "
            f"обновлено строк топлива {run.updated_fuel_rows}; "
            f"итераций подбора k {run.iterations}"
            f"{restr_note}; ΣE={run.total_distributed_e:.1f}"
            f"{converge_note}.",
            flash_level,
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка этапа «Распред»: {e}", "danger")

    return redirect_back_after_post()
