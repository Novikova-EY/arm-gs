"""Маршруты справочника «Типы электростанций»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

# Блюпринт
from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

# Формы
from app.refdata.forms.refdata_for_stations.stations.station_type_forms import (
    StationTypeFilterForm, 
    AddStationTypeForm,
)

# Сервисы
from app.refdata.services.refdata_for_stations.stations.station_type_services import (
    station_type_query,
    get_station_type_list,
    update_station_type_service, 
    update_station_type_all_versions_service, 
    add_station_type_service, 
    add_station_type_all_versions_service, 
    delete_station_type_service,
    export_station_type_service, 
)

# Логирование
from app.logs.services.logging_service import log_to_db


def _normalize_filter(value):
    """Нормализует строку фильтра: пустые/None/'None' -> None."""
    if value in (None, "", "None"):
        return None
    return value


@refdata_bp.route("/station_type", methods=["GET", "POST"])
@login_required
def station_type_list():
    """Маршрут для отображения списка типов электростанций."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница типов электростанций", 
        entity_type="station_type")
    
    # Создание формы
    form = StationTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    station_type_filter    = _normalize_filter(request.args.get("station_type_filter"))

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "display_order")
        sort_dir            = request.form.get("sort_dir", "asc")
        station_type_filter    = _normalize_filter(request.form.get("station_type_filter"))

        # Получение данных из формы
        station_type_ids       = request.form.getlist("station_ids[]")
        station_type_names     = request.form.getlist("station_type_names[]")
        station_type_orders    = request.form.getlist("display_orders[]")
        station_type_delete    = request.form.getlist("station_type_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if station_type_delete:
            try:
                delete_station_type_service(station_type_delete, user)
                deleted_ids = {int(item) for item in station_type_delete if item}
                flash("Записи типов электростанций успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not station_type_ids or not station_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.station_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        station_type_filter=station_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            station_type_data = []
            for station_type_id, station_type_name, display_order in zip(
                station_type_ids, station_type_names, station_type_orders
            ):
                if station_type_id and int(station_type_id) in deleted_ids:
                    continue
                try:
                    parsed_display_order = int(display_order) if display_order and str(display_order).strip() else None
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки порядка отображения для записи c ID={station_type_id}: "
                            f"значение «{display_order}» не является целым числом."
                        )
                    )

                station_type_data.append({
                    "station_type_id": int(station_type_id) if station_type_id else None,
                    "name": station_type_name.strip(),
                    "display_order": parsed_display_order,
                })
            
            if not station_type_data:
                return redirect(url_for("refdata_bp.station_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        station_type_filter=station_type_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["station_type_id"] for record in station_type_data if record["station_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов электростанций: {duplicates}")

            # Обновление данных в базе
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.station_type_list",
                            page=page,
                            per_page=per_page,
                            station_type_filter=station_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                update_station_type_all_versions_service(station_type_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_station_type_service(station_type_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.station_type_list", 
                                page=page, 
                                per_page=per_page, 
                                station_type_filter=station_type_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_station_type_list(
                                page, 
                                per_page, 
                                station_type_filter,
                                sort_by, 
                                sort_dir)

    return render_template(
        "refdata/refdata_for_stations/stations/station_type/station_type.html",
        form=form,
        station_type_list=pagination.items,
        pagination=pagination,
        station_type_filter=station_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_station_type", methods=["GET", "POST"])
@login_required
def add_station_type():
    """ Маршрут для добавления нового типа  электростанции. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типов электростанций", 
        entity_type="station_type")

    # Создание формы
    form = AddStationTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    station_type_filter    = request.args.get("station_type_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/stations/station_type/station_type_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.station_type_list",
                            page=page,
                            per_page=per_page,
                            station_type_filter=station_type_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                add_station_type_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_station_type_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = station_type_query(
                                station_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.station_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                station_type_filter=station_type_filter,
            ))

        except ValueError as e:
             # Логирование и отображение ошибок валидации
            flash(str(e), "danger")
        except Exception as e:
            # Логирование и отображение других ошибок
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")

    # Рендеринг формы
    return render_template(
        "refdata/refdata_for_stations/stations/station_type/station_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        station_type_filter=station_type_filter,
    )


@refdata_bp.route("/export_station_type", methods=["GET"])
@login_required
def export_station_type():
    """Маршрут для экспорта типов электростанций в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    station_type_filter    = request.args.get("station_type_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_station_type_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        station_type_filter=station_type_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.station_type_list"))
        
        # Формирование имени файла
        filename = f"station_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.station_type_list"))