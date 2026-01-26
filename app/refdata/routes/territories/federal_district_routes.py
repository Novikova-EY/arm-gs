"""Маршруты справочника «Федеральные округа»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.territories.federal_district_forms import (
    FederalDistrictFilterForm, 
    AddFederalDistrictForm,
)

# Сервисы
from app.refdata.services.territories.federal_district_services import (
    federal_district_query,
    get_federal_district_list, 
    update_federal_district_service, 
    add_federal_district_service, 
    delete_federal_district_service,
    import_federal_district_service, 
    export_federal_district_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/federal_district", methods=["GET", "POST"])
@login_required
def federal_district_list():
    """Маршрут для отображения списка федеральных округов."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница федеральных округов", entity_type="federal_district")
    
    # Создание формы
    form = FederalDistrictFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    federal_district_filter = request.args.get("federal_district_filter", "").strip()
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 25, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")
        federal_district_filter = request.form.get("federal_district_filter", "").strip()

        # Получение данных из формы
        federal_district_ids = request.form.getlist("federal_district_ids[]")
        display_orders = request.form.getlist("display_orders[]")
        federal_district_names = request.form.getlist("federal_district_names[]")
        federal_district_full_names = request.form.getlist("federal_district_full_names[]")
        federal_district_abr_names = request.form.getlist("federal_district_abr_names[]")
        federal_district_delete = request.form.getlist("federal_district_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if federal_district_delete:
            try:
                delete_federal_district_service(federal_district_delete, user)
                deleted_ids = {int(item) for item in federal_district_delete if item}
                flash("Записи успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
           
        # Обновление данных в базе
        try:
            if not (federal_district_ids and display_orders and federal_district_names and federal_district_full_names and federal_district_abr_names):
                if not deleted_ids:
                    log_to_db(user, "Нет данных для обновления.", entity_type="federal_district")
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.federal_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        federal_district_filter=federal_district_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            federal_district_data = []
            for federal_district_id, display_order, federal_district_name, federal_district_full_name, federal_district_abr_name in zip(
                federal_district_ids, display_orders, federal_district_names, federal_district_full_names, federal_district_abr_names
            ):
                if federal_district_id and int(federal_district_id) in deleted_ids:
                    continue
                try:
                    if not federal_district_name.strip():
                        log_to_db(user, f"Пустое имя обнаружено: ID={federal_district_id}", entity_type="federal_district")
                        raise ValueError(f"Пустое имя для ID: {federal_district_id}")

                    federal_district_data.append({
                        "federal_district_id": int(federal_district_id) if federal_district_id else None,
                        "display_order": int(display_order) if display_order and str(display_order).strip() else None,
                        "name": federal_district_name.strip(),
                        "name_full": federal_district_full_name.strip(),
                        "name_abr": federal_district_abr_name.strip(),
                    })
                except ValueError as e:
                    raise ValueError(
                        f"Ошибка обработки данных: "
                        f"federal_district_id={federal_district_id}, "
                        f"display_order={display_order}, "
                        f"name={federal_district_name}, "
                        f"name_full={federal_district_full_name}, "
                        f"name_abr={federal_district_abr_name}. "
                        f"Ошибка: {e}"
                    )
            
            if not federal_district_data:
                return redirect(url_for("refdata_bp.federal_district_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        federal_district_filter=federal_district_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["federal_district_id"] for record in federal_district_data if record["federal_district_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
           
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID федерального округа: {duplicates}")

            # Обновление данных в базе
            update_federal_district_service(federal_district_data, user)
            flash("Изменения успешно сохранены.", "success")
            
        except ValueError as e:
            msg = str(e)
            if 'уже существует' in msg:
                flash(msg, 'warning')
            else:
                flash(msg, 'danger')
        except Exception as e:
            log_to_db(user, f"Ошибка сохранения данных федерального округа: {e}", entity_type="federal_district")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.federal_district_list", 
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
        "refdata/territories/federal_district/federal_district.html",
        form=form,
        federal_district_list=pagination.items,
        pagination=pagination,
        federal_district_filter=federal_district_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_federal_district", methods=["GET", "POST"])
@login_required
def add_federal_district():
    """ Маршрут для добавления нового федерального округа. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления федерального округа", entity_type="federal_district")

    # Создание формы
    form = AddFederalDistrictForm()

    # Сохранение текущих фильтров и параметров отображения
    page                        = request.args.get("page", 1, type=int)
    per_page                    = request.args.get("per_page", 25, type=int)
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    federal_district_filter     = request.args.get("federal_district_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/territories/federal_district/federal_district_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": form.name.data,
                "name_full": form.name_full.data,
                "name_abr": form.name_abr.data,
            }]
        
            # Добавление новой записи через сервис
            add_federal_district_service(payload, user)            
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = federal_district_query(
                                federal_district_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.federal_district_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                federal_district_filter=federal_district_filter,
            ))
        except ValueError as e:
            # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")
            log_to_db(user, "Неизвестная ошибка добавления нового федерального округа", str(e), entity_type="federal_district")

    # Рендеринг формы
    return render_template(
        "refdata/territories/federal_district/federal_district_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form,
        federal_district_filter=federal_district_filter, 
    )


@refdata_bp.route("/import_federal_district", methods=["POST"])
@login_required
def import_federal_district():
    """Маршрут для импорта данных из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт федеральных округов из Excel", entity_type="federal_district")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.federal_district_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.federal_district_list"))

    try:
        imported_count = import_federal_district_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.federal_district_list"))


@refdata_bp.route("/export_federal_district", methods=["GET"])
def export_federal_district():
    """ Маршрут для экспорта федеральных округов в Excel. """

    user = session.get('username', 'Неизвестный пользователь')
    
    sort_by                     = request.args.get("sort_by", "id")
    sort_dir                    = request.args.get("sort_dir", "asc")
    federal_district_filter     = request.args.get("federal_district_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_federal_district_service(
                user=user, 
                sort_by=sort_by, 
                sort_dir=sort_dir,
                federal_district_filter=federal_district_filter, 
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.federal_district_list"))
        
        # Формирование имени файла
        filename = f"federal_district_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)

        # Возврат файла через send_file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.federal_district_list"))