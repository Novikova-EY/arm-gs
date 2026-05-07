"""Сервис кэширования для оптимизации производительности."""

from functools import lru_cache
from typing import List, Dict, Any
from app.extensions import db
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.generation.models.station.station_group_model import StationGroup
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit


class CacheService:
    """Сервис для кэширования часто используемых справочников."""
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_condition_types_cached():
        """Кэшированный список типов состояний."""
        return db.session.query(ConditionType).all()
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_station_groups_cached():
        """Кэшированный список групп станций."""
        return db.session.query(StationGroup).all()
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_gen_companies_cached():
        """Кэшированный список генерирующих компаний."""
        return db.session.query(GenCompany).all()
    
    @staticmethod
    @lru_cache(maxsize=1)
    def get_energy_units_cached():
        """Кэшированный список энергоузлов."""
        return db.session.query(EnergyUnit).order_by(EnergyUnit.id).all()
    
    @staticmethod
    def clear_cache():
        """Очистка кэша (вызывать при изменении справочников)."""
        CacheService.get_condition_types_cached.cache_clear()
        CacheService.get_station_groups_cached.cache_clear()
        CacheService.get_gen_companies_cached.cache_clear()
        CacheService.get_energy_units_cached.cache_clear()
    
    @staticmethod
    def get_station_details_form_data():
        """Получение всех данных для форм деталей электростанции одним вызовом."""
        return {
            'condition_types': CacheService.get_condition_types_cached(),
            'station_groups': CacheService.get_station_groups_cached(),
            'gen_companies': CacheService.get_gen_companies_cached(),
            'energy_units': CacheService.get_energy_units_cached()
        }
