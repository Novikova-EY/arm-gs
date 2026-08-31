# -*- coding: utf-8 -*-
from flask import g
from run import app

with app.app_context():
    g.current_db_version = 46
    from app.energy_balance.services.power_balance_page_services import get_power_balance_sheets
    from app.energy_balance.services.power_balance_installed_capacity_services import (
        load_power_balance_installed_capacity_inputs,
        _aggregated_metric,
    )
    from app.generation.services.station_services.aggregation_station_services.aggregation_rows import (
        get_full_aggregation_rows,
    )
    from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import (
        aggregate_all_at_once,
    )
    from app.generation.services.station_services.station_services import get_filtered_station_ids

    sheets = get_power_balance_sheets()
    res_sheets = [s for s in sheets if s.get("group") == "res"]
    print("RES SHEETS", [(s["slug"], s["sheet_name"], s.get("territory")) for s in res_sheets])
    years = [2026, 2027, 2028, 2029, 2030, 2031]
    try:
        inputs = load_power_balance_installed_capacity_inputs(years, sheets=res_sheets)
        print("INPUT SLUGS", list(inputs))
        for slug, rows in inputs.items():
            tes = rows.get("installed_tes") or {}
            ges = rows.get("installed_ges") or {}
            print(
                slug,
                "tes",
                {y: tes.get(y) for y in years},
                "ges",
                {y: ges.get(y) for y in years},
            )
    except Exception as exc:
        print("LOAD ERROR", type(exc).__name__, exc)

    station_ids = get_filtered_station_ids({})
    print("STATION_IDS", len(station_ids or []))
    rows = get_full_aggregation_rows(2026, 2031, station_ids)
    print("AGG ROWS", len(rows or []))
    res_ids = {}
    for row in rows or []:
        rid = getattr(row, "regional_energy_system_id", None)
        res_ids[rid] = res_ids.get(rid, 0) + 1
    wanted = {s["territory"]["id"] for s in res_sheets}
    print("WANTED RES IDS", wanted)
    print("WANTED IN AGG", {rid: res_ids.get(rid) for rid in wanted})
    print("SAMPLE AGG RES KEYS", list(res_ids)[:20], "count", len(res_ids))
    aggregated = aggregate_all_at_once(rows)
    res_st = _aggregated_metric(
        aggregated, "aggregate_regional_energy_systems_by_station_types", "p_ust"
    )
    print("RES_ST KEYS sample", list(res_st)[:15], "len", len(res_st))
    for rid in wanted:
        by_type = res_st.get(rid) or res_st.get(int(rid)) or {}
        print("RES", rid, "type keys", list(by_type)[:10], "n", len(by_type))
        if by_type:
            first = next(iter(by_type))
            print("  first type", first, dict(by_type[first]))
