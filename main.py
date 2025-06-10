# main.py
import os
from typing import List, Optional
from datetime import timedelta

from fastapi import FastAPI, HTTPException, status, Query, Path, Depends, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import operations
import database
import auth
from models import (
    Game, GameCreate, GameRead, GameUpdate, GameReadWithReviews,
    User, UserCreate, UserRead, UserReadWithReviews,
    ReviewBase, ReviewReadWithDetails, Review,
)

app = FastAPI(
    title="API de Videojuegos de Steam",
    description="Servicio para consultar y gestionar información de juegos, usuarios, reseñas y actividad de jugadores en Steam.",
    version="1.1.0",
)

origins = [
    "http://localhost",
    "http://localhost:8000",
    "https://juegos-steam-s8wn.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for simplicity, can be restricted to 'origins' list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    """Function executed on application startup."""
    database.create_db_and_tables()
    if not os.path.exists("uploads"):
        os.makedirs("uploads")
        print("DEBUG: 'uploads' folder created.")

# Mount a directory to serve static files (uploaded images)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# --- Dependencies ---
def get_db_session():
    """Provides a database session."""
    with Session(database.engine) as session:
        yield session

async def get_current_user(
    token: str = Depends(auth.oauth2_scheme),
    session: Session = Depends(get_db_session)
) -> User:
    """Gets the current user from the JWT token."""
    user = auth.get_current_active_user(session, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de autenticación inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Frontend and Root Endpoint ---
@app.get("/")
async def read_root():
    """Serves the index.html frontend file."""
    return FileResponse("index.html")

# --- Authentication Endpoints ---
@app.post("/api/v1/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session)
):
    """Logs a user in and returns an access token."""
    user = auth.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id, "username": user.username}

@app.post("/api/v1/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(user_data: UserCreate, session: Session = Depends(get_db_session)):
    """Creates a new user."""
    db_user = operations.get_user_by_username(session, user_data.username)
    if db_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado")
    return operations.create_user_in_db(session=session, user_data=user_data)

@app.get("/api/v1/users/me/", response_model=UserRead)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Gets the information of the currently authenticated user."""
    return current_user

# --- Game Endpoints ---
@app.post("/api/v1/games/", response_model=GameRead, status_code=status.HTTP_201_CREATED)
def create_game_endpoint(
    game_data: GameCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Creates a new game in the database."""
    return operations.create_game_in_db(session=session, game_data=game_data)

@app.get("/api/v1/games/", response_model=List[GameRead])
def read_games_endpoint(
    skip: int = 0, limit: int = 100,
    session: Session = Depends(get_db_session)
):
    """Gets a list of games with pagination."""
    return operations.get_all_games(session=session, skip=skip, limit=limit)

@app.get("/api/v1/games/{game_id}", response_model=GameReadWithReviews)
def read_game_endpoint(
    game_id: int,
    session: Session = Depends(get_db_session)
):
    """Gets a specific game by ID, including its reviews."""
    game = operations.get_game_by_id_with_reviews(session=session, game_id=game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return game

@app.put("/api/v1/games/{game_id}", response_model=GameRead)
def update_game_endpoint(
    game_id: int,
    game_update: GameUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Updates an existing game."""
    db_game = operations.get_game_by_id(session, game_id)
    if not db_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    return operations.update_game_in_db(session=session, db_game=db_game, game_data=game_update)

@app.delete("/api/v1/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game_endpoint(
    game_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Marks a game as deleted (soft delete)."""
    db_game = operations.get_game_by_id(session, game_id)
    if not db_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")
    operations.delete_game_in_db(session=session, db_game=db_game)

# --- Review Endpoints ---
@app.post("/api/v1/reviews/", response_model=ReviewReadWithDetails, status_code=status.HTTP_201_CREATED)
async def create_review_for_game(
    review_data: ReviewBase,
    game_id: int = Query(..., description="ID of the game to review"),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Creates a new review for a specific game."""
    db_game = operations.get_game_by_id(session, game_id)
    if not db_game:
        raise HTTPException(status_code=404, detail="Juego no encontrado")

    db_review = operations.create_review_in_db(
        session=session,
        review_text=review_data.review_text,
        rating=review_data.rating,
        game_id=game_id,
        user_id=current_user.id,
        image_filename=review_data.image_filename
    )
    return db_review

@app.get("/api/v1/reviews/", response_model=List[ReviewReadWithDetails])
def read_reviews_endpoint(
    skip: int = 0, limit: int = 100,
    game_id: Optional[int] = Query(None, description="Filter reviews by game ID"),
    user_id: Optional[int] = Query(None, description="Filter reviews by user ID"),
    session: Session = Depends(get_db_session)
):
    """Gets a list of reviews, with filtering options."""
    return operations.get_all_reviews(session=session, skip=skip, limit=limit, game_id=game_id, user_id=user_id)
    
@app.get("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails)
def read_single_review_endpoint(review_id: int, session: Session = Depends(get_db_session)):
    """Gets a single review by its ID."""
    db_review = operations.get_review_by_id(session, review_id)
    if not db_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    return db_review


@app.put("/api/v1/reviews/{review_id}", response_model=ReviewReadWithDetails)
def update_review_endpoint(
    review_id: int,
    review_update: ReviewBase,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Updates an existing review. Only the author can update it."""
    db_review = operations.get_review_by_id(session, review_id)
    if not db_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if db_review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta reseña")
    
    return operations.update_review_in_db(session=session, db_review=db_review, review_data=review_update)

@app.delete("/api/v1/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review_endpoint(
    review_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Deletes a review (soft delete). Only the author can delete it."""
    db_review = operations.get_review_by_id(session, review_id)
    if not db_review:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if db_review.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta reseña")
    operations.delete_review_in_db(session=session, db_review=db_review)

# --- Image Upload Endpoint ---
@app.post("/api/v1/upload_image")
async def upload_image(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Uploads an image, saves it, and returns the public URL."""
    image_url = await operations.save_uploaded_image(file)
    if not image_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se pudo procesar la imagen.")
    return {"filename": file.filename, "url": image_url, "message": "Imagen guardada exitosamente."}

# --- Steam API Integration Endpoints ---

@app.get("/api/v1/steam/app_list", response_model=List[dict])
async def get_steam_app_list_endpoint():
    """(NEW) Gets the full list of apps from Steam."""
    return await operations.get_steam_app_list()

@app.get("/api/v1/steam/search_games/")
async def search_steam_games_endpoint(query: str = Query(...)):
    """Searches for games on the Steam store by name."""
    steam_games = await operations.search_steam_store_games(query)
    if not steam_games:
        raise HTTPException(status_code=404, detail=f"No se encontraron juegos en Steam para '{query}'.")
    return steam_games

@app.get("/api/v1/steam/game_details/{app_id}")
async def get_steam_game_details_endpoint(app_id: int):
    """(NEW) Gets details for a specific game from Steam."""
    details = await operations.get_steam_game_details(app_id)
    if not details:
        raise HTTPException(status_code=404, detail=f"No se encontraron detalles para el App ID {app_id}.")
    return details


@app.post("/api/v1/steam/import_game/{app_id}", response_model=GameRead)
async def import_steam_game_endpoint(
    app_id: int = Path(..., description="The Steam App ID of the game to import"),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """Imports a Steam game into the local database."""
    if operations.get_game_by_steam_app_id(session, app_id):
        raise HTTPException(status_code=409, detail=f"El juego con App ID {app_id} ya existe.")

    db_game = await operations.import_game_from_steam(session, app_id)
    if not db_game:
        raise HTTPException(status_code=404, detail=f"No se pudo importar el juego con App ID {app_id}.")
    return db_game

@app.get("/api/v1/steam/current_players/{app_id}")
async def get_steam_current_players_endpoint(app_id: int):
    """Gets the current player count for a Steam App ID."""
    player_count = await operations.get_current_players_for_app(app_id)
    if player_count is not None:
        return {"app_id": app_id, "player_count": player_count}
    raise HTTPException(status_code=404, detail=f"No se pudo obtener el número de jugadores actuales para el App ID {app_id}.")
