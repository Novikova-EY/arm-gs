from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.oes_forms import OesFilterForm, AddOesForm
from app.services.oes_services import (
    get_oes_list, get_oes_types, update_oes, add_oes, delete_oes_list,
    import_oes_from_excel, export_oes_to_excel, log_to_db, get_total_oes_records
)


from app import db
from app.models.log_models import Log

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


from collections import Counter

@app_bp.route("/oes", methods=["GET", "POST"])
def oes_list():
    """Маршрут для отображения списка ОЭС."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ОЭС")
    
    form = OesFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    oes_filter = request.args.get("oes_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        try:
            # Обновление параметров из формы
            page = request.form.get("page", 1, type=int)
            per_page = request.form.get("per_page", 10, type=int)
            sort_by = request.form.get("sort_by", "id")
            sort_dir = request.form.get("sort_dir", "asc")
            oes_filter = request.form.get("oes_filter", "").strip()

            # Получение данных из формы
            oes_ids = request.form.getlist("oes_ids[]")
            oes_names = request.form.getlist("oes_names[]")
            oes_types = request.form.getlist("oes_types[]")
            oes_delete = request.form.getlist("oes_delete[]")
  
            # Удаление записей
            if oes_delete:
                delete_oes_list(oes_delete, user)
                flash("Записи ОЭС успешно удалены.", "success")

           # Формирование данных для обновления
            oes_data = []
            for oes_id, oes_name, oes_type in zip(oes_ids, oes_names, oes_types):
                oes_data.append({
                    "id": int(oes_id) if oes_id else None,
                    "name": oes_name.strip(),
                    "oes_type_id": int(oes_type) if oes_type else None
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in oes_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID ОЭС: {duplicates}")

            # Обновление данных в базе
            update_oes(oes_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных ОЭС: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.oes_list", 
                                page=page, 
                                per_page=per_page, 
                                oes_filter=oes_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_oes_list(page, 
                              per_page, 
                              oes_filter, 
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    oes_types = get_oes_types()
    form.oes_type.choices = [(0, "Не указан")] + [(t.id, t.name) for t in oes_types]

    return render_template(
        "oes/oes.html",
        form=form,
        oes_list=pagination.items,
        pagination=pagination,
        oes_types=form.oes_type.choices,
        oes_filter=oes_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/add_oes", methods=["GET", "POST"])
def add_oes_routes():
    """
    Маршрут для добавления новой ОЭС.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ОЭС")

    # Создание формы
    form = AddOesForm()

    # Получение списка типов ОЭС
    try:
        oes_types = get_oes_types()
        if not oes_types:
            flash("Ошибка: отсутствуют типы ОЭС. Добавьте типы перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления ОЭС", "Отсутствуют типы ОЭС.")
            return redirect(url_for("app_bp.oes_list"))

        form.oes_type.choices = [(t.id, t.name) for t in oes_types]
    except Exception as e:
        current_app.logger.error(f"Ошибка получения типов ОЭС: {e}")
        flash("Ошибка при загрузке данных типов ОЭС.", "danger")
        return redirect(url_for("app_bp.oes_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    oes_filter = request.args.get("oes_filter", "").strip()
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
                "oes/oes_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_oes_id = add_oes([{
                "name": form.name.data, 
                "oes_type_id": form.oes_type.data}], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой ОЭС", f"Имя: {form.name.data}, Тип: {form.oes_type.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_oes_records(oes_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.oes_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                oes_filter=oes_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_oes_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления ОЭС", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления ОЭС", str(e))

    # Рендеринг формы
    return render_template(
        "oes/oes_add.html", 
        form=form, 
        oes_types=form.oes_type.choices, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        oes_filter=oes_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_oes_to_sql", methods=["POST"])
def import_oes_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт ОЭС из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.oes_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.oes_list"))

    try:
        imported_count = import_oes_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.oes_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_oes_to_excel", methods=["GET"])
def export_oes_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    oes_filter = request.args.get("oes_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_oes_to_excel(user, oes_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {oes_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.oes_list"))
        
        # Формирование имени файла
        filename = f"region_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("app_bp.oes_list"))
