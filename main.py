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

# ✅ Endpoint para servir index.html desde la raíz
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

# --- Desde aquí continúan tus endpoints de juegos, usuarios, reseñas y actividad ---
# ✅ Ya están bien definidos en tu versión anterior, puedes mantenerlos sin cambios.
# Asegúrate de no tener el endpoint `/` comentado o eliminado nuevamente.


# --- Endpoints para Juegos (Games) ---

@app.post("/api/v1/juegos", response_model=GameRead, status_code=status.HTTP_201_CREATED, summary="Crear nuevo Juego")
def create_new_game(
    game: GameCreate = Body(..., description="Datos del juego a crear. **¡Recuerda cambiar 'steam_app_id' cada vez!"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuevo juego en la base de datos. Solo usuarios autenticados pueden hacerlo.
    **Importante:** Asegúrate de que 'steam_app_id' sea único para cada juego que crees.
    """
    try:
        created_game = operations.create_game_in_db(session=session, game_data=game)
        return created_game
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No se pudo crear el juego, verifica si el steam_app_id ya existe u otro error: {e}")

@app.get("/api/v1/juegos", response_model=List[GameRead], summary="Listado de todos los Juegos")
def read_all_games(
    session: Session = Depends(database.get_session)
):
    """
    Obtiene una lista de todos los videojuegos disponibles en la base de datos (no eliminados lógicamente).
    """
    games = operations.get_all_games(session=session)
    return games

@app.get("/api/v1/juegos/ids", response_model=List[int], summary="Obtener solo los IDs de los Juegos (Ordenados)")
def get_all_game_ids(
    session: Session = Depends(database.get_session)
):
    """
    Obtiene una lista de todos los IDs de los videojuegos disponibles en la base de datos,
    ordenados de forma ascendente y sin duplicados.
    """
    game_ids = session.exec(select(Game.id).where(Game.is_deleted == False)).all()
    return sorted(list(game_ids))

@app.get("/api/v1/juegos/filtrar", response_model=List[GameRead], summary="Filtrar juegos por Género")
def filter_games(
    genre: str = Query(..., description="Género por el que filtrar los juegos. Ej: Action, RPG."),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene una lista de juegos filtrada por el género especificado desde la base de datos.
    """
    filtered_games = operations.filter_games_by_genre(session=session, genre=genre)
    return filtered_games

@app.get("/api/v1/juegos/buscar", response_model=List[GameRead], summary="Buscar juegos por Título")
def search_games(
    q: str = Query(..., description="Palabra clave o frase para buscar en el título del juego. Ej: Grand Theft Auto."),
    session: Session = Depends(database.get_session)
):
    """
    Busca juegos cuyos títulos contengan la cadena de consulta especificada en la base de datos.
    """
    found_games = operations.search_games_by_title(session=session, query=q)
    return found_games

@app.get("/api/v1/juegos/{id_juego}", response_model=GameReadWithReviews, summary="Detalle de Juego por ID (con reseñas)")
def read_game_by_id(
    id_juego: int = Path(..., description="ID único del juego a obtener"),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene los detalles de un juego específico utilizando su ID, incluyendo sus reseñas asociadas.
    Retorna 404 Not Found si el juego no existe o está marcado como eliminado lógicamente.
    """
    game = operations.get_game_with_reviews(session=session, game_id=id_juego)
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o eliminado.")
    return game

@app.put("/api/v1/juegos/{id_juego}", response_model=GameRead, summary="Actualizar Juego por ID")
def update_existing_game(
    id_juego: int = Path(..., description="ID único del juego a actualizar"),
    update_data: GameUpdate = Body(..., description="Datos para actualizar el juego"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza los datos de un juego existente por su ID en la base de datos. Solo usuarios autenticados.
    Retorna 404 si el juego no existe o está eliminado lógicamente.
    """
    updated_game = operations.update_game(session=session, game_id=id_juego, game_update=update_data)
    if not updated_game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o eliminado.")
    return updated_game

@app.delete("/api/v1/juegos/{id_juego}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar Juego (Lógico) por ID")
def delete_existing_game(
    id_juego: int = Path(..., description="ID único del juego a eliminar lógicamente"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Marca un juego existente como eliminado lógicamente por su ID (Soft Delete) en la base de datos.
    Solo usuarios autenticados pueden hacerlo.
    Retorna 404 si el juego no existe o ya estaba marcado como eliminado.
    Retorna 204 No Content si la eliminación lógica fue exitosa.
    """
    deleted_game = operations.delete_game_soft(session=session, game_id=id_juego)
    if not deleted_game:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Juego no encontrado o ya eliminado.")
    return

# --- Endpoints para Usuarios (Users) ---

@app.post("/api/v1/usuarios", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Crear nuevo Usuario")
def create_new_user(
    user_data: UserCreate = Body(..., description="Datos del usuario a crear (username, email, password)"),
    session: Session = Depends(database.get_session)
):
    """
    Crea un nuevo usuario en la base de datos con la contraseña hasheada.
    """
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = operations.create_user_in_db(session=session, user_data=user_data, hashed_password=hashed_password)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nombre de usuario o email ya registrado.")
    return db_user

@app.get("/api/v1/usuarios", response_model=List[UserRead], summary="Listado de todos los Usuarios")
def read_all_users(
    session: Session = Depends(database.get_session)
):
    """
    Obtiene una lista de todos los usuarios registrados en la base de datos.
    """
    users = operations.get_all_users(session=session)
    return users

@app.get("/api/v1/usuarios/{user_id}", response_model=UserReadWithReviews, summary="Detalle de Usuario por ID (con reseñas)")
def read_user_by_id(
    user_id: int = Path(..., description="ID único del usuario a obtener"),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene los detalles de un usuario específico utilizando su ID, incluyendo sus reseñas.
    Retorna 404 Not Found si el usuario no existe.
    """
    user = operations.get_user_with_reviews(session=session, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado.")
    return user

# --- Endpoint de Login para obtener Token ---
@app.post("/token", summary="Obtener Token de Acceso para Autenticación")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(database.get_session)
):
    user = operations.authenticate_user(session, form_data.username, form_data.password)
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

# --- Endpoints para Reseñas (Reviews) ---

@app.post("/api/v1/reviews", response_model=Review, status_code=status.HTTP_201_CREATED, summary="Crear nueva Reseña")
def create_new_review(
    review_data: ReviewBase = Body(..., description="Datos de la reseña (review_text, rating, etc.)"),
    game_id: int = Query(..., description="ID del juego al que se asocia la reseña"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Crea una nueva reseña en la base de datos para un juego y el usuario autenticado.
    Asegúrate de que el juego exista y sea válido. El user_id se tomará del token.
    """
    created_review = operations.create_review_in_db(session=session, review_data=review_data, game_id=game_id, user_id=current_user.id)
    if not created_review:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo crear la reseña. Verifique que el juego exista y esté activo.")
    return created_review

@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails, summary="Detalle de Reseña por ID (con detalles de juego/usuario)")
def read_review_by_id(
    review_id: int = Path(..., description="ID único de la reseña a obtener"),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene los detalles de una reseña específica por su ID, incluyendo los detalles del juego y el usuario.
    Retorna 404 Not Found si la reseña no existe o está eliminada lógicamente.
    """
    review = operations.get_review_with_details(session=session, review_id=review_id)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada o eliminada.")
    return review

@app.get("/api/v1/juegos/{game_id}/reviews", response_model=List[Review], summary="Listado de Reseñas para un Juego")
def read_reviews_for_game(
    game_id: int = Path(..., description="ID del juego para el cual se quieren obtener las reseñas"),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene todas las reseñas (no eliminadas lógicamente) para un juego específico.
    """
    reviews = operations.get_reviews_for_game(session=session, game_id=game_id)
    return reviews

@app.get("/api/v1/usuarios/{user_id}/reviews", response_model=List[Review], summary="Listado de Reseñas por Usuario")
def read_reviews_by_user(
    user_id: int = Path(..., description="ID del usuario del cual se quieren obtener las reseñas"),
    session: Session = Depends(database.get_session)
):
    """
    Obtiene todas las reseñas (no eliminadas lógicamente) escritas por un usuario específico.
    """
    reviews = operations.get_reviews_by_user(session=session, user_id=user_id)
    return reviews

@app.put("/api/v1/reviews/{review_id}", response_model=Review, summary="Actualizar Reseña por ID")
def update_existing_review(
    review_id: int = Path(..., description="ID único de la reseña a actualizar"),
    review_update: ReviewBase = Body(..., description="Datos para actualizar la reseña"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza los datos de una reseña existente en la base de datos. Solo el usuario autenticado.
    """
    review_to_update = operations.get_review_by_id(session, review_id)
    if review_to_update and review_to_update.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para actualizar esta reseña.")

    updated_review = operations.update_review_in_db(session=session, review_id=review_id, review_update=review_update)
    if not updated_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada o eliminada.")
    return updated_review

@app.delete("/api/v1/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar Reseña (Lógico) por ID")
def delete_existing_review(
    review_id: int = Path(..., description="ID único de la reseña a eliminar lógicamente"),
    session: Session = Depends(database.get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Marca una reseña existente como eliminada lógicamente por su ID (Soft Delete).
    """
    review_to_delete = operations.get_review_by_id(session, review_id)
    if review_to_delete and review_to_delete.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para eliminar esta reseña.")

    deleted_review = operations.delete_review_soft(session=session, review_id=review_id)
    if not deleted_review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reseña no encontrada o ya eliminada.")
    return


# --- Endpoints para Actividad de Jugadores (PlayerActivity - Mock) ---

@app.get(
    "/api/v1/actividad_jugadores",
    response_model=List[PlayerActivityResponse],
    summary="Listado de Actividad de Jugadores (Mock)"
)
def read_all_player_activity(
    include_deleted: bool = Query(False, description="Incluir registros de actividad eliminados lógicamente en la respuesta."),
    current_user: User = Depends(get_current_user)
):
     """
    Obtiene la lista completa de registros de actividad de jugadores disponibles del mock.
    Solo usuarios autenticados.
    """
     activity_records = operations.get_all_player_activity_mock(include_deleted=include_deleted)
     return activity_records

@app.get(
    "/api/v1/actividad_jugadores/{id_actividad}",
    response_model=PlayerActivityResponse,
    summary="Detalle de Actividad por ID (Mock)"
)
def read_player_activity_by_id(
    id_actividad: int = Path(..., description="ID único del registro de actividad a obtener"),
    current_user: User = Depends(get_current_user)
):
    """
    Obtiene los detalles de un registro de actividad específico utilizando su ID del mock.
    Retorna 404 Not Found si el registro no existe o está marcado como eliminado.
    """
    activity = operations.get_player_activity_by_id_mock(id_actividad)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o eliminado.")
    return activity

@app.post(
    "/api/v1/actividad_jugadores",
    response_model=PlayerActivityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo Registro de Actividad (Mock)"
)
def create_new_player_activity(
    activity: PlayerActivityCreate = Body(..., description="Datos del registro de actividad a crear"),
    current_user: User = Depends(get_current_user)
):
    """
    Crea un nuevo registro de actividad de jugadores en el mock. Solo usuarios autenticados.
    """
    try:
        created_activity = operations.create_player_activity_mock(activity.model_dump())
        return created_activity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno del servidor al crear el registro de actividad: {e}")

@app.put(
    "/api/v1/actividad_jugadores/{id_actividad}",
    response_model=PlayerActivityResponse,
    summary="Actualizar Registro de Actividad por ID (Mock)"
)
def update_existing_player_activity(
    id_actividad: int = Path(..., description="ID único del registro de actividad a actualizar"),
    update_data: PlayerActivityCreate = Body(..., description="Datos para actualizar el registro de actividad"),
    current_user: User = Depends(get_current_user)
):
    """
    Actualiza los datos de un registro de actividad existente por su ID en el mock.
    Retorna 404 si el registro no existe o está marcado como eliminado.
    """
    try:
        updated_activity = operations.update_player_activity_mock(id_actividad, update_data.model_dump())
        if updated_activity is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o eliminado.")
        return updated_activity
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno del servidor al actualizar el registro de actividad: {e}")

@app.delete(
    "/api/v1/actividad_jugadores/{id_actividad}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar Registro de Actividad (Lógico) por ID (Mock)"
)
def delete_existing_player_activity(
    id_actividad: int = Path(..., description="ID único del registro de actividad a eliminar lógicamente"),
    current_user: User = Depends(get_current_user)
):
    """
    Marca un registro de actividad existente como eliminado lógicamente por su ID (Soft Delete) en el mock.
    Retorna 404 si el registro no existe o ya estaba marcado como eliminado.
    """
    try:
        deleted = operations.delete_player_activity_mock(id_actividad)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registro de actividad no encontrado o ya eliminado.")
        return
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno del servidor al eliminar el registro de actividad: {e}")
    