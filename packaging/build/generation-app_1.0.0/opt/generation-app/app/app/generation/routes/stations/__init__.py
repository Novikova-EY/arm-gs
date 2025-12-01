from flask import Blueprint

station_bp = Blueprint('station_bp', __name__)

# Импортируем модули с маршрутами
from .station_routes import *
from .export_stations_routes import *
from .import_stations_routes import *
from .machine_routes import *
from .station_details_routes import *
from .document_routes import *
from app.generation.routes.database_versions_routes import *

