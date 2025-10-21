# Версионирование связанных сущностей

## 🎯 Проблема

При изменении **связанных сущностей** агрегата (Machine):
- **Мощности** (`MachinePower`)
- **Типы ТЭС** (`MachineTesType`)
- **Типы топлива** (`MachineFuel`)

Версия основной записи `Machine` **НЕ увеличивалась** автоматически, потому что эти данные хранятся в отдельных таблицах.

### Проблемный сценарий:

```
Пользователь А: открывает агрегат (version=1)
Пользователь Б: открывает тот же агрегат (version=1)

Пользователь А: изменяет мощность p_ust = 150 МВт
                → MachinePower обновляется
                → Machine.version остаётся = 1  ❌

Пользователь Б: изменяет тип ТЭС
                → Проверка version: 1 == 1  ✅ Ошибочно пропускает!
                → Изменения пользователя А ПОТЕРЯНЫ  ❌
```

---

## ✅ Решение

При изменении связанных сущностей **принудительно обновляем** `Machine.updated_at`, что заставляет SQLAlchemy увеличить `version`.

### Реализация

**Файл:** `app/generation/services/machine_services/machine_services.py`

```python
# Добавлен флаг для отслеживания изменений
related_entities_changed = False

# При изменении мощности
if not is_same_decimal(old_val, val):
    setattr(mp, attr, val)
    flag_modified(mp, attr)
    changes.append(...)
    related_entities_changed = True  # ← Отмечаем изменение

# При изменении типа ТЭС
if mt.id_tes_type != new_tt and new_tt is not None:
    ...
    mt.id_tes_type = new_tt
    related_entities_changed = True  # ← Отмечаем изменение

# При изменении топлива
if mf.id_fuel != new_fuel and new_fuel is not None:
    ...
    mf.id_fuel = new_fuel
    related_entities_changed = True  # ← Отмечаем изменение

# После всех изменений
if related_entities_changed:
    from sqlalchemy.sql import func
    machine.updated_at = func.now()
    flag_modified(machine, 'updated_at')
    # Теперь version автоматически увеличится при commit()
```

---

## 🔧 Как это работает

### 1. **Отслеживание изменений**
Флаг `related_entities_changed` устанавливается в `True` при любом изменении:
- Мощностей (`p_ust`, `p_ogr`, `p_rasp`)
- Типа ТЭС (`id_tes_type`)
- Типа топлива (`id_fuel`)

### 2. **Принудительное обновление Machine**
```python
machine.updated_at = func.now()
flag_modified(machine, 'updated_at')
```

Это сообщает SQLAlchemy, что запись `Machine` изменилась.

### 3. **Автоматический инкремент version**
SQLAlchemy автоматически увеличивает `version` при `commit()`, потому что:
- Модель `Machine` наследует `VersionedModelMixin`
- В `__mapper_args__` указано `version_id_col`
- Запись помечена как "modified" через `flag_modified()`

---

## ✅ Результат

Теперь версионирование работает корректно:

```
Пользователь А: открывает агрегат (version=1)
Пользователь Б: открывает тот же агрегат (version=1)

Пользователь А: изменяет мощность p_ust = 150 МВт
                → MachinePower обновляется
                → Machine.updated_at обновляется
                → Machine.version становится = 2  ✅

Пользователь Б: изменяет тип ТЭС
                → Проверка version: 1 != 2  ❌ БЛОКИРОВКА!
                → Сообщение: "Данные были изменены..."
                → Изменения пользователя А СОХРАНЕНЫ  ✅
```

---

## 🧪 Тестирование

### Тест-сценарий 1: Изменение мощностей

1. Откройте страницу агрегата в двух вкладках
2. В первой вкладке измените мощность (p_ust) и сохраните
3. Во второй вкладке (не обновляя) попробуйте изменить тип ТЭС
4. **Ожидается:** Ошибка concurrent update

### Тест-сценарий 2: Изменение типа топлива

1. Откройте страницу агрегата в двух вкладках
2. В первой вкладке измените тип топлива и сохраните
3. Во второй вкладке (не обновляя) попробуйте изменить мощность
4. **Ожидается:** Ошибка concurrent update

### Автоматический тест

Запустите скрипт:
```bash
python test_related_version.py
```

**Ожидаемый результат:**
```
Machine ID: 1
Initial version: X
After power change version: X+1  ← Версия увеличилась!
SUCCESS: Version incremented!
```

---

## 📋 Изменённые файлы

1. **`app/generation/services/machine_services/machine_services.py`**
   - Добавлен флаг `related_entities_changed`
   - Добавлено обновление `machine.updated_at` при изменении связанных сущностей
   - Строки: ~312-362

---

## 🎯 Защищённые сущности

После этого исправления версионирование работает для:

✅ **Прямые изменения Machine:**
- `machine_name`, `machine_number`
- `id_condition_type`, `id_gen_company`
- `note`, `change_document`
- Даты (`date_exploitation`, `date_commission_fact`, и т.д.)

✅ **Связанные сущности (ИСПРАВЛЕНО):**
- `MachinePower` (p_ust, p_ogr, p_rasp)
- `MachineTesType` (id_tes_type)
- `MachineFuel` (id_fuel)

✅ **ПГУ машины:**
- `PGUMachine` (имеет собственное версионирование)
- `PGUMachinePower`

---

## 💡 Важные замечания

### 1. Почему обновляем `updated_at`, а не `version`?

```python
# ❌ НЕПРАВИЛЬНО:
machine.version += 1  # Ручное увеличение конфликтует с SQLAlchemy

# ✅ ПРАВИЛЬНО:
machine.updated_at = func.now()
flag_modified(machine, 'updated_at')
# SQLAlchemy сам увеличит version
```

SQLAlchemy управляет `version` автоматически. Мы просто помечаем запись как "изменённую".

### 2. Использование `flag_modified()`

```python
flag_modified(machine, 'updated_at')
```

Это **обязательно**, чтобы SQLAlchemy понял, что запись изменилась, даже если мы используем `func.now()` (серверная функция).

### 3. Транзакционность

Все изменения (MachinePower, Machine.version) происходят в **одной транзакции**, поэтому:
- Либо сохраняются ВСЕ изменения
- Либо НЕ сохраняется НИЧЕГО (откат при ошибке)

---

## 🔄 Аналогичные места

Такой же подход можно применить к:

1. **Станции** при изменении `StationPower`
2. **ПГУ машинам** при изменении `PGUMachinePower` (уже реализовано)
3. Любым моделям со связанными сущностями в отдельных таблицах

---

**Дата реализации:** 17 октября 2025  
**Статус:** ✅ Реализовано и протестировано

