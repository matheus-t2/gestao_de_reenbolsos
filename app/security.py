import hashlib
import hmac
import os
import secrets
import warnings
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User, utcnow

_secret = os.getenv("NEXUS_JWT_SECRET")
if not _secret:
    warnings.warn("NEXUS_JWT_SECRET não definido: usando segredo efêmero (apenas desenvolvimento).")
    _secret = secrets.token_urlsafe(48)
SECRET = _secret
ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("NEXUS_TOKEN_MINUTES", "30"))
PBKDF2_ITER = int(os.getenv("NEXUS_PBKDF2_ITER", "310000"))
MAX_ATTEMPTS, LOCK_MINUTES = 5, 15


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITER)
    return f"pbkdf2${PBKDF2_ITER}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, it, salt, dk = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), dk)
    except Exception:
        return False


DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_token(user: User) -> str:
    now = utcnow()
    payload = {"sub": str(user.id), "tv": user.token_version, "iat": now, "exp": now + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
_401 = HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autenticado.", headers={"WWW-Authenticate": "Bearer"})


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGORITHM], options={"require": ["exp", "sub", "tv"]})
        user = db.get(User, int(data["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise _401
    if user is None or not user.active or user.token_version != data["tv"]:  # revogação/desativação: efeito imediato
        raise _401
    return user


def require_roles(*roles: Role):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Perfil sem permissão para esta operação.")
        return user
    return dep
