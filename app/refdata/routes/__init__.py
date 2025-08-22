from flask import Blueprint

refdata_bp = Blueprint('refdata_bp', __name__)

from .refdata_routes import *
from .territories.federal_district_routes import *
from .territories.regional_district_routes import *
from .energy_systems.union_energy_system_routes import *
from .energy_systems.regional_energy_system_routes import *
from .energy_systems.energy_area_routes import *
from .energy_systems.energy_zone_routes import *
from .energy_systems.energy_system_type_routes import *
from .energy_systems.synchronous_area_routes import *
from .energy_systems.energy_unit_routes import *
from .gen_companies.gen_company_routes import *
from .fuels.fuel_routes import *
from .fuels.fuel_type_routes import *

