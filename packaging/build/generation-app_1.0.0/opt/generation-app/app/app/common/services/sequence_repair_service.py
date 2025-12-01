"""
Сервис для проверки и исправления последовательностей (sequences) в PostgreSQL.

Этот модуль предоставляет функции для автоматического исправления последовательностей
таблиц, когда возникают проблемы с автоинкрементом ID.
"""
from sqlalchemy import text
from app.extensions import db
from typing import List, Dict, Tuple


def get_all_sequences() -> List[Tuple[str, str, str]]:
    """
    Получает список всех последовательностей в базе данных.
    
    Returns:
        List[Tuple[str, str, str]]: Список кортежей (schema, table, column)
    """
    query = text("""
        SELECT 
            n.nspname as schema_name,
            c.relname as table_name,
            a.attname as column_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        JOIN pg_attrdef ad ON ad.adrelid = c.oid AND ad.adnum = a.attnum
        WHERE c.relkind = 'r'
          AND n.nspname IN ('generation', 'refdata', 'auth', 'logs')
          AND pg_get_expr(ad.adbin, ad.adrelid) LIKE 'nextval%'
          AND a.attname = 'id'
        ORDER BY n.nspname, c.relname
    """)
    
    with db.engine.connect() as conn:
        result = conn.execute(query)
        return [(row[0], row[1], row[2]) for row in result]


def check_sequence_status(schema: str, table: str, col: str = "id") -> Dict:
    """
    Проверяет статус последовательности для указанной таблицы.
    
    Args:
        schema: Схема базы данных
        table: Имя таблицы
        col: Имя колонки с последовательностью (по умолчанию "id")
        
    Returns:
        Dict: Словарь с информацией о последовательности
    """
    with db.engine.connect() as conn:
        # Получаем имя последовательности
        seq = conn.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": f"{schema}.{table}", "col": col}
        ).scalar()
        
        if not seq:
            return {
                "schema": schema,
                "table": table,
                "column": col,
                "sequence": None,
                "status": "no_sequence"
            }
        
        # Получаем текущее значение последовательности
        current_seq_val = conn.execute(
            text(f"SELECT last_value FROM {seq}")
        ).scalar()
        
        # Получаем максимальное значение в таблице
        max_id = conn.execute(
            text(f"SELECT COALESCE(MAX({col}), 0) FROM {schema}.{table}")
        ).scalar()
        
        # Получаем количество записей
        count = conn.execute(
            text(f"SELECT COUNT(*) FROM {schema}.{table}")
        ).scalar()
        
        status = "ok" if current_seq_val >= max_id else "needs_fix"
        
        return {
            "schema": schema,
            "table": table,
            "column": col,
            "sequence": seq,
            "current_value": current_seq_val,
            "max_id": max_id,
            "count": count,
            "status": status,
            "difference": max_id - current_seq_val if current_seq_val < max_id else 0
        }


def fix_sequence(schema: str, table: str, col: str = "id") -> Dict:
    """
    Исправляет последовательность для указанной таблицы.
    
    Args:
        schema: Схема базы данных
        table: Имя таблицы
        col: Имя колонки с последовательностью (по умолчанию "id")
        
    Returns:
        Dict: Результат исправления
    """
    status_before = check_sequence_status(schema, table, col)
    
    if status_before["status"] == "no_sequence":
        return {
            "success": False,
            "message": f"Последовательность не найдена для {schema}.{table}.{col}"
        }
    
    if status_before["status"] == "ok":
        return {
            "success": True,
            "message": f"Последовательность {schema}.{table} не нуждается в исправлении",
            "status_before": status_before
        }
    
    with db.engine.begin() as conn:
        seq = status_before["sequence"]
        max_id = status_before["max_id"]
        
        conn.execute(
            text(f"SELECT setval('{seq}', {int(max_id)}, true)")
        )
    
    status_after = check_sequence_status(schema, table, col)
    
    return {
        "success": True,
        "message": f"Последовательность {schema}.{table} исправлена: {status_before['current_value']} -> {status_after['current_value']}",
        "status_before": status_before,
        "status_after": status_after
    }


def check_all_sequences() -> List[Dict]:
    """
    Проверяет все последовательности в базе данных.
    
    Returns:
        List[Dict]: Список статусов всех последовательностей
    """
    sequences = get_all_sequences()
    results = []
    
    for schema, table, col in sequences:
        status = check_sequence_status(schema, table, col)
        results.append(status)
    
    return results


def fix_all_sequences() -> Dict:
    """
    Исправляет все последовательности, которые нуждаются в исправлении.
    
    Returns:
        Dict: Сводка результатов
    """
    sequences = get_all_sequences()
    results = {
        "total": len(sequences),
        "fixed": 0,
        "ok": 0,
        "errors": 0,
        "details": []
    }
    
    for schema, table, col in sequences:
        try:
            result = fix_sequence(schema, table, col)
            if result["success"]:
                status = result.get("status_before", {}).get("status")
                if status == "needs_fix":
                    results["fixed"] += 1
                elif status == "ok":
                    results["ok"] += 1
            results["details"].append(result)
        except Exception as e:
            results["errors"] += 1
            results["details"].append({
                "success": False,
                "schema": schema,
                "table": table,
                "message": f"Ошибка: {str(e)}"
            })
    
    return results

