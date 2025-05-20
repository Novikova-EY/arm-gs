from flask import Blueprint

reference_bp = Blueprint('reference_bp', __name__)

from .reference_routes import *
from .federal_district_routes import *
from .regional_district_routes import *
from .union_energy_system_routes import *
from .regional_energy_system_routes import *
from .energy_area_routes import *
from .energy_unit_routes import *
from .gen_company_routes import *
from .fuel_routes import *

