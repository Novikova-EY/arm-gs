from flask import Blueprint

arm_generation_bp = Blueprint('arm_generation_bp', __name__)

# Импортируем модули с маршрутами
from .arm_generation_routes import *

