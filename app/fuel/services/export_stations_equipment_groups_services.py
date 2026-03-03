# -*- coding: utf-8 -*-
"""Сервис экспорта таблицы stations_equipment_groups в Excel."""

from io import BytesIO
from datetime import datetime
from itertools import groupby

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from app.extensions import db
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from sqlalchemy.orm import selectinload

from app.common.services.database_version_filter import get_current_db_version_id
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
    energy_unit_names = hierarchy_data.get("energy_unit_name", {})
    
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
    
    # Загружаем station_equipment_groups и machines для всех станций
    if all_station_ids:
        stations_with_relations = db.session.query(Station).options(
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.equipment_group),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.territories_energy_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.department_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.union_energy_system_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.economic_region_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.federal_district_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.gen_company_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.gen_company_branch_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.business_unit_external_mapping),
            selectinload(Station.equipment_group_sets).selectinload(EquipmentGroupSet.cities_external_mapping),
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
        cell.value = column_title
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
        ws.append(row)
        
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
            ws.append(row)
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
                ws.append(row)
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
                        ws.append(row)
                        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                        cell = ws.cell(row=current_row, column=1)
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
                        cell.alignment = Alignment(horizontal="center", vertical="center")
                        current_row += 1
                    
                    # Сортируем энергоузлы
                    for eu_id in sorted(rd_group.keys()):
                        eu_group = rd_group[eu_id]
                        eu_name = energy_unit_names.get(eu_id)
                        
                        if eu_name and eu_name.lower() != "не указано":
                            # Строка с энергоузлом
                            row = [None] * len(columns)
                            row[2] = eu_name
                            for idx, value in enumerate(row):
                                if value is None:
                                    continue
                                length = len(str(value))
                                if length > max_lengths[idx]:
                                    max_lengths[idx] = length
                            ws.append(row)
                            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                            cell = ws.cell(row=current_row, column=1)
                            cell.font = Font(bold=True)
                            cell.fill = PatternFill(start_color="CCFFCC", end_color="CCFFCC", fill_type="solid")
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                            current_row += 1
                        
                        # Обрабатываем станции
                        for station in eu_group:
                            # Проверяем версию
                            station_version_id = getattr(station, 'database_version_id', None)
                            if current_version_id is not None and station_version_id != current_version_id:
                                continue
                            
                            station_id = station.id
                            
                            # Обрабатываем агрегаты станции (как на экране)
                            if hasattr(station, 'machines') and station.machines:
                                station_name = station.name if hasattr(station, 'name') and station.name else '—'
                                
                                filtered_machines = [
                                    m for m in station.machines
                                    if current_version_id is None
                                    or getattr(m, 'database_version_id', None) == current_version_id
                                ]
                                if not filtered_machines:
                                    row = [None] * len(columns)
                                    row[2] = "Нет агрегатов для отображения"
                                    for idx, value in enumerate(row):
                                        if value is None:
                                            continue
                                        length = len(str(value))
                                        if length > max_lengths[idx]:
                                            max_lengths[idx] = length
                                    ws.append(row)
                                    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                                    current_row += 1
                                    continue
                                
                                total_machines = len(filtered_machines)
                                station_first_row = None
                                
                                machines_with_group = [
                                    m for m in filtered_machines
                                    if getattr(m, 'id_equipment_group', None) is not None
                                ]
                                machines_without_group = [
                                    m for m in filtered_machines
                                    if getattr(m, 'id_equipment_group', None) is None
                                ]
                                
                                # Агрегаты с группами
                                sorted_machines = sorted(machines_with_group, key=lambda x: getattr(x, 'id_equipment_group', 0))
                                
                                for equipment_group_id, group_list in groupby(sorted_machines, key=lambda x: getattr(x, 'id_equipment_group', None)):
                                    group_list = list(group_list)
                                    if not group_list:
                                        continue
                                    
                                    # Получаем EquipmentGroupSet
                                    group_set = None
                                    machine = group_list[0]
                                    group_set = getattr(machine, 'equipment_group_set', None)
                                    
                                    if group_set is None and hasattr(station, 'equipment_group_sets'):
                                        seg_list = [
                                            s for s in station.equipment_group_sets
                                            if getattr(s, 'id_equipment_group', None) == equipment_group_id
                                        ]
                                        if seg_list:
                                            group_set = seg_list[0]
                                    
                                    group_name = '—'
                                    if group_set and hasattr(group_set, 'equipment_group') and group_set.equipment_group:
                                        group_name = group_set.equipment_group.name if hasattr(group_set.equipment_group, 'name') else '—'
                                    
                                    seg_name = group_set.name if group_set and hasattr(group_set, 'name') and group_set.name else '—'
                                    
                                    first_group_row = None
                                    
                                    for machine in group_list:
                                        row = [None] * len(columns)

                                        # id станции и агрегата
                                        row[0] = station_id
                                        row[1] = getattr(machine, "id", None)

                                        if station_first_row is None:
                                            station_first_row = current_row
                                            row[3] = station_name

                                        row[5] = machine.machine_number if hasattr(machine, 'machine_number') and machine.machine_number else '—'
                                        row[6] = machine.machine_name if hasattr(machine, 'machine_name') and machine.machine_name else '—'
                                        
                                        if first_group_row is None:
                                            first_group_row = current_row
                                            row[2] = seg_name
                                            row[4] = group_name
                                            
                                            if group_set:
                                                row[7] = group_set.niv if hasattr(group_set, 'niv') and group_set.niv else '—'
                                                row[8] = group_set.comp if hasattr(group_set, 'comp') and group_set.comp else '—'
                                                row[9] = group_set.main if hasattr(group_set, 'main') and group_set.main else '—'
                                                d_val = group_set.d if hasattr(group_set, 'd') and group_set.d else None
                                                r_val = group_set.r if hasattr(group_set, 'r') and group_set.r else None
                                                forem_val = group_set.forem if hasattr(group_set, 'forem') and group_set.forem else None
                                                row[10] = "да" if d_val is not None and str(d_val) == "1" else (d_val or "—")
                                                row[11] = "да" if r_val is not None and str(r_val) == "1" else (r_val or "—")
                                                row[12] = "да" if forem_val is not None and str(forem_val) == "1" else (forem_val or "—")

                                                _vedomstvo = group_set.vedomstvo if hasattr(group_set, 'vedomstvo') and group_set.vedomstvo else None
                                                if _vedomstvo and str(_vedomstvo) == "1":
                                                    row[13] = "станция\nотрасли"
                                                elif _vedomstvo and str(_vedomstvo) == "2":
                                                    row[13] = "пром.\nпредприятие"
                                                else:
                                                    row[13] = _vedomstvo or "—"

                                                terr_mapping = getattr(group_set, 'territories_energy_external_mapping', None)
                                                row[14] = (terr_mapping.external_name or group_set.obl) if terr_mapping and terr_mapping.external_name else (group_set.obl if hasattr(group_set, 'obl') and group_set.obl else '—')
                                                dep_mapping = getattr(group_set, 'department_external_mapping', None)
                                                row[15] = (dep_mapping.external_name or group_set.dep) if dep_mapping and dep_mapping.external_name else (group_set.dep if hasattr(group_set, 'dep') and group_set.dep else '—')
                                                ues_mapping = getattr(group_set, 'union_energy_system_external_mapping', None)
                                                row[16] = (ues_mapping.external_nameoes or group_set.oes) if ues_mapping and ues_mapping.external_nameoes else (group_set.oes if hasattr(group_set, 'oes') and group_set.oes else '—')
                                                er_mapping = getattr(group_set, 'economic_region_external_mapping', None)
                                                row[17] = (er_mapping.external_name or group_set.er) if er_mapping and er_mapping.external_name else (group_set.er if hasattr(group_set, 'er') and group_set.er else '—')
                                                fd_mapping = getattr(group_set, 'federal_district_external_mapping', None)
                                                row[18] = group_set.numb if hasattr(group_set, 'numb') and group_set.numb else '—'
                                                row[19] = group_set.tm if hasattr(group_set, 'tm') and group_set.tm else '—'
                                                row[20] = group_set.n1 if hasattr(group_set, 'n1') and group_set.n1 else '—'
                                                row[21] = group_set.n2 if hasattr(group_set, 'n2') and group_set.n2 else '—'
                                                row[22] = group_set.p1 if hasattr(group_set, 'p1') and group_set.p1 else '—'
                                                row[23] = group_set.p2 if hasattr(group_set, 'p2') and group_set.p2 else '—'
                                                row[24] = group_set.ordnumb if hasattr(group_set, 'ordnumb') and group_set.ordnumb else '—'
                                                row[25] = group_set.addr if hasattr(group_set, 'addr') and group_set.addr else '—'
                                                row[26] = group_set.note if hasattr(group_set, 'note') and group_set.note else '—'
                                                row[27] = (
                                                    group_set.cities_external_mapping.name
                                                    if group_set and getattr(group_set, 'cities_external_mapping', None) and group_set.cities_external_mapping
                                                    else (group_set.codegor if hasattr(group_set, 'codegor') and group_set.codegor else '—')
                                                )
                                                bu_mapping = getattr(group_set, 'business_unit_external_mapping', None)
                                                row[28] = (bu_mapping.external_name or group_set.be) if bu_mapping else (group_set.be if hasattr(group_set, 'be') and group_set.be else '—')
                                                gk_mapping = getattr(group_set, 'gen_company_external_mapping', None)
                                                row[29] = (gk_mapping.external_name or group_set.gk) if gk_mapping and gk_mapping.external_name else (group_set.gk if hasattr(group_set, 'gk') and group_set.gk else '—')
                                                gkf_mapping = getattr(group_set, 'gen_company_branch_external_mapping', None)
                                                row[30] = (gkf_mapping.external_name or group_set.gkf) if gkf_mapping and gkf_mapping.external_name else (group_set.gkf if hasattr(group_set, 'gkf') and group_set.gkf else '—')
                                            else:
                                                for col_idx in range(7, len(columns)):
                                                    row[col_idx] = "—"
                                        
                                        for idx, value in enumerate(row):
                                            if value is None:
                                                continue
                                            length = len(str(value))
                                            if length > max_lengths[idx]:
                                                max_lengths[idx] = length
                                        ws.append(row)
                                        current_row += 1
                                    
                                    # Объединяем ячейки для группы (rowspan) после добавления всех строк группы
                                    if first_group_row is not None and len(group_list) > 1:
                                        last_row = current_row - 1
                                        if last_row > first_group_row:
                                            # Группа оборудования, Тип
                                            ws.merge_cells(start_row=first_group_row, start_column=3,
                                                          end_row=last_row, end_column=3)
                                            ws.merge_cells(start_row=first_group_row, start_column=5,
                                                          end_row=last_row, end_column=5)
                                            # Поля StationEquipmentGroup (от niv до gkf)
                                            for col in range(8, len(columns) + 1):
                                                ws.merge_cells(start_row=first_group_row, start_column=col,
                                                              end_row=last_row, end_column=col)
                                
                                # Агрегаты без группы
                                if machines_without_group:
                                    no_group_first_row = None
                                    for machine in machines_without_group:
                                        row = [None] * len(columns)

                                        # id станции и агрегата
                                        row[0] = station_id
                                        row[1] = getattr(machine, "id", None)

                                        if station_first_row is None:
                                            station_first_row = current_row
                                            row[3] = station_name

                                        row[5] = machine.machine_number if hasattr(machine, 'machine_number') and machine.machine_number else '—'
                                        row[6] = machine.machine_name if hasattr(machine, 'machine_name') and machine.machine_name else '—'
                                        
                                        if no_group_first_row is None:
                                            no_group_first_row = current_row
                                            row[2] = '—'
                                            row[4] = '—'
                                            for col_idx in range(7, len(columns)):
                                                row[col_idx] = '—'
                                        
                                        for idx, value in enumerate(row):
                                            if value is None:
                                                continue
                                            length = len(str(value))
                                            if length > max_lengths[idx]:
                                                max_lengths[idx] = length
                                        ws.append(row)
                                        current_row += 1
                                    
                                    if no_group_first_row is not None and len(machines_without_group) > 1:
                                        last_row = current_row - 1
                                        if last_row > no_group_first_row:
                                            ws.merge_cells(start_row=no_group_first_row, start_column=3,
                                                          end_row=last_row, end_column=3)
                                            ws.merge_cells(start_row=no_group_first_row, start_column=5,
                                                          end_row=last_row, end_column=5)
                                            for col in range(8, len(columns) + 1):
                                                ws.merge_cells(start_row=no_group_first_row, start_column=col,
                                                              end_row=last_row, end_column=col)
                                
                                # Объединяем ячейки для станции (rowspan)
                                if station_first_row is not None and total_machines > 1:
                                    station_last_row = current_row - 1
                                    if station_last_row > station_first_row:
                                        ws.merge_cells(start_row=station_first_row, start_column=4,
                                                      end_row=station_last_row, end_column=4)
                            
                            else:
                                row = [None] * len(columns)
                                row[2] = "Нет агрегатов для отображения"
                                for idx, value in enumerate(row):
                                    if value is None:
                                        continue
                                    length = len(str(value))
                                    if length > max_lengths[idx]:
                                        max_lengths[idx] = length
                                ws.append(row)
                                ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=len(columns))
                                current_row += 1
    
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
