import os
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File

import operations
import database
import auth
from models import (
    Game, GameCreate, GameRead, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserRead, UserReadWithReviews,
    ReviewBase, ReviewReadWithDetails, Review, # Import ReviewReadWithDetails
    PlayerActivityCreate, PlayerActivityResponse
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Directorio para guardar las imágenes de reseña
IMAGE_DIR = os.path.join(BASE_DIR, "review_images")
os.makedirs(IMAGE_DIR, exist_ok=True)


app = FastAPI(
    title="API de Videojuegos de Steam",
    description="Servicio para consultar y gestionar información de juegos, usuarios, reseñas y actividad de jugadores en Steam.",
    version="1.0.0",
)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "https://juegos-steam-s8wn.onrender.com", # Tu dominio de Render
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

# Endpoint para servir el frontend (asume que 'index.html' está en la raíz del proyecto)
@app.get("/", include_in_schema=False)
async def read_root():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# Endpoint para servir archivos estáticos (imágenes)
@app.get("/review_images/{filename}", include_in_schema=False)
async def serve_review_image(filename: str):
    file_path = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Imagen no encontrada.")

# Esquema de seguridad OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependencia para obtener el usuario actual
async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(database.get_session)) -> User:
    user = auth.get_current_user_from_token(session, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# Endpoint de autenticación (login)
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(database.get_session)):
    user = auth.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nombre de usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Endpoints para Users ---
@app.post("/api/v1/usuarios", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, session: Session = Depends(database.get_session)):
    db_user = operations.get_user_by_username(session, user.username)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El nombre de usuario ya está registrado.")
    db_user = operations.create_user_in_db(session, user)
    return db_user

@app.get("/api/v1/usuarios", response_model=List[UserRead])
def get_users(session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    users = operations.get_all_users(session)
    return users

@app.get("/api/v1/usuarios/{user_id}", response_model=UserRead)
def get_user_by_id(user_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    user = operations.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return user

@app.get("/api/v1/usuarios/{user_id}/reviews", response_model=List[ReviewReadWithDetails]) # Use ReviewReadWithDetails
def get_user_reviews(user_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    # Opcional: solo permitir que un usuario vea sus propias reseñas
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para ver las reseñas de otros usuarios.")
    
    reviews = operations.get_reviews_by_user_id_from_db(session, user_id)
    return reviews


# --- Endpoints para Games ---
@app.post("/api/v1/juegos", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_game(game: GameCreate, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    try:
        db_game = operations.create_game_in_db(session, game)
        return db_game
    except Exception as e:
        print(f"🚨 Error al crear juego: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")

@app.post("/api/v1/juegos/from_steam", response_model=GameRead, status_code=status.HTTP_201_CREATED)
async def create_game_from_steam(app_id: int = Query(..., description="Steam App ID del juego a agregar"), session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    """
    Crea un nuevo juego en la DB local usando los detalles obtenidos de la API de Steam.
    """
    try:
        # Primero, obtener los detalles del juego de Steam
        steam_game_details = await get_steam_game_details(app_id) # Reutilizamos el endpoint existente o una función interna
        
        if not steam_game_details or not steam_game_details.get("success"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No se encontraron detalles para el Steam App ID: {app_id}")

        game_data = steam_game_details["data"]

        # Verificar si el juego ya existe en tu DB por steam_app_id
        existing_game = session.exec(select(Game).where(Game.steam_app_id == app_id, Game.is_deleted == False)).first()
        if existing_game:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"El juego con Steam App ID {app_id} ya existe en tu base de datos (ID: {existing_game.id}).")

        # Mapear los datos de Steam al modelo GameCreate
        new_game_data = GameCreate(
            title=game_data.get("name", "Nombre desconocido"),
            developer=", ".join(game_data.get("developers", [])) if game_data.get("developers") else None,
            publisher=", ".join(game_data.get("publishers", [])) if game_data.get("publishers") else None,
            genres=", ".join([g["description"] for g in game_data.get("genres", [])]) if game_data.get("genres") else None,
            release_date=game_data["release_date"].get("date") if game_data.get("release_date") else None,
            price=game_data.get("price_overview", {}).get("final") / 100.0 if game_data.get("price_overview") else 0.0,
            steam_app_id=app_id
        )
        
        # Crear el juego en tu DB
        db_game = operations.create_game_in_db(session, new_game_data)
        return db_game
    except HTTPException as e:
        raise e # Re-lanzar HTTPExceptions directamente
    except Exception as e:
        print(f"🚨 Error inesperado al agregar juego desde Steam: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")


@app.get("/api/v1/juegos", response_model=List[GameRead])
def get_games(session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    games = operations.get_all_games(session)
    return games

@app.get("/api/v1/juegos/{game_id}", response_model=GameRead)
def get_game(game_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    game = operations.get_game_by_id(session, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado.")
    return game

@app.put("/api/v1/juegos/{game_id}", response_model=GameRead)
def update_game(game_id: int, game: GameUpdate, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    updated_game = operations.update_game_in_db(session, game_id, game)
    if not updated_game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o ya eliminado.")
    return updated_game

@app.delete("/api/v1/juegos/{game_id}", status_code=204)
def delete_game(game_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    if not operations.delete_game_in_db(session, game_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o ya eliminado.")
    return

@app.get("/api/v1/juegos/{game_id}/reviews", response_model=List[ReviewReadWithDetails]) # Use ReviewReadWithDetails
def get_game_reviews(game_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    game = operations.get_game_by_id(session, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado.")
    reviews = operations.get_reviews_by_game_id_from_db(session, game_id)
    return reviews

# --- Endpoints para Reviews ---
@app.post("/api/v1/reviews", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
def create_review(review: ReviewCreate, game_id: int = Query(...), session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    game = operations.get_game_by_id(session, game_id)
    if not game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado.")
    
    # Comprobar si el usuario ya tiene una reseña para este juego
    existing_review = session.exec(
        select(Review).where(Review.game_id == game_id, Review.user_id == current_user.id, Review.is_deleted == False)
    ).first()
    if existing_review:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ya has enviado una reseña para este juego.")

    db_review = operations.create_review_in_db(session, review, game_id, current_user.id)
    return db_review

@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails) # Use ReviewReadWithDetails
def get_review(review_id: int, session: Session = Depends(database.get_session), current_user: User = Depends(get_current_user)):
    review = operations.get_review_by_id(session, review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada.")
    return review

# --- Endpoints para subir imágenes ---
@app.post("/api/v1/upload_image")
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    try:
        # Generar un nombre de archivo único
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # Usar el ID del usuario para evitar colisiones entre usuarios
        filename = f"{current_user.id}_{timestamp}_{file.filename}"
        file_path = os.path.join(IMAGE_DIR, filename)

        # Guardar el archivo
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Devolver la URL relativa para acceder a la imagen
        return {"filename": filename, "url": f"/review_images/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al subir imagen: {e}")

# --- Endpoints de integración con Steam API (proxy) ---
import httpx

STEAM_API_BASE_URL = "https://api.steampowered.com"
STEAM_STORE_API_BASE_URL = "https://store.steampowered.com/api"

@app.get("/api/v1/steam/app_list")
async def get_steam_app_list(current_user: User = Depends(get_current_user)):
    """
    Obtiene la lista de todas las aplicaciones (juegos) de Steam.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{STEAM_API_BASE_URL}/ISteamApps/GetAppList/v2/")
            response.raise_for_status()
            data = response.json()
            # La API de Steam devuelve un objeto con 'applist' y dentro 'apps'
            return data.get("applist", {}).get("apps", [])
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error de Steam API: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error de conexión con Steam API: {e}")
    except Exception as e:
        print(f"🚨 Error inesperado en get_steam_app_list: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")

@app.get("/api/v1/steam/game_details/{app_id}")
async def get_steam_game_details(app_id: int, current_user: User = Depends(get_current_user)):
    """
    Obtiene los detalles de un juego específico de Steam.
    """
    try:
        async with httpx.AsyncClient() as client:
            # lang=es para obtener detalles en español
            response = await client.get(f"{STEAM_STORE_API_BASE_URL}/appdetails?appids={app_id}&l=spanish")
            response.raise_for_status()
            data = response.json()
            game_data = data.get(str(app_id))
            if game_data and game_data.get("success"):
                return game_data
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalles del juego no encontrados o App ID inválido.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error de Steam Store API: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error de conexión con Steam Store API: {e}")
    except Exception as e:
        print(f"🚨 Error inesperado en get_steam_game_details: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")

@app.get("/api/v1/steam/current_players/{app_id}")
async def get_current_players(app_id: int, current_user: User = Depends(get_current_user)):
    """
    Obtiene el número de jugadores actuales para un juego de Steam.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{STEAM_API_BASE_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={app_id}")
            response.raise_for_status()
            data = response.json()
            player_count_data = data.get("response")
            if player_count_data and "player_count" in player_count_data:
                return {"app_id": app_id, "player_count": player_count_data["player_count"]}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontraron datos de jugadores para este App ID.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Error de Steam API (Players): {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Error de conexión con Steam API (Players): {e}")
    except Exception as e:
        print(f"🚨 Error inesperado en get_current_players: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")


# --- Endpoints para PlayerActivity (usando el mock) ---
@app.post("/api/v1/actividad_jugadores", response_model=PlayerActivityResponse, status_code=status.HTTP_201_CREATED)
def create_new_player_activity(activity: PlayerActivityCreate, current_user: User = Depends(get_current_user)):
    try:
        # Asignar el player_id del usuario autenticado si es necesario
        activity.player_id = current_user.id # Asegúrate de que player_id se asigne desde el usuario autenticado
        new_activity = operations.create_player_activity_mock(activity.model_dump())
        return new_activity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"🚨 Error inesperado al crear actividad de jugador: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")

@app.get("/api/v1/actividad_jugadores/{activity_id}", response_model=PlayerActivityResponse)
def get_single_player_activity(activity_id: int, current_user: User = Depends(get_current_user)):
    activity = operations.get_player_activity_mock(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")
    return activity

@app.put("/api/v1/actividad_jugadores/{id_actividad}", response_model=PlayerActivityResponse)
def update_existing_player_activity(id_actividad: int, update_data: PlayerActivityCreate, current_user: User = Depends(get_current_user)):
    try:
        updated = operations.update_player_activity_mock(id_actividad, update_data.model_dump())
        if not updated:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        print(f"🚨 Error inesperado al actualizar actividad de jugador: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")

@app.delete("/api/v1/actividad_jugadores/{id_actividad}", status_code=204)
def delete_existing_player_activity(id_actividad: int, current_user: User = Depends(get_current_user)):
    try:
        deleted = operations.delete_player_activity_mock(id_actividad)
        if not deleted:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        return
    except Exception as e:
        print(f"🚨 Error inesperado al eliminar actividad de jugador: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {e}")
