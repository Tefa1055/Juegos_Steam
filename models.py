from typing import List, Optional
from datetime import datetime, date
from sqlmodel import Field, SQLModel, Relationship
from pydantic import BaseModel

# --- Game Models ---

class GameBase(SQLModel):
    title: str = Field(index=True)
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[str] = None
    release_date: Optional[date] = None  # Corregido de str a date
    price: Optional[float] = None
    steam_app_id: int = Field(unique=True, index=True)
    image_filename: Optional[str] = None # ¡NUEVO CAMBIO AQUÍ! Campo para el nombre del archivo de imagen

class Game(GameBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    is_deleted: bool = Field(default=False)

    reviews: List["Review"] = Relationship(back_populates="game")

class GameCreate(GameBase):
    pass

class GameRead(GameBase):
    id: int
    is_deleted: bool

class GameUpdate(SQLModel):
    title: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[str] = None
    release_date: Optional[date] = None  # Corregido de str a date
    price: Optional[float] = None
    steam_app_id: Optional[int] = None

class GameReadWithReviews(GameRead):
    reviews: List["ReviewReadWithDetails"] = []

# --- User Models ---

class UserBase(SQLModel):
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_admin: bool = Field(default=False)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = Field(default=True)
    is_deleted: bool = Field(default=False)

    reviews: List["Review"] = Relationship(back_populates="user")

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    is_deleted: bool

class UserReadWithReviews(UserRead):
    reviews: List["ReviewReadWithDetails"] = []

# --- Review Models ---

class ReviewBase(SQLModel):
    review_text: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5) # Valoración de 1 a 5

class Review(ReviewBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.now)
    is_deleted: bool = Field(default=False)

    game_id: Optional[int] = Field(default=None, foreign_key="game.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)

    game: Optional["Game"] = Relationship(back_populates="reviews")
    user: Optional["User"] = Relationship(back_populates="reviews")

class ReviewCreate(ReviewBase):
    pass

class ReviewRead(ReviewBase):
    id: int
    created_at: datetime
    is_deleted: bool
    game_id: Optional[int]
    user_id: Optional[int]

class ReviewReadWithDetails(ReviewBase):
    id: int
    created_at: datetime
    is_deleted: bool
    game: Optional[GameRead] = None  # Add this line to include game details
    user: Optional[UserRead] = None

# --- PlayerActivity Models ---

class PlayerActivityCreate(BaseModel):
    player_id: int
    game_id: int
    activity_type: str # Ej: "played", "purchased", "wishlisted"
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[str] = None

class PlayerActivityResponse(PlayerActivityCreate):
    id: int

# --- Token Model (para autenticación) ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None