"""Маршруты справочника «Генерирующие компании»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.gen_companies.gen_company_forms import (
    GenCompanyFilterForm, 
    AddGenCompanyForm
)

# Сервисы
from app.refdata.services.gen_companies.gen_company_services import (
    gen_company_query,
    get_gen_company_list,
    update_gen_company_service,
    add_gen_company_service,
    delete_gen_company_service,
    export_gen_company_service,
    import_gen_company_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/gen_company", methods=["GET", "POST"])
@login_required
def gen_company_list():
    """Маршрут для отображения генерирующих компаний"""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница генерирующих компаний", 
        entity_type="gen_company")
    
    # Создание формы
    form = GenCompanyFilterForm()

    # Получение параметров запроса
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    gen_company_filter  = request.args.get("gen_company_filter", "").strip()

    if request.method == "POST":
        # Обновление параметров из формы
        page                = request.form.get("page", 1, type=int)
        per_page            = request.form.get("per_page", 20, type=int)
        sort_by             = request.form.get("sort_by", "id")
        sort_dir            = request.form.get("sort_dir", "asc")
        gen_company_filter  = request.form.get("gen_company_filter", "").strip()

        # Получение данных из формы
        gen_company_ids     = request.form.getlist("gen_company_ids[]")
        gen_company_names   = request.form.getlist("gen_company_names[]")
        gen_company_delete  = request.form.getlist("gen_company_delete[]")
        
        # Удаление записей
        if gen_company_delete:
            try:
                delete_gen_company_service(gen_company_delete, user)
                flash("Записи генерирующих компаний успешно удалены.", "success")
            except Exception as e:
                flash("Ошибка удаления записей.", "danger")
            return redirect(url_for("refdata_bp.gen_company_list", 
                                    page=page, 
                                    per_page=per_page, 
                                    gen_company_filter=gen_company_filter, 
                                    sort_by=sort_by, 
                                    sort_dir=sort_dir))
           
        # Обновление данных в базе
        try:
            if not gen_company_ids or not gen_company_names:
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for("refdata_bp.gen_company_list", 
                                        page=page, 
                                        per_page=per_page, 
                                        gen_company_filter=gen_company_filter, 
                                        sort_by=sort_by, 
                                        sort_dir=sort_dir))

           # Формирование данных для обновления
            gen_company_data = []
            for gen_company_id, gen_company_name in zip(gen_company_ids, gen_company_names):
                if gen_company_name is None or gen_company_name.strip() == "":
                    raise ValueError(f"Пустое имя для ID: {gen_company_id}")
                gen_company_data.append({
                    "gen_company_id": int(gen_company_id) if gen_company_id else None,
                    "name": gen_company_name.strip(),
                })
            
            # Проверка на дублирующиеся IDs
            ids = [record["gen_company_id"] for record in gen_company_data if record["gen_company_id"] is not None]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID генерирующих компаний: {duplicates}")

            # Обновление данных в базе
            update_gen_company_service(gen_company_data, user)
            flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for("refdata_bp.gen_company_list", 
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
        "refdata/gen_companies/gen_company.html",
        form=form,
        gen_company_list=pagination.items,
        pagination=pagination,
        gen_company_filter=gen_company_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


@refdata_bp.route("/add_gen_company", methods=["GET", "POST"])
@login_required
def add_gen_company():
    """ Маршрут для добавления новой генерирующей компании. """

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user, 
        "Открыта страница добавления генерирующей компании", 
        entity_type="gen_company")

    # Создание формы
    form = AddGenCompanyForm()

    # Сохранение текущих фильтров и параметров отображения
    page                = request.args.get("page", 1, type=int)
    per_page            = request.args.get("per_page", 20, type=int)
    sort_by             = request.args.get("sort_by", "id")
    sort_dir            = request.args.get("sort_dir", "asc")
    gen_company_filter  = request.args.get("gen_company_filter", "").strip()

    # Обработка формы
    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/gen_companies/gen_company_add.html",
                form=form
            )

        try:
            payload = [{
                "name": form.name.data,
            }]
        
            # Добавление новой записи через сервис
            add_gen_company_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            # Перенаправление на список с сохранением параметров и переходом к новой записи
            total_records = gen_company_query(
                                gen_company_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            # Корректировка текущей страницы, если она больше последней
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.gen_company_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                gen_company_filter=gen_company_filter,
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
        "refdata/gen_companies/gen_company_add.html", 
        page=page,
        per_page=per_page, 
        sort_by=sort_by, 
        sort_dir=sort_dir, 
        form=form,
        gen_company_filter=gen_company_filter, 
    )


@refdata_bp.route("/import_gen_company", methods=["POST"])
@login_required
def import_gen_company():
    """Маршрут для импорта данных из Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("refdata_bp.gen_company_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("refdata_bp.gen_company_list"))

    try:
        imported_count = import_gen_company_service(file, user)
        flash(f"Импортировано записей: {imported_count}.", "success")
    except ValueError as e:
            msg = str(e)
            if 'уже существует' in msg:
                flash(msg, 'warning')
            else:
                flash(msg, 'danger')
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("refdata_bp.gen_company_list"))


@refdata_bp.route("/export_gen_company", methods=["GET"])
@login_required
def export_gen_company():
    """Маршрут для экспорта видов топлива в Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    
    sort_by                = request.args.get("sort_by", "id")
    sort_dir               = request.args.get("sort_dir", "asc")
    gen_company_filter     = request.args.get("gen_company_filter", "").strip()

    try:
        # Получение данных для экспорта
        excel_data = export_gen_company_service(
                        user=user, 
                        sort_by=sort_by, 
                        sort_dir=sort_dir,
                        gen_company_filter=gen_company_filter, 
        )

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.gen_company_list"))
        
        # Формирование имени файла
        filename = f"gen_company_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
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
        return redirect(url_for("refdata_bp.gen_company_list"))