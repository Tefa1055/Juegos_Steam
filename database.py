# database.py
from sqlmodel import create_engine, Session, SQLModel
import os # Necesitas importar os para leer variables de entorno

# Render.com (y otros proveedores de nube) inyectarán la URL de la base de datos PostgreSQL
# como una variable de entorno llamada DATABASE_URL.
# Si esta variable existe, la usaremos para conectarnos a PostgreSQL.
# Si no existe (como en tu entorno de desarrollo local), volveremos a SQLite.
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- Configuración del Motor de la Base de Datos (Engine) ---
# 'echo=True' es útil en desarrollo para ver las sentencias SQL que se ejecutan.
# Puedes cambiarlo a False en producción si no quieres esos logs detallados.

if DATABASE_URL:
    # Si estamos en un entorno con DATABASE_URL (ej. Render), usamos PostgreSQL
    # 'pool_pre_ping=True' ayuda a mantener las conexiones activas en entornos de nube.
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print(f"DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    # Si estamos en desarrollo local (no hay DATABASE_URL), usamos SQLite
    # El archivo database.db se creará en la misma carpeta que este script.
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    # 'connect_args={"check_same_thread": False}' es necesario para SQLite con FastAPI
    # porque FastAPI puede usar diferentes hilos para manejar peticiones.
    engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")


# --- Funciones de la Base de Datos ---

def create_db_and_tables():
    """
    Crea las tablas de la base de datos definidas en tus modelos SQLModel.
    - Si el motor está configurado para PostgreSQL, creará las tablas allí.
    - Si el motor está configurado para SQLite, creará/actualizará el archivo 'database.db'.
    """
    print("DEBUG: Intentando crear tablas de la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas de la base de datos creadas/verificadas.")

def get_session():
    """
    Proporciona una sesión de base de datos para las operaciones CRUD.
    Esta función se usa como una dependencia en FastAPI.
    """
    with Session(engine) as session:
        yield session