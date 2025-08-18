import os
import time
import hashlib
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.responses import FileResponse

from models.models import User, DatabaseManager
from dependencies import get_db, verify_token, get_bot
from schemas.user_schemas import UserBase, UserUpdate, UserCreate
from config import AVATARS_DIR, MOSCOW_TZ
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["users"])
# router = APIRouter(tags=["users"])


@router.get("", response_model=List[UserBase])
async def get_users(_: str = Depends(verify_token)):
    """Получение списка всех пользователей."""

    def _get_users(session):
        users = session.query(User).order_by(User.first_join_time.desc()).all()
        users_data = []
        for user in users:
            user_dict = {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "username": user.username,
                "successful_bookings": user.successful_bookings or 0,
                "language_code": user.language_code or "ru",
                "invited_count": user.invited_count or 0,
                "reg_date": user.reg_date,
                "first_join_time": user.first_join_time,
                "agreed_to_terms": user.agreed_to_terms or False,
                "avatar": user.avatar,
                "referrer_id": user.referrer_id,
            }
            users_data.append(user_dict)
        return users_data

    try:
        return DatabaseManager.safe_execute(_get_users)
    except Exception as e:
        logger.error(f"Ошибка в get_users: {e}")
        raise HTTPException(status_code=500, detail="Ошибка получения пользователей")


@router.get("/{user_id}", response_model=UserBase)
async def get_user(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Получение пользователя по ID."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/telegram/{telegram_id}")
async def get_user_by_telegram_id(telegram_id: int, db: Session = Depends(get_db)):
    """Получение пользователя по Telegram ID. Используется ботом."""
    user = db.query(User).filter_by(telegram_id=telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    is_complete = all([user.full_name, user.phone, user.email])

    user_data = {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "full_name": user.full_name,
        "phone": user.phone,
        "email": user.email,
        "username": user.username,
        "successful_bookings": user.successful_bookings,
        "language_code": user.language_code,
        "invited_count": user.invited_count,
        "reg_date": user.reg_date,
        "first_join_time": user.first_join_time,
        "agreed_to_terms": user.agreed_to_terms,
        "avatar": user.avatar,
        "referrer_id": user.referrer_id,
        "is_complete": is_complete,
    }

    return user_data


@router.put("/telegram/{telegram_id}")
async def update_user_by_telegram_id(telegram_id: int, user_data: UserUpdate):
    """Обновление пользователя по telegram_id."""

    def _update_user(session):
        user = session.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_dict = user_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(user, field):
                setattr(user, field, value)

        session.flush()
        return {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "email": user.email,
            "username": user.username,
            "successful_bookings": user.successful_bookings,
            "language_code": user.language_code,
            "invited_count": user.invited_count,
            "reg_date": user.reg_date,
            "first_join_time": user.first_join_time,
            "agreed_to_terms": user.agreed_to_terms,
            "avatar": user.avatar,
            "referrer_id": user.referrer_id,
        }

    try:
        return DatabaseManager.safe_execute(_update_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        raise HTTPException(
            status_code=500, detail=f"Ошибка обновления пользователя: {str(e)}"
        )


@router.post("/check_and_add")
async def check_and_add_user(
    telegram_id: int,
    username: Optional[str] = None,
    language_code: str = "ru",
    referrer_id: Optional[int] = None,
):
    """Проверка и добавление пользователя в БД с улучшенной обработкой."""

    def _check_and_add_user(session):
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        is_new = False

        if not user:
            from datetime import datetime

            user = User(
                telegram_id=telegram_id,
                username=username if username else None,
                language_code=language_code,
                first_join_time=datetime.now(MOSCOW_TZ),
                referrer_id=referrer_id if referrer_id else None,
                agreed_to_terms=False,
                successful_bookings=0,
                invited_count=0,
            )
            session.add(user)
            session.flush()
            is_new = True

            if referrer_id:
                referrer = (
                    session.query(User).filter_by(telegram_id=referrer_id).first()
                )
                if referrer:
                    referrer.invited_count += 1
        else:
            if username and user.username != username:
                user.username = username

        is_complete = all(
            [user.full_name, user.phone, user.email, user.agreed_to_terms]
        )

        return {
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "username": user.username,
                "successful_bookings": user.successful_bookings,
                "language_code": user.language_code,
                "invited_count": user.invited_count,
                "reg_date": user.reg_date,
                "first_join_time": user.first_join_time,
                "agreed_to_terms": user.agreed_to_terms,
                "avatar": user.avatar,
                "referrer_id": user.referrer_id,
            },
            "is_new": is_new,
            "is_complete": is_complete,
        }

    try:
        return DatabaseManager.safe_execute(_check_and_add_user)
    except Exception as e:
        logger.error(f"Ошибка в check_and_add_user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{user_identifier}")
async def update_user(
    user_identifier: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Обновление пользователя по ID или telegram_id."""

    def _update_user(session):
        user = None

        if user_identifier.isdigit():
            user_id = int(user_identifier)
            user = session.query(User).filter(User.id == user_id).first()

        if not user and user_identifier.isdigit():
            telegram_id = int(user_identifier)
            user = session.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        update_data = user_data.dict(exclude_unset=True)

        if "reg_date" in update_data and isinstance(update_data["reg_date"], str):
            try:
                from datetime import datetime

                update_data["reg_date"] = datetime.fromisoformat(
                    update_data["reg_date"]
                )
            except ValueError:
                del update_data["reg_date"]

        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        session.flush()
        return user

    try:
        return DatabaseManager.safe_execute(_update_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обновления пользователя: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{user_id}/avatar")
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(verify_token),
):
    """Загрузка аватара пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.avatar:
        old_avatar_path = AVATARS_DIR / user.avatar
        if old_avatar_path.exists():
            try:
                old_avatar_path.unlink()
                logger.info(f"Удален старый аватар: {user.avatar}")
            except Exception as e:
                logger.warning(f"Не удалось удалить старый аватар: {e}")

    avatar_filename = f"{user.telegram_id}.jpg"
    avatar_path = AVATARS_DIR / avatar_filename

    contents = await file.read()
    with open(avatar_path, "wb") as f:
        f.write(contents)

    user.avatar = avatar_filename
    db.commit()

    logger.info(f"Загружен новый аватар для пользователя {user_id}: {avatar_filename}")

    timestamp = int(time.time() * 1000)
    return {
        "message": "Avatar uploaded successfully",
        "filename": avatar_filename,
        "avatar_url": f"/avatars/{avatar_filename}?v={timestamp}",
        "version": timestamp,
    }


@router.delete("/{user_id}/avatar")
async def delete_avatar(
    user_id: int, db: Session = Depends(get_db), _: str = Depends(verify_token)
):
    """Удаление аватара пользователя."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = False

    if user.avatar:
        avatar_path = AVATARS_DIR / user.avatar
        if avatar_path.exists():
            try:
                avatar_path.unlink()
                deleted = True
                logger.info(f"Удален аватар: {user.avatar}")
            except Exception as e:
                logger.warning(f"Не удалось удалить аватар {user.avatar}: {e}")
        user.avatar = None
        db.commit()

    standard_path = AVATARS_DIR / f"{user.telegram_id}.jpg"
    if standard_path.exists():
        try:
            standard_path.unlink()
            deleted = True
            logger.info(f"Удален файл аватара: {standard_path.name}")
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {standard_path.name}: {e}")

    return {"deleted": deleted}


@router.get("/avatars/{filename}")
async def get_avatar(filename: str):
    """Получение аватара по имени файла."""
    file_path = AVATARS_DIR / filename

    if not file_path.exists():
        placeholder_path = AVATARS_DIR / "placeholder_avatar.png"
        if placeholder_path.exists():
            return FileResponse(
                placeholder_path,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        raise HTTPException(status_code=404, detail="Avatar not found")

    mtime = file_path.stat().st_mtime
    last_modified = f"{mtime}"
    etag_base = f"{filename}-{mtime}"
    etag = hashlib.md5(etag_base.encode()).hexdigest()

    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, proxy-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "ETag": f'"{etag}"',
            "Last-Modified": last_modified,
            "Surrogate-Control": "no-store",
        },
    )


@router.post("/{user_id}/download-telegram-avatar")
async def download_telegram_avatar(
    user_id: int,
    _: str = Depends(verify_token),
):
    """Скачивание аватара пользователя из Telegram."""
    try:

        def _get_user_data(session):
            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            if not user.telegram_id:
                raise HTTPException(status_code=400, detail="User has no Telegram ID")

            if user.avatar:
                old_avatar_path = AVATARS_DIR / user.avatar
                if old_avatar_path.exists():
                    try:
                        old_avatar_path.unlink()
                        logger.info(f"Удален старый аватар: {user.avatar}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления старого аватара: {e}")

            return {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "full_name": user.full_name,
            }

        user_data = DatabaseManager.safe_execute(_get_user_data)
        bot = get_bot()

        if not bot:
            raise HTTPException(status_code=503, detail="Bot not available")

        logger.info(
            f"Попытка скачать аватар для пользователя {user_data['telegram_id']}"
        )

        profile_photos = await bot.get_user_profile_photos(
            user_id=user_data["telegram_id"], limit=1
        )

        if not profile_photos.photos:
            logger.info(f"У пользователя {user_data['telegram_id']} нет фото профиля")
            raise HTTPException(
                status_code=404,
                detail="User has no profile photo or photo is not accessible",
            )

        photo = profile_photos.photos[0][-1]
        file = await bot.get_file(photo.file_id)

        avatar_filename = f"{user_data['telegram_id']}.jpg"
        avatar_path = AVATARS_DIR / avatar_filename

        AVATARS_DIR.mkdir(parents=True, exist_ok=True)

        if avatar_path.exists():
            try:
                avatar_path.unlink()
                logger.info(f"Удален существующий аватар: {avatar_filename}")
            except Exception as e:
                logger.warning(f"Не удалось удалить существующий аватар: {e}")

        await bot.download_file(file.file_path, destination=avatar_path)
        logger.info(f"Аватар сохранен: {avatar_path}")

        def _update_avatar(session):
            user_obj = session.query(User).filter(User.id == user_id).first()
            if user_obj:
                user_obj.avatar = avatar_filename
                session.commit()
                return {
                    "id": user_obj.id,
                    "telegram_id": user_obj.telegram_id,
                    "avatar": user_obj.avatar,
                }
            return None

        updated_user_data = DatabaseManager.safe_execute(_update_avatar)

        if not updated_user_data:
            raise HTTPException(status_code=404, detail="Failed to update user")

        timestamp = int(time.time() * 1000)
        return {
            "message": "Avatar downloaded successfully",
            "avatar_filename": avatar_filename,
            "avatar_url": f"/avatars/{avatar_filename}?v={timestamp}",
            "version": timestamp,
            "user_id": updated_user_data["id"],
            "telegram_id": updated_user_data["telegram_id"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при скачивании аватара пользователя {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error downloading avatar: {str(e)}"
        )


@router.delete("/{user_id}")
async def delete_user(user_id: int, _: str = Depends(verify_token)):
    """Удаление пользователя и всех связанных данных."""

    def _delete_user(session):
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_name = user.full_name or f"Пользователь #{user.telegram_id}"
        telegram_id = user.telegram_id

        if user.avatar:
            try:
                avatar_path = AVATARS_DIR / user.avatar
                if avatar_path.exists():
                    avatar_path.unlink()
                    logger.info(f"Удален аватар: {avatar_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить аватар: {e}")

        session.delete(user)

        logger.info(
            f"Удален пользователь: {user_name} (ID: {user_id}, Telegram ID: {telegram_id})"
        )

        return {
            "message": f"Пользователь {user_name} успешно удален",
            "deleted_user": {
                "id": user_id,
                "telegram_id": telegram_id,
                "full_name": user_name,
            },
        }

    try:
        return DatabaseManager.safe_execute(_delete_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления пользователя")
