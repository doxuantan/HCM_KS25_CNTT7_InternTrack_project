from collections.abc import Callable

from app.dependencies.auth import require_roles
from app.models.user import User, UserRole


def require_role(*allowed_roles: UserRole | str) -> Callable[..., User]:
    return require_roles(*allowed_roles)