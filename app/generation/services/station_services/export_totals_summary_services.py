# -*- coding: utf-8 -*-
"""Сервисы для экспорта итоговых сумм в Excel."""
from io import BytesIO
from datetime import datetime
from flask import current_app
from collections import defaultdict
from decimal import Decimal
from app.generation.services.station_services.station_services import (
    get_filtered_station_ids,
    build_energy_system_type_aggregates,
    build_total_energy_system_type_aggregates,
    build_synchronous_area_aggregates,
    build_federal_district_aggregates,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_rows import get_full_aggregation_rows
from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import aggregate_all_at_once
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_map,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
)
from app.common.services.get_services.years.year_feature_services import get_year_feature_dict
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list_full,
    get_federal_districts_map,
)
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.common.services.database_version_filter import filter_by_db_version
from config import Config


def round_value(val, digits):
    """Округление значения с учетом digits."""
    if val is None:
        return None
    if val == 0:
        return 0
    if digits is None:
        return val
    try:
        if digits == -1:
            return int(round(val, 0))
        elif digits == 0:
            return val
        else:
            return round(val, digits)
    except Exception:
        return val


def format_value(val, rounding_digits):
    """Форматирование значения для отображения."""
    if val is None or val == 0:
        return "—"
    rounded = round_value(val, rounding_digits)
    if rounded is None:
        return "—"
    if rounding_digits == -1:
        return str(int(rounded)).replace('.', ',')
    elif rounding_digits == 0:
        return str(rounded).replace('.', ',')
    else:
        return f"{rounded:.{rounding_digits}f}".replace('.', ',')


def export_totals_summary_to_excel(
    start_year: int,
    end_year: int,
    show_p_ogr: bool = False,
    show_p_rasp: bool = False,
    rounding_digits: int = 1,
    aggregation_types: list = None,
):
    """Экспортирует итоговые суммы в Excel файл со всеми деталями как на экране."""
    try:
        import xlsxwriter
    except ImportError:
        current_app.logger.error("xlsxwriter not available")
        raise
    
    def round_val(val):
        return round_value(val, rounding_digits)
    
    # Обработка параметра aggregation_types (ees/tites/russia + sync_area_{id})
    if aggregation_types is None:
        aggregation_types = ["ees"]  # По умолчанию только ЕЭС

    valid_types = ["fo", "ees", "tites", "russia"]
    filtered_aggregation_types = []
    for at in aggregation_types:
        if at in valid_types:
            filtered_aggregation_types.append(at)
        elif isinstance(at, str) and at.startswith("sync_area_"):
            try:
                int(at.replace("sync_area_", ""))
                filtered_aggregation_types.append(at)
            except ValueError:
                pass
    aggregation_types = filtered_aggregation_types
    if not aggregation_types:
        aggregation_types = ["ees"]
    
    try:
        # Получаем данные (аналогично totals_summary роуту)
        filters = {}
        station_ids = get_filtered_station_ids(filters)
        rows = get_full_aggregation_rows(start_year, end_year, station_ids, filters)
        all_aggregations = aggregate_all_at_once(rows)
        
        # Строим агрегаты
        energy_system_type_aggregates = build_energy_system_type_aggregates(all_aggregations)
        total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(all_aggregations)
        synchronous_area_aggregates = build_synchronous_area_aggregates(all_aggregations)
        federal_district_aggregates = build_federal_district_aggregates(all_aggregations)
    
        # Получаем списки для имен
        energy_system_type_list = get_energy_system_type_list_full()
        energy_system_type_names = get_energy_system_type_map()
        sorted_energy_system_type_ids = sorted([est.id for est in energy_system_type_list if est.id])

        # Синхронные зоны: имена + порядок как на экране (Калининградская область первой)
        synchronous_area_list = get_synchronous_area_list_full()
        synchronous_area_names = {sa.id: sa.name for sa in synchronous_area_list if sa.id}
        _sa_ids = [sa.id for sa in synchronous_area_list if sa.id and sa.id > 0]
        _kaliningrad_ids = []
        try:
            rd_query = filter_by_db_version(RegionalDistrict.query, RegionalDistrict)
            rd_sa_ids = (
                rd_query.filter(RegionalDistrict.region_number.in_(["39", "039"]))
                .with_entities(RegionalDistrict.id_synchronous_area)
                .all()
            )
            _kaliningrad_ids = [sa_id for (sa_id,) in rd_sa_ids if sa_id]
        except Exception:
            _kaliningrad_ids = []
        if not _kaliningrad_ids:
            for _sa in synchronous_area_list:
                try:
                    _sid = _sa.id
                    _name_l = (_sa.name or "").lower()
                except Exception:
                    continue
                if _sid and _sid > 0 and ("калининград" in _name_l):
                    _kaliningrad_ids.append(_sid)
        _kaliningrad_ids = sorted(set([i for i in _kaliningrad_ids if i in set(_sa_ids)]))
        _rest_ids = sorted([i for i in _sa_ids if i not in set(_kaliningrad_ids)])
        sorted_synchronous_area_ids = _kaliningrad_ids + _rest_ids

        # Федеральные округа: список + имена (порядок: display_order ASC)
        federal_district_list = get_federal_district_list_full()
        federal_district_names = get_federal_districts_map()
        _fd_sorted = sorted(
            federal_district_list,
            key=lambda fd: (
                fd.display_order is None,
                fd.display_order if fd.display_order is not None else 0,
                (fd.name or ""),
                fd.id or 0,
            ),
        )
        sorted_federal_district_ids = [fd.id for fd in _fd_sorted if fd.id and fd.id > 0]
        
        # Формируем should_show_totals в зависимости от выбранных типов агрегации
        should_show_totals = {
            "energy_system_types": {},
            "synchronous_areas": {},
            "federal_districts": False,
            "total": False,
        }
        
        # Проверяем каждый выбранный тип агрегации
        if "russia" in aggregation_types:
            should_show_totals["total"] = True

        if "fo" in aggregation_types:
            should_show_totals["federal_districts"] = True
        
        # Показываем выбранные типы энергосистем (ЕЭС и/или ТИТЭС)
        for est_id in sorted_energy_system_type_ids:
            es_type_name = energy_system_type_names.get(est_id, "")
            if "ees" in aggregation_types and "ЕЭС" in es_type_name:
                should_show_totals["energy_system_types"][est_id] = True
            if "tites" in aggregation_types and "ТИТЭС" in es_type_name:
                should_show_totals["energy_system_types"][est_id] = True

        # Показываем выбранные синхронные зоны (aggregation_type = "sync_area_{id}")
        for sa_id in sorted_synchronous_area_ids:
            if f"sync_area_{sa_id}" in aggregation_types:
                should_show_totals["synchronous_areas"][sa_id] = True
        
        # Получаем типы для шаблона
        station_type_query = StationType.query
        station_type_query = filter_by_db_version(station_type_query, StationType)
        station_type_names = station_type_query.order_by(StationType.id.asc()).all()
        station_type_list = {st.id: st.name for st in station_type_names}
        
        tes_type_query = TesType.query
        tes_type_query = filter_by_db_version(tes_type_query, TesType)
        tes_type_names = tes_type_query.order_by(TesType.id.asc()).all()
        tes_type_list = {tt.id: tt.name for tt in tes_type_names}
        
        tes_machine_type_query = TesMachineType.query
        tes_machine_type_query = filter_by_db_version(tes_machine_type_query, TesMachineType)
        tes_machine_type_names = tes_machine_type_query.order_by(TesMachineType.id.asc()).all()
        tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}
        
        fuel_type_query = FuelType.query
        fuel_type_query = filter_by_db_version(fuel_type_query, FuelType)
        fuel_type_names = fuel_type_query.order_by(FuelType.id.asc()).all()
        fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}
        fuel_type_items_sorted = sorted(
            fuel_type_list.items(),
            key=lambda item: (item[0], (item[1] or "")),
        )
        
        year_features = get_year_feature_dict()
        
        # Создаем Excel файл
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Итоговые суммы")
        
        # Стили
        header_format = workbook.add_format({
        "bold": True,
        "bg_color": "#d1e7dd",  # table-success цвет
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        })
        
        # Цвета для разных типов энергосистем
        ees_format = workbook.add_format({
        "bg_color": "#cfe2ff",  # table-info (голубой)
        "align": "center",
        "valign": "vcenter",
        "border": 1,
        })
        
        ees_bold_format = workbook.add_format({
            "bold": True,
            "bg_color": "#cfe2ff",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        
        tites_format = workbook.add_format({
            "bg_color": "#fff3cd",  # table-warning (желтый)
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        
        tites_bold_format = workbook.add_format({
            "bold": True,
            "bg_color": "#fff3cd",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        
        russia_format = workbook.add_format({
            "bg_color": "#f8d7da",  # table-danger (красный)
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        
        russia_bold_format = workbook.add_format({
            "bold": True,
            "bg_color": "#f8d7da",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        
        # Числовые форматы для ячеек с мощностью
        # Определяем формат в зависимости от округления
        if rounding_digits == -1:
            num_format_str = "#,##0"  # Целое число
        elif rounding_digits == 0:
            num_format_str = "#,##0"  # Без десятичных знаков
        else:
            num_format_str = f"#,##0.{'0' * rounding_digits}"  # С десятичными знаками
        
        # Создаем числовые форматы с цветами фона
        ees_num_format = workbook.add_format({
            "bg_color": "#cfe2ff",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        ees_bold_num_format = workbook.add_format({
            "bold": True,
            "bg_color": "#cfe2ff",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        tites_num_format = workbook.add_format({
            "bg_color": "#fff3cd",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        tites_bold_num_format = workbook.add_format({
            "bold": True,
            "bg_color": "#fff3cd",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        russia_num_format = workbook.add_format({
            "bg_color": "#f8d7da",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        russia_bold_num_format = workbook.add_format({
            "bold": True,
            "bg_color": "#f8d7da",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })

        # Цвета/форматы для синхронных зон (table-secondary)
        sync_bg = "#e2e3e5"
        sync_format = workbook.add_format({
            "bg_color": sync_bg,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        sync_bold_format = workbook.add_format({
            "bold": True,
            "bg_color": sync_bg,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        sync_num_format = workbook.add_format({
            "bg_color": sync_bg,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        sync_bold_num_format = workbook.add_format({
            "bold": True,
            "bg_color": sync_bg,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "num_format": num_format_str,
        })
        
        # Форматы для столбца A (Энергосистема) с выравниванием по левому краю
        ees_format_left = workbook.add_format({
            "bg_color": "#cfe2ff",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        ees_bold_format_left = workbook.add_format({
            "bold": True,
            "bg_color": "#cfe2ff",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        tites_format_left = workbook.add_format({
            "bg_color": "#fff3cd",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        tites_bold_format_left = workbook.add_format({
            "bold": True,
            "bg_color": "#fff3cd",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        russia_format_left = workbook.add_format({
            "bg_color": "#f8d7da",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        russia_bold_format_left = workbook.add_format({
            "bold": True,
            "bg_color": "#f8d7da",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })

        sync_format_left = workbook.add_format({
            "bg_color": sync_bg,
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        sync_bold_format_left = workbook.add_format({
            "bold": True,
            "bg_color": sync_bg,
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        header_format_left = workbook.add_format({
            "bold": True,
            "bg_color": "#d1e7dd",
            "align": "left",
            "valign": "vcenter",
            "border": 1,
        })
        
        # Заголовки
        row = 0
        col = 0
        
        worksheet.write(row, col, "Энергосистема", header_format_left)
        worksheet.write(row, col + 1, "Тип мощ-ти", header_format)
        col += 2
        
        for year in range(start_year, end_year + 1):
            year_label = str(year)
            if year in year_features:
                year_label += f"\n{year_features[year]}"
            worksheet.write(row, col, year_label, header_format)
            col += 1
        
        row += 1
        current_row = row
        
        # Функция для записи строки с данными
        def write_power_row(row_num, col_start, label, values, format_style, rowspan=1):
            """Записывает строку с мощностью."""
            col = col_start
            worksheet.write(row_num, col, label, format_style)
            if rowspan > 1:
                worksheet.merge_range(row_num, col, row_num + rowspan - 1, col, label, format_style)
            col += 1
            worksheet.write(row_num, col, "Руст", format_style)
            col += 1
            
            for year in range(start_year, end_year + 1):
                val = values.get(year, 0)
                formatted = format_value(val, rounding_digits)
                worksheet.write(row_num, col, formatted, format_style)
                col += 1
            
            row_num += 1
            
            # Строка Рогр (если нужно)
            if show_p_ogr:
                col = col_start + 1
                worksheet.write(row_num, col, "Рогр", format_style)
                col += 1
                for year in range(start_year, end_year + 1):
                    val = values.get(year, 0)  # Будет переопределено ниже
                    formatted = format_value(val, rounding_digits)
                    worksheet.write(row_num, col, formatted, format_style)
                    col += 1
                row_num += 1
            
            # Строка Ррасп (если нужно)
            if show_p_rasp:
                col = col_start + 1
                worksheet.write(row_num, col, "Ррасп", format_style)
                col += 1
                for year in range(start_year, end_year + 1):
                    val = values.get(year, 0)  # Будет переопределено ниже
                    formatted = format_value(val, rounding_digits)
                    worksheet.write(row_num, col, formatted, format_style)
                    col += 1
                row_num += 1
            
            return row_num
        
        # Функция для записи строки с данными (с отдельными словарями для p_ogr и p_rasp)
        def write_power_row_with_separate_dicts(row_num, col_start, label, p_ust_dict, p_ogr_dict, p_rasp_dict, format_style, num_format_style, rowspan=1, indent_level=0):
            """Записывает строку с мощностью, используя отдельные словари для каждого типа.
            indent_level: 0 - без отступа, 1 - 3 пробела (типы ТЭС, ВЭС/СЭС), 2 - 6 пробелов (типы агрегатов), 3 - 9 пробелов (топливо)
            num_format_style - числовой формат для ячеек с данными
            """
            col = col_start
            
            # Определяем отступ в зависимости от уровня
            if indent_level == 0:
                indent_str = ""
            elif indent_level == 1:
                indent_str = "   "  # 3 пробела для визуального отступа
            elif indent_level == 2:
                indent_str = "      "  # 6 пробелов
            elif indent_level == 3:
                indent_str = "         "  # 9 пробелов
            else:
                indent_str = "            "  # 12 пробелов для топлива
            
            label_with_indent = f"{indent_str}{label}"
            
            # Определяем формат для столбца A (Энергосистема) с выравниванием по левому краю
            # Создаем формат на основе переданного format_style, но с выравниванием по левому краю
            if format_style == ees_bold_format:
                label_format = ees_bold_format_left
            elif format_style == ees_format:
                label_format = ees_format_left
            elif format_style == tites_bold_format:
                label_format = tites_bold_format_left
            elif format_style == tites_format:
                label_format = tites_format_left
            elif format_style == russia_bold_format:
                label_format = russia_bold_format_left
            elif format_style == russia_format:
                label_format = russia_format_left
            elif format_style == header_format:
                label_format = header_format_left
            elif format_style == sync_bold_format:
                label_format = sync_bold_format_left
            elif format_style == sync_format:
                label_format = sync_format_left
            else:
                label_format = format_style  # Если формат не распознан, используем исходный
            
            worksheet.write(row_num, col, label_with_indent, label_format)
            if rowspan > 1:
                worksheet.merge_range(row_num, col, row_num + rowspan - 1, col, label_with_indent, label_format)
            col += 1
            worksheet.write(row_num, col, "Руст", format_style)
            col += 1
            
            for year in range(start_year, end_year + 1):
                val = p_ust_dict.get(year, 0)
                if val is None or val == 0:
                    worksheet.write(row_num, col, "", num_format_style)
                else:
                    rounded_val = round_value(val, rounding_digits)
                    if rounded_val is None:
                        worksheet.write(row_num, col, "", num_format_style)
                    else:
                        worksheet.write_number(row_num, col, float(rounded_val), num_format_style)
                col += 1
            
            row_num += 1
            
            # Строка Рогр (если нужно)
            if show_p_ogr:
                col = col_start + 1
                worksheet.write(row_num, col, "Рогр", format_style)
                col += 1
                for year in range(start_year, end_year + 1):
                    val = p_ogr_dict.get(year, 0)
                    if val is None or val == 0:
                        worksheet.write(row_num, col, "", num_format_style)
                    else:
                        rounded_val = round_value(val, rounding_digits)
                        if rounded_val is None:
                            worksheet.write(row_num, col, "", num_format_style)
                        else:
                            worksheet.write_number(row_num, col, float(rounded_val), num_format_style)
                    col += 1
                row_num += 1
            
            # Строка Ррасп (если нужно)
            if show_p_rasp:
                col = col_start + 1
                worksheet.write(row_num, col, "Ррасп", format_style)
                col += 1
                for year in range(start_year, end_year + 1):
                    val = p_rasp_dict.get(year, 0)
                    if val is None or val == 0:
                        worksheet.write(row_num, col, "", num_format_style)
                    else:
                        rounded_val = round_value(val, rounding_digits)
                        if rounded_val is None:
                            worksheet.write(row_num, col, "", num_format_style)
                        else:
                            worksheet.write_number(row_num, col, float(rounded_val), num_format_style)
                    col += 1
                row_num += 1
            
            return row_num
        
        # Получаем словари данных
        p_ust_dict = energy_system_type_aggregates.get("energy_system_types_yearly_p_ust", {})
        p_ogr_dict = energy_system_type_aggregates.get("energy_system_types_yearly_p_ogr", {})
        p_rasp_dict = energy_system_type_aggregates.get("energy_system_types_yearly_p_rasp", {})
        
        by_station_types_p_ust = energy_system_type_aggregates.get("energy_system_types_by_station_types_yearly_p_ust", {})
        by_station_types_p_ogr = energy_system_type_aggregates.get("energy_system_types_by_station_types_yearly_p_ogr", {})
        by_station_types_p_rasp = energy_system_type_aggregates.get("energy_system_types_by_station_types_yearly_p_rasp", {})
        
        by_tes_types_p_ust = energy_system_type_aggregates.get("energy_system_types_by_tes_types_yearly_p_ust", {})
        by_tes_types_p_ogr = energy_system_type_aggregates.get("energy_system_types_by_tes_types_yearly_p_ogr", {})
        by_tes_types_p_rasp = energy_system_type_aggregates.get("energy_system_types_by_tes_types_yearly_p_rasp", {})
        
        by_tes_machine_types_p_ust = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_yearly_p_ust", {})
        by_tes_machine_types_p_ogr = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_yearly_p_ogr", {})
        by_tes_machine_types_p_rasp = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_yearly_p_rasp", {})
        
        by_tes_machine_types_with_fuel_p_ust = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust", {})
        by_tes_machine_types_with_fuel_p_ogr = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr", {})
        by_tes_machine_types_with_fuel_p_rasp = energy_system_type_aggregates.get("energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp", {})

        # Синхронные зоны: словари данных
        sa_p_ust_dict = synchronous_area_aggregates.get("synchronous_areas_yearly_p_ust", {})
        sa_p_ogr_dict = synchronous_area_aggregates.get("synchronous_areas_yearly_p_ogr", {})
        sa_p_rasp_dict = synchronous_area_aggregates.get("synchronous_areas_yearly_p_rasp", {})

        sa_by_station_types_p_ust = synchronous_area_aggregates.get("synchronous_areas_by_station_types_yearly_p_ust", {})
        sa_by_station_types_p_ogr = synchronous_area_aggregates.get("synchronous_areas_by_station_types_yearly_p_ogr", {})
        sa_by_station_types_p_rasp = synchronous_area_aggregates.get("synchronous_areas_by_station_types_yearly_p_rasp", {})

        sa_by_tes_types_p_ust = synchronous_area_aggregates.get("synchronous_areas_by_tes_types_yearly_p_ust", {})
        sa_by_tes_types_p_ogr = synchronous_area_aggregates.get("synchronous_areas_by_tes_types_yearly_p_ogr", {})
        sa_by_tes_types_p_rasp = synchronous_area_aggregates.get("synchronous_areas_by_tes_types_yearly_p_rasp", {})

        sa_by_tes_machine_types_p_ust = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_yearly_p_ust", {})
        sa_by_tes_machine_types_p_ogr = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_yearly_p_ogr", {})
        sa_by_tes_machine_types_p_rasp = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_yearly_p_rasp", {})

        sa_by_tes_machine_types_with_fuel_p_ust = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_ust", {})
        sa_by_tes_machine_types_with_fuel_p_ogr = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_ogr", {})
        sa_by_tes_machine_types_with_fuel_p_rasp = synchronous_area_aggregates.get("synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_rasp", {})

        # Федеральные округа: словари данных (только итоги)
        fd_p_ust_dict = federal_district_aggregates.get("federal_districts_yearly_p_ust", {})
        fd_p_ogr_dict = federal_district_aggregates.get("federal_districts_yearly_p_ogr", {})
        fd_p_rasp_dict = federal_district_aggregates.get("federal_districts_yearly_p_rasp", {})

        # Федеральные округа: детализация (как для ЕЭС)
        fd_by_station_types_p_ust = federal_district_aggregates.get(
            "federal_districts_by_station_types_yearly_p_ust", {}
        )
        fd_by_station_types_p_ogr = federal_district_aggregates.get(
            "federal_districts_by_station_types_yearly_p_ogr", {}
        )
        fd_by_station_types_p_rasp = federal_district_aggregates.get(
            "federal_districts_by_station_types_yearly_p_rasp", {}
        )

        fd_by_tes_types_p_ust = federal_district_aggregates.get(
            "federal_districts_by_tes_types_yearly_p_ust", {}
        )
        fd_by_tes_types_p_ogr = federal_district_aggregates.get(
            "federal_districts_by_tes_types_yearly_p_ogr", {}
        )
        fd_by_tes_types_p_rasp = federal_district_aggregates.get(
            "federal_districts_by_tes_types_yearly_p_rasp", {}
        )

        fd_by_tes_machine_types_p_ust = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_yearly_p_ust", {}
        )
        fd_by_tes_machine_types_p_ogr = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_yearly_p_ogr", {}
        )
        fd_by_tes_machine_types_p_rasp = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_yearly_p_rasp", {}
        )

        fd_by_tes_machine_types_with_fuel_p_ust = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_with_fuel_yearly_p_ust", {}
        )
        fd_by_tes_machine_types_with_fuel_p_ogr = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_with_fuel_yearly_p_ogr", {}
        )
        fd_by_tes_machine_types_with_fuel_p_rasp = federal_district_aggregates.get(
            "federal_districts_by_tes_machine_types_with_fuel_yearly_p_rasp", {}
        )
        
        # Находим ID для ВЭС, СЭС и ТЭС
        ves_id = None
        ses_id = None
        tes_id = None
        for st_id, st_name in station_type_list.items():
            if st_name == 'ВЭС':
                ves_id = st_id
            elif st_name == 'СЭС':
                ses_id = st_id
            elif st_name == 'ТЭС':
                tes_id = st_id
        
        # Функция для сортировки типов станций
        def station_type_order(name: str) -> int:
            n = (name or "").lower()
            if "аэс" in n:
                return 0
            if "гэс" in n and "гаэс" not in n:
                return 1
            if "гаэс" in n:
                return 2
            if "тэс" in n:
                return 3
            if "вэс" in n or "сэс" in n or "виэ" in n:
                return 4
            return 9
        
        # ----------------------------
        # Сначала федеральные округа (ФО)
        # ----------------------------
        if should_show_totals.get("federal_districts"):
            for fd_id in sorted_federal_district_ids:
                if fd_id not in fd_p_ust_dict:
                    continue
                fd_name = federal_district_names.get(fd_id, f"ФО {fd_id}")

                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                current_row = write_power_row_with_separate_dicts(
                    current_row,
                    0,
                    f"{fd_name}, всего",
                    fd_p_ust_dict.get(fd_id, {}),
                    fd_p_ogr_dict.get(fd_id, {}),
                    fd_p_rasp_dict.get(fd_id, {}),
                    sync_bold_format,
                    sync_bold_num_format,
                    rowspan,
                    indent_level=0,
                )

                # Разбивка по типам станций
                st_dict = fd_by_station_types_p_ust.get(fd_id, {})
                st_dict_ogr = fd_by_station_types_p_ogr.get(fd_id, {})
                st_dict_rasp = fd_by_station_types_p_rasp.get(fd_id, {})

                # ВИЭ (ВЭС/СЭС)
                vie_aggregated = {
                    "p_ust": defaultdict(lambda: Decimal(0)),
                    "p_ogr": defaultdict(lambda: Decimal(0)),
                    "p_rasp": defaultdict(lambda: Decimal(0)),
                }
                vie_station_type_ids = []
                for st_id, st_name in station_type_list.items():
                    if st_name and ("вэс" in st_name.lower() or "сэс" in st_name.lower() or "виэ" in st_name.lower()):
                        vie_station_type_ids.append(st_id)
                        if st_id in st_dict:
                            for year, val in st_dict[st_id].items():
                                vie_aggregated["p_ust"][year] += val or Decimal(0)
                        if st_id in st_dict_ogr:
                            for year, val in st_dict_ogr.get(st_id, {}).items():
                                vie_aggregated["p_ogr"][year] += val or Decimal(0)
                        if st_id in st_dict_rasp:
                            for year, val in st_dict_rasp.get(st_id, {}).items():
                                vie_aggregated["p_rasp"][year] += val or Decimal(0)

                station_type_items_sorted = sorted(
                    st_dict.items(),
                    key=lambda item: (
                        station_type_order(station_type_list.get(item[0], f"id={item[0]}")),
                        station_type_list.get(item[0], "")
                    )
                )

                # Типы станций (без ВЭС/СЭС)
                for station_type_id, st_years in station_type_items_sorted:
                    if station_type_id is None or station_type_id in vie_station_type_ids:
                        continue
                    station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                    if "не указано" in station_type_name.lower():
                        continue

                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, station_type_name,
                        st_years,
                        st_dict_ogr.get(station_type_id, {}),
                        st_dict_rasp.get(station_type_id, {}),
                        sync_format, sync_num_format, rowspan, indent_level=0
                    )

                    # Если это ТЭС — детализация по типам ТЭС -> типам машин -> топливу
                    if station_type_id == tes_id:
                        for tes_type_id, tes_name in tes_type_list.items():
                            if (tes_name or "").lower() == "не указано":
                                continue
                            has_tes = fd_by_tes_types_p_ust.get(fd_id, {}).get(tes_type_id)
                            if not has_tes:
                                continue

                            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                            current_row = write_power_row_with_separate_dicts(
                                current_row, 0, tes_name,
                                fd_by_tes_types_p_ust.get(fd_id, {}).get(tes_type_id, {}),
                                fd_by_tes_types_p_ogr.get(fd_id, {}).get(tes_type_id, {}),
                                fd_by_tes_types_p_rasp.get(fd_id, {}).get(tes_type_id, {}),
                                sync_format, sync_num_format, rowspan, indent_level=1
                            )

                            # Типы машин ТЭС
                            mt_dict = fd_by_tes_machine_types_p_ust.get(fd_id, {}).get(tes_type_id, {})
                            mt_dict_ogr = fd_by_tes_machine_types_p_ogr.get(fd_id, {}).get(tes_type_id, {})
                            mt_dict_rasp = fd_by_tes_machine_types_p_rasp.get(fd_id, {}).get(tes_type_id, {})

                            for tm_id, tm_name in tes_machine_type_list.items():
                                if (tm_name or "").lower() == "не указано":
                                    continue
                                has_tm = mt_dict.get(tm_id)
                                if not has_tm:
                                    continue

                                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                current_row = write_power_row_with_separate_dicts(
                                    current_row, 0, tm_name,
                                    mt_dict.get(tm_id, {}),
                                    mt_dict_ogr.get(tm_id, {}),
                                    mt_dict_rasp.get(tm_id, {}),
                                    sync_format, sync_num_format, rowspan, indent_level=2
                                )

                                # Топливо
                                fuel_dict = fd_by_tes_machine_types_with_fuel_p_ust.get(fd_id, {}).get(tes_type_id, {}).get(tm_id, {})
                                fuel_dict_ogr = fd_by_tes_machine_types_with_fuel_p_ogr.get(fd_id, {}).get(tes_type_id, {}).get(tm_id, {})
                                fuel_dict_rasp = fd_by_tes_machine_types_with_fuel_p_rasp.get(fd_id, {}).get(tes_type_id, {}).get(tm_id, {})

                                for fuel_type_id, fuel_name in fuel_type_items_sorted:
                                    has_fuel = fuel_dict.get(fuel_type_id)
                                    if not has_fuel:
                                        continue
                                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                    current_row = write_power_row_with_separate_dicts(
                                        current_row, 0, fuel_name,
                                        fuel_dict.get(fuel_type_id, {}),
                                        fuel_dict_ogr.get(fuel_type_id, {}),
                                        fuel_dict_rasp.get(fuel_type_id, {}),
                                        sync_format, sync_num_format, rowspan, indent_level=3
                                    )

                # ВИЭ суммарно + ВЭС/СЭС
                if vie_aggregated["p_ust"]:
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, "ВИЭ",
                        dict(vie_aggregated["p_ust"]),
                        dict(vie_aggregated["p_ogr"]),
                        dict(vie_aggregated["p_rasp"]),
                        sync_format, sync_num_format, rowspan, indent_level=0
                    )
                    for station_type_id in vie_station_type_ids:
                        if station_type_id not in st_dict:
                            continue
                        station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                        if "не указано" in station_type_name.lower():
                            continue
                        rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                        current_row = write_power_row_with_separate_dicts(
                            current_row, 0, station_type_name,
                            st_dict.get(station_type_id, {}),
                            st_dict_ogr.get(station_type_id, {}),
                            st_dict_rasp.get(station_type_id, {}),
                            sync_format, sync_num_format, rowspan, indent_level=1
                        )

                current_row += 1  # пустая строка между ФО
            current_row += 1  # пустая строка после ФО

        # ----------------------------
        # Затем синхронные зоны (как на экране)
        # ----------------------------
        for sa_id in sorted_synchronous_area_ids:
            if not should_show_totals["synchronous_areas"].get(sa_id, False):
                continue

            sa_name = synchronous_area_names.get(sa_id, f"Синхронная зона {sa_id}")
            if sa_id not in sa_p_ust_dict:
                continue

            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
            current_row = write_power_row_with_separate_dicts(
                current_row, 0, f"{sa_name}, всего",
                sa_p_ust_dict.get(sa_id, {}),
                sa_p_ogr_dict.get(sa_id, {}),
                sa_p_rasp_dict.get(sa_id, {}),
                sync_bold_format, sync_bold_num_format, rowspan, indent_level=0
            )

            # Разбивка по типам станций
            st_dict = sa_by_station_types_p_ust.get(sa_id, {})
            st_dict_ogr = sa_by_station_types_p_ogr.get(sa_id, {})
            st_dict_rasp = sa_by_station_types_p_rasp.get(sa_id, {})

            # ВИЭ (ВЭС/СЭС)
            vie_aggregated = {
                "p_ust": defaultdict(lambda: Decimal(0)),
                "p_ogr": defaultdict(lambda: Decimal(0)),
                "p_rasp": defaultdict(lambda: Decimal(0)),
            }
            vie_station_type_ids = []
            for st_id, st_name in station_type_list.items():
                if st_name and ("вэс" in st_name.lower() or "сэс" in st_name.lower() or "виэ" in st_name.lower()):
                    vie_station_type_ids.append(st_id)
                    if st_id in st_dict:
                        for year, val in st_dict[st_id].items():
                            vie_aggregated["p_ust"][year] += val or Decimal(0)
                    if st_id in st_dict_ogr:
                        for year, val in st_dict_ogr.get(st_id, {}).items():
                            vie_aggregated["p_ogr"][year] += val or Decimal(0)
                    if st_id in st_dict_rasp:
                        for year, val in st_dict_rasp.get(st_id, {}).items():
                            vie_aggregated["p_rasp"][year] += val or Decimal(0)

            station_type_items_sorted = sorted(
                st_dict.items(),
                key=lambda item: (
                    station_type_order(station_type_list.get(item[0], f"id={item[0]}")),
                    station_type_list.get(item[0], "")
                )
            )

            # Типы станций (без ВЭС/СЭС)
            for station_type_id, st_years in station_type_items_sorted:
                if station_type_id is None or station_type_id in vie_station_type_ids:
                    continue
                station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                if "не указано" in station_type_name.lower():
                    continue

                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                current_row = write_power_row_with_separate_dicts(
                    current_row, 0, station_type_name,
                    st_years,
                    st_dict_ogr.get(station_type_id, {}),
                    st_dict_rasp.get(station_type_id, {}),
                    sync_format, sync_num_format, rowspan, indent_level=0
                )

                # Если это ТЭС — детализация по типам ТЭС -> типам машин -> топливу (как на экране)
                if station_type_id == tes_id:
                    for tes_type_id, tes_name in tes_type_list.items():
                        if (tes_name or "").lower() == "не указано":
                            continue
                        has_tes = sa_by_tes_types_p_ust.get(sa_id, {}).get(tes_type_id)
                        if not has_tes:
                            continue

                        rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                        current_row = write_power_row_with_separate_dicts(
                            current_row, 0, tes_name,
                            sa_by_tes_types_p_ust.get(sa_id, {}).get(tes_type_id, {}),
                            sa_by_tes_types_p_ogr.get(sa_id, {}).get(tes_type_id, {}),
                            sa_by_tes_types_p_rasp.get(sa_id, {}).get(tes_type_id, {}),
                            sync_format, sync_num_format, rowspan, indent_level=1
                        )

                        # Типы машин ТЭС
                        mt_dict = sa_by_tes_machine_types_p_ust.get(sa_id, {}).get(tes_type_id, {})
                        mt_dict_ogr = sa_by_tes_machine_types_p_ogr.get(sa_id, {}).get(tes_type_id, {})
                        mt_dict_rasp = sa_by_tes_machine_types_p_rasp.get(sa_id, {}).get(tes_type_id, {})

                        for tm_id, tm_name in tes_machine_type_list.items():
                            if (tm_name or "").lower() == "не указано":
                                continue
                            has_tm = mt_dict.get(tm_id)
                            if not has_tm:
                                continue

                            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                            current_row = write_power_row_with_separate_dicts(
                                current_row, 0, tm_name,
                                mt_dict.get(tm_id, {}),
                                mt_dict_ogr.get(tm_id, {}),
                                mt_dict_rasp.get(tm_id, {}),
                                sync_format, sync_num_format, rowspan, indent_level=2
                            )

                            # Топливо
                            fuel_dict = sa_by_tes_machine_types_with_fuel_p_ust.get(sa_id, {}).get(tes_type_id, {}).get(tm_id, {})
                            fuel_dict_ogr = sa_by_tes_machine_types_with_fuel_p_ogr.get(sa_id, {}).get(tes_type_id, {}).get(tm_id, {})
                            fuel_dict_rasp = sa_by_tes_machine_types_with_fuel_p_rasp.get(sa_id, {}).get(tes_type_id, {}).get(tm_id, {})

                            for fuel_type_id, fuel_name in fuel_type_items_sorted:
                                has_fuel = fuel_dict.get(fuel_type_id)
                                if not has_fuel:
                                    continue
                                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                current_row = write_power_row_with_separate_dicts(
                                    current_row, 0, fuel_name,
                                    fuel_dict.get(fuel_type_id, {}),
                                    fuel_dict_ogr.get(fuel_type_id, {}),
                                    fuel_dict_rasp.get(fuel_type_id, {}),
                                    sync_format, sync_num_format, rowspan, indent_level=3
                                )

            # ВИЭ суммарно + ВЭС/СЭС
            if vie_aggregated["p_ust"]:
                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                current_row = write_power_row_with_separate_dicts(
                    current_row, 0, "ВИЭ",
                    dict(vie_aggregated["p_ust"]),
                    dict(vie_aggregated["p_ogr"]),
                    dict(vie_aggregated["p_rasp"]),
                    sync_format, sync_num_format, rowspan, indent_level=0
                )
                for station_type_id in vie_station_type_ids:
                    if station_type_id not in st_dict:
                        continue
                    station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                    if "не указано" in station_type_name.lower():
                        continue
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, station_type_name,
                        st_dict.get(station_type_id, {}),
                        st_dict_ogr.get(station_type_id, {}),
                        st_dict_rasp.get(station_type_id, {}),
                        sync_format, sync_num_format, rowspan, indent_level=1
                    )

            current_row += 1  # пустая строка между синхронными зонами

        # ----------------------------
        # Затем типы энергосистем (ЕЭС/ТИТЭС)
        # ----------------------------
        # Записываем итоги по типам энергосистем (только выбранные)
        for es_type_id in sorted_energy_system_type_ids:
            # Пропускаем, если этот тип не выбран для отображения
            if not should_show_totals["energy_system_types"].get(es_type_id, False):
                continue
                
            es_type_name = energy_system_type_names.get(es_type_id, f"Тип {es_type_id}")
            if es_type_id not in p_ust_dict:
                continue
            
            # Определяем цвет
            if 'ЕЭС' in es_type_name:
                cell_format = ees_bold_format
                row_format = ees_format
                num_cell_format = ees_bold_num_format
                num_row_format = ees_num_format
            elif 'ТИТЭС' in es_type_name:
                cell_format = tites_bold_format
                row_format = tites_format
                num_cell_format = tites_bold_num_format
                num_row_format = tites_num_format
            else:
                cell_format = ees_bold_format
                row_format = ees_format
                num_cell_format = ees_bold_num_format
                num_row_format = ees_num_format
            
            # Итог по типу энергосистемы
            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
            es_p_ust = p_ust_dict.get(es_type_id, {})
            es_p_ogr = p_ogr_dict.get(es_type_id, {})
            es_p_rasp = p_rasp_dict.get(es_type_id, {})
            
            current_row = write_power_row_with_separate_dicts(
                current_row, 0, f"{es_type_name}, всего", 
                es_p_ust, es_p_ogr, es_p_rasp, cell_format, num_cell_format, rowspan, indent_level=0
            )
            
            # Разбивка по типам станций
            st_dict = by_station_types_p_ust.get(es_type_id, {})
            st_dict_ogr = by_station_types_p_ogr.get(es_type_id, {})
            st_dict_rasp = by_station_types_p_rasp.get(es_type_id, {})
            
            # Объединяем ВЭС и СЭС в ВИЭ
            vie_aggregated = {
                "p_ust": defaultdict(lambda: Decimal(0)),
                "p_ogr": defaultdict(lambda: Decimal(0)),
                "p_rasp": defaultdict(lambda: Decimal(0))
            }
            vie_station_type_ids = []
            
            for st_id, st_name in station_type_list.items():
                if st_name and ("вэс" in st_name.lower() or "сэс" in st_name.lower() or "виэ" in st_name.lower()):
                    vie_station_type_ids.append(st_id)
                    if st_id in st_dict:
                        for year, val in st_dict[st_id].items():
                            vie_aggregated["p_ust"][year] += val or Decimal(0)
                    if st_id in st_dict_ogr:
                        for year, val in st_dict_ogr.get(st_id, {}).items():
                            vie_aggregated["p_ogr"][year] += val or Decimal(0)
                    if st_id in st_dict_rasp:
                        for year, val in st_dict_rasp.get(st_id, {}).items():
                            vie_aggregated["p_rasp"][year] += val or Decimal(0)
            
            # Сортируем типы станций
            station_type_items_sorted = sorted(
                st_dict.items(),
                key=lambda item: (
                    station_type_order(station_type_list.get(item[0], f"id={item[0]}")),
                    station_type_list.get(item[0], "")
                )
            )
            
            # Записываем типы станций (АЭС, ГЭС, ГАЭС, ТЭС) - исключая ВЭС и СЭС
            for station_type_id, st_years in station_type_items_sorted:
                if station_type_id is None or station_type_id in vie_station_type_ids:
                    continue
                
                station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                if "не указано" in station_type_name.lower():
                    continue
                
                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                st_p_ust = st_years
                st_p_ogr = st_dict_ogr.get(station_type_id, {})
                st_p_rasp = st_dict_rasp.get(station_type_id, {})
                
                current_row = write_power_row_with_separate_dicts(
                    current_row, 0, station_type_name,
                    st_p_ust, st_p_ogr, st_p_rasp, row_format, num_row_format, rowspan, indent_level=0
                )
                
                # Если это ТЭС, добавляем разбивку по типам ТЭС
                if station_type_id == tes_id:
                    # Получаем типы ТЭС из by_tes_machine_types для данного типа станции
                    # Структура: es_type_id -> station_type_id -> tes_type_id -> machine_type_id -> year
                    # Нужно получить уникальные tes_type_id и агрегировать по годам
                    tes_types_for_station = {}
                    tes_types_for_station_ogr = {}
                    tes_types_for_station_rasp = {}
                    
                    station_tes_machine_dict = by_tes_machine_types_p_ust.get(es_type_id, {}).get(station_type_id, {})
                    station_tes_machine_dict_ogr = by_tes_machine_types_p_ogr.get(es_type_id, {}).get(station_type_id, {})
                    station_tes_machine_dict_rasp = by_tes_machine_types_p_rasp.get(es_type_id, {}).get(station_type_id, {})
                    
                    # Агрегируем по типам ТЭС
                    for tes_type_id, machine_dict in station_tes_machine_dict.items():
                        if tes_type_id is None:
                            continue
                        
                        tes_types_for_station[tes_type_id] = defaultdict(lambda: Decimal(0))
                        for machine_type_id, years_dict in machine_dict.items():
                            for year, val in years_dict.items():
                                tes_types_for_station[tes_type_id][year] += val or Decimal(0)
                        
                        tes_types_for_station_ogr[tes_type_id] = defaultdict(lambda: Decimal(0))
                        machine_dict_ogr = station_tes_machine_dict_ogr.get(tes_type_id, {})
                        for machine_type_id, years_dict in machine_dict_ogr.items():
                            for year, val in years_dict.items():
                                tes_types_for_station_ogr[tes_type_id][year] += val or Decimal(0)
                        
                        tes_types_for_station_rasp[tes_type_id] = defaultdict(lambda: Decimal(0))
                        machine_dict_rasp = station_tes_machine_dict_rasp.get(tes_type_id, {})
                        for machine_type_id, years_dict in machine_dict_rasp.items():
                            for year, val in years_dict.items():
                                tes_types_for_station_rasp[tes_type_id][year] += val or Decimal(0)
                    
                    for tes_type_id, tt_years in tes_types_for_station.items():
                        if tes_type_id is None:
                            continue
                        
                        tes_type_name = tes_type_list.get(tes_type_id, f"id={tes_type_id}")
                        if "не указано" in tes_type_name.lower():
                            continue
                        
                        rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                        tt_p_ust = dict(tt_years)
                        tt_p_ogr = dict(tes_types_for_station_ogr.get(tes_type_id, {}))
                        tt_p_rasp = dict(tes_types_for_station_rasp.get(tes_type_id, {}))
                        
                        current_row = write_power_row_with_separate_dicts(
                            current_row, 0, tes_type_name,
                            tt_p_ust, tt_p_ogr, tt_p_rasp, row_format, num_row_format, rowspan, indent_level=1
                        )
                        
                        # Разбивка по типам агрегатов
                        mt_dict = by_tes_machine_types_p_ust.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {})
                        mt_dict_ogr = by_tes_machine_types_p_ogr.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {})
                        mt_dict_rasp = by_tes_machine_types_p_rasp.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {})
                        
                        for machine_type_id, mt_years in mt_dict.items():
                            if machine_type_id is None:
                                continue
                            
                            machine_type_name = tes_machine_type_list.get(machine_type_id, f"id={machine_type_id}")
                            if "не указано" in machine_type_name.lower():
                                continue
                            
                            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                            mt_p_ust = mt_years
                            mt_p_ogr = mt_dict_ogr.get(machine_type_id, {})
                            mt_p_rasp = mt_dict_rasp.get(machine_type_id, {})
                            
                            current_row = write_power_row_with_separate_dicts(
                                current_row, 0, machine_type_name,
                                mt_p_ust, mt_p_ogr, mt_p_rasp, row_format, num_row_format, rowspan, indent_level=2
                            )
                            
                            # Разбивка по типам топлива
                            fuel_dict = by_tes_machine_types_with_fuel_p_ust.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                            fuel_dict_ogr = by_tes_machine_types_with_fuel_p_ogr.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                            fuel_dict_rasp = by_tes_machine_types_with_fuel_p_rasp.get(es_type_id, {}).get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                            
                            for fuel_type_id, fuel_years in fuel_dict.items():
                                if fuel_type_id is None:
                                    continue
                                
                                fuel_type_name = fuel_type_list.get(fuel_type_id, f"id={fuel_type_id}")
                                
                                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                fuel_p_ust = fuel_years
                                fuel_p_ogr = fuel_dict_ogr.get(fuel_type_id, {})
                                fuel_p_rasp = fuel_dict_rasp.get(fuel_type_id, {})
                                
                                current_row = write_power_row_with_separate_dicts(
                                    current_row, 0, fuel_type_name,
                                    fuel_p_ust, fuel_p_ogr, fuel_p_rasp, row_format, num_row_format, rowspan, indent_level=3
                                )
            
            # Разбивка по типам ТЭС на уровне энергосистемы (после ГАЭС, перед ВИЭ)
            es_tes_types_p_ust = by_tes_types_p_ust.get(es_type_id, {})
            es_tes_types_p_ogr = by_tes_types_p_ogr.get(es_type_id, {})
            es_tes_types_p_rasp = by_tes_types_p_rasp.get(es_type_id, {})
            
            if es_tes_types_p_ust:
                for tes_type_id, tes_years in es_tes_types_p_ust.items():
                    if tes_type_id is None:
                        continue
                    
                    tes_type_name = tes_type_list.get(tes_type_id, f"id={tes_type_id}")
                    if "не указано" in tes_type_name.lower():
                        continue
                    
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    tes_p_ust = tes_years
                    tes_p_ogr = es_tes_types_p_ogr.get(tes_type_id, {})
                    tes_p_rasp = es_tes_types_p_rasp.get(tes_type_id, {})
                    
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, tes_type_name,
                        tes_p_ust, tes_p_ogr, tes_p_rasp, row_format, num_row_format, rowspan, indent_level=1
                    )
                    
                    # Разбивка по типам топлива для типа ТЭС на уровне энергосистемы
                    es_tes_types_with_fuel_p_ust = energy_system_type_aggregates.get("energy_system_types_by_tes_types_with_fuel_yearly_p_ust", {}).get(es_type_id, {}).get(tes_type_id, {})
                    es_tes_types_with_fuel_p_ogr = energy_system_type_aggregates.get("energy_system_types_by_tes_types_with_fuel_yearly_p_ogr", {}).get(es_type_id, {}).get(tes_type_id, {})
                    es_tes_types_with_fuel_p_rasp = energy_system_type_aggregates.get("energy_system_types_by_tes_types_with_fuel_yearly_p_rasp", {}).get(es_type_id, {}).get(tes_type_id, {})
                    
                    if es_tes_types_with_fuel_p_ust:
                        # Важно: сортировка топлива всегда одинаковая (по справочнику: id, затем name)
                        for fuel_type_id, fuel_type_name in fuel_type_items_sorted:
                            fuel_years = es_tes_types_with_fuel_p_ust.get(fuel_type_id)
                            if not fuel_years:
                                continue

                            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                            fuel_p_ust = fuel_years
                            fuel_p_ogr = es_tes_types_with_fuel_p_ogr.get(fuel_type_id, {})
                            fuel_p_rasp = es_tes_types_with_fuel_p_rasp.get(fuel_type_id, {})

                            current_row = write_power_row_with_separate_dicts(
                                current_row, 0, fuel_type_name,
                                fuel_p_ust, fuel_p_ogr, fuel_p_rasp, row_format, num_row_format, rowspan, indent_level=2
                            )
            
            # Добавляем суммарную строку ВИЭ (если есть)
            if vie_aggregated["p_ust"]:
                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                vie_p_ust = dict(vie_aggregated["p_ust"])
                vie_p_ogr = dict(vie_aggregated["p_ogr"])
                vie_p_rasp = dict(vie_aggregated["p_rasp"])
                
                current_row = write_power_row_with_separate_dicts(
                    current_row, 0, "ВИЭ",
                    vie_p_ust, vie_p_ogr, vie_p_rasp, row_format, num_row_format, rowspan, indent_level=0
                )
                
                # Добавляем отдельно ВЭС и СЭС после суммарной строки ВИЭ
                for station_type_id in vie_station_type_ids:
                    if station_type_id not in st_dict:
                        continue
                    
                    station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                    if "не указано" in station_type_name.lower():
                        continue
                    
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    st_p_ust = st_dict.get(station_type_id, {})
                    st_p_ogr = st_dict_ogr.get(station_type_id, {})
                    st_p_rasp = st_dict_rasp.get(station_type_id, {})
                    
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, station_type_name,
                        st_p_ust, st_p_ogr, st_p_rasp, row_format, num_row_format, rowspan, indent_level=1
                    )
            
            current_row += 1  # Пустая строка между типами энергосистем
        
        # Записываем итог по России (только если выбран)
        if should_show_totals["total"]:
            total_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_yearly_p_ust", {})
            total_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_yearly_p_ogr", {})
            total_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_yearly_p_rasp", {})
            
            if total_p_ust:
                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                current_row = write_power_row_with_separate_dicts(
                    current_row, 0, "Россия, всего",
                    total_p_ust, total_p_ogr, total_p_rasp, russia_bold_format, russia_bold_num_format, rowspan, indent_level=0
                )
                
                # Разбивка по типам станций для России
                total_by_st_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_station_types_yearly_p_ust", {})
                total_by_st_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_station_types_yearly_p_ogr", {})
                total_by_st_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_station_types_yearly_p_rasp", {})
                
                total_by_tes_types_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_ust", {})
                total_by_tes_types_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_ogr", {})
                total_by_tes_types_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_rasp", {})
                
                total_by_tes_machine_types_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_yearly_p_ust", {})
                total_by_tes_machine_types_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_yearly_p_ogr", {})
                total_by_tes_machine_types_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_yearly_p_rasp", {})
                
                total_by_tes_machine_types_with_fuel_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust", {})
                total_by_tes_machine_types_with_fuel_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr", {})
                total_by_tes_machine_types_with_fuel_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp", {})
                
                # Объединяем ВЭС и СЭС в ВИЭ для России
                vie_aggregated_russia = {
                    "p_ust": defaultdict(lambda: Decimal(0)),
                    "p_ogr": defaultdict(lambda: Decimal(0)),
                    "p_rasp": defaultdict(lambda: Decimal(0))
                }
                vie_station_type_ids_russia = []
                
                for st_id, st_name in station_type_list.items():
                    if st_name and ("вэс" in st_name.lower() or "сэс" in st_name.lower() or "виэ" in st_name.lower()):
                        vie_station_type_ids_russia.append(st_id)
                        if st_id in total_by_st_p_ust:
                            for year, val in total_by_st_p_ust[st_id].items():
                                vie_aggregated_russia["p_ust"][year] += val or Decimal(0)
                        if st_id in total_by_st_p_ogr:
                            for year, val in total_by_st_p_ogr.get(st_id, {}).items():
                                vie_aggregated_russia["p_ogr"][year] += val or Decimal(0)
                        if st_id in total_by_st_p_rasp:
                            for year, val in total_by_st_p_rasp.get(st_id, {}).items():
                                vie_aggregated_russia["p_rasp"][year] += val or Decimal(0)
                
                # Обрабатываем типы станций для России (структура плоская, без es_type_id)
                station_type_items_sorted = sorted(
                    total_by_st_p_ust.items(),
                    key=lambda item: (
                        station_type_order(station_type_list.get(item[0], f"id={item[0]}")),
                        station_type_list.get(item[0], "")
                    )
                )
                
                # Записываем типы станций для России (АЭС, ГЭС, ГАЭС, ТЭС) - исключая ВЭС и СЭС
                for station_type_id, st_years in station_type_items_sorted:
                    if station_type_id is None or station_type_id in vie_station_type_ids_russia:
                        continue
                    
                    station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                    if "не указано" in station_type_name.lower():
                        continue
                    
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    st_p_ust = st_years
                    st_p_ogr = total_by_st_p_ogr.get(station_type_id, {})
                    st_p_rasp = total_by_st_p_rasp.get(station_type_id, {})
                    
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, station_type_name,
                        st_p_ust, st_p_ogr, st_p_rasp, russia_format, russia_num_format, rowspan, indent_level=0
                    )
                    
                    # Если это ТЭС, добавляем разбивку по типам ТЭС
                    if station_type_id == tes_id:
                        # Получаем типы ТЭС из total_by_tes_machine_types для данного типа станции
                        # Структура: station_type_id -> tes_type_id -> machine_type_id -> year
                        # Нужно получить уникальные tes_type_id и агрегировать по годам
                        tes_types_for_station = {}
                        tes_types_for_station_ogr = {}
                        tes_types_for_station_rasp = {}
                        
                        station_tes_machine_dict = total_by_tes_machine_types_p_ust.get(station_type_id, {})
                        station_tes_machine_dict_ogr = total_by_tes_machine_types_p_ogr.get(station_type_id, {})
                        station_tes_machine_dict_rasp = total_by_tes_machine_types_p_rasp.get(station_type_id, {})
                        
                        # Агрегируем по типам ТЭС
                        for tes_type_id, machine_dict in station_tes_machine_dict.items():
                            if tes_type_id is None:
                                continue
                            
                            tes_types_for_station[tes_type_id] = defaultdict(lambda: Decimal(0))
                            for machine_type_id, years_dict in machine_dict.items():
                                for year, val in years_dict.items():
                                    tes_types_for_station[tes_type_id][year] += val or Decimal(0)
                            
                            tes_types_for_station_ogr[tes_type_id] = defaultdict(lambda: Decimal(0))
                            machine_dict_ogr = station_tes_machine_dict_ogr.get(tes_type_id, {})
                            for machine_type_id, years_dict in machine_dict_ogr.items():
                                for year, val in years_dict.items():
                                    tes_types_for_station_ogr[tes_type_id][year] += val or Decimal(0)
                            
                            tes_types_for_station_rasp[tes_type_id] = defaultdict(lambda: Decimal(0))
                            machine_dict_rasp = station_tes_machine_dict_rasp.get(tes_type_id, {})
                            for machine_type_id, years_dict in machine_dict_rasp.items():
                                for year, val in years_dict.items():
                                    tes_types_for_station_rasp[tes_type_id][year] += val or Decimal(0)
                        
                        for tes_type_id, tt_years in tes_types_for_station.items():
                            if tes_type_id is None:
                                continue
                            
                            tes_type_name = tes_type_list.get(tes_type_id, f"id={tes_type_id}")
                            if "не указано" in tes_type_name.lower():
                                continue
                            
                            rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                            tt_p_ust = dict(tt_years)
                            tt_p_ogr = dict(tes_types_for_station_ogr.get(tes_type_id, {}))
                            tt_p_rasp = dict(tes_types_for_station_rasp.get(tes_type_id, {}))
                            
                            current_row = write_power_row_with_separate_dicts(
                                current_row, 0, tes_type_name,
                                tt_p_ust, tt_p_ogr, tt_p_rasp, russia_format, russia_num_format, rowspan, indent_level=1
                            )
                            
                            # Разбивка по типам агрегатов для России
                            # Структура: station_type_id -> tes_type_id -> machine_type_id -> year
                            mt_dict = total_by_tes_machine_types_p_ust.get(station_type_id, {}).get(tes_type_id, {})
                            mt_dict_ogr = total_by_tes_machine_types_p_ogr.get(station_type_id, {}).get(tes_type_id, {})
                            mt_dict_rasp = total_by_tes_machine_types_p_rasp.get(station_type_id, {}).get(tes_type_id, {})
                            
                            for machine_type_id, mt_years in mt_dict.items():
                                if machine_type_id is None:
                                    continue
                                
                                machine_type_name = tes_machine_type_list.get(machine_type_id, f"id={machine_type_id}")
                                if "не указано" in machine_type_name.lower():
                                    continue
                                
                                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                mt_p_ust = mt_years
                                mt_p_ogr = mt_dict_ogr.get(machine_type_id, {})
                                mt_p_rasp = mt_dict_rasp.get(machine_type_id, {})
                                
                                current_row = write_power_row_with_separate_dicts(
                                    current_row, 0, machine_type_name,
                                    mt_p_ust, mt_p_ogr, mt_p_rasp, russia_format, russia_num_format, rowspan, indent_level=2
                                )
                                
                                # Разбивка по типам топлива для России
                                # Структура: station_type_id -> tes_type_id -> machine_type_id -> fuel_type_id -> year
                                fuel_dict = total_by_tes_machine_types_with_fuel_p_ust.get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                                fuel_dict_ogr = total_by_tes_machine_types_with_fuel_p_ogr.get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                                fuel_dict_rasp = total_by_tes_machine_types_with_fuel_p_rasp.get(station_type_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                                
                                for fuel_type_id, fuel_years in fuel_dict.items():
                                    if fuel_type_id is None:
                                        continue
                                    
                                    fuel_type_name = fuel_type_list.get(fuel_type_id, f"id={fuel_type_id}")
                                    
                                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                    fuel_p_ust = fuel_years
                                    fuel_p_ogr = fuel_dict_ogr.get(fuel_type_id, {})
                                    fuel_p_rasp = fuel_dict_rasp.get(fuel_type_id, {})
                                    
                                    current_row = write_power_row_with_separate_dicts(
                                        current_row, 0, fuel_type_name,
                                        fuel_p_ust, fuel_p_ogr, fuel_p_rasp, russia_format, russia_num_format, rowspan, indent_level=3
                                    )
                
                # Разбивка по типам ТЭС на уровне России (после ГАЭС, перед ВИЭ)
                total_tes_types_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_ust", {})
                total_tes_types_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_ogr", {})
                total_tes_types_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_yearly_p_rasp", {})
                
                if total_tes_types_p_ust:
                    for tes_type_id, tes_years in total_tes_types_p_ust.items():
                        if tes_type_id is None:
                            continue
                        
                        tes_type_name = tes_type_list.get(tes_type_id, f"id={tes_type_id}")
                        if "не указано" in tes_type_name.lower():
                            continue
                        
                        rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                        tes_p_ust = tes_years
                        tes_p_ogr = total_tes_types_p_ogr.get(tes_type_id, {})
                        tes_p_rasp = total_tes_types_p_rasp.get(tes_type_id, {})
                        
                        current_row = write_power_row_with_separate_dicts(
                            current_row, 0, tes_type_name,
                            tes_p_ust, tes_p_ogr, tes_p_rasp, russia_format, russia_num_format, rowspan, indent_level=1
                        )
                        
                        # Разбивка по типам топлива для типа ТЭС на уровне России
                        total_tes_types_with_fuel_p_ust = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_with_fuel_yearly_p_ust", {}).get(tes_type_id, {})
                        total_tes_types_with_fuel_p_ogr = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_with_fuel_yearly_p_ogr", {}).get(tes_type_id, {})
                        total_tes_types_with_fuel_p_rasp = total_energy_system_type_aggregates.get("total_energy_system_types_by_tes_types_with_fuel_yearly_p_rasp", {}).get(tes_type_id, {})
                        
                        if total_tes_types_with_fuel_p_ust:
                            # Важно: сортировка топлива всегда одинаковая (по справочнику: id, затем name)
                            for fuel_type_id, fuel_type_name in fuel_type_items_sorted:
                                fuel_years = total_tes_types_with_fuel_p_ust.get(fuel_type_id)
                                if not fuel_years:
                                    continue

                                rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                                fuel_p_ust = fuel_years
                                fuel_p_ogr = total_tes_types_with_fuel_p_ogr.get(fuel_type_id, {})
                                fuel_p_rasp = total_tes_types_with_fuel_p_rasp.get(fuel_type_id, {})

                                current_row = write_power_row_with_separate_dicts(
                                    current_row, 0, fuel_type_name,
                                    fuel_p_ust, fuel_p_ogr, fuel_p_rasp, russia_format, russia_num_format, rowspan, indent_level=2
                                )
                
                # Добавляем суммарную строку ВИЭ для России (если есть)
                if vie_aggregated_russia["p_ust"]:
                    rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                    vie_p_ust = dict(vie_aggregated_russia["p_ust"])
                    vie_p_ogr = dict(vie_aggregated_russia["p_ogr"])
                    vie_p_rasp = dict(vie_aggregated_russia["p_rasp"])
                    
                    current_row = write_power_row_with_separate_dicts(
                        current_row, 0, "ВИЭ",
                        vie_p_ust, vie_p_ogr, vie_p_rasp, russia_format, russia_num_format, rowspan, indent_level=0
                    )
                    
                    # Добавляем отдельно ВЭС и СЭС после суммарной строки ВИЭ для России
                    for station_type_id in vie_station_type_ids_russia:
                        if station_type_id not in total_by_st_p_ust:
                            continue
                        
                        station_type_name = station_type_list.get(station_type_id, f"id={station_type_id}")
                        if "не указано" in station_type_name.lower():
                            continue
                        
                        rowspan = 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                        st_p_ust = total_by_st_p_ust.get(station_type_id, {})
                        st_p_ogr = total_by_st_p_ogr.get(station_type_id, {})
                        st_p_rasp = total_by_st_p_rasp.get(station_type_id, {})
                        
                        current_row = write_power_row_with_separate_dicts(
                            current_row, 0, station_type_name,
                            st_p_ust, st_p_ogr, st_p_rasp, russia_format, russia_num_format, rowspan, indent_level=1
                        )
        
        # Устанавливаем ширину столбцов
        worksheet.set_column(0, 0, 30)  # Энергосистема
        worksheet.set_column(1, 1, 12)  # Тип мощ-ти
        for i in range(end_year - start_year + 1):
            worksheet.set_column(2 + i, 2 + i, 10)  # Годы
        
        workbook.close()
        output.seek(0)
        return output
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        current_app.logger.error(f"Ошибка экспорта totals_summary: {e}\n{error_details}")
        raise
