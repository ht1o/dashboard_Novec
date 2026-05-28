from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from api.auth.jwt_handler import verify_token

# FIX: The correct class is HTTPAuthorizationCredentials, NOT HTTPAuthCredentials.
security = HTTPBearer()

# Role-based access control matrix
ROLE_PAGES: dict[str, list[str]] = {
    "executive":        ["executive"],
    "dsi":              ["executive", "finance", "infra", "itsm", "cyber",
                         "apps", "itam", "parc_auto", "maintenance"],
    "cdg_it":           ["executive", "finance"],
    "manager_infra":    ["infra", "itam"],
    "manager_rssi":     ["cyber", "infra"],
    "manager_sd":       ["itsm"],
    "manager_apps":     ["apps"],
    "manager_facility": ["parc_auto", "maintenance"],
    "operationnel":     ["alerts"],
    "auditeur":         ["*"],   # read-only access to everything
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extract and verify the current user from the Bearer token.

    Returns:
        {"username": str, "role": str}

    Raises:
        HTTPException 401 if the token is missing or invalid.
    """
    return verify_token(credentials.credentials)


# ── Page-level access ────────────────────────────────────────────────────────

def check_page_access(required_page: str):
    """
    Dependency factory — raises 403 if the caller's role cannot access `required_page`.

    Usage:
        @router.get("/something")
        async def endpoint(user: dict = Depends(check_page_access("infra"))):
            ...
    """
    # FIX: factory functions used in Depends() must be synchronous (not async)
    # because FastAPI resolves them at import time for OpenAPI schema generation.
    # The inner dependency is async — that's fine.
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        role          = user.get("role", "")
        allowed_pages = ROLE_PAGES.get(role, [])

        if "*" in allowed_pages:          # auditeur — full read-only
            return user

        if required_page not in allowed_pages:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not allowed to access '{required_page}'",
            )
        return user

    return dependency


def check_role(required_role: str):
    """
    Dependency factory — raises 403 unless the caller has exactly `required_role`.
    """
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role", "")
        if role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires role '{required_role}', got '{role}'",
            )
        return user

    return dependency


def check_role_in(required_roles: list[str]):
    """
    Dependency factory — raises 403 unless the caller's role is in `required_roles`.
    """
    def dependency(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role", "")
        if role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not in the allowed list: {required_roles}",
            )
        return user

    return dependency