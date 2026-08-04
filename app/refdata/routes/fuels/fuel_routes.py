"""Маршруты справочника «Типы топлива»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app, jsonify
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

# Блюпринт
from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin
from app.auth.routes.decorators import roles_required

# Формы
from app.refdata.forms.fuels.fuel_forms import (
    FuelFilterForm, 
    AddFuelForm,
)

from app.common.services.choices_cache_service import choices_cache
from app.refdata.services.fuels.fuel_services import (
    fuel_query,
    get_fuel_list,
    get_fuel_hierarchy_tree,
    update_fuel_service, 
    update_fuel_all_versions_service, 
    add_fuel_service, 
    add_fuel_all_versions_service, 
    delete_fuel_service,
    import_fuel_service,
    build_fuel_import_payload,
    export_fuel_service, 
)

# Модели
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.fuels.fuel_model import Fuel

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/fuel/hierarchy", methods=["GET"])
@login_required
def fuel_hierarchy():
    """JSON-дерево иерархии видов топлива текущей версии БД."""
    user = session.get("username", "Неизвестный пользователь")
    try:
        tree = get_fuel_hierarchy_tree()
        log_to_db(
            user,
            "Открыта визуализация иерархии видов топлива",
            f"Узлов: {tree.get('total', 0)}; корней: {tree.get('roots_count', 0)}",
            entity_type="fuel",
        )
        return jsonify(ok=True, **tree)
    except Exception as e:
        current_app.logger.exception("Ошибка построения иерархии топлива")
        return jsonify(ok=False, error=str(e) or "Ошибка построения иерархии."), 500


@refdata_bp.route("/fuel", methods=["GET", "POST"])
@login_required
def fuel_list():
    """Маршрут для отображения списка типов топлива."""

    def _normalize_filter(value):
        if value in (None, "", "None"):
            return None
        return value

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница типов топлива", entity_type="fuel")
    
    # Создание формы
    form = FuelFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_filter         = _normalize_filter(request.args.get("fuel_filter"))
    if fuel_filter is not None:
        fuel_filter = fuel_filter.strip()
    fuel_type_filter    = _normalize_filter(request.args.get("fuel_type_filter"))
    parent_filter  = _normalize_filter(request.args.get("parent_filter"))
    nazvl_filter   = _normalize_filter(request.args.get("nazvl_filter"))
    kmbur_filter   = _normalize_filter(request.args.get("kmbur_filter"))

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 25, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        fuel_filter         = _normalize_filter(request.form.get("fuel_filter"))
        if fuel_filter is not None:
            fuel_filter = fuel_filter.strip()
        fuel_type_filter    = _normalize_filter(request.form.get("fuel_type_filter"))
        parent_filter  = _normalize_filter(request.form.get("parent_filter"))
        nazvl_filter   = _normalize_filter(request.form.get("nazvl_filter"))
        kmbur_filter   = _normalize_filter(request.form.get("kmbur_filter"))

        # Получение данных из формы
        fuel_ids = request.form.getlist("fuel_ids[]")
        fuel_names = request.form.getlist("fuel_names[]")
        fuel_kods = request.form.getlist("fuel_kods[]")
        fuel_types = request.form.getlist("fuel_types[]")
        fuel_parents = request.form.getlist("fuel_parents[]")
        fuel_nazvl = request.form.getlist("fuel_nazvl[]")
        fuel_kmbur = request.form.getlist("fuel_kmbur[]")
        fuel_delete = request.form.getlist("fuel_delete[]")
  
        deleted_ids = set()
        # Удаление записей
        if fuel_delete:
            try:
                delete_fuel_service(fuel_delete, user)
                deleted_ids = {int(item) for item in fuel_delete if item}
                flash("Записи типов топлива успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
        # Обновление данных в базе
        try:
            if not fuel_ids or not fuel_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.fuel_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_filter=fuel_filter,
                                        fuel_type_filter=fuel_type_filter,
                                        parent_filter=parent_filter,
                                        nazvl_filter=nazvl_filter,
                                        kmbur_filter=kmbur_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            fuel_data = []
            for fuel_id, fuel_name, fuel_kod, fuel_type, fuel_parent, nazvl, kmbur in zip(
                fuel_ids,
                fuel_names,
                fuel_kods,
                fuel_types,
                fuel_parents,
                fuel_nazvl,
                fuel_kmbur,
            ):
                if fuel_id and int(fuel_id) in deleted_ids:
                    continue
                fuel_data.append({
                    "fuel_id": int(fuel_id) if fuel_id else None,
                    "name": fuel_name.strip(),
                    "kod": fuel_kod,
                    # Ключ должен соответствовать ожидаемому в update_fuel_service ("fuel_type_id")
                    "fuel_type_id": int(fuel_type) if fuel_type else None,
                    "parent_id": int(fuel_parent) if fuel_parent else None,
                    "nazvl": (nazvl or "").strip(),
                    "kmbur": (kmbur or "").strip(),
                })
            
            if not fuel_data:
                return redirect(url_for("refdata_bp.fuel_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        fuel_filter=fuel_filter,
                                        fuel_type_filter=fuel_type_filter,
                                        parent_filter=parent_filter,
                                        nazvl_filter=nazvl_filter,
                                        kmbur_filter=kmbur_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

            # Проверка на дублирующиеся IDs
            ids = [record["fuel_id"] for record in fuel_data if record["fuel_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID типов топлива: {duplicates}")

            # Обновление данных в базе
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.fuel_list",
                            page=page,
                            per_page=per_page,
                            fuel_filter=fuel_filter,
                            fuel_type_filter=fuel_type_filter,
                            parent_filter=parent_filter,
                            nazvl_filter=nazvl_filter,
                            kmbur_filter=kmbur_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                update_fuel_all_versions_service(fuel_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_fuel_service(fuel_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.fuel_list", 
                                page=page, 
                                per_page=per_page, 
                                fuel_filter=fuel_filter,
                                fuel_type_filter=fuel_type_filter,
                                parent_filter=parent_filter,
                                nazvl_filter=nazvl_filter,
                                kmbur_filter=kmbur_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_fuel_list(
        page,
        per_page,
        fuel_filter,
        fuel_type_filter,
        nazvl_filter,
        kmbur_filter,
        sort_by,
        sort_dir,
        parent_filter=parent_filter,
    )

    nazvl_values = [
        row[0] for row in (
            fuel_query(
                fuel_filter=fuel_filter,
                fuel_type_filter=fuel_type_filter,
                parent_filter=parent_filter,
            )
            .with_entities(Fuel.nazvl)
            .order_by(None)
            .distinct()
            .order_by(Fuel.nazvl.asc())
            .all()
        )
        if row[0]
    ]
    kmbur_values = [
        row[0] for row in (
            fuel_query(
                fuel_filter=fuel_filter,
                fuel_type_filter=fuel_type_filter,
                parent_filter=parent_filter,
            )
            .with_entities(Fuel.kmbur)
            .order_by(None)
            .distinct()
            .order_by(Fuel.kmbur.asc())
            .all()
        )
        if row[0]
    ]

    # Подготовка данных для формы
    # Заполняем список типов топлива с фильтрацией по версии БД
    form.fuel_type.choices = choices_cache.get_choices(FuelType, FuelType.id)
    form.parent.choices = choices_cache.get_choices_with_default(
        Fuel, Fuel.id, default_text="— (корень)"
    )

    return render_template(
        "refdata/fuels/fuel/fuel.html",
        form=form,
        fuel_list=pagination.items,
        pagination=pagination,
        fuel_types=form.fuel_type.choices,
        fuel_parents=form.parent.choices,
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        parent_filter=parent_filter,
        nazvl_filter=nazvl_filter,
        kmbur_filter=kmbur_filter,
        nazvl_values=nazvl_values,
        kmbur_values=kmbur_values,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@refdata_bp.route("/add_fuel", methods=["GET", "POST"])
@login_required
def add_fuel():
    """ Маршрут для добавления нового топлива. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления типов топлива", 
        entity_type="fuel")

    # Создание формы
    form = AddFuelForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 25, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_filter         = request.args.get("fuel_filter", "").strip()
    fuel_type_filter    = request.args.get("fuel_type_filter", "").strip()
    nazvl_filter   = request.args.get("nazvl_filter", "").strip()
    kmbur_filter   = request.args.get("kmbur_filter", "").strip()

    # Подготовка данных для формы с фильтрацией по версии БД
    form.fuel_type.choices = choices_cache.get_choices(FuelType, FuelType.id)
    form.parent.choices = choices_cache.get_choices_with_default(
        Fuel, Fuel.id, default_text="— (корень)"
    )

    # Обработка формы
    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "kod": form.kod.data,
                "fuel_type_id": form.fuel_type.data,
                "parent_id": form.parent.data,
            }]

            # Добавление новой записи через сервис
            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for("refdata_bp.fuel_list",
                            page=page,
                            per_page=per_page,
                            fuel_filter=fuel_filter,
                            fuel_type_filter=fuel_type_filter,
                            nazvl_filter=nazvl_filter,
                            kmbur_filter=kmbur_filter,
                            sort_by=sort_by,
                            sort_dir=sort_dir,
                    ))
                add_fuel_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_fuel_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = fuel_query(
                                fuel_filter, 
                                fuel_type_filter,
                                nazvl_filter,
                                kmbur_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.fuel_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                fuel_filter=fuel_filter,
                fuel_type_filter=fuel_type_filter,
                nazvl_filter=nazvl_filter,
                kmbur_filter=kmbur_filter,
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
        "refdata/fuels/fuel/fuel_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        fuel_types=form.fuel_type.choices,
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        nazvl_filter=nazvl_filter,
        kmbur_filter=kmbur_filter,
    )


def _wants_json_response() -> bool:
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and (
        request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]
    )


@refdata_bp.route("/import_fuel", methods=["POST"])
@login_required
@roles_required(["admin"])
def import_fuel():
    """Импорт состава видов топлива из Excel во все версии БД (только роль admin)."""

    user = session.get('username', 'Неизвестный пользователь')
    wants_json = _wants_json_response()

    def _error(message: str, status: int = 400):
        if wants_json:
            return jsonify(ok=False, error=message), status
        flash(message, "danger")
        return redirect(url_for("refdata_bp.fuel_list"))

    if 'file' not in request.files:
        return _error("Файл не найден.")

    file = request.files['file']
    if not file or not file.filename:
        return _error("Файл не выбран.")

    allowed_mimes = {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    }
    if file.mimetype and file.mimetype not in allowed_mimes:
        return _error("Неверный формат файла.")

    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return _error("Неверный формат файла.")

    try:
        result = import_fuel_service(file, user)
        payload = build_fuel_import_payload(result)
        if wants_json:
            return jsonify(payload)
        flash(payload["message"], "success")
        if payload.get("hints"):
            flash(payload["hints"][0], "warning")
    except ValueError as e:
        return _error(str(e))
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        return _error("Ошибка импорта данных.", status=500)

    return redirect(url_for("refdata_bp.fuel_list"))


@refdata_bp.route("/export_fuel", methods=["GET"])
@login_required
def export_fuel():
    """Маршрут для экспорта типов топлива в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    fuel_filter         = request.args.get("fuel_filter", "").strip()
    fuel_type_filter    = request.args.get("fuel_type_filter", "").strip()
    nazvl_filter   = request.args.get("nazvl_filter", "").strip()
    kmbur_filter   = request.args.get("kmbur_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_fuel_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        fuel_filter=fuel_filter,
                        fuel_type_filter=fuel_type_filter,
                        nazvl_filter=nazvl_filter,
                        kmbur_filter=kmbur_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.fuel_list"))
        
        # Формирование имени файла
        filename = f"fuel_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        current_app.logger.exception("Ошибка экспорта топлива")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("refdata_bp.fuel_list"))