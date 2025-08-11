from flask import Blueprint

start_bp = Blueprint('start', __name__)

# Импорты маршрутов
from .start_routes import *