from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.fo_forms import FoFilterForm, AddFoForm
from app.services.fo_services import (
    get_fo_list, update_fo, add_fo, delete_fo_list,
    import_fo_from_excel, export_fo_to_excel, log_to_db, get_total_fo_records
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

@app_bp.route("/fo", methods=["GET", "POST"])
def fo_list():
    """Маршрут для отображения списка ФО."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ФО")
    
    form = FoFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    fo_filter = request.args.get("fo_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        try:
            # Обновление параметров из формы
            page = request.form.get("page", 1, type=int)
            per_page = request.form.get("per_page", 10, type=int)
            sort_by = request.form.get("sort_by", "id")
            sort_dir = request.form.get("sort_dir", "asc")
            fo_filter = request.form.get("fo_filter", "").strip()

            # Получение данных из формы
            fo_ids = request.form.getlist("fo_ids[]")
            fo_names = request.form.getlist("fo_names[]")
            fo_delete = request.form.getlist("fo_delete[]")
  
            # Удаление записей
            if fo_delete:
                delete_fo_list(fo_delete, user)
                flash("Записи ФО успешно удалены.", "success")

           # Формирование данных для обновления
            fo_data = []
            for fo_id, fo_name in zip(fo_ids, fo_names):
                if fo_name is None or fo_name.strip() == "":
                    log_to_db(user, f"Пустое имя обнаружено: ID={fo_id}")
                    raise ValueError(f"Пустое имя для ID: {fo_id}")
                fo_data.append({
                    "id": int(fo_id) if fo_id else None,
                    "name": fo_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in fo_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID ФО: {duplicates}")

            # Обновление данных в базе
            update_fo(fo_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных ФО: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.fo_list", 
                                page=page, 
                                per_page=per_page, 
                                fo_filter=fo_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_fo_list(page, 
                              per_page, 
                              fo_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "fo/fo.html",
        form=form,
        fo_list=pagination.items,
        pagination=pagination,
        fo_filter=fo_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/add_fo", methods=["GET", "POST"])
def add_fo_routes():
    """
    Маршрут для добавления нового ФО.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ФО")

    # Создание формы
    form = AddFoForm()

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    fo_filter = request.args.get("fo_filter", "").strip()
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
                "fo/fo_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_fo_id = add_fo([{
                "name": form.name.data }], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового ФО", f"Имя: {form.name.data} ")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_fo_records(fo_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.fo_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                fo_filter=fo_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_fo_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления ФО", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления ФО", str(e))

    # Рендеринг формы
    return render_template(
        "fo/fo_add.html", 
        form=form,
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        fo_filter=fo_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_fo_to_sql", methods=["POST"])
def import_fo_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт ФО из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.fo_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.fo_list"))

    try:
        imported_count = import_fo_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.fo_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_fo_to_excel", methods=["GET"])
def export_fo_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    fo_filter = request.args.get("fo_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_fo_to_excel(user, fo_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {fo_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.fo_list"))
        
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
        return redirect(url_for("app_bp.fo_list"))
