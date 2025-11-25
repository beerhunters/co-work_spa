"""
Модуль для автоматического резервного копирования базы данных
"""

import os
import shutil
import sqlite3
import gzip
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import time
import asyncio

from utils.logger import get_logger

logger = get_logger(__name__)

# Импортируем DATA_DIR из config для совместимости с CI и Docker
try:
    from config import DATA_DIR
except ImportError:
    # Fallback для тестов если config не доступен
    DATA_DIR = Path("./data")


class BackupConfig:
    """Конфигурация системы бэкапов"""

    def __init__(self):
        # Основные настройки (читаем динамически при создании экземпляра)
        self.BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
        self.BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "6"))  # Каждые 6 часов

        # Используем DATA_DIR из config вместо hardcoded /app/data
        default_backup_dir = DATA_DIR / "backups"
        self.BACKUP_DIR = Path(os.getenv("BACKUP_DIR", str(default_backup_dir)))

        # Ротация бэкапов
        self.KEEP_HOURLY_BACKUPS = int(os.getenv("KEEP_HOURLY_BACKUPS", "48"))  # 2 дня почасовых
        self.KEEP_DAILY_BACKUPS = int(os.getenv("KEEP_DAILY_BACKUPS", "30"))  # 30 дней ежедневных
        self.KEEP_WEEKLY_BACKUPS = int(os.getenv("KEEP_WEEKLY_BACKUPS", "12"))  # 12 недель еженедельных
        self.KEEP_MONTHLY_BACKUPS = int(os.getenv("KEEP_MONTHLY_BACKUPS", "6"))  # 6 месяцев ежемесячных

        # Сжатие и безопасность
        self.COMPRESS_BACKUPS = os.getenv("COMPRESS_BACKUPS", "true").lower() == "true"
        self.BACKUP_ENCRYPTION = os.getenv("BACKUP_ENCRYPTION", "false").lower() == "true"
        self.MAX_BACKUP_SIZE_MB = int(os.getenv("MAX_BACKUP_SIZE_MB", "1000"))  # 1GB лимит

        # База данных - используем DATA_DIR
        default_db_path = DATA_DIR / "coworking.db"
        self.DB_PATH = Path(os.getenv("DB_PATH", str(default_db_path)))


class BackupMetadata:
    """Класс для работы с метаданными бэкапов"""

    def __init__(self, backup_dir: Path):
        self.backup_dir = backup_dir
        self.metadata_file = backup_dir / "backup_metadata.json"
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Загрузка метаданных бэкапов"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading backup metadata: {e}")

        return {
            "backups": [],
            "last_cleanup": None,
            "total_backups_created": 0,
            "failed_backups": 0,
        }

    def _save_metadata(self):
        """Сохранение метаданных"""
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"Error saving backup metadata: {e}")

    def add_backup(self, backup_info: Dict[str, Any]):
        """Добавление информации о новом бэкапе"""
        self._metadata["backups"].append(backup_info)
        self._metadata["total_backups_created"] += 1
        self._save_metadata()

    def remove_backup(self, backup_name: str):
        """Удаление бэкапа из метаданных"""
        self._metadata["backups"] = [
            b for b in self._metadata["backups"] if b.get("filename") != backup_name
        ]
        self._save_metadata()

    def record_failed_backup(self, error_message: str):
        """Запись неудачного бэкапа"""
        self._metadata["failed_backups"] += 1
        self._metadata["last_error"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": error_message,
        }
        self._save_metadata()

    def get_backups(self) -> List[Dict[str, Any]]:
        """Получение списка всех бэкапов"""
        return self._metadata.get("backups", [])

    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики бэкапов"""
        backups = self._metadata.get("backups", [])
        if not backups:
            return {
                "total_backups": 0,
                "total_created": self._metadata.get("total_backups_created", 0),
                "failed_backups": self._metadata.get("failed_backups", 0),
                "last_backup": None,
                "total_size_mb": 0,
            }

        last_backup = max(backups, key=lambda x: x.get("created_at", ""))
        total_size = sum(b.get("size_bytes", 0) for b in backups)

        return {
            "total_backups": len(backups),
            "total_created": self._metadata.get("total_backups_created", 0),
            "failed_backups": self._metadata.get("failed_backups", 0),
            "last_backup": last_backup,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }


class DatabaseBackupManager:
    """Менеджер резервного копирования базы данных"""

    def __init__(self):
        self.config = BackupConfig()
        self.backup_dir = self.config.BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.metadata = BackupMetadata(self.backup_dir)
        self._backup_lock = threading.Lock()
        self._scheduler_running = False
        self._scheduler_task = None

    def create_backup(self, backup_type: str = "scheduled") -> Optional[Dict[str, Any]]:
        """
        Создание бэкапа базы данных

        Args:
            backup_type: Тип бэкапа (scheduled, manual, pre_update)

        Returns:
            Информация о созданном бэкапе или None при ошибке
        """
        with self._backup_lock:
            try:
                # Проверяем существование БД
                if not self.config.DB_PATH.exists():
                    error_msg = f"Database file not found: {self.config.DB_PATH}"
                    logger.error(error_msg)
                    self.metadata.record_failed_backup(error_msg)
                    return None

                # Генерируем имя файла бэкапа
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"coworking_backup_{timestamp}_{backup_type}.db"

                if self.config.COMPRESS_BACKUPS:
                    backup_filename += ".gz"

                backup_path = self.backup_dir / backup_filename

                logger.info(f"Starting database backup: {backup_filename}")

                # Создаем бэкап
                success = self._perform_backup(self.config.DB_PATH, backup_path)

                if not success:
                    error_msg = "Backup creation failed"
                    self.metadata.record_failed_backup(error_msg)
                    return None

                # Получаем информацию о файле
                file_size = backup_path.stat().st_size

                # Проверяем размер
                if file_size > self.config.MAX_BACKUP_SIZE_MB * 1024 * 1024:
                    logger.warning(f"Backup size {file_size} exceeds limit")

                backup_info = {
                    "filename": backup_filename,
                    "type": backup_type,
                    "created_at": datetime.utcnow().isoformat(),
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "compressed": self.config.COMPRESS_BACKUPS,
                    "db_path": str(self.config.DB_PATH),
                }

                # Добавляем в метаданные
                self.metadata.add_backup(backup_info)

                logger.info(
                    f"Database backup created: {backup_filename}",
                    extra={
                        "event_type": "backup",
                        "backup_type": backup_type,
                        "size_mb": backup_info["size_mb"],
                    },
                )

                logger.info(
                    f"Backup created successfully: {backup_filename} ({backup_info['size_mb']} MB)"
                )

                return backup_info

            except Exception as e:
                error_msg = f"Backup creation error: {e}"
                logger.error(error_msg, exc_info=True)
                self.metadata.record_failed_backup(error_msg)
                return None

    def _perform_backup(self, source_db: Path, backup_path: Path) -> bool:
        """
        Выполнение физического бэкапа БД

        Args:
            source_db: Путь к исходной БД
            backup_path: Путь к файлу бэкапа

        Returns:
            True если успешно, False при ошибке
        """
        try:
            # Подключаемся к исходной БД
            source_conn = sqlite3.connect(str(source_db))

            if self.config.COMPRESS_BACKUPS:
                # Создаем сжатый бэкап
                with gzip.open(backup_path, "wb") as gz_file:
                    # Создаем временный бэкап в памяти
                    temp_backup = sqlite3.connect(":memory:")
                    source_conn.backup(temp_backup)

                    # Экспортируем в SQL и сжимаем
                    sql_dump = ""
                    for line in temp_backup.iterdump():
                        sql_dump += line + "\n"

                    gz_file.write(sql_dump.encode("utf-8"))
                    temp_backup.close()
            else:
                # Создаем несжатый бэкап
                backup_conn = sqlite3.connect(str(backup_path))
                source_conn.backup(backup_conn)
                backup_conn.close()

            source_conn.close()
            return True

        except Exception as e:
            logger.error(f"Error performing backup: {e}")
            return False

    def restore_backup(
        self, backup_filename: str, target_db: Optional[Path] = None
    ) -> bool:
        """
        Восстановление БД из бэкапа

        Args:
            backup_filename: Имя файла бэкапа
            target_db: Целевая БД (по умолчанию исходная)

        Returns:
            True если успешно
        """
        try:
            backup_path = self.backup_dir / backup_filename

            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_filename}")
                return False

            if target_db is None:
                target_db = self.config.DB_PATH

            logger.info(f"Starting database restore from: {backup_filename}")

            # Создаем резервную копию текущей БД
            if target_db.exists():
                backup_current = target_db.with_suffix(".db.backup")
                shutil.copy2(target_db, backup_current)
                logger.info(f"Current database backed up to: {backup_current}")

            # Восстанавливаем из бэкапа
            success = self._perform_restore(backup_path, target_db)

            if success:
                logger.info(
                    f"Backup restored successfully to: {target_db}",
                    extra={"event_type": "backup", "backup_type": "restore"},
                )
                return True
            else:
                # Если восстановление не удалось, возвращаем исходную БД
                if target_db.with_suffix(".db.backup").exists():
                    shutil.move(target_db.with_suffix(".db.backup"), target_db)
                    logger.info("Original database restored after failed restore")
                return False

        except Exception as e:
            logger.error(f"Error restoring backup: {e}", exc_info=True)
            return False

    def _perform_restore(self, backup_path: Path, target_db: Path) -> bool:
        """Выполнение физического восстановления"""
        try:
            if str(backup_path).endswith(".gz"):
                # Восстанавливаем из сжатого бэкапа
                with gzip.open(backup_path, "rb") as gz_file:
                    sql_content = gz_file.read().decode("utf-8")

                # Удаляем старую БД
                if target_db.exists():
                    target_db.unlink()

                # Создаем новую БД из SQL
                conn = sqlite3.connect(str(target_db))
                conn.executescript(sql_content)
                conn.close()
            else:
                # Простое копирование файла
                shutil.copy2(backup_path, target_db)

            return True

        except Exception as e:
            logger.error(f"Error performing restore: {e}")
            return False

    def cleanup_old_backups(self) -> Dict[str, int]:
        """
        Очистка старых бэкапов - удаляет все кроме самого последнего

        Returns:
            Статистика очистки
        """
        logger.info(
            "Starting backup cleanup - removing all backups except the latest one"
        )

        backups = self.metadata.get_backups()
        deleted_count = 0
        deleted_size = 0

        if len(backups) <= 1:
            logger.info("No backups to clean up (0 or 1 backup found)")
            return {"deleted_count": 0, "deleted_size_mb": 0.0}

        # Сортируем бэкапы по дате создания (новые сначала)
        backups.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Оставляем только самый последний бэкап (первый в отсортированном списке)
        latest_backup = backups[0]
        backups_to_delete = backups[1:]  # Все остальные

        logger.info(
            f"Keeping latest backup: {latest_backup['filename']} ({latest_backup['created_at']})"
        )
        logger.info(f"Will delete {len(backups_to_delete)} old backups")

        for backup in backups_to_delete:
            try:
                backup_path = self.backup_dir / backup["filename"]
                if backup_path.exists():
                    file_size = backup_path.stat().st_size
                    backup_path.unlink()
                    deleted_size += file_size
                    deleted_count += 1
                    logger.info(
                        f"Deleted old backup: {backup['filename']} ({backup['created_at']})"
                    )
                else:
                    logger.warning(
                        f"Backup file not found on disk: {backup['filename']}"
                    )

                # Удаляем из метаданных
                self.metadata.remove_backup(backup["filename"])

            except Exception as e:
                logger.error(
                    f"Error deleting backup {backup.get('filename', 'unknown')}: {e}"
                )

        # Обновляем метаданные
        self.metadata._metadata["last_cleanup"] = datetime.utcnow().isoformat()
        self.metadata._save_metadata()

        cleanup_stats = {
            "deleted_count": deleted_count,
            "deleted_size_mb": round(deleted_size / (1024 * 1024), 2),
        }

        logger.info(
            f"Backup cleanup completed: {deleted_count} files deleted ({cleanup_stats['deleted_size_mb']} MB)",
            extra={"event_type": "backup", "backup_type": "cleanup"},
        )

        return cleanup_stats

    async def start_scheduler(self):
        """Запуск планировщика автоматических бэкапов"""
        if not self.config.BACKUP_ENABLED:
            logger.info("📂 Backup scheduler disabled by configuration")
            return

        if self._scheduler_running:
            logger.warning("Backup scheduler already running")
            return

        self._scheduler_running = True

        logger.info(
            f"📂 Starting backup scheduler: interval {self.config.BACKUP_INTERVAL_HOURS}h"
        )

        # Создаем первый бэкап при запуске
        await asyncio.get_event_loop().run_in_executor(
            None, self.create_backup, "startup"
        )

        # Запускаем периодический планировщик
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def stop_scheduler(self):
        """Остановка планировщика"""
        self._scheduler_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Backup scheduler stopped")

    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        try:
            while self._scheduler_running:
                await asyncio.sleep(self.config.BACKUP_INTERVAL_HOURS * 3600)

                if not self._scheduler_running:
                    break

                # Создаем бэкап
                await asyncio.get_event_loop().run_in_executor(
                    None, self.create_backup, "scheduled"
                )

                # Очищаем старые бэкапы раз в день
                current_hour = datetime.utcnow().hour
                if current_hour == 2:  # В 2 ночи по UTC
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.cleanup_old_backups
                    )

        except asyncio.CancelledError:
            logger.info("Backup scheduler loop cancelled")
        except Exception as e:
            logger.error(f"Error in backup scheduler loop: {e}", exc_info=True)

    def get_backup_status(self) -> Dict[str, Any]:
        """Получение текущего статуса системы бэкапов"""
        stats = self.metadata.get_stats()

        return {
            "enabled": self.config.BACKUP_ENABLED,
            "scheduler_running": self._scheduler_running,
            "backup_interval_hours": self.config.BACKUP_INTERVAL_HOURS,
            "backup_dir": str(self.backup_dir),
            "stats": stats,
            "config": {
                "compress_backups": self.config.COMPRESS_BACKUPS,
                "keep_hourly": self.config.KEEP_HOURLY_BACKUPS,
                "keep_daily": self.config.KEEP_DAILY_BACKUPS,
                "keep_weekly": self.config.KEEP_WEEKLY_BACKUPS,
                "keep_monthly": self.config.KEEP_MONTHLY_BACKUPS,
                "max_size_mb": self.config.MAX_BACKUP_SIZE_MB,
            },
        }


# Глобальный экземпляр менеджера бэкапов
backup_manager = DatabaseBackupManager()


# Публичные функции для использования в приложении
async def start_backup_scheduler():
    """Запуск планировщика бэкапов"""
    await backup_manager.start_scheduler()


async def stop_backup_scheduler():
    """Остановка планировщика бэкапов"""
    await backup_manager.stop_scheduler()


async def restart_backup_scheduler():
    """Перезапуск планировщика бэкапов с перезагрузкой конфигурации"""
    global backup_manager
    try:
        # Останавливаем текущий планировщик
        await backup_manager.stop_scheduler()
        logger.info("Backup scheduler stopped")
        
        # Ждем немного перед перезапуском
        import asyncio
        await asyncio.sleep(1)
        
        # Перезагружаем конфигурацию из файла
        from pathlib import Path
        import json
        config_file = Path("config") / "backup_config.json"
        if config_file.exists():
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
            
            # Обновляем переменные окружения
            for key, value in saved_config.items():
                os.environ[key] = value
            logger.info("Backup configuration reloaded from file")
        
        # Создаем новый экземпляр менеджера с новой конфигурацией
        backup_manager = DatabaseBackupManager()
        
        # Запускаем планировщик с новыми настройками
        await backup_manager.start_scheduler()
        logger.info("Backup scheduler restarted with new configuration")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restart backup scheduler: {e}")
        return False


def create_manual_backup() -> Optional[Dict[str, Any]]:
    """Создание ручного бэкапа"""
    return backup_manager.create_backup("manual")


def get_backup_status() -> Dict[str, Any]:
    """Получение статуса системы бэкапов"""
    return backup_manager.get_backup_status()


def list_available_backups() -> List[Dict[str, Any]]:
    """Получение списка доступных бэкапов"""
    return backup_manager.metadata.get_backups()


def restore_from_backup(backup_filename: str) -> bool:
    """Восстановление БД из бэкапа"""
    return backup_manager.restore_backup(backup_filename)


def cleanup_backups() -> Dict[str, int]:
    """Очистка старых бэкапов"""
    return backup_manager.cleanup_old_backups()
