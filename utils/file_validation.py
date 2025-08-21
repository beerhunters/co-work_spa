"""
Модуль для безопасной валидации загружаемых файлов
"""
import imghdr
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, UploadFile

# Разрешенные MIME типы и расширения
ALLOWED_IMAGE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'image/webp': ['.webp']
}

# Максимальные размеры файлов (в байтах)
MAX_FILE_SIZES = {
    'image': 10 * 1024 * 1024,  # 10MB для изображений
    'document': 5 * 1024 * 1024,  # 5MB для документов
}

# Запрещенные расширения файлов
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.msi', '.dll',
    '.jar', '.js', '.vbs', '.ps1', '.sh', '.php', '.py', '.rb',
    '.pl', '.sql', '.html', '.htm', '.asp', '.aspx', '.jsp'
}


class FileValidator:
    """Класс для валидации загружаемых файлов"""
    
    @staticmethod
    def validate_image_file(file: UploadFile, max_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Комплексная валидация изображения
        
        Args:
            file: Загружаемый файл
            max_size: Максимальный размер файла в байтах
            
        Returns:
            Dict с результатами валидации
            
        Raises:
            HTTPException: При ошибках валидации
        """
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="Файл не предоставлен")
        
        # Проверка расширения
        file_ext = Path(file.filename).suffix.lower()
        if file_ext in DANGEROUS_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Запрещенное расширение файла: {file_ext}"
            )
        
        # Проверка MIME типа
        if not file.content_type or file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Неподдерживаемый тип файла: {file.content_type}"
            )
        
        # Проверка соответствия расширения и MIME типа
        allowed_extensions = ALLOWED_IMAGE_TYPES[file.content_type]
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Расширение {file_ext} не соответствует типу {file.content_type}"
            )
        
        # Проверка размера файла
        max_allowed_size = max_size or MAX_FILE_SIZES['image']
        if file.size and file.size > max_allowed_size:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой: {file.size} байт (максимум: {max_allowed_size})"
            )
        
        return {
            'filename': file.filename,
            'content_type': file.content_type,
            'extension': file_ext,
            'size': file.size,
            'valid': True
        }
    
    @staticmethod
    async def validate_file_content(file_content: bytes, expected_type: str) -> bool:
        """
        Валидация содержимого файла (magic numbers)
        
        Args:
            file_content: Содержимое файла
            expected_type: Ожидаемый тип файла ('image', 'document')
            
        Returns:
            bool: True если содержимое соответствует типу
        """
        try:
            if expected_type == 'image':
                # Проверка через imghdr (встроенная библиотека Python)
                image_type = imghdr.what(None, h=file_content)
                return image_type is not None
            
            # Для других типов можно использовать python-magic
            # mime_type = magic.from_buffer(file_content, mime=True)
            # return mime_type.startswith(expected_type)
            
            return True  # Базовая реализация
            
        except Exception:
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Очистка имени файла от опасных символов
        
        Args:
            filename: Исходное имя файла
            
        Returns:
            str: Безопасное имя файла
        """
        # Удаляем опасные символы
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/', '\x00']
        sanitized = filename
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Ограничиваем длину
        if len(sanitized) > 100:
            name, ext = Path(sanitized).stem, Path(sanitized).suffix
            sanitized = name[:95] + ext
        
        return sanitized
    
    @staticmethod
    def generate_safe_filename(original_filename: str, prefix: str = "") -> str:
        """
        Генерация безопасного уникального имени файла
        
        Args:
            original_filename: Исходное имя файла
            prefix: Префикс для имени файла
            
        Returns:
            str: Безопасное уникальное имя файла
        """
        import time
        import uuid
        
        # Получаем расширение
        ext = Path(original_filename).suffix.lower()
        
        # Генерируем уникальное имя
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        
        if prefix:
            safe_filename = f"{prefix}_{timestamp}_{unique_id}{ext}"
        else:
            safe_filename = f"{timestamp}_{unique_id}{ext}"
        
        return safe_filename


# Декоратор для валидации файлов
def validate_uploaded_file(file_type: str = 'image', max_size: Optional[int] = None):
    """
    Декоратор для валидации загружаемых файлов
    
    Args:
        file_type: Тип файла ('image', 'document')
        max_size: Максимальный размер файла
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Поиск UploadFile в аргументах
            for arg in args:
                if isinstance(arg, UploadFile):
                    if file_type == 'image':
                        FileValidator.validate_image_file(arg, max_size)
                    break
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator