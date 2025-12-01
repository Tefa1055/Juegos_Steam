from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ⚠️ Login REAL usa OAuth2PasswordRequestForm
# por eso se envía como form-data, NO JSON.

def test_login_correcto():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "1234"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_contraseña_incorrecta():
    response = client.post(
        "/token",
        data={"username": "admin", "password": "clave_mala"},
    )
    assert response.status_code == 401


def test_acceso_sin_token():
    response = client.get("/api/v1/usuarios")
    assert response.status_code in (401, 403)


def test_token_invalido():
    response = client.get(
        "/api/v1/usuarios",
        headers={"Authorization": "Bearer token_falso_123"},
    )
    assert response.status_code in (401, 403)