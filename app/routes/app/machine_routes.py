from config import Config
from flask import (
    render_template, request, session
)
from . import app_bp
from app.models.logs_models import Log
from app.forms.station_forms import StationFilterForm
from app.services.station_services import (
    log_to_db, get_machine_by_id

)
from flask_login import login_required
from app.routes.auth import role_required
from app import db

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")
from flask import session


@app_bp.route("/machine_details/<int:machine_id>", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def machine_details(machine_id):
    """Маршрут для отображения сведений об агрегате электростанции."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, f"Открыта страница агрегата электростанции ID {machine_id}")

    form = StationFilterForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", 2021, type=int)
    end_year = request.args.get("end_year", 2031, type=int)

    # Получаем данные по станции
    machine = get_machine_by_id(machine_id)
    
    return render_template(
        "stations/machine_details.html",
        form=form,
        machine=machine,
        start_year=start_year,
        end_year=end_year, 
    )