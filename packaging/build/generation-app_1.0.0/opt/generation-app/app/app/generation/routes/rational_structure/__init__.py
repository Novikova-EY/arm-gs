from flask import Blueprint

rational_structure_bp = Blueprint('rational_structure_bp', __name__)

# Импортируем модули с маршрутами
from .ti_table_routes import *

