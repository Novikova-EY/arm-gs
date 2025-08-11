from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.logs.models.logs_models import Log
from app.auth.models.auth_models import User, Role, user_roles as user_roles_table

# Функция логирования действий

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")

# Создание Blueprint для маршрутов авторизации

auth_bp = Blueprint('auth', __name__)

# Авторизация пользователя

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    log_to_db('Система', 'Попытка входа на страницу авторизации')
    try:
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            log_to_db('Система', f'Попытка входа с email: {email}')

            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                session['username'] = user.username
                log_to_db(user.username, 'Успешный вход в систему')
                flash('Вы успешно вошли.', 'success')
                return redirect(url_for('start.index'))
            else:
                log_to_db('Система', f'Неудачная попытка входа с email: {email}')
                flash('Неправильный email или пароль.', 'danger')
    except Exception as e:
        log_to_db('Система', f'Ошибка во время входа: {e}')
        flash('Произошла ошибка. Попробуйте снова.', 'danger')

    return render_template('login.html')

# Регистрация нового пользователя
# Рекомендуется: лог писать отдельной транзакцией
def log_to_db_safe(username, action, details=None):
    try:
        with db.engine.begin() as conn:
            conn.execute(
                # замените на вашу таблицу логов
                db.text('INSERT INTO "arm_gs".logs (timestamp, username, action, details) VALUES (now(), :u, :a, :d)'),
                {"u": username, "a": action, "d": details},
            )
    except Exception:
        pass  # не валим основной поток из‑за логов

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    log_to_db_safe('Система', 'Попытка регистрации нового пользователя')

    if request.method != 'POST':
        return render_template('register.html')

    username = (request.form.get('username') or '').strip()
    email    = (request.form.get('email') or '').strip()
    password = (request.form.get('password') or '').strip()

    log_to_db_safe('Система', f'Получены данные для регистрации: username={username}, email={email}')

    if not username or not email or not password:
        flash('Заполните все поля.', 'warning')
        return redirect(url_for('auth.register'))

    try:
        # уже существует?
        if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
            log_to_db_safe('Система', f'Попытка регистрации с существующим email: {email}')
            flash('Пользователь с таким email уже существует.', 'warning')
            return redirect(url_for('auth.register'))

        # get-or-create для роли «Пользователь‑гость»
        guest_role = db.session.execute(
            db.select(Role).filter_by(name='Пользователь-гость')
        ).scalar_one_or_none()

        if guest_role is None:
            guest_role = Role(name='Пользователь-гость')
            db.session.add(guest_role)
            db.session.flush()  # получим guest_role.id

        # создаём пользователя
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()      # получим user.id

        # привязываем роль (любой из вариантов):
        # Вариант 1: через M2M-таблицу напрямую
        db.session.execute(
            user_roles_table.insert().values(user_id=user.id, role_id=guest_role.id)
        )
        # Вариант 2 (проще): ORM
        # user.roles.append(guest_role)

        db.session.commit()

        log_to_db_safe(username, 'Успешная регистрация')
        flash('Регистрация прошла успешно. Вы можете войти.', 'success')
        return redirect(url_for('auth.login'))

    except IntegrityError as e:
        db.session.rollback()
        log_to_db_safe('Система', f'Ошибка целостности данных при регистрации: {e}')
        flash('Произошла ошибка при регистрации (конфликт данных). Попробуйте снова.', 'danger')
    except Exception as e:
        db.session.rollback()
        log_to_db_safe('Система', f'Неизвестная ошибка при регистрации: {e}')
        flash('Произошла непредвиденная ошибка при регистрации. Попробуйте позже.', 'danger')

    return render_template('register.html')

# Выход из учетной записи пользователя

@auth_bp.route('/logout')
@login_required
def logout():
    try:
        username = session.pop('username', 'Неизвестный пользователь')
        logout_user()
        log_to_db(username, 'Пользователь вышел из системы')
        flash('Вы успешно вышли.', 'success')
    except Exception as e:
        log_to_db('Система', f'Ошибка при выходе из системы: {e}')
        flash('Произошла ошибка при выходе. Попробуйте снова.', 'danger')
    return redirect(url_for('auth.login'))
