# main.py
import os
from typing import List

from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

import database
import operations
import auth
from models import (
    User, UserCreate, UserRead,
    Game, GameCreate, GameUpdate, GameRead,
)

# =========================================================
# Configuración de la app
# =========================================================
app = FastAPI(
    title="API Juegos",
    description="Backend con autenticación estricta y CRUD de juegos con dueño.",
    version="1.0.0",
)

# CORS (ajusta tu dominio si cambias de URL)
origins = [
    "http://localhost",
    "http://127.0.0.1:8000",
    "https://juegos-steam-s8wn.onrender.com",
    "null",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos estáticos / index.html (wireframe)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")

@app.get("/", include_in_schema=False)
def root():
    """
    Sirve index.html si existe (wireframe).
    """
    index_path = os.path.join(BASE_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Backend OK"}

# Base de datos
@app.on_event("startup")
def on_startup():
    database.create_db_and_tables()

# =========================================================
# Autenticación y dependencia de usuario actual
# =========================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(database.get_session),
) -> User:
    """
    Devuelve el usuario actual a partir del token.
    Lanza 401 si no es válido.
    """
    user = auth.get_current_active_user(session=session, token=token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron validar las credenciales",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# =========================================================
# Usuarios
# =========================================================
@app.post("/api/v1/usuarios", response_model=UserRead, status_code=201)
def create_user(
    user_data: UserCreate,
    session: Session = Depends(database.get_session),
):
    """
    Crea un nuevo usuario (username y email únicos).
    """
    user = operations.create_user_in_db(session, user_data)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Usuario o email ya registrado."
        )
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active
    )

@app.get("/api/v1/usuarios", response_model=List[UserRead])
def list_users(session: Session = Depends(database.get_session)):
    """
    Lista usuarios activos (endpoint abierto para pruebas).
    """
    users = operations.get_all_users(session)
    return [
        UserRead(id=u.id, username=u.username, email=u.email, is_active=u.is_active)
        for u in users
    ]

@app.get("/api/v1/usuarios/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)):
    """
    Devuelve los datos del usuario autenticado (clave para el frontend).
    """
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active
    )

# =========================================================
# Token (login)
# =========================================================
@app.post("/token")
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(database.get_session),
):
    """
    Login con username y password -> Bearer token JWT.
    """
    user = auth.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# =========================================================
# Recuperación de contraseña (2 pasos)
# =========================================================
from pydantic import BaseModel, EmailStr

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

@app.post("/password-recovery")
def request_password_recovery(
    payload: PasswordResetRequest,
    session: Session = Depends(database.get_session),
):
    """
    Paso 1: Solicitar reset. Respuesta neutral.
    Imprime el token en consola para pruebas.
    """
    user = operations.get_user_by_email(session, payload.email)
    if not user:
        return {"message": "Si el email está registrado, se enviará un enlace de recuperación."}
    token = auth.create_password_reset_token(user.email)
    # Para demo: muestra el token en logs
    print("=== TOKEN RESET ===", token)
    return {"message": "Si el email está registrado, se enviará un enlace de recuperación."}

@app.post("/reset-password")
def reset_password(
    payload: PasswordResetConfirm,
    session: Session = Depends(database.get_session),
):
    """
    Paso 2: Confirmar reset con token + nueva contraseña.
    """
    email = auth.decode_password_reset_token(payload.token)
    if not email:
        raise HTTPException(status_code=400, detail="Token inválido o expirado.")
    user = operations.get_user_by_email(session, email)
    if not user:
        raise HTTPException(status_code=400, detail="Usuario no encontrado.")
    ok = operations.reset_user_password(session, user, payload.new_password)
    if not ok:
        raise HTTPException(status_code=500, detail="No se pudo actualizar la contraseña.")
    return {"message": "Contraseña actualizada correctamente."}

# =========================================================
# Juegos (modo estricto: requieren login)
# =========================================================
@app.post("/api/v1/juegos", response_model=GameRead, status_code=201)
def create_game(
    game_data: GameCreate,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Crea un juego y lo asocia al dueño (current_user.id).
    """
    game = operations.create_game_in_db(session, game_data, owner_id=current_user.id)
    return GameRead.from_orm(game)

@app.get("/api/v1/juegos", response_model=List[GameRead])
def list_games(
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Lista juegos no eliminados. Requiere login (dashboard).
    """
    games = operations.get_all_games(session)
    return [GameRead.from_orm(g) for g in games]

@app.get("/api/v1/juegos/{game_id}", response_model=GameRead)
def get_game(
    game_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene un juego por id. Requiere login.
    """
    game = operations.get_game_by_id(session, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Juego no encontrado.")
    return GameRead.from_orm(game)

@app.put("/api/v1/juegos/{game_id}", response_model=GameRead)
def update_game(
    game_id: int,
    data: GameUpdate,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Actualiza un juego (solo dueño). Requiere login.
    """
    game = operations.update_game_in_db(session, game_id, data, current_user_id=current_user.id)
    if not game:
        raise HTTPException(status_code=403, detail="No autorizado o juego inexistente.")
    return GameRead.from_orm(game)

@app.delete("/api/v1/juegos/{game_id}", status_code=204)
def delete_game(
    game_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Borrado lógico de juego (solo dueño). Requiere login.
    """
    ok = operations.soft_delete_game(session, game_id, current_user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=403, detail="No autorizado o juego inexistente.")
    return
