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
    if not isinstance(subject, str) or not subject.isdecimal():
        raise unauthorized

    user = db.get(User, int(subject))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    if not allowed_roles:
        raise ValueError("At least one role must be specified.")
    if any(not isinstance(role, UserRole) for role in allowed_roles):
        raise TypeError("Allowed roles must be UserRole values.")

    def role_dependency(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return user

    return role_dependency