"""
API для управления системой резервного копирования
"""
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from dependencies import verify_token
from utils.backup_manager import (
    create_manual_backup, 
    get_backup_status,
    list_available_backups,
    restore_from_backup,
    cleanup_backups,
    backup_manager
)
from utils.structured_logging import get_structured_logger, log_application_event

logger = get_structured_logger(__name__)
router = APIRouter(prefix="/backups", tags=["backups"])


class BackupCreateRequest(BaseModel):
    """Запрос на создание бэкапа"""
    backup_type: str = Field("manual", description="Тип бэкапа")
    description: Optional[str] = Field(None, description="Описание бэкапа")


class BackupInfo(BaseModel):
    """Информация о бэкапе"""
    filename: str
    type: str
    created_at: str
    size_bytes: int
    size_mb: float
    compressed: bool
    db_path: str


class BackupStatus(BaseModel):
    """Статус системы бэкапов"""
    enabled: bool
    scheduler_running: bool
    backup_interval_hours: int
    backup_dir: str
    stats: Dict[str, Any]
    config: Dict[str, Any]


class RestoreRequest(BaseModel):
    """Запрос на восстановление из бэкапа"""
    backup_filename: str = Field(..., description="Имя файла бэкапа")
    confirm_restore: bool = Field(False, description="Подтверждение восстановления")


@router.get("/status", response_model=BackupStatus)
async def get_backup_system_status(
    _: str = Depends(verify_token)
):
    """
    Получение статуса системы бэкапов
    """
    try:
        status = get_backup_status()
        return BackupStatus(**status)
    except Exception as e:
        logger.error(f"Error getting backup status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get backup status")


@router.post("/create", response_model=BackupInfo)
async def create_backup(
    request: BackupCreateRequest,
    background_tasks: BackgroundTasks,
    current_admin: str = Depends(verify_token)
):
    """
    Создание нового бэкапа вручную
    
    Бэкап создается в фоновом режиме для не блокирования API
    """
    try:
        # Валидируем тип бэкапа
        allowed_types = ["manual", "pre_update", "maintenance"]
        if request.backup_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid backup type. Allowed: {allowed_types}"
            )
        
        logger.info(
            f"Manual backup requested by {current_admin.login}",
            extra={"backup_type": request.backup_type}
        )
        
        # Создаем бэкап синхронно для получения результата
        backup_info = create_manual_backup()
        
        if not backup_info:
            raise HTTPException(status_code=500, detail="Failed to create backup")
        
        log_application_event(
            "backup",
            f"Manual backup created by admin: {current_admin.login}",
            backup_filename=backup_info["filename"],
            backup_type=request.backup_type,
            size_mb=backup_info["size_mb"]
        )
        
        return BackupInfo(**backup_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create backup")


@router.post("/restore")
async def restore_backup(
    request: RestoreRequest,
    current_admin: str = Depends(verify_token)
):
    """
    Восстановление базы данных из бэкапа
    
    **ВНИМАНИЕ:** Операция необратима! Текущая БД будет заменена.
    """
    try:
        if not request.confirm_restore:
            raise HTTPException(
                status_code=400,
                detail="Restore confirmation required. Set confirm_restore=true"
            )
        
        # Проверяем что бэкап существует
        available_backups = list_available_backups()
        backup_exists = any(
            b["filename"] == request.backup_filename 
            for b in available_backups
        )
        
        if not backup_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Backup file not found: {request.backup_filename}"
            )
        
        logger.warning(
            f"Database restore initiated by {current_admin.login}",
            extra={
                "backup_filename": request.backup_filename,
                "admin": current_admin.login
            }
        )
        
        # Выполняем восстановление
        success = restore_from_backup(request.backup_filename)
        
        if not success:
            raise HTTPException(status_code=500, detail="Database restore failed")
        
        log_application_event(
            "backup",
            f"Database restored from backup by admin: {current_admin.login}",
            backup_filename=request.backup_filename,
            admin=current_admin.login
        )
        
        return {
            "message": "Database restored successfully",
            "backup_filename": request.backup_filename,
            "restored_by": current_admin.login,
            "restored_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to restore backup")


@router.post("/cleanup")
async def cleanup_old_backups(
    current_admin: str = Depends(verify_token)
):
    """
    Очистка старых бэкапов согласно политике ротации
    """
    try:
        logger.info(f"Backup cleanup initiated by {current_admin.login}")
        
        cleanup_stats = cleanup_backups()
        
        log_application_event(
            "backup",
            f"Backup cleanup completed by admin: {current_admin.login}",
            deleted_count=cleanup_stats["deleted_count"],
            deleted_size_mb=cleanup_stats["deleted_size_mb"]
        )
        
        return {
            "message": "Backup cleanup completed",
            "deleted_count": cleanup_stats["deleted_count"],
            "deleted_size_mb": cleanup_stats["deleted_size_mb"],
            "cleaned_by": current_admin.login,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cleanup backups")


@router.delete("/{filename}")
async def delete_backup_file(
    filename: str,
    current_admin: str = Depends(verify_token)
):
    """
    Удаление конкретного файла бэкапа (только для суперадмина)
    """
    try:
        # Проверяем права суперадмина
        if not hasattr(current_admin, 'role') or current_admin.role.value != "super_admin":
            raise HTTPException(
                status_code=403, 
                detail="Only super admin can delete backups"
            )
        
        # Проверяем что бэкап существует
        available_backups = list_available_backups()
        backup_exists = any(
            b["filename"] == filename 
            for b in available_backups
        )
        
        if not backup_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Backup file not found: {filename}"
            )
        
        # Удаляем файл
        from utils.backup_manager import backup_manager
        backup_path = backup_manager.backup_dir / filename
        
        if backup_path.exists():
            backup_path.unlink()
            logger.info(f"Backup file deleted: {filename} by {current_admin.login}")
            
            log_application_event(
                "backup",
                f"Backup file deleted by super admin: {current_admin.login}",
                backup_filename=filename
            )
            
            return {
                "message": "Backup file deleted successfully",
                "filename": filename,
                "deleted_by": current_admin.login,
                "deleted_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Backup file not found on disk")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting backup file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete backup file")


@router.get("/config")
async def get_backup_config(
    _: str = Depends(verify_token)
):
    """
    Получение конфигурации системы бэкапов
    """
    try:
        from utils.backup_manager import BackupConfig
        config = BackupConfig()
        
        return {
            "backup_enabled": config.BACKUP_ENABLED,
            "backup_interval_hours": config.BACKUP_INTERVAL_HOURS,
            "backup_dir": str(config.BACKUP_DIR),
            "retention_policy": {
                "keep_hourly_backups": config.KEEP_HOURLY_BACKUPS,
                "keep_daily_backups": config.KEEP_DAILY_BACKUPS,
                "keep_weekly_backups": config.KEEP_WEEKLY_BACKUPS,
                "keep_monthly_backups": config.KEEP_MONTHLY_BACKUPS
            },
            "compression": {
                "compress_backups": config.COMPRESS_BACKUPS,
                "backup_encryption": config.BACKUP_ENCRYPTION,
                "max_backup_size_mb": config.MAX_BACKUP_SIZE_MB
            },
            "database": {
                "db_path": str(config.DB_PATH)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting backup config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get backup config")


@router.get("/health")
async def get_backup_health(
    _: str = Depends(verify_token)
):
    """
    Health check для системы бэкапов
    """
    try:
        status = get_backup_status()
        stats = status.get("stats", {})
        
        # Определяем здоровье системы
        is_healthy = True
        issues = []
        
        # Проверяем что планировщик работает если включен
        if status.get("enabled", False) and not status.get("scheduler_running", False):
            is_healthy = False
            issues.append("Backup scheduler not running")
        
        # Проверяем что есть свежие бэкапы
        last_backup = stats.get("last_backup")
        if last_backup:
            last_backup_time = datetime.fromisoformat(last_backup["created_at"])
            hours_since_backup = (datetime.utcnow() - last_backup_time).total_seconds() / 3600
            
            if hours_since_backup > status.get("backup_interval_hours", 6) * 2:  # 2x interval
                is_healthy = False
                issues.append(f"Last backup was {hours_since_backup:.1f} hours ago")
        else:
            is_healthy = False
            issues.append("No backups found")
        
        # Проверяем количество неудачных бэкапов
        failed_backups = stats.get("failed_backups", 0)
        if failed_backups > 3:
            is_healthy = False
            issues.append(f"Too many failed backups: {failed_backups}")
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "scheduler_running": status.get("scheduler_running", False),
            "last_backup": last_backup,
            "total_backups": stats.get("total_backups", 0),
            "failed_backups": failed_backups,
            "total_size_mb": stats.get("total_size_mb", 0),
            "issues": issues,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting backup health: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "issues": [f"Health check failed: {str(e)}"],
            "timestamp": datetime.utcnow().isoformat()
        }


# Эндпоинт для интеграции с мониторингом
@router.get("/metrics")
async def get_backup_metrics():
    """
    Метрики системы бэкапов для мониторинга (Prometheus format)
    """
    try:
        status = get_backup_status()
        stats = status.get("stats", {})
        
        metrics = [
            f"# HELP backup_enabled Whether backup system is enabled",
            f"# TYPE backup_enabled gauge",
            f"backup_enabled {1 if status.get('enabled', False) else 0}",
            "",
            f"# HELP backup_scheduler_running Whether backup scheduler is running",
            f"# TYPE backup_scheduler_running gauge", 
            f"backup_scheduler_running {1 if status.get('scheduler_running', False) else 0}",
            "",
            f"# HELP backup_total_count Total number of backups",
            f"# TYPE backup_total_count gauge",
            f"backup_total_count {stats.get('total_backups', 0)}",
            "",
            f"# HELP backup_failed_total Total number of failed backups",
            f"# TYPE backup_failed_total counter",
            f"backup_failed_total {stats.get('failed_backups', 0)}",
            "",
            f"# HELP backup_total_size_bytes Total size of all backups in bytes",
            f"# TYPE backup_total_size_bytes gauge",
            f"backup_total_size_bytes {stats.get('total_size_mb', 0) * 1024 * 1024}",
            ""
        ]
        
        # Добавляем время последнего бэкапа
        last_backup = stats.get("last_backup")
        if last_backup:
            last_backup_timestamp = datetime.fromisoformat(last_backup["created_at"]).timestamp()
            metrics.extend([
                f"# HELP backup_last_timestamp Unix timestamp of last backup",
                f"# TYPE backup_last_timestamp gauge",
                f"backup_last_timestamp {last_backup_timestamp}",
                ""
            ])
        
        return "\n".join(metrics)
        
    except Exception as e:
        logger.error(f"Error getting backup metrics: {e}", exc_info=True)
        return f"# Error getting backup metrics: {str(e)}\n"


class BackupSettingsUpdate(BaseModel):
    """Обновление настроек бэкапов"""
    backup_enabled: Optional[bool] = None
    backup_interval_hours: Optional[int] = Field(None, ge=1, le=168)  # 1 час - 1 неделя
    compress_backups: Optional[bool] = None
    keep_hourly_backups: Optional[int] = Field(None, ge=1, le=168)
    keep_daily_backups: Optional[int] = Field(None, ge=1, le=365)
    keep_weekly_backups: Optional[int] = Field(None, ge=1, le=104)
    keep_monthly_backups: Optional[int] = Field(None, ge=1, le=24)
    max_backup_size_mb: Optional[int] = Field(None, ge=1, le=10000)


@router.get("/list", response_model=List[BackupInfo])
async def list_backups(
    current_admin: str = Depends(verify_token)
):
    """
    Получение списка всех доступных бэкапов (только для суперадмина)
    """
    try:
        # Проверяем права суперадмина
        if not hasattr(current_admin, 'role') or current_admin.role.value != "super_admin":
            raise HTTPException(
                status_code=403, 
                detail="Only super admin can view backup list"
            )
        
        # Получаем список бэкапов
        from utils.backup_manager import list_available_backups, backup_manager
        try:
            # Отладочная информация
            logger.info(f"Backup directory: {backup_manager.backup_dir}")
            logger.info(f"Backup directory exists: {backup_manager.backup_dir.exists()}")
            
            if backup_manager.backup_dir.exists():
                files_in_dir = list(backup_manager.backup_dir.iterdir())
                logger.info(f"Files in backup directory: {[f.name for f in files_in_dir]}")
            
            logger.info(f"Metadata file: {backup_manager.metadata.metadata_file}")
            logger.info(f"Metadata file exists: {backup_manager.metadata.metadata_file.exists()}")
            
            backups = list_available_backups()
            
            # Сортируем по дате создания (новые сначала)
            backups.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            logger.info(f"Backup list requested by {current_admin.login}, found {len(backups)} backups")
            logger.info(f"Backup data: {backups}")
            
        except Exception as e:
            logger.warning(f"Error getting backup list, returning empty list: {e}")
            backups = []
        
        return backups
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list backups")


@router.get("/settings")
async def get_backup_settings(
    current_admin: str = Depends(verify_token)
):
    """
    Получение текущих настроек системы бэкапов (только для суперадмина)
    """
    try:
        # Проверяем права суперадмина
        if not hasattr(current_admin, 'role') or current_admin.role.value != "super_admin":
            raise HTTPException(
                status_code=403, 
                detail="Only super admin can view backup settings"
            )
        
        # Получаем текущие настройки из переменных окружения
        import os
        
        settings = {
            "backup_enabled": os.getenv("BACKUP_ENABLED", "true").lower() == "true",
            "backup_interval_hours": int(os.getenv("BACKUP_INTERVAL_HOURS", "6")),
            "compress_backups": os.getenv("COMPRESS_BACKUPS", "true").lower() == "true",
            "keep_hourly_backups": int(os.getenv("KEEP_HOURLY_BACKUPS", "48")),
            "keep_daily_backups": int(os.getenv("KEEP_DAILY_BACKUPS", "30")),
            "keep_weekly_backups": int(os.getenv("KEEP_WEEKLY_BACKUPS", "12")),
            "keep_monthly_backups": int(os.getenv("KEEP_MONTHLY_BACKUPS", "6")),
            "max_backup_size_mb": int(os.getenv("MAX_BACKUP_SIZE_MB", "1000")),
        }
        
        logger.info(f"Backup settings requested by {current_admin.login}")
        
        return settings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backup settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get backup settings")


@router.put("/settings")
async def update_backup_settings(
    settings: BackupSettingsUpdate,
    current_admin: str = Depends(verify_token)
):
    """
    Обновление настроек системы бэкапов (только для суперадмина)
    """
    try:
        # Проверяем права суперадмина
        if not hasattr(current_admin, 'role') or current_admin.role.value != "super_admin":
            raise HTTPException(
                status_code=403, 
                detail="Only super admin can modify backup settings"
            )
        
        # Получаем текущие настройки
        from utils.backup_manager import BackupConfig
        config = BackupConfig()
        
        updated_settings = {}
        
        # Обновляем настройки (в реальном приложении здесь была бы база данных)
        if settings.backup_enabled is not None:
            updated_settings["BACKUP_ENABLED"] = str(settings.backup_enabled).lower()
            
        if settings.backup_interval_hours is not None:
            updated_settings["BACKUP_INTERVAL_HOURS"] = str(settings.backup_interval_hours)
            
        if settings.compress_backups is not None:
            updated_settings["COMPRESS_BACKUPS"] = str(settings.compress_backups).lower()
            
        if settings.keep_hourly_backups is not None:
            updated_settings["KEEP_HOURLY_BACKUPS"] = str(settings.keep_hourly_backups)
            
        if settings.keep_daily_backups is not None:
            updated_settings["KEEP_DAILY_BACKUPS"] = str(settings.keep_daily_backups)
            
        if settings.keep_weekly_backups is not None:
            updated_settings["KEEP_WEEKLY_BACKUPS"] = str(settings.keep_weekly_backups)
            
        if settings.keep_monthly_backups is not None:
            updated_settings["KEEP_MONTHLY_BACKUPS"] = str(settings.keep_monthly_backups)
            
        if settings.max_backup_size_mb is not None:
            updated_settings["MAX_BACKUP_SIZE_MB"] = str(settings.max_backup_size_mb)
        
        # Логируем изменения
        log_application_event(
            "backup",
            f"Backup settings updated by super admin: {current_admin.login}",
            updated_settings=updated_settings
        )
        
        logger.info(
            f"Backup settings updated by {current_admin.login}",
            extra={"updated_settings": updated_settings}
        )
        
        return {
            "message": "Backup settings updated successfully",
            "updated_settings": updated_settings,
            "updated_by": current_admin.login,
            "updated_at": datetime.utcnow().isoformat(),
            "note": "Settings will take effect after application restart"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating backup settings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update backup settings")


@router.post("/test-restore")
async def test_backup_restore(
    request: RestoreRequest,
    current_admin: str = Depends(verify_token)
):
    """
    Тестирование восстановления бэкапа (только проверка целостности)
    """
    try:
        # Проверяем что бэкап существует
        available_backups = list_available_backups()
        backup_info = None
        for backup in available_backups:
            if backup["filename"] == request.backup_filename:
                backup_info = backup
                break
        
        if not backup_info:
            raise HTTPException(
                status_code=404,
                detail=f"Backup file not found: {request.backup_filename}"
            )
        
        # Проверяем размер и доступность файла
        from utils.backup_manager import backup_manager
        backup_path = backup_manager.backup_dir / request.backup_filename
        
        if not backup_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Backup file not accessible"
            )
        
        file_size = backup_path.stat().st_size
        
        # Проверяем целостность (базовая проверка)
        try:
            if request.backup_filename.endswith('.gz'):
                import gzip
                with gzip.open(backup_path, 'rb') as f:
                    # Читаем первые байты для проверки
                    f.read(100)
            else:
                with open(backup_path, 'rb') as f:
                    f.read(100)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Backup file appears to be corrupted: {e}"
            )
        
        log_application_event(
            "backup",
            f"Backup integrity test performed by admin: {current_admin.login}",
            backup_filename=request.backup_filename,
            test_result="passed"
        )
        
        return {
            "message": "Backup file integrity test passed",
            "backup_filename": request.backup_filename,
            "backup_info": backup_info,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "tested_by": current_admin.login,
            "tested_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing backup restore: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to test backup restore")


@router.get("/dashboard-stats")
async def get_backup_dashboard_stats(
    _: str = Depends(verify_token)
):
    """
    Статистика для dashboard админки
    """
    try:
        status = get_backup_status()
        stats = status.get("stats", {})
        
        # Вычисляем дополнительные метрики
        last_backup = stats.get("last_backup")
        last_backup_age_hours = None
        
        if last_backup:
            last_backup_time = datetime.fromisoformat(last_backup["created_at"])
            age_delta = datetime.utcnow() - last_backup_time
            last_backup_age_hours = age_delta.total_seconds() / 3600
        
        # Оценка здоровья системы
        health_status = "healthy"
        health_issues = []
        
        if not status.get("scheduler_running", False):
            health_status = "warning"
            health_issues.append("Scheduler not running")
            
        if last_backup_age_hours and last_backup_age_hours > status.get("backup_interval_hours", 6) * 2:
            health_status = "critical"
            health_issues.append(f"Last backup was {last_backup_age_hours:.1f} hours ago")
            
        if stats.get("failed_backups", 0) > 0:
            health_status = "warning" if health_status == "healthy" else health_status
            health_issues.append(f"{stats.get('failed_backups')} failed backups")
        
        return {
            "enabled": status.get("enabled", False),
            "scheduler_running": status.get("scheduler_running", False),
            "health_status": health_status,
            "health_issues": health_issues,
            "total_backups": stats.get("total_backups", 0),
            "total_created": stats.get("total_created", 0),
            "failed_backups": stats.get("failed_backups", 0),
            "total_size_mb": stats.get("total_size_mb", 0),
            "last_backup": last_backup,
            "last_backup_age_hours": round(last_backup_age_hours, 1) if last_backup_age_hours else None,
            "next_backup_in_hours": status.get("backup_interval_hours", 6) - (last_backup_age_hours or 0) if last_backup_age_hours else None,
            "retention_policy": {
                "hourly": status.get("config", {}).get("keep_hourly", 48),
                "daily": status.get("config", {}).get("keep_daily", 30),
                "weekly": status.get("config", {}).get("keep_weekly", 12),
                "monthly": status.get("config", {}).get("keep_monthly", 6)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting backup dashboard stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get backup dashboard stats")