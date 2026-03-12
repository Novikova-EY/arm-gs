# -*- coding: utf-8 -*-
"""Сервис экспорта таблицы stations_equipment_groups в Excel."""

from io import BytesIO
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from app.common.services.help_services import apply_nbsp_to_row
from app.extensions import db
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.services.stations_equipment_groups_v2_services import (
    build_station_equipment_groups_v2,
    reorganize_by_equipment_group_first,
)
from sqlalchemy.orm import selectinload

from app.generation.services.station_services.station_services import (
    get_station_list_data,
)
from app.generation.services.station_services.filters_services import (
    extract_filters_from_args,
)


def export_stations_equipment_groups_to_excel(filters, start_year, end_year):
    """
    Экспортирует данные stations_equipment_groups в Excel.
    Формат точно соответствует отображению на странице.
    """
    # Получаем все данные без пагинации
    data = get_station_list_data(
        filters=filters,
        per_page="all",
        page=1,
        rounding_digits=1,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=False,
        show_p_rasp=False,
        show_all=True,
        show_totals=False,
    )
    
    hierarchy_data = data.get("hierarchy_data", {})
    grouped_stations = hierarchy_data.get("grouped_stations", {})
    energy_system_type_names = hierarchy_data.get("energy_system_type_name", {})
    union_energy_system_names = hierarchy_data.get("union_energy_system_name", {})
    regional_energy_system_names = hierarchy_data.get("regional_energy_system_name", {})
    regional_district_names = hierarchy_data.get("regional_district_name", {})
    
    # Получаем union_energy_system_list для правильной сортировки
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
    )
    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = union_energy_system_objects
    
    # Сортируем типы энергосистем
    sorted_energy_system_type_ids = sorted(grouped_stations.keys())
    
    # Собираем все ID станций для загрузки station_equipment_groups
    all_station_ids = set()
    for es_type_group in grouped_stations.values():
        for ues_group in es_type_group.values():
            for res_group in ues_group.values():
                for rd_group in res_group.values():
                    for eu_group in rd_group.values():
                        for station in eu_group:
                            all_station_ids.add(station.id)
    
    stations_dict = {}
    # Загружаем station_equipment_groups и machines для всех станций
    if all_station_ids:
        stations_with_relations = db.session.query(Station).options(
            selectinload(Station.machines),
            selectinload(Station.regional_district),
        ).filter(Station.id.in_(all_station_ids)).all()
        
        # Создаем словарь для быстрого доступа
        stations_dict = {s.id: s for s in stations_with_relations}
        
        # Заменяем станции в grouped_stations на загруженные с группами
        for es_type_group in grouped_stations.values():
            for ues_group in es_type_group.values():
                for res_group in ues_group.values():
                    for rd_group in res_group.values():
                        for eu_group in rd_group.values():
                            for i, station in enumerate(eu_group):
                                if station.id in stations_dict:
                                    eu_group[i] = stations_dict[station.id]
    
    v2_groups_map = build_station_equipment_groups_v2(
        list(stations_dict.values()),
        filters=filters,
        start_year=start_year,
        end_year=end_year,
    )
    current_version_id = get_current_db_version_id()
    
    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = "Группы оборудования"
    
    # Определяем столбцы: сначала технические id, затем как на экране
    columns = [
        "id_station",
        "id_machine",
        "Группа оборудования",
        "Станция",
        "Тип",
        "ст. №",
        "Тип агрегата",
        "Субъект РФ",
        "Региональная энергосистема",
        "niv",
        "comp",
        "main",
        "d",
        "r",
        "forem",
        "Ведомство",
        "Субъект РФ",
        "Департамент",
        "ОЭС",
        "Экономический район",
        "Федеральный округ",
        "Код станции",
        "Типы турбин",
        "Мощность блока (вар. 1)",
        "Мощность блока (вар. 2)",
        "Давление пара (вар. 1)",
        "Давление пара (вар. 2)",
        "Порядковый номер станции",
        "Адрес",
        "Примечание",
        "Код города",
        "Тип генерирующей компании",
        "Генерирующая компания",
        "Филиал ГК",
    ]
    
    # Заголовки
    header_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    header_font = Font(bold=True, size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    # Предварительно считаем максимальные длины по заголовкам
    max_lengths = [len(str(col)) if col is not None else 0 for col in columns]
    
    for col_num, column_title in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = apply_nbsp_to_row([column_title])[0]
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    current_row = 2
    
    # Обрабатываем иерархию
    for es_type_id in sorted_energy_system_type_ids:
        es_type_group = grouped_stations[es_type_id]
        es_type_name = energy_system_type_names.get(es_type_id, f"Тип {es_type_id}")
        
        # Строка с типом энергосистемы
        row = [None] * len(columns)
        row[2] = es_type_name  # Группа оборудования
        for idx, value in enumerate(row):
            if value is None:
                continue
            length = len(str(value))
            if length > max_lengths[idx]:
                max_lengths[idx] = length
        ws.append(apply_nbsp_to_row(row))
        
        # Стиль для заголовков иерархии
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
        cell = ws.cell(row=current_row, column=1)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        current_row += 1
        
        # Сортируем по union_energy_system_list
        for ues in union_energy_system_list:
            ues_id = ues.id
            ues_group = es_type_group.get(ues_id)
            
            if not ues_group:
                continue
            
            ues_name = union_energy_system_names.get(ues_id, f"ОЭС {ues_id}")
            
            # Строка с объединенной энергосистемой
            row = [None] * len(columns)
            row[2] = ues_name
            for idx, value in enumerate(row):
                if value is None:
                    continue
                length = len(str(value))
                if length > max_lengths[idx]:
                    max_lengths[idx] = length
            ws.append(apply_nbsp_to_row(row))
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
            cell = ws.cell(row=current_row, column=1)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            current_row += 1
            
            # Сортируем региональные энергосистемы
            for res_id in sorted(ues_group.keys()):
                res_group = ues_group[res_id]
                res_name = regional_energy_system_names.get(res_id, f"РЭС {res_id}")
                
                # Строка с региональной энергосистемой
                row = [None] * len(columns)
                row[2] = res_name
                for idx, value in enumerate(row):
                    if value is None:
                        continue
                    length = len(str(value))
                    if length > max_lengths[idx]:
                        max_lengths[idx] = length
                ws.append(apply_nbsp_to_row(row))
                ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                cell = ws.cell(row=current_row, column=1)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="CCFFFF", end_color="CCFFFF", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                current_row += 1
                
                # Сортируем региональные округа
                for rd_id in sorted(res_group.keys()):
                    rd_group = res_group[rd_id]
                    rd_name = regional_district_names.get(rd_id)
                    
                    if rd_name and rd_name.lower() != "не указано":
                        # Строка с региональным округом
                        row = [None] * len(columns)
                        row[2] = rd_name
                        for idx, value in enumerate(row):
                            if value is None:
                                continue
                            length = len(str(value))
                            if length > max_lengths[idx]:
                                max_lengths[idx] = length
                        ws.append(apply_nbsp_to_row(row))
                        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                        cell = ws.cell(row=current_row, column=1)
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        current_row += 1
                    
                    # Обрабатываем станции (без отдельного уровня энергоузлов)
                    for eu_group in rd_group.values():
                        eu_group_filtered = [
                            s for s in eu_group
                            if current_version_id is None
                            or getattr(s, "database_version_id", None) == current_version_id
                        ]
                        blocks = reorganize_by_equipment_group_first(
                            eu_group_filtered, v2_groups_map
                        )

                        if not blocks and eu_group_filtered:
                            row = [None] * len(columns)
                            row[2] = "Нет агрегатов для отображения"
                            for idx, value in enumerate(row):
                                if value is None:
                                    continue
                                length = len(str(value))
                                if length > max_lengths[idx]:
                                    max_lengths[idx] = length
                            ws.append(apply_nbsp_to_row(row))
                            ws.merge_cells(
                                start_row=current_row,
                                start_column=1,
                                end_row=current_row,
                                end_column=len(columns),
                            )
                            current_row += 1
                            continue

                        for block in blocks:
                            group_obj = block.get("equipment_group")
                            group_first_row = None

                            for station_entry in block.get("station_entries") or []:
                                station = station_entry.get("station")
                                if not station:
                                    continue
                                station_id = station.id
                                station_name = (
                                    station.name if hasattr(station, "name") and station.name else "—"
                                )
                                station_first_row = None

                                for link in station_entry.get("links") or []:
                                    link_first_row = None
                                    group_type = link.get("equipment_group_type")
                                    for machine in link.get("machines") or []:
                                        row = [None] * len(columns)
                                        row[0] = station_id
                                        row[1] = getattr(machine, "id", None)

                                        if station_first_row is None:
                                            station_first_row = current_row
                                            row[3] = station_name

                                        row[5] = (
                                            machine.machine_number
                                            if getattr(machine, "machine_number", None)
                                            else "—"
                                        )
                                        row[6] = (
                                            machine.machine_name
                                            if getattr(machine, "machine_name", None)
                                            else "—"
                                        )

                                        if group_first_row is None:
                                            group_first_row = current_row
                                            group_name = (
                                                group_obj.name
                                                if group_obj and group_obj.name
                                                else (
                                                    group_obj.name_ext
                                                    if group_obj and group_obj.name_ext
                                                    else "—"
                                                )
                                            )
                                            row[2] = group_name

                                            if group_obj:
                                                rd = getattr(group_obj, "regional_district", None)
                                                row[7] = rd.name if rd and rd.name else "—"
                                                res = getattr(group_obj, "regional_energy_system", None)
                                                row[8] = res.name if res and res.name else "—"
                                                row[9] = group_obj.niv if group_obj.niv else "—"
                                                row[10] = group_obj.comp if group_obj.comp else "—"
                                                row[11] = group_obj.main if group_obj.main else "—"
                                                d_val = group_obj.d
                                                r_val = group_obj.r
                                                forem_val = group_obj.forem
                                                row[12] = "да" if d_val and str(d_val) == "1" else (d_val or "—")
                                                row[13] = "да" if r_val and str(r_val) == "1" else (r_val or "—")
                                                row[14] = "да" if forem_val and str(forem_val) == "1" else (forem_val or "—")

                                                _vedomstvo = group_obj.vedomstvo
                                                if _vedomstvo and str(_vedomstvo) == "1":
                                                    row[15] = "станция\nотрасли"
                                                elif _vedomstvo and str(_vedomstvo) == "2":
                                                    row[15] = "пром.\nпредприятие"
                                                else:
                                                    row[15] = _vedomstvo or "—"

                                                terr_mapping = getattr(
                                                    group_obj, "territories_energy_external_mapping", None
                                                )
                                                row[16] = (
                                                    terr_mapping.external_name
                                                    if terr_mapping and terr_mapping.external_name
                                                    else (group_obj.obl or "—")
                                                )
                                                dep_mapping = getattr(
                                                    group_obj, "department_external_mapping", None
                                                )
                                                row[17] = (
                                                    dep_mapping.external_name
                                                    if dep_mapping and dep_mapping.external_name
                                                    else (group_obj.dep or "—")
                                                )
                                                ues_mapping = getattr(
                                                    group_obj, "union_energy_system_external_mapping", None
                                                )
                                                row[18] = (
                                                    ues_mapping.external_nameoes
                                                    if ues_mapping and ues_mapping.external_nameoes
                                                    else (group_obj.oes or "—")
                                                )
                                                er_mapping = getattr(
                                                    group_obj, "economic_region_external_mapping", None
                                                )
                                                row[19] = (
                                                    er_mapping.external_name
                                                    if er_mapping and er_mapping.external_name
                                                    else (group_obj.er or "—")
                                                )
                                                fd_mapping = getattr(
                                                    group_obj, "federal_district_external_mapping", None
                                                )
                                                row[20] = (
                                                    fd_mapping.external_name
                                                    if fd_mapping and fd_mapping.external_name
                                                    else (group_obj.fo or "—")
                                                )
                                                row[21] = group_obj.numb if group_obj.numb else "—"
                                                row[22] = group_obj.tm if group_obj.tm else "—"
                                                row[23] = group_obj.n1 if group_obj.n1 else "—"
                                                row[24] = group_obj.n2 if group_obj.n2 else "—"
                                                row[25] = group_obj.p1 if group_obj.p1 else "—"
                                                row[26] = group_obj.p2 if group_obj.p2 else "—"
                                                row[27] = group_obj.ordnumb if group_obj.ordnumb else "—"
                                                row[28] = group_obj.addr if group_obj.addr else "—"
                                                row[29] = group_obj.note if group_obj.note else "—"
                                                row[30] = (
                                                    group_obj.cities_external_mapping.name
                                                    if group_obj.cities_external_mapping
                                                    else (group_obj.codegor or "—")
                                                )
                                                bu_mapping = getattr(
                                                    group_obj, "business_unit_external_mapping", None
                                                )
                                                row[31] = (
                                                    bu_mapping.external_name
                                                    if bu_mapping and bu_mapping.external_name
                                                    else (group_obj.be or "—")
                                                )
                                                gk_mapping = getattr(
                                                    group_obj, "gen_company_external_mapping", None
                                                )
                                                row[32] = (
                                                    gk_mapping.external_name
                                                    if gk_mapping and gk_mapping.external_name
                                                    else (group_obj.gk or "—")
                                                )
                                                gkf_mapping = getattr(
                                                    group_obj, "gen_company_branch_external_mapping", None
                                                )
                                                row[33] = (
                                                    gkf_mapping.external_name
                                                    if gkf_mapping and gkf_mapping.external_name
                                                    else (group_obj.gkf or "—")
                                                )
                                            else:
                                                for col_idx in range(7, len(columns)):
                                                    row[col_idx] = "—"

                                        if link_first_row is None:
                                            link_first_row = current_row
                                            row[4] = (
                                                group_type.name
                                                if group_type and getattr(group_type, "name", None)
                                                else "—"
                                            )

                                        for idx, value in enumerate(row):
                                            if value is None:
                                                continue
                                            length = len(str(value))
                                            if length > max_lengths[idx]:
                                                max_lengths[idx] = length
                                        ws.append(apply_nbsp_to_row(row))
                                        current_row += 1

                                    if link_first_row is not None and current_row - 1 > link_first_row:
                                        ws.merge_cells(
                                            start_row=link_first_row,
                                            start_column=5,
                                            end_row=current_row - 1,
                                            end_column=5,
                                        )

                                if station_first_row is not None and current_row - 1 > station_first_row:
                                    ws.merge_cells(
                                        start_row=station_first_row,
                                        start_column=4,
                                        end_row=current_row - 1,
                                        end_column=4,
                                    )

                            if group_first_row is not None and current_row - 1 > group_first_row:
                                ws.merge_cells(
                                    start_row=group_first_row,
                                    start_column=3,
                                    end_row=current_row - 1,
                                    end_column=3,
                                )
                                for col in range(8, len(columns) + 1):
                                    ws.merge_cells(
                                        start_row=group_first_row,
                                        start_column=col,
                                        end_row=current_row - 1,
                                        end_column=col,
                                    )
    
    # Автоподбор ширины столбцов (по предвычисленным длинам)
    for col_idx, max_length in enumerate(max_lengths, start=1):
        adjusted_width = min(max_length + 2, 60)
        column_letter = get_column_letter(col_idx)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Сохраняем в BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
