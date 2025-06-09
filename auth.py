# auth.py
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext # Para hashear contraseñas
from jose import JWTError, jwt # Para JWT (JSON Web Tokens)

# --- Configuración de Seguridad ---
# Necesitas una clave secreta para firmar tus JWTs.
# ¡IMPORTANTE! En un entorno de producción, esto DEBE ser una variable de entorno segura,
# NO un string codificado aquí.
SECRET_KEY = "tu-super-secreto-ultra-seguro-y-largo" # ¡Cámbialo a algo más complejo en producción!
ALGORITHM = "HS256" # Algoritmo de encriptación para el JWT
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Tiempo de expiración del token de acceso

# Contexto para hashear y verificar contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Funciones de Contraseña ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con una contraseña hasheada."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera el hash de una contraseña en texto plano."""
    return pwd_context.hash(password)

# --- Funciones de JWT ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un nuevo token de acceso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica y valida un token de acceso JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None # Token inválido o expirado