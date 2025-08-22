"""
Юнит-тесты для системы логирования
"""
import pytest
import logging
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

from utils.logger import (
    ProductionLogger,
    get_production_logger,
    get_logger,
    set_log_level,
    log_startup_info
)


class TestProductionLogger:
    """Тесты production логгера"""
    
    def test_logger_creation(self):
        """Тест создания логгера"""
        logger = ProductionLogger("test_logger")
        assert logger.name == "test_logger"
        assert logger.logger.name == "test_logger"
    
    def test_development_log_level(self):
        """Тест уровня логирования в development"""
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "LOG_LEVEL": "DEBUG"}):
            logger = ProductionLogger("dev_test")
            assert logger.environment == "development"
            assert logger.log_level == "DEBUG"
            assert logger.effective_log_level == "DEBUG"
    
    def test_production_log_level_filtering(self):
        """Тест фильтрации уровней в production"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "LOG_LEVEL": "DEBUG"}):
            logger = ProductionLogger("prod_test")
            assert logger.environment == "production"
            assert logger.log_level == "DEBUG"
            assert logger.effective_log_level == "WARNING"  # DEBUG -> WARNING в production
    
    def test_production_log_level_warning(self):
        """Тест сохранения WARNING уровня в production"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "LOG_LEVEL": "WARNING"}):
            logger = ProductionLogger("prod_test")
            assert logger.effective_log_level == "WARNING"
    
    def test_production_log_level_error(self):
        """Тест сохранения ERROR уровня в production"""
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "LOG_LEVEL": "ERROR"}):
            logger = ProductionLogger("prod_test")
            assert logger.effective_log_level == "ERROR"
    
    @patch('utils.production_logging.LOGS_DIR')
    def test_file_logging_setup(self, mock_logs_dir):
        """Тест настройки файлового логирования"""
        mock_logs_dir.mkdir = MagicMock()
        
        with patch.dict(os.environ, {"LOG_TO_FILE": "true"}):
            logger = ProductionLogger("file_test")
            
            # Проверяем, что директория создается
            mock_logs_dir.mkdir.assert_called_once_with(exist_ok=True)
    
    def test_json_formatter_production(self):
        """Тест JSON форматтера в production"""
        with patch.dict(os.environ, {"LOG_FORMAT": "json", "ENVIRONMENT": "production"}):
            logger = ProductionLogger("json_test")
            formatter = logger._get_json_formatter()
            
            # Создаем тестовую запись лога
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=100,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            result = formatter.format(record)
            
            # Проверяем, что результат - валидный JSON
            import json
            parsed = json.loads(result)
            assert parsed["level"] == "INFO"
            assert parsed["message"] == "Test message"
            assert parsed["service"] == "coworking-api"
    
    def test_text_formatter_development(self):
        """Тест текстового форматтера в development"""
        with patch.dict(os.environ, {"LOG_FORMAT": "text", "ENVIRONMENT": "development"}):
            logger = ProductionLogger("text_test")
            formatter = logger._get_text_formatter()
            
            # Создаем тестовую запись лога
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=100,
                msg="Test message",
                args=(),
                exc_info=None
            )
            record.filename = "test.py"  # Добавляем атрибут filename
            
            result = formatter.format(record)
            
            # В development должен быть подробный формат с файлом и номером строки
            assert "test.py:100" in result
            assert "Test message" in result
    
    def test_text_formatter_production(self):
        """Тест текстового форматтера в production"""
        with patch.dict(os.environ, {"LOG_FORMAT": "text", "ENVIRONMENT": "production"}):
            logger = ProductionLogger("text_test")
            formatter = logger._get_text_formatter()
            
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="/path/to/test.py",
                lineno=100,
                msg="Test message",
                args=(),
                exc_info=None
            )
            
            result = formatter.format(record)
            
            # В production не должно быть файла и номера строки
            assert "test.py:100" not in result
            assert "Test message" in result


class TestLoggerUtils:
    """Тесты утилит логирования"""
    
    def test_get_production_logger_singleton(self):
        """Тест синглтон поведения get_production_logger"""
        logger1 = get_production_logger("singleton_test")
        logger2 = get_production_logger("singleton_test")
        
        # Должен вернуть тот же экземпляр
        assert logger1 is logger2
    
    def test_get_logger_convenience(self):
        """Тест convenience функции get_logger"""
        logger = get_logger("convenience_test")
        assert logger.name == "convenience_test"
        assert isinstance(logger, logging.Logger)
    
    @patch('utils.production_logging._loggers')
    def test_set_log_level(self, mock_loggers):
        """Тест изменения уровня логирования"""
        # Создаем мок логгеров
        mock_loggers.keys.return_value = ["test1", "test2"]
        mock_loggers.__delitem__ = MagicMock()
        
        with patch.dict(os.environ, {}):
            set_log_level("ERROR")
            
            # Проверяем, что переменная окружения обновлена
            assert os.environ.get("LOG_LEVEL") == "ERROR"
            
            # Проверяем, что логгеры удалены для пересоздания
            assert mock_loggers.__delitem__.call_count == 2
    
    def test_set_log_level_invalid(self):
        """Тест установки невалидного уровня логирования"""
        with pytest.raises(ValueError, match="Invalid log level"):
            set_log_level("INVALID_LEVEL")
    
    @patch('utils.production_logging.get_logger')
    @patch('utils.production_logging.ENVIRONMENT', "test")
    @patch('utils.production_logging.LOG_LEVEL', "DEBUG")
    @patch('utils.production_logging.LOG_FORMAT', "json")
    @patch('utils.production_logging.LOG_TO_FILE', True)
    def test_log_startup_info(self, mock_get_logger):
        """Тест логирования информации о запуске"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        log_startup_info()
        
        # Проверяем, что были вызваны нужные методы логирования
        assert mock_logger.info.call_count >= 5
        
        # Проверяем, что в логах есть информация о настройках
        calls = [call.args[0] for call in mock_logger.info.call_args_list]
        startup_info = " ".join(calls)
        
        assert "Coworking SPA starting up" in startup_info
        assert "Environment: test" in startup_info
        assert "Log Level: DEBUG" in startup_info


class TestProductionLoggerMixin:
    """Тесты миксина ProductionLoggerMixin"""
    
    def test_mixin_integration(self):
        """Тест интеграции миксина"""
        from utils.logger import ProductionLoggerMixin
        
        class TestClass(ProductionLoggerMixin):
            def __init__(self):
                super().__init__()
        
        test_obj = TestClass()
        
        # Проверяем, что логгер создан
        assert hasattr(test_obj, 'logger')
        assert isinstance(test_obj.logger, logging.Logger)
    
    def test_mixin_log_methods(self):
        """Тест методов логирования миксина"""
        from utils.logger import ProductionLoggerMixin
        
        class TestClass(ProductionLoggerMixin):
            def __init__(self):
                super().__init__()
        
        test_obj = TestClass()
        
        # Проверяем наличие методов логирования
        assert hasattr(test_obj, 'log_debug')
        assert hasattr(test_obj, 'log_info')
        assert hasattr(test_obj, 'log_warning')
        assert hasattr(test_obj, 'log_error')
        assert hasattr(test_obj, 'log_critical')
        
        # Проверяем, что методы работают без ошибок
        with patch.object(test_obj.logger, 'debug') as mock_debug:
            test_obj.log_debug("Test debug message", extra_field="value")
            mock_debug.assert_called_once_with("Test debug message", extra={'extra_field': 'value'})
    
    def test_mixin_error_with_exception(self):
        """Тест логирования ошибки с исключением"""
        from utils.logger import ProductionLoggerMixin
        
        class TestClass(ProductionLoggerMixin):
            def __init__(self):
                super().__init__()
        
        test_obj = TestClass()
        
        with patch.object(test_obj.logger, 'error') as mock_error:
            exception = ValueError("Test exception")
            test_obj.log_error("Error occurred", exception=exception, context="test")
            
            mock_error.assert_called_once_with(
                "Error occurred", 
                exc_info=exception, 
                extra={'context': 'test'}
            )