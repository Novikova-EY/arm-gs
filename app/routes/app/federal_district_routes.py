from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.federal_district_forms import FederalDistrictFilter, AddFederalDistrict
from app.services.federal_district_services import (
    get_federal_district_list, update_federal_district, add_federal_district, delete_federal_district_list,
    import_federal_district_from_excel, export_federal_district_to_excel, log_to_db, get_total_federal_district_records
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

@app_bp.route("/federal_district", methods=["GET", "POST"])
def federal_district_list():
    """Маршрут для отображения списка ФО."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ФО")
    
    form = FederalDistrictFilter()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    federal_district_filter = request.args.get("federal_district_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        federal_district_filter = request.form.get("federal_district_filter", "").strip()

        # Получение данных из формы
        federal_district_ids = request.form.getlist("federal_district_ids[]")
        federal_district_names = request.form.getlist("federal_district_names[]")
        federal_district_full_names = request.form.getlist("federal_district_full_names[]")
        federal_district_abr_names = request.form.getlist("federal_district_abr_names[]")
        federal_district_delete = request.form.getlist("federal_district_delete[]")
  
        # Удаление записей
        if federal_district_delete:
            try:
                delete_federal_district_list(federal_district_delete, user)
                flash("Записи успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления записей: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("app_bp.federal_district_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    federal_district_filter=federal_district_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not (federal_district_ids and federal_district_names and federal_district_full_names and federal_district_abr_names):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("app_bp.federal_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        federal_district_filter=federal_district_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            federal_district_data = []
            for federal_district_id, federal_district_name, federal_district_full_name, federal_district_abr_name in zip(
                federal_district_ids, federal_district_names, federal_district_full_names, federal_district_abr_names
            ):
                # Проверка на пустое имя
                if not federal_district_name.strip():
                    log_to_db(user, f"Пустое имя обнаружено: ID={federal_district_id}")
                    raise ValueError(f"Пустое имя для ID: {federal_district_id}")

                federal_district_data.append({
                    "id": int(federal_district_id) if federal_district_id else None,
                    "name": federal_district_name.strip(),
                    "name_full": federal_district_full_name.strip(),
                    "name_abr": federal_district_abr_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in federal_district_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID ФО: {duplicates}")

            # Обновление данных в базе
            update_federal_district(federal_district_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных ФО: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.federal_district_list", 
                                page=page, 
                                per_page=per_page, 
                                federal_district_filter=federal_district_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_federal_district_list(page, 
                              per_page, 
                              federal_district_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "references/federal_district/federal_district.html",
        form=form,
        federal_district_list=pagination.items,
        pagination=pagination,
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@app_bp.route("/add_federal_district", methods=["GET", "POST"])
def add_federal_district_routes():
    """
    Маршрут для добавления нового ФО.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ФО")

    # Создание формы
    form = AddFederalDistrict()

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    federal_district_filter = request.args.get("federal_district_filter", "").strip()
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
                "references/federal_district/federal_district_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_federal_district_id = add_federal_district([{
                "name": form.name.data,
                "name_full": form.name_full.data,
                "name_abr": form.name_abr.data}], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового ФО", f"Имя: {form.name.data} ")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_federal_district_records(federal_district_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.federal_district_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                federal_district_filter=federal_district_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_federal_district_id
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
        "references/federal_district/federal_district_add.html", 
        form=form,
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        federal_district_filter=federal_district_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_federal_district_to_sql", methods=["POST"])
def import_federal_district_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт ФО из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.federal_district_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.federal_district_list"))

    try:
        imported_count = import_federal_district_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.federal_district_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_federal_district_to_excel", methods=["GET"])
def export_federal_district_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    federal_district_filter = request.args.get("federal_district_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_federal_district_to_excel(user, federal_district_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {federal_district_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.federal_district_list"))
        
        # Формирование имени файла
        filename = f"federal_district_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("app_bp.federal_district_list"))
