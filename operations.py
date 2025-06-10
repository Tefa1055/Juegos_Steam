# operations.py
# Este archivo contiene la lógica de negocio para interactuar con la base de datos
# y con los datos en memoria (mock), incluyendo la integración con la API de Steam.

import os
import httpx # Importar httpx para hacer peticiones HTTP
from typing import List, Optional
from datetime import datetime, date
from sqlmodel import Session, select, SQLModel
from fastapi import UploadFile # Importar UploadFile para manejo de archivos

# Importa todos los modelos de tu aplicación
import auth
from models import (
    Game, GameCreate, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserReadWithReviews,
    Review, ReviewBase, ReviewReadWithDetails,
    PlayerActivityCreate, PlayerActivityResponse
)

# Clave de API de Steam (¡En producción, esto DEBE ser una variable de entorno!)
STEAM_API_KEY = os.environ.get("STEAM_API_KEY")

# URLs base para diferentes APIs de Steam
STEAM_STORE_API_BASE_URL = "https://store.steampowered.com/api"
STEAM_WEB_API_BASE_URL = "https://api.steampowered.com"


# --- Operaciones para Games (Base de datos) ---

def create_game_in_db(session: Session, game_data: GameCreate) -> Game:
    """
    Crea un nuevo juego en la base de datos.
    """
    db_game = Game.model_validate(game_data)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

def get_all_games(session: Session) -> List[Game]:
    """
    Obtiene todos los juegos no eliminados de la base de datos.
    """
    games = session.exec(select(Game).where(Game.is_deleted == False)).all()
    return games

def get_game_by_id(session: Session, game_id: int) -> Optional[Game]:
    """
    Obtiene un juego por su ID si no está eliminado.
    """
    game = session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()
    return game

def get_game_by_steam_app_id(session: Session, steam_app_id: int) -> Optional[Game]:
    """
    Obtiene un juego por su Steam App ID si no está eliminado.
    """
    game = session.exec(select(Game).where(Game.steam_app_id == steam_app_id, Game.is_deleted == False)).first()
    return game

def get_game_with_reviews(session: Session, game_id: int) -> Optional[GameReadWithReviews]:
    """
    Obtiene un juego por su ID, incluyendo sus reseñas, si no está eliminado.
    """
    game = session.exec(
        select(Game).where(Game.id == game_id, Game.is_deleted == False)
    ).first()

    if game:
        return game
    return None

def filter_games_by_genre(session: Session, genre: str) -> List[Game]:
    """
    Filtra juegos por género (búsqueda de subcadena, insensible a mayúsculas/minúsculas).
    """
    games = session.exec(
        select(Game).where(Game.genres.ilike(f"%{genre}%"), Game.is_deleted == False)
    ).all()
    return games

def search_games_by_title(session: Session, query: str) -> List[Game]:
    """
    Busca juegos cuyos títulos contengan la cadena de consulta especificada en la base de datos.
    """
    games = session.exec(
        select(Game).where(Game.title.ilike(f"%{query}%"), Game.is_deleted == False)
    ).all()
    return games

def update_game(session: Session, game_id: int, game_update: GameUpdate) -> Optional[Game]:
    """
    Actualiza un juego existente por su ID.
    """
    game = session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()
    if game:
        game_data = game_update.model_dump(exclude_unset=True)
        for key, value in game_data.items():
            setattr(game, key, value)
        session.add(game)
        session.commit()
        session.refresh(game)
        return game
    return None

def delete_game_soft(session: Session, game_id: int) -> Optional[Game]:
    """
    Realiza una eliminación lógica (soft delete) de un juego.
    """
    game = session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()
    if game:
        game.is_deleted = True
        session.add(game)
        session.commit()
        session.refresh(game)
        return game
    return None

# --- Operaciones para Users (Incluye funciones de autenticación) ---

def create_user_in_db(session: Session, user_data: UserCreate, hashed_password: str) -> Optional[User]:
    """
    Crea un nuevo usuario en la base de datos.
    Retorna None si el username o email ya existen.
    """
    existing_user_by_username = session.exec(select(User).where(User.username == user_data.username)).first()
    existing_user_by_email = session.exec(select(User).where(User.email == user_data.email)).first()

    if existing_user_by_username or existing_user_by_email:
        return None

    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def get_all_users(session: Session) -> List[User]:
    """
    Obtiene todos los usuarios activos de la base de datos.
    """
    users = session.exec(select(User).where(User.is_active == True)).all()
    return users

def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    """
    Obtiene un usuario por su ID si está activo.
    """
    user = session.exec(select(User).where(User.id == user_id, User.is_active == True)).first()
    return user

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    """Obtiene un usuario por su nombre de usuario."""
    return session.exec(select(User).where(User.username == username)).first()

def get_user_with_reviews(session: Session, user_id: int) -> Optional[UserReadWithReviews]:
    """
    Obtiene un usuario por su ID, incluyendo sus reseñas, si está activo.
    """
    user = session.exec(
        select(User).where(User.id == user_id, User.is_active == True)
    ).first()
    if user:
        return user
    return None

def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    """Autentica un usuario verificando su nombre de usuario y contraseña."""
    user = get_user_by_username(session, username)
    if not user or not auth.verify_password(password, user.hashed_password):
        return None
    return user

# --- Operaciones para Reseñas ---

def create_review_in_db(session: Session, review_data: ReviewBase, game_id: int, user_id: int) -> Optional[Review]:
    """
    Crea una nueva reseña, asociándola a un juego y un usuario.
    """
    game = session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()
    user = session.exec(select(User).where(User.id == user_id, User.is_active == True)).first()

    if not game or not user:
        return None

    db_review = Review.model_validate(review_data, update={'game_id': game_id, 'user_id': user_id})
    session.add(db_review)
    session.commit()
    session.refresh(db_review)
    return db_review

def get_review_by_id(session: Session, review_id: int) -> Optional[Review]:
    """
    Obtiene una reseña por su ID si no está eliminada.
    """
    review = session.exec(select(Review).where(Review.id == review_id, Review.is_deleted == False)).first()
    return review

def get_review_with_details(session: Session, review_id: int) -> Optional[ReviewReadWithDetails]:
    """
    Obtiene una reseña por su ID, incluyendo detalles del juego y el usuario, si no está eliminada.
    """
    review = session.exec(
        select(Review).where(Review.id == review_id, Review.is_deleted == False)
    ).first()

    if review:
        if review.game:
            pass
        if review.user:
            pass
        return review
    return None


def get_reviews_for_game(session: Session, game_id: int) -> List[Review]:
    """
    Obtiene todas las reseñas no eliminadas para un juego específico.
    """
    reviews = session.exec(select(Review).where(Review.game_id == game_id, Review.is_deleted == False)).all()
    return reviews

def get_reviews_by_user(session: Session, user_id: int) -> List[Review]:
    """
    Obtiene todas las reseñas no eliminadas escritas por un usuario específico.
    """
    reviews = session.exec(select(Review).where(Review.user_id == user_id, Review.is_deleted == False)).all()
    return reviews

def update_review_in_db(session: Session, review_id: int, review_update: ReviewBase) -> Optional[Review]:
    """
    Actualiza una reseña existente.
    """
    review = session.exec(select(Review).where(Review.id == review_id, Review.is_deleted == False)).first()
    if review:
        review_data = review_update.model_dump(exclude_unset=True)
        for key, value in review_data.items():
            setattr(review, key, value)
        session.add(review)
        session.commit()
        session.refresh(review)
        return review
    return None

def delete_review_soft(session: Session, review_id: int) -> Optional[Review]:
    """
    Realiza una eliminación lógica (soft delete) de una reseña.
    """
    review = session.exec(select(Review).where(Review.id == review_id, Review.is_deleted == False)).first()
    if review:
        review.is_deleted = True
        session.add(review)
        session.commit()
        session.refresh(review)
        return review
    return None


# --- Operaciones para Actividad de Jugadores (PlayerActivity - Mock) ---
# Este es un mock simple, NO una base de datos persistente.

_player_activity_mock_db: List[PlayerActivityResponse] = []
_next_player_activity_id = 1

def get_all_player_activity_mock(include_deleted: bool = False) -> List[PlayerActivityResponse]:
    """
    Obtiene todos los registros de actividad de jugadores del mock.
    """
    if include_deleted:
        return _player_activity_mock_db
    return [activity for activity in _player_activity_mock_db if not activity.is_deleted]

def get_player_activity_by_id_mock(activity_id: int) -> Optional[PlayerActivityResponse]:
    """
    Obtiene un registro de actividad por su ID del mock.
    """
    for activity in _player_activity_mock_db:
        if activity.id == activity_id and not activity.is_deleted:
            return activity
    return None

def create_player_activity_mock(activity_data: dict) -> PlayerActivityResponse:
    """
    Crea un nuevo registro de actividad de jugador en el mock.
    """
    global _next_player_activity_id
    new_activity = PlayerActivityResponse(id=_next_player_activity_id, **activity_data)
    _player_activity_mock_db.append(new_activity)
    _next_player_activity_id += 1
    return new_activity

def update_player_activity_mock(activity_id: int, update_data: dict) -> Optional[PlayerActivityResponse]:
    """
    Actualiza un registro de actividad existente en el mock.
    """
    for i, activity in enumerate(_player_activity_mock_db):
        if activity.id == activity_id and not activity.is_deleted:
            updated_activity = activity.model_copy(update=update_data)
            _player_activity_mock_db[i] = updated_activity
            return updated_activity
    return None

def delete_player_activity_mock(activity_id: int) -> bool:
    """
    Realiza una eliminación lógica de un registro de actividad en el mock.
    """
    for activity in _player_activity_mock_db:
        if activity.id == activity_id and not activity.is_deleted:
            activity.is_deleted = True
            return True
    return False

# --- Operaciones para la API de Steam (MEJORADAS y NUEVAS) ---

async def get_steam_app_list() -> Optional[List[dict]]:
    """
    Obtiene la lista de todos los juegos disponibles en Steam (App ID y nombre).
    Este endpoint no requiere una clave de API.
    """
    url = f"{STEAM_WEB_API_BASE_URL}/ISteamApps/GetAppList/v2/"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=20.0) # Puede ser una lista grande
            response.raise_for_status()
            data = response.json()
            if data and data.get("applist") and data["applist"].get("apps"):
                return data["applist"]["apps"]
            return None
    except httpx.HTTPStatusError as e:
        print(f"🚨 Error de estado HTTP al llamar a GetAppList ({e.response.status_code}): {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Error de red/conexión al llamar a GetAppList: {e}")
        return None
    except Exception as e:
        print(f"🚨 Error inesperado al procesar la respuesta de GetAppList: {e}")
        return None

async def get_game_details_from_steam_api(app_id: int) -> Optional[dict]:
    """
    Obtiene detalles completos de un juego de la API de la tienda de Steam usando su App ID.
    Este endpoint devuelve imágenes y mucha más información.
    """
    # No se requiere STEAM_API_KEY para este endpoint de la tienda
    # Podemos especificar el idioma y el país para la descripción y el formato de precio
    url = f"{STEAM_STORE_API_BASE_URL}/appdetails?appids={app_id}&cc=us&l=en" 

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=15.0) # Aumentar el timeout por si acaso
            response.raise_for_status()

            data = response.json()
            
            if data and str(app_id) in data and data[str(app_id)].get("success"):
                game_data = data[str(app_id)]["data"]
                
                # Extraer y formatear los datos
                extracted_data = {
                    "app_id": app_id,
                    "name": game_data.get("name"),
                    "header_image": game_data.get("header_image"),
                    "short_description": game_data.get("short_description"),
                    "developers": game_data.get("developers"),
                    "publishers": game_data.get("publishers"),
                    "price": None, # Inicializar a None
                    "genres": [g.get("description") for g in game_data.get("genres", []) if g.get("description")],
                    "release_date": game_data.get("release_date", {}).get("date") # Fecha de lanzamiento como string
                }

                # Manejar el precio
                price_overview = game_data.get("price_overview")
                if price_overview:
                    extracted_data["price"] = price_overview.get('final_formatted') # Ya viene formateado con el símbolo de moneda
                elif game_data.get("is_free"):
                    extracted_data["price"] = "Free to Play"


                return extracted_data
            return None # Si no se encontró el App ID o la solicitud no fue exitosa
    except httpx.HTTPStatusError as e:
        print(f"🚨 Error de estado HTTP al llamar a la API de Steam Store ({e.response.status_code}): {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Error de red/conexión al llamar a la API de Steam Store: {e}")
        return None
    except Exception as e:
        print(f"🚨 Error inesperado al procesar la respuesta de la API de Steam Store: {e}")
        return None

async def get_current_players_for_app(app_id: int) -> Optional[int]:
    """
    Obtiene el número actual de jugadores para un App ID dado.
    Requiere una clave de API de Steam Web (STEAM_API_KEY).
    """
    if not STEAM_API_KEY:
        print("🚨 Advertencia: STEAM_API_KEY no configurada. No se puede acceder a la API de Steam para jugadores.")
        return None
    
    url = f"{STEAM_WEB_API_BASE_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?key={STEAM_API_KEY}&appid={app_id}"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            if data and data.get("response") and data["response"].get("result") == 1:
                return data["response"].get("player_count")
            return None
    except httpx.HTTPStatusError as e:
        print(f"🚨 Error de estado HTTP al llamar a GetNumberOfCurrentPlayers ({e.response.status_code}): {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Error de red/conexión al llamar a GetNumberOfCurrentPlayers: {e}")
        return None
    except Exception as e:
        print(f"🚨 Error inesperado al procesar la respuesta de GetNumberOfCurrentPlayers: {e}")
        return None


async def add_steam_game_to_db(session: Session, app_id: int) -> Optional[Game]:
    """
    Obtiene los detalles de un juego de Steam y lo guarda en la base de datos local.
    Verifica si el juego ya existe por steam_app_id.
    """
    # 1. Obtener detalles del juego de Steam API
    steam_game_details = await get_game_details_from_steam_api(app_id)
    if not steam_game_details:
        print(f"No se pudieron obtener detalles de Steam para App ID: {app_id}")
        return None

    # 2. Verificar si el juego ya existe en nuestra DB por steam_app_id
    existing_game = get_game_by_steam_app_id(session, app_id)
    if existing_game:
        print(f"Juego con Steam App ID {app_id} ya existe en la base de datos local (ID: {existing_game.id}).")
        return existing_game # Retorna el juego existente

    # 3. Mapear los detalles de Steam a GameCreate
    # Asegúrate de que los tipos de datos coincidan con tu modelo GameCreate
    try:
        # La fecha de lanzamiento viene como string "MMM DD, YYYY" o "YYYY"
        # Necesitamos convertirla a date o manejarla como string si el modelo lo permite
        release_date_str = steam_game_details.get("release_date")
        parsed_release_date = None
        if release_date_str and release_date_str != "Coming Soon":
            try:
                # Intenta parsear "Month Day, Year"
                parsed_release_date = datetime.strptime(release_date_str, "%b %d, %Y").date()
            except ValueError:
                try:
                    # Intenta parsear "YYYY" si el formato es solo el año
                    parsed_release_date = datetime.strptime(release_date_str, "%Y").date()
                except ValueError:
                    print(f"Advertencia: No se pudo parsear la fecha de lanzamiento '{release_date_str}' para {app_id}. Guardando como None.")
                    parsed_release_date = None

        game_data_for_db = GameCreate(
            title=steam_game_details.get("name", f"Juego Steam App ID {app_id}"),
            developer=", ".join(steam_game_details.get("developers", [])),
            publisher=", ".join(steam_game_details.get("publishers", [])),
            genres=", ".join(steam_game_details.get("genres", [])),
            release_date=parsed_release_date,
            price=float(steam_game_details.get("price", "0").replace("$", "").replace(",", "")) if steam_game_details.get("price") and steam_game_details.get("price") != "Free to Play" else 0.0, # Convertir precio a float, manejar "Free to Play"
            steam_app_id=app_id
        )
    except Exception as e:
        print(f"🚨 Error al mapear detalles de Steam a GameCreate para App ID {app_id}: {e}")
        return None

    # 4. Guardar en la base de datos
    db_game = Game.model_validate(game_data_for_db)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

# --- Nueva Operación para Subir Imágenes (SIMULADA) ---

async def save_uploaded_image(file: UploadFile) -> Optional[str]:
    """
    SIMULA la carga de una imagen.
    En un entorno de producción, aquí guardarías el archivo en un almacenamiento persistente
    (ej. S3, Google Cloud Storage) y retornarías la URL pública del archivo.
    Para esta demostración, simplemente generamos una URL basada en el nombre del archivo.
    """
    if not file.filename:
        return None
    
    # Para la demostración, retornamos una URL simulada.
    # Podrías usar un servicio de CDN o tu propio servidor de archivos en producción.
    simulated_url = f"/uploads/{file.filename.replace(' ', '_')}" # Reemplazar espacios por guiones bajos
    print(f"📦 Imagen simuladamente 'guardada': {simulated_url}")
    return simulated_url