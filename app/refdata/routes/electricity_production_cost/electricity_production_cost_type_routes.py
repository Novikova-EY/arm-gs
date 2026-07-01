"""Маршруты справочника «Типы затрат на производство ЭЭ и ТЭ»."""

from flask import render_template, request, redirect, url_for, flash, send_file, session, current_app
from collections import Counter
from datetime import datetime

from flask_login import login_required, current_user

from app.refdata.routes import refdata_bp
from app.refdata.routes.refdata_all_versions_guard import block_all_versions_without_admin

from app.refdata.forms.electricity_production_cost.electricity_production_cost_type_forms import (
    ElectricityProductionCostTypeFilterForm,
    AddElectricityProductionCostTypeForm,
)

from app.refdata.services.electricity_production_cost.electricity_production_cost_type_services import (
    electricity_production_cost_type_query,
    get_electricity_production_cost_type_list,
    update_electricity_production_cost_type_service,
    update_electricity_production_cost_type_all_versions_service,
    add_electricity_production_cost_type_service,
    add_electricity_production_cost_type_all_versions_service,
    delete_electricity_production_cost_type_service,
    export_electricity_production_cost_type_service,
)

from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/electricity_production_cost_type", methods=["GET", "POST"])
@login_required
def electricity_production_cost_type_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user,
        "Открыта страница затрат на производство и реализацию электрической энергии (мощности)",
        entity_type="electricity_production_cost_type",
    )

    form = ElectricityProductionCostTypeFilterForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "cost_code")
    sort_dir = request.args.get("sort_dir", "asc")
    _tf = request.args.get("electricity_production_cost_type_filter") or ""
    electricity_production_cost_type_filter = "" if str(_tf) == "None" else str(_tf)

    if request.method == "POST":
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 25, type=int)
        sort_by = request.form.get("sort_by", "cost_code")
        sort_dir = request.form.get("sort_dir", "asc")
        _tf = request.form.get("electricity_production_cost_type_filter") or ""
        electricity_production_cost_type_filter = "" if _tf == "None" else _tf.strip()

        record_ids = request.form.getlist("electricity_production_cost_type_ids[]")
        record_names = request.form.getlist("electricity_production_cost_type_names[]")
        record_delete = request.form.getlist("electricity_production_cost_type_delete[]")
        cost_codes = request.form.getlist("cost_codes[]")

        deleted_ids = set()
        if record_delete:
            try:
                delete_electricity_production_cost_type_service(record_delete, user)
                deleted_ids = {int(item) for item in record_delete if item}
                flash("Записи успешно удалены.", "success")
            except Exception:
                flash("Ошибка удаления записей.", "danger")

        try:
            if not record_ids or not record_names:
                if not deleted_ids:
                    flash("Данные для обновления отсутствуют.", "info")
                return redirect(url_for(
                    "refdata_bp.electricity_production_cost_type_list",
                    page=page,
                    per_page=per_page,
                    electricity_production_cost_type_filter=electricity_production_cost_type_filter,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                ))

            n = len(record_ids)
            cost_codes_padded = (cost_codes + [""] * n)[:n]
            names_padded = (list(record_names) + [""] * n)[:n]
            record_data = []
            for record_id, cost_code, record_name in zip(
                record_ids, cost_codes_padded, names_padded
            ):
                if record_id and int(record_id) in deleted_ids:
                    continue
                try:
                    code_val = int(cost_code) if cost_code and str(cost_code).strip() else None
                except (TypeError, ValueError):
                    code_val = None
                record_data.append({
                    "electricity_production_cost_type_id": int(record_id) if record_id else None,
                    "name": record_name.strip(),
                    "cost_code": code_val,
                })

            if not record_data:
                return redirect(url_for(
                    "refdata_bp.electricity_production_cost_type_list",
                    page=page,
                    per_page=per_page,
                    electricity_production_cost_type_filter=electricity_production_cost_type_filter,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                ))

            ids = [
                record["electricity_production_cost_type_id"]
                for record in record_data
                if record["electricity_production_cost_type_id"] is not None
            ]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]

            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID: {duplicates}")

            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for(
                        "refdata_bp.electricity_production_cost_type_list",
                        page=page,
                        per_page=per_page,
                        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                    ))
                update_electricity_production_cost_type_all_versions_service(record_data, user)
                flash("Изменения применены во всех версиях БД (по ref_uuid).", "success")
            else:
                update_electricity_production_cost_type_service(record_data, user)
                flash("Изменения успешно сохранены.", "success")

        except ValueError as e:
            flash(str(e), "danger")
        except Exception:
            flash("Ошибка сохранения данных.", "danger")

        return redirect(url_for(
            "refdata_bp.electricity_production_cost_type_list",
            page=page,
            per_page=per_page,
            electricity_production_cost_type_filter=electricity_production_cost_type_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
        ))

    pagination = get_electricity_production_cost_type_list(
        page,
        per_page,
        electricity_production_cost_type_filter,
        sort_by,
        sort_dir,
    )

    return render_template(
        "refdata/electricity_production_cost/electricity_production_cost_type/electricity_production_cost_type.html",
        form=form,
        electricity_production_cost_type_list=pagination.items,
        pagination=pagination,
        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
    )


@refdata_bp.route("/add_electricity_production_cost_type", methods=["GET", "POST"])
@login_required
def add_electricity_production_cost_type():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(
        user,
        "Открыта страница добавления затрат на производство ЭЭ (мощности)",
        entity_type="electricity_production_cost_type",
    )

    form = AddElectricityProductionCostTypeForm()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    sort_by = request.args.get("sort_by", "cost_code")
    sort_dir = request.args.get("sort_dir", "asc")
    electricity_production_cost_type_filter = request.args.get(
        "electricity_production_cost_type_filter", ""
    ).strip()

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Пожалуйста, заполните все обязательные поля.", "danger")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(
                        f"Ошибка в поле '{getattr(form, field).label.text}': {error}",
                        "danger",
                    )
            return render_template(
                "refdata/electricity_production_cost/electricity_production_cost_type/electricity_production_cost_type_add.html",
                form=form,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                electricity_production_cost_type_filter=electricity_production_cost_type_filter,
            )

        try:
            payload = [{
                "name": (form.name.data or "").strip(),
                "cost_code": form.cost_code.data,
            }]

            if request.values.get("all_versions") == "1":
                if block_all_versions_without_admin(current_user):
                    return redirect(url_for(
                        "refdata_bp.electricity_production_cost_type_list",
                        page=page,
                        per_page=per_page,
                        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                    ))
                add_electricity_production_cost_type_all_versions_service(payload, user)
                flash("Новая запись добавлена во всех версиях БД (общий ref_uuid).", "success")
            else:
                add_electricity_production_cost_type_service(payload, user)
                flash("Новая запись успешно добавлена.", "success")

            total_records = electricity_production_cost_type_query(
                electricity_production_cost_type_filter=electricity_production_cost_type_filter,
            ).count()
            last_page = (total_records + per_page - 1) // per_page
            page = min(page, last_page)

            return redirect(url_for(
                "refdata_bp.electricity_production_cost_type_list",
                page=last_page,
                per_page=per_page,
                sort_by=sort_by,
                sort_dir=sort_dir,
                electricity_production_cost_type_filter=electricity_production_cost_type_filter,
            ))

        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка добавления записи: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")

    return render_template(
        "refdata/electricity_production_cost/electricity_production_cost_type/electricity_production_cost_type_add.html",
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        form=form,
        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
    )


@refdata_bp.route("/export_electricity_production_cost_type", methods=["GET"])
@login_required
def export_electricity_production_cost_type():
    user = session.get('username', 'Неизвестный пользователь')

    sort_by = request.args.get("sort_by", "cost_code")
    sort_dir = request.args.get("sort_dir", "asc")
    electricity_production_cost_type_filter = request.args.get(
        "electricity_production_cost_type_filter"
    )

    try:
        excel_data = export_electricity_production_cost_type_service(
            user=user,
            sort_by=sort_by,
            sort_dir=sort_dir,
            electricity_production_cost_type_filter=electricity_production_cost_type_filter,
        )

        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("refdata_bp.electricity_production_cost_type_list"))

        filename = (
            f"electricity_production_cost_type_data_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
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
        return redirect(url_for("refdata_bp.electricity_production_cost_type_list"))
