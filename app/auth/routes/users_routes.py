# -*- coding: utf-8 -*-
"""
Маршруты раздела «Пользователи и роли».

Стиль: как у gen_company_routes.py
- PRG-паттерн: POST -> redirect(GET) с сохранением параметров
- Все операции с БД через сервисы (никакой бизнес-логики во вьюхах)
- Подробное логирование
- Единый макет пагинации и сортировки (как на gen_company)
"""

from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.auth.forms.users_forms import UsersBulkForm
from app.common.models.pagination import Pagination
from app.auth.routes.decorators import roles_required
from app.auth.models.user_model import User
from app.auth.models.role_model import Role
from app.auth.services.users_services import (
    fetch_roles_all,
    get_users_page,
    update_users_and_roles,
    bulk_delete_users,
    create_user,
)
from . import users_bp

# Список пользователей (GET + POST/сохранение)
# -----------------------------------------
@users_bp.route("", methods=["GET", "POST"])
@login_required
@roles_required(["admin"])
def list_users():
    """
    GET: вывод страницы.
    POST: массовое сохранение (логины/email + роли) и/или удаление.
    После POST — редирект на GET с теми же args (PRG).
    """
    form = UsersBulkForm()
    # Общие параметры
    q = (request.values.get("q") or "").strip()
    sort_by = request.values.get("sort_by") or "id"
    sort_dir = request.values.get("sort_dir") or "asc"
    page = int(request.values.get("page") or 1)
    per_page = int(request.values.get("per_page") or 50)

    if request.method == "POST":
        if not form.validate_on_submit():
            flash("Сессия изменилась. Обновите страницу и попробуйте снова.", "warning")
            return redirect(url_for("users_bp.list_users",
                                    q=request.values.get("q",''),
                                    sort_by=request.values.get("sort_by",'id'),
                                    sort_dir=request.values.get("sort_dir",'asc'),
                                    page=request.values.get("page",1),
                                    per_page=request.values.get("per_page", 50)))
        try:
            # 1) Основные списки
            user_ids = request.form.getlist("user_ids[]")
            usernames = request.form.getlist("usernames[]")
            emails = request.form.getlist("emails[]")

            # 2) assign[user_id][role_id] = "on"
            assign = {}
            for k in request.form:
                if not k.startswith("assign["):
                    continue
                value = request.form.get(k)
                try:
                    inside = k[len("assign["):-1]  # '<uid>][<rid>'
                    uid_str, rid_str = inside.split("][")
                except Exception:
                    continue
                assign.setdefault(uid_str, {})[rid_str] = value


            # 3) признак «снимка» по пользователю
            assign_present = {
                k[len("assign_present["):-1]: "1"
                for k in request.form.keys()
                if k.startswith("assign_present[")
            }

            # 4) удаление
            to_delete = [int(x) for x in request.form.getlist("users_delete[]")]
            if current_user.id in to_delete:
                to_delete.remove(current_user.id)
                flash("Нельзя удалить текущего пользователя.", "warning")

            # 5) Сохранение
            updated = update_users_and_roles(
                user=current_user,
                user_ids=[int(x) for x in user_ids],
                usernames=usernames,
                emails=emails,
                assign=assign,
                assign_present=assign_present,
            )

            deleted = 0
            if to_delete:
                deleted = bulk_delete_users(current_user, to_delete)

            if updated:
                flash(f"Изменения сохранены: {updated} пользователи(ей).", "success")
            if deleted:
                flash(f"Удалено: {deleted} пользователи(ей).", "success")
            if not updated and not deleted:
                flash("Нет изменений для сохранения.", "info")

            return redirect(url_for(
                "users_bp.list_users",
                q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
            ))

        except Exception as e:
            db.session.rollback()
            flash(str(e), "danger")
            return redirect(url_for(
                "users_bp.list_users",
                q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
            ))

    # --- GET ---
    roles = fetch_roles_all(current_user)
    users, total = get_users_page(current_user, q, sort_by, sort_dir, page, per_page)
    pagination = Pagination(page=page, per_page=per_page, total=total)

    return render_template(
        "auth/users/users.html",
        form=form,
        users=users,
        roles=roles,
        pagination=pagination,
        q=q, sort_by=sort_by, sort_dir=sort_dir, per_page=per_page
    )


# -----------------------------------------
# Создание пользователя (GET + POST)
# -----------------------------------------
@users_bp.route("/add", methods=["GET", "POST"])
@login_required
@roles_required(["admin"])
def add_user():
    """
    Простая форма создания пользователя.
    Шаблон можно сделать минимальным (username, email, password, роли[]).
    После успешного создания — редирект на список с сохранением args.
    """
    # Параметры для возврата на список
    q = (request.values.get("q") or "").strip()
    sort_by = request.values.get("sort_by") or "id"
    sort_dir = request.values.get("sort_dir") or "asc"
    page = int(request.values.get("page") or 1)
    per_page = int(request.values.get("per_page") or 50)

    if request.method == "POST":
        try:
            username = (request.form.get("username") or "").strip()
            email = (request.form.get("email") or "").strip()
            raw_password = (request.form.get("password") or "").strip()
            role_ids = [int(r) for r in request.form.getlist("role_ids[]")]

            u = create_user(
                user=current_user,
                username=username,
                email=email,
                raw_password=raw_password,
                role_ids=role_ids,
            )
            flash(f"Пользователь «{u.username}» создан.", "success")
            return redirect(url_for(
                "users_bp.list_users",
                q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
            ))

        except Exception as e:
            db.session.rollback()
            log_to_db(current_user, "Ошибка создания пользователя", str(e))
            flash(str(e), "danger")
            # падать не будем — снова отрисуем форму

    roles = fetch_roles_all(current_user)
    return render_template(
        "auth/users/user_add.html",
        roles=roles,
        q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
    )


# -----------------------------------------
# Совместимость: одиночное удаление по старому URL
# -----------------------------------------
@users_bp.route("/delete/<int:user_id>", methods=["POST"])
@login_required
@roles_required(["admin"])
def delete_user(user_id: int):
    """
    Совместимость для кнопок/скриптов, которые еще могут вызывать одиночное удаление.
    В новой версии используется массовое удаление чекбоксами в основной форме.
    """
    q = (request.values.get("q") or "").strip()
    sort_by = request.values.get("sort_by") or "id"
    sort_dir = request.values.get("sort_dir") or "asc"
    page = int(request.values.get("page") or 1)
    per_page = int(request.values.get("per_page") or 50)

    if user_id == current_user.id:
        flash("Нельзя удалить текущего пользователя.", "warning")
        return redirect(url_for(
            "users_bp.list_users",
            q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
        ))

    try:
        deleted = bulk_delete_users(current_user, [user_id])
        if deleted:
            flash("Пользователь удален.", "success")
        else:
            flash("Пользователь не найден.", "warning")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for(
        "users_bp.list_users",
        q=q, sort_by=sort_by, sort_dir=sort_dir, page=page, per_page=per_page
    ))


@users_bp.after_request
def no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp