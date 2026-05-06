"""Маршруты справочника «Типы состояния»."""

from flask import render_template, request, redirect, url_for, flash, session, current_app, send_file
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

# Блюпринт
from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

# Формы
from app.refdata.forms.refdata_for_stations.condition_type_forms import (
    ConditionTypeFilterForm,
    AddConditionTypeForm,
)

# Сервисы
from app.refdata.services.refdata_for_stations.condition_type_services import (
    condition_type_query,
    get_condition_type_list,
    update_condition_type_service,
    update_condition_type_all_versions_service, 
    add_condition_type_service,
    add_condition_type_all_versions_service, 
    delete_condition_type_service,
    export_condition_type_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/condition_type", methods=["GET", "POST"])
@login_required
def condition_type_list():
    """Маршрут для отображения списка типов состояния."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов состояния", 
        entity_type="condition_type"
    )

    # Создание формы
    form = ConditionTypeFilterForm()

    # Получение параметров запроса
    page        = request.args.get("page", 1, type=int)
    per_page    = request.args.get("per_page", 25, type=int)
    sort_by     = request.args.get("sort_by", "id")
    sort_dir    = request.args.get("sort_dir", "asc")
    condition_type_filter = request.args.get("condition_type_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page        = request.form.get("page", 1, type=int)
        per_page    = request.form.get("per_page", 25, type=int)
        sort_by     = request.form.get("sort_by", "id")
        sort_dir    = request.form.get("sort_dir", "asc")
        condition_type_filter = request.form.get("condition_type_filter", "").strip()

        # Получение данных из формы
        condition_type_ids     = request.form.getlist("condition_type_ids[]")
        condition_type_names   = request.form.getlist("condition_type_names[]")
        condition_type_delete = request.form.getlist("condition_type_delete[]")

        deleted_ids = set()
        # Удаление записей
        if condition_type_delete:
            try:
                delete_condition_type_service(condition_type_delete, user)
                deleted_ids = {int(item) for item in condition_type_delete if item}
                flash("Записи типов состоянияуспешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")

        # Обновление данных в базе
        try:
            if not condition_type_ids or not condition_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.condition_type_list",
                                        page=page,
                                        per_page=per_page,
                                        sort_by=sort_by,
                                        sort_dir=sort_dir,
                                        condition_type_filter=condition_type_filter))

           # Формирование данных для обновления
            condition_type_payload = []
            for condition_type_id, condition_type_name in zip(condition_type_ids, condition_type_names):
                if condition_type_id and int(condition_type_id) in deleted_ids:
                    continue
                condition_type_payload.append({
                    "condition_type_id": int(condition_type_id) if condition_type_id else None,
                    "name": (condition_type_name or "").strip(),
                })

            if not condition_type_payload:
                return redirect(url_for("refdata_bp.condition_type_list",
                                        page=page,
                                        per_page=per_page,
                                        sort_by=sort_by,
                                        sort_dir=sort_dir,
                                        condition_type_filter=condition_type_filter))

            # Проверка на дублирующиеся IDs
            ids = [record["condition_type_id"] for record in condition_type_payload if record["condition_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов состояния: {duplicates}")

            # Обновление данных в базе
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.condition_type_list",
                                            page=page,
                                            per_page=per_page,
                                            condition_type_filter=condition_type_filter,
                                            sort_by=sort_by,
                                            sort_dir=sort_dir))
                update_condition_type_all_versions_service(condition_type_payload, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_condition_type_service(condition_type_payload, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка сохранения типов состояния: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.condition_type_list",
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                condition_type_filter=condition_type_filter))

    pagination = get_condition_type_list(
                                    page, 
                                    per_page, 
                                    condition_type_filter, 
                                    sort_by, 
                                    sort_dir
        )

    return render_template(
        "refdata/refdata_for_stations/condition_type/condition_type.html",
        form=form,
        condition_type_list=pagination.items,
        pagination=pagination,
        condition_type_filter=condition_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@refdata_bp.route("/add_condition_type", methods=["GET", "POST"])
@login_required
def add_condition_type():
    """ Маршрут для добавления нового вида топлива. """
        
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типа состояния", 
        entity_type="condition_type"
        )

    # Создание формы
    form = AddConditionTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page        = request.args.get("page", 1, type=int)
    per_page    = request.args.get("per_page", 25, type=int)
    sort_by     = request.args.get("sort_by", "id")
    sort_dir    = request.args.get("sort_dir", "asc")
    condition_type_filter = request.args.get("condition_type_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/refdata_for_stations/condition_type/condition_type_add.html",
                form=form
            )

        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.condition_type_list",
                            page=page,
                            per_page=per_page,
                            condition_type_filter=condition_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                add_condition_type_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_condition_type_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = condition_type_query(
                            condition_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            page = min(page, last_page)

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for("refdata_bp.condition_type_list",
                                    page=last_page,
                                    per_page=per_page,
                                    sort_by=sort_by,
                                    sort_dir=sort_dir,
                                    condition_type_filter=condition_type_filter))

        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи.", "danger")

    # Рендеринг формы
    return render_template(
        "refdata/refdata_for_stations/condition_type/condition_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        condition_type_filter=condition_type_filter,
    )


@refdata_bp.route("/export_condition_type", methods=["GET"])
@login_required
def export_condition_type():
    """Маршрут для экспорта типов состояния в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by     = request.args.get("sort_by", "id")
    sort_dir    = request.args.get("sort_dir", "asc")
    condition_type_filter = request.args.get("condition_type_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_condition_type_service(
            user=user, 
            condition_type_filter=condition_type_filter, 
            sort_by=sort_by, 
            sort_dir=sort_dir)

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.condition_type_list"))

        # Формирование имени файла
        filename = f"condition_type_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.condition_type_list"))


