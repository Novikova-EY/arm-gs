from flask import Blueprint

app_bp = Blueprint('app_bp', __name__)

# Импортируем модули с маршрутами
from .reference_routes import *
from .fo_routes import *
from .region_routes import *
from .oes_routes import *
from .res_routes import *

