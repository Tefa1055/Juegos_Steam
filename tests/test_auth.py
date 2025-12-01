from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Prueba 1: Login correcto
def test_login_correcto():
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "1234"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data

# Prueba 2: Contraseña incorrecta
def test_contraseña_incorrecta():
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "malaclave"}
    )
    assert response.status_code in (400, 401)

# Prueba 3: Usuario inexistente
def test_usuario_inexistente():
    response = client.post(
        "/auth/login",
        json={"username": "no_existe", "password": "1234"}
    )
    assert response.status_code in (400, 401, 404)

# Prueba 4: Acceso sin token
def test_acceso_sin_token():
    response = client.get("/usuarios")
    assert response.status_code in (401, 403)

# Prueba 5: Token inválido
def test_token_invalido():
    response = client.get(
        "/usuarios",
        headers={"Authorization": "Bearer token_invalido_123"}
    )
    assert response.status_code in (401, 403)
