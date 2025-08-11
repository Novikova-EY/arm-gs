from flask import Blueprint

station_changes_bp = Blueprint('station_changes_bp', __name__)

# Импортируем модули с маршрутами
from .station_changes_routes import *

