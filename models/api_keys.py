"""
Модели для управления API ключами
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from datetime import datetime, timedelta

# Import the Base from the main models file
from models.models import Base

class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)  # Хешированный ключ
    scopes = Column(JSON, nullable=False, default=list)  # Области доступа
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ip_whitelist = Column(JSON, nullable=False, default=list)  # IP адреса для доступа
    rate_limit = Column(Integer, default=1000, nullable=False)  # Лимит запросов в час
    request_count = Column(Integer, default=0, nullable=False)  # Общее количество запросов
    last_used_at = Column(DateTime, nullable=True)
    created_by = Column(String(255), nullable=False)  # Кто создал ключ

class ApiKeyAuditLog(Base):
    __tablename__ = "api_key_audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False, index=True)  # create, update, delete, activate, deactivate
    api_key_name = Column(String(255), nullable=True)
    api_key_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=False)  # Поддержка IPv6
    success = Column(Boolean, nullable=False, default=True)
    details = Column(JSON, nullable=True)  # Дополнительные детали операции

class ApiKeyUsage(Base):
    __tablename__ = "api_key_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Integer, nullable=False)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(String(500), nullable=True)