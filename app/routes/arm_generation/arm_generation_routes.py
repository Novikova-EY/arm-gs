from . import arm_generation_bp
from flask import (
    render_template
)

@arm_generation_bp.route("/arm-generation")
def arm_generation_start():
    return render_template("arm_generation_start.html")