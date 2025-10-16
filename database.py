from sqlmodel import create_engine, Session, SQLModel
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# Normaliza esquema legacy
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

def migrate_owner_id():
    """
    Añade la columna game.owner_id si no existe.
    - En Postgres: añade columna y FK a user(id).
    - En SQLite: añade columna (ALTER limitado; sin FK).
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        dialect = engine.url.get_backend_name()
        if dialect == "postgresql":
            # ¿Existe la columna?
            exists_sql = text("""
                SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = 'game' AND column_name = 'owner_id';
            """)
            count = conn.execute(exists_sql).scalar() or 0
            if count == 0:
                print("DEBUG: Agregando columna owner_id a game (PostgreSQL)...")
                conn.execute(text("ALTER TABLE game ADD COLUMN owner_id INTEGER NULL;"))
                # Agrega FK (opcional pero recomendado)
                conn.execute(text("""
                    ALTER TABLE game
                    ADD CONSTRAINT fk_game_owner
                    FOREIGN KEY (owner_id)
                    REFERENCES "user"(id)
                    ON DELETE SET NULL;
                """))
                print("DEBUG: owner_id agregado con FK.")
            else:
                print("DEBUG: owner_id ya existe (PostgreSQL).")

        else:
            # SQLite
            pragma = conn.execute(text("PRAGMA table_info('game');")).fetchall()
            cols = {row[1] for row in pragma}  # row[1] = name
            if "owner_id" not in cols:
                print("DEBUG: Agregando columna owner_id a game (SQLite)...")
                conn.execute(text("ALTER TABLE game ADD COLUMN owner_id INTEGER;"))
                print("DEBUG: owner_id agregado (SQLite).")
            else:
                print("DEBUG: owner_id ya existe (SQLite).")

def get_session():
    with Session(engine) as session:
        yield session
