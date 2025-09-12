"""Маршруты справочника «Типы энергосистем»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.energy_system_type_forms import (
    EnergySystemTypeFilterForm,
    AddEnergySystemTypeForm,
)

# Сервисы
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_total_energy_system_type_records,
)
from app.refdata.services.energy_systems.energy_system_type_services import (
    get_energy_system_type_list,
    update_energy_system_type_service,
    add_energy_system_type_service,
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
    log_to_db(user, "Открыта страница типов частей энергосистемы России")

    # Создание формы
    form = EnergySystemTypeFilterForm()

    # Получение параметров запроса
    page                        = request.args.get("page", 1, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    per_page                    = request.args.get("per_page", 10, type=int)
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                        = request.form.get("page", 1, type=int)
        per_page                    = request.form.get("per_page", 10, type=int)
        sort_by                     = request.form.get("sort_by", "id")
        sort_dir                    = request.form.get("sort_dir", "asc")
        energy_system_type_filter   = request.form.get("energy_system_type_filter", "").strip()

        # Получение данных из формы
        energy_system_type_ids      = request.form.getlist("energy_system_type_ids[]")
        energy_system_type_names    = request.form.getlist("energy_system_type_names[]")
        energy_system_type_delete   = request.form.getlist("energy_system_type_delete[]")
  
        # Удаление записей
        if energy_system_type_delete:
            try:
                delete_energy_system_type_service(energy_system_type_delete, user)
                flash("Записи типов частей энергосистемы России успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления типов частей энергосистемы России: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.energy_system_type_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    energy_system_type_filter=energy_system_type_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not (energy_system_type_ids and energy_system_type_names):
                log_to_db(user, "Нет данных для обновления.")
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
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in energy_system_type_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов частей энергосистем России: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления ОЭС", str(energy_system_type_data))
            update_energy_system_type_service(energy_system_type_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных списка типов частей энергосистем России: {e}")
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
        "refdata/energy_system_type/energy_system_type.html",
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
def add_energy_system_type_routes():
    """Добавление записи «Тип энергосистемы»."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления типа энергосистемы")

    # Создаём форму ввода данных
    form = AddEnergySystemTypeForm()

    # Сохраняем текущие параметры фильтра/сортировки/страницы для возврата после добавления
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    energy_system_type_filter = request.args.get("energy_system_type_filter", "").strip()
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
                "refdata/energy_system_type/energy_system_type_add.html",
                form=form
            )
        
        try:
            # Формируем payload и передаём его сервису добавления
            new_energy_system_type_id = add_energy_system_type_service([{
                "number": form.number.data,
                "name": form.name.data,}], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой типа энергосистемы", f"Номер: {form.number.data}, Имя: {form.name.data}")

            # После успешного добавления перенаправляем на последнюю страницу списка (PRG)
            total_records = get_total_energy_system_type_records(energy_system_type_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.energy_system_type_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_system_type_filter=energy_system_type_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_energy_system_type_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления новой типа энергосистемы", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления новой типа энергосистемы", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/energy_system_type/energy_system_type_add.html", 
        form=form,
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        energy_system_type_filter=energy_system_type_filter, 
        per_page=per_page, 
        page=page
    )


@refdata_bp.route("/export_energy_system_type_to_excel", methods=["GET"])
@login_required
def export_energy_system_type_to_excel_routes():
    """Экспорт «Типы энергосистем» в Excel с учётом текущих фильтров/сортировки."""
    user = session.get('username', 'Неизвестный пользователь')
    
    energy_system_type_filter = request.args.get("energy_system_type_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Запрашиваем у сервиса сформированный поток Excel
        excel_data = export_energy_system_type_service(user, energy_system_type_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {energy_system_type_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Если данных нет — информируем пользователя
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.energy_system_type_list"))
        
        # Формируем имя файла с меткой времени
        filename = f"energy_system_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.energy_system_type_list"))
