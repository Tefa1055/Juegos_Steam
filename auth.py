# auth.py
from datetime import datetime, timedelta
from typing import Optional
import os
import hashlib  # ⬅️ nuevo

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlmodel import Session
from models import User  # ✅ usa el modelo directo; evita import de operations en top-level

# --- Security Settings ---
SECRET_KEY = os.environ.get("SECRET_KEY", "Jeffthekiller789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _short(password: str) -> str:
    """
    Pre-hash con SHA-256 para evitar el límite de 72 bytes de bcrypt.
    Devuelve un hex de 64 chars (siempre <72 bytes), estable y seguro.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(_short(plain_password), hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(_short(password))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ✅ Import perezoso para romper el ciclo auth <-> operations
def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    import operations  # <--- se importa aquí adentro, no arriba
    user = operations.get_user_by_username(session=session, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_current_active_user(session: Session, token: str) -> Optional[User]:
    import operations  # <--- también aquí adentro
    credentials_exception = JWTError("Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception

    user = operations.get_user_by_username(session=session, username=username)
    if user is None:
        raise credentials_exception
    return user
