import requests

# URL de tu API
url = "http://127.0.0.1:8000/api/v1/juegos"

try:
    response = requests.get(url)
    response.raise_for_status()  # Lanza una excepción para errores HTTP (4xx o 5xx)
    games_data = response.json()

    # Extraer los IDs
    game_ids = [game["id"] for game in games_data]

    # Ordenar y eliminar duplicados (aunque los IDs de DB suelen ser únicos y secuenciales, es una buena práctica)
    unique_sorted_ids = sorted(list(set(game_ids)))

    print("IDs de juegos únicos y ordenados:")
    for game_id in unique_sorted_ids:
        print(game_id)

except requests.exceptions.RequestException as e:
    print(f"Error al conectar con la API: {e}")
except KeyError:
    print("La respuesta de la API no tiene el formato esperado (falta la clave 'id').")
except Exception as e:
    print(f"Ocurrió un error inesperado: {e}")