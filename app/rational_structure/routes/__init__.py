from flask import Blueprint

rational_structure_module_bp = Blueprint("rational_structure_module_bp", __name__)

from . import technical_characteristic_routes  # noqa: E402, F401
from . import territory_technology_routes  # noqa: E402, F401
from . import territory_data_routes  # noqa: E402, F401
from . import territory_cell_routes  # noqa: E402, F401
from . import equipment_runtime_routes  # noqa: E402, F401
from . import marginal_price_routes  # noqa: E402, F401
from . import calculated_values_routes  # noqa: E402, F401
