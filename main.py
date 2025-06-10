import os
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Depends, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # ¡NUEVO CAMBIO AQUÍ! Importar StaticFiles


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
    "http://127.0.0.1", # Añadir 127.0.0.1 para pruebas locales
    "http://127.0.0.1:8000", # Añadir 127.0.0.1:8000 para pruebas locales
    "https://juegos-steam-s8wn.onrender.com", # Tu dominio de Render
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ¡NUEVO CAMBIO AQUÍ! Montar el directorio 'uploads' para servir archivos estáticos
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.on_event("startup")
def on_startup():
    database.create_db_and_tables()

# Endpoint para servir el frontend (asume que 'index.html' está en la raíz del proyecto)
@app.get("/")
async def read_root():
    return FileResponse("index.html")

# Dependencia para obtener la sesión de la base de datos
def get_session():
    with Session(database.engine) as session:
        yield session

# Dependencia para obtener el usuario actual
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")

async def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = auth.get_user_from_token(session, token)
    if user is None:
        raise credentials_exception
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuario inactivo o eliminado"
        )
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user

async def get_current_admin_user(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador")
    return current_user

# --- Autenticación y Usuarios ---

@app.post("/api/v1/token", response_model=auth.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)
):
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

@app.get("/api/v1/users/me/", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/api/v1/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_new_user(
    user_create: UserCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin_user) # Solo admin puede crear usuarios
):
    db_user = operations.get_user_by_username(session, user_create.username)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El nombre de usuario ya está registrado"
        )
    db_user = operations.get_user_by_email(session, user_create.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El correo electrónico ya está registrado"
        )
    return operations.create_user_in_db(session, user_create)

@app.get("/api/v1/users/{user_id}", response_model=UserReadWithReviews)
async def read_user_by_id(user_id: int, session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    user = operations.get_user_with_reviews_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user

@app.put("/api/v1/users/me/", response_model=UserRead)
async def update_my_profile(
    user_update: UserCreate, # Podrías crear un UserUpdate si no quieres que puedan cambiar el password así
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Asegúrate de que el usuario no intente cambiar a un username/email ya existente por otro usuario
    if user_update.username != current_user.username:
        if operations.get_user_by_username(session, user_update.username):
            raise HTTPException(status_code=400, detail="Este nombre de usuario ya está en uso.")
    if user_update.email != current_user.email:
        if operations.get_user_by_email(session, user_update.email):
            raise HTTPException(status_code=400, detail="Este email ya está en uso.")

    updated_user = operations.update_user_in_db(session, current_user.id, user_update)
    if not updated_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado para actualizar.")
    return updated_user

@app.delete("/api/v1/users/me/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if not operations.delete_user_in_db(session, current_user.id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return {"message": "Cuenta eliminada exitosamente."}

# --- Endpoints para Games ---

@app.post("/api/v1/juegos/", response_model=GameRead, status_code=status.HTTP_201_CREATED)
async def create_game(
    game: GameCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin_user) # Solo admin puede crear juegos
):
    db_game = operations.get_game_by_steam_app_id(session, game.steam_app_id)
    if db_game:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un juego con este Steam App ID ya existe."
        )
    return operations.create_game_in_db(session, game)

@app.get("/api/v1/juegos/", response_model=List[GameRead])
async def read_games(offset: int = 0, limit: int = Query(default=100, le=100), session: Session = Depends(get_session)):
    return operations.get_all_games(session, offset=offset, limit=limit)

@app.get("/api/v1/juegos/{game_id}", response_model=GameReadWithReviews)
async def read_game(game_id: int = Path(..., gt=0), session: Session = Depends(get_session)):
    game = operations.get_game_with_reviews_by_id(session, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return game

@app.put("/api/v1/juegos/{game_id}", response_model=GameRead)
async def update_game(
    game_id: int,
    game: GameUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin_user) # Solo admin puede actualizar juegos
):
    updated_game = operations.update_game_in_db(session, game_id, game)
    if not updated_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return updated_game

@app.delete("/api/v1/juegos/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game(
    game_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_admin_user) # Solo admin puede eliminar juegos
):
    if not operations.delete_game_in_db(session, game_id):
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return {"message": "Juego eliminado exitosamente."}

# --- Endpoints para Reviews ---

@app.post("/api/v1/reviews/", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review_for_game(
    review_create: ReviewCreate,
    game_id: int = Body(..., embed=True), # Permite enviar game_id en el cuerpo
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return operations.create_review_in_db(session, review_create, game_id, current_user.id)

@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails)
async def read_review(review_id: int, session: Session = Depends(get_session)):
    review = operations.get_review_with_details_by_id(session, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return review

@app.put("/api/v1/reviews/{review_id}", response_model=ReviewRead)
async def update_review(
    review_id: int,
    review_update: ReviewCreate, # Podrías crear un ReviewUpdate para parciales
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Asegúrate de que el usuario solo pueda actualizar sus propias reseñas (a menos que sea admin)
    db_review = operations.get_review_by_id(session, review_id)
    if not db_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if db_review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar esta reseña.")

    updated_review = operations.update_review_in_db(session, review_id, review_update)
    if not updated_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada después de intentar actualizar.")
    return updated_review

@app.delete("/api/v1/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    db_review = operations.get_review_by_id(session, review_id)
    if not db_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if db_review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta reseña.")

    if not operations.delete_review_in_db(session, review_id):
        raise HTTPException(status_code=404, detail="Reseña no encontrada.")
    return {"message": "Reseña eliminada exitosamente."}


# --- Endpoints para PlayerActivity ---

@app.post("/api/v1/player-activity/", response_model=PlayerActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_player_activity(
    activity: PlayerActivityCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Aquí puedes añadir lógica para asegurar que el player_id corresponda al current_user.id
    # o que solo los admins puedan registrar actividad para otros jugadores.
    # Por ahora, simplemente lo creamos.
    return operations.create_player_activity_in_db(session, activity)

@app.get("/api/v1/player-activity/{activity_id}", response_model=PlayerActivityResponse)
async def read_player_activity(activity_id: int, session: Session = Depends(get_session)):
    activity = operations.get_player_activity_by_id(session, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Actividad de jugador no encontrada")
    return activity

@app.get("/api/v1/player-activity/user/{user_id}", response_model=List[PlayerActivityResponse])
async def read_player_activity_by_user(user_id: int, session: Session = Depends(get_session)):
    activities = operations.get_player_activity_by_user_id(session, user_id)
    return activities

@app.get("/api/v1/player-activity/game/{game_id}", response_model=List[PlayerActivityResponse])
async def read_player_activity_by_game(game_id: int, session: Session = Depends(get_session)):
    activities = operations.get_player_activity_by_game_id(session, game_id)
    return activities


# --- Endpoints de Integración con Steam API ---

@app.get("/api/v1/steam/game/{app_id}", response_model=GameRead)
async def get_steam_game_details_and_add_to_db(app_id: int, session: Session = Depends(get_session)):
    """
    Obtiene los detalles de un juego de la API de Steam y lo añade/actualiza en la base de datos local.
    """
    try:
        game = await operations.get_steam_game_details_and_add_to_db(session, app_id)
        if game:
            return game
        raise HTTPException(status_code=404, detail=f"No se encontraron detalles para el App ID {app_id}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener detalles del juego de Steam: {e}")

@app.get("/api/v1/steam/current_players/{app_id}")
async def get_steam_current_players_endpoint(app_id: int):
    """
    Obtiene el número de jugadores actuales para un App ID de Steam.
    """
    player_count = await operations.get_current_players_for_app(app_id)
    if player_count is not None:
        return {"app_id": app_id, "player_count": player_count}
    raise HTTPException(status_code=404, detail=f"No se pudo obtener el número de jugadores actuales para el App ID {app_id}. Asegúrate de que el App ID sea correcto y la STEAM_API_KEY esté configurada.")


# --- Endpoint para Subir Imágenes ---
@app.post("/api/v1/upload_image")
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)): # Añadido current_user para que requiera auth
    """
    Endpoint para subir una imagen.
    En este demo, simula el guardado y retorna una URL temporal.
    """
    try:
        # En una aplicación real, aquí guardarías el archivo a un almacenamiento persistente
        # Por ahora, operations.save_uploaded_image solo genera una URL simulada
        # Para que funcione con StaticFiles, operations.save_uploaded_image debe
        # realmente guardar el archivo en la carpeta 'uploads'.
        # Vamos a modificar operations.py para que guarde el archivo de verdad.

        # Guardar el archivo en la carpeta 'uploads'
        UPLOAD_DIR = "uploads"
        os.makedirs(UPLOAD_DIR, exist_ok=True) # Asegura que la carpeta exista
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb+") as file_object:
            file_object.write(await file.read())

        image_url = f"/uploads/{file.filename}" # URL accesible a través de StaticFiles

        if not image_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo procesar la imagen.")
        return {"filename": file.filename, "url": image_url, "message": "Imagen procesada y guardada en /uploads."}
    except Exception as e:
        print(f"🚨 Error al procesar la imagen: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno al procesar la imagen: {e}")