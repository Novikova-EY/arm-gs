import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, db, Role

# Настройка логирования для авторизации
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Авторизация пользователя
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    logger.info("Попытка входа в систему.")
    try:
        if request.method == 'POST':
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()
            logger.info(f"Получены данные для входа: email={email}")

            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                login_user(user)
                session['username'] = user.username
                logger.info(f"Успешный вход пользователя: {user.username}")
                flash('Вы успешно вошли.', 'success')
                return redirect(url_for('start.index'))
            else:
                logger.warning(f"Неудачная попытка входа с email: {email}")
                flash('Неправильный email или пароль.', 'danger')
    except Exception as e:
        logger.error(f"Ошибка во время входа: {e}")
        flash('Произошла ошибка. Попробуйте снова.', 'danger')

    return render_template('login.html')

# Регистрация нового пользователя
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    logger.info("Попытка регистрации нового пользователя.")
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '').strip()

            logger.info(f"Получены данные для регистрации: username={username}, email={email}")

            if User.query.filter_by(email=email).first():
                logger.warning(f"Попытка регистрации с существующим email: {email}")
                flash('Пользователь с таким email уже существует.', 'warning')
                return redirect(url_for('auth.register'))

            user_role = Role.query.filter_by(name='Пользователь-гость').first()
            user = User(username=username, email=email, role=user_role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            logger.info(f"Успешная регистрация пользователя: {username}")
            flash('Регистрация прошла успешно. Вы можете войти.', 'success')
            return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Ошибка во время регистрации: {e}")
        flash('Произошла ошибка при регистрации. Попробуйте снова.', 'danger')

    return render_template('register.html')

# Выход из учетной записи пользователя
@auth_bp.route('/logout')
@login_required
def logout():
    try:
        username = session.pop('username', 'Неизвестный пользователь')
        logout_user()
        logger.info(f"Пользователь {username} вышел из системы.")
        flash('Вы успешно вышли.', 'success')
    except Exception as e:
        logger.error(f"Ошибка при выходе из системы: {e}")
        flash('Произошла ошибка при выходе. Попробуйте снова.', 'danger')
    return redirect(url_for('auth.login'))
