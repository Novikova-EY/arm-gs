from flask import render_template, request, send_file
from flask_login import login_required

from . import fuel_bp
from app.fuel.services.stations.station_power_comparison_services import (
    build_station_power_comparison,
)
from app.fuel.services.fuel_exports.export_station_power_comparison_services import (
    export_station_power_comparison_to_excel,
)


def _comparison_options():
    raw_year = request.args.get("year")
    if raw_year is None:
        year = None
    elif raw_year == "":
        year = ""
    else:
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            year = None

    try:
        rounding_digits = int(request.args.get("rounding_digits", 0))
    except (TypeError, ValueError):
        rounding_digits = 0

    return {
        "selected_year": year,
        "show_p_rasp": request.args.get("p_rasp", "0") == "1",
        "show_ved0": request.args.get("ved0", "0") == "1",
        "show_boilers": request.args.get("boilers", "0") == "1",
        "rounding_digits": rounding_digits,
    }


@fuel_bp.route("/stations_equipment_groups/power_comparison", methods=["GET"])
@login_required
def station_power_comparison():
    data = build_station_power_comparison(
        **_comparison_options(), page=request.args.get("page", 1, type=int),
    )
    return render_template(
        "fuel/equipment_groups/stations_equipment_groups_power_comparison.html",
        comparison=data,
    )


@fuel_bp.route("/stations_equipment_groups/power_comparison/export", methods=["GET"])
@login_required
def export_station_power_comparison():
    data = build_station_power_comparison(**_comparison_options(), paginate=False)
    excel_file = export_station_power_comparison_to_excel(data)
    year = data["selected_year"]
    year_label = "без_года" if year in (None, "") else str(year)
    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Сравнение_мощностей_{year_label}.xlsx",
    )
