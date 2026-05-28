# api/routers/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from api.auth.jwt_handler import create_access_token, create_refresh_token, verify_token
from api.auth.dependencies import get_current_user
from datetime import datetime, timezone
import logging

router = APIRouter(prefix="/api/auth")
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900
    role: str = ""        # FIX: ajouté — useAuth.js lit ce champ
    username: str = ""    # FIX: ajouté — useAuth.js lit ce champ


# TODO production: remplacer par requête Gold.users avec bcrypt
# SELECT Username, Password_Hash, Role FROM Gold.users WHERE Username=:u AND Is_Active=1
DEMO_USERS = {
    "admin":     {"password": "admin",     "role": "dsi"},
    "executive": {"password": "executive", "role": "executive"},
    "manager":   {"password": "manager",   "role": "manager_infra"},
    "rssi":      {"password": "rssi",      "role": "manager_rssi"},
    "sd":        {"password": "sd",        "role": "manager_sd"},
    "apps":      {"password": "apps",      "role": "manager_apps"},
    "facility":  {"password": "facility",  "role": "manager_facility"},
    "cdg":       {"password": "cdg",       "role": "cdg_it"},
    "ops":       {"password": "ops",       "role": "operationnel"},
    "demo":      {"password": "demo",      "role": "auditeur"},
}


@router.post("/login", response_model=TokenResponse, tags=["auth"])
async def login(request: LoginRequest):
    """Login — retourne access_token (15 min) + refresh_token (7 jours) + role + username."""
    user_data = DEMO_USERS.get(request.username)

    if not user_data or user_data["password"] != request.password:
        logger.warning(f"❌ Tentative de connexion échouée: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides"
        )

    token_data = {"sub": request.username, "role": user_data["role"]}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    logger.info(f"✅ Connexion: {request.username} ({user_data['role']})")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        role=user_data["role"],
        username=request.username
    )


@router.post("/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_token(request: RefreshTokenRequest):
    """Renouvelle l'access token via le refresh token (7 jours)."""
    try:
        payload = verify_token(request.refresh_token)
        username = payload.get("username")
        role = payload.get("role")

        if not username or not role:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Payload du refresh token invalide"
            )

        new_access_token = create_access_token(data={"sub": username, "role": role})
        logger.info(f"✅ Token renouvelé pour: {username}")

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=request.refresh_token,
            role=role,
            username=username
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Échec du refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalide"
        )


@router.get("/me", tags=["auth"])
async def get_me(user: dict = Depends(get_current_user)):
    """
    Profil de l'utilisateur connecté depuis le JWT.
    Appelé par useAuth.js au rechargement de page pour vérifier la session.
    """
    return {
        "username": user.get("username"),
        "role": user.get("role"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }