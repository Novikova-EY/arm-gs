"""Сервис мониторинга производительности для отладки узких мест."""

import time
import functools
from typing import Callable, Any
from flask import current_app


class PerformanceMonitor:
    """Класс для мониторинга производительности функций и запросов."""
    
    @staticmethod
    def time_function(func: Callable) -> Callable:
        """Декоратор для измерения времени выполнения функции."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            
            execution_time = end_time - start_time
            if execution_time > 0.1:  # Логируем только медленные функции (>100ms)
                current_app.logger.warning(
                    f"Медленная функция {func.__name__}: {execution_time:.3f} сек"
                )
            
            return result
        return wrapper
    
    @staticmethod
    def log_db_query_time(query_name: str, execution_time: float):
        """Логирование времени выполнения запроса к БД."""
        if execution_time > 0.05:  # Логируем запросы >50ms
            current_app.logger.warning(
                f"Медленный запрос {query_name}: {execution_time:.3f} сек"
            )
    
    @staticmethod
    def measure_template_render(template_name: str):
        """Контекстный менеджер для измерения времени рендеринга шаблона."""
        class TemplateTimer:
            def __init__(self, name):
                self.name = name
                self.start_time = None
            
            def __enter__(self):
                self.start_time = time.time()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.start_time:
                    execution_time = time.time() - self.start_time
                    if execution_time > 0.2:  # Логируем медленные шаблоны >200ms
                        current_app.logger.warning(
                            f"Медленный рендеринг шаблона {self.name}: {execution_time:.3f} сек"
                        )
        
        return TemplateTimer(template_name)


# Глобальный экземпляр для использования в приложении
performance_monitor = PerformanceMonitor()
