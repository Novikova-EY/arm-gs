from flask import render_template
from . import refdata_bp
from flask_login import login_required
from app.auth.routes import roles_required

@refdata_bp.errorhandler(403)
def forbidden(error):
    return render_template('errors/forbidden.html'), 403

@refdata_bp.route("/")
@login_required
def refdata():
    return render_template("refdata/refdata.html")