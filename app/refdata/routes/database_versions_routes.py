# -*- coding: utf-8 -*-
"""Маршруты управления версиями базы данных."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app, jsonify
from collections import Counter
from datetime import datetime
import os

from flask_login import login_required

# Блюпринт
from app.generation.routes.stations import station_bp

# Формы
from app.generation.forms.database_version_forms import (
    DatabaseVersionFilterForm, 
    AddDatabaseVersionForm,
)

# Сервисы
from app.common.services.database_version_services import (
    version_query,
    get_version_list,
    update_version_service, 
    add_version_service, 
    delete_version_service,
    export_version_service,
    set_active_version,
    save_version_snapshot,
    load_version_snapshot,
)
from app.common.services.version_comparison_service import (
    compare_versions,
    export_comparison_to_excel,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.models.log_model import Log

# Модели и расширения
from app.common.models.database_version_model import DatabaseVersion
from app.common.middleware.database_version_middleware import set_session_version
from app.extensions import db


@station_bp.route("/database_versions", methods=["GET", "POST"], endpoint="database_versions_v2")
@login_required
def database_versions():
    """Маршрут для отображения списка версий базы данных."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница управления версиями БД", entity_type="database_version")
    
    # Создание формы
    form = DatabaseVersionFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter")
    
    # Нормализация значения фильтра
    if version_filter in (None, "", "None", "none"):
        version_filter = None

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 20, type=int)
        sort_by             = request.form.get("sort_by", "version_number")
        sort_dir            = request.form.get("sort_dir", "desc")
        version_filter      = request.form.get("version_filter")
        if version_filter in (None, "", "None", "none"):
            version_filter = None

        # Получение данных из формы
        version_ids         = request.form.getlist("version_ids[]")
        version_numbers     = request.form.getlist("version_numbers[]")
        version_names       = request.form.getlist("version_names[]")
        version_descriptions= request.form.getlist("version_descriptions[]")
        version_delete      = request.form.getlist("version_delete[]")
  
        # Удаление записей
        if version_delete:
            try:
                result = delete_version_service(version_delete, user)
                
                # Формируем подробное сообщение об удалении
                message_parts = [f"Удалено версий: {result['deleted']}"]
                if result.get('deleted_names'):
                    message_parts.append(f"Названия: {', '.join(result['deleted_names'])}")
                if result.get('total_data_deleted', 0) > 0:
                    message_parts.append(f"Удалено записей данных: {result['total_data_deleted']}")
                if result.get('not_found'):
                    message_parts.append(f"Не найдены ID: {result['not_found']}")
                if result.get('invalid'):
                    message_parts.append(f"Некорректные ID: {result['invalid']}")
                
                flash("; ".join(message_parts), "success")
            except ValueError as e:
                flash(str(e), "danger")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("station_bp.database_versions", 
                                    page=page, 
                                    per_page=per_page, 
                                    version_filter=version_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
        
        # Обновление данных в базе
        try:
            if not version_ids or not version_names or not version_numbers:
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("station_bp.database_versions", 
                                        page=page, 
                                        per_page=per_page, 
                                        version_filter=version_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            version_data = []
            for vid, vnum, vname, vdesc in zip(version_ids, version_numbers, version_names, version_descriptions):
                version_data.append({
                    "version_id": int(vid) if vid else None,
                    "version_number": int(vnum) if vnum else None,
                    "name": vname.strip(),
                    "description": vdesc.strip() if vdesc else "",
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["version_id"] for record in version_data if record["version_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID версий: {duplicates}")

            # Обновление данных в базе
            update_version_service(version_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("station_bp.database_versions", 
                                page=page, 
                                per_page=per_page, 
                                version_filter=version_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_version_list(
                                page, 
                                per_page, 
                                version_filter,
                                sort_by, 
                                sort_dir)
    
    # Определяем создателя версии по логам (если поле не хранится в модели)
    creators_map = {}
    try:
        version_ids = [v.id for v in pagination.items]
        if version_ids:
            logs = (Log.query
                        .filter(
                            Log.entity_type == "database_version",
                            Log.entity_id.in_(version_ids),
                            Log.action.ilike("%Создана версия БД%")
                        )
                        .order_by(Log.timestamp.asc())
                        .all())
            # Берем первый лог создания на каждый id
            for lg in logs:
                if lg.entity_id not in creators_map:
                    creators_map[lg.entity_id] = lg.username
    except Exception:
        creators_map = {}

    return render_template(
        "generation/database_versions/database_versions.html",
        form=form,
        version_list=pagination.items,
        pagination=pagination,
        version_filter=version_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        creators_map=creators_map
    )


@station_bp.route("/add_database_version", methods=["GET", "POST"], endpoint="add_database_version_v2")
@login_required
def add_database_version():
    """ Маршрут для добавления новой версии БД. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления версии БД", 
        entity_type="database_version")

    # Создание формы
    form = AddDatabaseVersionForm()
    
    # Заполнение выбора базовой версии
    all_versions = DatabaseVersion.query.order_by(DatabaseVersion.version_number.desc()).all()
    base_parent_choices = [
        ('', 'Выберите вариант'),
        ('empty', 'Новая пустая версия')
    ]
    form.parent_version_id.choices = base_parent_choices + [
        (str(v.id), f"Версия {v.version_number}: {v.name}")
        for v in all_versions
    ]
    form.refdata_source_version_id.choices = [('', 'Выберите версию для копирования')] + [
        (str(v.id), f"Версия {v.version_number}: {v.name}")
        for v in all_versions
    ]

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "generation/database_versions/database_versions_add.html",
                form=form
            )
        
        try:
            raw_parent_value = (form.parent_version_id.data or '').strip()
            create_mode = 'default'  # default, empty, inherit

            if raw_parent_value.lower() in ('', 'none'):
                parent_id = None
            elif raw_parent_value == 'empty':
                parent_id = None
                create_mode = 'empty'
            else:
                try:
                    parent_id = int(raw_parent_value)
                    create_mode = 'inherit'
                except ValueError as exc:
                    raise ValueError("Некорректное значение поля «Создать на основе версии».") from exc

            refdata_source_id = form.refdata_source_version_id.data
            if refdata_source_id in (None, '', 'None', 'none'):
                refdata_source_id = None
            else:
                refdata_source_id = int(refdata_source_id)

            if create_mode != 'empty':
                refdata_source_id = None
            elif not refdata_source_id:
                flash("Для пустой версии необходимо выбрать источник справочников.", "danger")
                return render_template(
                    "generation/database_versions/database_versions_add.html",
                    form=form,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    version_filter=version_filter,
                )

            if parent_id and refdata_source_id:
                flash("Нельзя одновременно копировать полную версию и только справочники.", "danger")
                return render_template(
                    "generation/database_versions/database_versions_add.html",
                    form=form,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    version_filter=version_filter,
                )
            
            payload = [{
                "version_number": form.version_number.data,
                "name": (form.name.data or "").strip(),
                "description": (form.description.data or "").strip(),
                "parent_version_id": parent_id,
                "refdata_source_version_id": refdata_source_id,
            }]

            # Добавление новой записи через сервис
            new_version_id = add_version_service(payload, user)
            
            # Сообщение зависит от того, копировались ли данные
            if create_mode == 'inherit' and parent_id:
                parent = DatabaseVersion.query.get(parent_id)
                if parent:
                    flash(f"Новая версия успешно создана на основе версии {parent.version_number}: {parent.name}. Данные скопированы.", "success")
                else:
                    flash("Новая версия успешно добавлена.", "success")
            elif create_mode == 'empty' and refdata_source_id:
                ref_parent = DatabaseVersion.query.get(refdata_source_id)
                if ref_parent:
                    flash(f"Новая версия создана как пустая, но справочники скопированы из версии {ref_parent.version_number}: {ref_parent.name}.", "success")
                else:
                    flash("Новая версия успешно добавлена.", "success")
            elif create_mode == 'empty':
                flash("Новая пустая версия успешно создана.", "success")
            else:
                flash("Новая версия успешно создана.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = version_query(version_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "station_bp.database_versions",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                version_filter=version_filter,
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
        "generation/database_versions/database_versions_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        version_filter=version_filter,
    )


@station_bp.route("/export_database_versions", methods=["GET"], endpoint="export_database_versions_v2")
@login_required
def export_database_versions():
    """Маршрут для экспорта версий БД в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_version_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        version_filter=version_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.database_versions"))
        
        # Формирование имени файла
        filename = f"database_versions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/set_active_version/<int:version_id>", methods=["POST"], endpoint="set_active_version_route_v2")
@login_required
def set_active_version_route(version_id):
    """Маршрут для установки активной версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = set_active_version(version_id, user)
        flash(f"Версия '{version.name}' (v{version.version_number}) установлена как активная.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка установки активной версии: {e}")
        flash("Ошибка при установке активной версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/save_version_snapshot/<int:version_id>", methods=["POST"], endpoint="save_version_snapshot_route_v2")
@login_required
def save_version_snapshot_route(version_id):
    """Маршрут для сохранения снимка версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = save_version_snapshot(version_id, user)
        flash(f"Снимок версии '{version.name}' (v{version.version_number}) успешно сохранен.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка сохранения снимка: {e}")
        flash("Ошибка при сохранении снимка версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/load_version_snapshot/<int:version_id>", methods=["POST"], endpoint="load_version_snapshot_route_v2")
@login_required
def load_version_snapshot_route(version_id):
    """Маршрут для загрузки снимка версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = load_version_snapshot(version_id, user)
        flash(f"Снимок версии '{version.name}' (v{version.version_number}) успешно загружен.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка загрузки снимка: {e}")
        flash("Ошибка при загрузке снимка версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/compare_versions", methods=["GET", "POST"], endpoint="compare_versions_route_v2")
@login_required
def compare_versions_route():
    """Маршрут для сравнения двух версий БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    # Получаем список всех версий для выбора
    all_versions = DatabaseVersion.query.order_by(DatabaseVersion.version_number.desc()).all()
    
    if request.method == "POST":
        version_id_1 = request.form.get("version_id_1", type=int)
        version_id_2 = request.form.get("version_id_2", type=int)
        
        if not version_id_1 or not version_id_2:
            flash("Необходимо выбрать две версии для сравнения.", "warning")
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions
            )
        
        if version_id_1 == version_id_2:
            flash("Выберите разные версии для сравнения.", "warning")
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions
            )
        
        try:
            comparison = compare_versions(version_id_1, version_id_2)
            
            log_to_db(
                user,
                f"Выполнено сравнение версий БД",
                f"Версия {comparison['version1']['version_number']} vs Версия {comparison['version2']['version_number']}",
                entity_type="database_version"
            )
            
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions,
                comparison=comparison
            )
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка сравнения версий: {e}")
            flash("Ошибка при сравнении версий.", "danger")
    
    return render_template(
        "generation/database_versions/compare_versions.html",
        versions=all_versions
    )


@station_bp.route("/export_comparison/<int:version_id_1>/<int:version_id_2>", methods=["GET"], endpoint="export_comparison_route_v2")
@login_required
def export_comparison_route(version_id_1, version_id_2):
    """Маршрут для экспорта сравнения версий в Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        excel_data = export_comparison_to_excel(version_id_1, version_id_2)
        
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.compare_versions"))
        
        # Формирование имени файла
        filename = f"version_comparison_{version_id_1}_vs_{version_id_2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)
        
        log_to_db(
            user,
            f"Экспортировано сравнение версий БД",
            f"Версия {version_id_1} vs Версия {version_id_2}",
            entity_type="database_version"
        )
        
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта сравнения: {e}")
        flash("Ошибка экспорта данных сравнения.", "danger")
        return redirect(url_for("station_bp.compare_versions"))


@station_bp.route("/set_session_version/<int:version_id>", methods=["POST"], endpoint="set_session_version_route_v2")
@login_required
def set_session_version_route(version_id):
    """Маршрут для установки версии БД только для текущего пользователя (сессии)."""

    user = session.get('username', 'Неизвестный пользователь')

    try:
        version = DatabaseVersion.query.get(version_id)
        if not version:
            flash("Выбранная версия БД не найдена.", "danger")
        else:
            # Устанавливаем версию в сессии (перекрывает глобально активную)
            set_session_version(version_id)
            flash(
                f"Для пользователя {user} установлена версия БД "
                f"«{version.name}» (v{version.version_number}).",
                "success",
            )
    except Exception as e:
        current_app.logger.error(f"Ошибка установки версии для сессии: {e}")
        flash("Ошибка при выборе версии БД для текущего пользователя.", "danger")

    # Возвращаемся на предыдущую страницу или к списку версий
    referrer = request.referrer or url_for("station_bp.database_versions")
    return redirect(referrer)


# -*- coding: utf-8 -*-
"""Маршруты управления версиями базы данных."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app, jsonify
from collections import Counter
from datetime import datetime
import os

from flask_login import login_required

# Блюпринт
from app.generation.routes.stations import station_bp

# Формы
from app.generation.forms.database_version_forms import (
    DatabaseVersionFilterForm, 
    AddDatabaseVersionForm,
)

# Сервисы
from app.common.services.database_version_services import (
    version_query,
    get_version_list,
    update_version_service, 
    add_version_service, 
    delete_version_service,
    export_version_service,
    set_active_version,
    save_version_snapshot,
    load_version_snapshot,
)
from app.common.services.version_comparison_service import (
    compare_versions,
    export_comparison_to_excel,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.models.log_model import Log

# Модели и расширения
from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db


@station_bp.route("/database_versions", methods=["GET", "POST"])
@login_required
def database_versions():
    """Маршрут для отображения списка версий базы данных."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница управления версиями БД", entity_type="database_version")
    
    # Создание формы
    form = DatabaseVersionFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter")
    
    # Нормализация значения фильтра
    if version_filter in (None, "", "None", "none"):
        version_filter = None

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 20, type=int)
        sort_by             = request.form.get("sort_by", "version_number")
        sort_dir            = request.form.get("sort_dir", "desc")
        version_filter      = request.form.get("version_filter")
        if version_filter in (None, "", "None", "none"):
            version_filter = None

        # Получение данных из формы
        version_ids         = request.form.getlist("version_ids[]")
        version_numbers     = request.form.getlist("version_numbers[]")
        version_names       = request.form.getlist("version_names[]")
        version_descriptions= request.form.getlist("version_descriptions[]")
        version_delete      = request.form.getlist("version_delete[]")
  
        # Удаление записей
        if version_delete:
            try:
                result = delete_version_service(version_delete, user)
                
                # Формируем подробное сообщение об удалении
                message_parts = [f"Удалено версий: {result['deleted']}"]
                if result.get('deleted_names'):
                    message_parts.append(f"Названия: {', '.join(result['deleted_names'])}")
                if result.get('total_data_deleted', 0) > 0:
                    message_parts.append(f"Удалено записей данных: {result['total_data_deleted']}")
                if result.get('not_found'):
                    message_parts.append(f"Не найдены ID: {result['not_found']}")
                if result.get('invalid'):
                    message_parts.append(f"Некорректные ID: {result['invalid']}")
                
                flash("; ".join(message_parts), "success")
            except ValueError as e:
                flash(str(e), "danger")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("station_bp.database_versions", 
                                    page=page, 
                                    per_page=per_page, 
                                    version_filter=version_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
        
        # Обновление данных в базе
        try:
            if not version_ids or not version_names or not version_numbers:
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("station_bp.database_versions", 
                                        page=page, 
                                        per_page=per_page, 
                                        version_filter=version_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            version_data = []
            for vid, vnum, vname, vdesc in zip(version_ids, version_numbers, version_names, version_descriptions):
                version_data.append({
                    "version_id": int(vid) if vid else None,
                    "version_number": int(vnum) if vnum else None,
                    "name": vname.strip(),
                    "description": vdesc.strip() if vdesc else "",
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["version_id"] for record in version_data if record["version_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID версий: {duplicates}")

            # Обновление данных в базе
            update_version_service(version_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("station_bp.database_versions", 
                                page=page, 
                                per_page=per_page, 
                                version_filter=version_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_version_list(
                                page, 
                                per_page, 
                                version_filter,
                                sort_by, 
                                sort_dir)
    
    # Определяем создателя версии по логам (если поле не хранится в модели)
    creators_map = {}
    try:
        version_ids = [v.id for v in pagination.items]
        if version_ids:
            logs = (Log.query
                        .filter(
                            Log.entity_type == "database_version",
                            Log.entity_id.in_(version_ids),
                            Log.action.ilike("%Создана версия БД%")
                        )
                        .order_by(Log.timestamp.asc())
                        .all())
            # Берем первый лог создания на каждый id
            for lg in logs:
                if lg.entity_id not in creators_map:
                    creators_map[lg.entity_id] = lg.username
    except Exception:
        creators_map = {}

    return render_template(
        "generation/database_versions/database_versions.html",
        form=form,
        version_list=pagination.items,
        pagination=pagination,
        version_filter=version_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        creators_map=creators_map
    )


@station_bp.route("/add_database_version", methods=["GET", "POST"])
@login_required
def add_database_version():
    """ Маршрут для добавления новой версии БД. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления версии БД", 
        entity_type="database_version")

    # Создание формы
    form = AddDatabaseVersionForm()
    
    # Заполнение выбора базовой версии
    all_versions = DatabaseVersion.query.order_by(DatabaseVersion.version_number.desc()).all()
    base_parent_choices = [
        ('', 'Выберите вариант'),
        ('empty', 'Новая пустая версия')
    ]
    form.parent_version_id.choices = base_parent_choices + [
        (str(v.id), f"Версия {v.version_number}: {v.name}")
        for v in all_versions
    ]
    form.refdata_source_version_id.choices = [('', 'Выберите версию для копирования')] + [
        (str(v.id), f"Версия {v.version_number}: {v.name}")
        for v in all_versions
    ]

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "generation/database_versions/database_versions_add.html",
                form=form
            )
        
        try:
            raw_parent_value = (form.parent_version_id.data or '').strip()
            create_mode = 'default'  # default, empty, inherit

            if raw_parent_value.lower() in ('', 'none'):
                parent_id = None
            elif raw_parent_value == 'empty':
                parent_id = None
                create_mode = 'empty'
            else:
                try:
                    parent_id = int(raw_parent_value)
                    create_mode = 'inherit'
                except ValueError as exc:
                    raise ValueError("Некорректное значение поля «Создать на основе версии».") from exc

            refdata_source_id = form.refdata_source_version_id.data
            if refdata_source_id in (None, '', 'None', 'none'):
                refdata_source_id = None
            else:
                refdata_source_id = int(refdata_source_id)

            if create_mode != 'empty':
                refdata_source_id = None
            elif not refdata_source_id:
                flash("Для пустой версии необходимо выбрать источник справочников.", "danger")
                return render_template(
                    "generation/database_versions/database_versions_add.html",
                    form=form,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    version_filter=version_filter,
                )

            if parent_id and refdata_source_id:
                flash("Нельзя одновременно копировать полную версию и только справочники.", "danger")
                return render_template(
                    "generation/database_versions/database_versions_add.html",
                    form=form,
                    page=page,
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    version_filter=version_filter,
                )
            
            payload = [{
                "version_number": form.version_number.data,
                "name": (form.name.data or "").strip(),
                "description": (form.description.data or "").strip(),
                "parent_version_id": parent_id,
                "refdata_source_version_id": refdata_source_id,
            }]

            # Добавление новой записи через сервис
            new_version_id = add_version_service(payload, user)
            
            # Сообщение зависит от того, копировались ли данные
            if create_mode == 'inherit' and parent_id:
                parent = DatabaseVersion.query.get(parent_id)
                if parent:
                    flash(f"Новая версия успешно создана на основе версии {parent.version_number}: {parent.name}. Данные скопированы.", "success")
                else:
                    flash("Новая версия успешно добавлена.", "success")
            elif create_mode == 'empty' and refdata_source_id:
                ref_parent = DatabaseVersion.query.get(refdata_source_id)
                if ref_parent:
                    flash(f"Новая версия создана как пустая, но справочники скопированы из версии {ref_parent.version_number}: {ref_parent.name}.", "success")
                else:
                    flash("Новая версия успешно добавлена.", "success")
            elif create_mode == 'empty':
                flash("Новая пустая версия успешно создана.", "success")
            else:
                flash("Новая версия успешно создана.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = version_query(version_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "station_bp.database_versions",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                version_filter=version_filter,
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
        "generation/database_versions/database_versions_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        version_filter=version_filter,
    )


@station_bp.route("/export_database_versions", methods=["GET"])
@login_required
def export_database_versions():
    """Маршрут для экспорта версий БД в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "version_number")
    sort_dir            = request.args.get("sort_dir", "desc")
    version_filter      = request.args.get("version_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_version_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        version_filter=version_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.database_versions"))
        
        # Формирование имени файла
        filename = f"database_versions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/set_active_version/<int:version_id>", methods=["POST"])
@login_required
def set_active_version_route(version_id):
    """Маршрут для установки активной версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = set_active_version(version_id, user)
        flash(f"Версия '{version.name}' (v{version.version_number}) установлена как активная.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка установки активной версии: {e}")
        flash("Ошибка при установке активной версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/save_version_snapshot/<int:version_id>", methods=["POST"])
@login_required
def save_version_snapshot_route(version_id):
    """Маршрут для сохранения снимка версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = save_version_snapshot(version_id, user)
        flash(f"Снимок версии '{version.name}' (v{version.version_number}) успешно сохранен.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка сохранения снимка: {e}")
        flash("Ошибка при сохранении снимка версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/load_version_snapshot/<int:version_id>", methods=["POST"])
@login_required
def load_version_snapshot_route(version_id):
    """Маршрут для загрузки снимка версии БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        version = load_version_snapshot(version_id, user)
        flash(f"Снимок версии '{version.name}' (v{version.version_number}) успешно загружен.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка загрузки снимка: {e}")
        flash("Ошибка при загрузке снимка версии.", "danger")
    
    return redirect(url_for("station_bp.database_versions"))


@station_bp.route("/compare_versions", methods=["GET", "POST"])
@login_required
def compare_versions_route():
    """Маршрут для сравнения двух версий БД."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    # Получаем список всех версий для выбора
    all_versions = DatabaseVersion.query.order_by(DatabaseVersion.version_number.desc()).all()
    
    if request.method == "POST":
        version_id_1 = request.form.get("version_id_1", type=int)
        version_id_2 = request.form.get("version_id_2", type=int)
        
        if not version_id_1 or not version_id_2:
            flash("Необходимо выбрать две версии для сравнения.", "warning")
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions
            )
        
        if version_id_1 == version_id_2:
            flash("Выберите разные версии для сравнения.", "warning")
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions
            )
        
        try:
            comparison = compare_versions(version_id_1, version_id_2)
            
            log_to_db(
                user,
                f"Выполнено сравнение версий БД",
                f"Версия {comparison['version1']['version_number']} vs Версия {comparison['version2']['version_number']}",
                entity_type="database_version"
            )
            
            return render_template(
                "generation/database_versions/compare_versions.html",
                versions=all_versions,
                comparison=comparison
            )
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка сравнения версий: {e}")
            flash("Ошибка при сравнении версий.", "danger")
    
    return render_template(
        "generation/database_versions/compare_versions.html",
        versions=all_versions
    )


@station_bp.route("/export_comparison/<int:version_id_1>/<int:version_id_2>", methods=["GET"])
@login_required
def export_comparison_route(version_id_1, version_id_2):
    """Маршрут для экспорта сравнения версий в Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        excel_data = export_comparison_to_excel(version_id_1, version_id_2)
        
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.compare_versions"))
        
        # Формирование имени файла
        filename = f"version_comparison_{version_id_1}_vs_{version_id_2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)
        
        log_to_db(
            user,
            f"Экспортировано сравнение версий БД",
            f"Версия {version_id_1} vs Версия {version_id_2}",
            entity_type="database_version"
        )
        
        return send_file(
            excel_data,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_age=0,
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта сравнения: {e}")
        flash("Ошибка экспорта данных сравнения.", "danger")
        return redirect(url_for("station_bp.compare_versions"))


