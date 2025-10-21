# auth.py
from datetime import datetime, timedelta
from typing import Optional
import os
import hashlib

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlmodel import Session
from models import User  # sólo el modelo, sin imports cruzados

# --- Config JWT ---
SECRET_KEY = os.environ.get("SECRET_KEY", "Jeffthekiller789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Password hashing (bcrypt con pre-hash SHA-256 para >72 bytes) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _short(password: str) -> str:
    """Pre-hash con SHA-256 para evitar límite de 72 bytes de bcrypt."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_short(plain_password), hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(_short(password))

# --- Tokens ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    """Devuelve el payload si es válido; None si no lo es."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# --- Helpers de autenticación (con import perezoso para evitar ciclos) ---
def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    import operations  # lazy import para no crear ciclo
    user = operations.get_user_by_username(session=session, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_current_active_user(session: Session, token: str) -> Optional[User]:
    import operations
    payload = decode_access_token(token)
    if not payload:
        return None
    username = payload.get("sub")
    if not username:
        return None
    return operations.get_user_by_username(session=session, username=username)
