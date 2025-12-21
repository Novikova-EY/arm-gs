"""
Точка входа для запуска приложения Flask.

ВАЖНО: Этот файл предназначен ТОЛЬКО для разработки!
Для production используйте gunicorn/waitress через start_production.sh/.bat

Переменные окружения:
- FLASK_ENV=development - режим разработки (по умолчанию)
- FLASK_ENV=production - production режим
"""
import os
from app import create_app
from flask_compress import Compress

# Устанавливаем окружение, если не задано
if not os.getenv('FLASK_ENV'):
    os.environ['FLASK_ENV'] = 'development'

# Создаем приложение (для gunicorn и прямого запуска)
app = create_app()
Compress(app)

# Экспортируем app для gunicorn
# Gunicorn будет использовать: gunicorn --config gunicorn_config.py "run:app"

if __name__ == "__main__":
    # В production режиме debug автоматически выключен
    # В development режиме можно включить через FLASK_ENV=development
    debug_mode = app.config.get('DEBUG', False)
    
    if debug_mode:
        print("=" * 60)
        print("ВНИМАНИЕ: Приложение запущено в режиме DEBUG!")
        print("=" * 60)
    
    app.run(
        debug=debug_mode,
        threaded=True,
        host=os.getenv('FLASK_RUN_HOST', '127.0.0.1'),
        port=int(os.getenv('FLASK_RUN_PORT', 5000))
    )