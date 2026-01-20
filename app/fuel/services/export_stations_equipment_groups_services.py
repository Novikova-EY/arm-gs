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
from app.refdata.models.fuels.station_equpment_group_model import StationEquipmentGroup
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
    all_station_ids = []
    for es_type_group in grouped_stations.values():
        for ues_group in es_type_group.values():
            for res_group in ues_group.values():
                for rd_group in res_group.values():
                    for eu_group in rd_group.values():
                        for station in eu_group:
                            if station.id not in all_station_ids:
                                all_station_ids.append(station.id)
    
    # Загружаем station_equipment_groups и machines для всех станций
    if all_station_ids:
        stations_with_relations = db.session.query(Station).options(
            selectinload(Station.station_equipment_groups).selectinload(StationEquipmentGroup.equipment_group),
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
    ws.title = "Станции с группами оборудования"
    
    # Определяем столбцы (первым добавляем ID станции)
    columns = [
        "ID станции",  # Первый столбец с ID станции активной версии
        "ID агрегата",  # ID агрегата активной версии (для строк с агрегатами)
        "Наименование",
        "Тип",
        "ст. №",
        "Тип агрегата",
        "niv",
        "comp",
        "main",
        "d",
        "r",
        "form",
        "type",
        "vedomstvo",
        "obl",
        "dep",
        "oes",
        "er",
        "fo",
        "numb",
        "tm",
        "n1",
        "n2",
        "p1",
        "p2",
        "ordnumb",
        "addr",
        "note",
        "codegor",
        "be",
        "gk",
        "gkf",
    ]
    
    # Заголовки
    header_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    header_font = Font(bold=True, size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
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
        row[2] = es_type_name  # Наименование
        ws.append(row)
        
        # Стиль для заголовков иерархии
        ws.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=len(columns))
        cell = ws.cell(row=current_row, column=3)
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
            ws.append(row)
            ws.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=len(columns))
            cell = ws.cell(row=current_row, column=3)
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
                ws.append(row)
                ws.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=len(columns))
                cell = ws.cell(row=current_row, column=3)
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
                        ws.append(row)
                        ws.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=len(columns))
                        cell = ws.cell(row=current_row, column=3)
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
                            ws.append(row)
                            ws.merge_cells(start_row=current_row, start_column=3, end_row=current_row, end_column=len(columns))
                            cell = ws.cell(row=current_row, column=3)
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
                            
                            # Строка со станцией (аналогично HTML: colspan=4 для региона, colspan=4 для названия, остальное для gen_companies)
                            # В HTML: colspan="4" регион, colspan="4" название, colspan="22" компания (всего 30 колонок)
                            # В Excel: ID станции (1), ID агрегата (2), затем те же 30 колонок
                            row = [None] * len(columns)
                            row[0] = station_id  # ID станции
                            # ID агрегата остается пустым для строки станции
                            
                            # Региональный округ (колонки 3-6 = 4 колонки)
                            region_name = station.regional_district.name if station.regional_district and station.regional_district.name else '—'
                            row[2] = region_name
                            
                            # Название станции (колонки 7-10 = 4 колонки)
                            station_name = station.name if hasattr(station, 'name') and station.name else '—'
                            row[6] = station_name  # Индекс 6 = колонка 7
                            
                            # Компания (колонки 11-32 = остальные 22 колонки)
                            gen_companies = station.gen_companies if hasattr(station, 'gen_companies') and station.gen_companies else '—'
                            row[10] = gen_companies  # Индекс 10 = колонка 11
                            
                            ws.append(row)
                            
                            # Объединяем ячейки для станции
                            station_row = current_row
                            ws.merge_cells(start_row=station_row, start_column=3, end_row=station_row, end_column=6)  # Регион (4 колонки: 3-6)
                            ws.merge_cells(start_row=station_row, start_column=7, end_row=station_row, end_column=10)  # Название (4 колонки: 7-10)
                            ws.merge_cells(start_row=station_row, start_column=11, end_row=station_row, end_column=len(columns))  # Компания (остальные: 11-32)
                            
                            # Стиль для строки станции
                            for col in range(1, len(columns) + 1):
                                cell = ws.cell(row=station_row, column=col)
                                cell.font = Font(bold=True)
                                cell.alignment = Alignment(horizontal="left", vertical="center")
                            
                            current_row += 1
                            
                            # Обрабатываем агрегаты станции
                            if hasattr(station, 'machines') and station.machines:
                                # Группируем агрегаты по группам оборудования
                                machines_with_group = [m for m in station.machines 
                                                      if getattr(m, 'id_equipment_group', None) is not None]
                                machines_without_group = [m for m in station.machines 
                                                         if getattr(m, 'id_equipment_group', None) is None]
                                
                                # Сортируем и группируем агрегаты с группами
                                sorted_machines = sorted(machines_with_group, key=lambda x: getattr(x, 'id_equipment_group', 0))
                                
                                for equipment_group_id, group_list in groupby(sorted_machines, key=lambda x: getattr(x, 'id_equipment_group', None)):
                                    group_list = list(group_list)
                                    
                                    # Получаем StationEquipmentGroup
                                    seg = None
                                    if group_list:
                                        machine = group_list[0]
                                        seg = getattr(machine, 'station_equipment_group', None)
                                        
                                        if seg is None and hasattr(station, 'station_equipment_groups'):
                                            seg_list = [s for s in station.station_equipment_groups 
                                                       if getattr(s, 'id_equipment_group', None) == equipment_group_id]
                                            if seg_list:
                                                seg = seg_list[0]
                                    
                                    group_name = '—'
                                    if seg and hasattr(seg, 'equipment_group') and seg.equipment_group:
                                        group_name = seg.equipment_group.name if hasattr(seg.equipment_group, 'name') else '—'
                                    
                                    seg_name = seg.name if seg and hasattr(seg, 'name') and seg.name else '—'
                                    
                                    # Обрабатываем каждый агрегат в группе
                                    first_machine_row = None
                                    for machine in group_list:
                                        # Проверяем версию агрегата
                                        machine_version_id = getattr(machine, 'database_version_id', None)
                                        if current_version_id is not None and machine_version_id != current_version_id:
                                            continue
                                        
                                        machine_id = machine.id
                                        
                                        row = [None] * len(columns)
                                        row[0] = station_id  # ID станции
                                        row[1] = machine_id  # ID агрегата
                                        row[4] = machine.machine_number if hasattr(machine, 'machine_number') and machine.machine_number else '—'
                                        row[5] = machine.machine_name if hasattr(machine, 'machine_name') and machine.machine_name else '—'
                                        
                                        # Данные из StationEquipmentGroup (только в первой строке группы)
                                        if first_machine_row is None:
                                            first_machine_row = current_row
                                            row[2] = seg_name  # Наименование группы
                                            row[3] = group_name  # Тип группы
                                            
                                            if seg:
                                                row[6] = seg.niv if hasattr(seg, 'niv') and seg.niv else '—'
                                                row[7] = seg.comp if hasattr(seg, 'comp') and seg.comp else '—'
                                                row[8] = seg.main if hasattr(seg, 'main') and seg.main else '—'
                                                row[9] = seg.d if hasattr(seg, 'd') and seg.d else '—'
                                                row[10] = seg.r if hasattr(seg, 'r') and seg.r else '—'
                                                row[11] = seg.form if hasattr(seg, 'form') and seg.form else '—'
                                                row[12] = seg.type if hasattr(seg, 'type') and seg.type else '—'
                                                row[13] = seg.vedomstvo if hasattr(seg, 'vedomstvo') and seg.vedomstvo else '—'
                                                row[14] = seg.obl if hasattr(seg, 'obl') and seg.obl else '—'
                                                row[15] = seg.dep if hasattr(seg, 'dep') and seg.dep else '—'
                                                row[16] = seg.oes if hasattr(seg, 'oes') and seg.oes else '—'
                                                row[17] = seg.er if hasattr(seg, 'er') and seg.er else '—'
                                                row[18] = seg.fo if hasattr(seg, 'fo') and seg.fo else '—'
                                                row[19] = seg.numb if hasattr(seg, 'numb') and seg.numb else '—'
                                                row[20] = seg.tm if hasattr(seg, 'tm') and seg.tm else '—'
                                                row[21] = seg.n1 if hasattr(seg, 'n1') and seg.n1 else '—'
                                                row[22] = seg.n2 if hasattr(seg, 'n2') and seg.n2 else '—'
                                                row[23] = seg.p1 if hasattr(seg, 'p1') and seg.p1 else '—'
                                                row[24] = seg.p2 if hasattr(seg, 'p2') and seg.p2 else '—'
                                                row[25] = seg.ordnumb if hasattr(seg, 'ordnumb') and seg.ordnumb else '—'
                                                row[26] = seg.addr if hasattr(seg, 'addr') and seg.addr else '—'
                                                row[27] = seg.note if hasattr(seg, 'note') and seg.note else '—'
                                                row[28] = seg.codegor if hasattr(seg, 'codegor') and seg.codegor else '—'
                                                row[29] = seg.be if hasattr(seg, 'be') and seg.be else '—'
                                                row[30] = seg.gk if hasattr(seg, 'gk') and seg.gk else '—'
                                                row[31] = seg.gkf if hasattr(seg, 'gkf') and seg.gkf else '—'
                                        
                                        ws.append(row)
                                        
                                        if first_machine_row is None:
                                            first_machine_row = current_row
                                        
                                        current_row += 1
                                    
                                    # Объединяем ячейки для группы (rowspan) после добавления всех строк группы
                                    if first_machine_row is not None and len(group_list) > 1:
                                        last_row = current_row - 1
                                        if last_row > first_machine_row:
                                            # Объединяем Наименование (колонка 3) и Тип (колонка 4)
                                            ws.merge_cells(start_row=first_machine_row, start_column=3, 
                                                          end_row=last_row, end_column=3)
                                            ws.merge_cells(start_row=first_machine_row, start_column=4, 
                                                          end_row=last_row, end_column=4)
                                            # Объединяем поля StationEquipmentGroup (от niv=7 до gkf=32)
                                            for col in range(7, len(columns) + 1):
                                                ws.merge_cells(start_row=first_machine_row, start_column=col, 
                                                              end_row=last_row, end_column=col)
                                
                                # Агрегаты без группы
                                for machine in machines_without_group:
                                    machine_version_id = getattr(machine, 'database_version_id', None)
                                    if current_version_id is not None and machine_version_id != current_version_id:
                                        continue
                                    
                                    machine_id = machine.id
                                    
                                    row = [None] * len(columns)
                                    row[0] = station_id  # ID станции
                                    row[1] = machine_id  # ID агрегата
                                    row[2] = '—'  # Наименование группы
                                    row[3] = '—'  # Тип группы
                                    row[4] = machine.machine_number if hasattr(machine, 'machine_number') and machine.machine_number else '—'
                                    row[5] = machine.machine_name if hasattr(machine, 'machine_name') and machine.machine_name else '—'
                                    # Остальные поля пустые
                                    ws.append(row)
                                    current_row += 1
    
    # Автоподбор ширины столбцов
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = min(max_length + 2, 60)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Сохраняем в BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
