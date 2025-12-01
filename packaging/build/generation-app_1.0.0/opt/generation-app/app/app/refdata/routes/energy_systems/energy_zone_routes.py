# -*- coding: utf-8 -*-
"""Маршруты справочника «Энергозоны»."""

from datetime import datetime
from collections import Counter
from flask import render_template, request, redirect, url_for, flash, session, current_app, send_file
from flask_login import login_required
from app.auth.routes import roles_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.energy_zone_forms import EnergyZoneFilterForm, AddEnergyZoneForm

# Сервисы
from app.refdata.services.energy_systems.energy_zone_services import (
    energy_zone_query,
    get_energy_zone_list,
    update_energy_zone_service,
    add_energy_zone_service,
    delete_energy_zone_service,
    export_energy_zone_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/energy_zone", methods=["GET", "POST"])
@login_required
def energy_zone_list():
    """Маршрут для отображения списка энергозон."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница: энергозоны", 
        entity_type="energy_zone")

    # Создание формы
    form = EnergyZoneFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    energy_zone_filter  = request.args.get("energy_zone_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 20, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        energy_zone_filter  = request.form.get("energy_zone_filter", energy_zone_filter).strip()

        # Получение данных из формы
        energy_zone_ids     = request.form.getlist("energy_zone_ids[]")
        energy_zone_numbers = request.form.getlist("energy_zone_numbers[]")
        energy_zone_names   = request.form.getlist("energy_zone_names[]")
        energy_zone_delete  = request.form.getlist("energy_zone_delete[]")

        # Удаление записей
        if energy_zone_delete:
            try:
                delete_energy_zone_service(energy_zone_delete, user)
                flash("Записи энергозон успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.energy_zone_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    energy_zone_filter=energy_zone_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))

        # Обновление данных в базе
        try:
            if not (energy_zone_ids and energy_zone_names and energy_zone_numbers):
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.energy_zone_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        energy_zone_filter=energy_zone_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            energy_zone_data = []
            for energy_zone_id, energy_zone_number, energy_zone_name in zip(
                energy_zone_ids, energy_zone_numbers, energy_zone_names
            ):
                try:
                    energy_zone_data.append({
                        "energy_zone_id": int(energy_zone_id) if energy_zone_id else None,
                        "number": energy_zone_number.strip(),
                        "name": energy_zone_name.strip(),
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={energy_zone_id},"
                            f"Номер: {energy_zone_number}, "
                            f"Наименование: {energy_zone_name}, "
                            f"Ошибка: {str(e)}"
                        )
                    )
            
            # Проверка на дублирующиеся IDs
            ids = [record["energy_zone_id"] for record in energy_zone_data if record["energy_zone_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID энергозоны: {duplicates}")

            # Обновление данных в базе
            update_energy_zone_service(energy_zone_data, user)
            flash("Изменения успешно сохранены.", "success")
            
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.energy_zone_list", 
                                page=page, 
                                per_page=per_page, 
                                energy_zone_filter=energy_zone_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_energy_zone_list(page, 
                              per_page, 
                              energy_zone_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "refdata/energy_systems/energy_zone/energy_zone.html",
        form=form,
        energy_zone_list=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_energy_zone", methods=["GET", "POST"])
@login_required
def add_energy_zone():
    """ Маршрут для добавления новой энергозоны». """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления энергозоны", 
        entity_type="energy_zone")

    # Создание формы
    form = AddEnergyZoneForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 20, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    energy_zone_filter          = request.args.get("energy_zone_filter", "").strip()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/energy_systems/energy_zone/energy_zone_add.html",
                form=form
            )
        
        try:
            payload = [{
                "number": (form.number.data or "").strip(),
                "name": (form.name.data or "").strip(),
            }]

            add_energy_zone_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = energy_zone_query(
                                energy_zone_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.energy_zone_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_zone_filter=energy_zone_filter,
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
        "refdata/energy_systems/energy_zone/energy_zone_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form, 
        energy_zone_filter=energy_zone_filter, 
    )

@refdata_bp.route("/export_energy_zone", methods=["GET"])
@login_required
def export_energy_zone():
    """Маршрут для экспорта энергозон в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by                 = request.args.get("sort_by", "id")
    sort_dir                = request.args.get("sort_dir", "asc")
    energy_zone_filter      = request.args.get("energy_zone_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_energy_zone_service(
            user=user,
            sort_by=sort_by,
            sort_dir=sort_dir,
            energy_zone_filter=energy_zone_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.energy_zone_list"))
        
        # Формирование имени файла
        filename = f"energy_zone_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.energy_zone_list"))