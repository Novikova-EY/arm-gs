# ПОЭТАПНАЯ логика копирования версий базы данных

## Проблема

При создании новой версии базы данных на основе существующей неправильно привязывались машины к станциям, мощности к машинам и другие взаимосвязи.

**ОБНОВЛЕНИЕ**: Также была обнаружена проблема с внешними ключами в таблицах схемы `refdata` - при копировании версий внешние ключи (`id_federal_district`, `id_energy_zone`, `id_synchronous_area` в `regional_districts` и другие) оставались ссылаться на записи из предыдущей версии, а не на соответствующие записи из новой версии.

## Причина

Неправильный порядок операций при копировании данных и обновлении связей между таблицами.

## ПОЭТАПНАЯ логика копирования

### Принцип: Сначала таблицы без взаимосвязей, затем поэтапно с зависимостями

**НОВАЯ ПОЭТАПНАЯ ЛОГИКА:**
1. **ЭТАП 1**: Копируем ТОЛЬКО полностью независимые таблицы (без внешних ключей)
2. **ЭТАП 2**: Копируем таблицы с зависимостями от ЭТАПА 1
3. **ЭТАП 3**: Копируем таблицы с зависимостями от ЭТАПОВ 1-2
4. **ЭТАП 4**: Копируем таблицы с зависимостями от ЭТАПОВ 1-3
5. **ЭТАП 5**: Копируем таблицы generation с зависимостями от всех предыдущих этапов
6. **ЭТАП 6**: Копируем таблицы, зависящие от stations
7. **ЭТАП 7**: Копируем таблицы, зависящие от machines
8. **ЭТАП 8**: Копируем таблицы, зависящие от pgu_machines

### 1. ЭТАП 1: Полностью независимые таблицы

```python
# Таблицы без внешних ключей на другие таблицы
completely_independent_tables = [
    ('refdata', 'station_types'),
    ('refdata', 'machine_types'), 
    ('refdata', 'tes_types'),
    ('refdata', 'tes_machine_types'),
    ('refdata', 'pgu_tes_machine_types'),
    ('refdata', 'condition_types'),
    ('refdata', 'technology_types'),
    ('refdata', 'technology_availabilities'),
    ('refdata', 'equipment_groups'),
    ('refdata', 'energy_system_types'),
    ('refdata', 'fuel_categories'),
    ('refdata', 'fuel_types'),
    ('refdata', 'fuels'),
    ('refdata', 'gen_companies'),
    ('generation', 'station_groups'),
    ('generation', 'documents_kommod')
]
```

### 2. ЭТАП 2: Таблицы с зависимостями от ЭТАПА 1

```python
stage2_tables = [
    {
        'schema': 'refdata',
        'table': 'union_energy_systems',
        'dependencies': []  # Независимая, но копируем во 2 этапе для логической группировки
    },
    {
        'schema': 'refdata', 
        'table': 'synchronous_areas',
        'dependencies': []
    },
    {
        'schema': 'refdata',
        'table': 'energy_zones', 
        'dependencies': []
    },
    {
        'schema': 'refdata',
        'table': 'federal_districts',
        'dependencies': []
    }
]
```

### 3. ЭТАП 3: Таблицы с зависимостями от ЭТАПОВ 1-2

```python
stage3_tables = [
    {
        'schema': 'refdata',
        'table': 'regional_districts',
        'dependencies': [
            {'fk': 'id_federal_district', 'ref_table': 'refdata.federal_districts'},
            {'fk': 'id_energy_zone', 'ref_table': 'refdata.energy_zones'},
            {'fk': 'id_synchronous_area', 'ref_table': 'refdata.synchronous_areas'}
        ]
    },
    {
        'schema': 'refdata',
        'table': 'regional_energy_systems',
        'dependencies': [
            {'fk': 'id_union_energy_system', 'ref_table': 'refdata.union_energy_systems'}
        ]
    }
]
```

### 4. ЭТАП 4: Таблицы с зависимостями от ЭТАПОВ 1-3

```python
stage4_tables = [
    {
        'schema': 'refdata',
        'table': 'energy_areas',
        'dependencies': [
            {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'}
        ]
    },
    {
        'schema': 'refdata',
        'table': 'energy_units',
        'dependencies': [
            {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'},
            {'fk': 'id_regional_energy_system', 'ref_table': 'refdata.regional_energy_systems'}
        ]
    }
]
```

### 5. ЭТАП 5: Таблицы generation с зависимостями от всех предыдущих этапов

```python
stage5_tables = [
    {
        'schema': 'generation',
        'table': 'stations',
        'dependencies': [
            {'fk': 'id_station_group', 'ref_table': 'gs_gen.station_groups'},
            {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'},
            {'fk': 'id_energy_unit', 'ref_table': 'refdata.energy_units'},
            {'fk': 'id_station_type', 'ref_table': 'refdata.station_types'},
            {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'},
            {'fk': 'id_gen_company', 'ref_table': 'refdata.gen_companies'}
        ]
    }
]
```

### 6. ЭТАП 6: Таблицы, зависящие от stations

```python
stage6_tables = [
    {
        'schema': 'generation',
        'table': 'station_powers',
        'dependencies': [
            {'fk': 'id_station', 'ref_table': 'gs_gen.stations'}
        ]
    },
    {
        'schema': 'generation',
        'table': 'machines',
        'dependencies': [
            {'fk': 'id_station', 'ref_table': 'gs_gen.stations'},
            {'fk': 'id_machine_type', 'ref_table': 'refdata.machine_types'},
            {'fk': 'id_tes_machine_type', 'ref_table': 'refdata.tes_machine_types'},
            {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'},
            {'fk': 'id_gen_company', 'ref_table': 'refdata.gen_companies'},
            {'fk': 'id_energy_area', 'ref_table': 'refdata.energy_areas'},
            {'fk': 'id_technology_availability', 'ref_table': 'refdata.technology_availabilities'},
            {'fk': 'id_technology_type', 'ref_table': 'refdata.technology_types'},
            {'fk': 'id_equipment_group', 'ref_table': 'refdata.equipment_groups'}
        ]
    },
    {
        'schema': 'generation',
        'table': 'boilers',
        'dependencies': [
            {'fk': 'id_station', 'ref_table': 'gs_gen.stations'}
        ]
    }
]
```

### 7. ЭТАП 7: Таблицы, зависящие от machines

```python
stage7_tables = [
    {
        'schema': 'generation',
        'table': 'machine_powers',
        'dependencies': [
            {'fk': 'id_machine', 'ref_table': 'gs_gen.machines'}
        ]
    },
    {
        'schema': 'generation',
        'table': 'machine_fuels',
        'dependencies': [
            {'fk': 'id_machine', 'ref_table': 'gs_gen.machines'},
            {'fk': 'id_fuel', 'ref_table': 'refdata.fuels'}
        ]
    },
    {
        'schema': 'generation',
        'table': 'machine_tes_types',
        'dependencies': [
            {'fk': 'id_machine', 'ref_table': 'gs_gen.machines'},
            {'fk': 'id_tes_type', 'ref_table': 'refdata.tes_types'}
        ]
    },
    {
        'schema': 'generation',
        'table': 'pgu_machines',
        'dependencies': [
            {'fk': 'id_parent_machine', 'ref_table': 'gs_gen.machines'},
            {'fk': 'id_pgu_tes_machine_type', 'ref_table': 'refdata.pgu_tes_machine_types'},
            {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'}
        ]
    }
]
```

### 8. ЭТАП 8: Таблицы, зависящие от pgu_machines

```python
stage8_tables = [
    {
        'schema': 'generation',
        'table': 'pgu_machine_powers',
        'dependencies': [
            {'fk': 'id_pgu_machine', 'ref_table': 'gs_gen.pgu_machines'}
        ]
    }
]
```

### 2. Порядок обновления связей (согласно иерархии зависимостей)

```python
relationships = [
    # === СВЯЗИ В СХЕМЕ REFDATA (добавлены для исправления проблемы) ===
    # 1. regional_districts -> federal_districts
    {
        'table': 'refdata.regional_districts',
        'foreign_key': 'id_federal_district',
        'reference_table': 'refdata.federal_districts'
    },
    # 2. regional_districts -> energy_zones
    {
        'table': 'refdata.regional_districts',
        'foreign_key': 'id_energy_zone',
        'reference_table': 'refdata.energy_zones'
    },
    # 3. regional_districts -> synchronous_areas
    {
        'table': 'refdata.regional_districts',
        'foreign_key': 'id_synchronous_area',
        'reference_table': 'refdata.synchronous_areas'
    },
    # 4. regional_energy_systems -> union_energy_systems
    {
        'table': 'refdata.regional_energy_systems',
        'foreign_key': 'id_union_energy_system',
        'reference_table': 'refdata.union_energy_systems'
    },
    # 5. energy_areas -> regional_districts
    {
        'table': 'refdata.energy_areas',
        'foreign_key': 'id_regional_district',
        'reference_table': 'refdata.regional_districts'
    },
    # 6. energy_units -> regional_districts
    {
        'table': 'refdata.energy_units',
        'foreign_key': 'id_regional_district',
        'reference_table': 'refdata.regional_districts'
    },
    # 7. energy_units -> regional_energy_systems
    {
        'table': 'refdata.energy_units',
        'foreign_key': 'id_regional_energy_system',
        'reference_table': 'refdata.regional_energy_systems'
    },
    
    # === СВЯЗИ В СХЕМЕ GENERATION ===
    # 8. stations -> station_groups (станции ссылаются на группы)
    {
        'table': 'gs_gen.stations',
        'foreign_key': 'id_station_group',
        'reference_table': 'gs_gen.station_groups'
    },
    # 9. station_powers -> stations (мощности станций ссылаются на станции)
    {
        'table': 'gs_gen.station_powers',
        'foreign_key': 'id_station',
        'reference_table': 'gs_gen.stations'
    },
    # 10. machines -> stations (машины ссылаются на станции)
    {
        'table': 'gs_gen.machines',
        'foreign_key': 'id_station',
        'reference_table': 'gs_gen.stations'
    },
    # 11. boilers -> stations (котлы ссылаются на станции)
    {
        'table': 'gs_gen.boilers',
        'foreign_key': 'id_station',
        'reference_table': 'gs_gen.stations'
    },
    # 12. machine_powers -> machines (мощности машин ссылаются на машины)
    {
        'table': 'gs_gen.machine_powers',
        'foreign_key': 'id_machine',
        'reference_table': 'gs_gen.machines'
    },
    # 13. machine_fuels -> machines (топливо машин ссылается на машины)
    {
        'table': 'gs_gen.machine_fuels',
        'foreign_key': 'id_machine',
        'reference_table': 'gs_gen.machines'
    },
    # 14. machine_tes_types -> machines (типы ТЭС машин ссылаются на машины)
    {
        'table': 'gs_gen.machine_tes_types',
        'foreign_key': 'id_machine',
        'reference_table': 'gs_gen.machines'
    },
    # 15. pgu_machines -> machines (ПГУ машины ссылаются на машины)
    {
        'table': 'gs_gen.pgu_machines',
        'foreign_key': 'id_parent_machine',
        'reference_table': 'gs_gen.machines'
    },
    # 16. pgu_machine_powers -> pgu_machines (мощности ПГУ машин ссылаются на ПГУ машины)
    {
        'table': 'gs_gen.pgu_machine_powers',
        'foreign_key': 'id_pgu_machine',
        'reference_table': 'gs_gen.pgu_machines'
    }
]
```

## Ключевые принципы

### 1. Иерархия зависимостей
- **Родительские таблицы** копируются первыми
- **Дочерние таблицы** копируются после родительских
- **Связи обновляются** в том же порядке

### 2. Соответствие ID
- Старые и новые ID должны получаться в **одинаковом порядке**
- Использовать `ORDER BY id` при копировании и получении соответствий
- Создавать маппинг `{старый_id: новый_id}` для каждой таблицы

### 3. Обновление связей
- Использовать **временные таблицы** для маппинга FK
- Обновлять foreign key через `JOIN` с временной таблицей
- Обрабатывать связи в **правильном порядке** зависимостей

## Исправленные функции

1. `_copy_version_data_fixed()` - исправленная версия копирования данных
2. `_update_version_relationships_fixed()` - исправленная версия обновления связей

## Результат

После применения исправлений:
- ✅ Машины правильно привязываются к станциям
- ✅ Мощности машин правильно привязываются к машинам
- ✅ **НОВОЕ**: Внешние ключи в таблицах refdata правильно привязываются к соответствующим записям новой версии
- ✅ **НОВОЕ**: regional_districts правильно ссылаются на federal_districts, energy_zones, synchronous_areas новой версии
- ✅ **НОВОЕ**: energy_areas и energy_units правильно ссылаются на regional_districts и regional_energy_systems новой версии
- ✅ Все остальные связи обновляются корректно
- ✅ Сохраняется целостность данных

## Тестирование

Для проверки правильности копирования:
1. Создать новую версию на основе существующей
2. Проверить, что все машины привязаны к правильным станциям
3. Проверить, что все мощности привязаны к правильным машинам
4. **НОВОЕ**: Проверить, что внешние ключи в regional_districts ссылаются на правильные записи новой версии
5. **НОВОЕ**: Проверить, что energy_areas и energy_units правильно ссылаются на regional_districts и regional_energy_systems новой версии
6. Проверить целостность данных через `_verify_version_data_integrity()`

### Автоматическое тестирование

Используйте скрипт `test_version_copying_fix.py` для автоматической проверки:
```bash
python test_version_copying_fix.py
```

Этот скрипт проверит:
- Соответствие внешних ключей в regional_districts
- Правильность ссылок на federal_districts, energy_zones, synchronous_areas
- Целостность данных в других таблицах refdata

---

# ПОЭТАПНАЯ логика удаления версий базы данных

## Принцип: Обратная логика копирования

При удалении версии базы данных применяется **обратная логика** копирования:
1. **ЭТАП 8-5**: Сначала удаляем таблицы GENERATION с максимальными зависимостями
2. **ЭТАП 4-2**: Затем удаляем таблицы REFDATA с зависимостями
3. **ЭТАП 1**: В конце удаляем полностью независимые таблицы

**Порядок: GENERATION -> REFDATA** (так как generation зависит от refdata)
Это предотвращает ошибки нарушения внешних ключей при удалении.

## Этапы удаления (в обратном порядке)

### ЭТАП 8: GENERATION - Таблицы с максимальными зависимостями (удаляем первыми)
```python
stage8_tables = [
    ('generation', 'pgu_machine_powers')
]
```

### ЭТАП 7: GENERATION - Таблицы, зависящие от machines
```python
stage7_tables = [
    ('generation', 'machine_powers'),
    ('generation', 'machine_fuels'),
    ('generation', 'machine_tes_types'),
    ('generation', 'pgu_machines')
]
```

### ЭТАП 6: GENERATION - Таблицы, зависящие от stations
```python
stage6_tables = [
    ('generation', 'station_powers'),
    ('generation', 'machines'),
    ('generation', 'boilers')
]
```

### ЭТАП 5: GENERATION - Таблицы с зависимостями
```python
stage5_tables = [
    ('generation', 'stations')
]
```

### ЭТАП 4: REFDATA - Таблицы с зависимостями от ЭТАПОВ 1-3
```python
stage4_tables = [
    ('refdata', 'energy_areas'),
    ('refdata', 'energy_units')
]
```

### ЭТАП 3: REFDATA - Таблицы с зависимостями от ЭТАПОВ 1-2
```python
stage3_tables = [
    ('refdata', 'regional_districts'),
    ('refdata', 'regional_energy_systems')
]
```

### ЭТАП 2: REFDATA - Таблицы с зависимостями от ЭТАПА 1
```python
stage2_tables = [
    ('refdata', 'union_energy_systems'),
    ('refdata', 'synchronous_areas'),
    ('refdata', 'energy_zones'),
    ('refdata', 'federal_districts')
]
```

### ЭТАП 1: REFDATA + GENERATION - Полностью независимые таблицы (удаляем последними)
```python
stage1_tables = [
    ('refdata', 'station_types'),
    ('refdata', 'machine_types'),
    ('refdata', 'tes_types'),
    ('refdata', 'tes_machine_types'),
    ('refdata', 'pgu_tes_machine_types'),
    ('refdata', 'condition_types'),
    ('refdata', 'technology_types'),
    ('refdata', 'technology_availabilities'),
    ('refdata', 'equipment_groups'),
    ('refdata', 'energy_system_types'),
    ('refdata', 'fuel_categories'),
    ('refdata', 'fuel_types'),
    ('refdata', 'fuels'),
    ('refdata', 'gen_companies'),
    ('generation', 'station_groups'),
    ('generation', 'documents_kommod')
]
```

## Функция удаления

```python
def _delete_version_data_staged(version_id, user):
    """
    Удаляет все данные, связанные с указанной версией, используя ПОЭТАПНУЮ логику в ОБРАТНОМ порядке.
    
    Логика удаления:
    1. Сначала удаляем таблицы GENERATION с максимальными зависимостями (ЭТАП 8-5)
    2. Затем удаляем таблицы REFDATA с зависимостями (ЭТАП 4-2)
    3. В конце удаляем полностью независимые таблицы (ЭТАП 1)
    
    Порядок: GENERATION -> REFDATA (так как generation зависит от refdata)
    Это предотвращает ошибки нарушения внешних ключей.
    """
```

## Преимущества поэтапного удаления

- ✅ **Предотвращение ошибок FK**: Удаление в правильном порядке исключает нарушения внешних ключей
- ✅ **Надежность**: Даже при ошибке в одной таблице процесс продолжается
- ✅ **Логирование**: Подробное логирование каждого этапа удаления
- ✅ **Симметричность**: Логика удаления зеркально отражает логику копирования

## Тестирование удаления

Для проверки правильности удаления используйте скрипт:
```bash
python test_staged_version_deletion_logic.py
```

Этот скрипт:
1. Создает тестовую версию
2. Копирует в неё данные
3. Проверяет, что данные скопированы
4. Удаляет данные поэтапно
5. Проверяет, что все данные удалены
6. Очищает тестовые данные
