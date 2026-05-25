"""
TrustHire AI — Authentication & RBAC middleware.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models import User
from ..security import decode_jwt

bearer_scheme = HTTPBearer(auto_error=False)

# Role hierarchy — higher index = more permissions
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {
        "candidates:read",
        "verifications:read",
        "compliance:read",
        "reports:read",
    },
    "recruiter": {
        "candidates:read", "candidates:write",
        "verifications:read", "verifications:write",
        "reports:read",
    },
    "compliance_reviewer": {
        "candidates:read",
        "verifications:read",
        "compliance:read", "compliance:write",
        "reports:read",
    },
    "org_admin": {
        "candidates:read", "candidates:write", "candidates:delete",
        "verifications:read", "verifications:write",
        "compliance:read", "compliance:write",
        "reports:read", "reports:write",
        "admin:read",
        "members:read", "members:write",
    },
    "super_admin": {"*"},
}


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate Bearer JWT and return the authenticated User.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_jwt(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("userId") or payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user: User | None = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Stash user on request state for audit middleware
    request.state.user_id = str(user.id)
    request.state.org_id = str(user.organization_id) if user.organization_id else None

    return user


def require_roles(*roles: str):
    """
    Dependency factory — raises 403 if the current user's role is not in `roles`.

    Usage:
        @router.delete("/x", dependencies=[Depends(require_roles("org_admin", "super_admin"))])
    """
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles and current_user.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}",
            )
        return current_user

    return _checker


def has_permission(user: User, permission: str) -> bool:
    """Check whether a user has a specific permission string."""
    perms = ROLE_PERMISSIONS.get(user.role, set())
    return "*" in perms or permission in perms


def require_permission(permission: str):
    """Dependency that checks a fine-grained permission string."""
    async def _checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return current_user

    return _checker
