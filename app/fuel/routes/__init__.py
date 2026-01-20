from flask import Blueprint

fuel_bp = Blueprint("fuel_bp", __name__)

from .fuel_routes import *  # noqa: F401,F403
