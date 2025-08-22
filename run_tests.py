#!/usr/bin/env python3
"""
Скрипт для запуска тестов проекта
"""
import sys
import subprocess
import os
from pathlib import Path

def run_command(cmd, description):
    """Выполнение команды с логированием"""
    print(f"\n🔧 {description}")
    print(f"Команда: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ {description} - успешно")
        if result.stdout.strip():
            print(result.stdout)
    else:
        print(f"❌ {description} - ошибка")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return False
    
    return True

def main():
    """Основная функция запуска тестов"""
    print("🧪 Запуск тестов проекта Coworking SPA")
    
    # Проверяем, что мы в правильной директории
    if not Path("main.py").exists():
        print("❌ Запустите скрипт из корневой директории проекта")
        sys.exit(1)
    
    # Устанавливаем переменные окружения для тестов
    os.environ.update({
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "LOG_TO_FILE": "false",
        "DEBUG": "false",
    })
    
    success = True
    
    # Запуск юнит-тестов
    if not run_command([
        sys.executable, "-m", "pytest", 
        "tests/unit/", 
        "-v", 
        "--tb=short",
        "-m", "not slow"
    ], "Юнит-тесты"):
        success = False
    
    # Запуск API тестов
    if not run_command([
        sys.executable, "-m", "pytest", 
        "tests/api/", 
        "-v", 
        "--tb=short",
        "-m", "not slow"
    ], "API тесты"):
        success = False
    
    # Запуск тестов безопасности
    if not run_command([
        sys.executable, "-m", "pytest", 
        "tests/", 
        "-v", 
        "--tb=short",
        "-m", "security"
    ], "Тесты безопасности"):
        success = False
    
    # Запуск всех быстрых тестов с покрытием (если pytest-cov установлен)
    try:
        import pytest_cov
        if not run_command([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-fail-under=50",
            "-m", "not slow"
        ], "Тесты с покрытием кода"):
            success = False
    except ImportError:
        print("⚠️  pytest-cov не установлен, пропускаем анализ покрытия")
    
    if success:
        print("\n🎉 Все тесты прошли успешно!")
        return 0
    else:
        print("\n💥 Некоторые тесты не прошли")
        return 1

if __name__ == "__main__":
    sys.exit(main())