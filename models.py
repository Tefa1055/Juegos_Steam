from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    email: str
    password_hash: str
    is_admin: bool = False
    reviews: List["Review"] = Relationship(back_populates="user")

class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    titulo: str
    categoria: str
    descripcion: Optional[str] = ""
    portada_url: Optional[str] = ""
    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    reviews: List["Review"] = Relationship(back_populates="game")

class Review(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(foreign_key="game.id")
    user_id: int = Field(foreign_key="user.id")
    titulo: str
    contenido: str
    rating: int
    imagen_url: Optional[str] = ""
    user: Optional[User] = Relationship(back_populates="reviews")
    game: Optional[Game] = Relationship(back_populates="reviews")
