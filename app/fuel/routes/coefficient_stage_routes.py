# -*- coding: utf-8 -*-
from decimal import Decimal, InvalidOperation

from flask import flash, request
from flask_login import login_required

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    FuelCoefficientCalculationService,
)
from app.fuel.routes.equipment_group_fuel_batch_ui_routes import _csrf_ok
from app.fuel.routes.fuel_calculation_common import redirect_back_after_post
from app.fuel.routes import fuel_bp


def _ph_for_psu_hd_column(summary: DistributionCoefficientSummary | None):
    """
    PH = hd / bh (как в этапе «Коэфф») — показатель для ячейки строки ПСУ под столбцом «hd».
    В сводке хранится поле ph; иначе восстанавливаем из hd и bh.
    """
    if summary is None:
        return None
    ph = getattr(summary, "ph", None)
    if ph is not None:
        return ph
    hd = getattr(summary, "hd", None)
    bh = getattr(summary, "bh", None)
    if hd is None or bh is None:
        return None
    try:
        bh_d = Decimal(str(bh))
        if bh_d <= 0:
            return None
        return Decimal(str(hd)) / bh_d
    except (InvalidOperation, ValueError, TypeError):
        return None


def coeff_tech_type_table(summary: DistributionCoefficientSummary | None):
    """
    Строки ПСУ / ГТУ / ПГУ для второй таблицы этапа «Коэфф».
    N_нов — cnustn*; в колонке «ЧЧИУМ» вводятся hnps/hngt/hnpg; K_нов — knps/kngt/knpg (hn/ch после расчёта).
    """
    if summary is None:
        return []
    specs = [
        ("ПСУ", summary.cnustnps, summary.hnps, summary.knps, "hnps"),
        ("ГТУ", summary.cnustngt, summary.hngt, summary.kngt, "hngt"),
        ("ПГУ", summary.cnustnpg, summary.hnpg, summary.knpg, "hnpg"),
    ]
    ph_psu = _ph_for_psu_hd_column(summary)
    out = []
    for label, n, h, k, h_field in specs:
        out.append(
            {
                "label": label,
                "n": n,
                "h": h,
                "k": k,
                "h_field": h_field,
                "hd_col_ph": ph_psu if label == "ПСУ" else None,
            }
        )
    return out


def get_coeff_tech_aggregate_row(summary):
    """
    Строка сразу под шапкой второй таблицы «Коэфф» (как в Access): cnustn, hd, kn.
    Далее идут строки ПСУ / ГТУ / ПГУ с разбивкой по типам.
    """
    if summary is None:
        return None
    return {
        "cnustn": getattr(summary, "cnustn", None),
        "hd": getattr(summary, "hd", None),
        "kn": getattr(summary, "kn", None),
    }


def parse_e_eraspred(raw) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation as e:
        raise ValueError("Некорректное числовое значение поля «Ераспред».") from e


@fuel_bp.route("/calculation/run_coeff", methods=["POST"])
@login_required
def run_coeff_stage():
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
            row.e = parse_e_eraspred(request.form.get("e"))
            db.session.add(row)
            db.session.flush()

        res = FuelCoefficientCalculationService().run_for_distribution_parameter(dp_id)
        flash(
            f"Этап «Коэфф» выполнен. Групп: {res.total_groups}, "
            f"обновлено строк fuel_param: {res.updated_fuel_rows}.",
            "success",
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка этапа «Коэфф»: {e}", "danger")

    return redirect_back_after_post()


_ALLOWED_TECH_H_FIELDS = frozenset({"hnps", "hngt", "hnpg"})


def _parse_optional_decimal(raw) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        return Decimal(s.replace(",", "."))
    except InvalidOperation as e:
        raise ValueError("Некорректное числовое значение hn.") from e


@fuel_bp.route("/calculation/update_tech_hn", methods=["POST"])
@login_required
def fuel_calculation_update_tech_hn():
    """Сохранение hnps/hngt/hnpg из столбца «ЧЧИУМ» и пересчёт этапа «Коэфф» (kn = hn/ch)."""
    if not _csrf_ok():
        flash("Недействительный CSRF-токен.", "danger")
        return redirect_back_after_post()

    dp_id = request.form.get("distribution_parameter_id", type=int)
    h_field = (request.form.get("h_field") or "").strip()
    if not dp_id or h_field not in _ALLOWED_TECH_H_FIELDS:
        flash("Некорректные данные формы (параметр распределения или поле hn).", "danger")
        return redirect_back_after_post()

    try:
        val = _parse_optional_decimal(request.form.get("h_value"))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect_back_after_post()

    try:
        row = db.session.get(DistributionParameter, dp_id)
        if row is None:
            flash(f"Не найден параметр распределения id={dp_id}.", "danger")
            return redirect_back_after_post()

        setattr(row, h_field, val)
        db.session.add(row)
        db.session.flush()

        res = FuelCoefficientCalculationService().run_for_distribution_parameter(dp_id)
        flash(
            f"Сохранено поле {h_field}. Этап «Коэфф» обновлён: групп {res.total_groups}, "
            f"строк топлива {res.updated_fuel_rows}.",
            "success",
        )
    except ValueError as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при сохранении hn и пересчёте «Коэфф»: {e}", "danger")

    return redirect_back_after_post()
