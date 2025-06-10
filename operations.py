# operations.py
# Este archivo contiene la lógica de negocio para interactuar con la base de datos
# y con los datos en memoria (mock).

from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select, SQLModel
from sqlmodel.select import Select, selectinload # Import selectinload

# Importa todos los modelos de tu aplicación
import auth # <-- NUEVA IMPORTACIÓN para usar funciones de hasheo/verificación
from models import (
    Game, GameCreate, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserReadWithReviews,
    Review, ReviewBase, ReviewReadWithDetails,
    PlayerActivityCreate, PlayerActivityResponse # Para el mock
)

# --- Operaciones para Games ---

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

def update_game_in_db(session: Session, game_id: int, game_data: GameUpdate) -> Optional[Game]:
    """
    Actualiza un juego existente en la base de datos.
    """
    db_game = session.get(Game, game_id)
    if not db_game or db_game.is_deleted:
        return None
    
    # Actualizar solo los campos que se proporcionan en game_data
    game_data_dict = game_data.model_dump(exclude_unset=True)
    for key, value in game_data_dict.items():
        setattr(db_game, key, value)
    
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

def delete_game_in_db(session: Session, game_id: int) -> bool:
    """
    Realiza una eliminación lógica de un juego.
    """
    db_game = session.get(Game, game_id)
    if not db_game or db_game.is_deleted:
        return False
    db_game.is_deleted = True
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return True

# --- Operaciones para Users ---

def create_user_in_db(session: Session, user_data: UserCreate) -> User:
    """
    Crea un nuevo usuario en la base de datos con la contraseña hasheada.
    """
    hashed_password = auth.get_password_hash(user_data.password)
    db_user = User(username=user_data.username, email=user_data.email, hashed_password=hashed_password)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    """
    Obtiene un usuario por su nombre de usuario.
    """
    return session.exec(select(User).where(User.username == username)).first()

def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    """
    Obtiene un usuario por su ID.
    """
    return session.exec(select(User).where(User.id == user_id)).first()

def get_all_users(session: Session) -> List[User]:
    """
    Obtiene todos los usuarios de la base de datos.
    """
    return session.exec(select(User)).all()


# --- Operaciones para Reviews ---

def create_review_in_db(session: Session, review_data: ReviewCreate, game_id: int, user_id: int) -> Review:
    """
    Crea una nueva reseña en la base de datos, asociándola a un juego y un usuario.
    """
    db_review = Review.model_validate(review_data, update={"game_id": game_id, "user_id": user_id})
    session.add(db_review)
    session.commit()
    session.refresh(db_review)
    return db_review

def get_review_by_id(session: Session, review_id: int) -> Optional[Review]:
    """
    Obtiene una reseña por su ID si no está eliminada, cargando el juego y el usuario.
    """
    # Usamos selectinload para cargar las relaciones 'game' y 'user' de forma eficiente
    statement = select(Review).where(Review.id == review_id, Review.is_deleted == False).options(
        selectinload(Review.game), selectinload(Review.user)
    )
    return session.exec(statement).first()

def get_reviews_by_game_id_from_db(session: Session, game_id: int) -> List[Review]:
    """
    Obtiene todas las reseñas no eliminadas para un juego específico, cargando también el usuario.
    """
    # Asegúrate de cargar tanto el juego como el usuario para ReviewReadWithDetails
    statement = select(Review).where(Review.game_id == game_id, Review.is_deleted == False).options(
        selectinload(Review.game), selectinload(Review.user)
    )
    return session.exec(statement).all()

def get_reviews_by_user_id_from_db(session: Session, user_id: int) -> List[Review]:
    """
    Obtiene todas las reseñas no eliminadas de un usuario específico, cargando también el juego.
    """
    # Asegúrate de cargar tanto el usuario como el juego para ReviewReadWithDetails
    statement = select(Review).where(Review.user_id == user_id, Review.is_deleted == False).options(
        selectinload(Review.user), selectinload(Review.game)
    )
    return session.exec(statement).all()


# --- MOCK DB para PlayerActivity (sin persistencia en DB) ---
_player_activity_mock_db: List[PlayerActivityResponse] = []
_next_player_activity_id = 1

def get_player_activity_mock(activity_id: int) -> Optional[PlayerActivityResponse]:
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
