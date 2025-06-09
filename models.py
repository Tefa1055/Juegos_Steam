# models.py
# Este archivo define los modelos de datos para la base de datos (SQLModel)
# y para la entrada/salida de la API (Pydantic).

from typing import List, Optional
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel # Asegúrate de que BaseModel esté aquí

# --- Game Models ---

class GameBase(SQLModel):
    """
    Define los campos base para un juego.
    Utilizado para creación y actualización.
    """
    title: str = Field(index=True) # Permite búsquedas rápidas por título
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[str] = None # Podría ser List[str] en un modelo más avanzado
    tags: Optional[str] = None   # Podría ser List[str]
    release_date: Optional[str] = None # O datetime.date
    price: Optional[float] = None
    steam_app_id: int = Field(unique=True, index=True) # **¡DEBE SER ÚNICO!**

class Game(GameBase, table=True):
    """
    Representa la tabla 'game' en la base de datos.
    Añade campos de la DB como 'id' y 'is_deleted'.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    is_deleted: bool = Field(default=False) # Para eliminación lógica (soft delete)

    # Relación con Review: un juego puede tener muchas reseñas
    reviews: List["Review"] = Relationship(back_populates="game")


class GameCreate(GameBase):
    """
    Modelo para la creación de un juego (lo que recibe la API en POST).
    Hereda de GameBase.
    """
    pass

class GameRead(GameBase):
    """
    Modelo para la lectura de un juego (lo que devuelve la API en GET/PUT).
    Incluye el 'id' y 'is_deleted' de la base de datos.
    """
    id: int
    is_deleted: bool

class GameUpdate(SQLModel):
    """
    Modelo para la actualización de un juego (campos opcionales).
    """
    title: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[str] = None
    tags: Optional[str] = None
    release_date: Optional[str] = None
    price: Optional[float] = None
    steam_app_id: Optional[int] = None # steam_app_id también podría ser actualizado si es necesario

class GameReadWithReviews(GameRead):
    """
    Modelo para leer un juego incluyendo sus reseñas asociadas.
    """
    reviews: List["ReviewReadWithDetails"] = [] # Usa ReviewReadWithDetails para evitar recursión circular


# --- User Models ---

class UserBase(SQLModel):
    """
    Define los campos base para un usuario.
    """
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)

class User(UserBase, table=True):
    """
    Representa la tabla 'user' en la base de datos.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str # Esto almacena el hash de la contraseña
    is_active: bool = Field(default=True)

    # Relación con Review: un usuario puede escribir muchas reseñas
    reviews: List["Review"] = Relationship(back_populates="user")

class UserCreate(UserBase):
    """
    Modelo para la creación de un usuario.
    Incluye la contraseña que se necesita para la creación.
    """
    password: str # Contraseña en texto plano para la entrada (NO se guarda así)

class UserRead(UserBase):
    """
    Modelo para la lectura de un usuario (lo que devuelve la API).
    """
    id: int
    is_active: bool

class UserReadWithReviews(UserRead):
    """
    Modelo para leer un usuario incluyendo sus reseñas.
    """
    reviews: List["ReviewReadWithDetails"] = []


# --- Review Models ---

class ReviewBase(SQLModel):
    """
    Define los campos base para una reseña.
    """
    review_text: str = Field(index=True)
    rating: Optional[int] = Field(default=None, ge=1, le=5) # Calificación de 1 a 5 estrellas
    image_filename: Optional[str] = None # Para guardar el nombre de un archivo de imagen si aplica

class Review(ReviewBase, table=True):
    """
    Representa la tabla 'review' en la base de datos.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    is_deleted: bool = Field(default=False)

    # Claves foráneas para las relaciones
    game_id: Optional[int] = Field(default=None, foreign_key="game.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)

    # Relaciones con Game y User
    game: Optional[Game] = Relationship(back_populates="reviews")
    user: Optional[User] = Relationship(back_populates="reviews")

class ReviewCreate(ReviewBase):
    """
    Modelo para la creación de una reseña.
    """
    pass # No necesita campos adicionales además de ReviewBase

class ReviewRead(ReviewBase):
    """
    Modelo para la lectura básica de una reseña.
    """
    id: int
    created_at: datetime
    is_deleted: bool
    game_id: Optional[int]
    user_id: Optional[int]

class ReviewReadWithDetails(ReviewBase):
    """
    Modelo para leer una reseña con detalles del juego y del usuario.
    Este modelo es para la salida de la API y no para la DB.
    """
    id: int
    created_at: datetime
    is_deleted: bool
    # Los campos game y user se rellenarán con los modelos de lectura respectivos
    game: Optional[GameRead] = None
    user: Optional[UserRead] = None


# --- PlayerActivity Models (Pydantic puros, no SQLModel) ---
# Estos modelos son para la actividad de jugadores si la manejas en memoria o con otra DB.

class PlayerActivityCreate(BaseModel):
    """
    Modelo para crear un registro de actividad de jugador.
    """
    player_id: int = Field(..., description="ID único del jugador.")
    game_id: int = Field(..., description="ID del juego.")
    activity_type: str = Field(..., description="Tipo de actividad (ej. 'play', 'purchase', 'achievement').")
    timestamp: datetime = Field(default_factory=datetime.now, description="Momento de la actividad.")
    details: Optional[dict] = Field(default_factory=dict, description="Detalles adicionales de la actividad (ej. score, item_id).")

class PlayerActivityResponse(PlayerActivityCreate):
    """
    Modelo para la respuesta de un registro de actividad de jugador.
    Añade un ID simulado para el mock.
    """
    id: int
    is_deleted: bool = False # Para la eliminación lógica en el mock