from flask import Blueprint

auth_bp = Blueprint('auth', __name__)

# Импорты маршрутов
from .auth_routes import *
from .decorators import *


