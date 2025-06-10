from sqlmodel import create_engine, Session, SQLModel
import os

# Obtener la URL de la base de datos desde la variable de entorno
DATABASE_URL = os.environ.get("DATABASE_URL")

# Crear el engine de la base de datos según el entorno
if DATABASE_URL:
    # PostgreSQL en Render
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print("DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    # SQLite en entorno local
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")

# Crear las tablas
def create_db_and_tables():
    print("DEBUG: Intentando crear tablas de la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas de la base de datos creadas/verificadas.")

# Sesión para operaciones CRUD
def get_session():
    with Session(engine) as session:
        yield session
