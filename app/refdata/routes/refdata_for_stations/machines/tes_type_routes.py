"""Маршруты справочника «Типы ТЭС»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.refdata_for_stations.machines.tes_type_forms import (
    TesTypeFilterForm, 
    AddTesTypeForm,
)

# Сервисы
from app.refdata.services.refdata_for_stations.machines.tes_type_services import (
    tes_type_query,
    get_tes_type_list,
    update_tes_type_service, 
    add_tes_type_service, 
    delete_tes_type_service,
    export_tes_type_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/tes_type", methods=["GET", "POST"])
@login_required
def tes_type_list():
    """Маршрут для отображения списка типов ТЭС."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов ТЭС", 
        entity_type="tes_type")
    
    # Создание формы
    form = TesTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    tes_type_filter    = request.args.get("tes_type_filter")

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        tes_type_filter    = request.form.get("tes_type_filter")

        # Получение данных из формы
        tes_type_ids       = request.form.getlist("tes_ids[]")
        tes_type_names     = request.form.getlist("tes_type_names[]")
        tes_type_delete    = request.form.getlist("tes_type_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if tes_type_delete:
            try:
                delete_tes_type_service(tes_type_delete, user)
                deleted_ids = {int(item) for item in tes_type_delete if item}
                flash("Записи типов ТЭС успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not tes_type_ids or not tes_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.tes_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        tes_type_filter=tes_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            tes_type_data = []
            for tes_type_id, tes_type_name in zip(tes_type_ids, tes_type_names):
                if tes_type_id and int(tes_type_id) in deleted_ids:
                    continue
                tes_type_data.append({
                    "tes_type_id": int(tes_type_id) if tes_type_id else None,
                    "name": tes_type_name.strip(),
                })
            
            if not tes_type_data:
                return redirect(url_for("refdata_bp.tes_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        tes_type_filter=tes_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["tes_type_id"] for record in tes_type_data if record["tes_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов ТЭС: {duplicates}")

            # Обновление данных в базе
            update_tes_type_service(tes_type_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.tes_type_list", 
                                page=page, 
                                per_page=per_page, 
                                tes_type_filter=tes_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_tes_type_list(
                                page, 
                                per_page, 
                                tes_type_filter,
                                sort_by, 
                                sort_dir)

    return render_template(
        "refdata/refdata_for_stations/machines/tes_type/tes_type.html",
        form=form,
        tes_type_list=pagination.items,
        pagination=pagination,
        tes_type_filter=tes_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_tes_type", methods=["GET", "POST"])
@login_required
def add_tes_type():
    """ Маршрут для добавления нового типа ТЭС. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типов ТЭС", 
        entity_type="tes_type")

    # Создание формы
    form = AddTesTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    tes_type_filter    = request.args.get("tes_type_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/tess/tes_type/tes_type_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            add_tes_type_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = tes_type_query(
                                tes_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.tes_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                tes_type_filter=tes_type_filter,
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
        "refdata/refdata_for_stations/machines/tes_type/tes_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        tes_type_filter=tes_type_filter,
    )


@refdata_bp.route("/export_tes_type", methods=["GET"])
@login_required
def export_tes_type():
    """Маршрут для экспорта типов ТЭС в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    tes_type_filter    = request.args.get("tes_type_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_tes_type_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        tes_type_filter=tes_type_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.tes_type_list"))
        
        # Формирование имени файла
        filename = f"tes_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.tes_type_list"))