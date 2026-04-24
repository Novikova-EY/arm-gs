# -*- coding: utf-8 -*-
"""
Сервис сравнения версий БД.
"""

from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from sqlalchemy import text, inspect
from collections import defaultdict
from datetime import datetime


def get_version_statistics(version_id):
    """
    Получает статистику по версии БД.
    
    Args:
        version_id: ID версии для статистики
        
    Returns:
        dict: Статистика по таблицам и количеству записей
    """
    from config import SCHEMA_GENERATION, SCHEMA_REFDATA
    
    stats = {
        'version_id': version_id,
        'tables': {},
        'total_records': 0
    }
    
    # Список таблиц для проверки
    tables_to_check = [
        # Generation tables
        (SCHEMA_GENERATION, 'stations'),
        (SCHEMA_GENERATION, 'machines'),
        (SCHEMA_GENERATION, 'station_powers'),
        (SCHEMA_GENERATION, 'machine_powers'),
        (SCHEMA_GENERATION, 'machine_fuels'),
        (SCHEMA_GENERATION, 'pgu_machines'),
        (SCHEMA_GENERATION, 'boilers'),
        (SCHEMA_GENERATION, 'documents'),
        # Refdata tables
        (SCHEMA_REFDATA, 'gs_sys_companies'),
        (SCHEMA_REFDATA, 'fuels'),
        (SCHEMA_REFDATA, 'fuel_types'),
        (SCHEMA_REFDATA, 'regional_districts'),
        (SCHEMA_REFDATA, 'federal_districts'),
    ]
    
    for schema, table in tables_to_check:
        try:
            # Подсчет записей для данной версии
            query = text(f"""
                SELECT COUNT(*) as count
                FROM {schema}.{table}
                WHERE database_version_id = :version_id 
                   OR database_version_id IS NULL
            """)
            
            result = db.session.execute(query, {'version_id': version_id}).fetchone()
            count = result[0] if result else 0
            
            stats['tables'][f'{schema}.{table}'] = count
            stats['total_records'] += count
        except Exception as e:
            # Таблица может не существовать или не иметь поле database_version_id
            stats['tables'][f'{schema}.{table}'] = 0
    
    return stats


def compare_versions(version_id_1, version_id_2):
    """
    Сравнивает две версии БД и возвращает различия.
    
    Args:
        version_id_1: ID первой версии
        version_id_2: ID второй версии
        
    Returns:
        dict: Словарь с различиями между версиями
    """
    # Получаем информацию о версиях
    version1 = db.session.get(DatabaseVersion, version_id_1)
    version2 = db.session.get(DatabaseVersion, version_id_2)
    
    if not version1 or not version2:
        raise ValueError("Одна или обе версии не найдены")
    
    # Получаем статистику по версиям
    stats1 = get_version_statistics(version_id_1)
    stats2 = get_version_statistics(version_id_2)
    
    # Сравниваем статистику
    comparison = {
        'version1': {
            'id': version1.id,
            'name': version1.name,
            'version_number': version1.version_number,
            'created_at': version1.created_at,
            'stats': stats1
        },
        'version2': {
            'id': version2.id,
            'name': version2.name,
            'version_number': version2.version_number,
            'created_at': version2.created_at,
            'stats': stats2
        },
        'differences': {}
    }
    
    # Вычисляем различия по таблицам
    all_tables = set(stats1['tables'].keys()) | set(stats2['tables'].keys())
    
    for table in sorted(all_tables):
        count1 = stats1['tables'].get(table, 0)
        count2 = stats2['tables'].get(table, 0)
        diff = count2 - count1
        
        if diff != 0:
            comparison['differences'][table] = {
                'version1_count': count1,
                'version2_count': count2,
                'difference': diff,
                'change_percent': round((diff / count1 * 100) if count1 > 0 else 100, 2)
            }
    
    # Общая статистика различий
    comparison['summary'] = {
        'total_version1': stats1['total_records'],
        'total_version2': stats2['total_records'],
        'total_difference': stats2['total_records'] - stats1['total_records'],
        'tables_changed': len(comparison['differences']),
        'tables_total': len(all_tables)
    }
    
    return comparison


def get_detailed_changes(version_id_1, version_id_2, table_schema, table_name, limit=100):
    """
    Получает детальные изменения между версиями для конкретной таблицы.
    
    Args:
        version_id_1: ID первой версии
        version_id_2: ID второй версии
        table_schema: Схема таблицы
        table_name: Имя таблицы
        limit: Максимальное количество записей для отображения
        
    Returns:
        dict: Детальная информация об изменениях
    """
    changes = {
        'added': [],
        'removed': [],
        'table': f'{table_schema}.{table_name}'
    }
    
    try:
        # Получаем записи, добавленные во второй версии
        query_added = text(f"""
            SELECT * FROM {table_schema}.{table_name}
            WHERE database_version_id = :version_id_2
            LIMIT :limit
        """)
        
        results_added = db.session.execute(
            query_added, 
            {'version_id_2': version_id_2, 'limit': limit}
        ).fetchall()
        
        # Преобразуем в список словарей
        if results_added:
            columns = results_added[0]._fields
            changes['added'] = [
                dict(zip(columns, row)) 
                for row in results_added
            ]
        
        # Получаем записи, которые были в первой версии, но не во второй
        query_removed = text(f"""
            SELECT * FROM {table_schema}.{table_name}
            WHERE database_version_id = :version_id_1
            AND id NOT IN (
                SELECT id FROM {table_schema}.{table_name}
                WHERE database_version_id = :version_id_2
                   OR database_version_id IS NULL
            )
            LIMIT :limit
        """)
        
        results_removed = db.session.execute(
            query_removed,
            {'version_id_1': version_id_1, 'version_id_2': version_id_2, 'limit': limit}
        ).fetchall()
        
        if results_removed:
            columns = results_removed[0]._fields
            changes['removed'] = [
                dict(zip(columns, row))
                for row in results_removed
            ]
        
    except Exception as e:
        # Если возникла ошибка (таблица не существует или другая проблема)
        changes['error'] = str(e)
    
    changes['added_count'] = len(changes['added'])
    changes['removed_count'] = len(changes['removed'])
    
    return changes


def export_comparison_to_excel(version_id_1, version_id_2):
    """
    Экспортирует сравнение версий в Excel.
    
    Args:
        version_id_1: ID первой версии
        version_id_2: ID второй версии
        
    Returns:
        BytesIO: Excel файл с результатами сравнения
    """
    import pandas as pd
    from io import BytesIO
    
    # Получаем сравнение
    comparison = compare_versions(version_id_1, version_id_2)
    
    # Подготовка данных для Excel
    # 1. Общая информация
    summary_data = {
        'Метрика': [
            'Версия 1 (ID)',
            'Версия 1 (Название)',
            'Версия 2 (ID)',
            'Версия 2 (Название)',
            'Общее количество записей (Версия 1)',
            'Общее количество записей (Версия 2)',
            'Разница',
            'Таблиц изменено',
            'Всего таблиц'
        ],
        'Значение': [
            comparison['version1']['version_number'],
            comparison['version1']['name'],
            comparison['version2']['version_number'],
            comparison['version2']['name'],
            comparison['summary']['total_version1'],
            comparison['summary']['total_version2'],
            comparison['summary']['total_difference'],
            comparison['summary']['tables_changed'],
            comparison['summary']['tables_total']
        ]
    }
    
    # 2. Детальные различия по таблицам
    diff_data = []
    for table, diff_info in comparison['differences'].items():
        diff_data.append({
            'Таблица': table,
            'Количество (Версия 1)': diff_info['version1_count'],
            'Количество (Версия 2)': diff_info['version2_count'],
            'Разница': diff_info['difference'],
            'Изменение (%)': f"{diff_info['change_percent']}%"
        })
    
    # Создание Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Лист 1: Общая информация
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Общая информация', index=False)
        
        # Лист 2: Различия по таблицам
        if diff_data:
            df_diff = pd.DataFrame(diff_data)
            df_diff.to_excel(writer, sheet_name='Различия по таблицам', index=False)
        
        # Авто-ширина столбцов
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for i, col in enumerate(writer.sheets[sheet_name].columns):
                max_len = max(
                    len(str(col.header)),
                    *(len(str(val)) for val in col.values)
                ) if hasattr(col, 'values') else len(str(col))
                worksheet.set_column(i, i, min(max_len + 2, 60))
    
    output.seek(0)
    return output

