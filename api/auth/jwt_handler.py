from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import jwt                        # PyJWT  (pip install PyJWT)
import os
from fastapi import HTTPException, status

# ── Configuration ────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15   # short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS   = 7    # long-lived refresh token

# 10 roles from the spec
VALID_ROLES = {
    "executive", "dsi", "cdg_it", "manager_infra", "manager_rssi",
    "manager_sd", "manager_apps", "manager_facility", "operationnel", "auditeur",
}


def _utcnow() -> datetime:
    """Timezone-aware UTC now (avoids DeprecationWarning in Python 3.12+)."""
    return datetime.now(timezone.utc)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a short-lived JWT access token.

    Args:
        data: Must contain at least "sub" (username) and "role".
        expires_delta: Override the default expiry.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = _utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """
    Create a long-lived JWT refresh token (7 days).

    Args:
        data: Must contain at least "sub" and "role".

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Dict:
    """
    Verify and decode a JWT token (access or refresh).

    Args:
        token: Raw JWT string.

    Returns:
        Dict with "username" and "role".

    Raises:
        HTTPException 401 if token is invalid/expired.
        HTTPException 403 if the role embedded in the token is unknown.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role:     str = payload.get("role")

        if not username or not role:
            raise credentials_exception

        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token contains unknown role: '{role}'",
            )

        return {"username": username, "role": role}

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception


def get_role_from_token(token: str) -> str:
    """Convenience helper — extract role from a verified token."""
    return verify_token(token)["role"]