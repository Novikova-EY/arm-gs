"""Маршруты справочника «Номативные документы»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app, jsonify
from collections import Counter
from datetime import datetime
import os

from flask_login import login_required

# Блюпринт
from app.generation.routes.stations import station_bp

# Формы
from app.generation.forms.documents.document_forms import (
    DocumentFilterForm, 
    AddDocumentForm,
)

# Сервисы
from app.generation.services.documents.document_services import (
    document_query,
    get_document_list,
    update_document_service, 
    add_document_service, 
    delete_document_service,
    export_document_service,
    save_document_file,
    delete_document_file,
    get_document_file_path,
    normalize_file_path,
)

# Логирование
from app.logs.services.logging_service import log_to_db

# Модели и расширения
from app.generation.models.document.document_model import Document
from app.extensions import db


@station_bp.route("/documents_kommod", methods=["GET", "POST"])
@login_required
def documents_kommod():
    """Маршрут для отображения списка нормативных документов."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница нормативных документов", entity_type="document")
    
    # Создание формы
    form = DocumentFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    document_filter     = request.args.get("document_filter")
    # Нормализация значения фильтра (мог прийти строкой 'None')
    if document_filter in (None, "", "None", "none"):
        document_filter = None

    if request.method == "POST":       
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 20, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        document_filter     = request.form.get("document_filter")
        if document_filter in (None, "", "None", "none"):
            document_filter = None

        # Получение данных из формы
        document_ids        = request.form.getlist("document_ids[]")
        document_names      = request.form.getlist("document_names[]")
        document_delete     = request.form.getlist("document_delete[]")
  
        # Удаление записей
        if document_delete:
            try:
                delete_document_service(document_delete, user)
                flash("Записи документов успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("station_bp.documents_kommod", 
                                    page=page, 
                                    per_page=per_page, 
                                    document_filter=document_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
        # Обновление данных в базе
        try:
            if not document_ids or not document_names:
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("station_bp.documents_kommod", 
                                        page=page, 
                                        per_page=per_page, 
                                        document_filter=document_filter,
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))
           
           # Формирование данных для обновления
            document_data = []
            for document_id, document_name in zip(document_ids, document_names):
                document_data.append({
                    "document_id": int(document_id) if document_id else None,
                    "name": document_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["document_id"] for record in document_data if record["document_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID документов: {duplicates}")

            # Обновление данных в базе
            update_document_service(document_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("station_bp.documents_kommod", 
                                page=page, 
                                per_page=per_page, 
                                document_filter=document_filter,
                                sort_by=sort_by, 
                                sort_dir=sort_dir))

    # Получение данных для отображения
    pagination = get_document_list(
                                page, 
                                per_page, 
                                document_filter,
                                sort_by, 
                                sort_dir)

    return render_template(
        "generation/documents/documents_kommod.html",
        form=form,
        document_list=pagination.items,
        pagination=pagination,
        document_filter=document_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@station_bp.route("/add_document_kommod", methods=["GET", "POST"])
@login_required
def add_document_kommod():
    """ Маршрут для добавления нового нормативного документа. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления нормативных документов", 
        entity_type="document")

    # Создание формы
    form = AddDocumentForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    document_filter     = request.args.get("document_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "generation/documents/documents_kommod_add.html",
                form=form
            )
        
        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            # Добавление новой записи через сервис
            new_document_id = add_document_service(payload, user)
            
            # Если загружен файл, сохраняем его
            if form.file.data and new_document_id:
                try:
                    save_document_file(form.file.data, new_document_id, user)
                    flash("Новая запись и файл успешно добавлены.", "success")
                except ValueError as file_error:
                    flash(f"Запись добавлена, но ошибка при загрузке файла: {file_error}", "warning")
                except Exception as file_error:
                    current_app.logger.error(f"Ошибка загрузки файла: {file_error}")
                    flash(f"Запись добавлена, но ошибка при загрузке файла: {file_error}", "warning")
            else:
                flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = document_query(
                                document_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            
            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "station_bp.documents_kommod",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                document_filter=document_filter,
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
        "generation/documents/documents_kommod_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        document_filter=document_filter,
    )


@station_bp.route("/export_documents_kommod", methods=["GET"])
@login_required
def export_documents_kommod():
    """Маршрут для экспорта нормативых документов в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    document_filter     = request.args.get("document_filter")

    try:
        # Получение данных для экспорта
        excel_data = export_document_service(
                        user=user,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                        document_filter=document_filter,
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.documents_kommod"))
        
        # Формирование имени файла
        filename = f"documents_kommod_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("station_bp.documents_kommod"))


@station_bp.route("/view_document_file/<int:document_id>", methods=["GET"])
@login_required
def view_document_file(document_id):
    """Маршрут для просмотра файла документа в браузере."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        file_path, file_name = get_document_file_path(document_id)
        
        if not file_path or not file_name:
            flash("Файл не найден.", "warning")
            return redirect(url_for("station_bp.documents_kommod"))
        
        # Нормализуем путь для Windows (преобразуем относительный путь в абсолютный)
        file_path = normalize_file_path(file_path)
        
        if not os.path.exists(file_path):
            current_app.logger.error(f"Файл не найден по пути: {file_path}")
            flash("Файл не найден в файловой системе.", "danger")
            return redirect(url_for("station_bp.documents_kommod"))
        
        log_to_db(user, f"Просмотр файла документа ID={document_id}", file_name, entity_type="document", entity_id=document_id)
        
        # as_attachment=False позволяет открыть файл в браузере для просмотра
        return send_file(
            file_path,
            as_attachment=False,
            download_name=file_name,
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка просмотра файла: {e}")
        flash("Ошибка при открытии файла.", "danger")
        return redirect(url_for("station_bp.documents_kommod"))


@station_bp.route("/download_document_file/<int:document_id>", methods=["GET"])
@login_required
def download_document_file(document_id):
    """Маршрут для скачивания файла документа."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        file_path, file_name = get_document_file_path(document_id)
        
        if not file_path or not file_name:
            flash("Файл не найден.", "warning")
            return redirect(url_for("station_bp.documents_kommod"))
        
        # Нормализуем путь для Windows (преобразуем относительный путь в абсолютный)
        file_path = normalize_file_path(file_path)
        
        if not os.path.exists(file_path):
            current_app.logger.error(f"Файл не найден по пути: {file_path}")
            flash("Файл не найден в файловой системе.", "danger")
            return redirect(url_for("station_bp.documents_kommod"))
        
        log_to_db(user, f"Скачан файл документа ID={document_id}", file_name, entity_type="document", entity_id=document_id)
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_name,
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка скачивания файла: {e}")
        flash("Ошибка при скачивании файла.", "danger")
        return redirect(url_for("station_bp.documents_kommod"))


@station_bp.route("/upload_document_file/<int:document_id>", methods=["POST"])
@login_required
def upload_document_file(document_id):
    """Маршрут для загрузки/замены файла документа."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, f"Запрос на загрузку файла для документа ID={document_id}", f"Files в запросе: {list(request.files.keys())}", entity_type="document", entity_id=document_id)
    
    if 'file' not in request.files:
        log_to_db(user, f"Ошибка: файл не найден в запросе", "", entity_type="document", entity_id=document_id)
        flash("Файл не выбран.", "danger")
        return redirect(url_for("station_bp.documents_kommod"))
    
    file = request.files['file']
    log_to_db(user, f"Файл получен из запроса", f"Имя файла: {file.filename}", entity_type="document", entity_id=document_id)
    
    if file.filename == '':
        log_to_db(user, f"Ошибка: имя файла пустое", "", entity_type="document", entity_id=document_id)
        flash("Файл не выбран.", "danger")
        return redirect(url_for("station_bp.documents_kommod"))
    
    # Сохраняем текущие параметры отображения (если пришли из формы)
    page            = request.form.get("page", type=int)
    per_page        = request.form.get("per_page", type=int)
    sort_by         = request.form.get("sort_by")
    sort_dir        = request.form.get("sort_dir")
    document_filter = request.form.get("document_filter")

    try:
        save_document_file(file, document_id, user)
        flash("Файл успешно загружен.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка загрузки файла: {e}")
        flash("Ошибка при загрузке файла.", "danger")

    # Для избежания строки 'None' в URL совсем опустим параметр, если фильтра нет
    redirect_kwargs = {
        "page": page or 1,
        "per_page": per_page or 20,
        "sort_by": (sort_by or "id"),
        "sort_dir": (sort_dir or "asc"),
    }
    if document_filter:
        redirect_kwargs["document_filter"] = document_filter

    return redirect(url_for("station_bp.documents_kommod", **redirect_kwargs))


@station_bp.route("/delete_document_file/<int:document_id>", methods=["POST"])
@login_required
def delete_document_file_route(document_id):
    """Маршрут для удаления файла документа."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    try:
        delete_document_file(document_id, user)
        flash("Файл успешно удален.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка удаления файла: {e}")
        flash("Ошибка при удалении файла.", "danger")
    
    return redirect(url_for("station_bp.documents_kommod"))


@station_bp.route("/api/documents/search", methods=["GET"])
@login_required
def api_search_documents():
    """API endpoint для поиска документов с автозаполнением."""
    search_query = request.args.get("q", "").strip()
    
    if not search_query or len(search_query) < 2:
        return jsonify([])
    
    try:
        # Ищем документы по названию
        documents = (
            db.session.query(Document)
            .filter(Document.name.ilike(f"%{search_query}%"))
            .order_by(Document.name)
            .limit(20)
            .all()
        )
        
        # Формируем результат
        results = [
            {
                "id": doc.id,
                "name": doc.name,
                "url": url_for("station_bp.download_document_file", document_id=doc.id)
            }
            for doc in documents
        ]
        
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Ошибка поиска документов: {e}")
        return jsonify({"error": "Ошибка при поиске документов"}), 500

