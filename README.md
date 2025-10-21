# Steam Dashboard - Backend (FastAPI + SQLModel)
- Juegos (CRUD, scoping por propietario)
- Reseñas (CRUD, estrellas 1–5, imagen opcional)
- Usuarios (registro, login OAuth2 password, /me)
- Upload de imágenes (local; en producción usar S3/Cloudinary)
- CORS habilitado

## Desarrollo
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Producción (Render)
- Añade `render.yaml`
- Configura `DATABASE_URL` (Postgres) y `JWT_SECRET`

## Modelos
- User, Game, Review (SQLModel)

## Notas
- Para integración real con Steam API, crea un router extra usando `requests` contra endpoints públicos de Steam y normaliza campos a `Game`.
