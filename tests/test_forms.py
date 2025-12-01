from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def auth():
    r = client.post("/token", data={"username": "admin", "password": "1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def test_crear_juego_sin_json():
    headers = auth()
    response = client.post("/api/v1/juegos", headers=headers)
    assert response.status_code == 422


def test_crear_juego_campos_invalidos():
    headers = auth()
    response = client.post(
        "/api/v1/juegos",
        json={
            "title": "",
            "developer": "",
            "publisher": "",
            "genres": "",
            "price": -50
        },
        headers=headers,
    )
    assert response.status_code in (400, 422)


def test_error_interno_controlado():
    headers = auth()
    response = client.put(
        "/api/v1/juegos/999999999999",
        json={"title": "Test"},
        headers=headers,
    )
    assert response.status_code in (404, 500)
