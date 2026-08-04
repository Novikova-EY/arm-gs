# -*- coding: utf-8 -*-
"""
Централизованный маппинг технических названий полей на русские названия для логирования.
Названия полей берутся из HTML-форм для удобства пользователей.
"""

# Общие поля для всех справочников
COMMON_FIELDS = {
    "id": "ID",
    "name": "Наименование",
    "short_name": "Краткое наименование",
    "code": "Код",
    "description": "Описание",
    "note": "Примечание",
    "is_active": "Активно",
    "created_at": "Дата создания",
    "updated_at": "Дата обновления",
}

# Поля для электростанций (Station)
STATION_FIELDS = {
    "station_name": "Название электростанции",
    "name": "Название",
    "location": "Местоположение",
    "id_regional_district": "Субъект РФ",
    "id_gen_company": "Организация-собственник",
    "id_station_type": "Тип  электростанции",
    "id_condition_type": "Состояние",
    "federal_district": "Федеральный округ",
    "regional_energy_system": "Региональная энергосистема",
    "union_energy_system": "ОЭС",
    "energy_system_type": "Часть энергосистемы России",
}

# Поля для агрегатов (Machine)
MACHINE_FIELDS = {
    "machine_number": "Номер агрегата",
    "machine_name": "Название агрегата",
    "machine_group": "Номер/название группы агрегата",
    "fuel_so": "Топливо по СО",
    "id_condition_type": "Состояние агрегата электростанции",
    "id_gen_company": "Организация-собственник",
    "id_energy_area": "Энергорайон агрегата электростанции",
    "id_tes_machine_type": "Тип агрегата ТЭС",
    "id_equipment_group": "Тип технологии",
    "id_machine_type": "Тип агрегата",
    "id_tes_type": "Тип ТЭС",
    "id_fuel": "Топливо",
    "note": "Примечание",
    "change_document": "Документ-основание для изменения параметров агрегата",
    "p_ust": "Установленная мощность",
    "p_ogr": "Располагаемая мощность",
    "p_rasp": "Ограничение мощности",
    "install_date": "Дата ввода в эксплуатацию",
    "decommission_date": "Дата вывода из эксплуатации",
}

# Поля для ПГУ агрегатов (PGUMachine)
PGU_MACHINE_FIELDS = {
    "pgu_machine_number": "Номер ПГУ агрегата",
    "pgu_machine_name": "Название ПГУ агрегата",
    "id_parent_machine": "Родительский агрегат",
    "id_condition_type": "Состояние ПГУ агрегата",
    "id_tes_machine_type": "Тип ПГУ агрегата",
    "id_pgu_tes_machine_type": "Тип ПГУ агрегата ТЭС",
    "p_ust": "Установленная мощность ПГУ",
    "p_ogr": "Располагаемая мощность ПГУ",
    "p_rasp": "Ограничение мощности ПГУ",
}

# Поля для энергосистем
ENERGY_SYSTEM_FIELDS = {
    "id_energy_system_type": "Часть энергосистемы России",
    "id_union_energy_system": "ОЭС",
    "id_regional_energy_system": "Региональная энергосистема",
    "id_synchronous_area": "Синхронная зона",
    "id_energy_zone": "Энергетическая зона",
    "id_energy_unit": "Энергорайон",
    "id_energy_area": "Энергорайон",
    "name_rp": "Энергорайон (род. пад.)",
    "name_dp": "Энергорайон (предл. пад.)",
}

# Поля для территорий
TERRITORY_FIELDS = {
    "id_federal_district": "Федеральный округ",
    "id_regional_district": "Субъект РФ",
}

# Поля для генерирующих компаний
GEN_COMPANY_FIELDS = {
    "name": "Наименование генерирующей компании",
}

# Поля для топлива
FUEL_FIELDS = {
    "name": "Наименование топлива",
    "kod": "Код вида топлива",
    "id_fuel_type": "Тип топлива",
    "parent_id": "Родительский вид топлива",
    "nazvl": "Короткое наименование топлива",
    "kmbur": "Тип угольного топлива",
}

# Поля для типов топлива
FUEL_TYPE_FIELDS = {
    "name": "Наименование типа топлива",
    "nazvl": "Короткое наименование типа топлива",
}

# Поля для типов состояния
CONDITION_TYPE_FIELDS = {
    "name": "Наименование состояния",
}

# Поля для типов станций
STATION_TYPE_FIELDS = {
    "name": "Тип  электростанции",
}

# Поля для зарубежных стран, имеющих общие границы с РФ
FOREIGN_BORDER_COUNTRY_FIELDS = {
    "name": "Наименование страны",
}

# Поля для типов ТЭС
TES_TYPE_FIELDS = {
    "name": "Тип ТЭС",
}

# Поля для типов агрегатов ТЭС
TES_MACHINE_TYPE_FIELDS = {
    "name": "Тип агрегата ТЭС",
}

# Поля для типов агрегатов
MACHINE_TYPE_FIELDS = {
    "name": "Тип агрегата",
}

# Поля для типов ПГУ агрегатов ТЭС
PGU_TES_MACHINE_TYPE_FIELDS = {
    "name": "Тип ПГУ агрегата ТЭС",
}

# Поля для технологий
EQUIPMENT_GROUP_FIELDS = {
    "name": "Группа оборудования",
    "id_technology_type": "Тип технологии",
    "id_technology_availability": "Доступность технологии",
}

TECHNOLOGY_TYPE_FIELDS = {
    "name": "Тип технологии",
}

ELECTRICITY_PRODUCTION_COST_TYPE_FIELDS = {
    "name": "Наименование",
    "cost_code": "Код затрат",
}

ECONOMIC_ACTIVITY_TYPE_FIELDS = {
    "name": "Полное наименование",
    "name_2": "Краткое наименование",
    "display_order": "Порядок отображения",
}

TECHNOLOGY_AVAILABILITY_FIELDS = {
    "name": "Доступность технологии",
}

# Поля для документов
DOCUMENT_FIELDS = {
    "name": "Название документа",
    "file_path": "Путь к файлу",
    "upload_date": "Дата загрузки",
}

# Поля для пользователей
USER_FIELDS = {
    "username": "Имя пользователя",
    "email": "Email",
    "is_active": "Активен",
    "role": "Роль",
}

# Параметры распределения (DistributionParameter / fuel)
DISTRIBUTION_PARAMETER_FIELDS = {
    "id_union_energy_system": "ОЭС",
    "id_year": "Расчетный год",
    "id_base_year": "Базовый год (byear)",
    "e": "E (целевой Ераспред)",
    "kplus": "kplus",
    "kmin": "kmin",
    "k": "k",
    "bkl": "bkl",
    "kn": "kn",
    "knps": "knps",
    "kngt": "kngt",
    "knpg": "knpg",
    "hnps": "hnps",
    "hngt": "hngt",
    "hnpg": "hnpg",
    "numb": "Порядковый номер (numb)",
    "doptim": "Дополнительный параметр (doptim)",
    "lim": "Ограничение (lim)",
}

# Объединенный словарь всех полей
ALL_FIELDS = {
    **COMMON_FIELDS,
    **STATION_FIELDS,
    **MACHINE_FIELDS,
    **PGU_MACHINE_FIELDS,
    **ENERGY_SYSTEM_FIELDS,
    **TERRITORY_FIELDS,
    **GEN_COMPANY_FIELDS,
    **FUEL_FIELDS,
    **FUEL_TYPE_FIELDS,
    **CONDITION_TYPE_FIELDS,
    **STATION_TYPE_FIELDS,
    **FOREIGN_BORDER_COUNTRY_FIELDS,
    **TES_TYPE_FIELDS,
    **TES_MACHINE_TYPE_FIELDS,
    **MACHINE_TYPE_FIELDS,
    **PGU_TES_MACHINE_TYPE_FIELDS,
    **EQUIPMENT_GROUP_FIELDS,
    **TECHNOLOGY_TYPE_FIELDS,
    **ELECTRICITY_PRODUCTION_COST_TYPE_FIELDS,
    **ECONOMIC_ACTIVITY_TYPE_FIELDS,
    **TECHNOLOGY_AVAILABILITY_FIELDS,
    **DOCUMENT_FIELDS,
    **USER_FIELDS,
    **DISTRIBUTION_PARAMETER_FIELDS,
}


def get_field_name_ru(field_name: str, entity_type: str = None) -> str:
    """
    Возвращает русское название поля по его техническому названию.
    
    Args:
        field_name: Техническое название поля
        entity_type: Тип сущности (опционально, для более точного подбора)
    
    Returns:
        Русское название поля или исходное название, если перевод не найден
    """
    # Сначала ищем в специфичных для типа словарях
    if entity_type:
        type_fields = {
            "station": STATION_FIELDS,
            "machine": MACHINE_FIELDS,
            "pgu_machine": PGU_MACHINE_FIELDS,
            "gen_company": GEN_COMPANY_FIELDS,
            "fuel": FUEL_FIELDS,
            "fuel_type": FUEL_TYPE_FIELDS,
            "condition_type": CONDITION_TYPE_FIELDS,
            "station_type": STATION_TYPE_FIELDS,
            "foreign_border_country": FOREIGN_BORDER_COUNTRY_FIELDS,
            "tes_type": TES_TYPE_FIELDS,
            "tes_machine_type": TES_MACHINE_TYPE_FIELDS,
            "machine_type": MACHINE_TYPE_FIELDS,
            "pgu_tes_machine_type": PGU_TES_MACHINE_TYPE_FIELDS,
            "equipment_group": EQUIPMENT_GROUP_FIELDS,
            "technology_type": TECHNOLOGY_TYPE_FIELDS,
            "electricity_production_cost_type": ELECTRICITY_PRODUCTION_COST_TYPE_FIELDS,
            "economic_activity_type": ECONOMIC_ACTIVITY_TYPE_FIELDS,
            "technology_availability": TECHNOLOGY_AVAILABILITY_FIELDS,
            "document": DOCUMENT_FIELDS,
            "user": USER_FIELDS,
            "distribution_parameter": DISTRIBUTION_PARAMETER_FIELDS,
        }.get(entity_type, {})
        
        if field_name in type_fields:
            return type_fields[field_name]
    
    # Затем ищем в общем словаре
    return ALL_FIELDS.get(field_name, field_name)


def format_field_change(field_name: str, old_value, new_value, entity_type: str = None) -> str:
    """
    Форматирует изменение поля на русском языке.
    
    Args:
        field_name: Техническое название поля
        old_value: Старое значение
        new_value: Новое значение
        entity_type: Тип сущности (опционально)
    
    Returns:
        Строка с описанием изменения в формате "Русское название поля: старое → новое"
    """
    ru_name = get_field_name_ru(field_name, entity_type)
    
    # Обработка None значений
    old_str = old_value if old_value is not None else "не указано"
    new_str = new_value if new_value is not None else "не указано"
    
    return f"{ru_name}: {old_str} → {new_str}"


def format_field_value(field_name: str, value, entity_type: str = None) -> str:
    """
    Форматирует значение поля на русском языке.
    
    Args:
        field_name: Техническое название поля
        value: Значение поля
        entity_type: Тип сущности (опционально)
    
    Returns:
        Строка в формате "Русское название поля: значение"
    """
    ru_name = get_field_name_ru(field_name, entity_type)
    value_str = value if value is not None else "не указано"
    return f"{ru_name}: {value_str}"

