# -*- coding: utf-8 -*-
from flask import render_template
from flask_login import login_required

from app.energy_balance.routes.energy_balance_bp import energy_balance_bp


@energy_balance_bp.route("/")
@login_required
def hub():
    """Главная страница модуля «Балансы ЭЭ и ЭМ»."""
    return render_template("energy_balance/energy_balance_start.html")


