from fastapi import Depends, HTTPException, status

from app.api.deps.auth import get_current_user
from app.db.models import User

ADMIN_PRIVILEGES_REQUIRED_ERROR_CODE = "adminPrivilegesRequired"


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ADMIN_PRIVILEGES_REQUIRED_ERROR_CODE,
        )
    return current_user
