from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.models.energy_systems_models import RegionalEnergySystem
from app.forms.regional_energy_system_forms import RegionalEnergySystemFilterForm, AddRegionalEnergySystemForm
from app.services.regional_energy_system_services import (
    get_regional_energy_system_list, get_union_energy_system, update_regional_energy_system, add_regional_energy_system, delete_regional_energy_system_list, get_regional_districts,
    import_regional_energy_system_from_excel, export_regional_energy_system_to_excel, log_to_db, get_total_with_filter
)


from app import db
from app.models.logs_models import Log

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


from collections import Counter

@app_bp.route("/regional_energy_system", methods=["GET", "POST"])
def regional_energy_system_list():
    """Маршрут для отображения списка региональных энергосистем."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница региональных энергосистем")

    form = RegionalEnergySystemFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        try:
            # Обновление параметров из формы
            page = request.form.get("page", 1, type=int)
            per_page = request.form.get("per_page", 10, type=int)
            sort_by = request.form.get("sort_by", "id")
            sort_dir = request.form.get("sort_dir", "asc")
            regional_energy_system_filter = request.form.get("regional_energy_system_filter", "").strip()
            union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()

            # Получение данных из формы
            regional_energy_system_ids = request.form.getlist("regional_energy_system_ids[]")
            regional_energy_system_names = request.form.getlist("regional_energy_system_names[]")
            union_energy_system_ids = request.form.getlist("union_energy_system[]")
            regional_energy_system_delete = request.form.getlist("regional_energy_system_delete[]")
            
            from collections import defaultdict

            # Группируем субъектов РФ по энергосистемам
            regional_districts_mapping = defaultdict(list)

            # Получаем список всех ID энергосистем
            regional_energy_system_values = request.form.getlist("regional_energy_system_ids[]")

            # Группируем субъектов по энергосистемам
            for system_id in regional_energy_system_values:
                selected_districts = request.form.getlist(f"regional_districts_{system_id}[]")  # Получаем все субъекты для конкретной энергосистемы
                regional_districts_mapping[int(system_id)] = [int(d) for d in selected_districts if d.isdigit()]  # Игнорируем "on"

            # Формируем данные для обновления
            regional_energy_system_data = []
            for regional_energy_system_id, regional_energy_system_name, union_energy_system_id in zip(
                regional_energy_system_ids, regional_energy_system_names, union_energy_system_ids
            ):
                regional_energy_system_data.append({
                    "id": int(regional_energy_system_id) if regional_energy_system_id else None,
                    "name": regional_energy_system_name.strip(),
                    "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
                    "regional_districts": regional_districts_mapping.get(int(regional_energy_system_id), [])  # Получаем список субъектов
                })

            # Удаление записей
            if regional_energy_system_delete:
                delete_regional_energy_system_list(regional_energy_system_delete, user)
                flash("Записи региональных энергосистем успешно удалены.", "success")

            # Формирование данных для обновления
            regional_energy_system_data = []
            for regional_energy_system_id, regional_energy_system_name, union_energy_system_id in zip(regional_energy_system_ids, regional_energy_system_names, union_energy_system_ids):
                regional_energy_system_data.append({
                    "id": int(regional_energy_system_id) if regional_energy_system_id else None,
                    "name": regional_energy_system_name.strip(),
                    "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
                    "regional_districts": regional_districts_mapping.get(int(regional_energy_system_id), [])  # Получаем ID субъектов РФ
                })

            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in regional_energy_system_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID региональных энергосистем: {duplicates}")

            log_to_db(user, "Полученные данные для обновления региональных энергосистем", str(regional_energy_system_data))

            # Обновление данных в базе
            update_regional_energy_system(regional_energy_system_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных региональных энергосистем: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.regional_energy_system_list",
                                page=page,
                                per_page=per_page,
                                regional_energy_system_filter=regional_energy_system_filter,
                                union_energy_system_filter=union_energy_system_filter,
                                sort_by=sort_by,
                                sort_dir=sort_dir
        ))

    # Получение данных для отображения
    pagination = get_regional_energy_system_list(page, 
                              per_page, 
                              regional_energy_system_filter, 
                              union_energy_system_filter, 
                              sort_by, 
                              sort_dir)
    
    # Подготовка данных для формы
    union_energy_system_list = get_union_energy_system()
    form.union_energy_system.choices = [(o.id, o.name) for o in union_energy_system_list]
    
    regional_districts_list = get_regional_districts()  # Получаем все субъекты РФ

    return render_template(
        "references/regional_energy_system/regional_energy_system.html",
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


@app_bp.route("/add_regional_energy_system", methods=["GET", "POST"])
def add_regional_energy_system_routes():
    """
    Маршрут для добавления новой региональной энергосистемы.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления региональной энергосистемы")

    # Создание формы
    form = AddRegionalEnergySystemForm()

    # Получение списка типов ОЭС и регионов
    try:
        union_energy_system = get_union_energy_system()
        if not union_energy_system:
            flash("Ошибка: отсутствует список ОЭС. Добавьте ОЭС перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют ОЭС.")
            return redirect(url_for("app_bp.regional_energy_system_list"))

        regional_districts = get_regional_districts()
        if not regional_districts:
            flash("Ошибка: отсутствует список регионов. Добавьте регионы перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют регионы.")
            return redirect(url_for("app_bp.regional_energy_system_list"))

        form.union_energy_system.choices = [(t.id, t.name) for t in union_energy_system]
        form.regional_districts.choices = [(r.id, r.name) for r in regional_districts]

        if form.regional_districts.data is None:
            form.regional_districts.data = []  # Инициализация пустым списком для исключения ошибки

    except Exception as e:
        current_app.logger.error(f"Ошибка получения данных: {e}")
        flash("Ошибка при загрузке данных. Попробуйте позже.", "danger")
        return redirect(url_for("app_bp.regional_energy_system_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
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
                "regional_energy_system/regional_energy_system_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_regional_energy_system_id = add_regional_energy_system([
                {
                    "name": form.name.data,
                    "union_energy_system_id": form.union_energy_system.data,
                    "regional_districts": form.regional_districts.data
                }
            ], user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой региональной энергосистемы", f"Имя: {form.name.data}, ОЭС: {form.union_energy_system.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_with_filter(regional_energy_system_filter, union_energy_system_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.regional_energy_system_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                regional_energy_system_filter=regional_energy_system_filter,
                union_energy_system_filter=union_energy_system_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_regional_energy_system_id
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

    # Рендеринг формы
    return render_template(
        "regional_energy_system/regional_energy_system_add.html", 
        form=form, 
        union_energy_system=form.union_energy_system.choices, 
        regional_districts=regional_districts, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_regional_energy_system_to_sql", methods=["POST"])
def import_regional_energy_system_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт региональных энергосистем из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.regional_energy_system_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.regional_energy_system_list"))

    try:
        imported_count = import_regional_energy_system_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.regional_energy_system_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_regional_energy_system_to_excel", methods=["GET"])
def export_regional_energy_system_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "").strip()
    union_energy_system_filter = request.args.get("union_energy_system_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_regional_energy_system_to_excel(user, regional_energy_system_filter, union_energy_system_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {regional_energy_system_filter, union_energy_system_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")
        
        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.regional_energy_system_list"))
        
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
        return redirect(url_for("app_bp.regional_energy_system_list"))