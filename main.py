from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import init_db
from routers import users, games, reviews, uploads

app = FastAPI(title="Steam Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(users.router, prefix="/api/v1/usuarios", tags=["usuarios"])
app.include_router(games.router, prefix="/api/v1/juegos", tags=["juegos"])
app.include_router(reviews.router, prefix="/api/v1", tags=["reviews"])
app.include_router(uploads.router, prefix="/api/v1/uploads", tags=["uploads"])

@app.on_event("startup")
def on_startup():
    init_db()
