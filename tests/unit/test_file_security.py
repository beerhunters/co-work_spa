"""
Юнит-тесты для модуля безопасности файлов
"""
import pytest
import io
from unittest.mock import AsyncMock, patch
from PIL import Image

from utils.file_security import (
    validate_file_extension,
    validate_mime_type,
    validate_file_size,
    detect_file_type,
    validate_image_content,
    sanitize_filename,
    FileSecurityError,
    validate_upload_file,
    create_safe_file_path
)


class TestFileValidation:
    """Тесты валидации файлов"""
    
    def test_validate_file_extension_valid(self):
        """Тест валидного расширения файла"""
        assert validate_file_extension("image.jpg") == True
        assert validate_file_extension("photo.png") == True
        assert validate_file_extension("picture.jpeg") == True
        assert validate_file_extension("file.WEBP") == True  # case insensitive
    
    def test_validate_file_extension_invalid(self):
        """Тест невалидного расширения файла"""
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_extension("file.txt")
        
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_extension("script.exe")
        
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_file_extension("document.pdf")
    
    def test_validate_file_extension_empty(self):
        """Тест пустого имени файла"""
        with pytest.raises(FileSecurityError, match="empty"):
            validate_file_extension("")
        
        with pytest.raises(FileSecurityError, match="empty"):
            validate_file_extension(None)
    
    def test_validate_mime_type_valid(self):
        """Тест валидных MIME типов"""
        assert validate_mime_type("image/jpeg") == True
        assert validate_mime_type("image/png") == True
        assert validate_mime_type("image/gif") == True
        assert validate_mime_type("image/webp") == True
    
    def test_validate_mime_type_invalid(self):
        """Тест невалидных MIME типов"""
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_mime_type("text/plain")
        
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_mime_type("application/pdf")
        
        with pytest.raises(FileSecurityError, match="not allowed"):
            validate_mime_type("video/mp4")
    
    def test_validate_file_size_valid(self):
        """Тест валидных размеров файлов"""
        assert validate_file_size(1024) == True  # 1KB
        assert validate_file_size(5 * 1024 * 1024) == True  # 5MB
        assert validate_file_size(10 * 1024 * 1024 - 1) == True  # Just under 10MB
    
    def test_validate_file_size_too_large(self):
        """Тест слишком больших файлов"""
        with pytest.raises(FileSecurityError, match="too large"):
            validate_file_size(11 * 1024 * 1024)  # 11MB
        
        with pytest.raises(FileSecurityError, match="too large"):
            validate_file_size(50 * 1024 * 1024, file_type='image')
    
    def test_validate_file_size_zero(self):
        """Тест нулевого размера файла"""
        with pytest.raises(FileSecurityError, match="greater than 0"):
            validate_file_size(0)
        
        with pytest.raises(FileSecurityError, match="greater than 0"):
            validate_file_size(-1)


class TestFileTypeDetection:
    """Тесты определения типов файлов"""
    
    def test_detect_jpeg(self):
        """Тест определения JPEG файла"""
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF'
        assert detect_file_type(jpeg_header) == 'image/jpeg'
    
    def test_detect_png(self):
        """Тест определения PNG файла"""
        png_header = b'\x89PNG\r\n\x1a\n'
        assert detect_file_type(png_header) == 'image/png'
    
    def test_detect_gif(self):
        """Тест определения GIF файла"""
        gif87_header = b'GIF87a'
        gif89_header = b'GIF89a'
        assert detect_file_type(gif87_header) == 'image/gif'
        assert detect_file_type(gif89_header) == 'image/gif'
    
    def test_detect_webp(self):
        """Тест определения WEBP файла"""
        webp_header = b'RIFF\x00\x00\x00\x00WEBP'
        assert detect_file_type(webp_header) == 'image/webp'
    
    def test_detect_bmp(self):
        """Тест определения BMP файла"""
        bmp_header = b'BM'
        assert detect_file_type(bmp_header) == 'image/bmp'
    
    def test_detect_unknown_type(self):
        """Тест неизвестного типа файла"""
        with pytest.raises(FileSecurityError, match="Unknown or invalid file type"):
            detect_file_type(b'unknown content')


class TestImageValidation:
    """Тесты валидации изображений"""
    
    def test_validate_small_image(self):
        """Тест валидации малого изображения"""
        # Создаем малое тестовое изображение
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        width, height = validate_image_content(img_bytes.getvalue())
        assert width == 100
        assert height == 100
    
    def test_validate_large_image_dimensions(self):
        """Тест изображения со слишком большими размерами"""
        # Создаем изображение больше максимальных размеров
        img = Image.new('RGB', (5000, 5000), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        with pytest.raises(FileSecurityError, match="dimensions too large"):
            validate_image_content(img_bytes.getvalue())
    
    def test_validate_corrupted_image(self):
        """Тест поврежденного изображения"""
        corrupted_data = b'\xff\xd8\xff\xe0corrupted_jpeg_data'
        
        with pytest.raises(FileSecurityError, match="Invalid or corrupted"):
            validate_image_content(corrupted_data)


class TestFilenameSanitization:
    """Тесты санитизации имен файлов"""
    
    def test_sanitize_normal_filename(self):
        """Тест нормального имени файла"""
        assert sanitize_filename("image.jpg") == "image.jpg"
        assert sanitize_filename("my_photo.png") == "my_photo.png"
    
    def test_sanitize_dangerous_characters(self):
        """Тест опасных символов в имени файла"""
        assert sanitize_filename("../../../etc/passwd") == ".._.._.._etc_passwd"
        assert sanitize_filename("file<>:\"|?*.txt") == "file_________.txt"
        assert sanitize_filename("con.txt") == "con.txt"  # Windows reserved names
    
    def test_sanitize_long_filename(self):
        """Тест слишком длинного имени файла"""
        long_name = "a" * 200 + ".jpg"
        result = sanitize_filename(long_name)
        assert len(result) <= 100
        assert result.endswith(".jpg")
    
    def test_sanitize_empty_filename(self):
        """Тест пустого имени файла"""
        assert sanitize_filename("") == "unknown"
        assert sanitize_filename(None) == "unknown"
        assert sanitize_filename("   ") == "unknown"
    
    def test_sanitize_only_dots(self):
        """Тест имени файла только из точек"""
        assert sanitize_filename("...") == "unknown"
        assert sanitize_filename(".") == "unknown"


class TestUploadFileValidation:
    """Тесты комплексной валидации загружаемых файлов"""
    
    @pytest.mark.asyncio
    async def test_valid_upload_file(self):
        """Тест валидного загружаемого файла"""
        # Создаем мок UploadFile
        mock_file = AsyncMock()
        mock_file.filename = "test.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.size = 1024
        
        # Создаем валидное JPEG изображение
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        jpeg_content = img_bytes.getvalue()
        
        mock_file.read.return_value = jpeg_content
        mock_file.seek = AsyncMock()
        
        result = await validate_upload_file(mock_file)
        
        assert result['is_safe'] == True
        assert result['filename'] == "test.jpg"
        assert result['content_type'] == "image/jpeg"
        assert result['width'] == 100
        assert result['height'] == 100
    
    @pytest.mark.asyncio
    async def test_invalid_upload_file_type(self):
        """Тест загрузки файла неверного типа"""
        from fastapi import HTTPException
        
        mock_file = AsyncMock()
        mock_file.filename = "test.txt"
        mock_file.content_type = "text/plain"
        mock_file.size = 100
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_file(mock_file)
        
        assert exc_info.value.status_code == 400
    
    @pytest.mark.asyncio
    async def test_upload_file_too_large(self):
        """Тест загрузки слишком большого файла"""
        from fastapi import HTTPException
        
        mock_file = AsyncMock()
        mock_file.filename = "large.jpg"
        mock_file.content_type = "image/jpeg"
        mock_file.size = 11 * 1024 * 1024  # 11MB
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_upload_file(mock_file)
        
        assert exc_info.value.status_code == 400
        assert "too large" in str(exc_info.value.detail).lower()


class TestSafeFilePath:
    """Тесты создания безопасных путей к файлам"""
    
    def test_create_safe_path_normal(self, tmp_path):
        """Тест создания нормального безопасного пути"""
        result = create_safe_file_path(tmp_path, "image.jpg")
        
        assert result.parent == tmp_path
        assert result.name == "image.jpg"
        assert tmp_path.exists()
    
    def test_create_safe_path_with_prefix(self, tmp_path):
        """Тест создания пути с префиксом"""
        result = create_safe_file_path(tmp_path, "image.jpg", prefix="user123")
        
        assert result.name == "user123_image.jpg"
    
    def test_create_safe_path_dangerous_filename(self, tmp_path):
        """Тест опасного имени файла"""
        result = create_safe_file_path(tmp_path, "../../../etc/passwd")
        
        assert result.parent == tmp_path
        assert "passwd" in result.name
        assert ".." not in result.name
    
    def test_create_safe_path_traversal_attempt(self, tmp_path):
        """Тест попытки обхода директории"""
        with pytest.raises(FileSecurityError, match="Invalid file path"):
            # Создаем файл, который попытается выйти за пределы базовой директории
            malicious_path = tmp_path / ".." / "malicious.txt"
            create_safe_file_path(tmp_path, str(malicious_path))