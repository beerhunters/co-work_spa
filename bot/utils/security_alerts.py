"""
Модуль для отправки security alerts в Telegram группу
"""
import asyncio
import httpx
from config import GROUP_ID, BOT_TOKEN
from utils.logger import get_logger

logger = get_logger(__name__)


async def send_security_alert(ip: str, jail: str, country: str = "Unknown", isp: str = "Unknown"):
    """
    Отправляет уведомление о заблокированном IP в группу
    """
    try:
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        message = f"""🛡️ <b>SECURITY ALERT</b>

🚫 <b>IP заблокирован:</b> <code>{ip}</code>
🌍 <b>Страна:</b> {country}
🏢 <b>Провайдер:</b> {isp}
⚡ <b>Фильтр:</b> {jail}
⏰ <b>Время:</b> {current_time}

<i>IP автоматически заблокирован на 24 часа</i>"""

        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data={
                'chat_id': GROUP_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            })
            
            if response.status_code == 200:
                logger.info(f"Security alert sent to group for IP {ip}")
            else:
                logger.error(f"Failed to send security alert: {response.text}")
                
    except Exception as e:
        logger.error(f"Error sending security alert: {e}")


def send_security_alert_sync(ip: str, jail: str, country: str = "Unknown", isp: str = "Unknown"):
    """
    Синхронная версия для вызова из shell скриптов
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(send_security_alert(ip, jail, country, isp))
        loop.close()
    except Exception as e:
        logger.error(f"Error in sync security alert: {e}")