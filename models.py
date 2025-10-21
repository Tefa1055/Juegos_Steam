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
    release_date: Optional[date] = None
    price: Optional[float] = None
    steam_app_id: int = Field(unique=True, index=True)

class Game(GameBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    is_deleted: bool = Field(default=False)

    # 🔒 NUEVO: dueño del juego (si es None, nadie puede editar/borrar)
    owner_id: Optional[int] = Field(
        default=None,
        foreign_key="user.id",
        index=True
    )

    # (Opcional) relación hacia el dueño
    owner: Optional["User"] = Relationship(back_populates="games")

    reviews: List["Review"] = Relationship(back_populates="game")

class GameCreate(GameBase):
    # 👇 Importante: NO exponemos owner_id aquí (lo fija el backend con el user logueado)
    pass

class GameRead(GameBase):
    id: int
    is_deleted: bool
    # (Opcional, útil para debug/mostrar) 
    owner_id: Optional[int] = None

class GameUpdate(SQLModel):
    title: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    genres: Optional[str] = None
    release_date: Optional[date] = None
    price: Optional[float] = None
    steam_app_id: Optional[int] = None
    # 👇 No permitimos cambiar owner_id desde el cliente
    # owner_id: Optional[int] = None  # NO incluir

class GameReadWithReviews(GameRead):
    reviews: List["ReviewReadWithDetails"] = []

# --- User Models ---

class UserBase(SQLModel):
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    is_active: bool = Field(default=True)

    reviews: List["Review"] = Relationship(back_populates="user")
    # 🔗 Relación inversa: juegos que posee este usuario
    games: List[Game] = Relationship(back_populates="owner")

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    is_active: bool

class UserReadWithReviews(UserRead):
    reviews: List["ReviewReadWithDetails"] = []

# --- Review Models ---

class ReviewBase(SQLModel):
    review_text: str = Field(index=True)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    image_filename: Optional[str] = None

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
    game: Optional[GameRead] = None
    user: Optional[UserRead] = None

# --- PlayerActivity Models ---

class PlayerActivityCreate(BaseModel):
    player_id: int
    game_id: int
    activity_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[dict] = Field(default_factory=dict)

class PlayerActivityResponse(PlayerActivityCreate):
    id: int
    is_deleted: bool = False
