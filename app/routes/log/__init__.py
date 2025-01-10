from flask import Blueprint

logs_bp = Blueprint('logs', __name__)

# Импорты маршрутов
from .log_routes import *


