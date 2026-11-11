from flask import abort, current_app, jsonify, request
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from wtforms.validators import ValidationError

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.rational_structure.routes import rational_structure_module_bp
from app.rational_structure.services.territory_cell_services import save_territory_cell


@rational_structure_module_bp.route("/territory_inputs/cell", methods=["PATCH"], defaults={"kind": "inputs"})
@rational_structure_module_bp.route("/territory_technologies/cell", methods=["PATCH"], defaults={"kind": "technologies"})
@login_required
def update_territory_cell(kind):
    if not current_user.has_admin:
        abort(403)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Ожидается объект JSON."), 400
    if current_app.config.get("WTF_CSRF_ENABLED", True):
        try:
            validate_csrf(request.headers.get("X-CSRFToken"))
        except ValidationError:
            return jsonify(ok=False, error="Обновите страницу: не удалось проверить CSRF-токен."), 400
    try:
        result = save_territory_cell(kind, data, get_current_db_version_id(), current_user.username)
    except (ValueError, HTTPException) as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc) if isinstance(exc, ValueError) else exc.description), getattr(exc, "code", 400)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Ошибка автосохранения данных по территориям")
        return jsonify(ok=False, error="Ошибка базы данных. Значение не сохранено; повторите попытку."), 500
    log_to_db(current_user.username, "Изменена ячейка данных по территориям",
              f"Версия БД {data['database_version_id']}; таблица {kind}; запись {result['record_id']}; "
              f"энергозона {data.get('energy_zone_id', data.get('zone_number', ''))}; "
              f"поле {data.get('field')}; строка {data.get('row_key', data.get('row_id'))}; "
              f"год {data.get('year', '')}: {result['old_value']} → {result['value']}", entity_type="rational_structure")
    return jsonify(ok=True, value=result["value"], **(
        {"year_values": result["year_values"]} if "year_values" in result else {}))
