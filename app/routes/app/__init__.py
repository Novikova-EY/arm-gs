from flask import Blueprint

app_bp = Blueprint('app_bp', __name__)

# Импортируем модули с маршрутами
from .reference_routes import *
from .federal_district_routes import *
from .regional_district_routes import *
from .union_energy_system_routes import *
from .regional_energy_system_routes import *
from .gen_company_routes import *
from .fuel_routes import *
from .station_routes import *
from .machine_routes import *

