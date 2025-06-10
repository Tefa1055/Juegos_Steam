import os
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware

import operations
import database
import auth
from models import (
    Game, GameCreate, GameRead, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserRead, UserReadWithReviews,
    ReviewBase, ReviewReadWithDetails, Review,
    PlayerActivityCreate, PlayerActivityResponse
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="API de Videojuegos de Steam",
    description="Servicio para consultar y gestionar información de juegos, usuarios, reseñas y actividad de jugadores en Steam.",
    version="1.0.0",
)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "https://juegos-steam-s8wn.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    database.create_db_and_tables()

@app.get("/", response_class=FileResponse, include_in_schema=False)
async def root():
    return FileResponse("index.html")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(database.get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = auth.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    user = operations.get_user_by_username(session, username=username)
    if user is None:
        raise credentials_exception
    return user

# --- Endpoints de Juegos ---

@app.post("/api/v1/juegos", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_new_game(game: GameCreate, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    try:
        return operations.create_game_in_db(session, game)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo crear el juego: {e}")

@app.get("/api/v1/juegos", response_model=List[GameRead])
def read_all_games(session: Session = Depends(database.get_session)):
    return operations.get_all_games(session)

@app.get("/api/v1/juegos/ids", response_model=List[int])
def get_all_game_ids(session: Session = Depends(database.get_session)):
    ids = session.exec(select(Game.id).where(Game.is_deleted == False)).all()
    return sorted(list(ids))

@app.get("/api/v1/juegos/filtrar", response_model=List[GameRead])
def filter_games(genre: str = Query(...), session: Session = Depends(database.get_session)):
    return operations.filter_games_by_genre(session, genre)

@app.get("/api/v1/juegos/buscar", response_model=List[GameRead])
def search_games(q: str = Query(...), session: Session = Depends(database.get_session)):
    return operations.search_games_by_title(session, q)

@app.get("/api/v1/juegos/{id_juego}", response_model=GameReadWithReviews)
def read_game_by_id(id_juego: int, session: Session = Depends(database.get_session)):
    game = operations.get_game_with_reviews(session, id_juego)
    if game is None:
        raise HTTPException(status_code=404, detail="Juego no encontrado o eliminado.")
    return game

@app.put("/api/v1/juegos/{id_juego}", response_model=GameRead)
def update_existing_game(id_juego: int, update_data: GameUpdate, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    updated = operations.update_game(session, id_juego, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Juego no encontrado.")
    return updated

@app.delete("/api/v1/juegos/{id_juego}", status_code=204)
def delete_existing_game(id_juego: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    deleted = operations.delete_game_soft(session, id_juego)
    if not deleted:
        raise HTTPException(status_code=404, detail="Juego no encontrado.")
    return

# --- Endpoint corregido de Registro de Usuarios (con manejo de errores) ---

@app.post("/api/v1/usuarios", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(user_data: UserCreate, session: Session = Depends(database.get_session)):
    try:
        hashed_password = auth.get_password_hash(user_data.password)
        user = operations.create_user_in_db(session, user_data, hashed_password)
        if not user:
            raise HTTPException(status_code=400, detail="Nombre de usuario o email ya registrado.")
        return user
    except Exception as e:
        print("🚨 Error al crear usuario:", repr(e))
        raise HTTPException(status_code=500, detail=f"Excepción interna al crear usuario: {e}")

@app.get("/api/v1/usuarios", response_model=List[UserRead])
def read_all_users(session: Session = Depends(database.get_session)):
    return operations.get_all_users(session)

@app.get("/api/v1/usuarios/{user_id}", response_model=UserReadWithReviews)
def read_user_by_id(user_id: int, session: Session = Depends(database.get_session)):
    user = operations.get_user_with_reviews(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user

# --- Token Login ---

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(database.get_session)):
    user = operations.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Nombre de usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Bearer"})
    access_token = auth.create_access_token(data={"sub": user.username}, expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer"}

# --- Reseñas ---

@app.post("/api/v1/reviews", response_model=Review, status_code=201)
def create_new_review(review_data: ReviewBase, game_id: int = Query(...), session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    review = operations.create_review_in_db(session, review_data, game_id, current_user.id)
    if not review:
        raise HTTPException(status_code=400, detail="No se pudo crear la reseña.")
    return review

@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails)
def read_review_by_id(review_id: int, session: Session = Depends(database.get_session)):
    review = operations.get_review_with_details(session, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    return review

@app.get("/api/v1/juegos/{game_id}/reviews", response_model=List[Review])
def read_reviews_for_game(game_id: int, session: Session = Depends(database.get_session)):
    return operations.get_reviews_for_game(session, game_id)

@app.get("/api/v1/usuarios/{user_id}/reviews", response_model=List[Review])
def read_reviews_by_user(user_id: int, session: Session = Depends(database.get_session)):
    return operations.get_reviews_by_user(session, user_id)

@app.put("/api/v1/reviews/{review_id}", response_model=Review)
def update_existing_review(review_id: int, review_update: ReviewBase, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    review = operations.get_review_by_id(session, review_id)
    if review and review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado.")
    updated = operations.update_review_in_db(session, review_id, review_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    return updated

@app.delete("/api/v1/reviews/{review_id}", status_code=204)
def delete_existing_review(review_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    review = operations.get_review_by_id(session, review_id)
    if review and review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No autorizado.")
    deleted = operations.delete_review_soft(session, review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    return

# --- Actividad de Jugadores (mock) ---

@app.get("/api/v1/actividad_jugadores", response_model=List[PlayerActivityResponse])
def read_all_player_activity(include_deleted: bool = Query(False), current_user: User = Depends(get_current_user)):
    return operations.get_all_player_activity_mock(include_deleted=include_deleted)

@app.get("/api/v1/actividad_jugadores/{id_actividad}", response_model=PlayerActivityResponse)
def read_player_activity_by_id(id_actividad: int, current_user: User = Depends(get_current_user)):
    activity = operations.get_player_activity_by_id_mock(id_actividad)
    if not activity:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")
    return activity

@app.post("/api/v1/actividad_jugadores", response_model=PlayerActivityResponse, status_code=201)
def create_new_player_activity(activity: PlayerActivityCreate, current_user: User = Depends(get_current_user)):
    try:
        return operations.create_player_activity_mock(activity.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

@app.put("/api/v1/actividad_jugadores/{id_actividad}", response_model=PlayerActivityResponse)
def update_existing_player_activity(id_actividad: int, update_data: PlayerActivityCreate, current_user: User = Depends(get_current_user)):
    try:
        updated = operations.update_player_activity_mock(id_actividad, update_data.model_dump())
        if not updated:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")

@app.delete("/api/v1/actividad_jugadores/{id_actividad}", status_code=204)
def delete_existing_player_activity(id_actividad: int, current_user: User = Depends(get_current_user)):
    try:
        deleted = operations.delete_player_activity_mock(id_actividad)
        if not deleted:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        return
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")
