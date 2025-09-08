"""
Система отслеживания статуса компонентов и отправки сводного уведомления о запуске
"""

import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from config import ENVIRONMENT, MOSCOW_TZ, FOR_LOGS, BOT_TOKEN
from utils.bot_instance import get_bot

logger = logging.getLogger(__name__)

class SystemStatusManager:
    """Менеджер статуса системы и уведомлений"""
    
    def __init__(self):
        # Определяем путь к файлу статуса в зависимости от окружения
        if os.path.exists("/app/data"):
            # Продакшн/Docker окружение
            self.status_file = Path("/app/data/system_status.json")
        else:
            # Локальная разработка
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
            data_dir.mkdir(exist_ok=True)
            self.status_file = data_dir / "system_status.json"
            
        self.components = ["web", "bot"]  # Основные компоненты системы
        self.startup_timeout = 300  # 5 минут на запуск всех компонентов
        
    def _load_status(self) -> Dict:
        """Загружает текущий статус системы"""
        if not self.status_file.exists():
            return {
                "startup_time": datetime.now().isoformat(),
                "components": {},
                "notification_sent": False,
                "all_ready": False
            }
        
        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки статуса: {e}")
            return {
                "startup_time": datetime.now().isoformat(),
                "components": {},
                "notification_sent": False,
                "all_ready": False
            }
    
    def _save_status(self, status: Dict):
        """Сохраняет статус системы"""
        try:
            # Создаем директорию если не существует
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения статуса: {e}")
    
    def register_component_ready(self, component_name: str):
        """Регистрирует готовность компонента"""
        status = self._load_status()
        
        status["components"][component_name] = {
            "ready": True,
            "timestamp": datetime.now().isoformat(),
            "pid": os.getpid()
        }
        
        logger.info(f"Компонент {component_name} зарегистрирован как готовый")
        self._save_status(status)
        
        # Проверяем, готовы ли все компоненты
        asyncio.create_task(self._check_and_notify_if_all_ready())
    
    def _is_telegram_enabled(self) -> bool:
        """Проверяет, включены ли Telegram уведомления"""
        return (
            os.getenv("TELEGRAM_LOGGING_ENABLED", "false").lower() == "true" and
            bool(FOR_LOGS) and
            bool(BOT_TOKEN)
        )
    
    async def _check_and_notify_if_all_ready(self):
        """Проверяет готовность всех компонентов и отправляет уведомление"""
        status = self._load_status()
        
        # Если уведомление уже отправлено, не делаем ничего
        if status.get("notification_sent", False):
            return
        
        # Проверяем, готовы ли все компоненты
        ready_components = []
        for component in self.components:
            if component in status["components"] and status["components"][component].get("ready", False):
                ready_components.append(component)
        
        logger.info(f"Готовые компоненты: {ready_components} из {self.components}")
        
        # Если все компоненты готовы
        if len(ready_components) == len(self.components):
            await self._send_system_ready_notification(status, ready_components)
            
            # Помечаем как отправленное
            status["notification_sent"] = True
            status["all_ready"] = True
            status["ready_time"] = datetime.now().isoformat()
            self._save_status(status)
            
        # Проверяем таймаут
        elif self._is_startup_timeout(status):
            await self._send_partial_ready_notification(status, ready_components)
            
            # Помечаем как отправленное (чтобы не спамить)
            status["notification_sent"] = True
            self._save_status(status)
    
    def _is_startup_timeout(self, status: Dict) -> bool:
        """Проверяет, истек ли таймаут запуска"""
        startup_time = datetime.fromisoformat(status["startup_time"])
        return (datetime.now() - startup_time).total_seconds() > self.startup_timeout
    
    async def _send_system_ready_notification(self, status: Dict, ready_components: List[str]):
        """Отправляет уведомление о готовности всей системы"""
        if not self._is_telegram_enabled():
            return
        
        try:
            bot = get_bot()
            if not bot:
                return
            
            env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
            moscow_time = datetime.now(MOSCOW_TZ)
            
            # Вычисляем время запуска
            startup_time = datetime.fromisoformat(status["startup_time"])
            startup_duration = datetime.now() - startup_time
            
            message = f"✅ <b>СИСТЕМА ГОТОВА К РАБОТЕ</b> {env_text}\n\n"
            message += f"🕐 <b>Время готовности:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
            message += f"⏱️ <b>Время запуска:</b> {int(startup_duration.total_seconds())} сек\n"
            message += f"📊 <b>Среда:</b> {ENVIRONMENT}\n\n"
            
            message += f"🟢 <b>Готовые компоненты:</b>\n"
            for component in ready_components:
                comp_data = status["components"][component]
                comp_time = datetime.fromisoformat(comp_data["timestamp"])
                comp_duration = comp_time - startup_time
                
                if component == "web":
                    icon = "🌐"
                    name = "Web API"
                elif component == "bot":
                    icon = "🤖"
                    name = "Telegram Bot"
                else:
                    icon = "⚙️"
                    name = component.title()
                
                message += f"  {icon} {name} ({int(comp_duration.total_seconds())}s)\n"
            
            message += f"\n📝 <b>Уведомления:</b> включены"
            
            await bot.send_message(
                chat_id=FOR_LOGS,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.info("Отправлено уведомление о готовности всей системы")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о готовности системы: {e}")
    
    async def _send_partial_ready_notification(self, status: Dict, ready_components: List[str]):
        """Отправляет уведомление о частичной готовности (по таймауту)"""
        if not self._is_telegram_enabled():
            return
        
        try:
            bot = get_bot()
            if not bot:
                return
            
            env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
            moscow_time = datetime.now(MOSCOW_TZ)
            
            not_ready = [c for c in self.components if c not in ready_components]
            
            message = f"⚠️ <b>ЧАСТИЧНЫЙ ЗАПУСК СИСТЕМЫ</b> {env_text}\n\n"
            message += f"🕐 <b>Время:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
            message += f"📊 <b>Среда:</b> {ENVIRONMENT}\n\n"
            
            if ready_components:
                message += f"✅ <b>Готовые компоненты:</b>\n"
                for component in ready_components:
                    icon = "🌐" if component == "web" else "🤖" if component == "bot" else "⚙️"
                    name = "Web API" if component == "web" else "Telegram Bot" if component == "bot" else component.title()
                    message += f"  {icon} {name}\n"
            
            if not_ready:
                message += f"\n❌ <b>Не готовые компоненты:</b>\n"
                for component in not_ready:
                    icon = "🌐" if component == "web" else "🤖" if component == "bot" else "⚙️"
                    name = "Web API" if component == "web" else "Telegram Bot" if component == "bot" else component.title()
                    message += f"  {icon} {name}\n"
            
            message += f"\n⏰ <b>Таймаут:</b> {self.startup_timeout}s"
            
            await bot.send_message(
                chat_id=FOR_LOGS,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            
            logger.warning("Отправлено уведомление о частичной готовности системы")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о частичной готовности: {e}")
    
    def cleanup_old_status(self):
        """Очищает старый статус при новом запуске"""
        if self.status_file.exists():
            try:
                self.status_file.unlink()
                logger.info("Очищен старый файл статуса системы")
            except Exception as e:
                logger.error(f"Ошибка очистки старого статуса: {e}")

# Глобальный экземпляр менеджера
_system_manager = SystemStatusManager()

def register_component_startup(component_name: str):
    """Регистрирует запуск компонента системы"""
    _system_manager.register_component_ready(component_name)

def cleanup_system_status():
    """Очищает статус системы (вызывать при новом запуске)"""
    _system_manager.cleanup_old_status()

async def send_system_shutdown_notification() -> bool:
    """Отправляет уведомление об остановке системы"""
    if not _system_manager._is_telegram_enabled():
        return False
    
    try:
        bot = get_bot()
        if not bot:
            return False
        
        env_text = "🏭 PRODUCTION" if ENVIRONMENT == "production" else "🧪 DEVELOPMENT"
        moscow_time = datetime.now(MOSCOW_TZ)
        
        message = f"⏹️ <b>ОСТАНОВКА СИСТЕМЫ</b> {env_text}\n\n"
        message += f"🕐 <b>Время:</b> {moscow_time.strftime('%Y-%m-%d %H:%M:%S')} (МСК)\n"
        message += f"📊 <b>Среда:</b> {ENVIRONMENT}\n"
        
        await bot.send_message(
            chat_id=FOR_LOGS,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        # Очищаем статус после отправки
        _system_manager.cleanup_old_status()
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об остановке системы: {e}")
        return False