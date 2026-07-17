# -*- coding: utf-8 -*-
"""
Сервис автоматических бэкапов БД по расписанию.
"""

import os
import subprocess
from datetime import datetime
from flask import current_app
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class ScheduledBackupService:
    """Сервис для автоматического создания бэкапов по расписанию."""
    
    def __init__(self, app=None):
        self.scheduler = None
        self.app = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Инициализация сервиса с Flask приложением."""
        self.app = app
        
        # Проверяем, включены ли автоматические бэкапы
        if not app.config.get('ENABLE_SCHEDULED_BACKUPS', False):
            logger.info("Автоматические бэкапы отключены в конфигурации")
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.error(
                "APScheduler не установлен. Установите: pip install APScheduler==3.10.4"
            )
            return
        
        # Создаем scheduler
        self.scheduler = BackgroundScheduler()
        
        # Получаем расписание из конфигурации
        # По умолчанию: каждый день в 2:00 ночи
        cron_schedule = app.config.get('BACKUP_SCHEDULE', {
            'hour': 2,
            'minute': 0
        })
        
        # Добавляем задачу
        self.scheduler.add_job(
            func=lambda: self._run_backup_with_context(),
            trigger=CronTrigger(**cron_schedule),
            id='scheduled_database_backup',
            name='Автоматический бэкап БД',
            replace_existing=True
        )
        
        # Запускаем scheduler
        self.scheduler.start()
        logger.info(f"Автоматические бэкапы запущены по расписанию: {cron_schedule}")
    
    def _run_backup_with_context(self):
        """Запускает бэкап в контексте Flask приложения."""
        if not self.app:
            logger.error("Flask app не инициализировано")
            return
        
        with self.app.app_context():
            self._run_backup()
    
    def _run_backup(self):
        """Выполняет создание бэкапа БД."""
        try:
            logger.info("Начало автоматического бэкапа БД")
            
            # Путь к директории бэкапов (на сервере — /var/backups/generation-app/auto)
            backup_dir = self.app.config.get(
                'AUTO_BACKUP_DIR',
                os.path.join(self.app.config.get('BACKUP_BASE_DIR', 'backups'), 'auto'),
            )
            os.makedirs(backup_dir, exist_ok=True)
            
            # Формирование имени файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f"auto_backup_{timestamp}.dump")
            
            # Получение параметров подключения к БД
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_user = os.getenv("DB_USER")
            db_name = os.getenv("DB_NAME")
            db_pass = os.getenv("DB_PASS")
            
            if not all([db_user, db_name]):
                raise ValueError("Не указаны параметры подключения к БД")
            
            # Поиск pg_dump
            pg_dump_path = self._find_pg_binary("pg_dump")
            
            # Команда pg_dump
            cmd = [
                pg_dump_path,
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                "-F", "c",  # custom format (сжатый)
                "-b",  # include blobs
                "-f", backup_file,
                db_name
            ]
            
            # Подготовка окружения с паролем
            env = os.environ.copy()
            if db_pass:
                env["PGPASSWORD"] = db_pass
            
            # Выполнение pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # таймаут 1 час
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                raise Exception(f"pg_dump завершился с ошибкой: {error_msg}")
            
            # Проверка, что файл создан
            if not os.path.exists(backup_file):
                raise Exception(f"Файл бэкапа не найден: {backup_file}")
            
            # Получение размера файла
            file_size = os.path.getsize(backup_file)
            size_mb = file_size / (1024 * 1024)
            
            logger.info(
                f"Автоматический бэкап успешно создан: {backup_file}, "
                f"Размер: {size_mb:.2f} МБ"
            )
            
            # Очистка старых бэкапов
            self._cleanup_old_backups(backup_dir)
            
        except subprocess.TimeoutExpired:
            logger.error("Превышено время ожидания создания бэкапа (>1 час)")
        except Exception as e:
            logger.error(f"Ошибка создания автоматического бэкапа: {e}")
    
    def _cleanup_old_backups(self, backup_dir):
        """Удаляет старые бэкапы, оставляя только последние N."""
        try:
            # Количество бэкапов для хранения (из конфигурации)
            keep_backups = self.app.config.get('KEEP_AUTO_BACKUPS', 7)
            
            # Получаем список всех бэкапов
            backups = []
            for filename in os.listdir(backup_dir):
                if filename.startswith('auto_backup_') and filename.endswith('.dump'):
                    filepath = os.path.join(backup_dir, filename)
                    backups.append((filepath, os.path.getmtime(filepath)))
            
            # Сортируем по времени модификации (новые первые)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Удаляем старые бэкапы
            deleted_count = 0
            for filepath, _ in backups[keep_backups:]:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.info(f"Удален старый бэкап: {filepath}")
                except Exception as e:
                    logger.error(f"Ошибка удаления старого бэкапа {filepath}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Очистка завершена. Удалено старых бэкапов: {deleted_count}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых бэкапов: {e}")
    
    def _find_pg_binary(self, binary_name):
        """
        Ищет исполняемый файл PostgreSQL (pg_dump) в стандартных местах.
        """
        import shutil
        import glob
        import platform
        
        # Сначала проверяем PATH
        if shutil.which(binary_name):
            return binary_name
        
        # Для Windows ищем в стандартных местах установки PostgreSQL
        if platform.system() == 'Windows':
            search_paths = [
                r"C:\Program Files\PostgreSQL\*\bin",
                r"C:\Program Files (x86)\PostgreSQL\*\bin",
                r"C:\PostgreSQL\*\bin",
            ]
            
            for pattern in search_paths:
                for path in glob.glob(pattern):
                    binary_path = os.path.join(path, f"{binary_name}.exe")
                    if os.path.exists(binary_path):
                        return binary_path
        
        # Для Linux/Mac ищем в стандартных местах
        else:
            search_paths = [
                "/usr/bin",
                "/usr/local/bin",
                "/opt/postgresql/bin",
                "/usr/lib/postgresql/*/bin",
            ]
            
            for pattern in search_paths:
                for path in glob.glob(pattern):
                    binary_path = os.path.join(path, binary_name)
                    if os.path.exists(binary_path):
                        return binary_path
        
        # Если не найдено, возвращаем просто имя
        return binary_name
    
    def shutdown(self):
        """Останавливает scheduler."""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("Scheduler автоматических бэкапов остановлен")
    
    def run_backup_now(self):
        """Запускает бэкап немедленно (для тестирования)."""
        self._run_backup_with_context()


# Глобальный экземпляр сервиса
scheduled_backup_service = ScheduledBackupService()

