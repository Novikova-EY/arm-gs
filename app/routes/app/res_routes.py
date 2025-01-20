from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.forms.res_forms import ResFilterForm, AddResForm
from app.services.res_services import (
    get_res_list, get_oes, update_res, add_res, delete_res_list, get_regions,
    import_res_from_excel, export_res_to_excel, log_to_db, get_total_with_filter
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

@app_bp.route("/res", methods=["GET", "POST"])
def res_list():
    """Маршрут для отображения списка региональных энергосистем."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница региональных энергосистем")

    form = ResFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    res_filter = request.args.get("res_filter", "").strip()
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
            res_filter = request.form.get("res_filter", "").strip()
            oes_filter = request.args.get("oes_filter", "").strip()

            # Получение данных из формы
            res_ids = request.form.getlist("res_ids[]")
            res_names = request.form.getlist("res_names[]")
            oes_ids = request.form.getlist("oes[]")
            res_delete = request.form.getlist("res_delete[]")
            res_regions = {
                int(res_id): request.form.getlist(f"region_ids_{res_id}[]")
                for res_id in res_ids
            }

            # Удаление записей
            if res_delete:
                delete_res_list(res_delete, user)
                flash("Записи региональных энергосистем успешно удалены.", "success")

            # Формирование данных для обновления
            res_data = []
            for res_id, res_name, oes_id in zip(res_ids, res_names, oes_ids):
                res_data.append({
                    "id": int(res_id) if res_id else None,
                    "name": res_name.strip(),
                    "oes_id": int(oes_id) if oes_id else None,
                    "regions": [int(region_id) for region_id in res_regions[int(res_id)]]
                })

            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in res_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID региональных энергосистем: {duplicates}")

            log_to_db(user, "Полученные данные для обновления региональных энергосистем", str(res_data))

            # Обновление данных в базе
            update_res(res_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных региональных энергосистем: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("app_bp.res_list",
                                page=page,
                                per_page=per_page,
                                res_filter=res_filter,
                                oes_filter=oes_filter,
                                sort_by=sort_by,
                                sort_dir=sort_dir
        ))

    # Получение данных для отображения
    pagination = get_res_list(page, 
                              per_page, 
                              res_filter, 
                              oes_filter, 
                              sort_by, 
                              sort_dir)
    
    # Подготовка данных для формы
    oes_list = get_oes()
    form.oes.choices = [(0, "Не указан")] + [(o.id, o.name) for o in oes_list]
    
    regions = get_regions()  # Получаем все регионы
    for item in pagination.items:
        # Получаем список ID регионов, связанных с конкретным Res
        item.region_ids = [region.id_region for region in item.regions]

    return render_template(
        "res/res.html",
        form=form,
        res_list=pagination.items,
        pagination=pagination,
        oes_list=form.oes.choices,
        regions_list=regions,
        res_filter=res_filter,
        oes_filter=oes_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@app_bp.route("/add_res", methods=["GET", "POST"])
def add_res_routes():
    """
    Маршрут для добавления новой региональной энергосистемы.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления региональной энергосистемы")

    # Создание формы
    form = AddResForm()

    # Получение списка типов ОЭС и регионов
    try:
        oes = get_oes()
        if not oes:
            flash("Ошибка: отсутствует список ОЭС. Добавьте ОЭС перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют ОЭС.")
            return redirect(url_for("app_bp.res_list"))

        regions = get_regions()
        if not regions:
            flash("Ошибка: отсутствует список регионов. Добавьте регионы перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют регионы.")
            return redirect(url_for("app_bp.res_list"))

        form.oes.choices = [(t.id, t.name) for t in oes]
        form.regions.choices = [(r.id, r.name) for r in regions]

        if form.regions.data is None:
            form.regions.data = []  # Инициализация пустым списком для исключения ошибки

    except Exception as e:
        current_app.logger.error(f"Ошибка получения данных: {e}")
        flash("Ошибка при загрузке данных. Попробуйте позже.", "danger")
        return redirect(url_for("app_bp.res_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    res_filter = request.args.get("res_filter", "").strip()
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
                "res/res_add.html",
                form=form
            )
        
        try:
            # Добавление новой записи через сервис
            new_res_id = add_res([
                {
                    "name": form.name.data,
                    "oes_id": form.oes.data,
                    "regions": form.regions.data
                }
            ], user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление новой региональной энергосистемы", f"Имя: {form.name.data}, ОЭС: {form.oes.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_with_filter(res_filter, oes_filter)
            last_page = (total_records + per_page - 1) // per_page

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.res_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                res_filter=res_filter,
                oes_filter=oes_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_res_id
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
        "res/res_add.html", 
        form=form, 
        oes=form.oes.choices, 
        regions=regions, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        res_filter=res_filter,
        oes_filter=oes_filter,
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_res_to_sql", methods=["POST"])
def import_res_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт региональных энергосистем из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.res_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.res_list"))

    try:
        imported_count = import_res_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.res_list"))


from flask import send_file
from datetime import datetime

@app_bp.route("/export_res_to_excel", methods=["GET"])
def export_res_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    res_filter = request.args.get("res_filter", "").strip()
    oes_filter = request.args.get("oes_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        # Получение данных для экспорта
        excel_data = export_res_to_excel(user, res_filter, oes_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {res_filter, oes_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")
        
        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.res_list"))
        
        # Формирование имени файла
        filename = f"res_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

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
        return redirect(url_for("app_bp.res_list"))

