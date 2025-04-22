from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.fuel_forms import OesFilterForm, AddOesForm
from app.services.fuel_services import (
    get_fuel_list, get_fuel_types, update_fuel, add_fuel, delete_fuel_list,
    import_fuel_from_excel, export_fuel_to_excel, log_to_db, get_total_fuel_records
)
from app import db
from app.models.logs_models import Log
from app.services.logging_service import log_to_db
from collections import Counter

@app_bp.route("/fuel", methods=["GET", "POST"])
def fuel_list():
    """Маршрут для отображения списка типов топлива."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница типов топлива")
    
    form = OesFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    fuel_filter = request.args.get("fuel_filter", "").strip()
    fuel_type_filter = request.args.get("fuel_type_filter")
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":       
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        fuel_filter = request.form.get("fuel_filter", "").strip()
        fuel_type_filter = request.form.get("fuel_type_filter")

        # Получение данных из формы
        fuel_ids = request.form.getlist("fuel_ids[]")
        fuel_names = request.form.getlist("fuel_names[]")
        fuel_types = request.form.getlist("fuel_types[]")
        fuel_delete = request.form.getlist("fuel_delete[]")
  
        # Удаление записей
        if fuel_delete:
            try:
                delete_fuel_list(fuel_delete, user)
                flash("Записи типов топлива успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления типов топлива: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("app_bp.fuel_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    fuel_filter=fuel_filter,
                                    fuel_type_filter=fuel_type_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
        # Обновление данных в базе
        try:
            if not fuel_ids or not fuel_names:
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("app_bp.fuel_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_filter=fuel_filter,
                                        fuel_type_filter=fuel_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            fuel_data = []
            for fuel_id, fuel_name, fuel_type in zip(fuel_ids, fuel_names, fuel_types):
                fuel_data.append({
                    "id": int(fuel_id) if fuel_id else None,
                    "name": fuel_name.strip(),
                    "fuel_type_id": int(fuel_type) if fuel_type else None
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in fuel_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов топлива: {duplicates}")

            # Обновление данных в базе
            update_fuel(fuel_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных типов топлива: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.fuel_list", 
                                page=page, 
                                per_page=per_page, 
                                fuel_filter=fuel_filter,
                                fuel_type_filter=fuel_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_fuel_list(page, 
                              per_page, 
                              fuel_filter,
                              fuel_type_filter,
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    fuel_types = get_fuel_types()
    form.fuel_type.choices = [(t.id, t.name) for t in fuel_types]

    return render_template(
        "references/fuel/fuel.html",
        form=form,
        fuel_list=pagination.items,
        pagination=pagination,
        fuel_types=form.fuel_type.choices,
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/add_fuel", methods=["GET", "POST"])
def add_fuel_routes():
    """
    Маршрут для добавления нового топлива.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления типов топлива")

    # Создание формы
    form = AddOesForm()

    # Получение списка видов топлива
    try:
        fuel_types = get_fuel_types()
        if not fuel_types:
            flash("Ошибка: отсутствуют виды топлива. Добавьте типы перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления ОЭС", "Отсутствуют виды топлива.")
            return redirect(url_for("app_bp.fuel_list"))

        form.fuel_type.choices = [(t.id, t.name) for t in fuel_types]
    except Exception as e:
        current_app.logger.error(f"Ошибка получения видов топлива: {e}")
        flash("Ошибка при загрузке данных видов топлива.", "danger")
        return redirect(url_for("app_bp.fuel_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    fuel_filter = request.args.get("fuel_filter", "").strip()
    fuel_type_filter = request.args.get("fuel_type_filter")
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "references/fuel/fuel_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_fuel_id = add_fuel([{
                "name": form.name.data, 
                "fuel_type_id": form.fuel_type.data}], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового типа топлива", f"Имя: {form.name.data}, Вид: {form.fuel_type.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_fuel_records(fuel_filter, fuel_type_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.fuel_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                fuel_filter=fuel_filter,
                fuel_type_filter = fuel_type_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_fuel_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления ОЭС", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления типа топлива", str(e))

    # Рендеринг формы
    return render_template(
        "references/fuel/fuel_add.html", 
        form=form, 
        fuel_types=form.fuel_type.choices, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        fuel_filter=fuel_filter, 
        fuel_type_filter=fuel_type_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_fuel_to_sql", methods=["POST"])
def import_fuel_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт типов топлива из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.fuel_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.fuel_list"))

    try:
        imported_count = import_fuel_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.fuel_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_fuel_to_excel", methods=["GET"])
def export_fuel_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    fuel_filter = request.args.get("fuel_filter", "").strip()
    fuel_type_filter = request.args.get("fuel_type_filter")
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_fuel_to_excel(user, fuel_filter, fuel_type_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {fuel_filter, fuel_type_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.fuel_list"))
        
        # Формирование имени файла
        filename = f"fuel_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("app_bp.fuel_list"))
