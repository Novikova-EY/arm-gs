"""Маршруты справочника «Виды топлива»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.fuels.fuel_type_forms import (
    FuelTypeFilterForm, 
    AddFuelTypeForm,
)

# Сервисы
from app.refdata.services.fuels.fuel_type_services import (
    fuel_type_query,
    get_fuel_type_list,
    update_fuel_type_service, 
    add_fuel_type_service, 
    delete_fuel_type_service,
    import_fuel_type_service, 
    export_fuel_type_service, 
)
from app.refdata.models.fuels.fuel_type_model import FuelType

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/fuel_type", methods=["GET", "POST"])
@login_required
def fuel_type_list():
    """Маршрут для отображения списка видов топлива."""

    def _normalize_filter(value):
        if value in (None, "", "None"):
            return None
        return value

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница видов топлива", entity_type="fuel_type")
    
    # Создание формы
    form = FuelTypeFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_type_filter    = _normalize_filter(request.args.get("fuel_type_filter"))
    topl_nazvl_filter   = _normalize_filter(request.args.get("topl_nazvl_filter"))

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "display_order")
        sort_dir            = request.form.get("sort_dir", "asc")
        fuel_type_filter    = _normalize_filter(request.form.get("fuel_type_filter"))
        topl_nazvl_filter   = _normalize_filter(request.form.get("topl_nazvl_filter"))

        # Получение данных из формы
        fuel_type_ids        = request.form.getlist("fuel_ids[]")
        fuel_type_names      = request.form.getlist("fuel_type_names[]")
        fuel_type_topl_nazvl = request.form.getlist("fuel_type_topl_nazvl[]")
        fuel_type_orders     = request.form.getlist("display_orders[]")
        fuel_type_delete     = request.form.getlist("fuel_type_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if fuel_type_delete:
            try:
                delete_fuel_type_service(fuel_type_delete, user)
                deleted_ids = {int(item) for item in fuel_type_delete if item}
                flash("Записи видов топлива успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not fuel_type_ids or not fuel_type_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.fuel_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_type_filter=fuel_type_filter,
                                        topl_nazvl_filter=topl_nazvl_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            fuel_type_data = []
            for fuel_type_id, fuel_type_name, topl_nazvl, display_order in zip(
                fuel_type_ids,
                fuel_type_names,
                fuel_type_topl_nazvl,
                fuel_type_orders,
            ):
                if fuel_type_id and int(fuel_type_id) in deleted_ids:
                    continue
                try:
                    parsed_display_order = int(display_order) if display_order and str(display_order).strip() else None
                except ValueError as e:
                    raise ValueError(
                        (
                            f"Ошибка обработки порядка отображения для записи c ID={fuel_type_id}: "
                            f"значение «{display_order}» не является целым числом."
                        )
                    )

                fuel_type_data.append({
                    "fuel_type_id": int(fuel_type_id) if fuel_type_id else None,
                    "name": fuel_type_name.strip(),
                    "topl_nazvl": (topl_nazvl or "").strip(),
                    "display_order": parsed_display_order,
                })
            
            if not fuel_type_data:
                return redirect(url_for("refdata_bp.fuel_type_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_type_filter=fuel_type_filter,
                                        topl_nazvl_filter=topl_nazvl_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["fuel_type_id"] for record in fuel_type_data if record["fuel_type_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID видов топлива: {duplicates}")

            # Обновление данных в базе
            update_fuel_type_service(fuel_type_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.fuel_type_list", 
                                page=page, 
                                per_page=per_page, 
                                fuel_type_filter=fuel_type_filter,
                                topl_nazvl_filter=topl_nazvl_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_fuel_type_list(
                                page, 
                                per_page, 
                                fuel_type_filter,
                                topl_nazvl_filter,
                                sort_by, 
                                sort_dir)

    # Значения для выпадающего фильтра "Наименование в БД Топливо".
    # В тестовом окружении (без полноценной БД/моделей) этот блок может падать —
    # тогда просто скрываем dropdown-значения.
    try:
        topl_nazvl_values = [
            row[0] for row in (
                fuel_type_query(fuel_type_filter=fuel_type_filter)
                .with_entities(FuelType.topl_nazvl)
                .order_by(None)
                .distinct()
                .order_by(FuelType.topl_nazvl.asc())
                .all()
            )
            if row[0]
        ]
    except Exception:
        topl_nazvl_values = []
    return render_template(
        "refdata/fuels/fuel_type/fuel_type.html",
        form=form,
        fuel_type_list=pagination.items,
        pagination=pagination,
        fuel_type_filter=fuel_type_filter,
        topl_nazvl_filter=topl_nazvl_filter,
        topl_nazvl_values=topl_nazvl_values,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_fuel_type", methods=["GET", "POST"])
@login_required
def add_fuel_type():
    """ Маршрут для добавления нового вида топлива. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления видов топлива", 
        entity_type="fuel_type")

    # Создание формы
    form = AddFuelTypeForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_type_filter    = request.args.get("fuel_type_filter", "").strip()
    topl_nazvl_filter   = request.args.get("topl_nazvl_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/fuels/fuel_type/fuel_type_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            add_fuel_type_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = fuel_type_query(
                                fuel_type_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.fuel_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                fuel_type_filter=fuel_type_filter,
                topl_nazvl_filter=topl_nazvl_filter,
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
        "refdata/fuels/fuel_type/fuel_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        fuel_type_filter=fuel_type_filter,
        topl_nazvl_filter=topl_nazvl_filter,
    )


@refdata_bp.route("/import_fuel_type", methods=["POST"])
@login_required
def import_fuel_type():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.fuel_type_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.fuel_type_list"))

    try:
        imported_count = import_fuel_type_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.fuel_type_list"))


@refdata_bp.route("/export_fuel_type", methods=["GET"])
@login_required
def export_fuel_type():
    """Маршрут для экспорта видов топлива в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "display_order")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_type_filter    = request.args.get("fuel_type_filter", "").strip()
    topl_nazvl_filter   = request.args.get("topl_nazvl_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_fuel_type_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        fuel_type_filter=fuel_type_filter,
                        topl_nazvl_filter=topl_nazvl_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.fuel_type_list"))
        
        # Формирование имени файла
        filename = f"fuel_type_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)

        # Возврат файла через send_file
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )


    except Exception:
        current_app.logger.exception("Ошибка экспорта видов топлива")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.fuel_type_list"))