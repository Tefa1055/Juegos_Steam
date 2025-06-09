from sqlmodel import create_engine, Session, SQLModel
import os

# Define la URL de la base de datos SQLite.
# El archivo 'steam_project.db' se creará en el mismo directorio donde ejecutes la aplicación.
DATABASE_URL = "sqlite:///./steam_project.db"

# Crea el motor de la base de datos.
# echo=True es útil para depurar, ya que imprimirá las sentencias SQL ejecutadas.
engine = create_engine(DATABASE_URL, echo=True)

def create_db_and_tables():
    """
    Crea todas las tablas definidas en tus modelos SQLModel en la base de datos.
    Si las tablas ya existen, no hace nada.
    """
    print("Creando tablas de la base de datos si no existen...")
    SQLModel.metadata.create_all(engine)
    print("Tablas verificadas/creadas.")

def get_session():
    """
    Función de dependencia para FastAPI que proporciona una sesión de base de datos.
    Asegura que la sesión se cierre correctamente después de la solicitud.
    """
    with Session(engine) as session:
        yield session