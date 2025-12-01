import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def ensure_admin():
    """
    Crea el usuario admin si no existe.
    El endpoint /api/v1/usuarios no requiere autenticación.
    """
    resp = client.post(
        "/api/v1/usuarios",
        json={
            "username": "admin",
            "email": "admin@example.com",
            "password": "1234",
        },
    )
    # 201 = creado, 400 = ya existía (nombre o email repetido)
    assert resp.status_code in (201, 400)


def test_login_correcto():
    ensure_admin()
    response = client.post(
        "/token",
        data={"username": "admin", "password": "1234"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_contraseña_incorrecta():
    ensure_admin()
    response = client.post(
        "/token",
        data={"username": "admin", "password": "malaclave"},
    )
    # /token devuelve 401 si el usuario no existe o la clave es incorrecta
    assert response.status_code == 401


def test_acceso_sin_token():
    # Endpoint protegido: /api/v1/usuarios/me
    response = client.get("/api/v1/usuarios/me")
    # Debe devolver 401 porque NO se envía token
    assert response.status_code == 401


def test_token_invalido():
    # Llamamos al mismo endpoint protegido pero con un token inventado
    response = client.get(
        "/api/v1/usuarios/me",
        headers={"Authorization": "Bearer token_invalido_123"},
    )
    # Tu get_current_user devuelve 401 si el token no es válido
    assert response.status_code == 401