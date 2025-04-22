from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.gen_company_forms import GenCompanyFilterForm, AddGenCompanyForm
from app.services.gen_company_services import (
    get_gen_company_list, update_gen_company, add_gen_company, delete_gen_company_list,
    import_gen_company_from_excel, export_gen_company_to_excel, log_to_db, get_total_gen_company_records
)
from app import db
from app.models.logs_models import Log
from app.services.logging_service import log_to_db
from collections import Counter

@app_bp.route("/gen_company", methods=["GET", "POST"])
def gen_company_list():
    """Маршрут для отображения списка генерирующих компаний."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница генерирующих компаний")
    
    form = GenCompanyFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    gen_company_filter = request.args.get("gen_company_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        gen_company_filter = request.form.get("gen_company_filter", "").strip()

        # Получение данных из формы
        gen_company_ids = request.form.getlist("gen_company_ids[]")
        gen_company_names = request.form.getlist("gen_company_names[]")
        gen_company_delete = request.form.getlist("gen_company_delete[]")
        
        # Удаление записей
        if gen_company_delete:
            try:
                delete_gen_company_list(gen_company_delete, user)
                flash("Записи генерирующих компаний успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления генерирующих компаний: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("app_bp.gen_company_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    gen_company_filter=gen_company_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not gen_company_ids or not gen_company_names:
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("app_bp.gen_company_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        gen_company_filter=gen_company_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            gen_company_data = []
            for gen_company_id, gen_company_name in zip(gen_company_ids, gen_company_names):
                if gen_company_name is None or gen_company_name.strip() == "":
                    log_to_db(user, f"Пустое имя обнаружено: ID={gen_company_id}")
                    raise ValueError(f"Пустое имя для ID: {gen_company_id}")
                gen_company_data.append({
                    "id": int(gen_company_id) if gen_company_id else None,
                    "name": gen_company_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in gen_company_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID генерирующих компаний: {duplicates}")

            # Обновление данных в базе
            update_gen_company(gen_company_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных генерирующих компаний: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.gen_company_list", 
                                page=page, 
                                per_page=per_page, 
                                gen_company_filter=gen_company_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_gen_company_list(page, 
                              per_page, 
                              gen_company_filter, 
                              sort_by, 
                              sort_dir)

    return render_template(
        "references/gen_company/gen_company.html",
        form=form,
        gen_company_list=pagination.items,
        pagination=pagination,
        gen_company_filter=gen_company_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/add_gen_company", methods=["GET", "POST"])
def add_gen_company_routes():
    """
    Маршрут для добавления новой генерирующей компании.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления генерирующей компании")

    # Создание формы
    form = AddGenCompanyForm()

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    gen_company_filter = request.args.get("gen_company_filter", "").strip()
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
                "references/gen_company/gen_company_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_gen_company_id = add_gen_company([{
                "name": form.name.data }], 
                user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой генерирующей компании", f"Имя: {form.name.data} ")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_gen_company_records(gen_company_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.gen_company_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                gen_company_filter=gen_company_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_gen_company_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления генерирующей компании", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления генерирующей компании", str(e))

    # Рендеринг формы
    return render_template(
        "references/gen_company/gen_company_add.html", 
        form=form,
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        gen_company_filter=gen_company_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_gen_company_to_sql", methods=["POST"])
def import_gen_company_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт списка генерирующих компаний из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.gen_company_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.gen_company_list"))

    try:
        imported_count = import_gen_company_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.gen_company_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_gen_company_to_excel", methods=["GET"])
def export_gen_company_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    gen_company_filter = request.args.get("gen_company_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_gen_company_to_excel(user, gen_company_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {gen_company_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.gen_company_list"))
        
        # Формирование имени файла
        filename = f"gen_company_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("app_bp.gen_company_list"))
