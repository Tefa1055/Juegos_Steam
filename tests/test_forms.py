from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# ---------------------------
# 1. TEST: Crear un juego OK
# ---------------------------
def test_crear_juego_exitoso():
    response = client.post(
        "/games/create",
        json={
            "game_id": 123,
            "name": "Halo Infinite",
            "genre": "Shooter",
            "platform": "Steam",
            "release_date": "2023-01-01",
            "price": 59.99
        }
    )
    assert response.status_code == 201


# ---------------------------------------------------------
# 2. TEST: Crear un juego con campo vacío → debe fallar
# ---------------------------------------------------------
def test_crear_juego_nombre_vacio():
    response = client.post(
        "/games/create",
        json={
            "game_id": 999,
            "name": "",
            "genre": "Action",
            "platform": "Steam",
            "release_date": "2024-02-01",
            "price": 49.99
        }
    )
    assert response.status_code == 400


# ---------------------------------------------------------
# 3. TEST: Actualizar un juego con datos inválidos
# ---------------------------------------------------------
def test_actualizar_juego_invalido():
    response = client.put(
        "/games/update/123",
        json={
            "name": "",
            "genre": "",
            "platform": "Steam",
            "release_date": "2024-02-01",
            "price": -10
        }
    )
    assert response.status_code in (400, 422)


# ---------------------------------------------------------
# 4. TEST: Eliminar un ID existente
# ---------------------------------------------------------
def test_eliminar_juego_existente():
    # Primero creamos el juego
    client.post(
        "/games/create",
        json={
            "game_id": 50,
            "name": "Test Game",
            "genre": "Puzzle",
            "platform": "Steam",
            "release_date": "2024-01-01",
            "price": 10.0
        }
    )

    # Luego lo eliminamos
    response = client.delete("/games/delete/50")
    assert response.status_code in (200, 204)


# ---------------------------------------------------------
# 5. TEST: Eliminar un juego que NO existe
# ---------------------------------------------------------
def test_eliminar_juego_inexistente():
    response = client.delete("/games/delete/999999")
    assert response.status_code == 404
