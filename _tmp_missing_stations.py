# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from decimal import Decimal
from app import create_app

app = create_app()
with app.app_context():
    from app.energy_balance.services.ee_balance_ves_ses_page_services import (
        build_ves_ses_page_rows,
        ves_ses_station_type_ids,
        _load_stations_p_ust,
        _load_energy_maps,
        _station_type_key,
    )
    from app.generation.models.station.station_model import Station
    from app.common.services.database_version_filter import (
        filter_by_db_version,
        get_current_db_version_id,
    )
    from app.common.services.get_services.years.year_feature_services import (
        get_year_feature_dict,
    )
    from app.generation.services.station_services.ves_ses_plan_generation_services import (
        compute_ves_ses_plan_generation,
        classify_ves_ses_generation_years,
        load_station_commission_years,
        load_station_exploitation_dates,
        seven_year_sample_window,
    )
    from app.energy_balance.models.station_energy_generation_model import (
        StationEnergyGeneration,
    )
    from app.generation.models.station.station_owner_energy_generation_model import (
        StationOwnerEnergyGeneration,
    )

    missing = [
        35985, 35986, 35987, 35988, 35989, 35990, 35991, 35992, 35993,
        36009, 36010, 36040, 36041, 36042, 36043, 36044, 36045, 36046, 36047, 36054,
    ]

    years = list(range(2018, 2032))
    features = get_year_feature_dict() or {}
    current_year, plan_years = classify_ves_ses_generation_years(features)
    version_id = get_current_db_version_id()

    stations = Station.query.filter(Station.id.in_(missing))
    stations = filter_by_db_version(stations, Station).all()
    print("missing stations loaded", len(stations), "current", current_year, "plan", plan_years[:3], "...")

    load_start = min(years)
    load_end = max(years)
    if current_year is not None:
        load_start = min(load_start, seven_year_sample_window(int(current_year))[0])
        load_end = max(load_end, int(current_year))

    ids = [s.id for s in stations]
    energy = _load_energy_maps(
        ids, load_start, load_end, version_id, StationEnergyGeneration, "electricity_generation"
    )
    owner = _load_energy_maps(
        ids, load_start, load_end, version_id, StationOwnerEnergyGeneration, "electricity_generation"
    )
    commission = load_station_commission_years(ids, version_id)
    exploitation = load_station_exploitation_dates(ids, version_id)
    p_ust = _load_stations_p_ust(ids, years, version_id)

    ses = Decimal(0)
    ves = Decimal(0)
    for st in stations:
        type_key = _station_type_key(getattr(getattr(st, "station_type", None), "name", None))
        energy_full = energy.get(st.id, {})
        min_s, plan_calc, rules = compute_ves_ses_plan_generation(
            energy_full,
            owner.get(st.id) or {},
            current_year=current_year,
            plan_years=plan_years,
            commission_year=commission.get(st.id),
            capacity_by_year=p_ust.get(st.id) or {},
            type_key=type_key,
            exploitation_date_expected=exploitation.get(st.id) or "",
        )
        v2026_stored = energy_full.get(2026)
        v2026_calc = plan_calc.get(2026) if plan_calc else None
        display = v2026_stored if v2026_stored is not None else v2026_calc
        print(
            st.id,
            st.name,
            type_key,
            "stored=",
            v2026_stored,
            "calc=",
            v2026_calc,
            "p=",
            (p_ust.get(st.id) or {}).get(2026),
            "comm=",
            commission.get(st.id),
        )
        if display is not None:
            if type_key == "ses":
                ses += Decimal(str(display))
            elif type_key == "ves":
                ves += Decimal(str(display))
    print("EXTRA from missing ses", ses, "ves", ves, "sum", ses + ves)

    rows, pagination = build_ves_ses_page_rows(
        years=years,
        digits=1,
        year_features=features,
        page=1,
        per_page=0,
        list_filters={"union_energy_system_filter": [412]},
    )
    print("page rows", len(rows), "pagination", pagination)

    def walk(items, depth=0):
        for r in items or []:
            nm = str(r.get("name") or "")
            kind = r.get("row_kind") or r.get("kind")
            if "Средней Волги" in nm or r.get("ues_id") == 412 or kind in ("ues_total", "type_total"):
                energy = r.get("energy") or {}
                ed = r.get("energy_display") or {}
                val = energy.get(2026) if isinstance(energy, dict) else None
                print(
                    " " * depth,
                    kind,
                    nm[:60],
                    "type",
                    r.get("type_key"),
                    "e2026",
                    val,
                    "disp",
                    ed.get(2026) if isinstance(ed, dict) else None,
                )
            kids = r.get("children") or r.get("child_rows") or r.get("rows") or []
            if kids:
                walk(kids, depth + 1)

    walk(rows)
