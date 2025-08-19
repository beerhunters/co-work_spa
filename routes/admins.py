from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from werkzeug.security import generate_password_hash, check_password_hash

from dependencies import (
    get_db,
    verify_token,
    verify_token_with_permissions,
    require_super_admin,
)
from models.models import Admin, AdminPermission, AdminRole, Permission
from schemas.admin_schemas import (
    AdminCreate,
    AdminUpdate,
    AdminResponse,
    PasswordChange,
    AvailablePermissions,
    PermissionEnum,
)
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admins", tags=["admins"])


@router.get("/permissions", response_model=AvailablePermissions)
async def get_available_permissions(
    current_admin: Admin = Depends(require_super_admin),
):
    """Получение списка доступных разрешений"""
    return AvailablePermissions()


@router.get("", response_model=List[AdminResponse])
async def get_admins(
    db: Session = Depends(get_db), current_admin: Admin = Depends(require_super_admin)
):
    """Получение списка всех администраторов (только для супер админа)"""
    admins = db.query(Admin).all()

    result = []
    for admin in admins:
        admin_data = AdminResponse(
            id=admin.id,
            login=admin.login,
            role=admin.role,
            is_active=admin.is_active,
            created_at=admin.created_at,
            created_by=admin.created_by,
            creator_login=admin.creator.login if admin.creator else None,
            permissions=admin.get_permissions_list(),
        )
        result.append(admin_data)

    return result


@router.post("", response_model=AdminResponse)
async def create_admin(
    admin_data: AdminCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
):
    """Создание нового администратора (только для супер админа)"""

    # Проверяем, не существует ли админ с таким логином
    existing_admin = db.query(Admin).filter(Admin.login == admin_data.login).first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Администратор с таким логином уже существует",
        )

    # Создаем нового админа
    hashed_password = generate_password_hash(
        admin_data.password, method="pbkdf2:sha256"
    )

    new_admin = Admin(
        login=admin_data.login,
        password=hashed_password,
        role=AdminRole.MANAGER,
        is_active=True,
        created_by=current_admin.id,
    )

    db.add(new_admin)
    db.flush()  # Получаем ID нового админа

    # Добавляем разрешения
    for permission in admin_data.permissions:
        admin_permission = AdminPermission(
            admin_id=new_admin.id,
            permission=Permission(permission.value),
            granted=True,
            granted_by=current_admin.id,
        )
        db.add(admin_permission)

    db.commit()
    db.refresh(new_admin)

    logger.info(
        f"Создан новый администратор {admin_data.login} пользователем {current_admin.login}"
    )

    return AdminResponse(
        id=new_admin.id,
        login=new_admin.login,
        role=new_admin.role,
        is_active=new_admin.is_active,
        created_at=new_admin.created_at,
        created_by=new_admin.created_by,
        creator_login=current_admin.login,
        permissions=new_admin.get_permissions_list(),
    )


@router.get("/{admin_id}", response_model=AdminResponse)
async def get_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
):
    """Получение информации об администраторе"""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Администратор не найден"
        )

    return AdminResponse(
        id=admin.id,
        login=admin.login,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at,
        created_by=admin.created_by,
        creator_login=admin.creator.login if admin.creator else None,
        permissions=admin.get_permissions_list(),
    )


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    admin_data: AdminUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
):
    """Обновление администратора"""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Администратор не найден"
        )

    # Нельзя редактировать супер админа
    if admin.role == AdminRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя редактировать главного администратора",
        )

    # Проверяем уникальность логина
    if admin_data.login and admin_data.login != admin.login:
        existing = db.query(Admin).filter(Admin.login == admin_data.login).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Администратор с таким логином уже существует",
            )
        admin.login = admin_data.login

    # Обновляем пароль
    if admin_data.password:
        admin.password = generate_password_hash(
            admin_data.password, method="pbkdf2:sha256"
        )

    # Обновляем статус
    if admin_data.is_active is not None:
        admin.is_active = admin_data.is_active

    # Обновляем разрешения
    if admin_data.permissions is not None:
        # Удаляем старые разрешения
        db.query(AdminPermission).filter(AdminPermission.admin_id == admin_id).delete()

        # Добавляем новые разрешения
        for permission in admin_data.permissions:
            admin_permission = AdminPermission(
                admin_id=admin_id,
                permission=Permission(permission.value),
                granted=True,
                granted_by=current_admin.id,
            )
            db.add(admin_permission)

    db.commit()
    db.refresh(admin)

    logger.info(
        f"Обновлен администратор {admin.login} пользователем {current_admin.login}"
    )

    return AdminResponse(
        id=admin.id,
        login=admin.login,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at,
        created_by=admin.created_by,
        creator_login=admin.creator.login if admin.creator else None,
        permissions=admin.get_permissions_list(),
    )


@router.delete("/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_super_admin),
):
    """Удаление администратора"""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Администратор не найден"
        )

    # Нельзя удалять супер админа
    if admin.role == AdminRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя удалить главного администратора",
        )

    # Нельзя удалять самого себя
    if admin.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Нельзя удалить самого себя"
        )

    admin_login = admin.login
    db.delete(admin)
    db.commit()

    logger.info(
        f"Удален администратор {admin_login} пользователем {current_admin.login}"
    )

    return {"message": f"Администратор {admin_login} успешно удален"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(verify_token),
):
    """Смена пароля текущего администратора"""

    # Проверяем текущий пароль
    if not check_password_hash(current_admin.password, password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль"
        )

    # Устанавливаем новый пароль
    current_admin.password = generate_password_hash(
        password_data.new_password, method="pbkdf2:sha256"
    )
    db.commit()

    logger.info(f"Администратор {current_admin.login} сменил пароль")

    return {"message": "Пароль успешно изменен"}


@router.get("/current/profile", response_model=AdminResponse)
async def get_current_admin_profile(
    current_admin: Admin = Depends(verify_token), db: Session = Depends(get_db)
):
    """Получение профиля текущего администратора"""

    # Получаем свежую копию админа из базы данных
    # чтобы избежать DetachedInstanceError
    admin = db.query(Admin).filter(Admin.id == current_admin.id).first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found"
        )

    # Принудительно загружаем связанные данные
    permissions_list = admin.get_permissions_list()
    creator_login = None
    if admin.creator:
        creator_login = admin.creator.login

    return AdminResponse(
        id=admin.id,
        login=admin.login,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at,
        created_by=admin.created_by,
        creator_login=creator_login,
        permissions=permissions_list,
    )
