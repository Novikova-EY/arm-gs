from config import Config
from . import station_bp
from app.extensions import db
from flask import render_template, request, session, flash, redirect, url_for
from flask_login import login_required
from app.auth.routes import roles_required
from app.generation.services.machine_services.machine_services import (
    handle_machine_get,
    handle_machine_post, 
    handle_pgu_machine_get,
    handle_pgu_machine_post, 
    _fill_pgu_machines_form_choices,
    to_decimal
)
from app.generation.services.station_services.station_services import (
    get_machine_by_id,
    get_station_by_id, 
    recalculate_station_power,
)
from app.generation.services.station_services.help_services import (
    convert_to_date,
    rounded_decimal
)
from app.generation.services.station_services.help_services import (
    get_year_features,
)


@station_bp.route("/machine_details/<int:station_id>/<int:machine_id>", methods=["GET", "POST"])
@login_required
def machine_details(station_id, machine_id):
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 1, type=int)

    if request.method == "POST":
        return handle_machine_post(
            station_id=station_id,
            machine_id=machine_id,
            form_data=request.form,
            user=user,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
        )
    else:
        result = handle_machine_get(station_id, machine_id, start_year, end_year, rounding_digits)
        return render_template(
            "stations/machine_details.html",
            main_form=result['main_form'],
            advanced_form=result['advanced_form'],
            pgu_machines_form=result['pgu_machines_form'],
            pgu_machines=result['pgu_machines'],
            station=result['station'],
            machine=result['machine'],
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            year_features=result['year_features']
        )

@station_bp.route("/pgu_machine_details/<int:station_id>/<int:machine_id>/<int:pgu_machine_id>", methods=["GET", "POST"])
@login_required
def pgu_machine_details(station_id, machine_id, pgu_machine_id):
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)

    if request.method == "POST":
        return handle_pgu_machine_post(
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
            form_data=request.form,
            user=user,
            start_year=start_year,
            end_year=end_year
        )

    else:
        result = handle_pgu_machine_get(
            station_id=station_id,
            machine_id=machine_id,
            pgu_machine_id=pgu_machine_id,
            start_year=start_year,
            end_year=end_year
        )

        return render_template(
            "stations/pgu_machine_details.html",
            station=result['station'],
            parent_machine=result['parent_machine'],
            pgu_form=result['pgu_form'],
            start_year=result['start_year'],
            end_year=result['end_year'],
            pgu_machine_id=result['pgu_machine_id'],
            year_features=result['year_features']
        )