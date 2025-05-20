from flask import render_template
from . import reference_bp
from flask_login import login_required
from app.routes.auth import role_required

@reference_bp.errorhandler(403)
def forbidden(error):
    return render_template('errors/forbidden.html'), 403

@reference_bp.route("/")
@login_required
@role_required('super-admin')
def reference():
    return render_template("references/reference.html")