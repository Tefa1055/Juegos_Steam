# operations.py
# Lógica de negocio para DB, mock y APIs externas (Steam).

import os
import re
import uuid
import httpx
from typing import List, Optional
from datetime import datetime
from sqlmodel import Session, select
from fastapi import UploadFile

import auth
from models import (
    Game, GameCreate, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserReadWithReviews,
    Review, ReviewBase, ReviewReadWithDetails,
    PlayerActivityCreate, PlayerActivityResponse
)

# --- Config ---
STEAM_API_KEY = os.environ.get("STEAM_API_KEY")
STEAM_STORE_API_BASE_URL = "https://store.steampowered.com/api"
STEAM_WEB_API_BASE_URL = "https://api.steampowered.com"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8MB

# --- Helpers ---

def _safe_filename(name: str) -> str:
    # quita rutas, espacios, caracteres raros
    name = os.path.basename(name)
    name = name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._\-]", "", name)
    return name

def _ext_or_default(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return ext if ext in ALLOWED_EXTS else ""

# --- Games (DB) ---

def create_game_in_db(session: Session, game_data: GameCreate) -> Game:
    db_game = Game.model_validate(game_data)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

def get_all_games(session: Session) -> List[Game]:
    return session.exec(select(Game).where(Game.is_deleted == False)).all()

def get_game_by_id(session: Session, game_id: int) -> Optional[Game]:
    return session.exec(
        select(Game).where(Game.id == game_id, Game.is_deleted == False)
    ).first()

def get_game_by_steam_app_id(session: Session, steam_app_id: int) -> Optional[Game]:
    return session.exec(
        select(Game).where(Game.steam_app_id == steam_app_id, Game.is_deleted == False)
    ).first()

def get_game_with_reviews(session: Session, game_id: int) -> Optional[GameReadWithReviews]:
    game = session.exec(
        select(Game).where(Game.id == game_id, Game.is_deleted == False)
    ).first()
    return game or None

def filter_games_by_genre(session: Session, genre: str) -> List[Game]:
    # Evita NULL en genres
    return session.exec(
        select(Game).where(
            Game.is_deleted == False,
            Game.genres != None,  # noqa: E711
            Game.genres.ilike(f"%{genre}%"),
        )
    ).all()

def search_games_by_title(session: Session, query: str) -> List[Game]:
    # Evita NULL en title
    return session.exec(
        select(Game).where(
            Game.is_deleted == False,
            Game.title != None,  # noqa: E711
            Game.title.ilike(f"%{query}%"),
        )
    ).all()

def update_game(session: Session, game_id: int, game_update: GameUpdate) -> Optional[Game]:
    game = session.exec(
        select(Game).where(Game.id == game_id, Game.is_deleted == False)
    ).first()
    if not game:
        return None
    for k, v in game_update.model_dump(exclude_unset=True).items():
        setattr(game, k, v)
    session.add(game)
    session.commit()
    session.refresh(game)
    return game

def delete_game_soft(session: Session, game_id: int) -> Optional[Game]:
    game = session.exec(
        select(Game).where(Game.id == game_id, Game.is_deleted == False)
    ).first()
    if not game:
        return None
    game.is_deleted = True
    session.add(game)
    session.commit()
    session.refresh(game)
    return game

# --- Users ---

def create_user_in_db(session: Session, user_data: UserCreate, hashed_password: str) -> Optional[User]:
    if session.exec(select(User).where(User.username == user_data.username)).first():
        return None
    if session.exec(select(User).where(User.email == user_data.email)).first():
        return None

    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

def get_all_users(session: Session) -> List[User]:
    return session.exec(select(User).where(User.is_active == True)).all()

def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.exec(
        select(User).where(User.id == user_id, User.is_active == True)
    ).first()

def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()

def get_user_with_reviews(session: Session, user_id: int) -> Optional[UserReadWithReviews]:
    user = session.exec(
        select(User).where(User.id == user_id, User.is_active == True)
    ).first()
    return user or None

def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_username(session, username)
    if not user or not auth.verify_password(password, user.hashed_password):
        return None
    return user

# --- Reviews ---

def create_review_in_db(session: Session, review_data: ReviewBase, game_id: int, user_id: int) -> Optional[Review]:
    game = session.exec(select(Game).where(Game.id == game_id, Game.is_deleted == False)).first()
    user = session.exec(select(User).where(User.id == user_id, User.is_active == True)).first()
    if not game or not user:
        return None
    db_review = Review.model_validate(review_data, update={"game_id": game_id, "user_id": user_id})
    session.add(db_review)
    session.commit()
    session.refresh(db_review)
    return db_review

def get_review_by_id(session: Session, review_id: int) -> Optional[Review]:
    return session.exec(
        select(Review).where(Review.id == review_id, Review.is_deleted == False)
    ).first()

def get_review_with_details(session: Session, review_id: int) -> Optional[ReviewReadWithDetails]:
    review = session.exec(
        select(Review).where(Review.id == review_id, Review.is_deleted == False)
    ).first()
    return review or None

def get_reviews_for_game(session: Session, game_id: int) -> List[Review]:
    return session.exec(
        select(Review).where(Review.game_id == game_id, Review.is_deleted == False)
    ).all()

def get_reviews_by_user(session: Session, user_id: int) -> List[Review]:
    return session.exec(
        select(Review).where(Review.user_id == user_id, Review.is_deleted == False)
    ).all()

def update_review_in_db(session: Session, review_id: int, review_update: ReviewBase) -> Optional[Review]:
    review = session.exec(
        select(Review).where(Review.id == review_id, Review.is_deleted == False)
    ).first()
    if not review:
        return None
    for k, v in review_update.model_dump(exclude_unset=True).items():
        setattr(review, k, v)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review

def delete_review_soft(session: Session, review_id: int) -> Optional[Review]:
    review = session.exec(
        select(Review).where(Review.id == review_id, Review.is_deleted == False)
    ).first()
    if not review:
        return None
    review.is_deleted = True
    session.add(review)
    session.commit()
    session.refresh(review)
    return review

# --- PlayerActivity (mock) ---

_player_activity_mock_db: List[PlayerActivityResponse] = []
_next_player_activity_id = 1

def get_all_player_activity_mock(include_deleted: bool = False) -> List[PlayerActivityResponse]:
    return _player_activity_mock_db if include_deleted else [
        a for a in _player_activity_mock_db if not a.is_deleted
    ]

def get_player_activity_by_id_mock(activity_id: int) -> Optional[PlayerActivityResponse]:
    for a in _player_activity_mock_db:
        if a.id == activity_id and not a.is_deleted:
            return a
    return None

def create_player_activity_mock(activity_data: dict) -> PlayerActivityResponse:
    global _next_player_activity_id
    new_activity = PlayerActivityResponse(id=_next_player_activity_id, **activity_data)
    _player_activity_mock_db.append(new_activity)
    _next_player_activity_id += 1
    return new_activity

def update_player_activity_mock(activity_id: int, update_data: dict) -> Optional[PlayerActivityResponse]:
    for i, a in enumerate(_player_activity_mock_db):
        if a.id == activity_id and not a.is_deleted:
            updated = a.model_copy(update=update_data)
            _player_activity_mock_db[i] = updated
            return updated
    return None

def delete_player_activity_mock(activity_id: int) -> bool:
    for a in _player_activity_mock_db:
        if a.id == activity_id and not a.is_deleted:
            a.is_deleted = True
            return True
    return False

# --- Steam API ---

async def get_steam_app_list() -> Optional[List[dict]]:
    url = f"{STEAM_WEB_API_BASE_URL}/ISteamApps/GetAppList/v2/"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            if data and data.get("applist") and data["applist"].get("apps"):
                return data["applist"]["apps"]
            return None
    except httpx.HTTPStatusError as e:
        print(f"🚨 HTTP {e.response.status_code} GetAppList: {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Red GetAppList: {e}")
        return None
    except Exception as e:
        print(f"🚨 GetAppList inesperado: {e}")
        return None

async def get_game_details_from_steam_api(app_id: int) -> Optional[dict]:
    url = f"{STEAM_STORE_API_BASE_URL}/appdetails?appids={app_id}&cc=us&l=en"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            if data and str(app_id) in data and data[str(app_id)].get("success"):
                game = data[str(app_id)]["data"]
                extracted = {
                    "app_id": app_id,
                    "name": game.get("name"),
                    "header_image": game.get("header_image"),
                    "short_description": game.get("short_description"),
                    "developers": game.get("developers") or [],
                    "publishers": game.get("publishers") or [],
                    "price": None,
                    "genres": [g.get("description") for g in game.get("genres", []) if g.get("description")],
                    "release_date": game.get("release_date", {}).get("date"),
                }
                price = game.get("price_overview")
                if price:
                    extracted["price"] = price.get("final_formatted")
                elif game.get("is_free"):
                    extracted["price"] = "Free to Play"
                return extracted
            return None
    except httpx.HTTPStatusError as e:
        print(f"🚨 HTTP {e.response.status_code} appdetails: {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Red appdetails: {e}")
        return None
    except Exception as e:
        print(f"🚨 appdetails inesperado: {e}")
        return None

async def get_current_players_for_app(app_id: int) -> Optional[int]:
    if not STEAM_API_KEY:
        print("🚨 STEAM_API_KEY no configurada.")
        return None
    url = f"{STEAM_WEB_API_BASE_URL}/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?key={STEAM_API_KEY}&appid={app_id}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            if data and data.get("response") and data["response"].get("result") == 1:
                return data["response"].get("player_count")
            return None
    except httpx.HTTPStatusError as e:
        print(f"🚨 HTTP {e.response.status_code} current players: {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"🚨 Red current players: {e}")
        return None
    except Exception as e:
        print(f"🚨 current players inesperado: {e}")
        return None

async def add_steam_game_to_db(session: Session, app_id: int) -> Optional[Game]:
    details = await get_game_details_from_steam_api(app_id)
    if not details:
        print(f"No details for app {app_id}")
        return None

    existing = get_game_by_steam_app_id(session, app_id)
    if existing:
        print(f"Ya existe Steam App ID {app_id} (ID local {existing.id})")
        return existing

    # Parse fecha
    parsed_date = None
    release_date_str = details.get("release_date")
    if release_date_str and release_date_str != "Coming Soon":
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y"):  # ej: "Nov 10, 2023" / "November 10, 2023" / "2023"
            try:
                parsed_date = datetime.strptime(release_date_str, fmt).date()
                break
            except ValueError:
                continue

    # Precio -> float
    price_str = details.get("price")
    if price_str and price_str != "Free to Play":
        try:
            price_float = float(price_str.replace("$", "").replace("USD", "").replace(",", "").strip())
        except Exception:
            price_float = 0.0
    else:
        price_float = 0.0

    game_data = GameCreate(
        title=details.get("name", f"Steam App {app_id}"),
        developer=", ".join(details.get("developers", []) or []),
        publisher=", ".join(details.get("publishers", []) or []),
        genres=", ".join(details.get("genres", []) or []),
        release_date=parsed_date,
        price=price_float,
        steam_app_id=app_id,
    )

    db_game = Game.model_validate(game_data)
    session.add(db_game)
    session.commit()
    session.refresh(db_game)
    return db_game

# --- Upload de imágenes (persistente en disco local) ---

async def save_uploaded_image(file: UploadFile) -> Optional[str]:
    """
    Guarda una imagen en ./uploads y devuelve su URL pública /uploads/<nombre>.
    Lanza ValueError si el archivo no es válido.
    """
    if not file or not file.filename:
        return None

    # valida MIME y extensión
    if not (file.content_type or "").startswith("image/"):
        raise ValueError("Solo se permiten imágenes.")

    orig_name = _safe_filename(file.filename)
    ext = _ext_or_default(orig_name)
    if not ext:
        raise ValueError("Extensión no permitida. Usa png, jpg, jpeg, gif o webp.")

    # lee contenido (con límite)
    content = await file.read()
    if not content:
        raise ValueError("Archivo vacío.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("La imagen excede el tamaño máximo de 8MB.")

    # nombre único
    unique_name = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(UPLOAD_DIR, unique_name)

    # guarda en disco
    with open(abs_path, "wb") as f:
        f.write(content)

    # URL pública (servida por StaticFiles en main.py)
    return f"/uploads/{unique_name}"
