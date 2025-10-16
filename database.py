# database.py
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text
import os

# -------------------------------------------------------------------
# Config de conexión
# -------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

# Render a veces entrega 'postgres://'; SQLAlchemy espera 'postgresql://'
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    # Postgres en Render
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print("DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    # Fallback local SQLite
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    engine = create_engine(
        sqlite_url,
        echo=True,
        connect_args={"check_same_thread": False},
    )
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")

# -------------------------------------------------------------------
# Auto-migración ligera para agregar owner_id a la tabla game
#   - Postgres: crea columna si no existe + agrega FK si no existe
#   - SQLite: crea columna si no existe (sin FK estricta)
# -------------------------------------------------------------------
def _auto_migrate_owner_id():
    dialect = engine.dialect.name
    print(f"DEBUG: Ejecutando auto-migración (dialect={dialect})…")

    with engine.begin() as conn:
        if dialect == "postgresql":
            # 1) Asegura columna
            conn.execute(text('ALTER TABLE "game" ADD COLUMN IF NOT EXISTS owner_id INTEGER NULL'))

            # 2) Asegura la FK solo si no existe aún
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'fk_game_owner'
                    ) THEN
                        ALTER TABLE "game"
                        ADD CONSTRAINT fk_game_owner
                        FOREIGN KEY (owner_id) REFERENCES "user"(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
            """))

        elif dialect == "sqlite":
            # SQLite: verificar si la columna existe con PRAGMA
            cols = conn.execute(text("PRAGMA table_info('game')")).fetchall()
            col_names = {row[1] for row in cols}  # 2ª columna es el nombre
            if "owner_id" not in col_names:
                conn.execute(text("ALTER TABLE game ADD COLUMN owner_id INTEGER"))
            # Nota: aplicar FK en SQLite implica recrear tabla; omitimos para rapidez.

        else:
            # Otros motores: intento genérico de crear columna si no existe
            try:
                conn.execute(text("ALTER TABLE game ADD COLUMN owner_id INTEGER"))
            except Exception:
                # Si ya existe o el motor no soporta IF NOT EXISTS, ignoramos
                pass

    print("DEBUG: Auto-migración completada (owner_id listo).")

# -------------------------------------------------------------------
# Ciclo de vida de DB
# -------------------------------------------------------------------
def create_db_and_tables():
    print("DEBUG: Intentando crear tablas de la base de datos…")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas creadas/verificadas.")

    try:
        _auto_migrate_owner_id()
    except Exception as e:
        # Si algo falla, no tumbamos la app; dejamos registro.
        print(f"AVISO: auto-migración omitida/parcial: {e}")

def get_session():
    with Session(engine) as session:
        yield session
