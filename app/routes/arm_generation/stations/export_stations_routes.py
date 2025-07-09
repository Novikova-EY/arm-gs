from . import station_bp
from config import Config
from zipfile import ZipFile
from io import BytesIO
from datetime import datetime, date
from flask import request, send_file
from app.services.logging_services.logging_service import log_to_db
from flask import (
    request, redirect, url_for, flash, session, current_app, send_file
)
from app.services.station_services.station_services import (
    get_station_list_data
)
from app.services.station_services.filters_services import (
    extract_filters_from_args
)
from app.services.station_services.export_station_services import (
    export_station_sipr_ees_application_2_service, 
    generate_excel_export_with_all_totals,
)


@station_bp.route('/export_station_sipr_ees_application_2', methods=['GET'])
def export_station_sipr_ees_application_2_routes():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    filters = {
        key: request.args.get(key)
        for key in [
            'energy_system_type_filter', 'union_energy_system_filter', 
            'regional_energy_system_filter', 'federal_district_filter', 
            'regional_district_filter'
        ]
    }

    # Фильтруем None-значения, чтобы `url_for()` не получил их
    filters = {k: v for k, v in filters.items() if v}


    try:
        # Получение данных для экспорта
        excel_files = export_station_sipr_ees_application_2_service(user, filters)

        # Проверка наличия данных
        if not excel_files:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("station_bp.station_list"))

        # Если возвращён один файл, отправляем его напрямую
        if isinstance(excel_files, tuple):
            file_name, file_obj = excel_files
            return send_file(
                file_obj,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                as_attachment=True,
                download_name=file_name
            )

        # Если файлов несколько, создаём ZIP-архив
        zip_buffer = BytesIO()
        with ZipFile(zip_buffer, 'w') as zip_file:
            for file_name, file_obj in excel_files:
                zip_file.writestr(file_name, file_obj.getvalue())

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"Экспорт_станций_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )

    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        print(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("station_bp.station_list", **filters))


@station_bp.route('/export_station_full', methods=['GET'])
def export_station_full_routes():
    filters = extract_filters_from_args(request.args)
    start_year = int(request.args.get("start_year", Config.START_YEAR))
    end_year = int(request.args.get("end_year", Config.END_YEAR))
    rounding_digits = request.args.get("rounding_digits", "1")
    per_page = request.args.get("per_page", "all")
    show_p_ogr = request.args.get("show_p_ogr") == "1"
    show_p_rasp = request.args.get("show_p_rasp") == "1"

    try:
        rounding_digits = int(rounding_digits)
        if rounding_digits == 0:
            rounding_digits = None
    except (ValueError, TypeError):
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=None,
        page=1,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
    )

    rows = data["rows"]

    excel_file = generate_excel_export_with_all_totals(
        data=data,
        rows=rows,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stations_export_{timestamp}.xlsx"

    return send_file(
        excel_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

from io import BytesIO
import pandas as pd
from app.services.logging_services.logging_service import log_to_db
from app.services.station_services.station_changes_services import (
        get_filtered_stations
)

def export_station_list_to_excel(user, filters=None):
    """Экспортирует данные электростанций в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_filtered_stations(**filters)
    station_list = query.all()

    # Собираем уникальные компании для каждой станции
    for station in station_list:
        gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
        station.gen_companies = "\n".join(gen_companies)

    # Получаем список всех годов
    all_years = list(range(2024, 2032))

    data = []

    # Получаем название **региональной энергосистемы** для субъекта РФ
    regional_energy_system_name = ""
    if station.regional_district and station.regional_district.regional_energy_systems:
        regional_energy_system_name = ", ".join(
            res.name_full for res in station.regional_district.regional_energy_systems
        )

    # Добавляем строку с региональной энергосистемой
    data.append({
        "Электростанция": regional_energy_system_name,
        "Генерирующая компания": "",
        "Станционный номер": "",
        "Тип генерирующего оборудования": "",
        "Вид топлива": "",
        **{year: "" for year in all_years},
        "Примечание": "",
    })

    for station in station_list:
        station_total_p_ust = {year: 0 for year in all_years}  # Словарь для суммарной мощности
            
        # Добавляем строку с названием электростанции
        data.append({
            "Электростанция": station.name,
            "Генерирующая компания": station.gen_companies,
            "Станционный номер": "",
            "Тип генерирующего оборудования": "",
            "Вид топлива": "",
            **{year: "" for year in all_years},
            "Примечание": "",
        })


        for machine in station.machines:
            row = {
                "Электростанция": machine.machine_group,
                "Генерирующая компания": "",
                "Станционный номер": machine.machine_number,
                "Тип генерирующего оборудования": machine.machine_name,
                "Вид топлива": "",
                **{year: "" for year in all_years},
                "Примечание": machine.note,
            }

            # Добавляем мощности по годам
            for year in all_years:
                power_value = next(
                    (p.p_ust for p in machine.machine_powers if p.year.number == year), 0
                )
                row[year] = f"{power_value:.1f}".replace('.', ',')
                station_total_p_ust[year] += power_value  # Считаем суммарную мощность

            data.append(row)

        # 🔹 Добавляем строку "Установленная мощность, всего" по станции
        total_row = {
            "Электростанция": "Установленная мощность, всего",
            "Генерирующая компания": "",
            "Станционный номер": "–",
            "Тип генерирующего оборудования": "–",
            "Вид топлива": "–",
            **{year: f"{station_total_p_ust[year]:.1f}".replace('.', ',') for year in all_years},
            "Примечание": "",
        }

        data.append(total_row)

    log_to_db(user, "Подготовка данных для экспорта электростанций в Excel", f"Записей для экспорта: {len(data)}")

    df = pd.DataFrame(data)
    df = df.fillna("")

    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, header=False, startrow=6, sheet_name="Приложение А")
        workbook = writer.book
        workbook.use_nan_inf_to_errors = True
        worksheet = writer.sheets["Приложение А"]

        title_format =  workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 13,                 # Размер шрифта 13pt
            'bold': True,
            'align': 'center',               # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
        })

        subtitle_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 13,                 # Размер шрифта 13pt
            'align': 'left',                 # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
        })

        text_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 10,                 # Размер шрифта 10pt
            'align': 'left',                 # Выравнивание текста по левому краю
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
            'border': 1                      # Границы ячейки
        })

        text_center_format = workbook.add_format({
            'font_name': 'Times New Roman',  # Устанавливаем шрифт
            'font_size': 10,                 # Размер шрифта 10pt
            'align': 'center',               # Выравнивание текста по центру
            'valign': 'vcenter',             # Выравнивание по центру по вертикали
            'text_wrap': True,               # Перенос слов (разрыв строк)
            'border': 1                      # Границы ячейки
        })


        # Заголовки
        worksheet.merge_range("A1:N1", "ПРИЛОЖЕНИЕ А", title_format)
        worksheet.merge_range("A2:N2", "Перечень электростанций, действующих и планируемых к сооружению, расширению, модернизации и выводу из эксплуатации", title_format)
        worksheet.merge_range("A3:N3", "", title_format)
        worksheet.merge_range("A4:N4", "Таблица А.1 – Перечень действующих электростанций, с указанием состава генерирующего оборудования и планов по выводу из эксплуатации, реконструкции (модернизации или перемаркировке), вводу в эксплуатацию генерирующего оборудования в период до 2030 года", subtitle_format)
        worksheet.set_row(3, 42)

       # Шапка таблицы
        col_names = ["Электростанция", "Генерирующая компания", "Станционный номер",
                    "Тип генерирующего оборудования", "Вид топлива", "Примечание"]
        num_cols = len(col_names) - 1  # Без "Примечание"

        # Объединяем и форматируем первый столбец (первая колонка шапки)
        worksheet.merge_range(4, 0, 5, 0, col_names[0], text_format)

        # Объединяем и форматируем остальные столбцы
        for col_num in range(1, num_cols):  # Начинаем с 1, чтобы не дублировать первый столбец
            worksheet.merge_range(4, col_num, 5, col_num, col_names[col_num], text_center_format)

        # Первая строка над мощностями
        worksheet.merge_range(4, num_cols, 4, num_cols + len(all_years) - 1, "Установленная мощность (МВт)", text_center_format)

        # ✅ Заменяем первый год на "По состоянию на 01.01.<год>"
        first_year = all_years[0]  # Берем первый год из списка
        year_headers = ["По состоянию на 01.01.{}".format(first_year)] + [str(year) for year in all_years[1:]]

        # Вторая строка - годы
        for idx, year in enumerate(year_headers):
            col_num = num_cols + idx
            worksheet.write(5, col_num, year, text_center_format)

        # ✅ Устанавливаем особую ширину для первого года
        first_year_col_idx = num_cols  # Столбец первого года
        worksheet.set_column(first_year_col_idx, first_year_col_idx, 12.86, text_center_format)

        # ✅ Устанавливаем стандартную ширину для остальных годов
        for idx in range(1, len(all_years)):  # Пропускаем первый год
            col_num = num_cols + idx
            worksheet.set_column(col_num, col_num, 8, text_center_format)

        # Добавляем "Примечание" в 1 строке
        worksheet.merge_range(4, num_cols + len(all_years), 5, num_cols + len(all_years), "Примечание", text_center_format)

# Определяем индекс нужного столбца
        station_column_name = "Электростанция"
        gen_company_column_name = "Генерирующая компания"
        machine_number_column_name = "Станционный номер"
        machine_name_column_name = "Тип генерирующего оборудования"
        fuel_type_name = "Вид топлива"
        note_column_name = "Примечание"

        station_col_idx = df.columns.get_loc(station_column_name)
        gen_company_col_idx = df.columns.get_loc(gen_company_column_name)
        machine_number_col_idx = df.columns.get_loc(machine_number_column_name)
        machine_name_col_idx = df.columns.get_loc(machine_name_column_name)
        fuel_type_col_idx = df.columns.get_loc(fuel_type_name)
        p_ust_col_idxs = {year: df.columns.get_loc(year) for year in all_years}
        note_column_col_idx = df.columns.get_loc(note_column_name)

        # Применяем ширину (217 пикселей ≈ 30 Excel ширина) и формат только к этому столбцу
        worksheet.set_column(station_col_idx, station_col_idx, 30.29, text_format)
        worksheet.set_column(gen_company_col_idx, gen_company_col_idx, 17, text_center_format)
        worksheet.set_column(machine_number_col_idx, machine_number_col_idx, 12, text_center_format)
        worksheet.set_column(machine_name_col_idx, machine_name_col_idx, 20.86, text_center_format)
        worksheet.set_column(fuel_type_col_idx, fuel_type_col_idx, 11.29, text_center_format)
        
        worksheet.set_column(note_column_col_idx, note_column_col_idx, 28.71, text_format)

        # Определяем диапазон объединения (все столбцы)
        start_col = 0
        end_col = len(df.columns) - 1  # Последний столбец

        # Найти индекс строки, где находится региональная энергосистема (первое её появление в data)
        regional_row_idx = next(i for i, row in enumerate(data) if row["Электростанция"] == regional_energy_system_name)

        # Объединяем ячейки в Excel
        worksheet.merge_range(regional_row_idx + 6, start_col, regional_row_idx + 6, end_col,  # +6 из-за заголовков
                            regional_energy_system_name, text_format)

        # Определяем последнюю заполненную строку
        last_row = len(df) + 6  # +5 из-за заголовков

        # Определяем последний используемый столбец
        last_col = len(df.columns)

        # Создаем пустой стиль (без границ, выравнивания и других атрибутов)
        empty_format = workbook.add_format()

        # Снимаем форматирование с пустых строк после таблицы
        for row_num in range(last_row, 1000):  # 1000 - большое число, можно сделать динамическим
            worksheet.set_row(row_num, None, empty_format)

        # Снимаем форматирование с пустых столбцов после таблицы
        for col_num in range(last_col + 1, 50):  # 50 - запасное число столбцов
            worksheet.set_column(col_num, col_num, None, empty_format)


    output.seek(0)

    log_to_db(user, "Экспорт завершён", f"Экспортировано записей: {len(data)}")
    return output


