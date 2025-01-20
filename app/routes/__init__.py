from flask import Blueprint

start_bp = Blueprint('start', __name__)

# Импорты маршрутов
from .app.start_routes import *