from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from models import User
from database import get_session
from auth import hash_password, verify_password, create_access_token

router = APIRouter()

@router.post("/", status_code=201)
def register(data: dict, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.email == data["email"])).first():
        raise HTTPException(status_code=400, detail="Email ya registrado")
    u = User(username=data.get("username", data["email"].split("@")[0]), email=data["email"], password_hash=hash_password(data["password"]))
    session.add(u); session.commit(); session.refresh(u)
    return {"id": u.id, "username": u.username, "email": u.email}

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    u = session.exec(select(User).where(User.email == form.username)).first()
    if not u or not verify_password(form.password, u.password_hash):
        raise HTTPException(status_code=400, detail="Credenciales inválidas")
    token = create_access_token({"sub": str(u.id), "username": u.username, "email": u.email})
    return {"access_token": token, "token_type":"bearer"}

@router.get("/me")
def me(user: User = Depends(__import__('auth').get_current_user)):
    # This dependency is replaced inline to avoid circular import in example
    return {"id": user.id, "username": user.username, "email": user.email}
