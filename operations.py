# operations.py
import os
import httpx
from typing import List, Optional
from datetime import datetime, date
from sqlmodel import Session, select, SQLModel
from fastapi import UploadFile
import aiofiles

import auth
from models import (
    Game, GameCreate, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserReadWithReviews,
    Review, ReviewBase, ReviewReadWithDetails,
    PlayerActivityCreate, PlayerActivityResponse
)

STEAM_API_KEY = os.environ.get("STEAM_API_KEY")
STEAM_STORE_API_BASE_URL = "https://store.steampowered.com/api"
STEAM_WEB_API_BASE_URL = "https://api.steampowered.com"


# --- Game Operations (Database) ---

def create_game_in_db(session: Session, game_data: GameCreate) -> Game:
    """Creates a new game in the database."""
    db_game = Game.model_validate(game_data)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

def get_all_games(session: Session, skip: int = 0, limit: int = 100) -> List[Game]:
    """Gets all games from the database with pagination."""
    return session.exec(select(Game).where(Game.is_deleted == False).offset(skip).limit(limit)).all()

def get_game_by_id(session: Session, game_id: int) -> Optional[Game]:
    """Gets a game by its ID."""
    return session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()

def get_game_by_steam_app_id(session: Session, steam_app_id: int) -> Optional[Game]:
    """Gets a game by its Steam App ID."""
    return session.exec(select(Game).where(Game.steam_app_id == steam_app_id, Game.is_deleted == False)).first()

def get_game_by_id_with_reviews(session: Session, game_id: int) -> Optional[GameReadWithReviews]:
    """Gets a game by ID, including its reviews."""
    game = session.get(Game, game_id)
    if not game or game.is_deleted:
        return None
    
    # Manually filter reviews to ensure is_deleted is respected
    # and eager load related user/game data for the response model
    reviews_with_details = []
    for review in game.reviews:
        if not review.is_deleted:
            # Ensure related entities are loaded for the response model
            review.user = get_user_by_id(session, review.user_id) 
            review.game = game # Assign the game object itself
            reviews_with_details.append(review)

    # Re-validate the game object to fit the response model structure
    game_read = GameRead.model_validate(game)
    response_game = GameReadWithReviews(**game_read.model_dump(), reviews=reviews_with_details)

    return response_game


def update_game_in_db(session: Session, db_game: Game, game_data: GameUpdate) -> Game:
    """Updates an existing game's information."""
    hero_data = game_data.model_dump(exclude_unset=True)
    db_game.sqlmodel_update(hero_data)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

def delete_game_in_db(session: Session, db_game: Game):
    """Marks a game as deleted (soft delete)."""
    db_game.is_deleted = True
    session.add(db_game)
    session.commit()
    session.refresh(db_game)


# --- User Operations (Database) ---

def create_user_in_db(session: Session, user_data: UserCreate) -> User:
    """Creates a new user in the database."""
    # Hash the password before creating the user
    hashed_password = auth.get_password_hash(user_data.password)
    user_to_db = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    session.add(user_to_db)
    session.commit()
    session.refresh(user_to_db)
    return user_to_db

def get_all_users(session: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Gets all users from the database with pagination."""
    return session.exec(select(User).where(User.is_deleted == False).offset(skip).limit(limit)).all()

def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    """Gets a user by their ID."""
    return session.exec(select(User).where(User.id == user_id, User.is_deleted == False)).first()

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    """Gets a user by their username."""
    return session.exec(select(User).where(User.username == username, User.is_deleted == False)).first()

def get_user_by_email(session: Session, email: str) -> Optional[User]:
    """Gets a user by their email."""
    return session.exec(select(User).where(User.email == email, User.is_deleted == False)).first()

def get_user_by_id_with_reviews(session: Session, user_id: int) -> Optional[UserReadWithReviews]:
    """Gets a user by ID, including their reviews."""
    user = session.get(User, user_id)
    if not user or not user.is_active:
        return None

    reviews_with_details = []
    for review in user.reviews:
        if not review.is_deleted:
            review.game = get_game_by_id(session, review.game_id)
            review.user = user
            reviews_with_details.append(review)

    user_read = UserRead.model_validate(user)
    response_user = UserReadWithReviews(**user_read.model_dump(), reviews=reviews_with_details)
    return response_user


# --- Review Operations (Database) ---

def create_review_in_db(
    session: Session,
    review_text: str,
    rating: Optional[int],
    game_id: int,
    user_id: int,
    image_filename: Optional[str] = None
) -> Review:
    """Creates a new review in the database."""
    db_review = Review(
        review_text=review_text,
        rating=rating,
        game_id=game_id,
        user_id=user_id,
        image_filename=image_filename
    )
    session.add(db_review)
    session.commit()
    session.refresh(db_review)

    # Eager load relationships for the response
    db_review.game = get_game_by_id(session, game_id)
    db_review.user = get_user_by_id(session, user_id)

    return db_review

def get_all_reviews(
    session: Session,
    skip: int = 0,
    limit: int = 100,
    game_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> List[ReviewReadWithDetails]:
    """Gets all reviews from the database with pagination and filtering options."""
    query = select(Review).where(Review.is_deleted == False)
    if game_id:
        query = query.where(Review.game_id == game_id)
    if user_id:
        query = query.where(Review.user_id == user_id)

    reviews = session.exec(query.offset(skip).limit(limit)).all()

    # Eager load related game and user for the response model
    for review in reviews:
        review.game = get_game_by_id(session, review.game_id)
        review.user = get_user_by_id(session, review.user_id)
        
    return [ReviewReadWithDetails.model_validate(r) for r in reviews]

def get_review_by_id(session: Session, review_id: int) -> Optional[Review]:
    """Gets a review by its ID."""
    review = session.exec(select(Review).where(Review.id == review_id, Review.is_deleted == False)).first()
    if review:
        review.game = get_game_by_id(session, review.game_id)
        review.user = get_user_by_id(session, review.user_id)
    return review

def update_review_in_db(session: Session, db_review: Review, review_data: ReviewBase) -> Review:
    """Updates an existing review."""
    review_update_data = review_data.model_dump(exclude_unset=True)
    db_review.sqlmodel_update(review_update_data)
    session.add(db_review)
    session.commit()
    session.refresh(db_review)

    db_review.game = get_game_by_id(session, db_review.game_id)
    db_review.user = get_user_by_id(session, db_review.user_id)
    return db_review

def delete_review_in_db(session: Session, db_review: Review):
    """Marks a review as deleted (soft delete)."""
    db_review.is_deleted = True
    session.add(db_review)
    session.commit()


# --- Steam API Integration Operations ---

async def get_steam_app_list() -> List[dict]:
    """
    (NEW) Fetches the complete list of apps from the Steam Web API.
    """
    if not STEAM_API_KEY:
        print("🚨 STEAM_API_KEY is not configured. Cannot fetch the Steam app list.")
        return []

    app_list_url = f"{STEAM_WEB_API_BASE_URL}/ISteamApps/GetAppList/v2/"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(app_list_url)
            response.raise_for_status()
            data = response.json()
            if data and 'applist' in data and 'apps' in data['applist']:
                return data['applist']['apps']
            return []
    except httpx.HTTPStatusError as e:
        print(f"🚨 HTTP Error while fetching Steam app list: {e}")
        return []
    except httpx.RequestError as e:
        print(f"🚨 Network Error while fetching Steam app list: {e}")
        return []
    except Exception as e:
        print(f"🚨 Unexpected error while fetching Steam app list: {e}")
        return []


async def search_steam_store_games(query: str) -> List[dict]:
    """Searches for games on the Steam store using the public API."""
    search_url = f"{STEAM_STORE_API_BASE_URL}/storesearch/"
    params = {"term": query, "l": "spanish", "cc": "co"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'items' in data:
                return data['items']
            return []

    except httpx.HTTPStatusError as e:
        print(f"🚨 HTTP Error searching Steam games: {e}")
        return []
    except Exception as e:
        print(f"🚨 Unexpected error searching Steam games: {e}")
        return []

async def get_steam_game_details(app_id: int) -> Optional[dict]:
    """Gets details for a Steam game using the store API."""
    details_url = f"{STEAM_STORE_API_BASE_URL}/appdetails/"
    params = {"appids": app_id, "l": "spanish", "cc": "co"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(details_url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and str(app_id) in data and data[str(app_id)]['success']:
                return data[str(app_id)]['data']
            return None
    except Exception as e:
        print(f"🚨 Error getting Steam details for {app_id}: {e}")
        return None

async def get_current_players_for_app(app_id: int) -> Optional[int]:
    """Gets the current player count for a Steam App ID."""
    if not STEAM_API_KEY:
        print("🚨 STEAM_API_KEY is not configured.")
        return None

    player_count_url = f"{STEAM_WEB_API_BASE_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    params = {"appid": app_id, "key": STEAM_API_KEY}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(player_count_url, params=params)
            response.raise_for_status()
            data = response.json()
            if 'response' in data and 'player_count' in data['response']:
                return data['response']['player_count']
            return None
    except Exception as e:
        print(f"🚨 Error getting player count for {app_id}: {e}")
        return None

async def import_game_from_steam(session: Session, app_id: int) -> Optional[Game]:
    """Imports a Steam game into the local database using its App ID."""
    steam_game_details = await get_steam_game_details(app_id)
    if not steam_game_details:
        print(f"🚨 No details found for App ID {app_id} on Steam.")
        return None

    try:
        release_date_str = steam_game_details.get("release_date", {}).get("date")
        parsed_release_date = None
        if release_date_str:
            try:
                parsed_release_date = datetime.strptime(release_date_str, "%d %b, %Y").date()
            except ValueError:
                print(f"Warning: Could not parse release date '{release_date_str}'.")

        genres_list = [g['description'] for g in steam_game_details.get("genres", [])]
        price_data = steam_game_details.get("price_overview")
        price_float = price_data['final'] / 100.0 if price_data and 'final' in price_data else 0.0

        game_data_for_db = GameCreate(
            title=steam_game_details.get("name"),
            developer=", ".join(steam_game_details.get("developers", [])),
            publisher=", ".join(steam_game_details.get("publishers", [])),
            genres=", ".join(genres_list),
            release_date=parsed_release_date,
            price=price_float,
            steam_app_id=app_id
        )
    except Exception as e:
        print(f"🚨 Error mapping Steam details for App ID {app_id}: {e}")
        return None

    db_game = Game.model_validate(game_data_for_db)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

# --- Image Upload Operation ---

async def save_uploaded_image(file: UploadFile) -> Optional[str]:
    """Saves an uploaded image and returns its public URL."""
    if not file.filename:
        return None

    filename = file.filename.replace(' ', '_')
    file_location = f"uploads/{filename}"

    try:
        async with aiofiles.open(file_location, "wb") as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        
        public_url = f"/uploads/{filename}"
        print(f"DEBUG: Image saved at {file_location}, accessible at {public_url}")
        return public_url
    except Exception as e:
        print(f"🚨 Error saving image: {e}")
        return None
