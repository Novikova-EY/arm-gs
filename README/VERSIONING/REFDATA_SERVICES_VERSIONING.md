# Инструкция по добавлению фильтрации версий в Refdata Services

## Обзор

Для поддержки версионности данных все services refdata должны быть обновлены для фильтрации данных по текущей активной версии БД.

## ✅ Обновлено (5 services)

1. ✅ `app/refdata/services/gen_companies/gen_company_services.py`
2. ✅ `app/refdata/services/territories/federal_district_services.py`
3. ✅ `app/refdata/services/fuels/fuel_type_services.py`
4. ✅ `app/refdata/services/energy_systems/union_energy_system_services.py`
5. ✅ `app/refdata/services/refdata_for_stations/stations/station_type_services.py`

## 📋 Осталось обновить (~18 services)

### Energy Systems (6 services)
- `app/refdata/services/energy_systems/energy_area_services.py`
- `app/refdata/services/energy_systems/energy_system_type_services.py`
- `app/refdata/services/energy_systems/energy_unit_services.py`
- `app/refdata/services/energy_systems/energy_zone_services.py`
- `app/refdata/services/energy_systems/regional_energy_system_services.py`
- `app/refdata/services/energy_systems/synchronous_area_services.py`

### Fuels (1 service)
- `app/refdata/services/fuels/fuel_services.py`

### Territories (1 service)
- `app/refdata/services/territories/regional_district_services.py`

### Refdata for Stations (10 services)
- `app/refdata/services/refdata_for_stations/condition_type_services.py`
- `app/refdata/services/refdata_for_stations/machines/machine_type_services.py`
- `app/refdata/services/refdata_for_stations/machines/pgu_tes_machine_type_services.py`
- `app/refdata/services/refdata_for_stations/machines/tes_machine_type_services.py`
- `app/refdata/services/refdata_for_stations/machines/tes_type_services.py`
- `app/refdata/services/refdata_for_stations/technologies/equipment_group_services.py`
- `app/refdata/services/refdata_for_stations/technologies/technology_availability_services.py`
- `app/refdata/services/refdata_for_stations/technologies/technology_type_services.py`

## 🔧 Как обновить service

Для каждого service выполнить 2 шага:

### Шаг 1: Добавить импорт фильтра версий

В секцию импортов (после импорта логирования) добавить:

```python
# Фильтрация по версиям
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create
```

**Пример:**
```python
# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru

# Фильтрация по версиям
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create
```

### Шаг 2: Добавить фильтрацию в query-функцию

В функции `<model>_query(...)` сразу после создания базового query добавить:

```python
# Применяем фильтрацию по версии БД
query = apply_version_filter(query, ModelClass)
```

**Пример 1 (простой query):**
```python
def fuel_type_query(fuel_type_filter=None, sort_by="id", sort_dir="asc"):
    # Базовый запрос
    query = FuelType.query.filter(FuelType.id.isnot(None), FuelType.id > 0)
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, FuelType)
    
    # Фильтрация
    if fuel_type_filter:
        query = query.filter(FuelType.name.ilike(f"%{fuel_type_filter}%"))
    
    # ... остальной код
```

**Пример 2 (query с join):**
```python
def union_energy_system_query(union_energy_system_filter=None, ...):
    # Базовый запрос
    query = (
        UnionEnergySystem.query
        .options(joinedload(UnionEnergySystem.energy_system_type))
        .join(EnergySystemType)
    )
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, UnionEnergySystem)
    
    # Фильтрация по названию ОЭС
    if union_energy_system_filter:
        query = query.filter(...)
    
    # ... остальной код
```

## 📊 Как работает фильтрация

Функция `apply_version_filter(query, ModelClass)`:

1. Получает ID текущей активной версии из Flask context (`g.current_db_version`)
2. Если версия установлена - добавляет фильтр:
   ```python
   query.filter(
       (ModelClass.database_version_id == current_version_id) |
       (ModelClass.database_version_id.is_(None))
   )
   ```
3. Если версия не установлена - возвращает query без изменений (показывает все данные)

## ✨ Дополнительно: Установка версии при создании

Для автоматической установки версии при создании новых записей используйте `set_db_version_on_create()`:

```python
def add_fuel_type_service(data, user):
    # Создание новой записи
    obj = FuelType(name=name)
    
    # Автоматически установить текущую версию БД
    set_db_version_on_create(obj)
    
    db.session.add(obj)
    db.session.commit()
```

## 🎯 Приоритет обновления

**Высокий приоритет:**
- Services, используемые в основных операциях (fuel_services, regional_district_services)
- Services с большим количеством запросов

**Средний приоритет:**
- Services для справочников (condition_type, machine_type, etc.)
- Services энергосистем

**Низкий приоритет:**
- Редко используемые services

## 🔍 Проверка

После обновления service проверьте:

1. ✅ Импорт `apply_version_filter` добавлен
2. ✅ Фильтр применен в функции `*_query()`
3. ✅ Фильтр применен после создания базового query, но до других фильтров
4. ✅ Service работает корректно (не выдает ошибок)

## 📝 Примечания

- Фильтрация автоматически применяется middleware на основе активной версии
- Если версия не установлена - отображаются все данные (обратная совместимость)
- Записи с `database_version_id = NULL` доступны во всех версиях
- Middleware автоматически устанавливает `g.current_db_version` на каждый запрос

## 🚀 Статус

- **Обновлено:** 5 из 23 services (~22%)
- **Осталось:** 18 services
- **Оценка времени:** ~10-15 минут на все оставшиеся services

---

*Последнее обновление: 21.10.2025*

