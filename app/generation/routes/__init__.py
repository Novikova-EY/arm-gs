from flask import Blueprint

generation_bp = Blueprint('generation_bp', __name__)

# Импортируем модули с маршрутами
from .generation_routes import *

