# utils/database_maintenance.py
import sqlite3
import time
import shutil
import threading
import schedule
from pathlib import Path
from typing import Optional

from models.models import DatabaseManager
from config import DATA_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


def optimize_database():
    """Оптимизация базы данных SQLite с улучшенной обработкой ошибок."""
    db_path = DATA_DIR / "coworking.db"

    if not db_path.exists():
        logger.warning(f"База данных не найдена: {db_path}")
        return

    try:
        logger.info("Начинается плановая оптимизация базы данных...")

        # Создаем резервную копию
        backup_path = db_path.with_suffix(f".backup.{int(time.time())}")
        shutil.copy2(db_path, backup_path)
        logger.info(f"Создана резервная копия: {backup_path}")

        # Оптимизация через DatabaseManager
        def _optimize(session):
            from sqlalchemy import text

            session.execute(text("PRAGMA optimize"))
            session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
            return True

        DatabaseManager.safe_execute(_optimize)

        # Дополнительная оптимизация через прямое соединение
        conn = sqlite3.connect(str(db_path), timeout=60)
        cursor = conn.cursor()

        # Проверяем целостность
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        if integrity_result != "ok":
            logger.warning(f"Проблема целостности БД: {integrity_result}")

        # Оптимизируем
        cursor.execute("VACUUM")
        cursor.execute("REINDEX")
        cursor.execute("ANALYZE")

        conn.commit()
        conn.close()

        logger.info("Плановая оптимизация базы данных завершена успешно")

        # Удаляем старые бэкапы (оставляем только последние 3)
        backup_files = sorted(DATA_DIR.glob("*.backup.*"))
        if len(backup_files) > 3:
            for old_backup in backup_files[:-3]:
                old_backup.unlink()
                logger.info(f"Удален старый бэкап: {old_backup}")

    except Exception as e:
        logger.error(f"Ошибка плановой оптимизации БД: {e}")


def check_db_health():
    """Проверка состояния базы данных."""
    try:
        db_path = DATA_DIR / "coworking.db"
        if db_path.exists():
            conn = sqlite3.connect(str(db_path), timeout=5)
            conn.execute("SELECT 1")
            conn.close()
            logger.debug("Проверка БД: OK")
        else:
            logger.warning("Файл базы данных не найден")
    except Exception as e:
        logger.warning(f"Проблема с БД обнаружена: {e}")


def start_maintenance_tasks():
    """Запускает планировщик обслуживания БД."""

    # Оптимизация каждый день в 3:00
    schedule.every().day.at("03:00").do(optimize_database)

    # Проверка состояния каждые 10 минут
    schedule.every(10).minutes.do(check_db_health)

    def run_maintenance():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверяем каждую минуту

    maintenance_thread = threading.Thread(target=run_maintenance, daemon=True)
    maintenance_thread.start()
    logger.info("Планировщик обслуживания БД запущен")


def create_database_backup(backup_name: str = None) -> Path:
    """Создание резервной копии базы данных."""
    db_path = DATA_DIR / "coworking.db"

    if not db_path.exists():
        raise FileNotFoundError("База данных не найдена")

    if backup_name is None:
        backup_name = f"coworking_backup_{int(time.time())}.db"

    backup_path = DATA_DIR / backup_name
    shutil.copy2(db_path, backup_path)

    logger.info(f"Создана резервная копия: {backup_path}")
    return backup_path


def restore_database_backup(backup_path: Path) -> bool:
    """Восстановление базы данных из резервной копии."""
    try:
        db_path = DATA_DIR / "coworking.db"

        if not backup_path.exists():
            raise FileNotFoundError(f"Резервная копия не найдена: {backup_path}")

        # Создаем копию текущей БД на случай проблем
        if db_path.exists():
            current_backup = db_path.with_suffix(f".current_backup.{int(time.time())}")
            shutil.copy2(db_path, current_backup)
            logger.info(f"Создана копия текущей БД: {current_backup}")

        # Восстанавливаем из бэкапа
        shutil.copy2(backup_path, db_path)

        # Проверяем целостность восстановленной БД
        conn = sqlite3.connect(str(db_path), timeout=10)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()

        if result != "ok":
            logger.error(f"Восстановленная БД повреждена: {result}")
            return False

        logger.info(f"База данных восстановлена из: {backup_path}")
        return True

    except Exception as e:
        logger.error(f"Ошибка восстановления БД: {e}")
        return False


def cleanup_old_backups(keep_count: int = 5):
    """Очистка старых резервных копий."""
    try:
        backup_files = sorted(DATA_DIR.glob("*.backup.*"))
        backup_files.extend(sorted(DATA_DIR.glob("*_backup_*.db")))

        if len(backup_files) > keep_count:
            for old_backup in backup_files[:-keep_count]:
                old_backup.unlink()
                logger.info(f"Удален старый бэкап: {old_backup}")

        logger.info(
            f"Очистка бэкапов завершена. Оставлено: {min(len(backup_files), keep_count)}"
        )

    except Exception as e:
        logger.error(f"Ошибка очистки бэкапов: {e}")


def get_database_stats() -> dict:
    """Получение статистики базы данных."""
    try:
        db_path = DATA_DIR / "coworking.db"

        if not db_path.exists():
            return {"error": "База данных не найдена"}

        conn = sqlite3.connect(str(db_path), timeout=10)
        cursor = conn.cursor()

        stats = {}

        # Размер файла
        stats["file_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 2)

        # Настройки PRAGMA
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]

        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]

        stats["page_count"] = page_count
        stats["page_size"] = page_size
        stats["database_size_mb"] = round((page_count * page_size) / (1024 * 1024), 2)

        # Режим журнала
        cursor.execute("PRAGMA journal_mode")
        stats["journal_mode"] = cursor.fetchone()[0]

        # Количество записей в таблицах
        tables = [
            "users",
            "bookings",
            "tickets",
            "tariffs",
            "promocodes",
            "notifications",
        ]
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            except Exception:
                stats[f"{table}_count"] = "N/A"

        conn.close()

        return stats

    except Exception as e:
        logger.error(f"Ошибка получения статистики БД: {e}")
        return {"error": str(e)}
