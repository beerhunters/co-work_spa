from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, List
import os
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import json
import aiofiles
import logging
import glob
from pydantic import BaseModel

from utils.logger import get_logger, setup_application_logging
from config import LOGS_DIR, LOG_LEVEL, LOG_FORMAT, LOG_TO_FILE, ENVIRONMENT
from models.models import Admin, Permission, AdminRole
from dependencies import verify_token, CachedAdmin
from schemas.logging_schemas import (
    LoggingConfig, LoggingConfigUpdate, LogEntry, LogFileInfo,
    TelegramNotificationConfig, LogStatistics
)

router = APIRouter(prefix="/logging", tags=["logging"])
logger = get_logger(__name__)





@router.get("/config", response_model=LoggingConfig)
async def get_logging_config(current_admin: CachedAdmin = Depends(verify_token)):
    """Получить текущую конфигурацию логирования"""
    if not current_admin.has_permission(Permission.MANAGE_LOGGING):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        # Получаем текущие настройки из переменных окружения (актуальные)
        config = LoggingConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_format=os.getenv("LOG_FORMAT", "detailed"),
            log_to_file=os.getenv("LOG_TO_FILE", "true").lower() == "true",
            environment=ENVIRONMENT,
            logs_directory=str(LOGS_DIR),
            telegram_notifications=await _get_telegram_config(),
            log_retention_days=int(os.getenv("LOG_RETENTION_DAYS", "30")),
            max_log_file_size_mb=int(os.getenv("MAX_LOG_FILE_SIZE_MB", "10"))
        )
        
        logger.info(f"Конфигурация логирования запрошена администратором {current_admin.login}")
        return config
        
    except Exception as e:
        logger.error(f"Ошибка получения конфигурации логирования: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения конфигурации")


@router.put("/config", response_model=LoggingConfig)
async def update_logging_config(
    config: LoggingConfigUpdate,
    current_admin: CachedAdmin = Depends(verify_token)
):
    """Обновить конфигурацию логирования"""
    if not current_admin.has_permission(Permission.MANAGE_LOGGING):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        # Обновляем переменные окружения
        if config.log_level:
            os.environ["LOG_LEVEL"] = config.log_level.upper()
            
        if config.log_format:
            os.environ["LOG_FORMAT"] = config.log_format.lower()
            
        if config.log_to_file is not None:
            os.environ["LOG_TO_FILE"] = "true" if config.log_to_file else "false"
            
        if config.log_retention_days:
            os.environ["LOG_RETENTION_DAYS"] = str(config.log_retention_days)
            
        if config.max_log_file_size_mb:
            os.environ["MAX_LOG_FILE_SIZE_MB"] = str(config.max_log_file_size_mb)
        
        # Сохраняем конфигурацию в файл для перезапуска
        await _save_config_to_file(config)
        
        # Применяем изменения к текущим логгерам
        if config.log_level:
            await _update_loggers_level(config.log_level)
        
        # Обновляем Telegram уведомления
        if config.telegram_notifications:
            await _update_telegram_config(config.telegram_notifications)
        
        logger.info(f"Конфигурация логирования обновлена администратором {current_admin.login}")
        
        # Возвращаем обновленную конфигурацию
        return await get_logging_config(current_admin)
        
    except Exception as e:
        logger.error(f"Ошибка обновления конфигурации логирования: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления конфигурации")


@router.get("/files", response_model=List[LogFileInfo])
async def get_log_files(current_admin: CachedAdmin = Depends(verify_token)):
    """Получить список файлов логов"""
    if not current_admin.has_permission(Permission.VIEW_LOGS):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        files = []
        
        # Ищем все файлы логов в директории
        log_patterns = [
            str(LOGS_DIR / "*.log"),
            str(LOGS_DIR / "app.log.*"),
        ]
        
        for pattern in log_patterns:
            for filepath in glob.glob(pattern):
                file_path = Path(filepath)
                if file_path.exists():
                    stat = file_path.stat()
                    files.append(LogFileInfo(
                        name=file_path.name,
                        path=str(file_path),
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime),
                        is_current=file_path.name == "app.log"
                    ))
        
        # Сортируем по дате изменения
        files.sort(key=lambda x: x.modified, reverse=True)
        
        logger.debug(f"Найдено {len(files)} файлов логов")
        return files
        
    except Exception as e:
        logger.error(f"Ошибка получения списка файлов логов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения списка файлов")


@router.get("/files/{filename}/download")
async def download_log_file(
    filename: str,
    current_admin: CachedAdmin = Depends(verify_token)
):
    """Скачать файл логов"""
    if not current_admin.has_permission(Permission.VIEW_LOGS):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        file_path = LOGS_DIR / filename
        
        # Проверяем безопасность пути
        if not str(file_path).startswith(str(LOGS_DIR.resolve())):
            raise HTTPException(status_code=400, detail="Недопустимое имя файла")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        logger.info(f"Скачивание файла логов {filename} администратором {current_admin.login}")
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type='text/plain'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка скачивания файла логов {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка скачивания файла")


@router.get("/files/{filename}/content")
async def get_log_file_content(
    filename: str,
    lines: int = Query(default=100, ge=1, le=10000, description="Количество последних строк"),
    search: Optional[str] = Query(default=None, description="Поиск по содержимому"),
    level: Optional[str] = Query(default=None, description="Фильтр по уровню"),
    current_admin: CachedAdmin = Depends(verify_token)
):
    """Получить содержимое файла логов"""
    if not current_admin.has_permission(Permission.VIEW_LOGS):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        file_path = LOGS_DIR / filename
        
        if not str(file_path).startswith(str(LOGS_DIR.resolve())):
            raise HTTPException(status_code=400, detail="Недопустимое имя файла")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Файл не найден")
        
        # Читаем файл
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            content_lines = await f.readlines()
        
        # Берем последние N строк
        content_lines = content_lines[-lines:]
        
        # Применяем фильтры
        filtered_lines = []
        for line in content_lines:
            line = line.strip()
            if not line:
                continue
                
            # Фильтр по поиску
            if search and search.lower() not in line.lower():
                continue
                
            # Фильтр по уровню
            if level and f"[{level.upper()}]" not in line:
                continue
                
            filtered_lines.append(line)
        
        logger.debug(f"Запрошено содержимое файла {filename}, строк: {len(filtered_lines)}")
        
        return {
            "filename": filename,
            "lines_count": len(filtered_lines),
            "content": filtered_lines
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка чтения файла логов {filename}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка чтения файла")


@router.get("/live")
async def get_live_logs(
    level: Optional[str] = Query(default=None, description="Фильтр по уровню"),
    search: Optional[str] = Query(default=None, description="Поиск по содержимому"),
    current_admin: CachedAdmin = Depends(verify_token)
):
    """Получить live-поток логов"""
    if not current_admin.has_permission(Permission.VIEW_LOGS):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    async def generate_logs():
        try:
            current_log_file = LOGS_DIR / "app.log"
            if not current_log_file.exists():
                yield "data: {\"error\": \"Файл логов не найден\"}\n\n"
                return
            
            # Читаем последние строки файла
            last_position = 0
            
            while True:
                try:
                    if current_log_file.exists():
                        current_size = current_log_file.stat().st_size
                        
                        if current_size > last_position:
                            async with aiofiles.open(current_log_file, 'r', encoding='utf-8') as f:
                                await f.seek(last_position)
                                new_content = await f.read()
                                last_position = current_size
                                
                                for line in new_content.split('\n'):
                                    line = line.strip()
                                    if not line:
                                        continue
                                    
                                    # Применяем фильтры
                                    if level and f"[{level.upper()}]" not in line:
                                        continue
                                        
                                    if search and search.lower() not in line.lower():
                                        continue
                                    
                                    # Отправляем строку как SSE
                                    yield f"data: {json.dumps({'line': line, 'timestamp': datetime.now().isoformat()})}\n\n"
                    
                    await asyncio.sleep(1)  # Проверяем каждую секунду
                    
                except Exception as e:
                    logger.error(f"Ошибка в live-потоке логов: {e}")
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    break
                    
        except Exception as e:
            logger.error(f"Критическая ошибка live-потока логов: {e}")
            yield f"data: {json.dumps({'error': 'Критическая ошибка'})}\n\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*"
        }
    )


@router.get("/statistics", response_model=LogStatistics)
async def get_log_statistics(
    hours: int = Query(default=24, ge=1, le=168, description="Период в часах"),
    current_admin: CachedAdmin = Depends(verify_token)
):
    """Получить статистику логов"""
    if not current_admin.has_permission(Permission.VIEW_LOGS):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        current_log_file = LOGS_DIR / "app.log"
        if not current_log_file.exists():
            return LogStatistics(
                total_entries=0,
                levels_count={},
                errors_count=0,
                warnings_count=0,
                period_hours=hours
            )
        
        # Читаем файл и анализируем
        levels_count = {}
        total_entries = 0
        errors_count = 0
        warnings_count = 0
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        async with aiofiles.open(current_log_file, 'r', encoding='utf-8') as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Простой парсинг даты из строки лога
                try:
                    # Ожидаем формат [2024-01-01 12:00:00] [LEVEL] ...
                    if line.startswith('['):
                        date_end = line.find(']')
                        if date_end > 0:
                            date_str = line[1:date_end]
                            try:
                                log_time = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                                if log_time < cutoff_time:
                                    continue
                            except ValueError:
                                pass  # Если не удалось парсить дату, включаем запись
                    
                    total_entries += 1
                    
                    # Определяем уровень
                    for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                        if f'[{level}]' in line:
                            levels_count[level] = levels_count.get(level, 0) + 1
                            
                            if level in ['ERROR', 'CRITICAL']:
                                errors_count += 1
                            elif level == 'WARNING':
                                warnings_count += 1
                            break
                            
                except Exception:
                    continue
        
        return LogStatistics(
            total_entries=total_entries,
            levels_count=levels_count,
            errors_count=errors_count,
            warnings_count=warnings_count,
            period_hours=hours
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики логов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения статистики")


@router.post("/test-notification")
async def test_telegram_notification(current_admin: CachedAdmin = Depends(verify_token)):
    """Отправить тестовое уведомление в Telegram"""
    if not current_admin.has_permission(Permission.MANAGE_LOGGING):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        from utils.telegram_logger import send_test_notification, _is_telegram_logging_enabled
        
        # Проверяем конфигурацию Telegram
        if not _is_telegram_logging_enabled():
            logger.warning("Telegram уведомления отключены в конфигурации")
            return {
                "success": False, 
                "message": "Telegram уведомления отключены. Проверьте настройки TELEGRAM_LOGGING_ENABLED, FOR_LOGS и BOT_TOKEN"
            }
        
        # Получаем минимальный уровень из настроек Telegram уведомлений для тестового сообщения
        telegram_min_level = os.getenv("TELEGRAM_LOG_MIN_LEVEL", "ERROR")
        result = await send_test_notification(telegram_min_level, current_admin.login)
        
        if result:
            logger.info(f"Тестовое уведомление отправлено администратором {current_admin.login}")
            return {"success": True, "message": "Тестовое уведомление отправлено"}
        else:
            logger.error("Не удалось отправить тестовое уведомление")
            return {"success": False, "message": "Не удалось отправить уведомление. Проверьте настройки Telegram"}
            
    except Exception as e:
        logger.error(f"Ошибка отправки тестового уведомления: {e}")
        return {"success": False, "message": f"Ошибка: {str(e)}"}


@router.post("/clear-logs")
async def clear_logs(current_admin: CachedAdmin = Depends(verify_token)):
    """Очистить все файлы логов"""
    if not current_admin.has_permission(Permission.MANAGE_LOGGING):
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    try:
        deleted_files = []
        errors = []
        
        # Ищем все файлы логов
        log_patterns = [
            str(LOGS_DIR / "*.log"),
            str(LOGS_DIR / "app.log.*"),
        ]
        
        for pattern in log_patterns:
            for filepath in glob.glob(pattern):
                try:
                    file_path = Path(filepath)
                    if file_path.exists():
                        # Для текущего лога просто очищаем его содержимое
                        if file_path.name == "app.log":
                            file_path.write_text("", encoding="utf-8")
                            deleted_files.append(f"{file_path.name} (очищен)")
                        else:
                            # Остальные файлы удаляем
                            file_path.unlink()
                            deleted_files.append(f"{file_path.name} (удален)")
                except Exception as e:
                    errors.append(f"{Path(filepath).name}: {str(e)}")
        
        logger.info(f"Логи очищены администратором {current_admin.login}, файлов обработано: {len(deleted_files)}")
        
        result = {
            "success": len(deleted_files) > 0,
            "files_processed": len(deleted_files),
            "files": deleted_files
        }
        
        if errors:
            result["errors"] = errors
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка очистки логов: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки логов")


# Вспомогательные функции

async def _get_telegram_config() -> TelegramNotificationConfig:
    """Получить конфигурацию Telegram уведомлений"""
    return TelegramNotificationConfig(
        enabled=bool(os.getenv("TELEGRAM_LOGGING_ENABLED", "false").lower() == "true"),
        chat_id=os.getenv("FOR_LOGS"),
        min_level=os.getenv("TELEGRAM_LOG_MIN_LEVEL", "ERROR"),
        rate_limit_minutes=int(os.getenv("TELEGRAM_LOG_RATE_LIMIT", "5"))
    )


async def _update_telegram_config(config: TelegramNotificationConfig):
    """Обновить конфигурацию Telegram уведомлений"""
    os.environ["TELEGRAM_LOGGING_ENABLED"] = "true" if config.enabled else "false"
    if config.chat_id:
        os.environ["FOR_LOGS"] = config.chat_id
    os.environ["TELEGRAM_LOG_MIN_LEVEL"] = config.min_level
    os.environ["TELEGRAM_LOG_RATE_LIMIT"] = str(config.rate_limit_minutes)


async def _save_config_to_file(config: LoggingConfigUpdate):
    """Сохранить конфигурацию в файл для применения после перезапуска"""
    config_file = Path("logging_config.json")
    
    config_data = {}
    if config.log_level:
        config_data["LOG_LEVEL"] = config.log_level.upper()
    if config.log_format:
        config_data["LOG_FORMAT"] = config.log_format.lower()
    if config.log_to_file is not None:
        config_data["LOG_TO_FILE"] = "true" if config.log_to_file else "false"
    if config.log_retention_days:
        config_data["LOG_RETENTION_DAYS"] = str(config.log_retention_days)
    if config.max_log_file_size_mb:
        config_data["MAX_LOG_FILE_SIZE_MB"] = str(config.max_log_file_size_mb)
    
    if config.telegram_notifications:
        config_data["TELEGRAM_LOGGING_ENABLED"] = "true" if config.telegram_notifications.enabled else "false"
        if config.telegram_notifications.chat_id:
            config_data["FOR_LOGS"] = config.telegram_notifications.chat_id
        config_data["TELEGRAM_LOG_MIN_LEVEL"] = config.telegram_notifications.min_level
        config_data["TELEGRAM_LOG_RATE_LIMIT"] = str(config.telegram_notifications.rate_limit_minutes)
    
    async with aiofiles.open(config_file, 'w') as f:
        await f.write(json.dumps(config_data, indent=2))


async def _update_loggers_level(new_level: str):
    """Обновить уровень всех активных логгеров"""
    try:
        # Получаем числовое значение уровня
        numeric_level = getattr(logging, new_level.upper())
        
        # Обновляем все логгеры
        for name in logging.Logger.manager.loggerDict:
            logger_obj = logging.getLogger(name)
            logger_obj.setLevel(numeric_level)
            
            # Обновляем обработчики
            for handler in logger_obj.handlers:
                handler.setLevel(numeric_level)
        
        # Обновляем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)
            
        logger.info(f"Уровень логирования изменен на {new_level} для всех логгеров")
        
    except Exception as e:
        logger.error(f"Ошибка обновления уровня логгеров: {e}")
        raise