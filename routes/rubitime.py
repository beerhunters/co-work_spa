# routes/rubitime.py
from fastapi import APIRouter, HTTPException
from utils.external_api import rubitime
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/rubitime", tags=["rubitime"])


@router.post("/create_record")
async def create_rubitime_record_from_bot(rubitime_params: dict):
    """
    Создает запись в Rubitime (вызывается из бота)
    """
    try:
        logger.info(f"Получен запрос на создание записи Rubitime: {rubitime_params}")

        # Проверяем наличие email и source
        logger.info(f"Email в запросе: '{rubitime_params.get('email', 'ОТСУТСТВУЕТ')}'")
        logger.info(
            f"Source в запросе: '{rubitime_params.get('source', 'ОТСУТСТВУЕТ')}'"
        )

        # НЕ перезаписываем source, если он уже передан
        if "source" not in rubitime_params:
            rubitime_params["source"] = "Telegram Bot"

        logger.info(
            f"Финальные параметры перед отправкой в rubitime(): {rubitime_params}"
        )

        result = await rubitime("create_record", rubitime_params)

        if result:
            logger.info(f"Успешно создана запись Rubitime с ID: {result}")
            return {"rubitime_id": result}
        else:
            logger.warning("Не удалось создать запись в Rubitime")
            raise HTTPException(
                status_code=400, detail="Не удалось создать запись в Rubitime"
            )

    except Exception as e:
        logger.error(f"Ошибка создания записи Rubitime: {e}")
        raise HTTPException(status_code=500, detail=str(e))
