from sqlmodel import create_engine, Session, SQLModel
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# ✅ Normaliza esquema legacy
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print("DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")

def create_db_and_tables():
    print("DEBUG: Intentando crear tablas de la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas de la base de datos creadas/verificadas.")

def get_session():
    with Session(engine) as session:
        yield session
