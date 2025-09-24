"""Маршруты справочника «Объединенные энергосистемы»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime
from collections import defaultdict

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.regional_energy_system_forms import (
    RegionalEnergySystemFilterForm, 
    AddRegionalEnergySystemForm,
)

# Сервисы
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
    get_union_energy_system_name,
)
from app.refdata.services.energy_systems.regional_energy_system_services import (
    regional_energy_system_query, 
    get_regional_energy_system_list, 
    update_regional_energy_system_service, 
    add_regional_energy_system_service, 
    delete_regional_energy_system_service, 
    import_regional_energy_system_service, 
    export_regional_energy_system_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/regional_energy_system", methods=["GET", "POST"])
@login_required
def regional_energy_system_list():
    """Маршрут для отображения списка региональных энергосистем."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница региональных энергосистем")

    # Создание формы
    form = RegionalEnergySystemFilterForm()

    # Получение параметров запроса
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 20, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                            = request.form.get("page", 1, type=int)
        per_page                        = request.form.get("per_page", 20, type=int)
        sort_by                         = request.form.get("sort_by", "id")
        sort_dir                        = request.form.get("sort_dir", "asc")
        regional_energy_system_filter   = request.form.get("regional_energy_system_filter", "").strip()
        union_energy_system_filter      = request.form.get("union_energy_system_filter", "").strip()

        # Получение данных из формы
        regional_energy_system_ids          = request.form.getlist("regional_energy_system_ids[]")
        regional_energy_system_names        = request.form.getlist("regional_energy_system_names[]")
        regional_energy_system_full_names   = request.form.getlist("regional_energy_system_full_names[]")
        regional_energy_system_delete       = request.form.getlist("regional_energy_system_delete[]")
        union_energy_system_ids             = request.form.getlist("union_energy_system[]")
        
        # Удаление записей
        if regional_energy_system_delete:
            try:
                delete_regional_energy_system_service(regional_energy_system_delete, user)
                flash("Записи региональных энергосистем успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления региональной энергосистемы {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.regional_energy_system_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    regional_energy_system_filter=regional_energy_system_filter,
                                    union_energy_system_filter=union_energy_system_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
    
        # Группируем субъектов по энергосистемам
        regional_districts_mapping = defaultdict(list)
        for res_id in regional_energy_system_ids:
            selected = request.form.getlist(f"regional_districts_{res_id}[]")
            regional_districts_mapping[int(res_id)] = [int(x) for x in selected if x.isdigit()]
           
        # Обновление данных в базе
        try:
            if not (regional_energy_system_ids and regional_energy_system_names and regional_energy_system_full_names):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.regional_energy_system_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        regional_energy_system_filter=regional_energy_system_filter,
                                        union_energy_system_filter=union_energy_system_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
            
            # Формирование данных для обновления
            regional_energy_system_data = []
            for regional_energy_system_id, regional_energy_system_name, regional_energy_system_name_full, union_energy_system_id in zip(regional_energy_system_ids, regional_energy_system_names, regional_energy_system_full_names, union_energy_system_ids):
                try:
                    regional_energy_system_data.append({
                        "regional_energy_system_id": int(regional_energy_system_id) if regional_energy_system_id else None,
                        "name": regional_energy_system_name.strip(),
                        "name_full": regional_energy_system_name_full.strip(),
                        "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
                        "regional_district_ids": regional_districts_mapping.get(int(regional_energy_system_id), [])
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={regional_energy_system_id},"
                            f"Наименование: {regional_energy_system_name},"
                            f"Полное наименование: {regional_energy_system_name_full},"
                            f"ОЭС: {get_union_energy_system_name(union_energy_system_id)}."
                            f"Ошибка: {str(e)}"
                        )
                    )
                
 
            # Проверка на дублирующиеся IDs
            ids = [record["regional_energy_system_id"] for record in regional_energy_system_data if record["regional_energy_system_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID региональных энергосистем: {duplicates}")

            log_to_db(user, "Полученные данные для обновления региональных энергосистем", str(regional_energy_system_data))

            # Обновление данных в базе
            update_regional_energy_system_service(regional_energy_system_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных региональных энергосистем: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.regional_energy_system_list",
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
        ))

    # Получение данных для отображения
    pagination = get_regional_energy_system_list(
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                )
    
    # Подготовка данных для формы
    union_energy_system_list = get_union_energy_system_list_full()
    form.union_energy_system.choices = [(ues.id, ues.name) for ues in union_energy_system_list]
    
    regional_districts_list = get_regional_district_list_full()

    return render_template(
        "refdata/energy_systems/regional_energy_system/regional_energy_system.html",
        form=form,
        regional_energy_system_list=pagination.items,
        pagination=pagination,
        union_energy_system_list=form.union_energy_system.choices,
        regional_districts_list=regional_districts_list,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_regional_energy_system", methods=["GET", "POST"])
@login_required
def add_regional_energy_system():
    """ Маршрут для добавления новой региональной энергосистемы. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления региональной энергосистемы")

    # Создание формы
    form = AddRegionalEnergySystemForm()

    # Сохранение текущих фильтров и параметров отображения
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 20, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    # Подготовка данных для формы
    union_energy_system_list = get_union_energy_system_list_full()
    form.union_energy_system.choices = [(ues.id, ues.name) for ues in union_energy_system_list]

    regional_district_list = get_regional_district_list_full()
    form.regional_districts.choices = [(rd.id, rd.name) for rd in regional_district_list]

    # Обработка формы
    if request.method == "POST":
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "name_full": (form.name_full.data or "").strip(),
                "union_energy_system_id": form.union_energy_system.data,
                "regional_districts": form.regional_districts.data
            }]

            # Добавление новой записи через сервис
            add_regional_energy_system_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            log_to_db(user, "Добавление новой региональной энергосистемы", 
                    (
                        f"Наименование: {form.name.data}, "
                        f"Полное наименование: {form.name_full.data}, "
                        f"ОЭС: {get_union_energy_system_name(form.union_energy_system.data)}"
                    )
            )

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = regional_energy_system_query(
                                regional_energy_system_filter, 
                                union_energy_system_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.regional_energy_system_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                regional_energy_system_filter=regional_energy_system_filter,
                union_energy_system_filter=union_energy_system_filter,
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления новой региональной энергосистемы", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления новой региональной энергосистемы", str(e))

    return render_template(
        "refdata/energy_systems/regional_energy_system/regional_energy_system_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form, 
        regional_districts=form.regional_districts.choices, 
        union_energy_system=form.union_energy_system.choices, 
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
    )


@refdata_bp.route("/import_regional_energy_system", methods=["POST"])
@login_required
def import_regional_energy_system():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт региональных энергосистем из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.regional_energy_system_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.regional_energy_system_list"))

    try:
        imported_count = import_regional_energy_system_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.regional_energy_system_list"))


@refdata_bp.route("/export_regional_energy_system", methods=["GET"])
@login_required
def export_regional_energy_system():
    """Маршрут для экспорта региональных энергосистем в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат экспорт списка региональных энергосистем в Excel")
    
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_regional_energy_system_service(
                        user, 
                        sort_by, 
                        sort_dir,
                        regional_energy_system_filter, 
                        union_energy_system_filter, 
        )
        log_to_db(user, "Экспорт завершен", 
                (
                    f"Фильтры: {regional_energy_system_filter, union_energy_system_filter}, "
                    f"Сортировка: {sort_by}, "
                    f"Направление: {sort_dir}"
                )
        )
        
        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.regional_energy_system_list"))
        
        # Формирование имени файла
        filename = f"regional_energy_system_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.regional_energy_system_list"))