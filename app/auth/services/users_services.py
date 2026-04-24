# -*- coding: utf-8 -*-
"""
Сервисы для раздела «Пользователи и роли».
Логирование: только факты изменений/добавлений/удалений (по-русски, без id/uid).
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any, Iterable

import sqlalchemy as sa
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.common.services.tranzaction_services import _commit_with_retry
from app.auth.models.user_model import User
from app.auth.models.role_model import Role
from app.logs.services.logging_service import log_to_db


# -------------------------------
# Вспомогательная сортировка
# -------------------------------

_SORT_COLUMNS = {
    "id": User.id,
    "username": User.username,
    "email": User.email,
    "number": User.id,  # визуальная нумерация
}

def _apply_sorting(query, sort_by: str, sort_dir: str):
    col = _SORT_COLUMNS.get((sort_by or "id").lower(), User.id)
    direction = desc if (sort_dir or "asc").lower() == "desc" else asc
    return query.order_by(direction(col))


# -------------------------------
# Чтение данных (без логов)
# -------------------------------

def fetch_roles_all(user) -> List[Role]:
    return Role.query.order_by(asc(Role.id)).all()

def build_users_query(user, q: str) -> "sa.Query":
    query = User.query
    if q:
        q_like = f"%{q.strip()}%"
        query = query.filter(
            (func.lower(User.username).ilike(func.lower(q_like))) |
            (func.lower(User.email).ilike(func.lower(q_like)))
        )
    return query

def get_users_page(user, q: str, sort_by: str, sort_dir: str,
                   page: int, per_page: int) -> Tuple[List[User], int]:
    base_q = build_users_query(user, q)
    total = base_q.count()
    page = max(int(page or 1), 1)
    per_page = max(int(per_page or 50), 1)
    items = _apply_sorting(base_q, sort_by, sort_dir) \
        .offset((page - 1) * per_page).limit(per_page).all()
    return items, total


# -------------------------------
# Утилиты форматирования для логов
# -------------------------------

def _roles_names_map() -> Dict[int, str]:
    rows = Role.query.with_entities(Role.id, Role.name_full).all()
    return {rid: name for rid, name in rows}

def _fmt_roles(ids: Iterable[int], names_map: Dict[int, str]) -> str:
    """Список ролей только по именам, без числовых id: [Гость, Генерация-чтение]."""
    names = [names_map.get(int(i), str(int(i))) for i in sorted({int(i) for i in ids})]
    return "[" + ", ".join(names) + "]"


# -------------------------------
# Мутации (только факт-логи)
# -------------------------------

def update_users_and_roles(user: Any,
                           user_ids: List[int],
                           usernames: List[str],
                           emails: List[str],
                           assign: Dict[str, Dict[str, str]],
                           assign_present: Optional[Dict[str, str]] = None) -> int:
    """
    Обновляем только реально измененные поля/роли.
    Логируем ПО ФАКТУ (после commit): для каждого измененного пользователя — детальный список изменений.
    """
    if not (user_ids and usernames and emails) or \
       not (len(user_ids) == len(usernames) == len(emails)):
        raise ValueError("Некорректные параметры обновления пользователей")

    names_map = _roles_names_map()

    # Копим строки логов и пишем их только после успешного commit
    change_logs: List[Tuple[str, str]] = []  # (action, details)
    updated = 0

    try:
        for idx, uid in enumerate(user_ids):
            uid = int(uid)
            u = User.query.get(uid)
            if not u:
                continue

            # Снимки "до"
            old_username = u.username
            old_email = u.email
            old_roles = {r.id for r in u.roles}

            per_user_changes: List[str] = []

            # --- username ---
            new_username = (usernames[idx] or "").strip()
            if new_username != old_username:
                if User.query.filter(User.id != uid, User.username == new_username).first():
                    raise ValueError(f"Имя '{new_username}' уже используется другим пользователем")
                u.username = new_username
                per_user_changes.append(f"Логин: {old_username!r} → {new_username!r}")

            # --- email ---
            new_email = (emails[idx] or "").strip()
            if new_email != old_email:
                if User.query.filter(User.id != uid, User.email == new_email).first():
                    raise ValueError(f"Email '{new_email}' уже используется другим пользователем")
                u.email = new_email
                per_user_changes.append(f"Email: {old_email!r} → {new_email!r}")

            # --- роли ---
            apply_snapshot = bool(assign_present and str(uid) in assign_present)
            if apply_snapshot:
                new_role_ids = set(int(rid) for rid in (assign.get(str(uid)) or {}).keys())
                if new_role_ids != old_roles:
                    added = sorted(new_role_ids - old_roles)
                    removed = sorted(old_roles - new_role_ids)
                    u.roles = Role.query.filter(Role.id.in_(new_role_ids)).all() if new_role_ids else []
                    per_user_changes.append(
                        "Роли: "
                        f"{_fmt_roles(old_roles, names_map)} → {_fmt_roles(new_role_ids, names_map)}; "
                        f"добавлено={_fmt_roles(added, names_map)}, удалено={_fmt_roles(removed, names_map)}"
                    )
            # если снимок не запрошен — роли не трогаем и не логируем

            if per_user_changes:
                updated += 1
                # Лог пишем после коммита; здесь только собираем
                username_display = new_username or old_username
                change_logs.append((
                    "Пользователь: изменения применены",
                    f"Пользователь={username_display!r}; " + " | ".join(per_user_changes)
                ))

        _commit_with_retry()

        # Пишем логи только после успешного коммита
        for action, details in change_logs:
            log_to_db(user, action, details, entity_type="user")

        return updated

    except (IntegrityError, ValueError):
        db.session.rollback()
        raise


def bulk_delete_users(user: Any, user_ids_to_delete: List[int]) -> int:
    """
    Массовое удаление. Логируем КАЖДОЕ успешное удаление с подробностями (после commit).
    """
    if not user_ids_to_delete:
        return 0

    names_map = _roles_names_map()
    to_log: List[Tuple[str, str]] = []
    deleted = 0

    try:
        for uid in user_ids_to_delete:
            uid = int(uid)
            u = User.query.get(uid)
            if not u:
                continue

            details_before = (
                f"Пользователь={u.username!r}, email={u.email!r}, "
                f"Роли={_fmt_roles([r.id for r in u.roles], names_map)}"
            )
            db.session.delete(u)
            deleted += 1
            to_log.append(("Пользователь: удален", details_before))

        _commit_with_retry()

        for action, details in to_log:
            log_to_db(user, action, details, entity_type="user")

        return deleted

    except Exception:
        db.session.rollback()
        raise


def create_user(user: Any, username: str, email: str, raw_password: str,
                role_ids: Optional[List[int]] = None) -> User:
    """
    Создание нового пользователя. Логируем факт создания с назначенными ролями (после commit).
    """
    username = (username or "").strip()
    email = (email or "").strip()

    if not username or not email or not raw_password:
        raise ValueError("Необходимо указать username, email и пароль")

    if User.query.filter(User.username == username).first():
        raise ValueError(f"Имя '{username}' уже существует")

    if User.query.filter(User.email == email).first():
        raise ValueError(f"Email '{email}' уже существует")

    try:
        u = User(username=username, email=email, password_hash=generate_password_hash(raw_password))
        if role_ids:
            roles = Role.query.filter(Role.id.in_(role_ids)).all()
            u.roles = roles

        db.session.add(u)
        _commit_with_retry()

        names_map = _roles_names_map()
        details = (
            f"Пользователь={u.username!r}, email={u.email!r}, "
            f"Роли={_fmt_roles([r.id for r in u.roles], names_map)}"
        )
        log_to_db(user, "Пользователь: создан", details, entity_type="user", entity_id=u.id)
        return u

    except (IntegrityError, ValueError):
        db.session.rollback()
        raise
