from flask import render_template, Response, request, redirect, url_for, current_app, flash, session
from app import db
from app.models import Oes, OesType, Log
from . import app_bp
from io import BytesIO
import pandas as pd
from sqlalchemy import text
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length
from sqlalchemy.exc import IntegrityError

# Flask-WTF форма
class OesFilterForm(FlaskForm):
    name_filter = StringField("Название ОЭС", validators=[Length(max=100)], render_kw={"placeholder": "Введите название ОЭС"})
    oes_ids = HiddenField("ID")
    name = StringField("Наименование", validators=[Length(max=100)])
    oes_type = SelectField("Тип энергосистемы", coerce=int)
    oes_delete = HiddenField("Удалить")

# Функция для логирования
def log_to_db(username, action, details=None):
    log_entry = Log(username=username, action=action, details=details)
    db.session.add(log_entry)
    db.session.commit()

# Контроллер для отображения списка ОЭС
@app_bp.route("/oes", methods=['GET', 'POST'])
def oes_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница ОЭС")
    form = OesFilterForm()

    try:
        # Фильтрация и сортировка
        per_page = request.args.get("per_page", 10, type=int)
        page = request.args.get("page", 1, type=int)
        name_filter = request.args.get("name_filter", "").strip()
        sort_by = request.args.get("sort_by", "id")
        sort_dir = request.args.get("sort_dir", "asc")

        # Формирование запроса
        query = Oes.query
        if name_filter:
            query = query.filter(Oes.name.ilike(f"%{name_filter}%"))
        if sort_by == "name":
            query = query.order_by(Oes.name.desc() if sort_dir == "desc" else Oes.name.asc())
        elif sort_by == "oes_type":
            query = query.join(OesType, Oes.id_oes_type == OesType.id)
            query = query.order_by(OesType.name.desc() if sort_dir == "desc" else OesType.name.asc())
        else:
            query = query.order_by(Oes.id.desc() if sort_dir == "desc" else Oes.id.asc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        # POST-запрос для сохранения изменений
        if request.method == "POST":
            oes_ids = request.form.getlist("oes_ids[]")
            oes_names = request.form.getlist("oes_names[]")
            oes_types = request.form.getlist("oes_types[]")
            oes_delete = request.form.getlist("oes_delete[]")

            # Удаление записей
            for oes_id in oes_delete:
                oes_item = Oes.query.get(oes_id)
                if oes_item:
                    db.session.delete(oes_item)

            # Обновление записей
            for oes_id, oes_name, oes_type in zip(oes_ids, oes_names, oes_types):
                oes_item = Oes.query.get(oes_id)
                if oes_item:
                    # Проверка на дублирование
                    duplicate = Oes.query.filter(Oes.name == oes_name, Oes.id != oes_id).first()
                    if duplicate:
                        flash(f"Запись с именем '{oes_name}' уже существует и не была обновлена.", "warning")
                        log_to_db(user, "Ошибка дублирования", f"Имя: {oes_name}, ID: {oes_id}")
                        continue
                    oes_item.name = oes_name
                    oes_item.id_oes_type = int(oes_type)

            try:
                db.session.commit()
                flash("Изменения успешно сохранены.", "success")
            except IntegrityError as e:
                db.session.rollback()
                flash("Произошла ошибка сохранения данных. Проверьте записи на дублирование.", "danger")
                log_to_db(user, "Ошибка сохранения", f"Ошибка: {e}")

            return redirect(url_for("app_bp.oes_list", page=page, name_filter=name_filter))

        # Подготовка данных для формы
        oes_types = OesType.query.all()
        form.oes_type.choices = [(t.id, t.name) for t in oes_types]

        return render_template(
            "oes.html",
            form=form,
            oes_list=pagination.items,
            oes_types=form.oes_type.choices,
            pagination=pagination,
            name_filter=name_filter,
            sort_by=sort_by,
            sort_dir=sort_dir,
            per_page=per_page
        )

    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка: {e}")
        flash("Произошла ошибка при обработке данных.", "danger")
        return redirect(url_for("app_bp.oes_list"))

# Контроллер для добавления новой ОЭС
@app_bp.route("/add_oes", methods=['GET', 'POST'])
def add_oes():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница добавления ОЭС")
    try:
        form = OesFilterForm()
        oes_types = OesType.query.all()
        form.oes_type.choices = [(t.id, t.name) for t in oes_types]

        if form.validate_on_submit():
            new_oes = Oes(name=form.name.data, id_oes_type=form.oes_type.data)
            db.session.add(new_oes)
            try:
                db.session.commit()
                flash("Новая запись успешно добавлена.", "success")
                log_to_db(user, "Добавление записи", f"Имя: {form.name.data}")
                return redirect(url_for("app_bp.oes_list"))
            except IntegrityError:
                db.session.rollback()  # Откат изменений в случае ошибки
                flash("Ошибка: запись с таким именем уже существует.", "danger")
                log_to_db(user, "Ошибка дублирования", f"Имя: {form.name.data}")
        
        return render_template("oes_add.html", form=form, oes_types=oes_types)
    
    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка в функции добавления новой ОЭС: {e}")
        flash("Произошла ошибка при добавлении записи.", "danger")
        return redirect(url_for("app_bp.oes_list"))

# Контроллер для загузки ОЭС в базу данных из файла Excel
@app_bp.route("/import_oes_to_sql", methods=["POST"])
def import_oes_to_sql():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начата загрузка таблицы ОЭС в базу данных")
    try:
        if 'file' not in request.files:
            flash("Файл не найден.", "danger")
            log_to_db(user, "Ошибка импорта", "Файл не найден")
            return redirect(url_for("app_bp.oes_list"))

        file = request.files['file']

        if file.filename == '' or not allowed_file(file.filename):
            flash("Неверный формат файла.", "danger")
            log_to_db(user, "Ошибка импорта", "Неверный формат файла")
            return redirect(url_for("app_bp.oes_list"))

        log_to_db(user, "Загрузка файла", f"Имя файла: {file.filename}")

        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_oes_type' not in data.columns:
            flash("Неверный формат файла. Отсутствуют необходимые столбцы.", "danger")
            log_to_db(user, "Ошибка импорта", "Отсутствуют необходимые столбцы")
            return redirect(url_for("app_bp.oes_list"))

        db.session.query(Oes).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE oes AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Oes(name=row['name'], id_oes_type=row['id_oes_type']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        flash("Данные успешно импортированы.", "success")
        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return redirect(url_for("app_bp.oes_list"))

    except Exception as e:
        log_to_db(user, "Ошибка", f"Ошибка в функции загрузки таблицы ФО в базу данных: {e}")
        flash(f"Ошибка при импорте данных: {e}", "danger")
        return redirect(url_for("app_bp.oes_list"))

# Контроллер для выгрузки ОЭС из базы данных в Excel
@app_bp.route("/export_oes_to_excel", methods=["GET"])
def export_oes_to_excel():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начата выгрузка таблицы ОЭС из базы данных")
    try:
        # Получение параметров фильтрации и сортировки из запроса
        name_filter = request.args.get("name_filter", "").strip()
        sort_by = request.args.get("sort_by", "id")
        sort_dir = request.args.get("sort_dir", "asc")

        log_to_db(user, "Параметры экспорта", f"name_filter={name_filter}, sort_by={sort_by}, sort_dir={sort_dir}")

        # Формирование запроса с учётом фильтрации и сортировки
        query = Oes.query
        if name_filter:
            query = query.filter(Oes.name.ilike(f"%{name_filter}%"))  # Фильтрация по имени

        if sort_by == "id":
            query = query.order_by(Oes.id.desc() if sort_dir == "desc" else Oes.id.asc())
        elif sort_by == "name":
            query = query.order_by(Oes.name.desc() if sort_dir == "desc" else Oes.name.asc())
        elif sort_by == "oes_type":
            query = query.join(OesType, Oes.id_oes_type == OesType.id).order_by(
                OesType.name.desc() if sort_dir == "desc" else OesType.name.asc()
            )

        # Выполнение запроса и сбор данных для выгрузки
        oes_items = query.all()
        data = [{
            "ID": o.id,
            "Наименование": o.name,
            "Тип энергосистемы": o.oes_type.name if o.oes_type else "Не указан"
        } for o in oes_items]

        log_to_db(user, "Подготовка данных для экспорта таблицы ОЭС в Excel", f"Записей для экспорта: {len(data)}")

        # Подготовка данных к записи в Excel
        df = pd.DataFrame(data)

        # Создание Excel-файла
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="ОЭС")

        # Возврат файла в ответе
        output.seek(0)
        log_to_db(user, "Экспорт таблицы ОЭС в Excel завершён", f"Экспортировано записей: {len(data)}")
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=oes_data.xlsx"}
        )

    except Exception as e:
        # Логирование и уведомление об ошибке
        log_to_db(user, "Ошибка", f"Ошибка в функции выгрузки таблицы ОЭС в Excel: {e}")
        flash(f"Ошибка при экспорте данных: {e}", "danger")
        return redirect(url_for("app_bp.oes_list"))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"xlsx", "xls"}
