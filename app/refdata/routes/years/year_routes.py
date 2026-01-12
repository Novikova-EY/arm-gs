# -*- coding: utf-8 -*-
"""Маршруты справочника «Годы»."""

from collections import Counter
from flask import render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user

from app.auth.routes import roles_required

# Блюпринт
from app.refdata.routes import refdata_bp

# Формы
from app.refdata.forms.years.year_forms import YearFilterForm, AddYearForm

from app.common.services.choices_cache_service import choices_cache
from app.common.services.database_version_services import get_current_version

# Модели
from app.refdata.models.years.year_feature_model import YearFeature

# Сервисы
from app.refdata.services.years.year_services import (
    year_query,
    get_year_list,
    update_year_service,
    add_year_service,
    delete_year_service,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@refdata_bp.route("/years", methods=["GET", "POST"])
@login_required
def years_list():
    """Страница справочника «Годы» (таблица + редактирование)."""

    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Открыта страница: годы", entity_type="year")

    # Для dropdown (строго по активной версии)
    version_id = get_current_version()

    # Форма
    form = YearFilterForm()

    # Параметры отображения
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort_by = request.args.get("sort_by", "number")
    sort_dir = request.args.get("sort_dir", "asc")
    year_filter = request.args.get("year_filter", "").strip()

    if request.method == "POST":
        if not current_user.has_admin:
            return render_template("errors/forbidden.html"), 403

        if not version_id:
            flash("Текущая версия БД не установлена", "danger")
            return redirect(url_for("refdata_bp.years_list"))

        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 20, type=int)
        sort_by = request.form.get("sort_by", "number")
        sort_dir = request.form.get("sort_dir", "asc")
        year_filter = (request.form.get("year_filter", "") or "").strip()

        year_ids = request.form.getlist("year_ids[]")
        year_numbers = request.form.getlist("year_numbers[]")
        year_features = request.form.getlist("year_features[]")
        year_delete = request.form.getlist("year_delete[]")

        # Удаление
        if year_delete:
            try:
                delete_year_service(year_delete, user)
                flash("Записи годов успешно удалены.", "success")
            except Exception as e:
                current_app.logger.error(f"Ошибка удаления годов: {e}")
                flash("Ошибка удаления записей.", "danger")

            return redirect(
                url_for(
                    "refdata_bp.years_list",
                    page=page,
                    per_page=per_page,
                    year_filter=year_filter,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                )
            )

        # Обновление
        try:
            if not year_ids or not year_numbers or not year_features:
                flash("Данные для обновления отсутствуют.", "info")
                return redirect(
                    url_for(
                        "refdata_bp.years_list",
                        page=page,
                        per_page=per_page,
                        year_filter=year_filter,
                        sort_by=sort_by,
                        sort_dir=sort_dir,
                    )
                )

            # Проверка на дублирующиеся IDs
            ids = [int(x) for x in year_ids if x]
            duplicates = [item for item, count in Counter(ids).items() if count > 1]
            if duplicates:
                raise ValueError(f"Обнаружены дублирующиеся ID годов: {duplicates}")

            payload = []
            for yid, ynum, yfeat in zip(year_ids, year_numbers, year_features):
                payload.append(
                    {
                        "year_id": int(yid) if yid else None,
                        "number": ynum,
                        "year_feature_id": int(yfeat) if yfeat else None,
                    }
                )

            update_year_service(payload, user)
            flash("Изменения успешно сохранены.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка сохранения годов: {e}")
            flash("Ошибка сохранения данных.", "danger")

        return redirect(
            url_for(
                "refdata_bp.years_list",
                page=page,
                per_page=per_page,
                year_filter=year_filter,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
        )

    # Наполняем choices (фильтрация по версии делается внутри choices_cache)
    year_feature_choices = choices_cache.get_choices(YearFeature, YearFeature.name)
    form.per_page.data = per_page

    # Получение данных
    pagination = get_year_list(
        page=page,
        per_page=per_page,
        year_filter=year_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return render_template(
        "refdata/years/year/year.html",
        form=form,
        year_list=pagination.items,
        pagination=pagination,
        year_features=year_feature_choices,
        year_filter=year_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page,
        version_id=version_id,
    )


@refdata_bp.route("/add_year", methods=["GET", "POST"])
@login_required
@roles_required(["admin"])
def add_year():
    """Страница добавления записи в справочник «Годы»."""

    user = session.get("username", "Неизвестный пользователь")
    log_to_db(user, "Открыта страница добавления года", entity_type="year")

    version_id = get_current_version()
    if not version_id:
        flash("Текущая версия БД не установлена", "danger")
        return redirect(url_for("refdata_bp.years_list"))

    form = AddYearForm()

    # Сохранение параметров возврата
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    sort_by = request.args.get("sort_by", "number")
    sort_dir = request.args.get("sort_dir", "asc")
    year_filter = request.args.get("year_filter", "").strip()

    # Dropdown признаков года (по версии)
    year_feature_choices = choices_cache.get_choices(YearFeature, YearFeature.name)
    form.year_feature.choices = year_feature_choices

    if request.method == "POST" and form.validate_on_submit():
        try:
            payload = [
                {
                    "number": form.number.data,
                    "year_feature_id": form.year_feature.data,
                }
            ]
            add_year_service(payload, user)
            flash("Новая запись успешно добавлена.", "success")

            total_records = year_query(year_filter=year_filter).count()
            last_page = (total_records + per_page - 1) // per_page

            return redirect(
                url_for(
                    "refdata_bp.years_list",
                    page=max(last_page, 1),
                    per_page=per_page,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                    year_filter=year_filter,
                )
            )
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Ошибка добавления года: {e}")
            flash("Произошла ошибка при добавлении записи. Попробуйте позже.", "danger")

    return render_template(
        "refdata/years/year/year_add.html",
        form=form,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_dir=sort_dir,
        year_filter=year_filter,
    )




