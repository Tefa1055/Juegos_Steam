from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# Verifica que eliminar un juego inexistente devuelva 404
def test_eliminar_juego_inexistente():
    response = client.delete("/games/delete/999999")
    assert response.status_code == 404


# Verifica validación: campos inválidos deben devolver 400 o 422
def test_crear_juego_campos_invalidos():
    response = client.post(
        "/games/create",
        json={
            "game_id": -1,          # ID no válido
            "name": "",             # Nombre vacío
            "genre": "",            # Género vacío
            "platform": "Steam",
            "release_date": "fecha-mal",  # Formato incorrecto
            "price": -50            # Precio negativo
        }
    )
    assert response.status_code in (400, 422)


# Verifica que enviar la petición sin JSON genere error 422
def test_crear_juego_sin_json():
    response = client.post("/games/create")
    assert response.status_code == 422


# Verifica que un ID extremadamente grande produzca un error (400 o 500)
def test_error_interno_controlado():
    response = client.put(
        "/games/update/9999999999999999999999",
        json={
            "name": "Test",
            "genre": "Action",
            "platform": "Steam",
            "release_date": "2024-01-01",
            "price": 10.0
        }
    )
    assert response.status_code in (400, 500)
