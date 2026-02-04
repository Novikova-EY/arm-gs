"""Маршруты справочника «Типы групп оборудования»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.refdata_for_stations.technologies.equipment_group_forms import (
    EquipmentGroupFilterForm, 
    AddEquipmentGroupForm,
)

# Сервисы
from app.common.services.get_services.refdata_for_stations.technologies.technology_type_get_services import (
    get_technology_type_list_full, 
)
from app.common.services.get_services.refdata_for_stations.technologies.technology_availability_get_services import (
    get_technology_availability_list_full, 
)
from app.refdata.services.refdata_for_stations.technologies.equipment_group_services import (
    equipment_group_query,
    get_equipment_group_list,
    update_equipment_group_service, 
    add_equipment_group_service, 
    delete_equipment_group_service,
    export_equipment_group_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


def _normalize_filter(value):
    """
    Приводит строковые фильтры к нормальному виду:
    - None, пустая строка и строка 'None' -> None
    - остальные значения возвращаются как строка без пробелов по краям
    """
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
    else:
        v = str(value).strip()
    if v == "" or v.lower() == "none":
        return None
    return v


@refdata_bp.route("/equipment_group", methods=["GET", "POST"])
@login_required
def equipment_group_list():
    """Маршрут для отображения списка типов групп оборудования."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов групп оборудования", 
        entity_type="equipment_group")
    
    # Создание формы
    form = EquipmentGroupFilterForm()

    # Получение параметров запроса
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 25, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    equipment_group_filter          = _normalize_filter(request.args.get("equipment_group_filter"))
    technology_type_filter          = _normalize_filter(request.args.get("technology_type_filter"))
    technology_availability_filter  = _normalize_filter(request.args.get("technology_availability_filter"))

    if request.method == "POST":       
        # Обновление параметров из формы
        page                            = request.form.get("page", 1, type=int)
        per_page                        = request.form.get("per_page", 25, type=int)
        sort_by                         = request.form.get("sort_by", "id")
        sort_dir                        = request.form.get("sort_dir", "asc")
        equipment_group_filter          = _normalize_filter(request.form.get("equipment_group_filter"))
        technology_type_filter          = _normalize_filter(request.form.get("technology_type_filter"))
        technology_availability_filter  = _normalize_filter(request.form.get("technology_availability_filter"))
        
        # Получение данных из формы
        equipment_group_ids             = request.form.getlist("equipment_group_ids[]")
        equipment_group_names           = request.form.getlist("equipment_group_names[]")
        equipment_group_delete          = request.form.getlist("equipment_group_delete[]")
        technology_types                = request.form.getlist("technology_types[]")
        technology_availabilities        = request.form.getlist("technology_availabilities[]")
        display_orders                  = request.form.getlist("display_orders[]")
  
        deleted_ids = set()
        # Удаление записей
        if equipment_group_delete:
            try:
                delete_result = delete_equipment_group_service(equipment_group_delete, user)
                deleted_ids = set(delete_result.get("deleted_ids", []))
                if delete_result.get("deleted", 0) > 0:
                    flash("Записи типов групп оборудования успешно удалены.", "success")
                if delete_result.get("blocked"):
                    blocked_names = delete_result.get("blocked_names", [])
                    flash(
                        "Некоторые записи не удалены, так как используются в сборных группах оборудования: "
                        + ", ".join(blocked_names),
                        "warning",
                    )
                if delete_result.get("not_found"):
                    flash(f"Не найдены ID: {delete_result.get('not_found')}", "warning")
                if delete_result.get("invalid"):
                    flash(f"Некорректные ID: {delete_result.get('invalid')}", "warning")
            except Exception:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not equipment_group_ids or not equipment_group_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.equipment_group_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        equipment_group_filter=equipment_group_filter,
                                        technology_type_filter=technology_type_filter, 
                                        technology_availability_filter=technology_availability_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            equipment_group_data = []
            for equipment_group_id, display_order, equipment_group_name, technology_type, technology_availability in zip(
                equipment_group_ids, display_orders, equipment_group_names, technology_types, technology_availabilities
            ):
                if equipment_group_id and int(equipment_group_id) in deleted_ids:
                    continue
                try:
                    equipment_group_data.append({
                        "equipment_group_id": int(equipment_group_id) if equipment_group_id else None,
                        "display_order": int(display_order) if display_order and str(display_order).strip() else None,
                        "name": equipment_group_name.strip(),
                        "technology_type_id": int(technology_type) if technology_type else None,
                        "technology_availability_id": int(technology_availability) if technology_availability else None
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={equipment_group_id}, "
                            f"Порядок отображения: {display_order}, "
                            f"Наименование: {equipment_group_name}, "
                            f"Тип технологии: {technology_type}, "
                            f"Доступность технологии: {technology_availability}. "
                            f"Ошибка: {str(e)}"
                        )
                    )
            
            if not equipment_group_data:
                return redirect(url_for("refdata_bp.equipment_group_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        equipment_group_filter=equipment_group_filter,
                                        technology_type_filter=technology_type_filter, 
                                        technology_availability_filter=technology_availability_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["equipment_group_id"] for record in equipment_group_data if record["equipment_group_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов групп оборудования: {duplicates}")

            # Обновление данных в базе
            update_equipment_group_service(equipment_group_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.equipment_group_list", 
                                page=page, 
                                per_page=per_page, 
                                equipment_group_filter=equipment_group_filter,
                                technology_type_filter=technology_type_filter, 
                                technology_availability_filter=technology_availability_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_equipment_group_list(
                                page, 
                                per_page, 
                                equipment_group_filter,
                                technology_type_filter,
                                technology_availability_filter,
                                sort_by, 
                                sort_dir)


    # Подготовка данных для формы
    technology_types = get_technology_type_list_full()
    form.technology_type.choices = [(t.id, t.name) for t in technology_types]
    technology_availabilities = get_technology_availability_list_full()
    form.technology_availability.choices = [(t.id, t.name) for t in technology_availabilities]

    return render_template(
        "refdata/refdata_for_stations/technologies/equipment_group/equipment_group.html",
        form=form,
        equipment_group_list=pagination.items,
        pagination=pagination,
        technology_types=form.technology_type.choices,
        technology_availabilities=form.technology_availability.choices,
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=technology_type_filter,
        technology_availability_filter=technology_availability_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_equipment_group", methods=["GET", "POST"])
@login_required
def add_equipment_group():
    """ Маршрут для добавления нового типа группы оборудования. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типов групп оборудования", 
        entity_type="equipment_group")

    # Создание формы
    form = AddEquipmentGroupForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    equipment_group_filter    = request.args.get("equipment_group_filter", "").strip()
    technology_type_filter    = request.args.get("technology_type_filter", "").strip()
    technology_availability_filter    = request.args.get("technology_availability_filter", "").strip()

    # Подготовка данных для формы
    technology_types = get_technology_type_list_full()
    form.technology_type.choices = [(t.id, t.name) for t in technology_types]
    technology_availabilities = get_technology_availability_list_full()
    form.technology_availability.choices = [(t.id, t.name) for t in technology_availabilities]

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "technology_type_id": form.technology_type.data,
                "technology_availability_id": form.technology_availability.data,
            }]

            # Добавление новой записи через сервис
            add_equipment_group_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = equipment_group_query(
                                equipment_group_filter,
                                technology_type_filter,
                                technology_availability_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.equipment_group_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                equipment_group_filter=equipment_group_filter,
                technology_type_filter=technology_type_filter,
                technology_availability_filter=technology_availability_filter,
            ))

        except ValueError as e:
             # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")

    # Рендеринг формы
    return render_template(
        "refdata/refdata_for_stations/technologies/equipment_group/equipment_group_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=technology_type_filter,
        technology_availability_filter=technology_availability_filter,
    )


@refdata_bp.route("/export_equipment_group", methods=["GET"])
@login_required
def export_equipment_group():
    """Маршрут для экспорта типов групп оборудования в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    equipment_group_filter    = request.args.get("equipment_group_filter")
    technology_type_filter    = request.args.get("technology_type_filter")
    technology_availability_filter    = request.args.get("technology_availability_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_equipment_group_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        equipment_group_filter=equipment_group_filter,
                        technology_type_filter=technology_type_filter,
                        technology_availability_filter=technology_availability_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.equipment_group_list",
                                    equipment_group_filter=equipment_group_filter,
                                    technology_type_filter=technology_type_filter,
                                    technology_availability_filter=technology_availability_filter,
                                    sort_by=sort_by,
                                    sort_dir=sort_dir))
        
        # Формирование имени файла
        filename = f"equipment_group_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.equipment_group_list"))