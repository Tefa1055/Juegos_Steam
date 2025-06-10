# auth.py
from datetime import datetime, timedelta
from typing import Optional
import os

from passlib.context import CryptContext
from jose import JWTError, jwt
from sqlmodel import Session
import operations # Import operations to fetch user

# --- Security Settings ---
SECRET_KEY = os.environ.get("SECRET_KEY", "Jeffthekiller789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Password Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if a plain text password matches a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates a hash for a plain text password."""
    return pwd_context.hash(password)

# --- JWT Functions ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None # Invalid or expired token

# --- User Authentication Function (NEWLY IMPLEMENTED) ---

def get_current_active_user(session: Session, token: str) -> Optional["operations.User"]:
    """
    Decodes the JWT token, extracts the username, and fetches the user from the database.
    Returns the user object if the token is valid and the user is active.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    
    username: Optional[str] = payload.get("sub")
    if username is None:
        return None
        
    user = operations.get_user_by_username(session=session, username=username)
    if user is None or not user.is_active:
        return None
        
    return user

def authenticate_user(session: Session, username: str, password: str) -> Optional["operations.User"]:
    """
    Authenticates a user by checking their username and password.
    """
    user = operations.get_user_by_username(session=session, username=username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
