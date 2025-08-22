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
    get_energy_zone_list,
    get_total_energy_zone_records,
    update_energy_zone_service,
    add_energy_zone_service,
    delete_energy_zone_service,
    export_energy_zone_to_excel_service,
    import_energy_zone_from_excel_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db

# Пагинация
from app.common.models.pagination import Pagination


@refdata_bp.route("/energy_zone", methods=["GET", "POST"])
@login_required
@roles_required(['admin', 'generation'])
def energy_zone_list():
    """Список «Энергозоны»: фильтрация, сортировка, редактирование, удаление, пагинация."""
    user = session.get("username", "anonymous")
    log_to_db(user, "Открыта страница: Энергозоны")

    form = EnergyZoneFilterForm()

    # --- Чтение параметров запроса (режим списка) ---
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    energy_zone_filter = request.args.get("energy_zone_filter", "", type=str).strip()
    sort_by = request.args.get("sort_by", "id", type=str)
    sort_dir = request.args.get("sort_dir", "asc", type=str)

    if request.method == "POST":
        # --- Обновляем состояние интерфейса из POST (страница/сортировка/фильтр) ---
        page = request.form.get("page", page, type=int)
        per_page = request.form.get("per_page", per_page, type=int)
        sort_by = request.form.get("sort_by", sort_by)
        sort_dir = request.form.get("sort_dir", sort_dir)
        energy_zone_filter = request.form.get("energy_zone_filter", energy_zone_filter).strip()

        # --- Удаление выбранных записей ---
        delete_ids = request.form.getlist("energy_zone_delete[]")
        if delete_ids:
            try:
                log_to_db(user, f"Удаление записей Энергозоны: {delete_ids}")
                delete_energy_zone_service(delete_ids, user)
                flash("Выбранные записи удалены.", "success")
            except Exception as e:
                current_app.logger.exception(e)
                log_to_db(user, f"Ошибка удаления Энергозоны: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.energy_zone_list",
                                    page=page, per_page=per_page,
                                    energy_zone_filter=energy_zone_filter,
                                    sort_by=sort_by, sort_dir=sort_dir))

        ids = request.form.getlist("energy_zone_ids[]")
        names = request.form.getlist("energy_zone_names[]")
        numbers = request.form.getlist("energy_zone_numbers[]") if "energy_zone_numbers[]" in request.form else []
        # --- Формирование данных для обновления ---
        data = []

        for i, _id in enumerate(ids):
            rec = {"id": int(_id) if _id else None}
            if i < len(names):
                name_val = (names[i] or "").strip()
                if not name_val:
                    raise ValueError("Пустое наименование недопустимо.")
                rec["name"] = name_val
            if i < len(numbers) and numbers:
                rec["number"] = (numbers[i] or "").strip()
            
            data.append(rec)

        # --- Контроль дублирующихся значений в запросе ---
        dup = [x for x, cnt in Counter([d.get("id") for d in data if d.get("id") is not None]).items() if cnt > 1]
        if dup:
            flash(f"Обнаружены дублирующиеся ID: {dup}", "danger")
            return redirect(url_for("refdata_bp.energy_zone_list",
                                    page=page, per_page=per_page,
                                    energy_zone_filter=energy_zone_filter,
                                    sort_by=sort_by, sort_dir=sort_dir))
        try:
            log_to_db(user, f"Пакетное обновление Энергозоны: {len(data)} записей")
            update_energy_zone_service(data, user)
            flash("Изменения сохранены.", "success")
        except Exception as e:
            current_app.logger.exception(e)
            log_to_db(user, f"Ошибка обновления Энергозоны: {e}")
            flash("Ошибка сохранения изменений.", "danger")

        return redirect(url_for("refdata_bp.energy_zone_list",
                                page=page, per_page=per_page,
                                energy_zone_filter=energy_zone_filter,
                                sort_by=sort_by, sort_dir=sort_dir))

    try:
        items = get_energy_zone_list(
            filter_value=energy_zone_filter,
            sort_by=sort_by, sort_dir=sort_dir,
            page=page, per_page=per_page
        )
        total = get_total_energy_zone_records(filter_value=energy_zone_filter)
    except Exception as e:
        current_app.logger.exception(e)
        log_to_db(user, f"Ошибка загрузки списка Энергозоны: {e}")
        items, total = [], 0

    # --- Загрузка данных и подготовка контекста ---
    pagination = Pagination(page=page, per_page=per_page, total=total)

    return render_template(
        "refdata/energy_zone.html",
        form=form,
        energy_zone_list=items,
        energy_zone_filter=energy_zone_filter,
        sort_by=sort_by, sort_dir=sort_dir,
        pagination=pagination, per_page=per_page
    )


@refdata_bp.route("/energy_zone/add", methods=["GET", "POST"])
@login_required
@roles_required(['admin', 'generation'])
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


@refdata_bp.route("/energy_zone/export", methods=["GET"])
@login_required
@roles_required(['admin', 'generation'])
def export_energy_zone_to_excel_routes():
    """Экспорт «Энергозоны» в Excel с учётом текущих фильтров/сортировки."""
    user = session.get("username", "anonymous")
    try:
        filter_value = request.args.get("energy_zone_filter", "", type=str).strip()
        sort_by = request.args.get("sort_by", "id", type=str)
        sort_dir = request.args.get("sort_dir", "asc", type=str)

        excel_io = export_energy_zone_to_excel_service(filter_value=filter_value, sort_by=sort_by, sort_dir=sort_dir)
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



@refdata_bp.route("/energy_zone/import", methods=["POST"])
@login_required
@roles_required(['admin', 'generation'])
def import_energy_zone_from_excel_routes():
    """Импорт «Энергозоны» из Excel."""
    user = session.get("username", "anonymous")
    try:
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Файл не выбран.", "warning")
            return redirect(url_for("refdata_bp.energy_zone_list"))
        count = import_energy_zone_from_excel_service(file.stream, user)
        flash(f"Импортировано записей: {count}", "success")
    except Exception as e:
        current_app.logger.exception(e)
        log_to_db(user, f"Ошибка импорта Энергозоны: {e}")
        flash("Ошибка импорта данных.", "danger")
    return redirect(url_for("refdata_bp.energy_zone_list"))