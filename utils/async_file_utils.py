# utils/async_file_utils.py - новый модуль для async файловых операций
import asyncio
import aiofiles
import os
from pathlib import Path
from typing import Optional, List
import time
from concurrent.futures import ThreadPoolExecutor
from utils.logger import get_logger

logger = get_logger(__name__)

# Thread pool для CPU-intensive операций
_file_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="file_ops")


class AsyncFileManager:
    """Менеджер для асинхронных файловых операций"""

    @staticmethod
    async def save_uploaded_file(file_content: bytes, file_path: Path) -> bool:
        """Асинхронное сохранение загруженного файла"""
        try:
            # Создаем директорию если не существует
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Асинхронная запись файла
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(file_content)

            logger.debug(f"File saved successfully: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error saving file {file_path}: {e}")
            return False

    @staticmethod
    async def read_file_async(file_path: Path) -> Optional[bytes]:
        """Асинхронное чтение файла"""
        try:
            if not file_path.exists():
                return None

            async with aiofiles.open(file_path, "rb") as f:
                content = await f.read()

            return content

        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None

    @staticmethod
    async def delete_file_async(file_path: Path) -> bool:
        """Асинхронное удаление файла"""
        try:
            if file_path.exists():
                # Используем thread pool для файловых операций
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(_file_executor, file_path.unlink)
                logger.debug(f"File deleted: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False

    @staticmethod
    async def move_file_async(src_path: Path, dst_path: Path) -> bool:
        """Асинхронное перемещение файла"""
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_file_executor, src_path.rename, dst_path)

            logger.debug(f"File moved: {src_path} -> {dst_path}")
            return True

        except Exception as e:
            logger.error(f"Error moving file {src_path} -> {dst_path}: {e}")
            return False

    @staticmethod
    async def get_file_info(file_path: Path) -> Optional[dict]:
        """Асинхронное получение информации о файле"""
        try:
            if not file_path.exists():
                return None

            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(_file_executor, file_path.stat)

            return {
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "is_file": file_path.is_file(),
                "name": file_path.name,
            }

        except Exception as e:
            logger.error(f"Error getting file info {file_path}: {e}")
            return None
