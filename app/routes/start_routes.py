from flask import Blueprint, render_template

start_bp = Blueprint('start', __name__)

@start_bp.route('/')
def index():
    return render_template('home.html')
