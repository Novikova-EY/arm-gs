from config import Config
from app.generation.routes.stations import station_bp
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
from app.common.services.help_services import (
    convert_to_date,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)
from app.logs.models.log_model import Log
from sqlalchemy import or_


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
        machine_logs = (
            db.session.query(Log)
            .filter(
                or_(
                    Log.action.ilike(f"%агрегат%"),
                    Log.details.ilike(f"%агрегат%"),
                    Log.details.ilike(f"%machine_id={machine_id}%"),
                    Log.details.ilike(f"%агрегата №{result['machine'].machine_number}%")
                )
            )
            .order_by(Log.timestamp.desc())
            .limit(200)
            .all()
        )
        return render_template(
            "generation/stations/machine_details.html",
            main_form=result['main_form'],
            advanced_form=result['advanced_form'],
            pgu_machines_form=result['pgu_machines_form'],
            pgu_machines=result['pgu_machines'],
            station=result['station'],
            machine=result['machine'],
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            year_features=result['year_features'],
            machine_logs=machine_logs,
            all_documents=result['all_documents']
        )

@station_bp.route("/pgu_machine_details/<int:station_id>/<int:machine_id>/<int:pgu_machine_id>", methods=["GET", "POST"])
@login_required
def pgu_machine_details(station_id, machine_id, pgu_machine_id):
    user = session.get('username', 'Неизвестный пользователь')

    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 1, type=int)

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

        # Загружаем журнал изменений для ПГУ-агрегата (если он существует)
        pgu_machine_logs = []
        try:
            if result.get('pgu_machine') and result['pgu_machine'].id:
                pm_id = result['pgu_machine'].id
                pgu_machine_logs = (
                    db.session.query(Log)
                    .filter(
                        or_(
                            Log.action.ilike("%ПГУ агрегат%"),
                            Log.details.ilike("%ПГУ агрегат%"),
                            Log.details.ilike(f"%ID: {pm_id}%"),
                            Log.details.ilike(f"%pgu_machine_id={pm_id}%")
                        )
                    )
                    .order_by(Log.timestamp.desc())
                    .limit(200)
                    .all()
                )
        except Exception:
            pgu_machine_logs = []

        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=result['station'],
            parent_machine=result['parent_machine'],
            pgu_form=result['pgu_form'],
            start_year=result['start_year'],
            end_year=result['end_year'],
            pgu_machine_id=result['pgu_machine_id'],
            year_features=result['year_features'],
            pgu_machine=result.get('pgu_machine'),
            pgu_machine_logs=pgu_machine_logs,
            rounding_digits=rounding_digits,
        )