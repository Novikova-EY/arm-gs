# -*- coding: utf-8 -*-
"""
Middleware для обработки concurrent updates и оптимистической блокировки.
"""
from functools import wraps
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.exc import IntegrityError
from flask import flash, redirect, request, jsonify
from app.extensions import db
import logging

logger = logging.getLogger(__name__)


class ConcurrentUpdateMiddleware:
    """
    Middleware для обработки ошибок параллельного обновления данных.
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация middleware с приложением Flask."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        # Не используем teardown_appcontext - SQLAlchemy управляет сессиями автоматически
        # app.teardown_appcontext(self.teardown)
    
    @staticmethod
    def before_request():
        """Выполняется перед каждым запросом."""
        # Здесь можно добавить логику для отслеживания активных сессий
        pass
    
    @staticmethod
    def after_request(response):
        """Выполняется после каждого запроса."""
        return response
    
    @staticmethod
    def teardown(exception=None):
        """Выполняется при завершении контекста приложения."""
        if exception:
            db.session.rollback()
            logger.error(f"Request teardown with exception: {exception}")
        else:
            # Не делаем автоматический commit для GET запросов (только чтение)
            # Commit должен быть явным в маршрутах изменения данных
            try:
                # Удаляем сессию, но не делаем commit
                db.session.remove()
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")
                db.session.rollback()


def handle_stale_data(func):
    """
    Декоратор для обработки ошибок StaleDataError (оптимистическая блокировка).
    
    Использование:
        @app.route('/update/<int:id>', methods=['POST'])
        @handle_stale_data
        def update_entity(id):
            entity = Entity.query.get(id)
            entity.name = request.form['name']
            db.session.commit()
            return redirect('/')
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except StaleDataError:
            db.session.rollback()
            logger.warning(f"StaleDataError in {func.__name__}: Concurrent update detected")
            
            # Проверяем, является ли это AJAX-запросом
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'concurrent_update',
                    'message': 'Данные были изменены другим пользователем. Пожалуйста, обновите страницу и попробуйте снова.'
                }), 409
            
            flash('Данные были изменены другим пользователем. Пожалуйста, обновите страницу и попробуйте снова.', 'warning')
            return redirect(request.referrer or '/')
        
        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"IntegrityError in {func.__name__}: {str(e)}")
            
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'integrity_error',
                    'message': 'Ошибка целостности данных. Возможно, запись с такими параметрами уже существует.'
                }), 400
            
            flash('Ошибка целостности данных. Возможно, запись с такими параметрами уже существует.', 'error')
            return redirect(request.referrer or '/')
    
    return wrapper


def with_db_retry(max_attempts=3, backoff_factor=0.5):
    """
    Декоратор для повторной попытки выполнения операции при временных ошибках БД.
    
    Args:
        max_attempts: Максимальное количество попыток
        backoff_factor: Множитель для экспоненциальной задержки между попытками
    
    Использование:
        @with_db_retry(max_attempts=3)
        def update_entity(id, data):
            entity = Entity.query.get(id)
            entity.update(data)
            db.session.commit()
    """
    import time
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except StaleDataError as e:
                    last_exception = e
                    db.session.rollback()
                    
                    if attempt < max_attempts - 1:
                        sleep_time = backoff_factor * (2 ** attempt)
                        logger.warning(f"StaleDataError in {func.__name__}, attempt {attempt + 1}/{max_attempts}. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"StaleDataError in {func.__name__} after {max_attempts} attempts")
                        raise
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Error in {func.__name__}: {str(e)}")
                    raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator

