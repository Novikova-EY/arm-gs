from flask import render_template, Response, request, redirect, url_for, current_app, flash, session
from app import db
from app.models import Fo, Log
from . import app_bp
from io import BytesIO
import pandas as pd
from sqlalchemy import text
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length
from sqlalchemy.exc import IntegrityError

# Flask-WTF форма
class FoFilterForm(FlaskForm):
    name_filter = StringField("Название ФО", validators=[Length(max=100)], render_kw={"placeholder": "Введите название ФО"})
    fo_ids = HiddenField("ID")
    name = StringField("Наименование", validators=[Length(max=100)])
    fo_delete = HiddenField("Удалить")

# Функция для логирования
def log_to_db(username, action, details=None):
    log_entry = Log(username=username, action=action, details=details)
    db.session.add(log_entry)
    db.session.commit()

# Контроллер для отображения списка ФО
@app_bp.route("/fo", methods=['GET', 'POST'])
def fo_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ФО")
    form = FoFilterForm()

    try:
        # Фильтрация и сортировка
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)
        name_filter = request.args.get("name_filter", "").strip()
        sort_by = request.args.get("sort_by", "id")
        sort_dir = request.args.get("sort_dir", "asc")

        # Формирование запроса
        query = Fo.query
        if name_filter:
            query = query.filter(Fo.name.ilike(f"%{name_filter}%"))
        if sort_by == "name":
            query = query.order_by(Fo.name.desc() if sort_dir == "desc" else Fo.name.asc())
        else:
            query = query.order_by(Fo.id.desc() if sort_dir == "desc" else Fo.id.asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # POST-запрос для сохранения изменений
        if request.method == "POST":
            fo_ids = request.form.getlist("fo_ids[]")
            fo_names = request.form.getlist("fo_names[]")
            fo_delete = request.form.getlist("fo_delete[]")

            # Удаление записей
            for fo_id in fo_delete:
                fo_item = Fo.query.get(fo_id)
                if fo_item:
                    db.session.delete(fo_item)

            # Обновление записей
            for fo_id, fo_name in zip(fo_ids, fo_names):
                fo_item = Fo.query.get(fo_id)
                if fo_item:
                    # Проверка на дублирование
                    duplicate = Fo.query.filter(Fo.name == fo_name, Fo.id != fo_id).first()
                    if duplicate:
                        flash(f"Запись с именем '{fo_name}' уже существует и не была обновлена.", "warning")
                        log_to_db(user, "Ошибка дублирования", f"Имя: {fo_name}, ID: {fo_id}")
                        continue
                    fo_item.name = fo_name

            try:
                db.session.commit()
                flash("Изменения успешно сохранены.", "success")
            except IntegrityError as e:
                db.session.rollback()
                flash("Произошла ошибка сохранения данных. Проверьте записи на дублирование.", "danger")
                log_to_db(user, "Ошибка сохранения", f"Ошибка: {e}")

            return redirect(url_for("app_bp.fo_list", page=page, name_filter=name_filter))

        return render_template(
            "fo.html",
            form=form,
            fo_list=pagination.items,
            pagination=pagination,
            name_filter=name_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
            per_page=per_page
        )

    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка: {e}")
        flash("Произошла ошибка при обработке данных.", "danger")
        return redirect(url_for("app_bp.fo_list"))

# Контроллер для добавления нового ФО
@app_bp.route("/add_fo", methods=['GET', 'POST'])
def add_fo():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ФО")
    try:
        form = FoFilterForm()

        if form.validate_on_submit():
            new_fo = Fo(name=form.name.data)
            db.session.add(new_fo)
            try:
                db.session.commit()
                flash("Новая запись успешно добавлена.", "success")
                log_to_db(user, "Добавление записи", f"Имя: {form.name.data}")
                return redirect(url_for("app_bp.fo_list"))
            except IntegrityError:
                db.session.rollback()  # Откат изменений в случае ошибки
                flash("Ошибка: запись с таким именем уже существует.", "danger")
                log_to_db(user, "Ошибка дублирования", f"Имя: {form.name.data}")
        
        return render_template("fo_add.html", form=form)
    
    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка в функции добавления нового ФО: {e}")
        flash("Произошла ошибка при добавлении записи.", "danger")
        return redirect(url_for("app_bp.fo_list"))

# Контроллер для загузки ФО в базу данных из файла Excel
@app_bp.route("/import_fo_to_sql", methods=["POST"])
def import_fo_to_sql():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начата загрузка таблицы ФО в базу данных")
    try:
        if 'file' not in request.files:
            flash("Файл не найден.", "danger")
            log_to_db(user, "Ошибка импорта", "Файл не найден")
            return redirect(url_for("app_bp.fo_list"))

        file = request.files['file']

        if file.filename == '' or not allowed_file(file.filename):
            flash("Неверный формат файла.", "danger")
            log_to_db(user, "Ошибка импорта", "Неверный формат файла")
            return redirect(url_for("app_bp.fo_list"))

        log_to_db(user, "Загрузка файла", f"Имя файла: {file.filename}")

        data = pd.read_excel(file)

        if 'name' not in data.columns not in data.columns:
            flash("Неверный формат файла. Отсутствуют необходимые столбцы.", "danger")
            log_to_db(user, "Ошибка импорта", "Отсутствуют необходимые столбцы")
            return redirect(url_for("app_bp.fo_list"))

        db.session.query(Fo).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fo AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Fo(name=row['name']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        flash("Данные успешно импортированы.", "success")
        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return redirect(url_for("app_bp.fo_list"))

    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка в функции загрузки таблицы ФО в базу данных: {e}")
        flash(f"Ошибка при импорте данных: {e}", "danger")
        return redirect(url_for("app_bp.fo_list"))

# Контроллер для выгрузки ФО из базы данных в Excel
@app_bp.route("/export_fo_to_excel", methods=["GET"])
def export_fo_to_excel():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начата выгрузка таблицы ФО из базы данных")
    try:
        # Получение параметров фильтрации и сортировки из запроса
        name_filter = request.args.get("name_filter", "").strip()
        sort_by = request.args.get("sort_by", "id")
        sort_dir = request.args.get("sort_dir", "asc")

        log_to_db(user, "Параметры экспорта", f"name_filter={name_filter}, sort_by={sort_by}, sort_dir={sort_dir}")

        # Формирование запроса с учётом фильтрации и сортировки
        query = Fo.query
        if name_filter:
            query = query.filter(Fo.name.ilike(f"%{name_filter}%"))  # Фильтрация по имени

        if sort_by == "id":
            query = query.order_by(Fo.id.desc() if sort_dir == "desc" else Fo.id.asc())
        elif sort_by == "name":
            query = query.order_by(Fo.name.desc() if sort_dir == "desc" else Fo.name.asc()
            )

        # Выполнение запроса и сбор данных для выгрузки
        fo_items = query.all()
        data = [{
            "ID": o.id,
            "Наименование": o.name,
        } for o in fo_items]

        log_to_db(user, "Подготовка данных для экспорта таблицы ФО в Excel", f"Записей для экспорта: {len(data)}")

        # Подготовка данных к записи в Excel
        df = pd.DataFrame(data)

        # Создание Excel-файла
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="ФЩ")

        # Возврат файла в ответе
        output.seek(0)
        log_to_db(user, "Экспорт таблицы ФО в Excel завершён", f"Экспортировано записей: {len(data)}")
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=fo_data.xlsx"}
        )

    except Exception as e:
        # Логирование и уведомление об ошибке
        log_to_db(user, "Ошибка", f"Ошибка в функции выгрузки таблицы ФО в Excel: {e}")
        flash(f"Ошибка при экспорте данных: {e}", "danger")
        return redirect(url_for("app_bp.fo_list"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"xlsx", "xls"}
