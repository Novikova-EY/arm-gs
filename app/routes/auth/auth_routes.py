from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.auth_models import User, db, Role
from app.models.log_models import Log

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

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    log_to_db('Система', 'Попытка регистрации нового пользователя')
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()

            log_to_db('Система', f'Получены данные для регистрации: username={username}, email={email}')

            if User.query.filter_by(email=email).first():
                log_to_db('Система', f'Попытка регистрации с существующим email: {email}')
                flash('Пользователь с таким email уже существует.', 'warning')
                return redirect(url_for('auth.register'))

            user_role = Role.query.filter_by(name='Пользователь-гость').first()
            user = User(username=username, email=email, role=user_role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log_to_db(username, 'Успешная регистрация')
            flash('Регистрация прошла успешно. Вы можете войти.', 'success')
            return redirect(url_for('auth.login'))
    except Exception as e:
        log_to_db('Система', f'Ошибка во время регистрации: {e}')
        flash('Произошла ошибка при регистрации. Попробуйте снова.', 'danger')

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
