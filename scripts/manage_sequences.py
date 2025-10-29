"""
CLI утилита для проверки и исправления последовательностей PostgreSQL.

Использование:
    python manage_sequences.py check              - Проверить все последовательности
    python manage_sequences.py fix                - Исправить все последовательности
    python manage_sequences.py check stations     - Проверить конкретную таблицу
    python manage_sequences.py fix stations       - Исправить конкретную таблицу
"""
import sys
from app import create_app
from app.common.services.sequence_repair_service import (
    check_all_sequences,
    fix_all_sequences,
    check_sequence_status,
    fix_sequence
)
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


def print_table_border(width=100):
    """Печатает границу таблицы."""
    print("=" * width)


def print_sequence_status(status):
    """Печатает статус последовательности."""
    table_name = f"{status['schema']}.{status['table']}"
    
    if status['status'] == 'no_sequence':
        print(f"  {table_name:<40} - Нет последовательности")
    elif status['status'] == 'ok':
        print(f"  {table_name:<40} - OK (текущее: {status['current_value']}, макс: {status['max_id']}, записей: {status['count']})")
    elif status['status'] == 'needs_fix':
        print(f"  {table_name:<40} - ТРЕБУЕТСЯ ИСПРАВЛЕНИЕ!")
        print(f"    Текущее значение: {status['current_value']}")
        print(f"    Максимальный ID:  {status['max_id']}")
        print(f"    Разница:          {status['difference']}")
        print(f"    Записей в таблице: {status['count']}")


def check_command(table=None):
    """Команда проверки последовательностей."""
    app = create_app()
    with app.app_context():
        if table:
            # Проверяем конкретную таблицу (сначала в generation, потом в refdata)
            print(f"\nПроверка последовательности для таблицы '{table}'...")
            print_table_border()
            
            schema = SCHEMA_GENERATION
            try:
                status = check_sequence_status(schema, table, "id")
                print_sequence_status(status)
            except Exception as e:
                # Если не нашли в generation, пробуем refdata
                schema = SCHEMA_REFDATA
                try:
                    status = check_sequence_status(schema, table, "id")
                    print_sequence_status(status)
                except Exception as e2:
                    print(f"  [ERROR] Ошибка при проверке {table}: {e2}")
        else:
            # Проверяем все последовательности
            print("\nПроверка всех последовательностей...")
            print_table_border()
            
            try:
                results = check_all_sequences()
                
                needs_fix = [r for r in results if r['status'] == 'needs_fix']
                ok = [r for r in results if r['status'] == 'ok']
                
                if needs_fix:
                    print("\n[!] ПОСЛЕДОВАТЕЛЬНОСТИ, ТРЕБУЮЩИЕ ИСПРАВЛЕНИЯ:")
                    for status in needs_fix:
                        print_sequence_status(status)
                
                if ok:
                    print(f"\n[OK] Последовательности в порядке: {len(ok)}")
                    if len(ok) <= 10:  # Показываем только если их немного
                        for status in ok:
                            print_sequence_status(status)
                
                print_table_border()
                print(f"\nИТОГО:")
                print(f"  Всего проверено: {len(results)}")
                print(f"  В порядке: {len(ok)}")
                print(f"  Требуется исправление: {len(needs_fix)}")
                
            except Exception as e:
                print(f"[ERROR] Ошибка при проверке: {e}")
                return 1
    
    return 0


def fix_command(table=None):
    """Команда исправления последовательностей."""
    app = create_app()
    with app.app_context():
        if table:
            # Исправляем конкретную таблицу
            print(f"\nИсправление последовательности для таблицы '{table}'...")
            print_table_border()
            
            schema = SCHEMA_GENERATION
            try:
                result = fix_sequence(schema, table, "id")
                if result['success']:
                    print(f"  [OK] {result['message']}")
                else:
                    print(f"  [ERROR] {result['message']}")
            except Exception as e:
                # Если не нашли в generation, пробуем refdata
                schema = SCHEMA_REFDATA
                try:
                    result = fix_sequence(schema, table, "id")
                    if result['success']:
                        print(f"  [OK] {result['message']}")
                    else:
                        print(f"  [ERROR] {result['message']}")
                except Exception as e2:
                    print(f"  [ERROR] Ошибка при исправлении {table}: {e2}")
                    return 1
        else:
            # Исправляем все последовательности
            print("\nИсправление всех последовательностей...")
            print_table_border()
            
            try:
                results = fix_all_sequences()
                
                print(f"\n[OK] Обработано таблиц: {results['total']}")
                print(f"  Исправлено: {results['fixed']}")
                print(f"  Уже в порядке: {results['ok']}")
                print(f"  Ошибок: {results['errors']}")
                
                if results['fixed'] > 0:
                    print("\nДетали исправлений:")
                    for detail in results['details']:
                        if detail.get('success') and detail.get('status_before', {}).get('status') == 'needs_fix':
                            print(f"  - {detail['message']}")
                
                if results['errors'] > 0:
                    print("\nОшибки:")
                    for detail in results['details']:
                        if not detail.get('success'):
                            print(f"  - {detail['message']}")
                
            except Exception as e:
                print(f"[ERROR] Ошибка при исправлении: {e}")
                return 1
    
    return 0


def main():
    """Главная функция CLI."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1].lower()
    table = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "check":
        return check_command(table)
    elif command == "fix":
        return fix_command(table)
    else:
        print(f"[ERROR] Неизвестная команда: {command}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main())

