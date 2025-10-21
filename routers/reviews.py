from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from sqlmodel import Session, select
from models import Review, Game, User
from database import get_session
from auth import get_current_user

router = APIRouter()

@router.get("/juegos/{game_id}/reviews", response_model=List[Review])
def list_reviews_for_game(game_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return session.exec(select(Review).where(Review.game_id == game_id)).all()

@router.post("/juegos/{game_id}/reviews", response_model=Review, status_code=201)
def create_review_for_game(game_id: int, data: Review, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    if not session.get(Game, game_id): raise HTTPException(status_code=404, detail="Juego no encontrado")
    r = Review(game_id=game_id, user_id=user.id, titulo=data.titulo, contenido=data.contenido, rating=max(1,min(5,data.rating)), imagen_url=data.imagen_url)
    session.add(r); session.commit(); session.refresh(r); return r

@router.get("/reviews", response_model=List[Review])
def list_reviews(game_id: Optional[int] = None, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    stmt = select(Review); 
    if game_id: stmt = stmt.where(Review.game_id == game_id)
    return session.exec(stmt).all()

def _owned_or_404(session: Session, user: User, id: int) -> Review:
    r = session.get(Review, id)
    if not r: raise HTTPException(status_code=404, detail="Reseña no encontrada")
    if r.user_id != user.id and not user.is_admin: raise HTTPException(status_code=403, detail="Sin permiso")
    return r

@router.put("/reviews/{id}", response_model=Review)
def update_review(id: int, data: Review, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    r = _owned_or_404(session, user, id)
    r.titulo = data.titulo; r.contenido = data.contenido; r.rating = max(1,min(5,data.rating)); r.imagen_url = data.imagen_url
    session.add(r); session.commit(); session.refresh(r); return r

@router.delete("/reviews/{id}", status_code=204)
def delete_review(id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    r = _owned_or_404(session, user, id)
    session.delete(r); session.commit(); return
