from sqlmodel import create_engine, Session, SQLModel
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

# ✅ Normaliza esquema legacy de Render
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL:
    engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    print("DEBUG: Usando PostgreSQL desde DATABASE_URL.")
else:
    sqlite_file_name = "database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    # check_same_thread sólo aplica a SQLite
    engine = create_engine(sqlite_url, echo=True, connect_args={"check_same_thread": False})
    print(f"DEBUG: Usando SQLite local: {sqlite_url}")


def get_session():
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """
    Crea tablas si no existen.
    (No rompe si ya están creadas)
    """
    print("DEBUG: Intentando crear tablas de la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("DEBUG: Tablas de la base de datos creadas/verificadas.")


def migrate_owner_id():
    """
    ✅ Migración idempotente para añadir `owner_id` a la tabla `game`.
    - En PostgreSQL: añade columna, índice e intenta añadir FK si no existe.
    - En SQLite: añade columna e índice (SQLite no permite añadir FK post-crear).
    Se puede llamar siempre; no falla si ya está aplicado.
    """
    dialect = engine.dialect.name
    print(f"DEBUG: Ejecutando migración owner_id (dialecto={dialect})...")

    try:
        with engine.begin() as conn:
            # 1) Columna owner_id
            if dialect == "postgresql":
                conn.exec_driver_sql(
                    "ALTER TABLE game ADD COLUMN IF NOT EXISTS owner_id INTEGER NULL;"
                )
            else:
                # SQLite >= 3.35 soporta IF NOT EXISTS; si tu versión es más vieja, intenta sin IF NOT EXISTS
                try:
                    conn.exec_driver_sql(
                        "ALTER TABLE game ADD COLUMN IF NOT EXISTS owner_id INTEGER;"
                    )
                except Exception:
                    # fallback si la versión de sqlite no soporta IF NOT EXISTS
                    try:
                        conn.exec_driver_sql("ALTER TABLE game ADD COLUMN owner_id INTEGER;")
                    except Exception:
                        pass  # ya existe

            # 2) Índice
            try:
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_game_owner_id ON game(owner_id);"
                )
            except Exception:
                pass  # si ya existe o el dialecto no lo soporta

            # 3) Foreign key (solo en Postgres; en SQLite requiere recrear la tabla)
            if dialect == "postgresql":
                conn.exec_driver_sql("""
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = 'fk_game_owner'
                      AND table_name = 'game'
                  ) THEN
                    ALTER TABLE game
                      ADD CONSTRAINT fk_game_owner
                      FOREIGN KEY (owner_id) REFERENCES "user"(id);
                  END IF;
                END$$;
                """)

        print("DEBUG: Migración owner_id completada.")
    except Exception as e:
        print(f"⚠️  DEBUG: Migración owner_id: se ignoró/ya aplicada. Detalle: {e}")
