from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, List
from sqlmodel import Session, select
from models import Game, User
from database import get_session
from auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[Game])
def list_games(q: Optional[str] = None, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    stmt = select(Game).where((Game.owner_id == user.id) if user else True)
    if q:
        stmt = stmt.where(Game.titulo.contains(q))
    return session.exec(stmt).all()

@router.post("/", response_model=Game, status_code=201)
def create_game(data: Game, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    g = Game(titulo=data.titulo, categoria=data.categoria, descripcion=data.descripcion, portada_url=data.portada_url, owner_id=user.id)
    session.add(g); session.commit(); session.refresh(g); return g

def _owned_or_404(session: Session, user: User, id: int) -> Game:
    g = session.get(Game, id)
    if not g: raise HTTPException(status_code=404, detail="Juego no encontrado")
    if g.owner_id != user.id and not user.is_admin: raise HTTPException(status_code=403, detail="Sin permiso")
    return g

@router.put("/{id}", response_model=Game)
def update_game(id: int, data: Game, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    g = _owned_or_404(session, user, id)
    g.titulo = data.titulo; g.categoria = data.categoria; g.descripcion = data.descripcion; g.portada_url = data.portada_url
    session.add(g); session.commit(); session.refresh(g); return g

@router.delete("/{id}", status_code=204)
def delete_game(id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)):
    g = _owned_or_404(session, user, id)
    session.delete(g); session.commit(); return
