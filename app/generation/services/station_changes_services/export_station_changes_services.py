from io import BytesIO
from datetime import datetime
from config import Config
import re

from flask import current_app
from xlsxwriter.utility import xl_col_to_name  # type: ignore

from app.generation.services.station_changes_services.station_changes_services import (
    get_station_changes_list_data,
)
from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_systems_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_list,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_map,
)
from app.common.services.get_services.stations.station_type_get_services import (
    get_station_type_list_full,
)
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_year_feature_dict,
)


def _get_event_label(event_types: list[tuple[str, str]], code: str) -> str:
    for k, v in event_types:
        if k == code:
            return v
    return code


def _extract_document_names(text: str) -> str:
    """
    Извлекает названия документов из токенов формата [DOC:id:название].
    Возвращает только текст названий без ID, разделенный запятыми.
    Пример: "[DOC:5:Приказ №123], [DOC:7:Распоряжение №456]" -> "Приказ №123, Распоряжение №456"
    """
    if not text:
        return ""
    
    # Паттерн для поиска ссылок на документы: [DOC:id:название]
    pattern = r'\[DOC:\d+:([^\]]+)\]'
    
    # Находим все совпадения и извлекаем только названия (группа 1)
    matches = re.findall(pattern, text)
    
    if matches:
        # Объединяем названия через запятую
        return ", ".join(matches)
    
    # Если токенов нет, возвращаем исходный текст (на случай, если это обычный текст)
    return text


def _get_sum_years_and_header(start_year: int, end_year: int, current_year: int | None) -> tuple[list[int], str]:
    """Возвращает список лет для суммирования и заголовок столбца суммы.

    Требование: сумма должна учитывать все годы из диапазона, кроме текущего года.
    Пример: для 2025–2031 (текущий 2025) суммируем 2026–2031.
    """
    years = list(range(start_year, end_year + 1))

    # Если текущий год не определён или не входит в диапазон — суммируем всё как есть.
    if current_year is None or current_year < start_year or current_year > end_year:
        return years, f"{start_year}–{end_year} гг."

    sum_years = [y for y in years if y != current_year]

    # Если текущий год — первый в диапазоне, делаем заголовок как в форме СиПР (со следующего года).
    if current_year == start_year and start_year + 1 <= end_year:
        return sum_years, f"{start_year + 1}–{end_year} гг."

    # Иначе оставляем исходный диапазон, но явно помечаем исключение текущего года.
    return sum_years, f"{start_year}–{end_year} гг.\n(без {current_year} г.)"


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
    current_db_version_id = get_current_db_version_id()

    # Сбрасываем кэши справочников, чтобы загрузить актуальные данные для текущей версии БД
    from app.common.services.get_services.stations.station_type_get_services import (
        get_station_type_list_full,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
    )
    
    cache_functions = [
        get_station_type_list_full,
        get_union_energy_system_list_full,
        get_energy_system_type_list_full,
    ]
    for func in cache_functions:
        if hasattr(func, "cache_clear"):
            func.cache_clear()

    # Загружаем все данные без пагинации, чтобы экспортировать всё отображаемое
    if (
        data is None
        or data.get("database_version_id") != current_db_version_id
    ):
        data = get_station_changes_list_data(
            filters=filters,
            per_page="all",
            page=1,
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            show_all=True,
        )
    if isinstance(data, dict):
        data.setdefault("database_version_id", current_db_version_id)

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
    
    # Список лет для суммирования в колонке "Итого": только годы с признаком "план"
    year_features = get_year_feature_dict() or {}
    plan_years = [
        y for y in range(start_year, end_year + 1)
        if str(year_features.get(y, "")).strip().lower() == "план"
    ]
    sum_years = plan_years
    if plan_years:
        all_years_header = f"{plan_years[0]}–{plan_years[-1]} гг.\n"
    else:
        all_years_header = ""
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

    # Для "обычной" выгрузки (кнопка «Экспорт изменений в Excel») выводим только таблицу,
    # без строк заголовков сверху.
    sub_row = 0

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
    # Столбец с основанием — скрываем в форме «Приложение 2 (Россия)»
    worksheet.set_column(note_col, note_col, 28, None, {"hidden": True})

    # Текущая строка для данных (сразу после шапки таблицы)
    current_row = sub_row + 1
    # Отслеживаем последнюю объединённую строку ПО КАЖДОМУ СТОЛБЦУ (а не глобально),
    # чтобы не "сдвигать" данные вниз из-за merge в других столбцах.
    max_merged_row_by_col: dict[int, int] = {}

    # Вспомогательная функция для объединения ячеек (без падения при rowspan<=1)
    def merge_if_needed(r1: int, c1: int, r2: int, c2: int, value, text_center_format):
        if r2 > r1 or c2 > c1:
            worksheet.merge_range(r1, c1, r2, c2, value, text_center_format)
            # Запоминаем последнюю объединённую строку для каждого затронутого столбца
            for c in range(c1, c2 + 1):
                prev = max_merged_row_by_col.get(c, -1)
                if r2 > prev:
                    max_merged_row_by_col[c] = r2
        else:
            worksheet.write(r1, c1, value, text_center_format)

    #  Справочники имён и хелпер вывода итогов по событиям
    try:
        union_energy_system_names = get_union_energy_systems_map()
    except Exception:
        union_energy_system_names = {}

    # Энергоузлы (для спец-логики ОЭС "ТИТЭС Сибири")
    try:
        from app.common.services.get_services.energy_systems.energy_unit_get_services import get_energy_unit_list_full
        energy_unit_list = get_energy_unit_list_full() or []
        energy_unit_names = {eu.id: eu.name for eu in energy_unit_list if getattr(eu, "id", None) is not None}
    except Exception:
        energy_unit_names = {}

    try:
        regional_district_names = get_regional_districts_map()
    except Exception:
        regional_district_names = {}

    # Родительный падеж субъектов РФ (для "Итого по ...")
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_rp = {rd.id: getattr(rd, "name_rp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_rp = {}
    
    # Наименование субъекта (name_dp) для итоговых строк вида "Итого по субъекту ..."
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_dp = {rd.id: getattr(rd, "name_dp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_dp = {}

    try:
        energy_system_type_names = get_energy_system_type_map()
    except Exception:
        energy_system_type_names = {}

    # Агрегаты по синхронным зонам на веб-странице формируются на этапе сборки template-context,
    # а в export у нас "сырые" data из get_station_changes_list_data. Поэтому считаем агрегаты здесь.
    try:
        from app.generation.services.station_changes_services.station_changes_services import (
            build_synchronous_area_aggregates,
        )
        sa_aggregates = build_synchronous_area_aggregates(data) or {}
        synchronous_areas_yearly_p_ust = sa_aggregates.get("synchronous_areas_yearly_p_ust", {}) or {}
        synchronous_areas_by_station_types_yearly_p_ust = sa_aggregates.get("synchronous_areas_by_station_types_yearly_p_ust", {}) or {}
    except Exception:
        synchronous_areas_yearly_p_ust = {}
        synchronous_areas_by_station_types_yearly_p_ust = {}

    def write_combined_totals_block(label: str, events_years_map: dict, station_type_events_map: dict):
        """Пишет комбинированный блок итогов: для каждого мероприятия сначала 'Всего', 
        затем разбивка по типам станций"""
        nonlocal current_row
        
        # Начинаем новый итоговый блок так, чтобы он не попадал внутрь merge_range
        # в СВОИХ столбцах (B/C/F/G/H/A). Это предотвращает OverlappingRange и не ломает разметку.
        block_cols = [subject_col, gen_company_col, station_name_col, machine_num_col, machine_name_col, fuel_col]
        safe_start = current_row
        for c in block_cols:
            safe_start = max(safe_start, max_merged_row_by_col.get(c, -1) + 1)
        current_row = safe_start
        
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
        
        # Столбец 0: уже сформированная подпись блока (без автодобавления ", всего")
        merge_if_needed(block_start_row, subject_col, block_start_row + total_block_height - 1, subject_col, label, text_center_format)
        
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
                if val is not None and y in sum_years:
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
                    if val is not None and y in sum_years:
                        row_sum += val
                worksheet.write(current_row, all_years_col, row_sum if row_sum != 0 else None, text_center_format)
                worksheet.write(current_row, note_col, "", text_center_format)
                current_row += 1

        # Важно: объединения ячеек для блока рассчитаны на total_block_height строк.
        # Даже если по каким-то причинам фактически было записано меньше строк,
        # нужно сдвинуть current_row до конца блока, иначе следующий merge_range может пересечься
        # с текущим (xlsxwriter.exceptions.OverlappingRange).
        expected_end = block_start_row + total_block_height
        if current_row < expected_end:
            current_row = expected_end

    # Обход иерархии как в шаблоне (тип энергосистемы -> (синхронная зона|энергозона) -> ОЭС -> РЭС -> субъект)
    # Для объединенного итога по всем ТИТЭС
    tites_ids = [
        est_id for est_id, name in energy_system_type_names.items()
        if name and "титэс" in str(name).lower().replace(" ", "")
    ]
    tites_events_map = {}
    tites_by_station_map = {}

    for es_type_id, es_group in stations_grouped.items():
        # Для ТИТЭС второй уровень (синхронные зоны) на вебе не используется:
        # для ветки ТИТЭС нет итогов по ОЭС и по синхронным зонам, только по субъектам.
        es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
        is_tites_es = "титэс" in str(es_name).lower().replace(" ", "")
        for sa_id, sa_group in es_group.items():
            # Спец-логика как на веб: для Калининградской синхронной зоны
            # - не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада)
            # - после станций выводим "Итого по Санкт-Петербургу/Ленобласти..." как обычно,
            #   но для Калининграда выводим "Итого по Калининградской области" отдельно внизу,
            #   затем "Итого по синхронной зоне Калининградской области"
            sa_names = data.get("synchronous_area_names", {}) or {}
            sa_name = sa_names.get(sa_id, "")
            is_kaliningrad_sa = "калининград" in str(sa_name).lower()

            # Собираем список субъектов (rd_id) внутри текущей синхронной зоны (для калининградской спец-логики)
            sa_rd_ids: list[int] = []
            for _ues_id, _ues_group in (sa_group or {}).items():
                for _res_id, _res_group in (_ues_group or {}).items():
                    for _rd_id in (_res_group or {}).keys():
                        try:
                            _rid = int(_rd_id)
                        except Exception:
                            continue
                        if _rid != 0 and _rid not in sa_rd_ids:
                            sa_rd_ids.append(_rid)

            for ues_id, rd_group in sa_group.items():
                for res_id, res_group in rd_group.items():
                    for rd_id, stations in res_group.items():
                        for station in stations:
                            # Каждая виртуальная станция содержит machines с выставленными rowspan'ами
                            for machine in getattr(station, "machines", []):
                                if not getattr(machine, "powers_by_year", None):
                                    continue

                                first_row_for_machine = current_row

                                # Сумма "Итого" по план-годам отдельно для каждого мероприятия
                                event_sum_map = {}
                                for _p in machine.powers_by_year:
                                    if not isinstance(_p, dict):
                                        continue
                                    _ev = _p.get("event")
                                    _y = _p.get("year")
                                    _v = _p.get("p_ust")
                                    if _y in sum_years and _ev:
                                        event_sum_map[_ev] = (event_sum_map.get(_ev) or 0) + (_v or 0)
                                seen_events = set()

                                for idx_power, power_row in enumerate(machine.powers_by_year):
                                    # Субъект РФ (region_rowspan применяется один раз)
                                    if idx_power == 0 and getattr(machine, "region_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.region_rowspan - 1
                                        ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                                        if "титэс сибири" in str(ues_label).lower():
                                            eu_id = getattr(station, "id_energy_unit", None) or 0
                                            value = energy_unit_names.get(eu_id, "Без энергоузла" if not eu_id else f"Энергоузел {eu_id}")
                                        else:
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
                                        station_type_obj = getattr(station, "station_type", None)
                                        station_type_name = getattr(station_type_obj, "name", None)
                                        if not station_type_name:
                                            st_id = getattr(station, "id_station_type", None)
                                            station_type_name = station_type_names.get(st_id) if st_id else None
                                        station_type_name = station_type_name or "—"
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

                                    # Столбец "Итого" — по каждому мероприятию, без объединений (пишем один раз на мероприятие)
                                    ev_code = power_row.get("event")
                                    if ev_code and ev_code not in seen_events:
                                        seen_events.add(ev_code)
                                        ev_sum = event_sum_map.get(ev_code)
                                        worksheet.write(current_row, all_years_col, ev_sum if ev_sum and ev_sum != 0 else None, text_center_format)
                                    else:
                                        worksheet.write(current_row, all_years_col, None, text_center_format)

                                    # Основание — один раз на агрегат, объединяем на высоту агрегата
                                    if idx_power == 0:
                                        r2 = first_row_for_machine + max(getattr(machine, "total_rows", 1) - 1, 0)
                                        change_doc = getattr(machine, "change_document", None)
                                        # Извлекаем только названия документов без ID
                                        doc_text = _extract_document_names(change_doc) if change_doc else None
                                        merge_if_needed(current_row, note_col, r2, note_col, doc_text or "", text_center_format)

                                    current_row += 1

                        # Итоги по субъекту РФ (события + по типам станций) — должны выводиться ДЛЯ КАЖДОГО rd_id
                        # (иначе при нескольких субъектах в одной РЭС "пропадает" один из итогов, напр. Санкт‑Петербург).
                        # Как на веб: для Калининграда не выводим внутри списка станций (выводим отдельно ниже)
                        if show_totals and (not is_kaliningrad_sa):
                            ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                            is_tites_siberia = "титэс сибири" in str(ues_label).lower()
                            if is_tites_siberia:
                                eu_events_map = (
                                    data.get("aggregate_changes_by_energy_units_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                eu_by_station_map = (
                                    data.get("aggregate_changes_energy_units_by_station_types_with_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                has_data = bool(eu_events_map) or bool(eu_by_station_map)
                                if has_data:
                                    eu_name = energy_unit_names.get(rd_id, f"Энергоузел {rd_id}")
                                    write_combined_totals_block(f"Итого по {eu_name}", eu_events_map, eu_by_station_map)
                            else:
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
                                has_data = bool(rd_events_map) or bool(rd_by_station_map)
                                if has_data:
                                    rd_name = regional_district_names.get(rd_id, f"Субъект {rd_id}")
                                    rd_rp = regional_district_names_rp.get(rd_id)
                                    rd_dp = regional_district_names_dp.get(rd_id) if "regional_district_names_dp" in locals() else None
                                    label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                                    write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # Итоги по ОЭС: должны выводиться для КАЖДОЙ ОЭС внутри синхронной зоны
                # Как на веб: для Калининграда не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада),
                # а для ТИТЭС итоги по ОЭС вообще не выводим (только по субъектам).
                if show_totals and (not is_kaliningrad_sa) and (not is_tites_es):
                    ues_events_map = (
                        data.get("aggregate_changes_by_union_energy_systems", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(ues_id, {})
                    )
                    ues_by_station_map = (
                        data.get("aggregate_changes_union_energy_systems_by_station_types", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(ues_id, {})
                    )
                    ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                    write_combined_totals_block(f"{ues_label}", ues_events_map, ues_by_station_map)

            # Итоги по синхронной зоне (как на веб-странице): выводим ОДИН раз после завершения синхронной зоны
            # Для ТИТЭС второй уровень отсутствует — итоги по синхронной зоне не выводим.
            if show_totals and (not is_tites_es):
                # 1) Для Калининграда: отдельный итог по области (субъекту)
                if is_kaliningrad_sa and sa_rd_ids:
                    kal_rd_id: int | None = None
                    for _rd_id in sa_rd_ids:
                        rd_name = regional_district_names.get(_rd_id, "") or ""
                        if "калининград" in str(rd_name).lower():
                            kal_rd_id = _rd_id
                            break
                    if kal_rd_id is None:
                        kal_rd_id = sa_rd_ids[0]

                    rd_events_map = (
                        data.get("aggregate_changes_by_regional_districts", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    rd_by_station_map = (
                        data.get("aggregate_changes_regional_districts_by_station_types", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    if rd_events_map or rd_by_station_map:
                        rd_name = regional_district_names.get(kal_rd_id, f"Субъект {kal_rd_id}")
                        rd_rp = regional_district_names_rp.get(kal_rd_id)
                        rd_dp = regional_district_names_dp.get(kal_rd_id) if "regional_district_names_dp" in locals() else None
                        label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                        write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # 2) Итог по синхронной зоне
                sa_events_map = (synchronous_areas_yearly_p_ust.get(sa_id, {}) or {})
                sa_by_station_map = (synchronous_areas_by_station_types_yearly_p_ust.get(sa_id, {}) or {})
                if sa_events_map or sa_by_station_map:
                    sa_l = str(sa_name).lower()
                    if "калининград" in sa_l:
                        sa_label = "Итого по синхронной зоне Калининградской области"
                    elif ("перва" in sa_l) or ("1" in sa_l):
                        sa_label = "Итого по 1-й синхронной зоне ЕЭС России"
                    elif ("втор" in sa_l) or ("2" in sa_l):
                        sa_label = "Итого по 2-й синхронной зоне ЕЭС России"
                    else:
                        sa_label = f"Итого по {sa_name or 'Синхронная зона'}"
                    write_combined_totals_block(sa_label, sa_events_map, sa_by_station_map)

        # Итоги по типу энергосистемы
        if show_totals:
            es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
            is_tites = "титэс" in str(es_name).lower().replace(" ", "")
            if not is_tites:
                es_events_map = (
                    data.get("aggregate_changes_by_energy_system_types", {})
                    .get("aggregated", {})
                    .get("p_ust", {})
                    .get(es_type_id, {})
                )
                if "еэс" in str(es_name).lower():
                    es_label = "Итого по ЕЭС России"
                else:
                    es_label = f"{es_name}, всего"
                write_combined_totals_block(es_label, es_events_map, {})

        # Собираем суммы для общего итога по ТИТЭС (для вывода один раз после всех типов)
        if show_totals and es_type_id in tites_ids:
            es_events_map = (
                data.get("aggregate_changes_by_energy_system_types", {})
                .get("aggregated", {})
                .get("p_ust", {})
                .get(es_type_id, {})
            ) or {}
            es_by_station_map = (
                data.get("aggregate_changes_energy_system_types_by_station_types", {})
                .get("aggregated", {})
                .get("p_ust", {})
                .get(es_type_id, {})
            ) or {}
            for ev_code, year_map in es_events_map.items():
                tites_events_map.setdefault(ev_code, {})
                for y, v in (year_map or {}).items():
                    tites_events_map[ev_code][y] = (tites_events_map[ev_code].get(y) or 0) + (v or 0)
            for st_id, ev_map in es_by_station_map.items():
                tites_by_station_map.setdefault(st_id, {})
                for ev_code, year_map in (ev_map or {}).items():
                    tites_by_station_map[st_id].setdefault(ev_code, {})
                    for y, v in (year_map or {}).items():
                        tites_by_station_map[st_id][ev_code][y] = (tites_by_station_map[st_id][ev_code].get(y) or 0) + (v or 0)

    # Итог по ТИТЭС (объединяет ТИТЭС Востока/Сибири и т.п.)
    if show_totals and tites_ids:
        write_combined_totals_block(
            "Итого по технологически изолированным территориальным электроэнергетическим системам",
            tites_events_map,
            tites_by_station_map,
        )

    # Итоги по России
    if show_totals:
        total_events_map = (
            data.get("aggregate_changes_by_total_energy_system_types", {})
            .get("aggregated", {})
            .get("p_ust", {})
        )
        write_combined_totals_block("Итого\nпо электроэнергетическим системам России", total_events_map, {})

    # Включаем автофильтры на строке заголовков по всей области таблицы
    try:
        worksheet.autofilter(sub_row, 0, max(current_row - 1, sub_row), note_col)
    except Exception:
        pass

    workbook.close()
    output.seek(0)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    # Для обычной кнопки экспорта возвращаем "классическое" имя файла
    filename = f"station_changes_{ts}.xlsx"
    return filename, output


def export_station_changes_pril_b_to_excel(
    user: str,
    filters: dict,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    show_totals: bool,
    data: dict | None = None,
):
    """
    Экспорт данных со страницы station_changes_list по форме «Приложение Б».
    """
    # Для экспорта «Приложение Б» вывод итогов должен не зависеть от переключателей на странице
    show_totals = True
    current_db_version_id = get_current_db_version_id()

    # Сбрасываем кэши справочников, чтобы загрузить актуальные данные для текущей версии БД
    from app.common.services.get_services.stations.station_type_get_services import (
        get_station_type_list_full,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
    )

    cache_functions = [
        get_station_type_list_full,
        get_union_energy_system_list_full,
        get_energy_system_type_list_full,
    ]
    for func in cache_functions:
        if hasattr(func, "cache_clear"):
            func.cache_clear()

    # Загружаем все данные без пагинации, чтобы экспортировать всё отображаемое
    if (
        data is None
        or data.get("database_version_id") != current_db_version_id
    ):
        data = get_station_changes_list_data(
            filters=filters,
            per_page="all",
            page=1,
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            show_all=True,
        )
    if isinstance(data, dict):
        data.setdefault("database_version_id", current_db_version_id)

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

    # Список лет для суммирования в колонке "Итого": только годы с признаком "план"
    year_features = get_year_feature_dict() or {}
    plan_years = [
        y for y in range(start_year, end_year + 1)
        if str(year_features.get(y, "")).strip().lower() == "план"
    ]
    sum_years = plan_years
    if plan_years:
        all_years_header = f"{plan_years[0]}–{plan_years[-1]} гг.\n"
    else:
        all_years_header = ""
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
    last_col_name = xl_col_to_name(all_years_col)

    worksheet.merge_range(
        f"A1:{last_col_name}1",
        "ПРИЛОЖЕНИЕ Б",
        title_format)
    worksheet.merge_range(
        f"A2:{last_col_name}2",
        f"Перечень планируемых изменений установленной генерирующей мощности объектов по производству электрической энергии в ЕЭС России\nна период {start_year + 1}–{end_year} годов",
        title_format)
    worksheet.set_row(1, 62.25)
    worksheet.merge_range(
        f"A3:{last_col_name}3",
        "",
        title_format)
    worksheet.set_row(2, 30.75)
    worksheet.merge_range(
        f"A4:{last_col_name}4",
        f"Таблица Б.1 – Перечень планируемых изменений установленной генерирующей мощности объектов по производству электрической энергии в ЕЭС России на период {start_year + 1}–{end_year} годов, МВт",
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
    worksheet.set_column(note_col, note_col, 28, None, {"hidden": True})

    # Текущая строка для данных (начинаем с 7-й строки Excel)
    current_row = sub_row + 1
    # Отслеживаем последнюю объединённую строку ПО КАЖДОМУ СТОЛБЦУ (а не глобально),
    # чтобы не "сдвигать" данные вниз из-за merge в других столбцах.
    max_merged_row_by_col: dict[int, int] = {}

    # Вспомогательная функция для объединения ячеек (без падения при rowspan<=1)
    def merge_if_needed(r1: int, c1: int, r2: int, c2: int, value, text_center_format):
        if r2 > r1 or c2 > c1:
            worksheet.merge_range(r1, c1, r2, c2, value, text_center_format)
            # Запоминаем последнюю объединённую строку для каждого затронутого столбца
            for c in range(c1, c2 + 1):
                prev = max_merged_row_by_col.get(c, -1)
                if r2 > prev:
                    max_merged_row_by_col[c] = r2
        else:
            worksheet.write(r1, c1, value, text_center_format)

    #  Справочники имён и хелпер вывода итогов по событиям
    try:
        union_energy_system_names = get_union_energy_systems_map()
    except Exception:
        union_energy_system_names = {}

    # Энергоузлы (для спец-логики ОЭС "ТИТЭС Сибири")
    try:
        from app.common.services.get_services.energy_systems.energy_unit_get_services import get_energy_unit_list_full
        energy_unit_list = get_energy_unit_list_full() or []
        energy_unit_names = {eu.id: eu.name for eu in energy_unit_list if getattr(eu, "id", None) is not None}
    except Exception:
        energy_unit_names = {}

    try:
        regional_district_names = get_regional_districts_map()
    except Exception:
        regional_district_names = {}

    # Родительный падеж субъектов РФ (для "Итого по ...")
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_rp = {rd.id: getattr(rd, "name_rp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_rp = {}

    # Наименование субъекта (name_dp) для итоговых строк вида "Итого по субъекту ..."
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_dp = {rd.id: getattr(rd, "name_dp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_dp = {}

    try:
        energy_system_type_names = get_energy_system_type_map()
    except Exception:
        energy_system_type_names = {}

    # Агрегаты по синхронным зонам на веб-странице формируются на этапе сборки template-context,
    # а в export у нас "сырые" data из get_station_changes_list_data. Поэтому считаем агрегаты здесь.
    try:
        from app.generation.services.station_changes_services.station_changes_services import (
            build_synchronous_area_aggregates,
        )
        sa_aggregates = build_synchronous_area_aggregates(data) or {}
        synchronous_areas_yearly_p_ust = sa_aggregates.get("synchronous_areas_yearly_p_ust", {}) or {}
        synchronous_areas_by_station_types_yearly_p_ust = sa_aggregates.get("synchronous_areas_by_station_types_yearly_p_ust", {}) or {}
    except Exception:
        synchronous_areas_yearly_p_ust = {}
        synchronous_areas_by_station_types_yearly_p_ust = {}

    def write_combined_totals_block(label: str, events_years_map: dict, station_type_events_map: dict):
        """Пишет комбинированный блок итогов: для каждого мероприятия сначала 'Всего',
        затем разбивка по типам станций"""
        nonlocal current_row

        # Начинаем новый итоговый блок так, чтобы он не попадал внутрь merge_range
        # в СВОИХ столбцах (B/C/F/G/H/A). Это предотвращает OverlappingRange и не ломает разметку.
        block_cols = [subject_col, gen_company_col, station_name_col, machine_num_col, machine_name_col, fuel_col]
        safe_start = current_row
        for c in block_cols:
            safe_start = max(safe_start, max_merged_row_by_col.get(c, -1) + 1)
        current_row = safe_start

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

        # Столбец 0: уже сформированная подпись блока (без автодобавления ", всего")
        merge_if_needed(block_start_row, subject_col, block_start_row + total_block_height - 1, subject_col, label, text_center_format)

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
                if val is not None and y in sum_years:
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
                    if val is not None and y in sum_years:
                        row_sum += val
                worksheet.write(current_row, all_years_col, row_sum if row_sum != 0 else None, text_center_format)
                worksheet.write(current_row, note_col, "", text_center_format)
                current_row += 1

        # Важно: объединения ячеек для блока рассчитаны на total_block_height строк.
        # Даже если по каким-то причинам фактически было записано меньше строк,
        # нужно сдвинуть current_row до конца блока, иначе следующий merge_range может пересечься
        # с текущим (xlsxwriter.exceptions.OverlappingRange).
        expected_end = block_start_row + total_block_height
        if current_row < expected_end:
            current_row = expected_end

    # Обход иерархии как в шаблоне (тип энергосистемы -> (синхронная зона|энергозона) -> ОЭС -> РЭС -> субъект)
    for es_type_id, es_group in stations_grouped.items():
        # Для экспорта по форме «Приложение Б» исключаем ТИТЭС целиком
        es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
        is_tites_es = "титэс" in str(es_name).lower().replace(" ", "")
        if is_tites_es:
            continue

        for sa_id, sa_group in es_group.items():
            # Спец-логика как на веб: для Калининградской синхронной зоны
            # - не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада)
            # - после станций выводим "Итого по Калининградской области", затем "Итого по синхронной зоне Калининградской области"
            sa_names = data.get("synchronous_area_names", {}) or {}
            sa_name = sa_names.get(sa_id, "")
            is_kaliningrad_sa = "калининград" in str(sa_name).lower()

            # Собираем список субъектов (rd_id) внутри текущей синхронной зоны (для калининградской спец-логики)
            sa_rd_ids: list[int] = []
            for _ues_id, _ues_group in (sa_group or {}).items():
                for _res_id, _res_group in (_ues_group or {}).items():
                    for _rd_id in (_res_group or {}).keys():
                        try:
                            _rid = int(_rd_id)
                        except Exception:
                            continue
                        if _rid != 0 and _rid not in sa_rd_ids:
                            sa_rd_ids.append(_rid)

            for ues_id, rd_group in sa_group.items():
                for res_id, res_group in rd_group.items():
                    for rd_id, stations in res_group.items():
                        for station in stations:
                            # Каждая виртуальная станция содержит machines с выставленными rowspan'ами
                            for machine in getattr(station, "machines", []):
                                if not getattr(machine, "powers_by_year", None):
                                    continue

                                first_row_for_machine = current_row

                                # Сумма "Итого" по план-годам отдельно для каждого мероприятия
                                event_sum_map = {}
                                for _p in machine.powers_by_year:
                                    if not isinstance(_p, dict):
                                        continue
                                    _ev = _p.get("event")
                                    _y = _p.get("year")
                                    _v = _p.get("p_ust")
                                    if _y in sum_years and _ev:
                                        event_sum_map[_ev] = (event_sum_map.get(_ev) or 0) + (_v or 0)
                                seen_events = set()

                                for idx_power, power_row in enumerate(machine.powers_by_year):
                                    # Субъект РФ (region_rowspan применяется один раз)
                                    if idx_power == 0 and getattr(machine, "region_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.region_rowspan - 1
                                        ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                                        if "титэс сибири" in str(ues_label).lower():
                                            eu_id = getattr(station, "id_energy_unit", None) or 0
                                            value = energy_unit_names.get(eu_id, "Без энергоузла" if not eu_id else f"Энергоузел {eu_id}")
                                        else:
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
                                        station_type_obj = getattr(station, "station_type", None)
                                        station_type_name = getattr(station_type_obj, "name", None)
                                        if not station_type_name:
                                            st_id = getattr(station, "id_station_type", None)
                                            station_type_name = station_type_names.get(st_id) if st_id else None
                                        station_type_name = station_type_name or "—"
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

                                    # Столбец "Итого" — по каждому мероприятию, без объединений (пишем один раз на мероприятие)
                                    ev_code = power_row.get("event")
                                    if ev_code and ev_code not in seen_events:
                                        seen_events.add(ev_code)
                                        ev_sum = event_sum_map.get(ev_code)
                                        worksheet.write(current_row, all_years_col, ev_sum if ev_sum and ev_sum != 0 else None, text_center_format)
                                    else:
                                        worksheet.write(current_row, all_years_col, None, text_center_format)

                                    # Основание — один раз на агрегат, объединяем на высоту агрегата
                                    if idx_power == 0:
                                        r2 = first_row_for_machine + max(getattr(machine, "total_rows", 1) - 1, 0)
                                        change_doc = getattr(machine, "change_document", None)
                                        # Извлекаем только названия документов без ID
                                        doc_text = _extract_document_names(change_doc) if change_doc else None
                                        merge_if_needed(current_row, note_col, r2, note_col, doc_text or "", text_center_format)

                                    current_row += 1

                        # Итоги по субъекту РФ (события + по типам станций) — должны выводиться ДЛЯ КАЖДОГО rd_id
                        # Как на веб: для Калининграда не выводим внутри списка станций (выводим отдельно ниже)
                        if show_totals and (not is_kaliningrad_sa):
                            ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                            is_tites_siberia = "титэс сибири" in str(ues_label).lower()
                            if is_tites_siberia:
                                eu_events_map = (
                                    data.get("aggregate_changes_by_energy_units_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                eu_by_station_map = (
                                    data.get("aggregate_changes_energy_units_by_station_types_with_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                has_data = bool(eu_events_map) or bool(eu_by_station_map)
                                if has_data:
                                    eu_name = energy_unit_names.get(rd_id, f"Энергоузел {rd_id}")
                                    write_combined_totals_block(f"Итого по {eu_name}", eu_events_map, eu_by_station_map)
                            else:
                                rd_events_map = (
                                    data.get("aggregate_changes_by_regional_districts", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                rd_by_station_map = (
                                    data.get("aggregate_changes_regional_districts_by_station_types_with_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                has_data = bool(rd_events_map) or bool(rd_by_station_map)
                                if has_data:
                                    rd_name = regional_district_names.get(rd_id, f"Субъект {rd_id}")
                                    rd_rp = regional_district_names_rp.get(rd_id)
                                    rd_dp = regional_district_names_dp.get(rd_id) if "regional_district_names_dp" in locals() else None
                                    label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                                    write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # Итоги по ОЭС (внутри синхронной зоны должны выводиться для КАЖДОЙ ОЭС, а не только для последней)
                # Как на веб: для Калининграда не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада)
                if show_totals and (not is_kaliningrad_sa):
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
                    write_combined_totals_block(f"{ues_label}", ues_events_map, ues_by_station_map)

            # Итоги по синхронной зоне (как на веб-странице): выводим ОДИН раз после завершения синхронной зоны
            if show_totals:
                # 1) Для Калининграда: отдельный итог по области (субъекту)
                if is_kaliningrad_sa and sa_rd_ids:
                    kal_rd_id: int | None = None
                    for _rd_id in sa_rd_ids:
                        rd_name = regional_district_names.get(_rd_id, "") or ""
                        if "калининград" in str(rd_name).lower():
                            kal_rd_id = _rd_id
                            break
                    if kal_rd_id is None:
                        kal_rd_id = sa_rd_ids[0]

                    rd_events_map = (
                        data.get("aggregate_changes_by_regional_districts", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    rd_by_station_map = (
                        data.get("aggregate_changes_regional_districts_by_station_types_with_events", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    if rd_events_map or rd_by_station_map:
                        rd_name = regional_district_names.get(kal_rd_id, f"Субъект {kal_rd_id}")
                        rd_rp = regional_district_names_rp.get(kal_rd_id)
                        rd_dp = regional_district_names_dp.get(kal_rd_id) if "regional_district_names_dp" in locals() else None
                        label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                        write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # 2) Итог по синхронной зоне
                sa_events_map = (synchronous_areas_yearly_p_ust.get(sa_id, {}) or {})
                sa_by_station_map = (synchronous_areas_by_station_types_yearly_p_ust.get(sa_id, {}) or {})
                if sa_events_map or sa_by_station_map:
                    sa_l = str(sa_name).lower()
                    if "калининград" in sa_l:
                        sa_label = "Итого по синхронной зоне Калининградской области"
                    elif ("перва" in sa_l) or ("1" in sa_l):
                        sa_label = "Итого по 1-й синхронной зоне ЕЭС России"
                    elif ("втор" in sa_l) or ("2" in sa_l):
                        sa_label = "Итого по 2-й синхронной зоне ЕЭС России"
                    else:
                        sa_label = f"Итого по {sa_name or 'Синхронная зона'}"
                    write_combined_totals_block(sa_label, sa_events_map, sa_by_station_map)

        # Итоги по типу энергосистемы
        if show_totals:
            es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
            is_tites = "титэс" in str(es_name).lower().replace(" ", "")
            if not is_tites:
                es_events_map = (
                    data.get("aggregate_changes_by_energy_system_types", {})
                    .get("aggregated", {})
                    .get("p_ust", {})
                    .get(es_type_id, {})
                )
                if "еэс" in str(es_name).lower():
                    es_label = "Итого по ЕЭС России"
                else:
                    es_label = f"{es_name}, всего"
                write_combined_totals_block(es_label, es_events_map, {})

    # Включаем автофильтры на строке заголовков по всей области таблицы
    try:
        worksheet.autofilter(sub_row, 0, max(current_row - 1, sub_row), note_col)
    except Exception:
        pass

    workbook.close()
    output.seek(0)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"Приложение Б_Перечень изменений уст мощности_{ts}.xlsx"
    return filename, output


def export_station_changes_pril_2_russia_to_excel(
    user: str,
    filters: dict,
    rounding_digits: int,
    start_year: int,
    end_year: int,
    show_totals: bool,
    data: dict | None = None,
):
    """Приложение 2 (Россия): полный дубль export_station_changes_to_excel.
    Изменена только преамбула перед таблицей (как в форме) и смещение шапки таблицы.
    """
    current_db_version_id = get_current_db_version_id()

    # Сбрасываем кэши справочников, чтобы загрузить актуальные данные для текущей версии БД
    from app.common.services.get_services.stations.station_type_get_services import (
        get_station_type_list_full,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
    )
    
    cache_functions = [
        get_station_type_list_full,
        get_union_energy_system_list_full,
        get_energy_system_type_list_full,
    ]
    for func in cache_functions:
        if hasattr(func, "cache_clear"):
            func.cache_clear()

    # Загружаем все данные без пагинации, чтобы экспортировать всё отображаемое
    if (
        data is None
        or data.get("database_version_id") != current_db_version_id
    ):
        data = get_station_changes_list_data(
            filters=filters,
            per_page="all",
            page=1,
            rounding_digits=rounding_digits,
            start_year=start_year,
            end_year=end_year,
            show_all=True,
        )
    if isinstance(data, dict):
        data.setdefault("database_version_id", current_db_version_id)

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
    
    # Список лет для суммирования в колонке "Итого": только годы с признаком "план"
    year_features = get_year_feature_dict() or {}
    plan_years = [
        y for y in range(start_year, end_year + 1)
        if str(year_features.get(y, "")).strip().lower() == "план"
    ]
    sum_years = plan_years
    if plan_years:
        all_years_header = f"{plan_years[0]}–{plan_years[-1]} гг.\n"
    else:
        all_years_header = ""
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

    # Преамбула формы «Приложение 2 (Россия)» (как на утверждённом шаблоне)
    last_col_name = xl_col_to_name(all_years_col)
    header_right_format = workbook.add_format({
        'font_name': 'Times New Roman',
        'font_size': 24,
        'align': 'right',
        'valign': 'vright',
        'text_wrap': True,
    })
    header_center_format = workbook.add_format({
        'font_name': 'Times New Roman',
        'font_size': 24,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })
    header_center_format_bold = workbook.add_format({
        'font_name': 'Times New Roman',
        'font_size': 24,
        'bold': True,
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
    })
    preamble_unit_format = workbook.add_format({
        'font_name': 'Times New Roman',
        'font_size': 20,
        'align': 'right',
        'valign': 'vright',
        'text_wrap': False,
    })

    right_start_col = max(all_years_col - 4, 0)
    right_start_name = xl_col_to_name(right_start_col)
    # 1-я строка Excel: «ПРИЛОЖЕНИЕ № 2» (не должно пересекаться с другими merge_range)
    worksheet.merge_range(f"{right_start_name}1:{last_col_name}1", "ПРИЛОЖЕНИЕ № 2", header_center_format)
    worksheet.set_row(0, 30)

    # 2-я строка Excel: пустая строка после заголовка
    worksheet.set_row(1, 12.75)

    # 3-я строка Excel: правый верхний блок (в одной строке)
    worksheet.merge_range(
        f"{right_start_name}3:{last_col_name}3",
        f"к схеме и программе развития электроэнергетических систем России на {start_year + 1}–{end_year} годы",
        header_center_format,
    )
    worksheet.set_row(2, 89.25)
    # 4-я строка Excel — без дополнительного отступа

    preamble_text = (
        "ПЕРЕЧЕНЬ\n"
        "планируемых изменений установленной генерирующей мощности объектов по производству электрической энергии в ЕЭС России и технологически\n"
        "изолированных территориальных электроэнергетических системах\n"
        f"на период {start_year + 1}–{end_year} годов"
    )
    # Пустая строка ПЕРЕД «ПЕРЕЧЕНЬ...»
    worksheet.set_row(4, 33)  # строка 5 Excel

    # «ПЕРЕЧЕНЬ...» — объединяем по всей ширине таблицы
    worksheet.merge_range(f"A6:{last_col_name}6", preamble_text, header_center_format_bold)
    worksheet.set_row(5, 117.75)  # строка 6 Excel

    # Пустая строка ПОСЛЕ «ПЕРЕЧЕНЬ...»
    worksheet.set_row(6, 15.75)  # строка 7 Excel

    # (МВт) — строка 8 Excel, над колонкой "Итого" (сумма по диапазону годов)
    worksheet.write(7, all_years_col, "(МВт)", preamble_unit_format)
    worksheet.set_row(7, 23.25)  # строка 8 Excel

    # Шапка таблицы теперь начинается с 9-й строки Excel
    sub_row = 8

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
    worksheet.set_column(note_col, note_col, 28, None, {"hidden": True})

    # Текущая строка для данных (сразу после шапки таблицы)
    current_row = sub_row + 1
    # Отслеживаем последнюю объединённую строку ПО КАЖДОМУ СТОЛБЦУ (а не глобально),
    # чтобы не "сдвигать" данные вниз из-за merge в других столбцах.
    max_merged_row_by_col: dict[int, int] = {}

    # Вспомогательная функция для объединения ячеек (без падения при rowspan<=1)
    def merge_if_needed(r1: int, c1: int, r2: int, c2: int, value, text_center_format):
        if r2 > r1 or c2 > c1:
            worksheet.merge_range(r1, c1, r2, c2, value, text_center_format)
            # Запоминаем последнюю объединённую строку для каждого затронутого столбца
            for c in range(c1, c2 + 1):
                prev = max_merged_row_by_col.get(c, -1)
                if r2 > prev:
                    max_merged_row_by_col[c] = r2
        else:
            worksheet.write(r1, c1, value, text_center_format)

    #  Справочники имён и хелпер вывода итогов по событиям
    try:
        union_energy_system_names = get_union_energy_systems_map()
    except Exception:
        union_energy_system_names = {}

    # Энергоузлы (для спец-логики ОЭС "ТИТЭС Сибири")
    try:
        from app.common.services.get_services.energy_systems.energy_unit_get_services import get_energy_unit_list_full
        energy_unit_list = get_energy_unit_list_full() or []
        energy_unit_names = {eu.id: eu.name for eu in energy_unit_list if getattr(eu, "id", None) is not None}
    except Exception:
        energy_unit_names = {}

    try:
        regional_district_names = get_regional_districts_map()
    except Exception:
        regional_district_names = {}

    # Родительный падеж субъектов РФ (для "Итого по ...")
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_rp = {rd.id: getattr(rd, "name_rp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_rp = {}
    
    # Наименование субъекта (name_dp) для итоговых строк вида "Итого по субъекту ..."
    try:
        rd_objs = get_regional_districts_list() or []
        regional_district_names_dp = {rd.id: getattr(rd, "name_dp", None) for rd in rd_objs if getattr(rd, "id", None) is not None}
    except Exception:
        regional_district_names_dp = {}

    try:
        energy_system_type_names = get_energy_system_type_map()
    except Exception:
        energy_system_type_names = {}

    # Агрегаты по синхронным зонам на веб-странице формируются на этапе сборки template-context,
    # а в export у нас "сырые" data из get_station_changes_list_data. Поэтому считаем агрегаты здесь.
    try:
        from app.generation.services.station_changes_services.station_changes_services import (
            build_synchronous_area_aggregates,
        )
        sa_aggregates = build_synchronous_area_aggregates(data) or {}
        synchronous_areas_yearly_p_ust = sa_aggregates.get("synchronous_areas_yearly_p_ust", {}) or {}
        synchronous_areas_by_station_types_yearly_p_ust = sa_aggregates.get("synchronous_areas_by_station_types_yearly_p_ust", {}) or {}
    except Exception:
        synchronous_areas_yearly_p_ust = {}
        synchronous_areas_by_station_types_yearly_p_ust = {}

    def write_combined_totals_block(label: str, events_years_map: dict, station_type_events_map: dict):
        """Пишет комбинированный блок итогов: для каждого мероприятия сначала 'Всего', 
        затем разбивка по типам станций"""
        nonlocal current_row
        
        # Начинаем новый итоговый блок так, чтобы он не попадал внутрь merge_range
        # в СВОИХ столбцах (B/C/F/G/H/A). Это предотвращает OverlappingRange и не ломает разметку.
        block_cols = [subject_col, gen_company_col, station_name_col, machine_num_col, machine_name_col, fuel_col]
        safe_start = current_row
        for c in block_cols:
            safe_start = max(safe_start, max_merged_row_by_col.get(c, -1) + 1)
        current_row = safe_start
        
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
        
        # Столбец 0: уже сформированная подпись блока (без автодобавления ", всего")
        merge_if_needed(block_start_row, subject_col, block_start_row + total_block_height - 1, subject_col, label, text_center_format)
        
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
                if val is not None and y in sum_years:
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
                    if val is not None and y in sum_years:
                        row_sum += val
                worksheet.write(current_row, all_years_col, row_sum if row_sum != 0 else None, text_center_format)
                worksheet.write(current_row, note_col, "", text_center_format)
                current_row += 1

        # Важно: объединения ячеек для блока рассчитаны на total_block_height строк.
        # Даже если по каким-то причинам фактически было записано меньше строк,
        # нужно сдвинуть current_row до конца блока, иначе следующий merge_range может пересечься
        # с текущим (xlsxwriter.exceptions.OverlappingRange).
        expected_end = block_start_row + total_block_height
        if current_row < expected_end:
            current_row = expected_end

    # Обход иерархии как в шаблоне (тип энергосистемы -> (синхронная зона|энергозона) -> ОЭС -> РЭС -> субъект)
    # Для объединенного итога по всем ТИТЭС
    tites_ids = [
        est_id for est_id, name in energy_system_type_names.items()
        if name and "титэс" in str(name).lower().replace(" ", "")
    ]
    tites_events_map = {}
    tites_by_station_map = {}

    for es_type_id, es_group in stations_grouped.items():
        # Для ТИТЭС второй уровень (синхронные зоны) на вебе не используется:
        # для ветки ТИТЭС нет итогов по ОЭС и по синхронным зонам, только по субъектам.
        es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
        is_tites_es = "титэс" in str(es_name).lower().replace(" ", "")
        for sa_id, sa_group in es_group.items():
            # Спец-логика как на веб: для Калининградской синхронной зоны
            # - не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада)
            # - после станций выводим "Итого по Санкт-Петербургу/Ленобласти..." как обычно,
            #   но для Калининграда выводим "Итого по Калининградской области" отдельно внизу,
            #   затем "Итого по синхронной зоне Калининградской области"
            sa_names = data.get("synchronous_area_names", {}) or {}
            sa_name = sa_names.get(sa_id, "")
            is_kaliningrad_sa = "калининград" in str(sa_name).lower()

            # Собираем список субъектов (rd_id) внутри текущей синхронной зоны (для калининградской спец-логики)
            sa_rd_ids: list[int] = []
            for _ues_id, _ues_group in (sa_group or {}).items():
                for _res_id, _res_group in (_ues_group or {}).items():
                    for _rd_id in (_res_group or {}).keys():
                        try:
                            _rid = int(_rd_id)
                        except Exception:
                            continue
                        if _rid != 0 and _rid not in sa_rd_ids:
                            sa_rd_ids.append(_rid)

            for ues_id, rd_group in sa_group.items():
                for res_id, res_group in rd_group.items():
                    for rd_id, stations in res_group.items():
                        for station in stations:
                            # Каждая виртуальная станция содержит machines с выставленными rowspan'ами
                            for machine in getattr(station, "machines", []):
                                if not getattr(machine, "powers_by_year", None):
                                    continue

                                first_row_for_machine = current_row

                                # Сумма "Итого" по план-годам отдельно для каждого мероприятия
                                event_sum_map = {}
                                for _p in machine.powers_by_year:
                                    if not isinstance(_p, dict):
                                        continue
                                    _ev = _p.get("event")
                                    _y = _p.get("year")
                                    _v = _p.get("p_ust")
                                    if _y in sum_years and _ev:
                                        event_sum_map[_ev] = (event_sum_map.get(_ev) or 0) + (_v or 0)
                                seen_events = set()

                                for idx_power, power_row in enumerate(machine.powers_by_year):
                                    # Субъект РФ (region_rowspan применяется один раз)
                                    if idx_power == 0 and getattr(machine, "region_rowspan", 0) > 0:
                                        r2 = first_row_for_machine + machine.region_rowspan - 1
                                        ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                                        if "титэс сибири" in str(ues_label).lower():
                                            eu_id = getattr(station, "id_energy_unit", None) or 0
                                            value = energy_unit_names.get(eu_id, "Без энергоузла" if not eu_id else f"Энергоузел {eu_id}")
                                        else:
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
                                        station_type_obj = getattr(station, "station_type", None)
                                        station_type_name = getattr(station_type_obj, "name", None)
                                        if not station_type_name:
                                            st_id = getattr(station, "id_station_type", None)
                                            station_type_name = station_type_names.get(st_id) if st_id else None
                                        station_type_name = station_type_name or "—"
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

                                    # Столбец "Итого" — по каждому мероприятию, без объединений (пишем один раз на мероприятие)
                                    ev_code = power_row.get("event")
                                    if ev_code and ev_code not in seen_events:
                                        seen_events.add(ev_code)
                                        ev_sum = event_sum_map.get(ev_code)
                                        worksheet.write(current_row, all_years_col, ev_sum if ev_sum and ev_sum != 0 else None, text_center_format)
                                    else:
                                        worksheet.write(current_row, all_years_col, None, text_center_format)

                                    # Основание — один раз на агрегат, объединяем на высоту агрегата
                                    if idx_power == 0:
                                        r2 = first_row_for_machine + max(getattr(machine, "total_rows", 1) - 1, 0)
                                        change_doc = getattr(machine, "change_document", None)
                                        # Извлекаем только названия документов без ID
                                        doc_text = _extract_document_names(change_doc) if change_doc else None
                                        merge_if_needed(current_row, note_col, r2, note_col, doc_text or "", text_center_format)

                                    current_row += 1

                        # Итоги по субъекту РФ (события + по типам станций) — должны выводиться ДЛЯ КАЖДОГО rd_id
                        # (иначе при нескольких субъектах в одной РЭС "пропадает" один из итогов, напр. Санкт‑Петербург).
                        # Как на веб: для Калининграда не выводим внутри списка станций (выводим отдельно ниже)
                        if show_totals and (not is_kaliningrad_sa):
                            ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                            is_tites_siberia = "титэс сибири" in str(ues_label).lower()
                            if is_tites_siberia:
                                eu_events_map = (
                                    data.get("aggregate_changes_by_energy_units_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                eu_by_station_map = (
                                    data.get("aggregate_changes_energy_units_by_station_types_with_events", {})
                                    .get("aggregated", {})
                                    .get("p_ust", {})
                                    .get(rd_id, {})
                                )
                                has_data = bool(eu_events_map) or bool(eu_by_station_map)
                                if has_data:
                                    eu_name = energy_unit_names.get(rd_id, f"Энергоузел {rd_id}")
                                    write_combined_totals_block(f"Итого по {eu_name}", eu_events_map, eu_by_station_map)
                            else:
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
                                has_data = bool(rd_events_map) or bool(rd_by_station_map)
                                if has_data:
                                    rd_name = regional_district_names.get(rd_id, f"Субъект {rd_id}")
                                    rd_rp = regional_district_names_rp.get(rd_id)
                                    rd_dp = regional_district_names_dp.get(rd_id) if "regional_district_names_dp" in locals() else None
                                    label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                                    write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # Итоги по ОЭС: должны выводиться для КАЖДОЙ ОЭС внутри синхронной зоны
                # Как на веб: для Калининграда не выводим итоги по ОЭС (в т.ч. ОЭС Северо-Запада),
                # а для ТИТЭС итоги по ОЭС вообще не выводим (только по субъектам).
                if show_totals and (not is_kaliningrad_sa) and (not is_tites_es):
                    ues_events_map = (
                        data.get("aggregate_changes_by_union_energy_systems", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(ues_id, {})
                    )
                    ues_by_station_map = (
                        data.get("aggregate_changes_union_energy_systems_by_station_types", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(ues_id, {})
                    )
                    ues_label = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
                    write_combined_totals_block(f"{ues_label}", ues_events_map, ues_by_station_map)

            # Итоги по синхронной зоне (как на веб-странице): выводим ОДИН раз после завершения синхронной зоны
            # Для ТИТЭС второй уровень отсутствует — итоги по синхронной зоне не выводим.
            if show_totals and (not is_tites_es):
                # 1) Для Калининграда: отдельный итог по области (субъекту)
                if is_kaliningrad_sa and sa_rd_ids:
                    kal_rd_id: int | None = None
                    for _rd_id in sa_rd_ids:
                        rd_name = regional_district_names.get(_rd_id, "") or ""
                        if "калининград" in str(rd_name).lower():
                            kal_rd_id = _rd_id
                            break
                    if kal_rd_id is None:
                        kal_rd_id = sa_rd_ids[0]

                    rd_events_map = (
                        data.get("aggregate_changes_by_regional_districts", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    rd_by_station_map = (
                        data.get("aggregate_changes_regional_districts_by_station_types", {})
                        .get("aggregated", {})
                        .get("p_ust", {})
                        .get(kal_rd_id, {})
                    )
                    if rd_events_map or rd_by_station_map:
                        rd_name = regional_district_names.get(kal_rd_id, f"Субъект {kal_rd_id}")
                        rd_rp = regional_district_names_rp.get(kal_rd_id)
                        rd_dp = regional_district_names_dp.get(kal_rd_id) if "regional_district_names_dp" in locals() else None
                        label = f"Итого по {rd_dp}" if rd_dp else f"Итого по {rd_rp or rd_name}"
                        write_combined_totals_block(label, rd_events_map, rd_by_station_map)

                # 2) Итог по синхронной зоне
                sa_events_map = (synchronous_areas_yearly_p_ust.get(sa_id, {}) or {})
                sa_by_station_map = (synchronous_areas_by_station_types_yearly_p_ust.get(sa_id, {}) or {})
                if sa_events_map or sa_by_station_map:
                    sa_l = str(sa_name).lower()
                    if "калининград" in sa_l:
                        sa_label = "Итого по синхронной зоне Калининградской области"
                    elif ("перва" in sa_l) or ("1" in sa_l):
                        sa_label = "Итого по 1-й синхронной зоне ЕЭС России"
                    elif ("втор" in sa_l) or ("2" in sa_l):
                        sa_label = "Итого по 2-й синхронной зоне ЕЭС России"
                    else:
                        sa_label = f"Итого по {sa_name or 'Синхронная зона'}"
                    write_combined_totals_block(sa_label, sa_events_map, sa_by_station_map)

        # Итоги по типу энергосистемы
        if show_totals:
            es_name = energy_system_type_names.get(es_type_id, f"Тип энергосистемы {es_type_id}")
            is_tites = "титэс" in str(es_name).lower().replace(" ", "")
            if not is_tites:
                es_events_map = (
                    data.get("aggregate_changes_by_energy_system_types", {})
                    .get("aggregated", {})
                    .get("p_ust", {})
                    .get(es_type_id, {})
                )
                if "еэс" in str(es_name).lower():
                    es_label = "Итого по ЕЭС России"
                else:
                    es_label = f"{es_name}, всего"
                write_combined_totals_block(es_label, es_events_map, {})

        # Собираем суммы для общего итога по ТИТЭС (для вывода один раз после всех типов)
        if show_totals and es_type_id in tites_ids:
            es_events_map = (
                data.get("aggregate_changes_by_energy_system_types", {})
                .get("aggregated", {})
                .get("p_ust", {})
                .get(es_type_id, {})
            ) or {}
            es_by_station_map = (
                data.get("aggregate_changes_energy_system_types_by_station_types", {})
                .get("aggregated", {})
                .get("p_ust", {})
                .get(es_type_id, {})
            ) or {}
            for ev_code, year_map in es_events_map.items():
                tites_events_map.setdefault(ev_code, {})
                for y, v in (year_map or {}).items():
                    tites_events_map[ev_code][y] = (tites_events_map[ev_code].get(y) or 0) + (v or 0)
            for st_id, ev_map in es_by_station_map.items():
                tites_by_station_map.setdefault(st_id, {})
                for ev_code, year_map in (ev_map or {}).items():
                    tites_by_station_map[st_id].setdefault(ev_code, {})
                    for y, v in (year_map or {}).items():
                        tites_by_station_map[st_id][ev_code][y] = (tites_by_station_map[st_id][ev_code].get(y) or 0) + (v or 0)

    # Итог по ТИТЭС (объединяет ТИТЭС Востока/Сибири и т.п.)
    if show_totals and tites_ids:
        write_combined_totals_block(
            "Итого по технологически изолированным территориальным электроэнергетическим системам",
            tites_events_map,
            tites_by_station_map,
        )

    # Итоги по России
    if show_totals:
        total_events_map = (
            data.get("aggregate_changes_by_total_energy_system_types", {})
            .get("aggregated", {})
            .get("p_ust", {})
        )
        write_combined_totals_block("Итого\nпо электроэнергетическим системам России", total_events_map, {})

    # Включаем автофильтры на строке заголовков по всей области таблицы
    try:
        worksheet.autofilter(sub_row, 0, max(current_row - 1, sub_row), note_col)
    except Exception:
        pass

    workbook.close()
    output.seek(0)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    # Для обычной кнопки экспорта возвращаем "классическое" имя файла
    filename = f"Приложение 2_{ts}.xlsx"
    return filename, output


