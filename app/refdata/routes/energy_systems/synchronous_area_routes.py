"""Маршруты справочника «Синхронные зоны»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.synchronous_area_forms import (
    SynchronousAreaFilterForm, 
    AddSynchronousAreaForm,
)

# Сервисы
from app.refdata.services.energy_systems.synchronous_area_services import (
    synchronous_area_query,
    get_synchronous_area_list,
    update_synchronous_area_service,
    add_synchronous_area_service,
    delete_synchronous_area_service,
    export_synchronous_area_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/synchronous_area", methods=["GET", "POST"])
@login_required
def synchronous_area_list():
    """Маршрут для отображения списка синхронных зон."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница синхронных зон")
    
    # Создание формы
    form = SynchronousAreaFilterForm()

    # Получение параметров запроса
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 20, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    synchronous_area_filter     = request.args.get("synchronous_area_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                        = request.form.get("page", 1, type=int)
        per_page                    = request.form.get("per_page", 20, type=int)
        sort_by                     = request.form.get("sort_by", "id")
        sort_dir                    = request.form.get("sort_dir", "asc")
        synchronous_area_filter     = request.form.get("synchronous_area_filter", "").strip()

        # Получение данных из формы
        synchronous_area_ids        = request.form.getlist("synchronous_area_ids[]")
        synchronous_area_numbers    = request.form.getlist("synchronous_area_numbers[]")
        synchronous_area_names      = request.form.getlist("synchronous_area_names[]")
        synchronous_area_delete     = request.form.getlist("synchronous_area_delete[]")
  
        # Удаление записей
        if synchronous_area_delete:
            try:
                delete_synchronous_area_service(synchronous_area_delete, user)
                flash("Записи синхронных зон успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления синхронных зон: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.synchronous_area_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    synchronous_area_filter=synchronous_area_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not (synchronous_area_ids and synchronous_area_names):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.synchronous_area_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        synchronous_area_filter=synchronous_area_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            synchronous_area_data = []
            for synchronous_area_id, synchronous_area_number, synchronous_area_name in zip(
                synchronous_area_ids, synchronous_area_numbers, synchronous_area_names
            ):
                try:
                    synchronous_area_data.append({
                        "synchronous_area_id": int(synchronous_area_id) if synchronous_area_id else None,
                        "number": synchronous_area_number.strip(),
                        "name": synchronous_area_name.strip(),
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={synchronous_area_id},"
                            f"Номер: {synchronous_area_number}, "
                            f"Наименование: {synchronous_area_name}, "
                            f"Ошибка: {str(e)}"
                        )
                    )

            # Проверка на дублирующиеся IDs
            ids = [record["synchronous_area_id"] for record in synchronous_area_data if record["synchronous_area_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID синхронных зон: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления синхронных зон", str(synchronous_area_data))
            update_synchronous_area_service(synchronous_area_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных синхронных зон: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.synchronous_area_list", 
                                page=page, 
                                per_page=per_page, 
                                synchronous_area_filter=synchronous_area_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_synchronous_area_list(page, 
                              per_page, 
                              synchronous_area_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "refdata/energy_systems/synchronous_area/synchronous_area.html",
        form=form,
        synchronous_area_list=pagination.items,
        pagination=pagination,
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_synchronous_area", methods=["GET", "POST"])
@login_required
def add_synchronous_area():
    """ Маршрут для добавления новой cинхронной зоны. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления синхронной зоны")

    # Создание формы
    form = AddSynchronousAreaForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 20, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    synchronous_area_filter     = request.args.get("synchronous_area_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/energy_systems/synchronous_area/synchronous_area_add.html",
                form=form
            )
        
        try:
            payload = [{
                "number": (form.number.data or "").strip(),
                "name": (form.name.data or "").strip(),
            }]
                        
            # Добавление новой записи
            add_synchronous_area_service(payload, user)
            log_to_db(user, "Добавление новой синхронной зоны", 
                    (
                        f"Номер: {form.number.data},"
                        f"Наименование: {form.name.data}"
                    )
            )
            flash("Новая запись успешно добавлена.", "success")

             # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = synchronous_area_query(
                                synchronous_area_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.synchronous_area_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                synchronous_area_filter=synchronous_area_filter,
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления новой синхронной зоны", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления новой синхронной зоны", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/energy_systems/synchronous_area/synchronous_area_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form,
        synchronous_area_filter=synchronous_area_filter, 
    )


@refdata_bp.route("/export_synchronous_area", methods=["GET"])
@login_required
def export_synchronous_area():
    """Маршрут для экспорта синхронных зон в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат экспорт списка синхронных зон в Excel")
    
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    synchronous_area_filter     = request.args.get("synchronous_area_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_synchronous_area_service(
                        user, 
                        sort_by, 
                        sort_dir,
                        synchronous_area_filter, 
        )
        log_to_db(user, "Экспорт завершен", 
                (
                    f"Фильтр: {synchronous_area_filter},"
                    f"Сортировка: {sort_by}, "
                    f"Направление: {sort_dir}"
                )
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.synchronous_area_list"))
        
        # Формирование имени файла
        filename = f"synchronous_area_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Возврат файла через send_file
        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.synchronous_area_list"))