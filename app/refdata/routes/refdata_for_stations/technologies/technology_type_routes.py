"""Маршруты справочника «Типы технологий»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.refdata_for_stations.technologies.technology_type_forms import (
    TechnologyTypeFilterForm, 
    AddTechnologyTypeForm,
)

# Сервисы
from app.refdata.services.refdata_for_stations.technologies.technology_type_services import (
    technology_type_query,
    get_technology_type_list,
    update_technology_type_service, 
    add_technology_type_service, 
    delete_technology_type_service,
    export_technology_type_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/technology_type", methods=["GET", "POST"])
@login_required
def technology_type_list():
    """Маршрут для отображения списка типов технологий."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов технологий", 
        entity_type="technology_type")
    
    # Создание формы
    form = TechnologyTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    technology_type_filter    = request.args.get("technology_type_filter")

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        technology_type_filter    = request.form.get("technology_type_filter")

        # Получение данных из формы
        technology_type_ids       = request.form.getlist("technology_ids[]")
        technology_type_names     = request.form.getlist("technology_type_names[]")
        technology_type_delete    = request.form.getlist("technology_type_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if technology_type_delete:
            try:
                delete_technology_type_service(technology_type_delete, user)
                deleted_ids = {int(item) for item in technology_type_delete if item}
                flash("Записи типов технологий успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not technology_type_ids or not technology_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.technology_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        technology_type_filter=technology_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            technology_type_data = []
            for technology_type_id, technology_type_name in zip(technology_type_ids, technology_type_names):
                if technology_type_id and int(technology_type_id) in deleted_ids:
                    continue
                technology_type_data.append({
                    "technology_type_id": int(technology_type_id) if technology_type_id else None,
                    "name": technology_type_name.strip(),
                })
            
            if not technology_type_data:
                return redirect(url_for("refdata_bp.technology_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        technology_type_filter=technology_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["technology_type_id"] for record in technology_type_data if record["technology_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов технологий: {duplicates}")

            # Обновление данных в базе
            update_technology_type_service(technology_type_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.technology_type_list", 
                                page=page, 
                                per_page=per_page, 
                                technology_type_filter=technology_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_technology_type_list(
                                page, 
                                per_page, 
                                technology_type_filter,
                                sort_by, 
                                sort_dir)

    return render_template(
        "refdata/refdata_for_stations/technologies/technology_type/technology_type.html",
        form=form,
        technology_type_list=pagination.items,
        pagination=pagination,
        technology_type_filter=technology_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_technology_type", methods=["GET", "POST"])
@login_required
def add_technology_type():
    """ Маршрут для добавления нового типа технологии. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типов технологий", 
        entity_type="technology_type")

    # Создание формы
    form = AddTechnologyTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    technology_type_filter    = request.args.get("technology_type_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/technologies/technology_type/technology_type_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            add_technology_type_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = technology_type_query(
                                technology_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.technology_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                technology_type_filter=technology_type_filter,
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
        "refdata/refdata_for_stations/technologies/technology_type/technology_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        technology_type_filter=technology_type_filter,
    )


@refdata_bp.route("/export_technology_type", methods=["GET"])
@login_required
def export_technology_type():
    """Маршрут для экспорта типов технологий в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    technology_type_filter    = request.args.get("technology_type_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_technology_type_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        technology_type_filter=technology_type_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.technology_type_list"))
        
        # Формирование имени файла
        filename = f"technology_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.technology_type_list"))