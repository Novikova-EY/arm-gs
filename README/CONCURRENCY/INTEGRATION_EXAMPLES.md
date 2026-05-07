# Примеры интеграции функций параллельной работы

Этот документ содержит практические примеры интеграции функций параллельной работы в существующий код.

## Оглавление

1. [Обработка concurrent updates в маршрутах](#обработка-concurrent-updates-в-маршрутах)
2. [Использование кэширования](#использование-кэширования)
3. [Версионирование в моделях](#версионирование-в-моделях)
4. [Retry механизм](#retry-механизм)
5. [Пример полной интеграции](#пример-полной-интеграции)

---

## Обработка concurrent updates в маршрутах

### Пример 1: Обновление электростанции

**До:**
```python
@station_bp.route('/station/<int:id>/update', methods=['POST'])
@login_required
def update_station(id):
    station = Station.query.get_or_404(id)
    station.name = request.form['name']
    station.location = request.form['location']
    db.session.commit()
    flash('Станция обновлена успешно', 'success')
    return redirect(url_for('station_bp.station_details', id=id))
```

**После:**
```python
from app.common.middleware import handle_stale_data

@station_bp.route('/station/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data  # Добавляем декоратор
def update_station(id):
    station = Station.query.get_or_404(id)
    
    # Проверка версии из формы (опционально, для дополнительной безопасности)
    form_version = request.form.get('version', type=int)
    if form_version and station.version != form_version:
        flash('Данные были изменены другим пользователем. Пожалуйста, обновите страницу.', 'error')
        return redirect(url_for('station_bp.station_details', id=id))
    
    station.name = request.form['name']
    station.location = request.form['location']
    db.session.commit()
    flash('Станция обновлена успешно', 'success')
    return redirect(url_for('station_bp.station_details', id=id))
```

**В шаблоне (добавить скрытое поле version):**
```html
<form method="POST">
    <input type="hidden" name="version" value="{{ station.version }}">
    <input type="text" name="name" value="{{ station.name }}">
    <input type="text" name="location" value="{{ station.location }}">
    <button type="submit">Сохранить</button>
</form>
```

### Пример 2: Обновление агрегата (машины)

```python
from app.common.middleware import handle_stale_data
from app.common.services.cache_decorator import invalidate_cache

@station_bp.route('/machine/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data
def update_machine(id):
    machine = Machine.query.get_or_404(id)
    
    machine.machine_name = request.form['machine_name']
    machine.machine_number = request.form['machine_number']
    machine.note = request.form.get('note', '')
    
    db.session.commit()
    
    # Инвалидация кэша после успешного обновления
    invalidate_cache('machine', machine_id=id)
    invalidate_cache('station', station_id=machine.id_station)
    
    flash('Агрегат обновлен успешно', 'success')
    log_to_db(session.get('username'), f'Обновлен агрегат {machine.machine_name}')
    
    return redirect(url_for('station_bp.machine_details', id=id))
```

### Пример 3: AJAX обновление

```python
from app.common.middleware import handle_stale_data

@station_bp.route('/api/station/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data
def api_update_station(id):
    station = Station.query.get_or_404(id)
    
    data = request.get_json()
    station.name = data.get('name', station.name)
    station.location = data.get('location', station.location)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Станция обновлена успешно',
        'version': station.version,  # Возвращаем новую версию
        'updated_at': station.updated_at.isoformat()
    })
```

**JavaScript для AJAX запроса:**
```javascript
async function updateStation(stationId, data) {
    try {
        const response = await fetch(`/api/station/${stationId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.status === 409) {
            // Concurrent update detected
            alert(result.message);
            location.reload();  // Обновить страницу
        } else if (result.success) {
            // Обновить версию на странице
            document.getElementById('station-version').value = result.version;
            alert('Данные обновлены успешно');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Произошла ошибка при обновлении');
    }
}
```

---

## Использование кэширования

### Пример 1: Кэширование списка станций

```python
from app.common.services.cache_decorator import cached_route, invalidate_cache

@station_bp.route("/station_list", methods=["GET"])
@login_required
@cached_route(timeout=300, key_prefix='station_list')  # Кэш на 5 минут
def station_list():
    """Маршрут для отображения списка всех электростанций."""
    
    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    per_page = filters.pop("per_page", 10)
    
    stations = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page
    )
    
    return render_template('station_list.html', stations=stations)
```

### Пример 2: Кэширование запросов к БД

```python
from app.common.services.cache_decorator import cached_query

@cached_query(timeout=600, key_prefix='station_details')
def get_station_with_relations(station_id):
    """Получение электростанции со всеми связанными данными."""
    return Station.query\
        .options(
            joinedload(Station.machines),
            joinedload(Station.station_powers),
            joinedload(Station.regional_district)
        )\
        .get(station_id)

@station_bp.route('/station/<int:id>')
@login_required
def station_details(id):
    station = get_station_with_relations(id)
    if not station:
        abort(404)
    return render_template('station_details.html', station=station)
```

### Пример 3: Инвалидация кэша при изменении данных

```python
from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern

@station_bp.route('/station/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data
def update_station(id):
    station = Station.query.get_or_404(id)
    station.name = request.form['name']
    db.session.commit()
    
    # Инвалидация кэша для конкретной электростанции
    invalidate_cache('station_details', station_id=id)
    
    # Инвалидация всех кэшей списков станций
    invalidate_cache_pattern('station_list:*')
    
    flash('Станция обновлена успешно', 'success')
    return redirect(url_for('station_bp.station_details', id=id))
```

### Пример 4: Кэширование справочников

```python
from app.common.services.cache_decorator import cached_query

@cached_query(timeout=3600, key_prefix='refdata_station_types')
def get_all_station_types():
    """Получение всех типов станций (кэш на 1 час)."""
    return StationType.query.order_by(StationType.name).all()

@cached_query(timeout=3600, key_prefix='refdata_machine_types')
def get_all_machine_types():
    """Получение всех типов агрегатов (кэш на 1 час)."""
    return MachineType.query.order_by(MachineType.name).all()

# Использование в форме
@station_bp.route('/station/add', methods=['GET', 'POST'])
@login_required
def add_station():
    form = AddStationForm()
    
    # Данные для выпадающих списков берутся из кэша
    form.station_type.choices = [(t.id, t.name) for t in get_all_station_types()]
    
    if form.validate_on_submit():
        # ... сохранение данных
        pass
    
    return render_template('add_station.html', form=form)
```

---

## Версионирование в моделях

### Пример 1: Добавление версионирования к существующей модели

```python
# Было:
class StationGroup(db.Model):
    __tablename__ = 'station_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

# Стало:
from app.common.models.versioned_model import VersionedModelMixin

class StationGroup(db.Model, VersionedModelMixin):
    __tablename__ = 'station_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # version колонка добавляется автоматически через миксин
```

**Создание миграции:**
```bash
flask db revision -m "add version to station_groups"
```

**В файле миграции:**
```python
def upgrade():
    op.add_column(
        'station_groups',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        schema='gs_gen'
    )

def downgrade():
    op.drop_column('station_groups', 'version', schema='gs_gen')
```

### Пример 2: Программная проверка версии

```python
def update_station_with_version_check(station_id, data, expected_version):
    """
    Обновление электростанции с явной проверкой версии.
    
    Args:
        station_id: ID электростанции
        data: Данные для обновления
        expected_version: Ожидаемая версия записи
    
    Returns:
        tuple: (success, message, new_version)
    """
    station = Station.query.get_or_404(station_id)
    
    if station.version != expected_version:
        return False, "Данные были изменены другим пользователем", station.version
    
    # Обновление данных
    for key, value in data.items():
        if hasattr(station, key):
            setattr(station, key, value)
    
    try:
        db.session.commit()
        return True, "Успешно обновлено", station.version
    except StaleDataError:
        db.session.rollback()
        return False, "Конфликт версий", None
```

---

## Retry механизм

### Пример 1: Критичная операция с retry

```python
from app.common.middleware import with_db_retry

@with_db_retry(max_attempts=3, backoff_factor=0.5)
def process_station_batch(station_ids, operation):
    """
    Пакетная обработка станций с автоматическими повторами.
    
    Args:
        station_ids: Список ID станций
        operation: Функция операции для применения
    """
    for station_id in station_ids:
        station = Station.query.get(station_id)
        if station:
            operation(station)
    
    db.session.commit()

# Использование
@station_bp.route('/stations/batch_update', methods=['POST'])
@login_required
def batch_update_stations():
    station_ids = request.form.getlist('station_ids', type=int)
    
    def update_operation(station):
        station.note = "Обновлено пакетно"
    
    try:
        process_station_batch(station_ids, update_operation)
        flash(f'Успешно обновлено {len(station_ids)} станций', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении: {str(e)}', 'error')
    
    return redirect(url_for('station_bp.station_list'))
```

### Пример 2: Retry для внешних API

```python
from app.common.middleware import with_db_retry
import requests

@with_db_retry(max_attempts=5, backoff_factor=1.0)
def fetch_and_save_external_data(station_id):
    """
    Получение данных из внешнего API и сохранение в БД.
    """
    # Запрос к внешнему API
    response = requests.get(f'https://api.example.com/station/{station_id}')
    response.raise_for_status()
    
    data = response.json()
    
    # Обновление данных в БД
    station = Station.query.get(station_id)
    if station:
        station.external_data = data
        db.session.commit()
```

---

## Пример полной интеграции

### Сервис с кэшированием и версионированием

```python
# app/generation/services/station_services/enhanced_station_services.py

from app.extensions import db
from app.generation.models.station.station_model import Station
from app.common.services.cache_decorator import cached_query, invalidate_cache, invalidate_cache_pattern
from app.common.middleware import handle_stale_data, with_db_retry
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import StaleDataError
import logging

logger = logging.getLogger(__name__)


@cached_query(timeout=600, key_prefix='station_full')
def get_station_full(station_id):
    """
    Получение электростанции со всеми связанными данными с кэшированием.
    """
    return Station.query\
        .options(
            joinedload(Station.machines).joinedload('machine_powers'),
            joinedload(Station.machines).joinedload('machine_fuels'),
            joinedload(Station.station_powers),
            joinedload(Station.regional_district),
            joinedload(Station.energy_unit)
        )\
        .get(station_id)


@with_db_retry(max_attempts=3, backoff_factor=0.5)
def update_station_safe(station_id, data, expected_version=None):
    """
    Безопасное обновление электростанции с проверкой версии и retry.
    
    Args:
        station_id: ID электростанции
        data: Словарь с данными для обновления
        expected_version: Ожидаемая версия (опционально)
    
    Returns:
        tuple: (success: bool, message: str, station: Station or None)
    """
    station = Station.query.get(station_id)
    
    if not station:
        return False, "Станция не найдена", None
    
    # Проверка версии
    if expected_version and station.version != expected_version:
        return False, f"Конфликт версий (текущая: {station.version}, ожидаемая: {expected_version})", station
    
    try:
        # Обновление полей
        for key, value in data.items():
            if hasattr(station, key) and key not in ['id', 'version', 'created_at']:
                setattr(station, key, value)
        
        db.session.commit()
        
        # Инвалидация кэша
        invalidate_cache('station_full', station_id=station_id)
        invalidate_cache_pattern('station_list:*')
        
        logger.info(f"Station {station_id} updated successfully to version {station.version}")
        return True, "Станция успешно обновлена", station
        
    except StaleDataError:
        db.session.rollback()
        logger.warning(f"StaleDataError when updating station {station_id}")
        return False, "Данные были изменены другим пользователем", None


def bulk_update_stations(station_ids, update_func):
    """
    Пакетное обновление станций с обработкой ошибок.
    
    Args:
        station_ids: Список ID станций
        update_func: Функция для обновления (принимает station как аргумент)
    
    Returns:
        dict: Статистика операции
    """
    stats = {
        'total': len(station_ids),
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for station_id in station_ids:
        try:
            station = Station.query.get(station_id)
            if station:
                update_func(station)
                db.session.commit()
                
                # Инвалидация кэша для каждой электростанции
                invalidate_cache('station_full', station_id=station_id)
                
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['errors'].append(f"Станция {station_id} не найдена")
                
        except StaleDataError:
            db.session.rollback()
            stats['failed'] += 1
            stats['errors'].append(f"Конфликт версии для электростанции {station_id}")
            logger.warning(f"StaleDataError for station {station_id}")
            
        except Exception as e:
            db.session.rollback()
            stats['failed'] += 1
            stats['errors'].append(f"Ошибка для электростанции {station_id}: {str(e)}")
            logger.error(f"Error updating station {station_id}: {str(e)}")
    
    # Инвалидация кэша списков
    invalidate_cache_pattern('station_list:*')
    
    return stats
```

### Маршрут с полной интеграцией

```python
# app/generation/routes/stations/enhanced_station_routes.py

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.generation.routes.stations import station_bp
from app.generation.services.station_services.enhanced_station_services import (
    get_station_full,
    update_station_safe,
    bulk_update_stations
)
from app.common.middleware import handle_stale_data
from app.logs.services.logging_service import log_to_db


@station_bp.route('/station/<int:id>')
@login_required
def enhanced_station_details(id):
    """
    Детальная информация о электростанции с кэшированием.
    """
    station = get_station_full(id)
    
    if not station:
        flash('Станция не найдена', 'error')
        return redirect(url_for('station_bp.station_list'))
    
    return render_template(
        'generation/stations/station_details.html',
        station=station
    )


@station_bp.route('/station/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data
def enhanced_update_station(id):
    """
    Обновление электростанции с версионированием и кэшированием.
    """
    # Получение данных из формы
    data = {
        'name': request.form.get('name'),
        'name_so': request.form.get('name_so'),
        'location': request.form.get('location'),
        'note': request.form.get('note'),
        'id_regional_district': request.form.get('id_regional_district', type=int),
        'id_condition_type': request.form.get('id_condition_type', type=int),
    }
    
    # Удаляем None значения
    data = {k: v for k, v in data.items() if v is not None}
    
    # Получение версии из формы
    expected_version = request.form.get('version', type=int)
    
    # Обновление
    success, message, station = update_station_safe(id, data, expected_version)
    
    if success:
        flash(message, 'success')
        log_to_db(request.form.get('username', 'Unknown'), f'Обновлена станция {station.name}')
    else:
        flash(message, 'error')
    
    return redirect(url_for('station_bp.enhanced_station_details', id=id))


@station_bp.route('/api/station/<int:id>/update', methods=['POST'])
@login_required
@handle_stale_data
def api_enhanced_update_station(id):
    """
    API для обновления электростанции (AJAX).
    """
    data = request.get_json()
    expected_version = data.pop('version', None)
    
    success, message, station = update_station_safe(id, data, expected_version)
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'version': station.version,
            'updated_at': station.updated_at.isoformat()
        })
    else:
        status_code = 409 if 'конфликт' in message.lower() or 'изменены' in message.lower() else 400
        return jsonify({
            'success': False,
            'error': message,
            'version': station.version if station else None
        }), status_code


@station_bp.route('/stations/batch_update', methods=['POST'])
@login_required
def enhanced_batch_update():
    """
    Пакетное обновление станций.
    """
    station_ids = request.form.getlist('station_ids', type=int)
    update_type = request.form.get('update_type')
    
    if not station_ids:
        flash('Не выбраны электростанции для обновления', 'error')
        return redirect(url_for('station_bp.station_list'))
    
    # Определяем функцию обновления
    if update_type == 'add_note':
        note_text = request.form.get('note_text', '')
        def update_func(station):
            station.note = note_text
    elif update_type == 'change_condition':
        condition_id = request.form.get('condition_id', type=int)
        def update_func(station):
            station.id_condition_type = condition_id
    else:
        flash('Неизвестный тип обновления', 'error')
        return redirect(url_for('station_bp.station_list'))
    
    # Выполнение пакетного обновления
    stats = bulk_update_stations(station_ids, update_func)
    
    # Отображение результатов
    if stats['success'] > 0:
        flash(f"Успешно обновлено: {stats['success']} из {stats['total']} станций", 'success')
    
    if stats['failed'] > 0:
        flash(f"Не удалось обновить: {stats['failed']} станций", 'error')
        for error in stats['errors'][:5]:  # Показываем первые 5 ошибок
            flash(error, 'warning')
    
    return redirect(url_for('station_bp.station_list'))
```

---

## Дополнительные рекомендации

1. **Всегда используйте** `@handle_stale_data` для маршрутов обновления данных
2. **Кэшируйте** часто используемые данные (списки, справочники, детали)
3. **Инвалидируйте** кэш сразу после изменения данных
4. **Используйте** retry механизм для критичных операций
5. **Добавляйте** версию в формы для дополнительной защиты
6. **Логируйте** все concurrent update события для анализа
7. **Тестируйте** concurrent updates на нескольких вкладках браузера

---

Для получения дополнительной информации см. `CONCURRENCY_SETUP.md`.

