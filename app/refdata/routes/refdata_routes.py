from datetime import datetime

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from . import refdata_bp
from app.auth.routes import roles_required
from app.common.services.database_version_services import get_current_version
from app.refdata.services.year_management_services import (
    get_current_year_info,
    update_current_year,
    update_sipr_dates,
)
from config import Config

@refdata_bp.errorhandler(403)
def forbidden(error):
    return render_template('errors/forbidden.html'), 403

@refdata_bp.route("/")
@login_required
def refdata():
    """Страница справочников, в т.ч. блок управления годами/СиПР."""
    version_id = get_current_version()

    if version_id:
        year_info = get_current_year_info(version_id)
    else:
        # Если версия не выбрана – по ТЗ показываем нули по годам
        year_info = {
            "current_year": 0,
            "sipr_start": 0,
            "sipr_end": 0,
            "date_sipr_start": None,
            "date_sipr_end": None,
        }

    system_year = datetime.now().year
    min_year = system_year - 3
    max_year = system_year + 3
    year_select_years = list(range(min_year, max_year + 1))

    return render_template(
        "refdata/refdata.html",
        year_info=year_info,
        year_select_years=year_select_years,
        general_scheme_end_year=Config.END_YEAR_GENERAL_SCHEME,
    )


@refdata_bp.route("/update_current_year", methods=["POST"])
@login_required
@roles_required(["admin"])
def update_current_year_refdata():
    """Обновление текущего года из формы на странице справочников."""
    version_id = get_current_version()
    if not version_id:
        flash("Текущая версия БД не установлена", "danger")
        return redirect(url_for("refdata_bp.refdata"))

    try:
        year = int(request.form.get("current_year", 0))
    except (TypeError, ValueError):
        flash("Некорректное значение года", "danger")
        return redirect(url_for("refdata_bp.refdata"))

    if year < 2000 or year > 2100:
        flash("Некорректное значение года", "danger")
        return redirect(url_for("refdata_bp.refdata"))

    success, message = update_current_year(version_id, year, current_user)
    flash(message, "success" if success else "danger")

    return redirect(url_for("refdata_bp.refdata"))


@refdata_bp.route("/update_sipr_dates", methods=["POST"])
@login_required
@roles_required(["admin"])
def update_sipr_dates_refdata():
    """Обновление дат СиПР из формы на странице справочников."""
    version_id = get_current_version()
    if not version_id:
        flash("Текущая версия БД не установлена", "danger")
        return redirect(url_for("refdata_bp.refdata"))

    date_sipr_start = request.form.get("date_sipr_start") or None
    date_sipr_end = request.form.get("date_sipr_end") or None

    success, message = update_sipr_dates(
        version_id, date_sipr_start, date_sipr_end, current_user
    )
    flash(message, "success" if success else "danger")

    return redirect(url_for("refdata_bp.refdata"))