"""Маршруты справочника «Виды экономической деятельности»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

# Блюпринт
from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

# Формы
from app.refdata.forms.economic_activity.economic_activity_type_forms import (
    EconomicActivityTypeFilterForm, 
    AddEconomicActivityTypeForm,
)

# Сервисы
from app.refdata.services.economic_activity.economic_activity_type_services import (
    economic_activity_type_query,
    get_economic_activity_type_list,
    update_economic_activity_type_service, 
    update_economic_activity_type_all_versions_service, 
    add_economic_activity_type_service, 
    add_economic_activity_type_all_versions_service, 
    delete_economic_activity_type_service,
    export_economic_activity_type_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/ved", methods=["GET", "POST"])
@login_required
def economic_activity_type_list():
    """Маршрут для отображения списка видов экономической деятельности."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница видов экономической деятельности", 
        entity_type="economic_activity_type")
    
    # Создание формы
    form = EconomicActivityTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    _tf = request.args.get("economic_activity_type_filter") or ""
    economic_activity_type_filter    = "" if str(_tf) == "None" else str(_tf)

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "display_order")
        sort_dir            = request.form.get("sort_dir", "asc")
        _tf = request.form.get("economic_activity_type_filter") or ""
        economic_activity_type_filter    = "" if _tf == "None" else _tf.strip()

        # Получение данных из формы
        economic_activity_type_ids       = request.form.getlist("economic_activity_ids[]")
        economic_activity_type_names     = request.form.getlist("economic_activity_type_names[]")
        economic_activity_type_names_2   = request.form.getlist("economic_activity_type_names_2[]")
        economic_activity_type_delete    = request.form.getlist("economic_activity_type_delete[]")
        display_orders            = request.form.getlist("display_orders[]")
  
        deleted_ids = set()
        delete_failed = False
        # Удаление записей
        if economic_activity_type_delete:
            try:
                delete_result = delete_economic_activity_type_service(
                    economic_activity_type_delete, user
                )
                deleted_count = delete_result.get("deleted", 0)
                deleted_ids = set(delete_result.get("deleted_ids") or [])
                if deleted_count:
                    flash(
                        f"Удалено видов экономической деятельности: {deleted_count}.",
                        "success",
                    )
                elif delete_result.get("not_found"):
                    flash(
                        "Выбранные записи не найдены в текущей версии БД.",
                        "warning",
                    )
            except ValueError as e:
                flash(str(e), "danger")
                delete_failed = True
            except Exception:
                flash("Ошибка удаления записей.", "danger")
                delete_failed = True

        if delete_failed:
            return redirect(url_for("refdata_bp.economic_activity_type_list",
                                    page=page,
                                    per_page=per_page,
                                    economic_activity_type_filter=economic_activity_type_filter,
                                    sort_by=sort_by,
                                    sort_dir=sort_dir))

        # Обновление данных в базе
        try:
            if not economic_activity_type_ids or not economic_activity_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.economic_activity_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        economic_activity_type_filter=economic_activity_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            n = len(economic_activity_type_ids)
            display_orders_padded = (display_orders + [""] * n)[:n]  # дополняем пустыми до n
            names_padded = (list(economic_activity_type_names) + [""] * n)[:n]
            names_2_padded = (list(economic_activity_type_names_2) + [""] * n)[:n]
            economic_activity_type_data = []
            # Порядок полей в строке таблицы: id → порядок отображения → наименование → наименование_2
            for economic_activity_type_id, display_order, economic_activity_type_name, economic_activity_type_name_2 in zip(
                economic_activity_type_ids, display_orders_padded, names_padded, names_2_padded
            ):
                if economic_activity_type_id and int(economic_activity_type_id) in deleted_ids:
                    continue
                try:
                    do_val = int(display_order) if display_order and str(display_order).strip() else None
                except (TypeError, ValueError):
                    do_val = None
                economic_activity_type_data.append({
                    "economic_activity_type_id": int(economic_activity_type_id) if economic_activity_type_id else None,
                    "name": economic_activity_type_name.strip(),
                    "name_2": economic_activity_type_name_2.strip() or None,
                    "display_order": do_val,
                })
            
            if not economic_activity_type_data:
                return redirect(url_for("refdata_bp.economic_activity_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        economic_activity_type_filter=economic_activity_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["economic_activity_type_id"] for record in economic_activity_type_data if record["economic_activity_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID видов экономической деятельности: {duplicates}")

            # Обновление данных в базе
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.economic_activity_type_list",
                            page=page,
                            per_page=per_page,
                            economic_activity_type_filter=economic_activity_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                update_economic_activity_type_all_versions_service(economic_activity_type_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_economic_activity_type_service(economic_activity_type_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.economic_activity_type_list", 
                                page=page, 
                                per_page=per_page, 
                                economic_activity_type_filter=economic_activity_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_economic_activity_type_list(
                                page, 
                                per_page, 
                                economic_activity_type_filter,
                                sort_by, 
                                sort_dir)

    return render_template(
        "refdata/economic_activity/economic_activity_type/economic_activity_type.html",
        form=form,
        economic_activity_type_list=pagination.items,
        pagination=pagination,
        economic_activity_type_filter=economic_activity_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_ved", methods=["GET", "POST"])
@login_required
def add_economic_activity_type():
    """ Маршрут для добавления нового вида экономической деятельности. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления видов экономической деятельности", 
        entity_type="economic_activity_type")

    # Создание формы
    form = AddEconomicActivityTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    economic_activity_type_filter    = request.args.get("economic_activity_type_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/economic_activity/economic_activity_type/economic_activity_type_add.html",
                form=form,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                economic_activity_type_filter=economic_activity_type_filter,
            )
        
        try:
            display_order = form.display_order.data  # IntegerField: None если пусто
            payload = [{
                "name": (form.name.data or "").strip(),
                "name_2": (form.name_2.data or "").strip() or None,
                "display_order": display_order,
            }]

            # Добавление новой записи через сервис
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.economic_activity_type_list",
                            page=page,
                            per_page=per_page,
                            economic_activity_type_filter=economic_activity_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                add_economic_activity_type_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_economic_activity_type_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = economic_activity_type_query(
                                economic_activity_type_filter=economic_activity_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.economic_activity_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                economic_activity_type_filter=economic_activity_type_filter,
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
        "refdata/economic_activity/economic_activity_type/economic_activity_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        economic_activity_type_filter=economic_activity_type_filter,
    )


@refdata_bp.route("/export_ved", methods=["GET"])
@login_required
def export_economic_activity_type():
    """Маршрут для экспорта видов экономической деятельности в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    economic_activity_type_filter    = request.args.get("economic_activity_type_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_economic_activity_type_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        economic_activity_type_filter=economic_activity_type_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.economic_activity_type_list"))
        
        # Формирование имени файла
        filename = f"economic_activity_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.economic_activity_type_list"))