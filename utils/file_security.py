"""
Безопасность файлов - валидация и проверка загружаемых файлов
"""
import os
import mimetypes
from pathlib import Path
from typing import Optional, List, Tuple
from fastapi import UploadFile, HTTPException
from PIL import Image
import io

from utils.logger import get_logger

logger = get_logger(__name__)

# Безопасные MIME типы для изображений
ALLOWED_IMAGE_TYPES = {
    'image/jpeg',
    'image/jpg', 
    'image/png',
    'image/gif',
    'image/webp',
    'image/bmp',
    'image/tiff'
}

# Безопасные расширения файлов
ALLOWED_IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'
}

# Максимальные размеры файлов (в байтах)
MAX_FILE_SIZES = {
    'image': 10 * 1024 * 1024,  # 10MB для изображений
    'avatar': 2 * 1024 * 1024,   # 2MB для аватаров
    'newsletter': 20 * 1024 * 1024,  # 20MB для рассылок
}

# Максимальные размеры изображений (пиксели)
MAX_IMAGE_DIMENSIONS = {
    'width': 4000,
    'height': 4000,
}

class FileSecurityError(Exception):
    """Ошибка безопасности файла"""
    pass

def validate_file_extension(filename: str, allowed_extensions: set = None) -> bool:
    """
    Валидация расширения файла
    
    Args:
        filename: Имя файла
        allowed_extensions: Разрешенные расширения (по умолчанию ALLOWED_IMAGE_EXTENSIONS)
    
    Returns:
        bool: True если расширение разрешено
    
    Raises:
        FileSecurityError: Если расширение запрещено
    """
    if not filename:
        raise FileSecurityError("Filename is empty")
    
    if allowed_extensions is None:
        allowed_extensions = ALLOWED_IMAGE_EXTENSIONS
    
    ext = Path(filename).suffix.lower()
    if ext not in allowed_extensions:
        raise FileSecurityError(f"File extension '{ext}' is not allowed. Allowed: {', '.join(allowed_extensions)}")
    
    return True

def validate_mime_type(content_type: str, allowed_types: set = None) -> bool:
    """
    Валидация MIME типа файла
    
    Args:
        content_type: MIME тип файла
        allowed_types: Разрешенные MIME типы (по умолчанию ALLOWED_IMAGE_TYPES)
    
    Returns:
        bool: True если MIME тип разрешен
    
    Raises:
        FileSecurityError: Если MIME тип запрещен
    """
    if not content_type:
        raise FileSecurityError("Content type is empty")
    
    if allowed_types is None:
        allowed_types = ALLOWED_IMAGE_TYPES
    
    if content_type not in allowed_types:
        raise FileSecurityError(f"Content type '{content_type}' is not allowed. Allowed: {', '.join(allowed_types)}")
    
    return True

def validate_file_size(file_size: int, max_size: int = None, file_type: str = 'image') -> bool:
    """
    Валидация размера файла
    
    Args:
        file_size: Размер файла в байтах
        max_size: Максимальный размер (если не указан, берется из MAX_FILE_SIZES)
        file_type: Тип файла для определения лимита
    
    Returns:
        bool: True если размер в пределах лимита
    
    Raises:
        FileSecurityError: Если файл слишком большой
    """
    if file_size <= 0:
        raise FileSecurityError("File size must be greater than 0")
    
    if max_size is None:
        max_size = MAX_FILE_SIZES.get(file_type, MAX_FILE_SIZES['image'])
    
    if file_size > max_size:
        max_size_mb = max_size / (1024 * 1024)
        file_size_mb = file_size / (1024 * 1024)
        raise FileSecurityError(f"File too large: {file_size_mb:.1f}MB. Maximum allowed: {max_size_mb:.1f}MB")
    
    return True

def detect_file_type(file_content: bytes) -> str:
    """
    Определение реального типа файла по содержимому (не по расширению)
    
    Args:
        file_content: Содержимое файла в байтах
    
    Returns:
        str: Реальный MIME тип файла
    
    Raises:
        FileSecurityError: Если не удается определить тип файла
    """
    try:
        # Определяем тип по магическим байтам (файловым сигнатурам)
        if file_content.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif file_content.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif file_content.startswith(b'GIF87a') or file_content.startswith(b'GIF89a'):
            return 'image/gif'
        elif file_content.startswith(b'RIFF') and b'WEBP' in file_content[:20]:
            return 'image/webp'
        elif file_content.startswith(b'BM'):
            return 'image/bmp'
        elif file_content.startswith(b'II*\x00') or file_content.startswith(b'MM\x00*'):
            return 'image/tiff'
        else:
            # Пробуем определить через Pillow
            try:
                with Image.open(io.BytesIO(file_content)) as img:
                    format_to_mime = {
                        'JPEG': 'image/jpeg',
                        'PNG': 'image/png',
                        'GIF': 'image/gif',
                        'WEBP': 'image/webp',
                        'BMP': 'image/bmp',
                        'TIFF': 'image/tiff'
                    }
                    return format_to_mime.get(img.format, 'application/octet-stream')
            except Exception:
                raise FileSecurityError("Unknown or invalid file type")
    except FileSecurityError:
        raise
    except Exception:
        raise FileSecurityError("Cannot detect file type")

def validate_image_content(file_content: bytes) -> Tuple[int, int]:
    """
    Валидация содержимого изображения и получение размеров
    
    Args:
        file_content: Содержимое файла в байтах
    
    Returns:
        Tuple[int, int]: Ширина и высота изображения
    
    Raises:
        FileSecurityError: Если файл поврежден или слишком большой
    """
    try:
        # Проверяем, что это действительно валидное изображение
        with Image.open(io.BytesIO(file_content)) as img:
            width, height = img.size
            
            # Проверяем размеры изображения
            if width > MAX_IMAGE_DIMENSIONS['width'] or height > MAX_IMAGE_DIMENSIONS['height']:
                raise FileSecurityError(
                    f"Image dimensions too large: {width}x{height}. "
                    f"Maximum allowed: {MAX_IMAGE_DIMENSIONS['width']}x{MAX_IMAGE_DIMENSIONS['height']}"
                )
            
            # Проверяем, что изображение не повреждено
            img.verify()
            
            return width, height
            
    except FileSecurityError:
        raise
    except Exception as e:
        logger.error(f"Image validation failed: {e}")
        raise FileSecurityError(f"Invalid or corrupted image: {e}")

def sanitize_filename(filename: str) -> str:
    """
    Санитизация имени файла для безопасного сохранения
    
    Args:
        filename: Исходное имя файла
    
    Returns:
        str: Безопасное имя файла
    """
    if not filename:
        return "unknown"
    
    # Удаляем путь, оставляем только имя файла
    filename = Path(filename).name
    
    # Заменяем опасные символы
    dangerous_chars = ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*', '\0']
    for char in dangerous_chars:
        filename = filename.replace(char, '_')
    
    # Ограничиваем длину
    if len(filename) > 100:
        name_part = filename[:95]
        ext_part = Path(filename).suffix[-5:]  # Сохраняем расширение
        filename = name_part + ext_part
    
    # Убираем начальные и конечные точки и пробелы
    filename = filename.strip('. ')
    
    if not filename:
        return "unknown"
    
    return filename

async def validate_upload_file(
    file: UploadFile, 
    file_type: str = 'image',
    check_content: bool = True
) -> dict:
    """
    Комплексная валидация загружаемого файла
    
    Args:
        file: Файл для валидации
        file_type: Тип файла (image, avatar, newsletter)
        check_content: Проверять ли содержимое файла (медленнее, но безопаснее)
    
    Returns:
        dict: Информация о валидированном файле
    
    Raises:
        HTTPException: Если валидация не прошла
    """
    try:
        # Базовые проверки
        if not file:
            raise FileSecurityError("No file provided")
        
        if not file.filename:
            raise FileSecurityError("Filename is required")
        
        # Валидация размера файла
        if file.size:
            validate_file_size(file.size, file_type=file_type)
        
        # Валидация расширения файла
        validate_file_extension(file.filename)
        
        # Валидация MIME типа
        if file.content_type:
            validate_mime_type(file.content_type)
        
        result = {
            'filename': sanitize_filename(file.filename),
            'content_type': file.content_type,
            'size': file.size,
            'is_safe': True
        }
        
        # Проверка содержимого файла (опционально)
        if check_content:
            file_content = await file.read()
            await file.seek(0)  # Возвращаем указатель в начало
            
            # Проверяем реальный тип файла
            real_mime_type = detect_file_type(file_content)
            validate_mime_type(real_mime_type)
            
            # Если MIME типы не совпадают, используем реальный
            if real_mime_type != file.content_type:
                logger.warning(
                    f"File MIME type mismatch: claimed '{file.content_type}', "
                    f"actual '{real_mime_type}'"
                )
                result['content_type'] = real_mime_type
            
            # Валидация изображения
            if real_mime_type.startswith('image/'):
                width, height = validate_image_content(file_content)
                result.update({
                    'width': width,
                    'height': height,
                    'pixels': width * height
                })
        
        logger.info(f"File validation passed: {result['filename']} ({result.get('width', '?')}x{result.get('height', '?')})")
        return result
        
    except FileSecurityError as e:
        logger.warning(f"File validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File validation error: {e}")
        raise HTTPException(status_code=500, detail="File validation failed")

def create_safe_file_path(base_dir: Path, filename: str, prefix: str = None) -> Path:
    """
    Создание безопасного пути для сохранения файла
    
    Args:
        base_dir: Базовая директория
        filename: Имя файла
        prefix: Префикс для имени файла
    
    Returns:
        Path: Безопасный путь к файлу
    """
    # Санитизируем имя файла
    safe_filename = sanitize_filename(filename)
    
    # Добавляем префикс если указан
    if prefix:
        name_part = Path(safe_filename).stem
        ext_part = Path(safe_filename).suffix
        safe_filename = f"{prefix}_{name_part}{ext_part}"
    
    # Проверяем, что базовая директория существует
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем полный путь
    file_path = base_dir / safe_filename
    
    # Проверяем, что путь не выходит за пределы базовой директории
    try:
        file_path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        raise FileSecurityError("Invalid file path detected")
    
    return file_path