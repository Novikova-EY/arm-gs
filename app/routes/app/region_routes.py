from flask import (
    render_template, request, redirect, url_for, flash, Response, session, current_app
)
from . import app_bp
from app.forms.region_forms import RegionFilterForm, AddRegionForm
from app.services.region_services import (
    get_region_list, get_fos, update_region, add_region, delete_region_list,
    import_region_from_excel, export_region_to_excel, log_to_db, get_total_region_records
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

@app_bp.route("/region", methods=["GET", "POST"])
def region_list():
    """Маршрут для отображения списка субъектов РФ."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница субъектов РФ")
    
    form = RegionFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    name_filter = request.args.get("name_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        try:
            page = request.form.get("page", 1, type=int)
            per_page = request.form.get("per_page", 10, type=int)
            sort_by = request.form.get("sort_by", "id")
            sort_dir = request.form.get("sort_dir", "asc")
            name_filter = request.form.get("name_filter", "").strip()

            region_ids = request.form.getlist("region_ids[]")
            region_names = request.form.getlist("region_names[]")
            fo = request.form.getlist("fo[]")
            region_delete = request.form.getlist("region_delete[]")

            if not all(isinstance(lst, list) for lst in [region_ids, region_names, fo]):
                raise ValueError("Получены некорректные данные: один из параметров не является списком.")
   
            # Удаление записей
            if region_delete:
                delete_region_list(region_delete, user)
                flash("Записи успешно удалены.", "success")

            # Обновление записей
            region_data = []
            for region_id, region_name, fo in zip(region_ids, region_names, fo):
                try:
                    region_data.append({
                        "id": int(region_id) if region_id else None,
                        "name": region_name.strip(),
                        "fo_id": int(fo) if fo else None
                    })
                except ValueError as e:
                    raise ValueError(f"Ошибка обработки данных: id={region_id}, name={region_name}, type={fo}. Ошибка: {str(e)}")
            
            ids = [record["id"] for record in region_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            update_region(region_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных: {e}")

        return redirect(url_for("app_bp.region_list", 
                                page=page, 
                                per_page=per_page, 
                                name_filter=name_filter, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_region_list(page, 
                              per_page, 
                              name_filter, 
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    fo = get_fos()
    form.fo.choices = [(0, "Не указан")] + [(t.id, t.name) for t in fo]

    return render_template(
        "region/region.html",
        form=form,
        region_list=pagination.items,
        pagination=pagination,
        fo_list=form.fo.choices,
        name_filter=name_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/add_region", methods=["GET", "POST"])
def add_region_routes():
    """
    Маршрут для добавления новой ОЭС.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления субъекта РФ")

    # Создание формы
    form = AddRegionForm()

    # Получение списка типов ОЭС
    try:
        fo = get_fos()
        if not fo:
            flash("Ошибка: отсутствует список ФО. Добавьте ФО перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют ФО.")
            return redirect(url_for("app_bp.region_list"))

        form.fo.choices = [(t.id, t.name) for t in fo]
    except Exception as e:
        current_app.logger.error(f"Ошибка получения списка ФО: {e}")
        flash("Ошибка при загрузке списка ФО.", "danger")
        return redirect(url_for("app_bp.region_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    name_filter = request.args.get("name_filter", "").strip()
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            # Добавление новой записи через сервис
            new_region_id = add_region([{"name": form.name.data, "fo_id": form.fo.data}], user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового субъекта РФ", f"Имя: {form.name.data}, ФО: {form.fo.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_region_records(name_filter)  # Предполагается функция получения общего числа записей
            last_page = (total_records + per_page - 1) // per_page  # Вычисление последней страницы

            # Если текущая страница больше последней, корректируем её
            page = min(page, last_page)

            return redirect(url_for(
                "app_bp.region_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                name_filter=name_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_region_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового субъекта РФ", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления ОЭС", str(e))

    # Рендеринг формы
    return render_template(
        "region/region_add.html", 
        form=form, 
        fo=form.fo.choices, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        name_filter=name_filter, 
        per_page=per_page, 
        page=page
    )


@app_bp.route("/import_region_to_sql", methods=["POST"])
def import_region_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт списка субъектов РФ из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.region_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.region_list"))

    try:
        imported_count = import_region_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.region_list"))


from datetime import datetime

@app_bp.route("/export_region_to_excel", methods=["GET"])
def export_region_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    name_filter = request.args.get("name_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        excel_data = export_region_to_excel(user, name_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {name_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        filename = f"region_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных.", "danger")
        return redirect(url_for("app_bp.region_list"))
