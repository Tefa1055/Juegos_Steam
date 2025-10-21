# main.py — FastAPI app con imports flexibles y static seguro
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db

# Importa routers desde paquete "routers" si existe; si no, desde la raíz.
try:
    from routers import users, games, reviews, uploads
except ModuleNotFoundError:
    import users, games, reviews, uploads  # si subiste los .py en la raíz

app = FastAPI(
    title="Steam Dashboard API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS (ajusta allow_origins con tu dominio del frontend si quieres más seguridad)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # p.ej. ["https://tu-frontend.onrender.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Asegura que exista la carpeta 'static/uploads' (evita RuntimeError en Render)
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Monta routers
app.include_router(users.router, prefix="/api/v1/usuarios", tags=["usuarios"])
app.include_router(games.router, prefix="/api/v1/juegos", tags=["juegos"])
app.include_router(reviews.router, prefix="/api/v1", tags=["reviews"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["uploads"])

# Evento de inicio: crea tablas si faltan
@app.on_event("startup")
def on_startup():
    init_db()

# Health-check simple (útil para verificar que está vivo)
@app.get("/healthz")
def healthz():
    return {"ok": True}
