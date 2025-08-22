# -*- coding: utf-8 -*-
"""Маршруты справочника «Синхронные зоны»."""

from datetime import datetime
from collections import Counter
from flask import (render_template, request, redirect, url_for, flash, session, current_app, send_file)
from flask_login import login_required
from app.auth.routes import roles_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.synchronous_area_forms import SynchronousAreaFilterForm, AddSynchronousAreaForm

# Сервисы
from app.refdata.services.energy_systems.synchronous_area_services import (
    get_total_synchronous_area_records,
    get_synchronous_area_list,
    update_synchronous_area_service,
    add_synchronous_area_service,
    delete_synchronous_area_service,
    export_synchronous_area_to_excel_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db

# Пагинация
from app.common.models.pagination import Pagination

@refdata_bp.route("/synchronous_area", methods=["GET", "POST"])
@login_required
@roles_required(['admin', 'generation'])
def synchronous_area_list():
    """Список «Синхронные зоны»: фильтр/сортировка/массовое редактирование/удаление/пагинация."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ФО")
    
    form = SynchronousAreaFilterForm()

    # --- Чтение параметров запроса (режим просмотра списка) ---
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    synchronous_area_filter = request.args.get("synchronous_area_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # --- Обновляем состояние интерфейса из POST (страница, сортировка, фильтр) ---
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        synchronous_area_filter = request.form.get("synchronous_area_filter", "").strip()

        # --- Считываем массивы данных из формы (id, номер, наименование, пометка удаления) ---
        synchronous_area_ids = request.form.getlist("synchronous_area_ids[]")
        synchronous_area_numbers = request.form.getlist("synchronous_area_numbers[]")
        synchronous_area_names = request.form.getlist("synchronous_area_names[]")
        synchronous_area_delete = request.form.getlist("synchronous_area_delete[]")
  
        # --- Обработка удаления выбранных записей ---
        if synchronous_area_delete:
            try:
                delete_synchronous_area_service(synchronous_area_delete, user)
                flash("Записи успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления записей: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.synchronous_area_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    synchronous_area_filter=synchronous_area_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # --- Обработка пакетного сохранения изменений ---
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
                # Контроль обязательного поля: наименование не должно быть пустым
                if not synchronous_area_name.strip():
                    log_to_db(user, f"Пустое имя обнаружено: ID={synchronous_area_id}")
                    raise ValueError(f"Пустое имя для ID: {synchronous_area_id}")

                synchronous_area_data.append({
                    "id": int(synchronous_area_id) if synchronous_area_id else None,
                    "number": synchronous_area_number.strip(),
                    "name": synchronous_area_name.strip(),
                })
            
            # Контроль целостности: проверяем дублирование идентификаторов в одном запросе
            ids = [record["id"] for record in synchronous_area_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID ФО: {duplicates}")

            # --- Обработка пакетного сохранения изменений ---
            update_synchronous_service_service(synchronous_area_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных ФО: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.synchronous_area_list", 
                                page=page, 
                                per_page=per_page, 
                                synchronous_area_filter=synchronous_area_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # --- Загрузка данных и подготовка контекста для шаблона ---
    pagination = get_synchronous_area_list(page, 
                              per_page, 
                              synchronous_area_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "refdata/synchronous_area/synchronous_area.html",
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
@roles_required(['admin', 'generation'])
def add_synchronous_area_routes():
    """Добавление записи «Синхронные зоны»."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления синхронной зоны")

    # Создаём форму ввода данных
    form = AddSynchronousAreaForm()

    # Сохраняем текущие параметры фильтра/сортировки/страницы для возврата после добавления
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    synchronous_area_filter = request.args.get("synchronous_area_filter", "").strip()
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))

    # --- Обработка отправки формы ---
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/synchronous_area/synchronous_area_add.html",
                form=form
            )
        
        try:
            # Формируем payload и передаём его сервису добавления
            new_synchronous_area_id = add_synchronous_area_service([{
                "number": form.number.data,
                "name": form.name.data,}], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой синхронной зоны", f"Номер: {form.number.data}, Имя: {form.name.data}")

            # После успешного добавления перенаправляем на последнюю страницу списка (PRG)
            total_records = get_total_synchronous_area_records(synchronous_area_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.synchronous_area_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                synchronous_area_filter=synchronous_area_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_synchronous_area_id
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
        "refdata/synchronous_area/synchronous_area_add.html", 
        form=form,
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        synchronous_area_filter=synchronous_area_filter, 
        per_page=per_page, 
        page=page
    )


@refdata_bp.route("/export_synchronous_area_to_excel", methods=["GET"])
@login_required
@roles_required(['admin', 'generation'])
def export_synchronous_area_to_excel_routes():
    """Экспорт «Синхронные зоны» в Excel с учётом текущих фильтров/сортировки."""
    user = session.get('username', 'Неизвестный пользователь')
    
    synchronous_area_filter = request.args.get("synchronous_area_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Запрашиваем у сервиса сформированный поток Excel
        excel_data = export_synchronous_area_to_excel_service(user, synchronous_area_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {synchronous_area_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Если данных нет — информируем пользователя
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.synchronous_area_list"))
        
        # Формируем имя файла с меткой времени
        filename = f"synchronous_area_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Отдаём файл пользователю через send_file
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
