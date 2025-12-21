"""Маршруты справочника «Энергоузлы»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.energy_unit_forms import (
    EnergyUnitFilterForm, 
    AddEnergyUnitForm,
)

# Сервисы
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_list_full, 
    get_regional_energy_system_name,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full, 
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
    get_regional_district_name,
    get_regional_districts_list,
)
from app.refdata.services.energy_systems.energy_unit_services import (
    energy_unit_query, 
    get_energy_unit_list, 
    update_energy_unit_service, 
    add_energy_unit_service, 
    delete_energy_unit_service, 
    export_energy_unit_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/energy_units", methods=["GET", "POST"])
@login_required
def energy_unit_list():
    """Маршрут для отображения списка энергоузлов."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница энергоузла", 
        entity_type="energy_unit")

    # Создание формы
    form = EnergyUnitFilterForm()

    # Получение параметров запроса
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 20, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_unit_filter              = request.args.get("energy_unit_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                            = request.form.get("page", 1, type=int)
        per_page                        = request.form.get("per_page", 20, type=int)
        sort_by                         = request.form.get("sort_by", "id")
        sort_dir                        = request.form.get("sort_dir", "asc")
        energy_unit_filter              = request.form.get("energy_unit_filter", "").strip()
        regional_district_filter        = request.form.get("regional_district_filter", "").strip()
        regional_energy_system_filter   = request.form.get("regional_energy_system_filter", "").strip()
        union_energy_system_filter      = request.form.get("union_energy_system_filter", "").strip()

        # Получение данных из формы
        energy_unit_ids             = request.form.getlist("energy_unit_ids[]")
        energy_unit_names           = request.form.getlist("energy_unit_names[]")
        regional_energy_system_ids  = request.form.getlist("regional_energy_system_ids[]")
        regional_district_ids       = request.form.getlist("regional_district_ids[]")
        energy_unit_delete          = request.form.getlist("energy_unit_delete[]")
        
        # Удаление записей
        if energy_unit_delete:
            try:
                delete_energy_unit_service(energy_unit_delete, user)
                flash("Записи энергоузлов успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.energy_unit_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir,
                                    energy_unit_filter=energy_unit_filter,
                                    regional_district_filter=regional_district_filter,
                                    regional_energy_system_filter=regional_energy_system_filter,
                                    union_energy_system_filter=union_energy_system_filter,
                                    ))

        # Обновление данных в базе
        try:
            if not (energy_unit_ids and energy_unit_names and regional_energy_system_ids and regional_district_ids):
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.energy_unit_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir,
                                        energy_unit_filter=energy_unit_filter,
                                        regional_district_filter=regional_district_filter,
                                        regional_energy_system_filter=regional_energy_system_filter,
                                        union_energy_system_filter=union_energy_system_filter,
                                        ))
            
           # Формирование данных для обновления
            energy_unit_data = []
            for energy_unit_id, energy_unit_name, regional_district_id, regional_energy_system_id in zip(
                energy_unit_ids, energy_unit_names, regional_district_ids, regional_energy_system_ids
            ):
                try:
                    energy_unit_data.append({
                        "energy_unit_id": int(energy_unit_id) if energy_unit_id else None,
                        "name": energy_unit_name.strip(),
                        "regional_district_id": int(regional_district_id) if regional_district_id else None,
                        "regional_energy_system_id": int(regional_energy_system_id) if regional_energy_system_id else None,
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={energy_unit_id},"
                            f"Наименование: {energy_unit_name}, "
                            f"Субъект РФ: {get_regional_district_name(regional_district_id)}, "
                            f"Региональная энергосистема: {get_regional_energy_system_name(regional_energy_system_id)}. "
                            f"Ошибка: {str(e)}"
                        )
                    )
        
            # Проверка на дублирующиеся IDs
            ids = [record["energy_unit_id"] for record in energy_unit_data if record["energy_unit_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID энергоузлы: {duplicates}")

            # Обновление данных в базе
            update_energy_unit_service(energy_unit_data, user)
            flash("Изменения энергоузлов успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных энергоузлов.", "danger")

        return redirect(url_for("refdata_bp.energy_unit_list",
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                energy_unit_filter=energy_unit_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
        ))

    # Получение данных для отображения
    pagination = get_energy_unit_list( 
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                energy_unit_filter=energy_unit_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                )
    
    # Подготовка данных для формы
    # choices для WTForms (format: [(id, name), ...])
    regional_district_choices = get_regional_district_list_full()
    form.regional_district.choices = regional_district_choices

    # Полный список ORM‑объектов для шаблона (нужны .id и .name)
    regional_district_list = get_regional_districts_list()

    regional_energy_system_list = get_regional_energy_system_list_full()
    form.regional_energy_system.choices = [(res.id, res.name) for res in regional_energy_system_list]

    union_energy_system_list = get_union_energy_system_list_full()
    form.union_energy_system.choices = [(ues.id, ues.name) for ues in union_energy_system_list]
    
    return render_template(
        "refdata/energy_systems/energy_unit/energy_unit.html",
        form=form,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        pagination=pagination,
        energy_unit_list=pagination.items,
        regional_district_list=regional_district_list,
        regional_energy_system_list=regional_energy_system_list,
        union_energy_system_list=union_energy_system_list,
        energy_unit_filter=energy_unit_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
    )


@refdata_bp.route("/add_energy_unit", methods=["GET", "POST"])
@login_required
def add_energy_unit():
    """ Маршрут для добавления нового энергоузла. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления энергоузла", 
        entity_type="energy_unit")

    # Создание формы
    form = AddEnergyUnitForm()

    # Сохранение текущих фильтров и параметров отображения
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 20, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_unit_filter              = request.args.get("energy_unit_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()
 
    # Подготовка данных для формы
    regional_district_list = get_regional_district_list_full()
    form.regional_district.choices = regional_district_list
        
    regional_energy_system_list = get_regional_energy_system_list_full()
    form.regional_energy_system.choices = [(res.id, res.name) for res in regional_energy_system_list]

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/energy_systems/energy_unit/energy_unit_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи
            payload = [{
                    "name": form.name.data,
                    "regional_district_id": form.regional_district.data,
                    "regional_energy_system_id": form.regional_energy_system.data
            }]

            add_energy_unit_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = energy_unit_query(
                                energy_unit_filter, 
                                regional_district_filter, 
                                regional_energy_system_filter, 
                                union_energy_system_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.energy_unit_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_unit_filter=energy_unit_filter,
                regional_district_filter=regional_district_filter,
                regional_energy_system_filter=regional_energy_system_filter,
                union_energy_system_filter=union_energy_system_filter,
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")


    return render_template(
        "refdata/energy_systems/energy_unit/energy_unit_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form, 
        energy_unit_filter=energy_unit_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
    )


@refdata_bp.route("/export_energy_unit", methods=["GET"])
@login_required
def export_energy_unit():
    """Маршрут для экспорта энергоузлов в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_unit_filter              = request.args.get("energy_unit_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_energy_unit_service(
            user=user,
            energy_unit_filter=energy_unit_filter,
            regional_district_filter=regional_district_filter,
            regional_energy_system_filter=regional_energy_system_filter,
            union_energy_system_filter=union_energy_system_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.energy_unit_list"))
        
        # Формирование имени файла
        filename = f"energy_unit_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.energy_unit_list"))