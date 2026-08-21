from flask import Blueprint

fuel_bp = Blueprint("fuel_bp", __name__)

from .fuel_routes import *  # noqa: F401,F403
from .fuel_calculation_routes import *  # noqa: F401,F403
from .calculation.fuel_calculation_edit_data_routes import *  # noqa: F401,F403
from .calculation.distribution_stage_routes import *  # noqa: F401,F403
from .calculation.fuel_stage_routes import *  # noqa: F401,F403
from .equipment_group_fuel_batch_ui_routes import *  # noqa: F401,F403
from .equipment_group_fuel_formula_routes import *  # noqa: F401,F403
from .fuel_formulas_routes import *  # noqa: F401,F403
from app.fuel.refdata.routes.fuel_routes import *  # noqa: F401,F403
from app.fuel.refdata.routes.fuel_type_routes import *  # noqa: F401,F403
