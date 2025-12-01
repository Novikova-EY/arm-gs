from . import generation_bp
from flask import (
    render_template
)

@generation_bp.route("/generation")
def generation_start():
    return render_template("generation/generation_start.html")