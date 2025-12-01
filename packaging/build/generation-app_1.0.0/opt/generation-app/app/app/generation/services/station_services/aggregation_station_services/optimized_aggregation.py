"""Оптимизированный модуль агрегации - все агрегации за один проход по данным."""

from collections import defaultdict
from decimal import Decimal


def aggregate_all_at_once(rows):
    """
    Выполняет все агрегации за один проход по данным.
    Возвращает словарь со всеми агрегированными данными.
    """
    
    # Инициализация структур данных для всех агрегаций
    # Energy Units
    eu_p_ust = defaultdict(lambda: defaultdict(Decimal))
    eu_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    eu_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    eu_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    eu_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    eu_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    eu_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    eu_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    eu_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    eu_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    eu_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    eu_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    eu_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    eu_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    eu_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    eu_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Regional Districts
    rd_p_ust = defaultdict(lambda: defaultdict(Decimal))
    rd_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    rd_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    rd_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    rd_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    rd_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    rd_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    rd_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    rd_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    rd_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    rd_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    rd_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    rd_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    rd_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    rd_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    rd_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Regional Energy Systems
    res_p_ust = defaultdict(lambda: defaultdict(Decimal))
    res_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    res_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    res_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    res_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    res_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    res_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    res_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    res_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    res_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    res_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    res_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    res_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    res_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    res_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    res_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Union Energy Systems
    ues_p_ust = defaultdict(lambda: defaultdict(Decimal))
    ues_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    ues_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    ues_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    ues_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    ues_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    ues_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    ues_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    ues_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    ues_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    ues_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    ues_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    ues_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    ues_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    ues_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    ues_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Energy System Types
    est_p_ust = defaultdict(lambda: defaultdict(Decimal))
    est_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    est_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    est_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    est_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    est_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    est_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    est_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    est_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    est_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    est_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    est_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    est_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    est_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    est_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    est_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Total Energy System Types
    test_p_ust = defaultdict(lambda: defaultdict(Decimal))
    test_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    test_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    test_st_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    test_st_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    test_st_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    test_st_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_st_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_st_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    test_tes_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    test_tes_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    test_tes_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    
    test_tes_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_tes_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_tes_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    test_tes_machine_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_tes_machine_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    test_tes_machine_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))
    
    test_tes_machine_fuel_p_ust = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    test_tes_machine_fuel_p_ogr = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    test_tes_machine_fuel_p_rasp = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))))
    
    # Один проход по всем данным
    for row in rows:
        eu = row.energy_unit_id
        rd = row.regional_district_id
        res = row.regional_energy_system_id
        ues = row.union_energy_system_id
        est = row.energy_system_type_id
        st = row.station_type_id
        tes_type = row.tes_type_id
        tes_machine = row.tes_machine_type_id
        fuel = row.fuel_type_id
        year = row.year
        db_version = getattr(row, 'database_version_id', 1)  # Используем database_version_id строки
        
        p_ust_val = row.p_ust or Decimal(0)
        p_ogr_val = row.p_ogr or Decimal(0)
        p_rasp_val = row.p_rasp or Decimal(0)
        
        # Energy Units агрегации
        eu_p_ust[eu][year] += p_ust_val
        eu_p_ogr[eu][year] += p_ogr_val
        eu_p_rasp[eu][year] += p_rasp_val
        
        eu_st_p_ust[eu][st][year] += p_ust_val
        eu_st_p_ogr[eu][st][year] += p_ogr_val
        eu_st_p_rasp[eu][st][year] += p_rasp_val
        
        eu_st_fuel_p_ust[eu][st][fuel][year] += p_ust_val
        eu_st_fuel_p_ogr[eu][st][fuel][year] += p_ogr_val
        eu_st_fuel_p_rasp[eu][st][fuel][year] += p_rasp_val
        
        eu_tes_p_ust[eu][tes_type][year] += p_ust_val
        eu_tes_p_ogr[eu][tes_type][year] += p_ogr_val
        eu_tes_p_rasp[eu][tes_type][year] += p_rasp_val
        
        eu_tes_fuel_p_ust[eu][tes_type][fuel][year] += p_ust_val
        eu_tes_fuel_p_ogr[eu][tes_type][fuel][year] += p_ogr_val
        eu_tes_fuel_p_rasp[eu][tes_type][fuel][year] += p_rasp_val
        
        eu_tes_machine_p_ust[eu][tes_type][tes_machine][year] += p_ust_val
        eu_tes_machine_p_ogr[eu][tes_type][tes_machine][year] += p_ogr_val
        eu_tes_machine_p_rasp[eu][tes_type][tes_machine][year] += p_rasp_val
        
        eu_tes_machine_fuel_p_ust[eu][tes_type][tes_machine][fuel][year] += p_ust_val
        eu_tes_machine_fuel_p_ogr[eu][tes_type][tes_machine][fuel][year] += p_ogr_val
        eu_tes_machine_fuel_p_rasp[eu][tes_type][tes_machine][fuel][year] += p_rasp_val
        
        # Regional Districts агрегации
        rd_p_ust[rd][year] += p_ust_val
        rd_p_ogr[rd][year] += p_ogr_val
        rd_p_rasp[rd][year] += p_rasp_val
        
        rd_st_p_ust[rd][st][year] += p_ust_val
        rd_st_p_ogr[rd][st][year] += p_ogr_val
        rd_st_p_rasp[rd][st][year] += p_rasp_val
        
        rd_st_fuel_p_ust[rd][st][fuel][year] += p_ust_val
        rd_st_fuel_p_ogr[rd][st][fuel][year] += p_ogr_val
        rd_st_fuel_p_rasp[rd][st][fuel][year] += p_rasp_val
        
        rd_tes_p_ust[rd][tes_type][year] += p_ust_val
        rd_tes_p_ogr[rd][tes_type][year] += p_ogr_val
        rd_tes_p_rasp[rd][tes_type][year] += p_rasp_val
        
        rd_tes_fuel_p_ust[rd][tes_type][fuel][year] += p_ust_val
        rd_tes_fuel_p_ogr[rd][tes_type][fuel][year] += p_ogr_val
        rd_tes_fuel_p_rasp[rd][tes_type][fuel][year] += p_rasp_val
        
        rd_tes_machine_p_ust[rd][tes_type][tes_machine][year] += p_ust_val
        rd_tes_machine_p_ogr[rd][tes_type][tes_machine][year] += p_ogr_val
        rd_tes_machine_p_rasp[rd][tes_type][tes_machine][year] += p_rasp_val
        
        rd_tes_machine_fuel_p_ust[rd][tes_type][tes_machine][fuel][year] += p_ust_val
        rd_tes_machine_fuel_p_ogr[rd][tes_type][tes_machine][fuel][year] += p_ogr_val
        rd_tes_machine_fuel_p_rasp[rd][tes_type][tes_machine][fuel][year] += p_rasp_val
        
        # Regional Energy Systems агрегации
        res_p_ust[res][year] += p_ust_val
        res_p_ogr[res][year] += p_ogr_val
        res_p_rasp[res][year] += p_rasp_val
        
        res_st_p_ust[res][st][year] += p_ust_val
        res_st_p_ogr[res][st][year] += p_ogr_val
        res_st_p_rasp[res][st][year] += p_rasp_val
        
        res_st_fuel_p_ust[res][st][fuel][year] += p_ust_val
        res_st_fuel_p_ogr[res][st][fuel][year] += p_ogr_val
        res_st_fuel_p_rasp[res][st][fuel][year] += p_rasp_val
        
        res_tes_p_ust[res][tes_type][year] += p_ust_val
        res_tes_p_ogr[res][tes_type][year] += p_ogr_val
        res_tes_p_rasp[res][tes_type][year] += p_rasp_val
        
        res_tes_fuel_p_ust[res][tes_type][fuel][year] += p_ust_val
        res_tes_fuel_p_ogr[res][tes_type][fuel][year] += p_ogr_val
        res_tes_fuel_p_rasp[res][tes_type][fuel][year] += p_rasp_val
        
        res_tes_machine_p_ust[res][tes_type][tes_machine][year] += p_ust_val
        res_tes_machine_p_ogr[res][tes_type][tes_machine][year] += p_ogr_val
        res_tes_machine_p_rasp[res][tes_type][tes_machine][year] += p_rasp_val
        
        res_tes_machine_fuel_p_ust[res][tes_type][tes_machine][fuel][year] += p_ust_val
        res_tes_machine_fuel_p_ogr[res][tes_type][tes_machine][fuel][year] += p_ogr_val
        res_tes_machine_fuel_p_rasp[res][tes_type][tes_machine][fuel][year] += p_rasp_val
        
        # Union Energy Systems агрегации
        ues_p_ust[ues][year] += p_ust_val
        ues_p_ogr[ues][year] += p_ogr_val
        ues_p_rasp[ues][year] += p_rasp_val
        
        ues_st_p_ust[ues][st][year] += p_ust_val
        ues_st_p_ogr[ues][st][year] += p_ogr_val
        ues_st_p_rasp[ues][st][year] += p_rasp_val
        
        ues_st_fuel_p_ust[ues][st][fuel][year] += p_ust_val
        ues_st_fuel_p_ogr[ues][st][fuel][year] += p_ogr_val
        ues_st_fuel_p_rasp[ues][st][fuel][year] += p_rasp_val
        
        ues_tes_p_ust[ues][tes_type][year] += p_ust_val
        ues_tes_p_ogr[ues][tes_type][year] += p_ogr_val
        ues_tes_p_rasp[ues][tes_type][year] += p_rasp_val
        
        ues_tes_fuel_p_ust[ues][tes_type][fuel][year] += p_ust_val
        ues_tes_fuel_p_ogr[ues][tes_type][fuel][year] += p_ogr_val
        ues_tes_fuel_p_rasp[ues][tes_type][fuel][year] += p_rasp_val
        
        ues_tes_machine_p_ust[ues][tes_type][tes_machine][year] += p_ust_val
        ues_tes_machine_p_ogr[ues][tes_type][tes_machine][year] += p_ogr_val
        ues_tes_machine_p_rasp[ues][tes_type][tes_machine][year] += p_rasp_val
        
        ues_tes_machine_fuel_p_ust[ues][tes_type][tes_machine][fuel][year] += p_ust_val
        ues_tes_machine_fuel_p_ogr[ues][tes_type][tes_machine][fuel][year] += p_ogr_val
        ues_tes_machine_fuel_p_rasp[ues][tes_type][tes_machine][fuel][year] += p_rasp_val
        
        # Energy System Types агрегации
        est_p_ust[est][year] += p_ust_val
        est_p_ogr[est][year] += p_ogr_val
        est_p_rasp[est][year] += p_rasp_val
        
        est_st_p_ust[est][st][year] += p_ust_val
        est_st_p_ogr[est][st][year] += p_ogr_val
        est_st_p_rasp[est][st][year] += p_rasp_val
        
        est_st_fuel_p_ust[est][st][fuel][year] += p_ust_val
        est_st_fuel_p_ogr[est][st][fuel][year] += p_ogr_val
        est_st_fuel_p_rasp[est][st][fuel][year] += p_rasp_val
        
        est_tes_p_ust[est][tes_type][year] += p_ust_val
        est_tes_p_ogr[est][tes_type][year] += p_ogr_val
        est_tes_p_rasp[est][tes_type][year] += p_rasp_val
        
        est_tes_fuel_p_ust[est][tes_type][fuel][year] += p_ust_val
        est_tes_fuel_p_ogr[est][tes_type][fuel][year] += p_ogr_val
        est_tes_fuel_p_rasp[est][tes_type][fuel][year] += p_rasp_val
        
        est_tes_machine_p_ust[est][tes_type][tes_machine][year] += p_ust_val
        est_tes_machine_p_ogr[est][tes_type][tes_machine][year] += p_ogr_val
        est_tes_machine_p_rasp[est][tes_type][tes_machine][year] += p_rasp_val
        
        est_tes_machine_fuel_p_ust[est][tes_type][tes_machine][fuel][year] += p_ust_val
        est_tes_machine_fuel_p_ogr[est][tes_type][tes_machine][fuel][year] += p_ogr_val
        est_tes_machine_fuel_p_rasp[est][tes_type][tes_machine][fuel][year] += p_rasp_val
        
        # Total Energy System Types агрегации (для всей системы с ключом database_version_id)
        test_p_ust[db_version][year] += p_ust_val
        test_p_ogr[db_version][year] += p_ogr_val
        test_p_rasp[db_version][year] += p_rasp_val
        
        test_st_p_ust[db_version][st][year] += p_ust_val
        test_st_p_ogr[db_version][st][year] += p_ogr_val
        test_st_p_rasp[db_version][st][year] += p_rasp_val
        
        test_st_fuel_p_ust[db_version][st][fuel][year] += p_ust_val
        test_st_fuel_p_ogr[db_version][st][fuel][year] += p_ogr_val
        test_st_fuel_p_rasp[db_version][st][fuel][year] += p_rasp_val
        
        test_tes_p_ust[db_version][tes_type][year] += p_ust_val
        test_tes_p_ogr[db_version][tes_type][year] += p_ogr_val
        test_tes_p_rasp[db_version][tes_type][year] += p_rasp_val
        
        test_tes_fuel_p_ust[db_version][tes_type][fuel][year] += p_ust_val
        test_tes_fuel_p_ogr[db_version][tes_type][fuel][year] += p_ogr_val
        test_tes_fuel_p_rasp[db_version][tes_type][fuel][year] += p_rasp_val
        
        test_tes_machine_p_ust[db_version][tes_type][tes_machine][year] += p_ust_val
        test_tes_machine_p_ogr[db_version][tes_type][tes_machine][year] += p_ogr_val
        test_tes_machine_p_rasp[db_version][tes_type][tes_machine][year] += p_rasp_val
        
        test_tes_machine_fuel_p_ust[db_version][tes_type][tes_machine][fuel][year] += p_ust_val
        test_tes_machine_fuel_p_ogr[db_version][tes_type][tes_machine][fuel][year] += p_ogr_val
        test_tes_machine_fuel_p_rasp[db_version][tes_type][tes_machine][fuel][year] += p_rasp_val
    
    # Возвращаем все агрегации в формате, совместимом с существующим кодом
    return {
        # Energy Units
        "aggregate_power_by_energy_units": {
            "aggregated": {"p_ust": eu_p_ust, "p_ogr": eu_p_ogr, "p_rasp": eu_p_rasp}
        },
        "aggregate_energy_units_by_station_types": {
            "aggregated": {"p_ust": eu_st_p_ust, "p_ogr": eu_st_p_ogr, "p_rasp": eu_st_p_rasp}
        },
        "aggregate_energy_units_by_station_type_with_fuel": {
            "aggregated": {"p_ust": eu_st_fuel_p_ust, "p_ogr": eu_st_fuel_p_ogr, "p_rasp": eu_st_fuel_p_rasp}
        },
        "aggregate_energy_units_by_tes_types": {
            "aggregated": {"p_ust": eu_tes_p_ust, "p_ogr": eu_tes_p_ogr, "p_rasp": eu_tes_p_rasp}
        },
        "aggregate_energy_units_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": eu_tes_fuel_p_ust, "p_ogr": eu_tes_fuel_p_ogr, "p_rasp": eu_tes_fuel_p_rasp}
        },
        "aggregate_energy_units_by_tes_machine_types": {
            "aggregated": {"p_ust": eu_tes_machine_p_ust, "p_ogr": eu_tes_machine_p_ogr, "p_rasp": eu_tes_machine_p_rasp}
        },
        "aggregate_energy_units_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": eu_tes_machine_fuel_p_ust, "p_ogr": eu_tes_machine_fuel_p_ogr, "p_rasp": eu_tes_machine_fuel_p_rasp}
        },
        
        # Regional Districts
        "aggregate_power_by_regional_districts": {
            "aggregated": {"p_ust": rd_p_ust, "p_ogr": rd_p_ogr, "p_rasp": rd_p_rasp}
        },
        "aggregate_regional_districts_by_station_types": {
            "aggregated": {"p_ust": rd_st_p_ust, "p_ogr": rd_st_p_ogr, "p_rasp": rd_st_p_rasp}
        },
        "aggregate_regional_districts_by_station_types_with_fuel": {
            "aggregated": {"p_ust": rd_st_fuel_p_ust, "p_ogr": rd_st_fuel_p_ogr, "p_rasp": rd_st_fuel_p_rasp}
        },
        "aggregate_regional_districts_by_tes_types": {
            "aggregated": {"p_ust": rd_tes_p_ust, "p_ogr": rd_tes_p_ogr, "p_rasp": rd_tes_p_rasp}
        },
        "aggregate_regional_districts_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": rd_tes_fuel_p_ust, "p_ogr": rd_tes_fuel_p_ogr, "p_rasp": rd_tes_fuel_p_rasp}
        },
        "aggregate_regional_districts_by_tes_machine_types": {
            "aggregated": {"p_ust": rd_tes_machine_p_ust, "p_ogr": rd_tes_machine_p_ogr, "p_rasp": rd_tes_machine_p_rasp}
        },
        "aggregate_regional_districts_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": rd_tes_machine_fuel_p_ust, "p_ogr": rd_tes_machine_fuel_p_ogr, "p_rasp": rd_tes_machine_fuel_p_rasp}
        },
        
        # Regional Energy Systems
        "aggregate_power_by_regional_energy_systems": {
            "aggregated": {"p_ust": res_p_ust, "p_ogr": res_p_ogr, "p_rasp": res_p_rasp}
        },
        "aggregate_regional_energy_systems_by_station_types": {
            "aggregated": {"p_ust": res_st_p_ust, "p_ogr": res_st_p_ogr, "p_rasp": res_st_p_rasp}
        },
        "aggregate_regional_energy_systems_by_station_types_with_fuel": {
            "aggregated": {"p_ust": res_st_fuel_p_ust, "p_ogr": res_st_fuel_p_ogr, "p_rasp": res_st_fuel_p_rasp}
        },
        "aggregate_regional_energy_systems_by_tes_types": {
            "aggregated": {"p_ust": res_tes_p_ust, "p_ogr": res_tes_p_ogr, "p_rasp": res_tes_p_rasp}
        },
        "aggregate_regional_energy_systems_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": res_tes_fuel_p_ust, "p_ogr": res_tes_fuel_p_ogr, "p_rasp": res_tes_fuel_p_rasp}
        },
        "aggregate_regional_energy_systems_by_tes_machine_types": {
            "aggregated": {"p_ust": res_tes_machine_p_ust, "p_ogr": res_tes_machine_p_ogr, "p_rasp": res_tes_machine_p_rasp}
        },
        "aggregate_regional_energy_systems_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": res_tes_machine_fuel_p_ust, "p_ogr": res_tes_machine_fuel_p_ogr, "p_rasp": res_tes_machine_fuel_p_rasp}
        },
        
        # Union Energy Systems
        "aggregate_power_by_union_energy_systems": {
            "aggregated": {"p_ust": ues_p_ust, "p_ogr": ues_p_ogr, "p_rasp": ues_p_rasp}
        },
        "aggregate_union_energy_systems_by_station_types": {
            "aggregated": {"p_ust": ues_st_p_ust, "p_ogr": ues_st_p_ogr, "p_rasp": ues_st_p_rasp}
        },
        "aggregate_union_energy_systems_by_station_types_with_fuel": {
            "aggregated": {"p_ust": ues_st_fuel_p_ust, "p_ogr": ues_st_fuel_p_ogr, "p_rasp": ues_st_fuel_p_rasp}
        },
        "aggregate_union_energy_systems_by_tes_types": {
            "aggregated": {"p_ust": ues_tes_p_ust, "p_ogr": ues_tes_p_ogr, "p_rasp": ues_tes_p_rasp}
        },
        "aggregate_union_energy_systems_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": ues_tes_fuel_p_ust, "p_ogr": ues_tes_fuel_p_ogr, "p_rasp": ues_tes_fuel_p_rasp}
        },
        "aggregate_union_energy_systems_by_tes_machine_types": {
            "aggregated": {"p_ust": ues_tes_machine_p_ust, "p_ogr": ues_tes_machine_p_ogr, "p_rasp": ues_tes_machine_p_rasp}
        },
        "aggregate_union_energy_systems_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": ues_tes_machine_fuel_p_ust, "p_ogr": ues_tes_machine_fuel_p_ogr, "p_rasp": ues_tes_machine_fuel_p_rasp}
        },
        
        # Energy System Types
        "aggregate_power_by_energy_system_types": {
            "aggregated": {"p_ust": est_p_ust, "p_ogr": est_p_ogr, "p_rasp": est_p_rasp}
        },
        "aggregate_energy_system_types_by_station_types": {
            "aggregated": {"p_ust": est_st_p_ust, "p_ogr": est_st_p_ogr, "p_rasp": est_st_p_rasp}
        },
        "aggregate_energy_system_types_by_station_types_with_fuel": {
            "aggregated": {"p_ust": est_st_fuel_p_ust, "p_ogr": est_st_fuel_p_ogr, "p_rasp": est_st_fuel_p_rasp}
        },
        "aggregate_energy_system_types_by_tes_types": {
            "aggregated": {"p_ust": est_tes_p_ust, "p_ogr": est_tes_p_ogr, "p_rasp": est_tes_p_rasp}
        },
        "aggregate_energy_system_types_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": est_tes_fuel_p_ust, "p_ogr": est_tes_fuel_p_ogr, "p_rasp": est_tes_fuel_p_rasp}
        },
        "aggregate_energy_system_types_by_tes_machine_types": {
            "aggregated": {"p_ust": est_tes_machine_p_ust, "p_ogr": est_tes_machine_p_ogr, "p_rasp": est_tes_machine_p_rasp}
        },
        "aggregate_energy_system_types_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": est_tes_machine_fuel_p_ust, "p_ogr": est_tes_machine_fuel_p_ogr, "p_rasp": est_tes_machine_fuel_p_rasp}
        },
        
        # Total Energy System Types
        "aggregate_power_by_total_energy_system_types": {
            "aggregated": {"p_ust": test_p_ust, "p_ogr": test_p_ogr, "p_rasp": test_p_rasp}
        },
        "aggregate_total_energy_system_types_by_station_types": {
            "aggregated": {"p_ust": test_st_p_ust, "p_ogr": test_st_p_ogr, "p_rasp": test_st_p_rasp}
        },
        "aggregate_total_energy_system_types_by_station_types_with_fuel": {
            "aggregated": {"p_ust": test_st_fuel_p_ust, "p_ogr": test_st_fuel_p_ogr, "p_rasp": test_st_fuel_p_rasp}
        },
        "aggregate_total_energy_system_types_by_tes_types": {
            "aggregated": {"p_ust": test_tes_p_ust, "p_ogr": test_tes_p_ogr, "p_rasp": test_tes_p_rasp}
        },
        "aggregate_total_energy_system_types_by_tes_types_with_fuel": {
            "aggregated": {"p_ust": test_tes_fuel_p_ust, "p_ogr": test_tes_fuel_p_ogr, "p_rasp": test_tes_fuel_p_rasp}
        },
        "aggregate_total_energy_system_types_by_tes_machine_types": {
            "aggregated": {"p_ust": test_tes_machine_p_ust, "p_ogr": test_tes_machine_p_ogr, "p_rasp": test_tes_machine_p_rasp}
        },
        "aggregate_total_energy_system_types_by_tes_machine_types_with_fuel": {
            "aggregated": {"p_ust": test_tes_machine_fuel_p_ust, "p_ogr": test_tes_machine_fuel_p_ogr, "p_rasp": test_tes_machine_fuel_p_rasp}
        },
    }

