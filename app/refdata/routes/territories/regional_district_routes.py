"""Маршруты справочника «Субъекты РФ»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.territories.regional_district_forms import (
    RegionalDistrictFilterForm, 
    AddRegionalDistrictForm,
)

# Сервисы
from app.common.services.get_services.territories.regional_district_get_services import (
    get_total_regional_district_records,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list,
)
from app.common.services.get_services.energy_systems.energy_zone_get_services import (
    get_energy_zone_list,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list,
)
from app.refdata.services.territories.regional_district_services import (
    get_regional_district_list,
    update_regional_district_service, 
    add_regional_district_service, 
    delete_regional_district_service,
    import_regional_district_service, 
    export_regional_district_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/regional_district", methods=["GET", "POST"])
@login_required
def regional_district_list():
    """Маршрут для отображения списка субъектов РФ."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница субъектов РФ")
    
    # Создание формы
    form = RegionalDistrictFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    region_ids = request.args.getlist("region_ids[]")
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter = request.args.get("federal_district_filter")
    energy_zone_filter = request.args.get("energy_zone_filter")
    synchronous_area_filter = request.args.get("synchronous_area_filter")
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        regional_district_filter = request.form.get("regional_district_filter", "").strip()
        federal_district_filter = request.form.get("federal_district_filter")
        energy_zone_filter = request.args.get("energy_zone_filter")
        synchronous_area_filter = request.args.get("synchronous_area_filter")

        # Получение данных из формы
        region_ids = request.form.getlist("region_ids[]")
        regional_district_ids = request.form.getlist("regional_district_ids[]")
        regional_district_names = request.form.getlist("regional_district_names[]")
        regional_district_full_names = request.form.getlist("regional_district_full_names[]")
        regional_district_delete = request.form.getlist("regional_district_delete[]")
        federal_district_ids = request.form.getlist("federal_districts[]")
        energy_zone_ids = request.form.getlist("energy_zones[]")
        synchronous_area_ids = request.form.getlist("synchronous_areas[]")

        # Удаление записей
        if regional_district_delete:
            try:
                delete_regional_district_service(regional_district_delete, user)
                flash("Записи субъектов РФ успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления субъектов РФ: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.regional_district_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    regional_district_filter=regional_district_filter,
                                    federal_district_filter=federal_district_filter,
                                    energy_zone_filter=energy_zone_filter,
                                    synchronous_area_filter=synchronous_area_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not regional_district_ids:
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.regional_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        regional_district_filter=regional_district_filter,
                                        federal_district_filter=federal_district_filter,
                                        energy_zone_filter=energy_zone_filter,
                                        synchronous_area_filter=synchronous_area_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
            
            # Формирование данных для обновления
            regional_district_data = []
            for regional_district_id, regional_district_name, regional_district_full_name, federal_district_id, energy_zone_id, synchronous_area_id, region_id in zip(
                regional_district_ids, regional_district_names, regional_district_full_names, federal_district_ids, energy_zone_ids, synchronous_area_ids, region_ids
            ):
                try:
                    regional_district_data.append({
                        "regional_district_id": int(regional_district_id) if regional_district_id else None,
                        "region_id": int(region_id) if region_id else None,
                        "name": regional_district_name.strip(),
                        "name_full": regional_district_full_name.strip(),
                        "federal_district_id": int(federal_district_id) if federal_district_id else None,
                        "energy_zone_id": int(energy_zone_id) if energy_zone_id else None,
                        "id_synchronous_area": int(synchronous_area_id) if synchronous_area_id else None,
                    })
                except ValueError as e:
                    raise ValueError(
                        f"Ошибка обработки данных: "
                        f"regional_district_id={regional_district_id}, "
                        f"region_id={region_id}, "
                        f"name={regional_district_name}, "
                        f"name_full={regional_district_full_name}, "
                        f"federal_district_id={federal_district_id}, "
                        f"energy_zone_id={energy_zone_id}, "
                        f"synchronous_area_id={synchronous_area_id}. "
                        f"Ошибка: {e}"
                    )
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in regional_district_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            # Обновление данных в базе
            update_regional_district_service(regional_district_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.regional_district_list", 
                                page=page, 
                                per_page=per_page, 
                                regional_district_filter=regional_district_filter,
                                federal_district_filter=federal_district_filter,
                                energy_zone_filter=energy_zone_filter,
                                synchronous_area_filter=synchronous_area_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_regional_district_list(page, 
                              per_page, 
                              regional_district_filter,
                              federal_district_filter,
                              energy_zone_filter,
                              synchronous_area_filter,
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    federal_districts = get_federal_district_list()
    form.federal_district.choices = [(fd.id, fd.name) for fd in federal_districts]

    energy_zones = get_energy_zone_list()
    form.energy_zone.choices = [(ez.id, ez.number, ez.name) for ez in energy_zones]

    synchronous_areas = get_synchronous_area_list()
    form.synchronous_area.choices = [(sa.id, sa.name) for sa in synchronous_areas]

    return render_template(
        "refdata/territories/regional_district/regional_district.html",
        form=form,
        regional_districts_list=pagination.items,
        pagination=pagination,
        federal_district_list=form.federal_district.choices,
        energy_zone_list=form.energy_zone.choices,
        synchronous_area_list=form.synchronous_area.choices,
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_regional_district", methods=["GET", "POST"])
@login_required
def add_regional_district():
    """ Маршрут для добавления нового субъекта РФ."""

    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Открыта страница добавления субъекта РФ")

    # Создание формы
    form = AddRegionalDistrictForm()

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    regional_district_filter = (request.args.get("regional_district_filter") or "").strip()
    federal_district_filter = request.args.get("federal_district_filter")
    energy_zone_filter = request.args.get("energy_zone_filter")
    synchronous_area_filter = request.args.get("synchronous_area_filter")
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))
    
    # Получение списка федеральных округов
    try:
        federal_districts = get_federal_district_list()
        if not federal_districts:
            flash("Ошибка: отсутствует список федеральных округов. Добавьте ФО перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют федеральные округа")
            return redirect(url_for("refdata_bp.regional_district_list"))
        form.federal_district.choices = [(t.id, t.name) for t in federal_districts]
    except Exception as e:
        current_app.logger.error(f"Ошибка получения списка ФО: {e}")
        flash("Ошибка при загрузке списка федеральных округов.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "name_full": (form.name_full.data or "").strip(),
                "id_federal_district": form.federal_district.data,
            }]

            # Добавление новой записи через сервис
            add_regional_district_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            log_to_db(user, "Добавление нового субъекта РФ", 
                      f"Имя: {form.name.data}, Полное имя: {form.name_full.data}, ФО: {form.federal_district.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_regional_district_records(
                                regional_district_filter, 
                                federal_district_filter, 
                                energy_zone_filter, 
                                synchronous_area_filter)
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.regional_district_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                regional_district_filter=regional_district_filter,
                federal_district_filter=federal_district_filter,
                energy_zone_filter=energy_zone_filter,
                synchronous_area_filter=synchronous_area_filter,
                per_page=per_page,
                page=last_page,
            ))

        except ValueError as e:
             # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового субъекта РФ", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления субъекта РФ", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/territories/regional_district/regional_district_add.html",
        form=form,
        federal_district=form.federal_district.choices,
        sort_by=sort_by,
        sort_dir=sort_dir,
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
        per_page=per_page,
        page=page,
    )


@refdata_bp.route("/import_regional_district", methods=["POST"])
@login_required
def import_regional_district():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт списка субъектов РФ из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))

    try:
        imported_count = import_regional_district_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.regional_district_list"))


@refdata_bp.route("/export_regional_district", methods=["GET"])
@login_required
def export_regional_district():
    """Маршрут для экспорта данных в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter  = request.args.get("federal_district_filter")
    energy_zone_filter       = request.args.get("energy_zone_filter")
    synchronous_area_filter  = request.args.get("synchronous_area_filter")
    sort_by                  = request.args.get("sort_by", "id")
    sort_dir                 = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_regional_district_service(
                user=user,
                regional_district_filter=regional_district_filter,
                federal_district_filter=federal_district_filter,
                energy_zone_filter=energy_zone_filter,
                synchronous_area_filter=synchronous_area_filter,
                sort_by=sort_by,
                sort_dir=sort_dir,
        )
        log_to_db(user, "Экспорт завершён", f"Фильтр: {regional_district_filter, federal_district_filter, energy_zone_filter, synchronous_area_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")


        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.regional_district_list"))
        
        # Формирование имени файла
        filename = f"regional_district_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)

        # Возврат файла через send_file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )


    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.regional_district_list"))