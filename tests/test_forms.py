from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def ensure_admin():
    """
    Crea el usuario admin si no existe.
    """
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
    """
    Obtiene un token válido usando el endpoint /token.
    Usa las mismas credenciales que el resto de pruebas.
    """
    ensure_admin()
    r = client.post("/token", data={"username": "admin", "password": "1234"})
    assert r.status_code == 200
    access_token = r.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def test_login_correcto():
    """
    Verifica que el login funcione correctamente con credenciales válidas.
    """
    ensure_admin()
    r = client.post("/token", data={"username": "admin", "password": "1234"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_crear_juego_valido():
    """
    Verifica que se pueda crear un juego con datos válidos
    y que la API responda 201 con el objeto creado.
    """
    headers = auth()
    response = client.post(
        "/api/v1/juegos",
        json={
            "title": "Juego de prueba",
            "developer": "Dev Test",
            "publisher": "Publisher Test",
            "genres": "Action",
            "price": 9.99,
        },
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["title"] == "Juego de prueba"
    assert data["developer"] == "Dev Test"
    assert data["publisher"] == "Publisher Test"
    assert data["genres"] == "Action"
    assert data["price"] == 9.99


def test_listar_juegos():
    """
    Verifica que el endpoint de listado de juegos funcione
    y devuelva una lista (aunque esté vacía).
    """
    response = client.get("/api/v1/juegos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
