"""Маршруты справочника «Виды топлива»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.fuels.fuel_type_forms import (
    FuelTypeFilterForm, 
    AddFuelTypeForm,
)

# Сервисы
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_list_full,
)
from app.refdata.services.fuels.fuel_type_services import (
    fuel_type_query,
    get_fuel_type_list,
    update_fuel_type_service, 
    add_fuel_type_service, 
    delete_fuel_type_service,
    import_fuel_type_service, 
    export_fuel_type_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/fuel_type", methods=["GET", "POST"])
@login_required
def fuel_type_list():
    """Маршрут для отображения списка видов топлива."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница видов топлива")
    
    # Создание формы
    form = FuelTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 10, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_type_filter    = request.args.get("fuel_type_filter")

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 10, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        fuel_type_filter    = request.form.get("fuel_type_filter")

        # Получение данных из формы
        fuel_type_ids       = request.form.getlist("fuel_ids[]")
        fuel_type_names     = request.form.getlist("fuel_type_names[]")
        fuel_type_delete    = request.form.getlist("fuel_type_delete[]")
  
        # Удаление записей
        if fuel_type_delete:
            try:
                delete_fuel_type_service(fuel_type_delete, user)
                flash("Записи видов топлива успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления видов топлива: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.fuel_type_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    fuel_type_filter=fuel_type_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
        # Обновление данных в базе
        try:
            if not fuel_type_ids or not fuel_type_names:
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.fuel_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_type_filter=fuel_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            fuel_type_data = []
            for fuel_type_id, fuel_type_name in zip(fuel_type_ids, fuel_type_names):
                fuel_type_data.append({
                    "fuel_type_id": int(fuel_type_id) if fuel_type_id else None,
                    "name": fuel_type_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in fuel_type_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID видов топлива: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления видов топлива", str(fuel_type_data))
            update_fuel_type_service(fuel_type_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных видов топлива: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.fuel_type_list", 
                                page=page, 
                                per_page=per_page, 
                                fuel_type_filter=fuel_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_fuel_type_list(page, 
                              per_page, 
                              fuel_type_filter,
                              sort_by, 
                              sort_dir)

    return render_template(
        "refdata/fuels/fuel_type/fuel_type.html",
        form=form,
        fuel_type_list=pagination.items,
        pagination=pagination,
        fuel_type_filter=fuel_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@refdata_bp.route("/add_fuel_type", methods=["GET", "POST"])
@login_required
def add_fuel_type():
    """ Маршрут для добавления нового топлива. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления видов топлива")

    # Создание формы
    form = AddFuelTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    fuel_type_filter = request.args.get("fuel_type_filter")
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            add_fuel_type_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = fuel_type_query(fuel_type_filter).count
            last_page = (total_records + per_page - 1) // per_page
            
            # Пересчет последней страницы (без дубля логики сервиса)
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.fuel_type_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                fuel_type_filter=fuel_type_filter,
                per_page=per_page,
                page=last_page,
            ))

        except ValueError as e:
             # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления субъекта РФ", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/fuels/fuel_type/fuel_type_add.html",
        form=form,
        sort_by=sort_by,
        sort_dir=sort_dir,
        fuel_type_filter=fuel_type_filter,
        per_page=per_page,
        page=page,
    )


@refdata_bp.route("/import_fuel_type", methods=["POST"])
@login_required
def import_fuel_type():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт видов топлива из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.fuel_type_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.fuel_type_list"))

    try:
        imported_count = import_fuel_type_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.fuel_type_list"))


@refdata_bp.route("/export_fuel_type", methods=["GET"])
@login_required
def export_fuel_type():
    """Маршрут для экспорта данных в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    fuel_type_filter    = request.args.get("fuel_type_filter")
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_fuel_type_service(
            user=user,
            fuel_type_filter=fuel_type_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.fuel_type_list"))
        
        # Формирование имени файла
        filename = f"fuel_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.fuel_type_list"))