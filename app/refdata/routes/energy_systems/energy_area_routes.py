"""Маршруты справочника «Энергорайоны»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.energy_systems.energy_area_forms import (
    EnergyAreaFilterForm, 
    AddEnergyAreaForm,
)

# Сервисы
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_name,
    get_regional_district_list_full,
)
from app.refdata.services.energy_systems.energy_area_services import (
    energy_area_query,
    get_energy_area_list, 
    update_energy_area_service, 
    add_energy_area_service, 
    delete_energy_area_service, 
    export_energy_area_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/energy_areas", methods=["GET", "POST"])
def energy_area_list():
    """Маршрут для отображения списка энергорайонов'"""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница энергорайонов")

    # Создание формы
    form = EnergyAreaFilterForm()

    # Получение параметров запроса
    page                            = request.args.get("page", 1, type=int)
    per_page                        = request.args.get("per_page", 20, type=int)
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_area_filter              = request.args.get("energy_area_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                            = request.form.get("page", 1, type=int)
        per_page                        = request.form.get("per_page", 20, type=int)
        sort_by                         = request.form.get("sort_by", "id")
        sort_dir                        = request.form.get("sort_dir", "asc")
        energy_area_filter              = request.form.get("energy_area_filter", "").strip()
        regional_district_filter        = request.form.get("regional_district_filter", "").strip()
        regional_energy_system_filter   = request.form.get("regional_energy_system_filter", "").strip()
        union_energy_system_filter      = request.form.get("union_energy_system_filter", "").strip()

        # Получение данных из формы
        energy_area_ids         = request.form.getlist("energy_area_ids[]")
        energy_area_names       = request.form.getlist("energy_area_names[]")
        energy_area_delete      = request.form.getlist("energy_area_delete[]")
        regional_district_ids   = request.form.getlist("regional_district_ids[]")
        
        # Удаление записей
        if energy_area_delete:
            try:
                delete_energy_area_service(energy_area_delete, user)
                flash("Записи энергорайонов успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления энергорайонов': {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.energy_area_list", 
                                    page=page,
                                    per_page=per_page,
                                    sort_by=sort_by,
                                    sort_dir=sort_dir,
                                    energy_area_filter=energy_area_filter,
                                    regional_district_filter=regional_district_filter,
                                    regional_energy_system_filter=regional_energy_system_filter,
                                    union_energy_system_filter=union_energy_system_filter,
                                    ))

        # Обновление данных в базе
        try:
            if not (energy_area_ids and energy_area_names):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.energy_area_list", 
                                    page=page,
                                    per_page=per_page,
                                    sort_by=sort_by,
                                    sort_dir=sort_dir,
                                    energy_area_filter=energy_area_filter,
                                    regional_district_filter=regional_district_filter,
                                    regional_energy_system_filter=regional_energy_system_filter,
                                    union_energy_system_filter=union_energy_system_filter,
                                    ))
        
            # Формирование данных для обновления
            energy_area_data = []
            for energy_area_id, energy_area_name, regional_district_id in zip(
                energy_area_ids, energy_area_names, regional_district_ids
            ):
                try:
                    energy_area_data.append({
                        "energy_area_id": int(energy_area_id) if energy_area_id else None,
                        "name": energy_area_name.strip(),
                        "regional_district_id": int(regional_district_id) if regional_district_id else None
                    })
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки данных: id={energy_area_id},"
                            f"Наименование: {energy_area_name}, "
                            f"Субъект РФ: {get_regional_district_name(regional_district_id)}. "
                            f"Ошибка: {str(e)}"
                        )
                    )

            # Проверка на дублирующиеся IDs
            ids = [record["energy_area_id"] for record in energy_area_data if record["energy_area_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID энергорайона: {duplicates}")

            # Обновление данных в базе
            log_to_db(user, "Полученные данные для обновления энергорайона", str(energy_area_data))
            update_energy_area_service(energy_area_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных энергорайонов: {e}")
            flash("Ошибка сохранения данных энергорайонов.", "danger")

        return redirect(url_for("refdata_bp.energy_area_list",
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                energy_area_filter=energy_area_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                ))

    # Получение данных для отображения
    pagination = get_energy_area_list( 
                                page=page,
                                per_page=per_page,
                                sort_by=sort_by,
                                sort_dir=sort_dir,
                                energy_area_filter=energy_area_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                )
    
    # Подготовка данных для формы
    regional_district_list = get_regional_district_list_full()
    form.regional_district.choices = [(rd.id, rd.name) for rd in regional_district_list]

    regional_energy_system_list = get_regional_energy_system_list_full()
    form.regional_energy_system.choices = [(res.id, res.name) for res in regional_energy_system_list]

    union_energy_system_list = get_union_energy_system_list_full()
    form.union_energy_system.choices = [(ues.id, ues.name) for ues in union_energy_system_list]
    
    return render_template(
        "refdata/energy_systems/energy_area/energy_area.html",
        form=form,
        energy_area_list=pagination.items,
        pagination=pagination,
        regional_district_list=regional_district_list,
        regional_energy_system_list=regional_energy_system_list,
        union_energy_system_list=union_energy_system_list,
        energy_area_filter=energy_area_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_energy_area", methods=["GET", "POST"])
def add_energy_area():
    """Маршрут для добавления нового энергорайона."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления энергорайона")

    # Создание формы
    form = AddEnergyAreaForm()

    # Сохранение текущих фильтров и параметров отображения
    page                            = request.args.get("page", 1, type=int) or 1
    per_page                        = request.args.get("per_page", 20, type=int) or 10
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_area_filter              = request.args.get("energy_area_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()
 
    # Подготовка данных для формы
    regional_district_list = get_regional_district_list_full()
    form.regional_district.choices = [(t.id, t.name) for t in regional_district_list]

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/energy_systems/energy_area/energy_area_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "regional_district_id": form.regional_district.data,
            }]

            # Добавление новой записи
            add_energy_area_service(payload, user)
            log_to_db(user, "Добавление нового энергорайона", 
                    (
                        f"Наименование: {form.name.data}, "
                        f"Субъект РФ: {get_regional_district_name(form.regional_district.data)}"
                    )
            )
            flash("Новая запись успешно добавлена.", "success")
    
            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = energy_area_query(
                                energy_area_filter, 
                                regional_district_filter, 
                                regional_energy_system_filter, 
                                union_energy_system_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.energy_area_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_area_filter=energy_area_filter,
                regional_district_filter=regional_district_filter,
                regional_energy_system_filter=regional_energy_system_filter,
                union_energy_system_filter=union_energy_system_filter,
            ))
        
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового энергорайона", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления нового энергорайона", str(e))

    # Рендеринг формы
    return render_template(
        "refdata/energy_systems/energy_area/energy_area_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form, 
        energy_area_filter=energy_area_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
    )


@refdata_bp.route("/export_energy_area_to_excel", methods=["GET"])
def export_energy_area():
    """Маршрут для экспорта данных в Excel."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат экспорт списка энергорайонов в Excel")
    
    sort_by                         = request.args.get("sort_by", "id")
    sort_dir                        = request.args.get("sort_dir", "asc")
    energy_area_filter              = request.args.get("energy_area_filter", "").strip()
    regional_district_filter        = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter   = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter      = request.args.get("union_energy_system_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_energy_area_service(
            user=user, 
            sort_by=sort_by, 
            sort_dir=sort_dir,
            energy_area_filter=energy_area_filter, 
            regional_district_filter=regional_district_filter, 
            regional_energy_system_filter=regional_energy_system_filter, 
            union_energy_system_filter=union_energy_system_filter, 
        )

        log_to_db(user, "Экспорт завершен", 
                    (
                        f"Фильтры: {energy_area_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter},"
                        f"Сортировка: {sort_by},"
                        f"Направление: {sort_dir}"
                    )
        )
        
        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.energy_area_list"))
        
        # Формирование имени файла
        filename = f"energy_area_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("refdata_bp.energy_area_list"))