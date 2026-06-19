"""Маршруты справочника «Зарубежные страны, имеющие общие границы с РФ»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

from app.refdata.forms.territories.foreign_border_country_forms import (
    ForeignBorderCountryFilterForm,
    AddForeignBorderCountryForm,
)

from app.refdata.services.territories.foreign_border_country_services import (
    foreign_border_country_query,
    get_foreign_border_country_list,
    update_foreign_border_country_service,
    update_foreign_border_country_all_versions_service,
    add_foreign_border_country_service,
    add_foreign_border_country_all_versions_service,
    delete_foreign_border_country_service,
    export_foreign_border_country_service,
)

from app.logs.services.logging_service import log_to_db


def _normalize_filter(value):
    if value in (None, "", "None"):
        return None
    return value


@refdata_bp.route("/foreign_border_country", methods=["GET", "POST"])
@login_required
def foreign_border_country_list():
    """Маршрут для отображения списка зарубежных стран."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user,
        "Открыта страница зарубежных стран, имеющих общие границы с РФ",
        entity_type="foreign_border_country",
    )

    form = ForeignBorderCountryFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "display_order")
    sort_dir = request.args.get("sort_dir", "asc")
    foreign_border_country_filter = _normalize_filter(request.args.get("foreign_border_country_filter"))

    if request.method == "POST":
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 25, type=int)
        sort_by = request.form.get("sort_by", "display_order")
        sort_dir = request.form.get("sort_dir", "asc")
        foreign_border_country_filter = _normalize_filter(request.form.get("foreign_border_country_filter"))

        foreign_border_country_ids = request.form.getlist("foreign_border_country_ids[]")
        foreign_border_country_names = request.form.getlist("foreign_border_country_names[]")
        foreign_border_country_orders = request.form.getlist("display_orders[]")
        foreign_border_country_delete = request.form.getlist("foreign_border_country_delete[]")

        deleted_ids = set()
        if foreign_border_country_delete:
            try:
                delete_foreign_border_country_service(foreign_border_country_delete, user)
                deleted_ids = {int(item) for item in foreign_border_country_delete if item}
                flash("Записи успешно удалены.", "success")
            except Exception:
                flash("Ошибка удаления записей.", "danger")

        try:
            if not foreign_border_country_ids or not foreign_border_country_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for(
                    "refdata_bp.foreign_border_country_list",
                    page=page,
                    per_page=per_page,
                    foreign_border_country_filter=foreign_border_country_filter,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                ))

            foreign_border_country_data = []
            for country_id, country_name, display_order in zip(
                foreign_border_country_ids,
                foreign_border_country_names,
                foreign_border_country_orders,
            ):
                if country_id and int(country_id) in deleted_ids:
                    continue
                try:
                    parsed_display_order = (
                        int(display_order)
                        if display_order and str(display_order).strip()
                        else None
                    )
                except ValueError:
                    raise ValueError(
                        (
                            f"Ошибка обработки порядка отображения для записи c ID={country_id}: "
                            f"значение «{display_order}» не является целым числом."
                        )
                    )

                foreign_border_country_data.append({
                    "foreign_border_country_id": int(country_id) if country_id else None,
                    "name": country_name.strip(),
                    "display_order": parsed_display_order,
                })

            if not foreign_border_country_data:
                return redirect(url_for(
                    "refdata_bp.foreign_border_country_list",
                    page=page,
                    per_page=per_page,
                    foreign_border_country_filter=foreign_border_country_filter,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                ))

            ids = [
                record["foreign_border_country_id"]
                for record in foreign_border_country_data
                if record["foreign_border_country_id"] is not None
            ]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for(
                        "refdata_bp.foreign_border_country_list",
                        page=page,
                        per_page=per_page,
                        foreign_border_country_filter=foreign_border_country_filter,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                    ))
                update_foreign_border_country_all_versions_service(foreign_border_country_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_foreign_border_country_service(foreign_border_country_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for(
            "refdata_bp.foreign_border_country_list",
            page=page,
            per_page=per_page,
            foreign_border_country_filter=foreign_border_country_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        ))

    pagination = get_foreign_border_country_list(
        page,
        per_page,
        foreign_border_country_filter,
        sort_by,
        sort_dir,
    )

    return render_template(
        "refdata/territories/foreign_border_country/foreign_border_country.html",
        form=form,
        foreign_border_country_list=pagination.items,
        pagination=pagination,
        foreign_border_country_filter=foreign_border_country_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@refdata_bp.route("/add_foreign_border_country", methods=["GET", "POST"])
@login_required
def add_foreign_border_country():
    """Маршрут для добавления новой зарубежной страны."""

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user,
        "Открыта страница добавления зарубежных стран",
        entity_type="foreign_border_country",
    )

    form = AddForeignBorderCountryForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "display_order")
    sort_dir = request.args.get("sort_dir", "asc")
    foreign_border_country_filter = request.args.get("foreign_border_country_filter", "").strip()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Ошибка в поле '{getattr(form, field).label.text}': {error}", "danger")
            return render_template(
                "refdata/territories/foreign_border_country/foreign_border_country_add.html",
                form=form,
            )

        try:
            payload = [{
                "name": (form.name.data or "").strip(),
            }]

            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for(
                        "refdata_bp.foreign_border_country_list",
                        page=page,
                        per_page=per_page,
                        foreign_border_country_filter=foreign_border_country_filter,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                    ))
                add_foreign_border_country_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_foreign_border_country_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            total_records = foreign_border_country_query(foreign_border_country_filter).count()
            last_page = (total_records + per_page - 1) // per_page
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.foreign_border_country_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                foreign_border_country_filter=foreign_border_country_filter,
            ))

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")

    return render_template(
        "refdata/territories/foreign_border_country/foreign_border_country_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        foreign_border_country_filter=foreign_border_country_filter,
    )


@refdata_bp.route("/export_foreign_border_country", methods=["GET"])
@login_required
def export_foreign_border_country():
    """Маршрут для экспорта зарубежных стран в Excel."""

    user = session.get('username', 'Неизвестный пользователь')

    sort_by = request.args.get("sort_by", "display_order")
    sort_dir = request.args.get("sort_dir", "asc")
    foreign_border_country_filter = request.args.get("foreign_border_country_filter")

    try:
        excel_data = export_foreign_border_country_service(
            user=user,
            sort_by=sort_by,
            sort_dir=sort_dir,
            foreign_border_country_filter=foreign_border_country_filter,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.foreign_border_country_list"))

        filename = f"foreign_border_country_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        excel_data.seek(0)

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
        return redirect(url_for("refdata_bp.foreign_border_country_list"))
