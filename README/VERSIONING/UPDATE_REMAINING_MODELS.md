# Оставшиеся модели refdata для обновления

## Обновлено (14 моделей)

### Generation (11 моделей) - ✅ ГОТОВО
1. ✅ Station
2. ✅ StationPower
3. ✅ StationGroup
4. ✅ Machine
5. ✅ MachinePower
6. ✅ MachineFuel
7. ✅ MachineTesType
8. ✅ PguMachine
9. ✅ PguMachinePower
10. ✅ Boiler
11. ✅ Document

### Refdata (3 модели) - ✅ ГОТОВО
1. ✅ RegionalDistrict
2. ✅ GenCompany
3. ✅ Fuel

## Осталось обновить (22 модели)

### Territories (1 модель)
- app/refdata/models/territories/federal_district_model.py

### Fuels (2 модели)
- app/refdata/models/fuels/fuel_category_model.py
- app/refdata/models/fuels/fuel_type_model.py

### Years (2 модели)
- app/refdata/models/years/year_feature_model.py
- app/refdata/models/years/year_model.py

### Energy Systems (7 моделей)
- app/refdata/models/energy_systems/union_energy_system_model.py
- app/refdata/models/energy_systems/synchronous_area_model.py
- app/refdata/models/energy_systems/energy_zone_model.py
- app/refdata/models/energy_systems/energy_area_model.py
- app/refdata/models/energy_systems/regional_energy_system_model.py
- app/refdata/models/energy_systems/energy_unit_model.py
- app/refdata/models/energy_systems/energy_system_type_model.py

### Refdata for Stations (10 моделей)
- app/refdata/models/refdata_for_stations/condition_type_model.py
- app/refdata/models/refdata_for_stations/station/station_type_model.py
- app/refdata/models/refdata_for_stations/machine/machine_type_model.py
- app/refdata/models/refdata_for_stations/machine/pgu_tes_machine_type_model.py
- app/refdata/models/refdata_for_stations/machine/tes_machine_type_model.py
- app/refdata/models/refdata_for_stations/machine/tes_type_model.py
- app/refdata/models/refdata_for_stations/technologies/equipment_group_model.py
- app/refdata/models/refdata_for_stations/technologies/technology_availability_model.py
- app/refdata/models/refdata_for_stations/technologies/technology_type_model.py

## Инструкция по обновлению

Для каждой модели выполнить 2 шага:

### Шаг 1: Добавить импорт SCHEMA_GENERATION
```python
# БЫЛО:
from config import SCHEMA_REFDATA

# СТАЛО:
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
```

### Шаг 2: Добавить поле database_version_id
Добавить после `created_at` и `updated_at`, перед первым `@property` или `def __repr__`:

```python
# Поле для связи с версией БД
database_version_id = db.Column(
    db.Integer,
    db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
    nullable=True,
    index=True
)
```

## Примечание

**ВАЖНО**: Поле `database_version_id` уже существует в базе данных для всех таблиц (миграция применена). 
Обновление моделей необходимо для того, чтобы SQLAlchemy мог работать с этим полем в Python-коде.

Однако, для базовой функциональности это не критично, так как:
1. База данных уже готова
2. Middleware работает
3. Страница управления версиями функциональна

Более критично сейчас - обновить services для фильтрации данных по версиям.

