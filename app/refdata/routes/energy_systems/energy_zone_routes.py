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
    get_energy_zone_query,
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
    log_to_db(user, "Открыта страница: Энергозоны")

    # Создание формы
    form = EnergyZoneFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 10, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    energy_zone_filter  = request.args.get("energy_zone_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 10, type=int)
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
                log_to_db(user, f"Ошибка удаления энергозоны {e}")
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
                log_to_db(user, "Нет данных для обновления.")
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
            ids = [record["id"] for record in energy_zone_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID энергозоны: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления энергозон", str(energy_zone_data))
            update_energy_zone_service(energy_zone_data, user)
            flash("Изменения успешно сохранены.", "success")
            
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных энергозон: {e}")
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
    """Добавление записи «Энергозоны»."""
    user = session.get("username", "anonymous")
    form = AddEnergyZoneForm()

    if request.method == "POST":
        # --- Обновляем состояние интерфейса из POST (страница/сортировка/фильтр) ---
        if form.validate_on_submit():
            try:
                payload = {"name": form.name.data.strip()}
                if hasattr(form, "number") and form.number.data:
                    payload["number"] = str(form.number.data).strip()
                for fname in ("fuel_type", "federal_district", "energy_zone", "synchronous_area",
                              "union_energy_system", "regional_energy_system", "regional_district"):
                    if hasattr(form, fname) and getattr(form, fname).data not in (None, "", []):
                        payload[fname] = getattr(form, fname).data
                log_to_db(user, f"Добавление Энергозоны: {payload}")
                new_id = add_energy_zone(payload, user)
                flash("Запись добавлена.", "success")
                return redirect(url_for("refdata_bp.energy_zone_list"))
            except Exception as e:
                current_app.logger.exception(e)
                log_to_db(user, f"Ошибка добавления Энергозоны: {e}")
                flash("Ошибка добавления записи.", "danger")
        else:
            flash("Проверьте заполнение формы.", "warning")

    return render_template("refdata/energy_zone_add.html", form=form)


@refdata_bp.route("/export_energy_zone", methods=["GET"])
@login_required
def export_energy_zone():
    """Экспорт «Энергозоны» в Excel с учётом текущих фильтров/сортировки."""
    user = session.get("username", "anonymous")
    try:
        filter_value = request.args.get("energy_zone_filter", "", type=str).strip()
        sort_by = request.args.get("sort_by", "id", type=str)
        sort_dir = request.args.get("sort_dir", "asc", type=str)

        excel_io = export_energy_zone_service(filter_value=filter_value, sort_by=sort_by, sort_dir=sort_dir)
        filename = f"energy_zone_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        # --- Экспорт: отдаём файл пользователю ---
        return send_file(
            excel_io,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.exception(e)
        log_to_db(user, f"Ошибка экспорта Энергозоны: {e}")
        flash("Ошибка экспорта данных.", "danger")
        return redirect(url_for("refdata_bp.energy_zone_list"))