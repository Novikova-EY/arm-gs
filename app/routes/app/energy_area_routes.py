from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from app import db
from . import app_bp
from app.models.logs_models import Log
from app.models.energy_systems_models import RegionalEnergySystem
from app.forms.energy_area_forms import EnergyAreaFilterForm, AddEnergyAreaForm
from app.services.energy_area_services import (
    get_energy_area_list, get_regional_energy_system, get_union_energy_system, update_energy_area, add_energy_area, delete_energy_area_list, get_regional_districts,
    export_energy_area_to_excel, log_to_db, get_total_with_filter
)


def log_to_db(username, action, details=None):
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


from collections import Counter

@app_bp.route("/energy_areas", methods=["GET", "POST"])
def energy_area_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница энергорайонов")

    form = EnergyAreaFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    energy_area_filter = request.args.get("energy_area_filter", "").strip()
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        try:
            # Обновление параметров из формы
            page = request.form.get("page", 1, type=int)
            per_page = request.form.get("per_page", 10, type=int)
            energy_area_filter = request.form.get("energy_area_filter", "").strip()
            regional_district_filter = request.form.get("regional_district_filter", "").strip()
            regional_energy_system_filter = request.form.get("regional_energy_system_filter", "").strip()
            union_energy_system_filter = request.form.get("union_energy_system_filter", "").strip()
            sort_by = request.form.get("sort_by", "id")
            sort_dir = request.form.get("sort_dir", "asc")

            # Получение данных из формы
            energy_area_ids = request.form.getlist("energy_area_ids[]")
            energy_area_names = request.form.getlist("energy_area_names[]")
            regional_district_ids = request.form.getlist("regional_district_ids[]")
            energy_area_delete = request.form.getlist("energy_area_delete[]")
            
            # Удаление записей
            if energy_area_delete:
                delete_energy_area_list(energy_area_delete, user)
                flash("Запись(и) энергорайона(ов) успешно удален(ы).", "success")

            # Формируем данные для обновления
            energy_area_data = []
            for energy_area_id, energy_area_name, regional_district_id in zip(
                energy_area_ids, energy_area_names, regional_district_ids
            ):
                energy_area_data.append({
                    "id": int(energy_area_id) if energy_area_id else None,
                    "name": energy_area_name.strip(),
                    "regional_district_id": int(regional_district_id) if regional_district_id else None,
                })

            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in energy_area_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID энергорайона: {duplicates}")

            log_to_db(user, "Полученные данные для обновления энергорайона", str(energy_area_data))

            # Обновление данных в базе
            update_energy_area(energy_area_data, user)

            flash("Изменения энергорайона(ов) успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных энергорайона(ов): {e}")
            flash("Ошибка сохранения данных энергорайона(ов).", "danger")

        return redirect(url_for("app_bp.energy_area_list",
                                page=page,
                                per_page=per_page,
                                energy_area_filter=energy_area_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                sort_by=sort_by,
                                sort_dir=sort_dir
        ))

    # Получение данных для отображения
    pagination = get_energy_area_list( 
                                page=page,
                                per_page=per_page,
                                energy_area_filter=energy_area_filter,
                                regional_district_filter=regional_district_filter,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                sort_by=sort_by,
                                sort_dir=sort_dir)
    
    # Подготовка данных для формы
    regional_district_list = get_regional_districts()
    form.regional_district.choices = [(o.id, o.name) for o in regional_district_list if o.id != 100]

    regional_energy_system_list = get_regional_energy_system()
    form.regional_energy_system.choices = [(o.id, o.name) for o in regional_energy_system_list if o.id != 100]

    union_energy_system_list = get_union_energy_system()
    form.union_energy_system.choices = [(o.id, o.name) for o in union_energy_system_list if o.id != 100]
    
    return render_template(
        "references/energy_area/energy_area.html",
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


@app_bp.route("/add_energy_area", methods=["GET", "POST"])
def add_energy_area_routes():
    """
    Маршрут для добавления нового энергорайона.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления энергорайона")

    # Создание формы
    form = AddEnergyAreaForm(request.form)

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    energy_area_filter = request.args.get("energy_area_filter", "").strip()
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))
 
    # Подготовка данных для формы
    regional_district_list = get_regional_districts()
    form.regional_district.choices = [(o.id, o.name) for o in regional_district_list if o.id != 100]
    
    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "references/energy_area/energy_area_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_energy_area_id = add_energy_area([
                {
                    "name": form.name.data,
                    "regional_district": form.regional_district.data
                }
            ], user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового энергорайона", f"Имя: {form.name.data}, ОЭС: {form.regional_district.data}")

            total_records = get_total_with_filter(energy_area_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter)
            last_page = (total_records + per_page - 1) // per_page

            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.energy_area_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                energy_area_filter=energy_area_filter,
                regional_district_filter=regional_district_filter,
                regional_energy_system_filter=regional_energy_system_filter,
                union_energy_system_filter=union_energy_system_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_energy_area_id
            ))
        except ValueError as e:
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового энергорайона", str(e))
        except Exception as e:
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления нового энергорайона", str(e))


    return render_template(
        "references/energy_area/energy_area_add.html", 
        form=form, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        energy_area_filter=energy_area_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        per_page=per_page, 
        page=page
    )


from flask import send_file
from datetime import datetime

@app_bp.route("/export_energy_area_to_excel", methods=["GET"])
def export_energy_area_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    energy_area_filter = request.args.get("energy_area_filter", "").strip()
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_energy_area_to_excel(user, energy_area_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {energy_area_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")
        
        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.energy_area_list"))
        
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
        return redirect(url_for("app_bp.energy_area_list"))