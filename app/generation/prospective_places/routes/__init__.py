from flask import Blueprint

prospective_places_bp = Blueprint('prospective_places_bp', __name__)

from .prospective_places_routes import *
from .prospective_places_ges_routes import *
from .prospective_places_gaes_routes import *
