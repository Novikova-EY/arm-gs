# -*- coding: utf-8 -*-
"""
Маршруты для управления текущим годом и годами СиПР.
"""

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from app.auth.routes.decorators import roles_required

from app.refdata.services.year_management_services import (
    get_current_year_info,
    update_current_year,
    update_sipr_years,
    update_sipr_dates
)
from app.common.services.database_version_services import get_current_version

# Создаем Blueprint
year_management_bp = Blueprint('year_management', __name__)


@year_management_bp.route("/api/current-year-info", methods=["GET"])
@login_required
def get_year_info():
    """Получает информацию о текущем годе и годах СиПР для текущей версии БД."""
    try:
        version_id = get_current_version()
        if not version_id:
            # Если текущая версия БД не установлена, возвращаем нули по годам (как по ТЗ)
            return jsonify({
                'success': True,
                'data': {
                    'current_year': 0,
                    'sipr_start': 0,
                    'sipr_end': 0,
                    'date_sipr_start': None,
                    'date_sipr_end': None
                }
            })
        
        info = get_current_year_info(version_id)
        return jsonify({
            'success': True,
            'data': info
        })
    except Exception as e:
        import traceback
        current_app.logger.error(f"Ошибка в get_year_info: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Ошибка получения информации о годах: {str(e)}'
        }), 500


@year_management_bp.route("/api/update-current-year", methods=["POST"])
@login_required
@roles_required(["admin"])
def update_year():
    """Обновляет текущий год для текущей версии БД. Только для администраторов."""
    try:
        version_id = get_current_version()
        if not version_id:
            return jsonify({
                'success': False,
                'message': 'Текущая версия БД не установлена'
            }), 400
        
        data = request.get_json()
        if not data or 'year' not in data:
            return jsonify({
                'success': False,
                'message': 'Не указан год'
            }), 400
        
        new_year = int(data['year'])
        if new_year < 2000 or new_year > 2100:
            return jsonify({
                'success': False,
                'message': 'Некорректное значение года'
            }), 400
        
        success, message = update_current_year(version_id, new_year, current_user)
        
        if success:
            # Получаем обновленную информацию
            info = get_current_year_info(version_id)
            return jsonify({
                'success': True,
                'message': message,
                'data': info
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Некорректное значение года'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка обновления текущего года: {str(e)}'
        }), 500


@year_management_bp.route("/api/update-sipr-years", methods=["POST"])
@login_required
@roles_required(["admin"])
def update_sipr():
    """Обновляет годы СиПР для текущей версии БД. Только для администраторов."""
    try:
        version_id = get_current_version()
        if not version_id:
            return jsonify({
                'success': False,
                'message': 'Текущая версия БД не установлена'
            }), 400
        
        data = request.get_json()
        if not data or 'sipr_start' not in data or 'sipr_end' not in data:
            return jsonify({
                'success': False,
                'message': 'Не указаны годы СиПР'
            }), 400
        
        sipr_start = int(data['sipr_start'])
        sipr_end = int(data['sipr_end'])
        
        if sipr_start < 2000 or sipr_start > 2100 or sipr_end < 2000 or sipr_end > 2100:
            return jsonify({
                'success': False,
                'message': 'Некорректные значения годов'
            }), 400
        
        success, message = update_sipr_years(version_id, sipr_start, sipr_end, current_user)
        
        if success:
            # Получаем обновленную информацию
            info = get_current_year_info(version_id)
            return jsonify({
                'success': True,
                'message': message,
                'data': info
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Некорректные значения годов'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка обновления годов СиПР: {str(e)}'
        }), 500


@year_management_bp.route("/api/update-sipr-dates", methods=["POST"])
@login_required
@roles_required(["admin"])
def update_sipr_dates_route():
    """Обновляет даты СиПР для текущей версии БД. Только для администраторов."""
    try:
        version_id = get_current_version()
        if not version_id:
            return jsonify({
                'success': False,
                'message': 'Текущая версия БД не установлена'
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Не указаны данные'
            }), 400
        
        date_sipr_start = data.get('date_sipr_start')  # Может быть None или строка
        date_sipr_end = data.get('date_sipr_end')  # Может быть None или строка
        
        success, message = update_sipr_dates(version_id, date_sipr_start, date_sipr_end, current_user)
        
        if success:
            # Получаем обновленную информацию
            info = get_current_year_info(version_id)
            return jsonify({
                'success': True,
                'message': message,
                'data': info
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка обновления дат СиПР: {str(e)}'
        }), 500

