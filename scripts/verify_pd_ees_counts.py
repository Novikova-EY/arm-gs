#!/usr/bin/env python
# -*- coding: utf-8 -*-
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    for t in (
        "gs_pd_ees_russia_demand_params",
        "gs_pd_ees_demand_params",
        "gs_pd_energy_system_type_demand_params",
    ):
        c = db.session.execute(text(f"SELECT COUNT(*) FROM gs_pd.{t}")).scalar()
        print(t, c)
