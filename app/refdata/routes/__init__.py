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

# refdata for stations
from .refdata_for_stations.condition_type_routes import *
from .refdata_for_stations.technologies.equipment_group_routes import *
from .refdata_for_stations.technologies.technology_availability_routes import *
from .refdata_for_stations.technologies.technology_type_routes import *
from .economic_activity.economic_activity_type_routes import *
from .refdata_for_stations.machines.machine_type_routes import *
from .refdata_for_stations.machines.pgu_tes_machine_type_routes import *
from .refdata_for_stations.machines.tes_machine_type_routes import *
from .refdata_for_stations.machines.tes_type_routes import *
from .refdata_for_stations.stations.station_type_routes import *

# Управление годами и версиями БД
from .years.year_management_routes import year_management_bp
from .years.year_routes import *
from .database_versions_routes import *  # добавляем маршруты /generation/database_versions на blueprint station_bp
refdata_bp.register_blueprint(year_management_bp)