from . import rational_structure_bp
from app.extensions import db
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from flask import render_template
from sqlalchemy.orm import joinedload
from app.common.services.help_services import (
    _clean_name,
)
from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)


def _filter_items_by_version(items, version_id):
    if not items:
        return []
    if version_id is None:
        return [item for item in items if getattr(item, "database_version_id", None) is None]
    return [
        item for item in items
        if getattr(item, "database_version_id", None) == version_id
    ]


@rational_structure_bp.route("/ti_table")
def ti_table():
    current_version_id = get_current_db_version_id()
    machines_query = Machine.query.options(
        joinedload(Machine.machine_station).joinedload(Station.regional_district),
        joinedload(Machine.machine_station).joinedload(Station.station_type),
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.equipment_group),
        joinedload(Machine.machine_powers),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    )
    machines_query = filter_by_db_version(machines_query, Machine)
    machines = machines_query.all()

    data = []
    for m in machines:
        m.machine_powers = _filter_items_by_version(m.machine_powers, current_version_id)
        m.machine_tes_types = _filter_items_by_version(m.machine_tes_types, current_version_id)
        station = m.machine_station
        power_2024 = next((p.p_ust for p in m.machine_powers if p.year_number == 2024), None)
        tes_types = {
            t.tes_type.name for t in m.machine_tes_types
            if t.tes_type and t.tes_type.name and t.tes_type.name.lower() != "не указано"
        }

        data.append({
            "subject": station.regional_district.name if station and station.regional_district else "—",
            "ti_number": m.id_ti or "—",
            "group_type": m.equipment_group.name if m.equipment_group else "—",
            "station": station.name if station else "—",
            "group_number": m.machine_group or "—",
            "machine_number": m.machine_number or "—",
            "machine_name": m.machine_name or "—",
            "exploitation_year": m.date_exploitation or "—",
            "power_2024": float(power_2024) if power_2024 else "—",
            "station_type": (
                station.station_type.name
                if station and station.station_type
                else "—"
            ),
            "tes_type": ", ".join(sorted(tes_types)) if tes_types else "—",
            "tes_machine_type": m.tes_machine_type.name if m.tes_machine_type else "—",
            "year_modern": m.year_modern if m.year_modern else "—",
            "year_demontaz": m.year_demontaz if m.year_demontaz else "—",
            "resurs_coal": m.resurs_coal if m.resurs_coal else "—",
            "resurs_gas": m.resurs_gas if m.resurs_gas else "—",
        })

    return render_template("generation/stations/ti_table.html", rows=data)


import re
from flask import request, jsonify
from decimal import Decimal
from sqlalchemy.orm import joinedload

import pandas as pd
@rational_structure_bp.route("/api/upload_and_update_machines", methods=["POST"])
def upload_and_update_machines():
    try:
        import pandas as pd
        from datetime import datetime
        from io import BytesIO
        import os
        current_version_id = get_current_db_version_id()

        file = request.files.get("file")
        if not file:
            print("[ERROR] Файл не получен")
            return jsonify({"error": "Файл не получен"}), 400

        df = pd.read_excel(file)
        print(f"[FILE] Прочитано строк: {len(df)}")
        df = df.dropna(how="all")
        updated = 0
        skipped = 0
        log_rows = []

        for index, row in df.iterrows():
            print(f"[DEBUG] Обрабатывается строка {index}: {row.to_dict()}")
            try:
                station_name = _clean_name(row.get("station_name"))
                gen_company_name = _clean_name(row.get("gen_company"))
                machine_number = _clean_name(row.get("machine_number"))
                machine_name = _clean_name(row.get("machine_name"))
                group_name = _clean_name(row.get("equipment_group"))
                year_modern = _clean_name(row.get("year_modern"))
                year_demontaz = _clean_name(row.get("year_demontaz"))
                resurs_coal = _clean_name(row.get("resurs_coal"))
                resurs_gas = _clean_name(row.get("resurs_gas"))
                date = str(row.get("date")).strip()
                p_ust = float(row.get("p_ust") or 0)
                id_ti = row.get("id_ti")

                # Поиск станции по подстроке
                candidate_stations_query = Station.query
                candidate_stations_query = filter_by_db_version(candidate_stations_query, Station)
                candidate_stations = candidate_stations_query.all()
                station = None
                for s in candidate_stations:
                    if station_name.lower() in _clean_name(s.name).lower():
                        station = s
                        break

                if not station:
                    msg = f"⛔ Станция не найдена (по подстроке): {station_name}"
                    log_rows.append([station_name, gen_company_name, machine_number, machine_name, msg])
                    skipped += 1
                    continue

                # Поиск агрегата: 3 попытки
                matched_machine = None

                station_machines = _filter_items_by_version(station.machines, current_version_id)
                for m in station_machines:
                    db_machine_number = _clean_name(m.machine_number) if m.machine_number else None
                    db_machine_name = _clean_name(m.machine_name) if m.machine_name else None
                    db_gen_company = _clean_name(m.gen_company.name) if m.gen_company else None

                    # 1. По номеру и ген. компании
                    if db_machine_number == machine_number and db_gen_company == gen_company_name:
                        matched_machine = m
                        break

                if not matched_machine:
                    for m in station_machines:
                        db_machine_number = _clean_name(m.machine_number) if m.machine_number else None
                        db_machine_name = _clean_name(m.machine_name) if m.machine_name else None

                        if (
                            db_machine_number == machine_number and
                            db_machine_name and machine_name and
                            machine_name.upper() in db_machine_name.upper()
                        ):
                            matched_machine = m
                            break

                if not matched_machine:
                    for m in station_machines:
                        db_machine_name = _clean_name(m.machine_name) if m.machine_name else None
                        db_gen_company = _clean_name(m.gen_company.name) if m.gen_company else None

                        if (
                            db_machine_name and machine_name and
                            machine_name.upper() in db_machine_name.upper() and
                            db_gen_company == gen_company_name and
                            station_name.lower() in _clean_name(station.name).lower()
                        ):
                            matched_machine = m
                            break

                if not matched_machine:
                    msg = "⛔ Не найден агрегат ни по (ген. компания + номер), ни по (имя + номер), ни по (имя станции + ген. компания + имя)"
                    log_rows.append([station_name, gen_company_name, machine_number, machine_name, msg])
                    skipped += 1
                    continue

                eq_group_query = EquipmentGroupType.query.filter_by(name=group_name)
                eq_group_query = filter_by_db_version(eq_group_query, EquipmentGroupType)
                eq_group = eq_group_query.first()
                if not eq_group:
                    msg = f"⛔ Не найдена группа оборудования: {group_name}"
                    log_rows.append([station_name, gen_company_name, machine_number, machine_name, msg])
                    skipped += 1
                    continue

                # Обработка id_ti — если не задан, ставим 0
                if not id_ti or int(id_ti) == 0:
                    id_ti = 0
                    
                matched_machine.id_equipment_group = eq_group.id
                matched_machine.id_ti = id_ti
                matched_machine.year_modern = year_modern
                matched_machine.year_demontaz = year_demontaz
                matched_machine.resurs_coal = resurs_coal
                matched_machine.resurs_gas = resurs_gas

                updated += 1
                log_rows.append([station_name, gen_company_name, machine_number, machine_name, "✅ Обновлено"])

            except Exception as inner:
                msg = f"‼️ Ошибка: {inner}"
                log_rows.append([
                    station_name or "—", gen_company_name or "—",
                    machine_number or "—", machine_name or "—", msg
                ])
                skipped += 1

        db.session.commit()

        # Сохраняем лог в Excel
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_filename = os.path.join(log_dir, f"machine_update_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

        log_df = pd.DataFrame(log_rows, columns=[
            "Станция", "Ген. компания", "Номер агрегата", "Имя агрегата", "Комментарий"
        ])
        log_df.to_excel(log_filename, index=False, engine="openpyxl")

        print(f"📁 Excel-лог сохранен: {log_filename}")

        return jsonify({"updated": updated, "skipped": skipped, "log_file": log_filename})

    except Exception as outer:
        print("‼️ Общая ошибка:", outer)
        return jsonify({"error": str(outer)}), 500



@rational_structure_bp.route("/export/machine_ti_subjects")
def export_machine_ti_subjects():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    from datetime import datetime

    # Используем один JOIN-запрос через SQLAlchemy ORM
    results = (
        db.session.query(
            Machine.id_ti,
            Station.name.label("station_name"),
            Machine.machine_number,
            Machine.machine_name,
            RegionalDistrict.name.label("region_name")
        )
        .join(Station, Station.id == Machine.id_station)
        .outerjoin(RegionalDistrict, RegionalDistrict.id == Station.id_regional_district)
        .all()
    )

    rows = []
    for id_ti, station_name, machine_number, machine_name, region_name in results:
        rows.append([
            id_ti or "—",
            region_name or "—",
            station_name or "—",
            machine_number or "—",
            machine_name or "—"
        ])

    df = pd.DataFrame(rows, columns=[
        "id_ti", "Субъект РФ", "Станция", "Номер агрегата", "Название агрегата"
    ])

    output = BytesIO()
    df.to_excel(output, index=False, engine='openpyxl')
    output.seek(0)

    filename = f"machine_ti_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )