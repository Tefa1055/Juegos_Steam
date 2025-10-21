import os, time
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlmodel import Session, select
from models import User
from database import get_session

SECRET_KEY = os.getenv("JWT_SECRET", "CHANGE_ME")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60*60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/usuarios/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p): return pwd_context.hash(p)
def verify_password(p, h): return pwd_context.verify(p, h)

def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_SECONDS):
    to_encode = data.copy()
    to_encode.update({"exp": int(time.time()) + expires_delta})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas", headers={"WWW-Authenticate":"Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None: raise cred_exc
    except JWTError:
        raise cred_exc
    user = session.exec(select(User).where(User.id == int(sub))).first()
    if not user: raise cred_exc
    return user
