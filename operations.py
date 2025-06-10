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
            steam_app_id=app_id,
            image_filename=steam_game_details.get("header_image") # Guardar la URL de la imagen del encabezado
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

}

{
type: uploaded file
fileName: auth.py
fullText:
from datetime import datetime, timedelta
from typing import Optional
import os # Importar os para leer variables de entorno

from passlib.context import CryptContext # Para hashear contraseñas
from jose import JWTError, jwt # Para JWT (JSON Web Tokens)

# --- Configuración de Seguridad ---
# Necesitas una clave secreta para firmar tus JWTs.
# ¡IMPORTANTE! En un entorno de producción, esto DEBE ser una variable de entorno segura,
# NO un string codificado aquí.
SECRET_KEY = os.environ.get("SECRET_KEY", "Jeffthekiller789")
ALGORITHM = "HS256" # Algoritmo de encriptación para el JWT
ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Tiempo de expiración del token de acceso

# Contexto para hashear y verificar contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Funciones de Contraseña ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si una contraseña en texto plano coincide con una contraseña hasheada."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera el hash de una contraseña en texto plano."""
    return pwd_context.hash(password)

# --- Funciones de JWT ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un nuevo token de acceso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica y valida un token de acceso JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None # Token inválido o expirado

}

{
type: uploaded file
fileName: requirements.txt
fullText:
fastapi==0.110.0
uvicorn==0.23.2
pydantic==2.6.4
typing-extensions==4.12.1
sqlmodel
passlib[bcrypt]==1.7.4  # Versión corregida para compatibilidad
bcrypt>=4.0.0           # Asegura una versión compatible de bcrypt
python-jose[cryptography]
python-multipart
psycopg2-binary
httpx # Nueva dependencia para hacer peticiones HTTP (para la API de Steam)

}

{
type: uploaded file
fileName: database.py
fullText:
from sqlmodel import create_engine, Session, SQLModel
import os

# Obtener la URL de la base de datos desde la variable de entorno
DATABASE_URL = os.environ.get("DATABASE_URL")

# Crear el engine de la base de datos según el entorno
if DATABASE_URL:
    # PostgreSQL en Render
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print("DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    # SQLite en entorno local
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")

# Crear las tablas
def create_db_and_tables():
    print("DEBUG: Intentando crear tablas de la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas de la base de datos creadas/verificadas.")

# Sesión para operaciones CRUD
def get_session():
    with Session(engine) as session:
        yield session

}
Claro, entiendo perfectamente la urgencia y la frustración cuando la aplicación no se inicia en Render. El error `RuntimeError: Directory 'uploads' does not exist` es engañoso porque el código que agregamos para crear el directorio en `on_startup` está correcto, **pero se ejecuta demasiado tarde.**

FastAPI intenta montar los archivos estáticos (la línea `app.mount(...)`) en el momento en que se carga el archivo `main.py`. La función `@app.on_event("startup")` se ejecuta *después* de que la aplicación ya ha intentado montar todo.

**La solución es simple: debemos asegurarnos de que el directorio `uploads` exista *antes* de que FastAPI intente montarlo.**

Aquí tienes el archivo `main.py` corregido. El cambio clave es mover la creación del directorio `uploads` justo después de su definición, antes de la inicialización de `FastAPI` y el `app.mount`.

---


```python
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

# --- ¡CAMBIO CRÍTICO AQUÍ! ---
# Asegurar que el directorio 'uploads' exista ANTES de que FastAPI intente montarlo.
if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR, exist_ok=True) # Añadir exist_ok=True por si acaso
    print(f"DEBUG: Directorio '{UPLOADS_DIR}' creado al inicio del módulo.")

app = FastAPI(
    title="API de Videojuegos de Steam",
    description="Servicio para consultar y gestionar información de juegos, usuarios, reseñas y actividad de jugadores en Steam.",
    version="1.0.0",
)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "[https://juegos-steam-s8wn.onrender.com](https://juegos-steam-s8wn.onrender.com)", # Tu dominio de Render
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
    # Este código se ejecuta DESPUÉS de que el app.mount ya se ha intentado.
    # Aquí solo necesitamos crear las tablas de la base de datos.
    database.create_db_and_tables()
    print("DEBUG: Tablas de la base de datos creadas/verificadas en el startup event.")


# Endpoint para servir el frontend (asume que 'index.html' está en la raíz del proyecto)
@app.get("/")
async def read_root():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# Montar el directorio de archivos estáticos para las imágenes subidas
# Esto ahora se ejecutará DESPUÉS de que el directorio haya sido creado arriba.
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
        developer=", ".join(steam_game_details.get("developers", [])), # Unir lista de desarrolladores
        publisher=", ".join(steam_game_details.get("publishers", [])), # Unir lista de publishers
        genres=", ".join(steam_game_details.get("genres", [])), # Unir lista de géneros
        release_date=datetime.strptime(steam_game_details["release_date"], "%b %d, %Y").date() if "release_date" in steam_game_details and steam_game_details["release_date"] != "Coming Soon" else None,
        price=float(steam_game_details.get("price", "0").replace("$", "").replace(",", "")) if steam_game_details.get("price") and steam_game_details.get("price") != "Free to Play" else 0.0, # Convertir precio a float, manejar "Free to Play"
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
