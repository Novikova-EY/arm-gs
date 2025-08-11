from flask import (
    render_template, request, redirect, url_for, flash, Response, session, current_app
)
from . import reference_bp
from app.refdata.forms.regional_district_forms import RegionalDistrictFilterForm, AddRegionalDistrictForm
from app.refdata.services.regional_district_services import (
    get_regional_district_list, get_regional_district_list, get_federal_district_list, update_regional_district, add_regional_district, delete_regional_district_list,
    import_regional_district_from_excel, export_regional_district_to_excel, log_to_db, get_total_regional_district_records
)
from app.extensions import db
from app.logs.models.logs_models import Log
from app.logs.services.logging_service import log_to_db
from collections import Counter

@reference_bp.route("/regional_district", methods=["GET", "POST"])
def regional_district_list():
    """Маршрут для отображения списка субъектов РФ."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница субъектов РФ")
    
    form = RegionalDistrictFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter = request.args.get("federal_district_filter")
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        regional_district_filter = request.form.get("regional_district_filter", "").strip()
        federal_district_filter = request.form.get("federal_district_filter")

        # Получение данных из формы
        regional_district_ids = request.form.getlist("regional_district_ids[]")
        regional_district_names = request.form.getlist("regional_district_names[]")
        regional_district_full_names = request.form.getlist("regional_district_full_names[]")
        federal_districts = request.form.getlist("federal_districts[]")
        regional_district_delete = request.form.getlist("regional_district_delete[]")

        # Удаление записей
        if regional_district_delete:
            try:
                delete_regional_district_list(regional_district_delete, user)
                flash("Записи субъектов РФ успешно удалены.", "success")
            except Exception as e:
                log_to_db(user, f"Ошибка удаления субъектов РФ: {e}")
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("reference_bp.regional_district_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    regional_district_filter=regional_district_filter,
                                    federal_district_filter=federal_district_filter,
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not (regional_district_ids and regional_district_names and regional_district_full_names and federal_districts):
                log_to_db(user, "Нет данных для обновления.")
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("reference_bp.regional_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        regional_district_filter=regional_district_filter,
                                        federal_district_filter=federal_district_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
            
            # Формирование данных для обновления
            regional_district_data = []
            for regional_district_id, regional_district_name, regional_district_full_name, id_federal_district in zip(
                regional_district_ids, regional_district_names, regional_district_full_names, federal_districts
            ):
                try:
                    regional_district_data.append({
                        "id": int(regional_district_id) if regional_district_id else None,
                        "name": regional_district_name.strip(),
                        "name_full": regional_district_full_name.strip(),
                        "id_federal_district": int(id_federal_district) if id_federal_district else None
                    })
                except ValueError as e:
                    raise ValueError(f"Ошибка обработки данных: id={regional_district_id}, name={regional_district_name}, name_full={regional_district_full_name}, id_federal_district={id_federal_district}. Ошибка: {str(e)}")
            
            # Проверка на дублирующиеся IDs
            ids = [record["id"] for record in regional_district_data if record["id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            # Обновление данных в базе
            update_regional_district(regional_district_data, user)

            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("reference_bp.regional_district_list", 
                                page=page, 
                                per_page=per_page, 
                                regional_district_filter=regional_district_filter,
                                federal_district_filter=federal_district_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_regional_district_list(page, 
                              per_page, 
                              regional_district_filter,
                              federal_district_filter,
                              sort_by, 
                              sort_dir)

    # Подготовка данных для формы
    federal_districts = get_federal_district_list()
    form.federal_district.choices = [(t.id, t.name) for t in federal_districts]

    return render_template(
        "references/regional_district/regional_district.html",
        form=form,
        regional_districts_list=pagination.items,
        pagination=pagination,
        federal_districts_list=form.federal_district.choices,
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@reference_bp.route("/add_regional_district", methods=["GET", "POST"])
def add_regional_district_routes():
    """
    Маршрут для добавления нового субъекта РФ.
    """
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления субъекта РФ")

    # Создание формы
    form = AddRegionalDistrictForm()

    # Получение списка федеральных округов
    try:
        federal_districts = get_federal_district_list()
        if not federal_districts:
            flash("Ошибка: отсутствует список ФО. Добавьте ФО перед созданием записи.", "danger")
            log_to_db(user, "Ошибка добавления субъекта РФ", "Отсутствуют федеральные округа.")
            return redirect(url_for("reference_bp.regional_district_list"))

        form.federal_district.choices = [(t.id, t.name) for t in federal_districts]
    except Exception as e:
        current_app.logger.error(f"Ошибка получения списка ФО: {e}")
        flash("Ошибка при загрузке списка федеральных округов.", "danger")
        return redirect(url_for("reference_bp.regional_district_list"))

    # Сохранение текущих фильтров и параметров отображения
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter = request.args.get("federal_district_filter")
    per_page = int(request.args.get("per_page", 10))
    page = int(request.args.get("page", 1))

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            # Добавление новой записи через сервис
            new_regional_district_id = add_regional_district([{
                "name": form.name.data.strip(),
                "name_full": form.name_full.data.strip(),
                "id_federal_district": form.federal_district.data
            }], user)
            flash("Новая запись успешно добавлена.", "success")
            log_to_db(user, "Добавление нового субъекта РФ", 
                      f"Имя: {form.name.data}, Полное имя: {form.name_full.data}, ФО: {form.federal_district.data}")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = get_total_regional_district_records(regional_district_filter, federal_district_filter)  # Общий подсчет записей
            last_page = (total_records + per_page - 1) // per_page  # Вычисление последней страницы

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "reference_bp.regional_district_list",
                sort_by=sort_by,
                sort_dir=sort_dir,
                regional_district_filter=regional_district_filter,
                federal_district_filter=federal_district_filter,
                per_page=per_page,
                page=last_page,
                highlight_id=new_regional_district_id
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
            log_to_db(user, "Ошибка добавления нового субъекта РФ", str(e))
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления субъекта РФ", str(e))

    # Рендеринг формы
    return render_template(
        "references/regional_district/regional_district_add.html", 
        form=form, 
        federal_district=form.federal_district.choices, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        per_page=per_page, 
        page=page
    )


@reference_bp.route("/import_regional_district_to_sql", methods=["POST"])
def import_regional_district_to_sql_routes():
    """Маршрут для импорта данных из Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт списка субъектов РФ из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("reference_bp.regional_district_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")


    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("reference_bp.regional_district_list"))

    try:
        imported_count = import_regional_district_from_excel(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("reference_bp.regional_district_list"))


from datetime import datetime

@reference_bp.route("/export_regional_district_to_excel", methods=["GET"])
def export_regional_district_to_excel_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    regional_district_filter = request.args.get("regional_district_filter", "").strip()
    federal_district_filter = request.args.get("federal_district_filter")
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    try:
        excel_data = export_regional_district_to_excel(user, regional_district_filter, federal_district_filter, sort_by, sort_dir)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {regional_district_filter, federal_district_filter}, Сортировка: {sort_by}, Направление: {sort_dir}")

        filename = f"regional_district_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return Response(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных.", "danger")
        return redirect(url_for("reference_bp.regional_district_list"))
