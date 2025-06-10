import os
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, status, Query, Body, Path, Depends, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles # Importar StaticFiles

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
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads") # Definir la ruta del directorio de uploads

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
    # Crear el directorio 'uploads' si no existe
    if not os.path.exists(UPLOADS_DIR):
        os.makedirs(UPLOADS_DIR)
        print(f"DEBUG: Directorio '{UPLOADS_DIR}' creado.")
    database.create_db_and_tables()

# Endpoint para servir el frontend (asume que 'index.html' está en la raíz del proyecto)
@app.get("/")
async def read_root():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# Montar el directorio de archivos estáticos para las imágenes subidas
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


# --- Endpoints de Autenticación ---

@app.post("/token", response_model=auth.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(database.get_session)
):
    user = operations.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Endpoints para Usuarios ---

@app.post("/api/v1/usuarios", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    session: Session = Depends(database.get_session)
):
    hashed_password = auth.get_password_hash(user_data.password) # Asume que UserCreate tiene un campo 'password'
    db_user = operations.create_user_in_db(session, user_data, hashed_password)
    if db_user is None:
        raise HTTPException(status_code=400, detail="El nombre de usuario o el email ya están registrados.")
    return db_user

@app.get("/api/v1/usuarios", response_model=List[UserRead])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user)
):
    users = operations.get_all_users(session)
    return users[skip : skip + limit]

@app.get("/api/v1/usuarios/me", response_model=UserRead)
async def read_users_me(
    current_user: User = Depends(auth.get_current_active_user)
):
    return current_user

@app.put("/api/v1/usuarios/me", response_model=UserRead)
async def update_users_me(
    user_update: UserCreate, # Usamos UserCreate para la actualización, ya que tiene los campos username y email
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user)
):
    # Aquí puedes añadir lógica para actualizar la contraseña si fuera necesario
    # Por ahora, solo actualizamos username y email
    if current_user.username != user_update.username and operations.get_user_by_username(session, user_update.username):
        raise HTTPException(status_code=400, detail="El nuevo nombre de usuario ya está en uso.")
    if current_user.email != user_update.email and session.exec(select(User).where(User.email == user_update.email)).first():
         raise HTTPException(status_code=400, detail="El nuevo email ya está en uso.")

    current_user.username = user_update.username
    current_user.email = user_update.email
    # No actualizamos la contraseña aquí a menos que se envíe una nueva y se procese el hash
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@app.get("/api/v1/usuarios/{user_id}", response_model=UserReadWithReviews)
async def get_user_by_id_endpoint(
    user_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user)
):
    user = operations.get_user_with_reviews(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo.")
    return user

@app.delete("/api/v1/usuarios/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_admin_user) # Solo administradores pueden eliminar usuarios
):
    # Si el usuario intenta eliminarse a sí mismo, se permite
    if user_id == current_user.id:
        deleted_user = operations.delete_user_soft(session, user_id)
        if not deleted_user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        return
    
    # Si no es administrador, no puede eliminar a otros usuarios
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para eliminar este usuario.")

    # Si es administrador, puede eliminar cualquier usuario
    deleted_user = operations.delete_user_soft(session, user_id)
    if not deleted_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return


# --- Endpoints para Juegos ---

@app.post("/api/v1/juegos", response_model=GameRead, status_code=status.HTTP_201_CREATED)
async def create_game(
    game: GameCreate,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación para crear juegos
):
    db_game = operations.create_game_in_db(session, game)
    return db_game

@app.post("/api/v1/juegos/from_steam", response_model=GameRead, status_code=status.HTTP_201_CREATED)
async def create_game_from_steam(
    app_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    """
    Crea un juego en la base de datos a partir de su App ID de Steam.
    Si el juego ya existe, lo retorna; si no, lo crea.
    """
    existing_game = session.exec(select(Game).where(Game.steam_app_id == app_id, Game.is_deleted == False)).first()
    if existing_game:
        return existing_game

    steam_game_details = await operations.get_game_details_from_steam_api(app_id)
    if not steam_game_details:
        raise HTTPException(status_code=404, detail=f"No se encontraron detalles de Steam para el App ID {app_id}.")

    # Mapear los detalles de Steam al modelo GameCreate
    # Esta parte asume un mapeo simple; ajusta según tus necesidades
    game_data_for_db = GameCreate(
        title=steam_game_details.get("name", f"Juego Steam {app_id}"),
        developer=steam_game_details.get("developers", ["N/A"])[0] if steam_game_details.get("developers") else "N/A",
        publisher=steam_game_details.get("publishers", ["N/A"])[0] if steam_game_details.get("publishers") else "N/A",
        genres=steam_game_details.get("genres", ["N/A"])[0] if steam_game_details.get("genres") else "N/A",
        release_date=datetime.strptime(steam_game_details["release_date"], "%b %d, %Y").date() if "release_date" in steam_game_details and steam_game_details["release_date"] != "Coming Soon" else None,
        price=float(steam_game_details.get("price_overview", {}).get("final_formatted", "0").replace("$", "").replace(",", "")) if steam_game_details.get("price_overview") else 0.0,
        steam_app_id=app_id,
        image_filename=steam_game_details.get("header_image") # Guardar la URL de la imagen del encabezado
    )
    
    db_game = operations.create_game_in_db(session, game_data_for_db)
    return db_game


@app.get("/api/v1/juegos", response_model=List[GameRead])
async def get_games(
    genre: Optional[str] = Query(None, description="Filtrar por género"),
    title_query: Optional[str] = Query(None, description="Buscar por título"),
    skip: int = 0,
    limit: int = 100,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    if genre:
        games = operations.filter_games_by_genre(session, genre)
    elif title_query:
        games = operations.search_games_by_title(session, title_query)
    else:
        games = operations.get_all_games(session)
    return games[skip : skip + limit]

@app.get("/api/v1/juegos/{game_id}", response_model=GameReadWithReviews)
async def get_game_by_id_with_reviews_endpoint(
    game_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    game = operations.get_game_with_reviews(session, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Juego no encontrado o eliminado.")
    return game

@app.put("/api/v1/juegos/{game_id}", response_model=GameRead)
async def update_game_endpoint(
    game_id: int,
    game_update: GameUpdate,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    updated_game = operations.update_game(session, game_id, game_update)
    if not updated_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado o eliminado.")
    return updated_game

@app.delete("/api/v1/juegos/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_game_endpoint(
    game_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_admin_user) # Solo administradores pueden eliminar juegos
):
    deleted_game = operations.delete_game_soft(session, game_id)
    if not deleted_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado o ya eliminado.")
    return


# --- Endpoints para Reseñas ---

@app.post("/api/v1/reviews", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    game_id: int = Query(..., description="ID del juego al que pertenece la reseña"),
    review: ReviewBase = Body(..., description="Datos de la reseña"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    db_review = operations.create_review_in_db(session, review, game_id, current_user.id)
    if not db_review:
        raise HTTPException(status_code=400, detail="No se pudo crear la reseña. Asegúrate de que el game_id sea válido.")
    return db_review

@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails)
async def get_review_by_id_endpoint(
    review_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    review = operations.get_review_with_details(session, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o eliminada.")
    return review

@app.get("/api/v1/reviews", response_model=List[ReviewReadWithDetails])
async def get_reviews_endpoint(
    game_id: Optional[int] = Query(None, description="Filtrar reseñas por ID de juego"),
    user_id: Optional[int] = Query(None, description="Filtrar reseñas por ID de usuario"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    if game_id:
        reviews = operations.get_reviews_for_game(session, game_id)
    elif user_id:
        reviews = operations.get_reviews_by_user(session, user_id)
    else:
        # Si no se especifica game_id ni user_id, y hay un usuario autenticado,
        # se obtienen las reseñas del usuario actual.
        if current_user:
            reviews = operations.get_reviews_by_user(session, current_user.id)
        else:
            # Opcional: Podrías retornar un error o todas las reseñas públicas si las hubiera
            # Por ahora, si no hay filtros y no hay usuario autenticado, devuelve vacío o error
            raise HTTPException(status_code=400, detail="Se requiere un ID de juego o usuario, o autenticación para ver las reseñas.")
            
    # Para incluir detalles del juego y usuario en cada reseña,
    # necesitamos procesar cada reseña individualmente.
    # Esto puede ser ineficiente para muchas reseñas.
    reviews_with_details = []
    for review in reviews:
        review_details = operations.get_review_with_details(session, review.id)
        if review_details:
            reviews_with_details.append(review_details)
    return reviews_with_details


@app.put("/api/v1/reviews/{review_id}", response_model=ReviewRead)
async def update_review_endpoint(
    review_id: int,
    review_update: ReviewBase,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user)
):
    # Verificar que el usuario actual es el autor de la reseña o un administrador
    existing_review = operations.get_review_by_id(session, review_id)
    if not existing_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o eliminada.")
    
    if existing_review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para modificar esta reseña.")
    
    updated_review = operations.update_review_in_db(session, review_id, review_update)
    if not updated_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o eliminada.")
    return updated_review

@app.delete("/api/v1/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review_endpoint(
    review_id: int,
    session: Session = Depends(database.get_session),
    current_user: User = Depends(auth.get_current_active_user)
):
    # Verificar que el usuario actual es el autor de la reseña o un administrador
    existing_review = operations.get_review_by_id(session, review_id)
    if not existing_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o eliminada.")
    
    if existing_review.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos para eliminar esta reseña.")

    deleted_review = operations.delete_review_soft(session, review_id)
    if not deleted_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada o ya eliminada.")
    return


# --- Endpoints para Player Activity ---

@app.post("/api/v1/player-activity", response_model=PlayerActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_player_activity(
    activity: PlayerActivityCreate,
    session: Session = Depends(database.get_session), # Aunque sea mock, mantenemos la dependencia
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    # Para el mock, no es necesario pasar la sesión a operations
    db_activity = operations.create_player_activity_mock(activity.model_dump())
    return db_activity

@app.get("/api/v1/player-activity/user/{user_id}", response_model=List[PlayerActivityResponse])
async def get_player_activity_by_user_endpoint(
    user_id: int,
    session: Session = Depends(database.get_session), # Mantenemos la dependencia
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    # Filtrar por player_id en el mock, ya que no hay una relación directa con User
    # En un sistema real, player_id probablemente sería el user_id.
    activities = [
        activity for activity in operations.get_all_player_activity_mock()
        if activity.player_id == user_id
    ]
    return activities


# --- Endpoints de la API de Steam (proxy) ---

@app.get("/api/v1/steam/app_list")
async def get_steam_app_list_endpoint(
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    """
    Obtiene la lista completa de aplicaciones de Steam.
    """
    try:
        # Se asume que este endpoint se llama a la API de Steam a través de operations.py
        # y no directamente aquí para manejar la clave de API.
        app_list = await operations.get_steam_app_list()
        if app_list:
            return app_list
        raise HTTPException(status_code=404, detail="No se pudo obtener la lista de aplicaciones de Steam.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener lista de Steam: {e}")


@app.get("/api/v1/steam/game_details/{app_id}")
async def get_steam_game_details_endpoint(
    app_id: int,
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    """
    Obtiene detalles de un juego de Steam por su App ID.
    """
    try:
        details = await operations.get_game_details_from_steam_api(app_id)
        if details:
            return details
        raise HTTPException(status_code=404, detail=f"No se encontraron detalles para el App ID {app_id}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener detalles de Steam: {e}")


@app.get("/api/v1/steam/current_players/{app_id}")
async def get_steam_current_players_endpoint(
    app_id: int,
    current_user: User = Depends(auth.get_current_active_user) # Requiere autenticación
):
    """
    Obtiene el número de jugadores actuales para un App ID de Steam.
    """
    player_count = await operations.get_current_players_for_app(app_id)
    if player_count is not None:
        return {"app_id": app_id, "player_count": player_count}
    raise HTTPException(status_code=404, detail=f"No se pudo obtener el número de jugadores actuales para el App ID {app_id}. Asegúrate de que el App ID sea correcto y la STEAM_API_KEY esté configurada.")


# --- Endpoint para Subir Imágenes ---
@app.post("/api/v1/upload_image")
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(auth.get_current_user)): # Añadido current_user para que requiera auth
    """
    Endpoint para subir una imagen.
    En este demo, simula el guardado y retorna una URL temporal.
    """
    try:
        image_url = await operations.save_uploaded_image(file)
        if not image_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo procesar la imagen.")
        return {"filename": file.filename, "url": image_url, "message": "Imagen procesada. En producción, se guardaría de forma persistente."}
    except Exception as e:
        print(f"Error al procesar la imagen: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al procesar la imagen: {e}")
