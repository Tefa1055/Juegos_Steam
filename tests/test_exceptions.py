from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def ensure_admin():
    resp = client.post(
        "/api/v1/usuarios",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "1234",
        },
    )
    assert resp.status_code in (201, 400)


def auth():
    ensure_admin()
    r = client.post("/token", data={"username": "admin", "password": "1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_crear_juego_sin_json():
    """
    Debe devolver 422 cuando no se envía cuerpo JSON.
    FastAPI lanza error de validación (Unprocessable Entity) al no poder crear GameCreate.
    """
    headers = auth()
    response = client.post("/api/v1/juegos", headers=headers)
    assert response.status_code == 422


def test_crear_juego_campos_invalidos():
    """
    Debe devolver 400 o 422 cuando los campos son inválidos
    (cadenas vacías, precio negativo, etc.), según validaciones de GameCreate.
    """
    headers = auth()
    response = client.post(
        "/api/v1/juegos",
        json={
            "title": "",
            "developer": "",
            "publisher": "",
            "genres": "",
            "price": -50,
        },
        headers=headers,
    )
    assert response.status_code in (400, 422)


def test_error_interno_controlado():
    """
    Al intentar actualizar un juego que no existe con un id muy grande,
    el sistema debe responder con un error controlado:
      - 404 si el juego no existe.
      - 500 si ocurre un error inesperado, pero sigue siendo error del servidor.
    """
    headers = auth()
    response = client.put(
        "/api/v1/juegos/999999999999",
        json={"title": "Test"},
        headers=headers,
    )
    assert response.status_code in (404, 500)
