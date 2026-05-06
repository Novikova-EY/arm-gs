"""Маршруты справочника «Типы энергосистем»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

# Блюпринт
from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

# Формы
from app.refdata.forms.energy_systems.energy_system_type_forms import (
    EnergySystemTypeFilterForm,
    AddEnergySystemTypeForm,
)

# Сервисы
from app.refdata.services.energy_systems.energy_system_type_services import (
    energy_system_type_query,
    get_energy_system_type_list,
    update_energy_system_type_service,
    update_energy_system_type_all_versions_service, 
    add_energy_system_type_service,
    add_energy_system_type_all_versions_service, 
    delete_energy_system_type_service,
    export_energy_system_type_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/energy_system_type", methods=["GET", "POST"])
@login_required
def energy_system_type_list():
    """Маршрут для отображения списка типов частей энергосистемы России."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов частей энергосистемы России", 
        entity_type="energy_system_type")

    # Создание формы
    form = EnergySystemTypeFilterForm()

    # Получение параметров запроса
    page                        = request.args.get("page", 1, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    per_page                    = request.args.get("per_page", 25, type=int)
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                        = request.form.get("page", 1, type=int)
        per_page                    = request.form.get("per_page", 25, type=int)
        sort_by                     = request.form.get("sort_by", "id")
        sort_dir                    = request.form.get("sort_dir", "asc")
        energy_system_type_filter   = request.form.get("energy_system_type_filter", "").strip()

        # Получение данных из формы
        energy_system_type_ids      = request.form.getlist("energy_system_type_ids[]")
        energy_system_type_names    = request.form.getlist("energy_system_type_names[]")
        energy_system_type_delete   = request.form.getlist("energy_system_type_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if energy_system_type_delete:
            try:
                delete_energy_system_type_service(energy_system_type_delete, user)
                deleted_ids = {int(item) for item in energy_system_type_delete if item}
                flash("Записи типов частей энергосистемы России успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
           
        # Обновление данных в базе
        try:
            if not (energy_system_type_ids and energy_system_type_names):
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.energy_system_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        energy_system_type_filter=energy_system_type_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            energy_system_type_data = []
            for energy_system_type_id, energy_system_type_name in zip(
                energy_system_type_ids, energy_system_type_names
            ):
                if energy_system_type_id and int(energy_system_type_id) in deleted_ids:
                    continue
                try:
                    energy_system_type_data.append({
                        "energy_system_type_id": int(energy_system_type_id) if energy_system_type_id else None,
                        "name": energy_system_type_name.strip(),
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={energy_system_type_id},"
                            f"Наименование: {energy_system_type_name}, "
                            f"Ошибка: {str(e)}"
                        )
                    )
            
            if not energy_system_type_data:
                return redirect(url_for("refdata_bp.energy_system_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        energy_system_type_filter=energy_system_type_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["energy_system_type_id"] for record in energy_system_type_data if record["energy_system_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов частей энергосистем России: {duplicates}")

            # Обновление данных в базе
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.energy_system_type_list",
                            page=page,
                            per_page=per_page,
                            energy_system_type_filter=energy_system_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                update_energy_system_type_all_versions_service(energy_system_type_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_energy_system_type_service(energy_system_type_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.energy_system_type_list", 
                                page=page, 
                                per_page=per_page, 
                                energy_system_type_filter=energy_system_type_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_energy_system_type_list(page, 
                              per_page, 
                              energy_system_type_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "refdata/energy_systems/energy_system_type/energy_system_type.html",
        form=form,
        energy_system_type_list=pagination.items,
        pagination=pagination,
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_energy_system_type", methods=["GET", "POST"])
@login_required
def add_energy_system_type():
    """ Маршрут для добавления новой части энергосистемы России. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления части энергосистемы России", 
        entity_type="energy_system_type")

    # Создание формы
    form = AddEnergySystemTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 25, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

   # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/energy_systems/energy_system_type/energy_system_type_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]
            # Добавление новой записи
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.energy_system_type_list",
                            page=page,
                            per_page=per_page,
                            energy_system_type_filter=energy_system_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                add_energy_system_type_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_energy_system_type_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = energy_system_type_query(
                                energy_system_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.energy_system_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_system_type_filter=energy_system_type_filter,
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
        "refdata/energy_systems/energy_system_type/energy_system_type_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form,
        energy_system_type_filter=energy_system_type_filter, 
    )


@refdata_bp.route("/export_energy_system_type", methods=["GET"])
@login_required
def export_energy_system_type():
    """Маршрут для экспорта типов частей энергосистемы России в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    try:
        # Запрашиваем у сервиса сформированный поток Excel
        excel_data = export_energy_system_type_service(
            user=user,
            energy_system_type_filter=energy_system_type_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.energy_system_type_list"))
        
        # Формирование имени файла
        filename = f"energy_system_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.energy_system_type_list"))
