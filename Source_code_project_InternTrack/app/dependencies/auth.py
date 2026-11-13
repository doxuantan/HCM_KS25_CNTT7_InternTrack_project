from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.database import get_db
from app.models.user import User, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
    except (InvalidTokenError, TypeError):
        raise unauthorized from None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
        raise unauthorized

    try:
        user_id = int(subject)
    except ValueError:
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )
    return user


def require_roles(*allowed_roles: UserRole | str) -> Callable[..., User]:
    if not allowed_roles:
        raise ValueError("At least one role must be specified.")

    normalized_roles = set()
    for role in allowed_roles:
        if isinstance(role, UserRole):
            normalized_roles.add(role.value)
        elif isinstance(role, str) and role.strip():
            normalized_roles.add(role.strip().upper())
        else:
            raise TypeError("Allowed roles must be non-empty strings or UserRole values.")

    def role_dependency(
        user: User = Depends(get_current_user),
    ) -> User:
        user_role = (
            user.role.value
            if isinstance(user.role, UserRole)
            else str(user.role).strip().upper()
        )
        if user_role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return user

    return role_dependency