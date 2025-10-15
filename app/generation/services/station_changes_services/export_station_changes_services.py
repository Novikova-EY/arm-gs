from io import BytesIO
from datetime import datetime
from config import Config

from flask import current_app
from xlsxwriter.utility import xl_col_to_name  # type: ignore

from app.generation.services.station_changes_services.station_changes_services import (
    get_station_changes_list_data,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_systems_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_map,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_map,
)
from app.common.services.get_services.stations.station_type_get_services import (
    get_station_type_list_full,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)


def _get_event_label(event_types: list[tuple[str, str]], code: str) -> str:
    for k, v in event_types:
        if k == code:
            return v
    return code


def export_station_changes_to_excel(
    user: str,
    filters: dict,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    show_totals: bool,
    data: dict | None = None,
):
    """Формирует Excel-файл со списком изменений мощности на странице station_changes_list
    с учетом текущих фильтров, округления и объединений ячеек как на экране.
    """
    # Загружаем все данные без пагинации, чтобы экспортировать всё отображаемое
    if data is None:
        data = get_station_changes_list_data(
            filters=filters,
            per_page="all",
            page=1,
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            show_all=True,
        )

    stations_grouped = data.get("stations_grouped", {})
    event_types = data.get("event_types", [])
    try:
        _st_list = get_station_type_list_full()
        station_type_names = {st.id: st.name for st in _st_list}
    except Exception:
        station_type_names = {}

    # Готовим книгу Excel (XlsxWriter удобен для объединений)
    output = BytesIO()
    try:
        import xlsxwriter  # type: ignore
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"xlsxwriter not available: {e}")
        raise

    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Приложение")

    # Стили

    title_format =  workbook.add_format({
        'font_name': 'Times New Roman',  # Устанавливаем шрифт
        'font_size': 24,                 # Размер шрифта 13pt
        'bold': True,
        'align': 'center',               # Выравнивание текста по левому краю
        'valign': 'vcenter',             # Выравнивание по центру по вертикали
        'text_wrap': True,               # Перенос строк и поддержка \n
    })

    subtitle_format = workbook.add_format({
        'font_name': 'Times New Roman',  # Устанавливаем шрифт
        'font_size': 24,                 # Размер шрифта 13pt
        'align': 'left',                 # Выравнивание текста по левому краю
        'valign': 'vcenter',             # Выравнивание по центру по вертикали
        'text_wrap': True,               # Перенос слов (разрыв строк)
    })

    text_center_format = workbook.add_format({
        'font_name': 'Times New Roman',  # Устанавливаем шрифт
        'font_size': 10,                 # Размер шрифта 10pt
        'align': 'center',               # Выравнивание текста по центру
        'valign': 'vcenter',             # Выравнивание по центру по вертикали
        'text_wrap': True,               # Перенос слов (разрыв строк)
        'border': 1                      # Границы ячейки
    })

    # Колонки (как на экране)
    static_headers = [
        "Субъект Российской Федерации",
        "Генерирующая компания",
        "Наименование",
        "Мероприятие",
        "Тип электростанции",
        "Станционный номер",
        "Тип генерирующего оборудования",
        "Вид топлива",
    ]
    # Формируем заголовки годов с " г.", для годов с признаком "текущий (оценка)" добавляем пометку
    year_headers = []
    year_feature_by_number = get_year_feature_dict()
    for y in range(start_year, end_year + 1):
        feature_name = year_feature_by_number.get(y)
        if feature_name == "текущий (оценка)":
            year_headers.append(f"{y} г.\n(ожидается, справочно)")
        else:
            year_headers.append(f"{y} г.")
    
    # Заголовок для столбца с суммой всех годов
    all_years_header = f"{start_year}–{end_year} гг."
    note_header = "Документ-основание"

    # Индексы колонок согласно static_headers
    subject_col = 0
    gen_company_col = 1
    station_name_col = 2
    event_col = 3
    station_type_col = 4
    machine_num_col = 5
    machine_name_col = 6
    fuel_col = 7

    # Вычисляем позиции колонок для заголовков
    years_start_col = len(static_headers)
    years_end_col = years_start_col + len(year_headers) - 1
    # Столбец с суммой всех годов
    all_years_col = years_end_col + 1
    # "Основание" — после столбца с суммой
    note_col = all_years_col + 1

    # Двухстрочная шапка таблицы после ваших заголовков
    # Табличная шапка начинается с 4-й строки Excel: sub_row=4
    sub_row = 4

    # Заголовки - динамическое определение последней колонки
    last_col_name = xl_col_to_name(note_col)
    
    worksheet.merge_range(
        f"A1:{last_col_name}1", 
        "ПРИЛОЖЕНИЕ Б", 
        title_format)
    worksheet.merge_range(
        f"A2:{last_col_name}2", 
        f"Перечень планируемых изменений установленной генерирующей мощности объектов по производству электрической энергии в ЕЭС России\nна период {start_year}–{end_year} годов", 
        title_format)
    worksheet.set_row(1, 62.25)
    worksheet.merge_range(
        f"A3:{last_col_name}3", 
        "",
        title_format)
    worksheet.set_row(2, 30.75)
    worksheet.merge_range(
        f"A4:{last_col_name}4",
        f"Таблица Б.1 – Перечень планируемых изменений установленной генерирующей мощности объектов по производству электрической энергии в ЕЭС России на период {start_year}–{end_year} годов, МВт",
        subtitle_format
    )
    worksheet.set_row(3, 47.25)

    # Шапка таблицы: конкретные заголовки
    for idx, name in enumerate(static_headers):
        worksheet.write(sub_row, idx, name, text_center_format)
    for i, y in enumerate(year_headers):
        worksheet.write(sub_row, years_start_col + i, y, text_center_format)
    # Добавляем столбец с суммой всех годов
    worksheet.write(sub_row, all_years_col, all_years_header, text_center_format)
    worksheet.write(sub_row, note_col, note_header, text_center_format)

    # Высота строки заголовков таблицы и фиксация панели (как в примере)
    worksheet.set_row(sub_row, 60)
    worksheet.freeze_panes(sub_row + 1, 0)

    # Ширины колонок приблизительно как на экране
    widths = [29, 25.86, 29.43, 23.43, 19.86, 17, 35.29, 15.71]
    for i, w in enumerate(widths):
        worksheet.set_column(i, i, w)
    # Годы
    for i in range(len(year_headers)):
        worksheet.set_column(years_start_col + i, years_start_col + i, 18)
    # Столбец с суммой всех годов
    worksheet.set_column(all_years_col, all_years_col, 15)
    # Столбец с основанием
    worksheet.set_column(note_col, note_col, 28)

    # Текущая строка для данных (начинаем с 7-й строки Excel)
    current_row = sub_row + 1

    # Вспомогательная функция для объединения ячеек (без падения при rowspan<=1)
    def merge_if_needed(r1: int, c1: int, r2: int, c2: int, value, text_center_format):
        if r2 > r1 or c2 > c1:
            worksheet.merge_range(r1, c1, r2, c2, value, text_center_format)
        else:
            worksheet.write(r1, c1, value, text_center_format)

    # Справочники имён и хелпер вывода итогов по событиям
    try:
        union_energy_system_names = get_union_energy_systems_map()
    except Exception:
        union_energy_system_names = {}

    try:
        regional_district_names = get_regional_districts_map()
    except Exception:
        regional_district_names = {}

    try:
        energy_system_type_names = get_energy_system_type_map()
    except Exception:
        energy_system_type_names = {}

    def write_combined_totals_block(label: str, events_years_map: dict, station_type_events_map: dict):
        """Пишет комбинированный блок итогов: для каждого мероприятия сначала 'Всего', 
        затем разбивка по типам станций"""
        nonlocal current_row
        
        # Определяем порядок типов станций: АЭС, ГЭС, ГАЭС, ТЭС, ВЭС, СЭС
        # Сначала создаем обратный маппинг: название -> id
        name_to_id = {}
        for st_id, st_name in station_type_names.items():
            name_to_id[st_name] = st_id
        
        # Порядок отображения типов станций
        station_order = ["АЭС", "ГЭС", "ГАЭС", "ТЭС", "ВЭС", "СЭС"]
        
        # Берем ВСЕ типы станций из порядка, даже если нет данных
        st_ids = []
        for st_name in station_order:
            st_id = name_to_id.get(st_name)
            if st_id:
                st_ids.append(st_id)
        
        # Для каждого мероприятия вычисляем количество строк (1 "Всего" + количество типов станций)
        rows_per_event = 1 + len(st_ids)  # 1 строка "Всего" + строки для каждого типа станции
        
        # Общее количество строк в блоке
        total_block_height = len(event_types) * rows_per_event
        block_start_row = current_row
        
        # Столбец 0 (Субъект РФ): название + ", всего" - объединить на высоту ВСЕГО блока
        merge_if_needed(block_start_row, subject_col, block_start_row + total_block_height - 1, subject_col, label + ", всего", text_center_format)
        
        # Столбец 1 (Генкомпания): объединить в пределах столбца на высоту ВСЕГО блока, прочерк
        merge_if_needed(block_start_row, gen_company_col, block_start_row + total_block_height - 1, gen_company_col, "—", text_center_format)
        
        # Столбец 2 (Наименование): объединить в пределах столбца на высоту ВСЕГО блока, прочерк
        merge_if_needed(block_start_row, station_name_col, block_start_row + total_block_height - 1, station_name_col, "—", text_center_format)
        
        # Столбец 5 (Станционный номер): объединить в пределах столбца на высоту ВСЕГО блока, прочерк
        merge_if_needed(block_start_row, machine_num_col, block_start_row + total_block_height - 1, machine_num_col, "—", text_center_format)
        
        # Столбец 6 (Тип генерирующего оборудования): объединить в пределах столбца на высоту ВСЕГО блока, прочерк
        merge_if_needed(block_start_row, machine_name_col, block_start_row + total_block_height - 1, machine_name_col, "—", text_center_format)
        
        # Столбец 7 (Вид топлива): объединить в пределах столбца на высоту ВСЕГО блока, прочерк
        merge_if_needed(block_start_row, fuel_col, block_start_row + total_block_height - 1, fuel_col, "—", text_center_format)
        
        # Обрабатываем каждое мероприятие
        for ev_code, ev_title in event_types:
            event_start_row = current_row
            event_label = _get_event_label(event_types, ev_code)
            
            # Первая строка: "Всего" для этого мероприятия
            # Столбец 3 (Мероприятие): пишем название мероприятия только в строке "Всего"
            worksheet.write(current_row, event_col, event_label, text_center_format)
            worksheet.write(current_row, station_type_col, "Всего", text_center_format)
            
            # Данные из events_years_map
            years_map_total = (events_years_map or {}).get(ev_code) or {}
            row_sum = 0
            for i, y in enumerate(range(start_year, end_year + 1)):
                val = years_map_total.get(y)
                display_val = val if val and val != 0 else None
                worksheet.write(current_row, years_start_col + i, display_val, text_center_format)
                if val is not None:
                    row_sum += val
            worksheet.write(current_row, all_years_col, row_sum if row_sum != 0 else None, text_center_format)
            worksheet.write(current_row, note_col, "", text_center_format)
            current_row += 1
            
            # Следующие строки: по каждому типу станции
            for st_id in st_ids:
                st_name = station_type_names.get(st_id, f"Тип станции {st_id}")
                
                # Столбец 3 (Мероприятие): пустая ячейка (название только в строке "Всего")
                worksheet.write(current_row, event_col, "", text_center_format)
                worksheet.write(current_row, station_type_col, st_name, text_center_format)
                
                # Данные из station_type_events_map
                years_map_st = (station_type_events_map or {}).get(st_id, {}).get(ev_code) or {}
                row_sum = 0
                for i, y in enumerate(range(start_year, end_year + 1)):
                    val = years_map_st.get(y)
                    display_val = val if val and val != 0 else None
                    worksheet.write(current_row, years_start_col + i, display_val, text_center_format)
                    if val is not None:
                        row_sum += val
                worksheet.write(current_row, all_years_col, row_sum if row_sum != 0 else None, text_center_format)
                worksheet.write(current_row, note_col, "", text_center_format)
                current_row += 1

    # Обход иерархии как в шаблоне
    for es_type_id, ues_group in stations_grouped.items():
        for ues_id, res_group in ues_group.items():
            for res_id, rd_group in res_group.items():
                for rd_id, eu_group in rd_group.items():
                    for eu_id, stations in eu_group.items():
                        for station in stations:
                            # Каждая виртуальная станция содержит machines с выставленными rowspan'ами
                            for machine in getattr(station, "machines", []):
                                if not getattr(machine, "powers_by_year", None):
                                    continue
                                first_row_for_machine = current_row

                                for idx_power, power_row in enumerate(machine.powers_by_year):
                                    # Субъект РФ (region_rowspan применяется один раз)
                                    if idx_power == 0 and getattr(machine, "region_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.region_rowspan - 1
                                        value = (
                                            station.regional_district.name_full
                                            if getattr(station, "regional_district", None)
                                            and getattr(station.regional_district, "name_full", None)
                                            else (
                                                station.regional_district.name
                                                if getattr(station, "regional_district", None)
                                                and getattr(station.regional_district, "name", None)
                                                else "Без субъекта"
                                            )
                                        )
                                        merge_if_needed(current_row, 0, r2, 0, value, text_center_format)

                                    # Генкомпания
                                    if idx_power == 0 and getattr(machine, "gen_company_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.gen_company_rowspan - 1
                                        value = machine.gen_company.name if getattr(machine, "gen_company", None) else "—"
                                        merge_if_needed(current_row, 1, r2, 1, value, text_center_format)

                                    # Станция
                                    if idx_power == 0 and getattr(machine, "station_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.station_rowspan - 1
                                        merge_if_needed(current_row, 2, r2, 2, getattr(station, "name", "—"), text_center_format)

                                    # Поля агрегата — один раз на агрегат, объединяем на machine.total_rows
                                    if idx_power == 0:
                                        r2 = first_row_for_machine + max(getattr(machine, "total_rows", 1) - 1, 0)
                                        # Станционный номер
                                        merge_if_needed(current_row, machine_num_col, r2, machine_num_col, getattr(machine, "machine_number", None), text_center_format)
                                        # Тип генерирующего оборудования
                                        merge_if_needed(current_row, machine_name_col, r2, machine_name_col, getattr(machine, "machine_name", None), text_center_format)
                                        # Тип станции
                                        station_type_name = getattr(getattr(machine, "station_type", None), "name", None) or "—"
                                        merge_if_needed(current_row, station_type_col, r2, station_type_col, station_type_name, text_center_format)

                                    # Топливо (по СО ЕЭС) — объединение на fuel_rowspan
                                    if idx_power == 0 and getattr(machine, "fuel_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.fuel_rowspan - 1
                                        merge_if_needed(current_row, fuel_col, r2, fuel_col, getattr(machine, "fuel_so", None) or "—", text_center_format)

                                    # Мероприятие — построчно
                                    worksheet.write(current_row, event_col, _get_event_label(event_types, power_row["event"]), text_center_format)

                                    # Годы — значение только в год power_row["year"], остальное пусто
                                    for i, y in enumerate(range(start_year, end_year + 1)):
                                        val = power_row["p_ust"] if power_row["year"] == y else None
                                        worksheet.write(current_row, years_start_col + i, val, text_center_format)

                                    # Столбец с суммой всех годов - построчно
                                    # В столбце суммы показываем значение p_ust для этой строки
                                    row_val = power_row.get("p_ust")
                                    worksheet.write(current_row, all_years_col, row_val if row_val and row_val != 0 else None, text_center_format)

                                    # Основание — один раз на агрегат, объединяем на высоту агрегата
                                    if idx_power == 0:
                                        r2 = first_row_for_machine + max(getattr(machine, "total_rows", 1) - 1, 0)
                                        merge_if_needed(current_row, note_col, r2, note_col, getattr(machine, "note", None), text_center_format)

                                    current_row += 1

                        # после всех станций в энергоузле — ничего не добавляем отдельно (итоги ниже, если включены)

                    # Итоги по субъекту РФ (события + по типам станций)
                    if show_totals:
                        rd_events_map = (
                            data.get("aggregate_changes_by_regional_districts", {})
                            .get("aggregated", {})
                            .get("p_ust", {})
                            .get(rd_id, {})
                        )
                        rd_by_station_map = (
                            data.get("aggregate_changes_regional_districts_by_station_types", {})
                            .get("aggregated", {})
                            .get("p_ust", {})
                            .get(rd_id, {})
                        )
                        rd_label = regional_district_names.get(rd_id, f"Субъект {rd_id}")
                        write_combined_totals_block(rd_label, rd_events_map, rd_by_station_map)

            # Итоги по ОЭС
            if show_totals:
                ues_events_map = (
                    data.get("aggregate_changes_by_union_energy_systems", {})
                    .get("aggregated", {})
                    .get("p_ust", {})
                    .get(ues_id, {})
                )
                # По типам станций и мероприятиям (для ОЭС)
                ues_by_station_map = (
                    data.get("aggregate_changes_union_energy_systems_by_station_types", {})
                    .get("aggregated", {})
                    .get("p_ust", {})
                    .get(ues_id, {})
                )
                ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                write_combined_totals_block(ues_label, ues_events_map, ues_by_station_map)

        # Итоги по типу энергосистемы
        if show_totals:
            es_events_map = (
                data.get("aggregate_changes_by_energy_system_types", {})
                .get("aggregated", {})
                .get("p_ust", {})
                .get(es_type_id, {})
            )
            es_label = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
            write_combined_totals_block(es_label, es_events_map, {})

    # Итоги по России
    if show_totals:
        total_events_map = (
            data.get("aggregate_changes_by_total_energy_system_types", {})
            .get("aggregated", {})
            .get("p_ust", {})
        )
        write_combined_totals_block("Россия", total_events_map, {})

    # Включаем автофильтры на строке заголовков по всей области таблицы
    try:
        worksheet.autofilter(sub_row, 0, max(current_row - 1, sub_row), note_col)
    except Exception:
        pass

    workbook.close()
    output.seek(0)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"station_changes_{ts}.xlsx"
    return filename, output


