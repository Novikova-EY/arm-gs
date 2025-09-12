"""Маршруты справочника «Объединенные энергосистемы»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.union_energy_system_forms import (
    UnionEnergySystemFilterForm, 
    AddUnionEnergySystemForm
)

# Сервисы
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list, 
    get_energy_system_type_list_full,
    get_energy_system_type_name,
)
from app.refdata.services.energy_systems.union_energy_system_services import (
    union_energy_system_query,
    get_union_energy_system_list, 
    update_union_energy_system_service, 
    add_union_energy_system_service, 
    delete_union_energy_system_service,
    import_union_energy_system_service, 
    export_union_energy_system_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/union_energy_system", methods=["GET", "POST"])
@login_required
def union_energy_system_list():
    """Маршрут для отображения списка ОЭС."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ОЭС")
    
    # Создание формы
    form = UnionEnergySystemFilterForm()

    # Получение параметров запроса
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 10, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    union_energy_system_filter  = request.args.get("union_energy_system_filter", "").strip()
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    if request.method == "POST":        
        # Обновление параметров из формы
        page                        = request.form.get("page", 1, type=int)
        per_page                    = request.form.get("per_page", 10, type=int)
        sort_by                     = request.form.get("sort_by", "id")
        sort_dir                    = request.form.get("sort_dir", "asc")
        union_energy_system_filter  = request.form.get("union_energy_system_filter", "").strip()
        energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

        # Получение данных из формы
        union_energy_system_ids         = request.form.getlist("union_energy_system_ids[]")
        union_energy_system_names       = request.form.getlist("union_energy_system_names[]")
        union_energy_system_full_names  = request.form.getlist("union_energy_system_full_names[]")
        union_energy_system_delete      = request.form.getlist("union_energy_system_delete[]")
        energy_system_type_ids          = request.form.getlist("energy_system_types[]")
  
        # Удаление записей
        if union_energy_system_delete:
            try:
                delete_union_energy_system_service(union_energy_system_delete, user)
                flash("Записи ОЭС успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления ОЭС {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.union_energy_system_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    union_energy_system_filter=union_energy_system_filter,
                                    energy_system_type_filter=energy_system_type_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not (union_energy_system_ids and union_energy_system_names and union_energy_system_full_names):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.union_energy_system_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        union_energy_system_filter=union_energy_system_filter,
                                        energy_system_type_filter=energy_system_type_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            union_energy_system_data = []
            for union_energy_system_id, union_energy_system_name, union_energy_system_name_full, energy_system_type_id in zip(
                union_energy_system_ids, union_energy_system_names, union_energy_system_full_names, energy_system_type_ids
            ):
                try:
                    union_energy_system_data.append({
                        "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
                        "name": union_energy_system_name.strip(),
                        "name_full": union_energy_system_name_full.strip(),
                        "energy_system_type_id": int(energy_system_type_id) if energy_system_type_id else None
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={union_energy_system_id},"
                            f"Наименование: {union_energy_system_name}, "
                            f"Полное наименование: {union_energy_system_name_full}, "
                            f"Часть энергосистемы России: {energy_system_type_id}. "
                            f"Ошибка: {str(e)}"
                        )
                    )
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in union_energy_system_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID ОЭС: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления ОЭС", str(union_energy_system_data))
            update_union_energy_system_service(union_energy_system_data, user)
            flash("Изменения успешно сохранены.", "success")
            
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных ОЭС: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.union_energy_system_list", 
                                page=page, 
                                per_page=per_page, 
                                union_energy_system_filter=union_energy_system_filter, 
                                energy_system_type_filter=energy_system_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_union_energy_system_list(page, 
                              per_page, 
                              union_energy_system_filter, 
                              energy_system_type_filter,
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    energy_system_types = get_energy_system_type_list_full()
    form.energy_system_type.choices = [(est.id, est.name) for est in energy_system_types]

    return render_template(
        "refdata/energy_systems/union_energy_system/union_energy_system.html",
        form=form,
        union_energy_system_list=pagination.items,
        pagination=pagination,
        energy_system_types=form.energy_system_type.choices,
        union_energy_system_filter=union_energy_system_filter,
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_union_energy_system", methods=["GET", "POST"])
@login_required
def add_union_energy_system():
    """ Маршрут для добавления новой ОЭС. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ОЭС")

    # Создание формы
    form = AddUnionEnergySystemForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = int(request.args.get("page", 1))
    per_page                    = int(request.args.get("per_page", 10))
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    union_energy_system_filter  = request.args.get("union_energy_system_filter", "").strip()
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    # Получение списка типов ОЭС
    try:
        energy_system_types = get_energy_system_type_list()
        if not energy_system_types:
            flash("Ошибка: отсутствуют типы ОЭС. Добавьте типы перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления ОЭС", "Отсутствуют типы ОЭС.")
            return redirect(url_for("refdata_bp.union_energy_system_list"))

        form.energy_system_type.choices = [(0, "Не указан")] + [(t.id, t.name) for t in energy_system_types]
        
    except Exception as e:
        current_app.logger.error(f"Ошибка получения типов ОЭС: {e}")
        flash("Ошибка при загрузке данных типов ОЭС.", "danger")
        return redirect(url_for("refdata_bp.union_energy_system_list"))

   # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "name_full": (form.name_full.data or "").strip(),
                "id_energy_system_type": form.energy_system_type.data
            }]
                        
            # Добавление новой записи через сервис
            add_union_energy_system_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            log_to_db(user, "Добавление новой ОЭС", 
                    (
                        f"Наименование: {form.name.data}, "
                        f"Полное наименование: {form.name_full.data}, "
                        f"Часть энергосистемы России: {get_energy_system_type_name(form.energy_system_type.data)}"
                    )
            )

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = union_energy_system_query(
                                union_energy_system_filter, 
                                energy_system_type_filter).count
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.union_energy_system_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                union_energy_system_filter=union_energy_system_filter,
                energy_system_type_filter=energy_system_type_filter,
                per_page=per_page,
                page=last_page,
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления новой ОЭС", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления ОЭС", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/energy_systems/union_energy_system/union_energy_system_add.html", 
        form=form, 
        energy_system_types=energy_system_types, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        union_energy_system_filter=union_energy_system_filter, 
        energy_system_type_filter=energy_system_type_filter,
        per_page=per_page, 
        page=page
    )


@refdata_bp.route("/import_union_energy_system", methods=["POST"])
@login_required
def import_union_energy_system():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт ОЭС из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.union_energy_system_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.union_energy_system_list"))

    try:
        imported_count = import_union_energy_system_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.union_energy_system_list"))


@refdata_bp.route("/export_union_energy_system", methods=["GET"])
@login_required
def export_union_energy_system():
    """Маршрут для экспорта данных в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    union_energy_system_filter  = request.args.get("union_energy_system_filter", "").strip()
    energy_system_type_filter   = request.args.get("energy_system_type_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_union_energy_system_service(
                        user, 
                        union_energy_system_filter, 
                        energy_system_type_filter, 
                        sort_by, 
                        sort_dir
        )
        log_to_db(user, "Экспорт завершён", 
                (
                    f"Фильтры: {union_energy_system_filter, energy_system_type_filter},"
                    f"Сортировка: {sort_by}, "
                    f"Направление: {sort_dir}"
                )
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.union_energy_system_list"))
        
        # Формирование имени файла
        filename = f"union_energy_system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.union_energy_system_list"))