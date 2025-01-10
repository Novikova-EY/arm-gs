from flask import render_template, Response, request, redirect, url_for, current_app
from app import db
from app.models import Fo, Region
from . import app_bp
from io import BytesIO
import os
import pandas as pd
from sqlalchemy import text


@app_bp.route("/region")
def region_list():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    region_items = Region.query.order_by(Region.id.asc()).paginate(
        page=page, per_page=per_page
    )
    fo_items = Fo.query.order_by(Fo.id.asc()).all()
    return render_template("region.html", region_items=region_items, fo_items=fo_items)


@app_bp.route("/add_region", methods=["GET", "POST"])
def add_region():
    if request.method == "POST":
        region_name = request.form.get("name")
        fo_id = request.form.get("region_type")  # Получаем ID ФО
        new_region = Region(name=region_name, id_fo=fo_id)
        db.session.add(new_region)
        db.session.commit()
        return redirect(url_for("app_bp.region"))

    # Получаем список типов энергосистем для выпадающего списка
    fo_items = Fo.query.order_by(Fo.id.asc()).all()
    return render_template("region_add.html", fo_items=fo_items)


@app_bp.route("/update_region", methods=["POST"])
def update_region():
    region_ids = request.form.getlist("region_ids[]")
    region_names = request.form.getlist("region_names[]")
    fo_ids = request.form.getlist("fo_ids[]")  # Получение id ФО
    region_delete_ids = request.form.getlist("region_delete[]")

    for region_id, region_name, fo_id in zip(region_ids, region_names, fo_ids):
        region = db.session.get(Region, region_id)
        if region:
            region.name = region_name
            region.id_fo = int(fo_id) if fo_id.isdigit() else None
            db.session.add(region)

    for region_id in region_delete_ids:
        region_to_delete = db.session.get(Region, region_id)
        if region_to_delete:
            db.session.delete(region_to_delete)

    db.session.commit()
    return redirect(url_for("app_bp.region"))


# Функция для проверки расширения файла
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


@app_bp.route("/import_region_to_sql", methods=["POST"])
def import_region_to_sql():
    if "file" not in request.files:
        return "Нет файла в запросе", 400

    file = request.files["file"]

    if file.filename == "":
        return "Файл не выбран", 400

    if file and allowed_file(file.filename):
        # Сохраняем файл в папке загрузки
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], file.filename)
        file.save(filepath)

        try:
            # Чтение данных из Excel
            data = pd.read_excel(filepath)

            # Проверка наличия столбца 'name'
            if "name" not in data.columns:
                return "Отсутствует столбец 'name' в Excel файле", 400

            # Очистка таблицы перед загрузкой
            db.session.query(Region).delete()
            db.session.commit()

            # Сброс автоинкремента в MySQL
            db.session.execute(text("ALTER TABLE region AUTO_INCREMENT = 1"))
            db.session.commit()

            # Загрузка данных в базу данных
            for index, row in data.iterrows():
                new_region = Region(
                    name=row["name"], id_fo=row["id_fo"]
                )  # Создаем новый объект модели Fo
                db.session.add(new_region)  # Добавляем объект в сессию

            db.session.commit()  # Подтверждаем изменения в базе данных
            return redirect(url_for("app_bp.region"))

        except Exception as e:
            return f"Произошла ошибка при обработке файла: {str(e)}", 500
    else:
        return "Неверный формат файла", 400


@app_bp.route("/export_region_to_excel", methods=["GET"])
def export_region_to_excel():
    try:
        # Получаем данные из базы данных
        region_items = db.session.query(Region).order_by(Region.id.asc()).all()

        # Преобразуем данные в формат pandas DataFrame
        data = [
            {
                "ID": region.id,
                "Наименование": region.name,
                "ФО": region.fo.name if region.fo else "Не указан",
            }
            for region in region_items
        ]
        df = pd.DataFrame(data)

        # Создаем Excel-файл в памяти
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Субъекты РФ")

            # Получаем доступ к объекту workbook и worksheet
            workbook = writer.book
            worksheet = writer.sheets["Субъекты РФ"]

            # Форматирование
            header_format = workbook.add_format(
                {
                    "bold": True,
                    "bg_color": "#F7F7F7",
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }
            )

            cell_format = workbook.add_format(
                {"border": 1, "align": "center", "valign": "vcenter"}
            )

            # Применяем форматирование заголовков
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Применяем форматирование к данным
            for row_num, row_data in enumerate(df.values, start=1):
                for col_num, cell_data in enumerate(row_data):
                    worksheet.write(row_num, col_num, cell_data, cell_format)

            # Настройка ширины столбцов по содержимому
            for col_num, col_name in enumerate(df.columns.values):
                column_len = max(
                    df[col_name].astype(str).apply(len).max(), len(col_name)
                )
                worksheet.set_column(col_num, col_num, column_len)

        # Перемещаемся в начало файла
        output.seek(0)

        # Возвращаем файл пользователю
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment;filename=region_data.xlsx"},
        )
    except Exception as e:
        return f"Произошла ошибка при экспорте: {e}", 500
