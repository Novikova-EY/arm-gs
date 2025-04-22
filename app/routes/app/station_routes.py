from config import Config
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify
)
from . import app_bp
from app.forms.station_forms import StationFilterForm
from app.forms.machine_forms import MachineFilterSmallForm
from app.models import RegionalDistrict, StationGroup, RegionalEnergySystem, ConditionType, GenCompany, StationPower
from app.services.station_services import (
    get_stations_list, get_union_energy_systems, get_regional_districts, get_energy_system_types, get_regional_districts,
    get_federal_districts, get_regional_energy_systems, log_to_db, import_station_list_from_excel, export_station_list_to_excel, 
    get_station_by_id, get_condition_type, get_station_groups, get_gen_companies, get_year_features, 
    import_fuel_tes_station_from_excel, group_machines_by_group_and_fuel, get_energy_units,
    extract_station_data_from_form, extract_filters_from_form, extract_filters_from_args, filter_machines,
    load_station_power_by_year, get_station_list_template_context, group_stations_hierarchy
)

from app.services.logging_service import log_to_db

from flask_login import login_required
from app.routes.auth import role_required
from sqlalchemy import func
from flask import session

@app_bp.route("/station_list", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    import time
    start_time = time.time()
    
    form = StationFilterForm()
    if request.method == "POST":
        station_data = extract_station_data_from_form(request.form)
        return redirect(url_for("app_bp.station_list", **extract_filters_from_form(request.form)))

    # Получение фильтров из запроса
    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    per_page = filters.pop("per_page", 10)
    start_year = filters.pop("start_year", Config.START_YEAR)
    end_year = filters.pop("end_year", Config.END_YEAR)


    # Получаем станции
    pagination = get_stations_list(page=page, per_page=per_page, **filters)

    # Фильтруем агрегаты, если нужно
    pagination["stations"] = filter_machines(
        pagination["stations"],
        filters.get("tes_type_filter", []),
        filters.get("tes_machine_type_filter", [])
    )

    # Обработка агрегатов и подсчёт по годам
    for station in pagination["stations"]:
        station.machines = group_machines_by_group_and_fuel([station])[0].machines
        station.powers_by_year = load_station_power_by_year(station, filters.get("start_year"), filters.get("end_year"))

    # Группировка станций по иерархии энергосистем
    grouped_result = group_stations_hierarchy(pagination["stations"])
    pagination["grouped_stations"] = grouped_result["grouped_stations"]

    for station in pagination["stations"]:
        station.machines = group_machines_by_group_and_fuel([station])[0].machines

    # Если страница вышла за предел — возвращаемся на последнюю
    if pagination["page"] > pagination["total_pages"]:
        return redirect(url_for("app_bp.station_list", page=pagination["total_pages"], per_page=per_page))

    # Подгружаем справочники
    context = get_station_list_template_context(form, {**filters, "start_year": start_year, "end_year": end_year}, pagination)



    return render_template(
        "stations/stations.html", 
        **context,
    )


@app_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции с логированием изменений."""

    user = session.get('username', 'Неизвестный пользователь')
    station = get_station_by_id(station_id)
    regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
    log_to_db(user, f"Открыта страница электростанции {station.name} ({regional_district_name})")

    form = StationFilterForm()
    form_machines = MachineFilterSmallForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", 2021, type=int)
    end_year = request.args.get("end_year", 2031, type=int)

    # Получаем данные по станции
    condition_types = get_condition_type()
    station_groups = get_station_groups()
    gen_companies = get_gen_companies()

    # Получаем мощности по годам из StationPower
    station.powers_by_year = {
        sp.year_number: {
            "p_ust": sp.p_ust,
            "p_ogr": sp.p_ogr,
            "p_rasp": sp.p_rasp
        }
        for sp in StationPower.query.filter_by(id_station=station.id).filter(
            StationPower.year_number >= start_year,
            StationPower.year_number <= end_year
        ).all()
    }


    # Загружаем списки данных из сервисов
    regional_districts_list, regional_district_names = get_regional_districts()
    federal_districts, regional_district_mapping = get_federal_districts()
    regional_energy_systems_list, regional_energy_system_names = get_regional_energy_systems()
    union_energy_systems, union_energy_system_names, _ = get_union_energy_systems()
    energy_system_types, energy_system_type_names = get_energy_system_types()

    # Заполняем список субъектов РФ
    form.id_regional_district.choices = [(d["id"], d["name"]) for d in regional_districts_list]
    form.id_condition_type.choices = [(ct.id, ct.name) for ct in condition_types] or [(0, "не указано")]
    form.id_station_group.choices = [(ct.id, ct.name) for ct in station_groups] or [(0, "не указано")]
    form_machines.id_gen_company.choices = [(gc.id, gc.name) for gc in gen_companies] or [(0, "не указано")]

    if request.method == "GET":
        form.process(obj=station)

    if request.method == "POST":

        if not form.validate():
            print("Ошибки в form:", form.errors)

        changes = []

        if form.validate_on_submit():
            try:
                # Проверяем название станции
                if station.name != form.name.data:
                    changes.append(f"Название: {station.name} → {form.name.data}")
                    station.name = form.name.data
                
                # Проверяем состояние станции
                new_condition_type_id = int(form.id_condition_type.data)
                new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
                if new_condition_type:
                    old_value = station.condition_type.name if station.condition_type else "не указано"
                    new_value = new_condition_type.name
                    if old_value != new_value:
                        changes.append(f"Состояние: {old_value} → {new_value}")
                    station.id_condition_type = new_condition_type.id
                else:
                    flash("Ошибка: выбранное состояние не найдено!", "danger")


                # Проверяем группу станции
                new_group_id = form.id_station_group.data
                if new_group_id:
                    group_exists = db.session.query(StationGroup).filter_by(id=new_group_id).first()
                    if group_exists:
                        if station.id_group != new_group_id:
                            old_group = station.group.name if station.group else "не указано"
                            new_group = group_exists.name
                            changes.append(f"Группа: {old_group} → {new_group}")
                            station.id_group = new_group_id
                    else:
                        flash("Выбранная группа не существует!", "warning")

                # Проверяем примечание
                new_note = form.note.data.strip() if form.note.data.strip() else None
                if station.note != new_note:
                    changes.append(f"Примечание: {station.note} → {new_note}")
                    station.note = new_note

                # Проверяем субъект РФ
                if station.id_regional_district != form.id_regional_district.data:
                    old_value = station.regional_district.name if station.regional_district else "не указано"
                    new_value = next((d["name"] for d in regional_districts_list if d["id"] == form.id_regional_district.data), "не указано")
                    changes.append(f"Субъект РФ: {old_value} → {new_value}")
                    station.id_regional_district = form.id_regional_district.data

                # Проверяем местоположение
                new_location = form.location.data.strip() if form.location.data.strip() else None
                if station.location != new_location:
                    changes.append(f"Местоположение: {station.location} → {new_location}")
                    station.location = new_location

                # Обновляем федеральный округ
                new_regional_district_obj = db.session.query(RegionalDistrict).filter_by(id=form.id_regional_district.data).first()

                if new_regional_district_obj:
                    old_federal_district = station.regional_district.federal_district.name if station.regional_district.federal_district else "не указано"
                    new_federal_district = new_regional_district_obj.federal_district.name if new_regional_district_obj.federal_district else "не указано"
                    if old_federal_district != new_federal_district:
                        changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")
                    station.regional_district = new_regional_district_obj

                # Обновляем энергосистему
                related_res_obj = db.session.query(RegionalEnergySystem).filter(
                    RegionalEnergySystem.id.in_(
                        regional_district_mapping.get(station.regional_district.id, [])
                    )
                ).first()


                related_res_obj = (
                    db.session.query(RegionalEnergySystem)
                    .join(RegionalDistrict, RegionalEnergySystem.regional_districts)
                    .filter(RegionalDistrict.id == station.id_regional_district)
                    .first()
                )

                if related_res_obj:
                    old_regional_energy_system = (
                        station.regional_district.regional_energy_systems[0].name
                        if station.regional_district.regional_energy_systems
                        else "не указано"
                    )
                    new_regional_energy_system = related_res_obj.name

                    if old_regional_energy_system != new_regional_energy_system:
                        changes.append(f"Региональная энергосистема: {old_regional_energy_system} → {new_regional_energy_system}")

                    old_union_energy_system = (
                        station.regional_district.regional_energy_systems[0].union_energy_system.name
                        if station.regional_district.regional_energy_systems and station.regional_district.regional_energy_systems[0].union_energy_system
                        else "не указано"
                    )
                    new_union_energy_system = (
                        related_res_obj.union_energy_system.name if related_res_obj.union_energy_system else "не указано"
                    )

                    if old_union_energy_system != new_union_energy_system:
                        changes.append(f"ОЭС: {old_union_energy_system} → {new_union_energy_system}")

                    station.regional_district.regional_energy_systems = [related_res_obj]


                # Сохраняем в БД
                db.session.commit()

                if changes:
                    log_to_db(user, f"Изменения в электростанции {station.name} ({regional_district_name})", details="; ".join(changes))

                flash("Изменения в электростанции успешно обновлены!", "success")
                return redirect(url_for("app_bp.station_details", station_id=station.id, **request.args))

            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при обновлении: {str(e)}")
                flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
                log_to_db(user, f"Ошибка обновления электростанции {station.name} ({regional_district_name})", details=str(e))

        if not form_machines.validate():
            print("Ошибки в form_machines:", form_machines.errors)

        if form_machines.validate_on_submit():
            for machine in station.machines:
                fuel_so_key = f"fuel_so_{machine.id}"
                gen_company_key = f"id_gen_company_{machine.id}"

                new_fuel_so = request.form.get(fuel_so_key, "").strip()
                new_gen_company_id = request.form.get(gen_company_key, type=int)

                if machine.fuel_so != new_fuel_so:
                    changes.append(f"Агрегат {machine.machine_number}: Топливо {machine.fuel_so} → {new_fuel_so}")
                    machine.fuel_so = new_fuel_so

                # Обновляем собственника агрегата
                if new_gen_company_id:
                    new_gen_company = db.session.query(GenCompany).filter_by(id=new_gen_company_id).first()
                    if new_gen_company:
                        old_gen_company_name = machine.gen_company.name if machine.gen_company else "не указано"
                        if machine.gen_company is None or machine.gen_company.id != new_gen_company_id:
                            changes.append(f"Агрегат {machine.machine_number}: Собственник {old_gen_company_name} → {new_gen_company.name}")
                            machine.gen_company = new_gen_company
                    else:
                        flash(f"Ошибка: выбранная генерирующая компания не существует!", "danger")


            db.session.commit()

            if changes:
                log_to_db(user, f"Обновлены агрегаты станции {station.name}", details="; ".join(changes))
                flash("Изменения агрегатов сохранены!", "success")

            return redirect(url_for("app_bp.station_details", station_id=station.id, **request.args))

    
    return render_template(
        "stations/station_details.html",
        form=form,
        form_machines=form_machines,
        station=station,
        start_year=start_year,
        end_year=end_year, 
        federal_districts=federal_districts,
        regional_districts_list=regional_districts_list,
        regional_energy_systems_list=regional_energy_systems_list,
        union_energy_systems=union_energy_systems,
        energy_system_types=energy_system_types, )


@app_bp.route("/get_energy_system_data/<int:regional_district_id>", methods=["GET"])
def get_energy_system_data(regional_district_id):
    regional_district = db.session.query(RegionalDistrict).filter_by(id=regional_district_id).first()

    if not regional_district:
        return jsonify({"error": "Регион не найден"}), 404

    federal_district = regional_district.federal_district.name if regional_district.federal_district else "Нет данных"

    # Получаем все возможные энергосистемы для данного субъекта РФ
    energy_systems = regional_district.regional_energy_systems

    if not energy_systems:
        return jsonify({"error": "Нет данных по энергосистеме"}), 404

    # Ищем правильную РЭС (если их несколько)
    regional_energy_system = next((res.name for res in energy_systems if res.union_energy_system), energy_systems[0].name)

    # Определяем ОЭС по найденной РЭС
    union_energy_system = next((res.union_energy_system.name for res in energy_systems if res.union_energy_system), "Нет данных")

    # Определяем тип энергосистемы
    energy_system_type = next((res.union_energy_system.energy_system_type.name for res in energy_systems if res.union_energy_system), "Нет данных")

    data = {
        "federal_district": federal_district,
        "regional_energy_system": regional_energy_system,
        "union_energy_system": union_energy_system,
        "energy_system_type": energy_system_type
    }

    return jsonify(data)


from app import db
from flask import request, send_file
from datetime import datetime

@app_bp.route("/import_stations_from_excel", methods=["POST"])
def import_station_list_from_excel_routes():
    """Маршрут для импорта данных электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных электростанций из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.station_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    try:
        result = import_station_list_from_excel(file, user)
        flash(result['message'], "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.station_list"))


from app import db
from flask import request, send_file
from datetime import datetime

@app_bp.route("/import_fuel_tes_station_from_excel", methods=["POST"])
def import_fuel_tes_station_from_excel_routes():
    """Маршрут для импорта данных по топливу электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных по топливу электростанций из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.station_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    try:
        result = import_fuel_tes_station_from_excel(file, user)
        flash(result['message'], "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.station_list"))

from flask import send_file, redirect, url_for, flash, request, session, current_app
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime
@app_bp.route('/export_stations', methods=['GET'])
def export_station_list():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    filters = {
        key: request.args.get(key)
        for key in [
            'energy_system_type_filter', 'union_energy_system_filter', 
            'regional_energy_system_filter', 'federal_district_filter', 
            'regional_district_filter'
        ]
    }

    # Фильтруем None-значения, чтобы `url_for()` не получил их
    filters = {k: v for k, v in filters.items() if v}


    try:
        # Получение данных для экспорта
        excel_files = export_station_list_to_excel(user, filters)

        # Проверка наличия данных
        if not excel_files:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.station_list"))

        # Если возвращён один файл, отправляем его напрямую
        if isinstance(excel_files, tuple):
            file_name, file_obj = excel_files
            return send_file(
                file_obj,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=file_name
            )

        # Если файлов несколько, создаём ZIP-архив
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for file_name, file_obj in excel_files:
                zip_file.writestr(file_name, file_obj.getvalue())

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"Экспорт_станций_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )

    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        print(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("app_bp.station_list", **filters))
    