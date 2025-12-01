from flask import Blueprint

auth_bp = Blueprint('auth', __name__)
users_bp = Blueprint('users_bp', __name__)

# Импорты маршрутов
from .auth_routes import *
from .users_routes import *
from .decorators import *


